// Frontend logic for api functionality.

import { formatBytes, jsonBytes } from './request_limits.js';
import { attachSummary, lacksVerdicts, summaryInput } from './run_status.js';
import { getState } from './state.js';
import { renderBatchProgress, setRunKicker, updateJobPhase, updateRunnerStatuses } from './status_cards.js';

export let BASE_URL = '';
if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    BASE_URL = window.location.origin;
}

export function getAuthHeaders(extraHeaders = {}) {
    const headers = { ...extraHeaders };
    if (getState().authToken) {
        headers['Authorization'] = `Bearer ${getState().authToken}`;
    }
    return headers;
}

/** FastAPI `detail` as text: a string as is, validation errors as "field: message" lines; a
 * message that already starts with its field name ("email must be ...") is not prefixed again. */
export function apiDetailText(detail) {
    if (detail === undefined || detail === null) return '';
    if (Array.isArray(detail)) {
        return detail.map(d => {
            const path = Array.isArray(d?.loc) ? d.loc.filter(x => x !== 'body') : [];
            const loc = path.join('.');
            const msg = typeof d?.msg === 'string' ? d.msg.replace(/^(Value|Assertion) error,\s*/i, '') : JSON.stringify(d);
            const field = String(path[path.length - 1] ?? '');
            if (field && msg.toLowerCase().startsWith(`${field.toLowerCase()} `)) return msg.charAt(0).toUpperCase() + msg.slice(1);
            return `${loc ? `${loc}: ` : ''}${msg}`;
        }).join('\n');
    }
    return typeof detail === 'string' ? detail.replace(/^(Value|Assertion) error,\s*/i, '') : JSON.stringify(detail);
}

/** The error text for an HTTP status and the server's message: the message alone for refusals
 * that explain themselves (401, 403, 404, 409), else prefixed with what kind of failure it was. */
export function apiErrorText(status, message, statusText = '') {
    const text = message || statusText;
    if ([401, 403, 404, 409].includes(status) && message) return message;
    const kind = status === 400 || status === 422 ? 'The server rejected the request'
        : status === 429 ? 'Too many requests' : 'Request failed';
    return `${kind} (HTTP ${status}): ${text}`;
}

/** The message of an HTML error page from a proxy in front of the API (502, 503, 504). */
export const API_NOT_ANSWERING = 'The API did not answer, and the proxy in front of it returned an error page. '
    + 'The server may be restarting; try again in a minute.';

/**
 * The server's message in an error body: FastAPI's `detail` (a string, or a list of validation
 * errors with their field paths), else `error`, else the body itself. An HTML page is never
 * shown as source: for 502, 503 and 504 it reads API_NOT_ANSWERING, otherwise it gives no
 * message.
 * @param {number} status
 * @param {string} body
 * @param {string} [contentType]
 */
export function errorBodyText(status, body, contentType = '') {
    try {
        const data = JSON.parse(body);
        const text = apiDetailText(data?.detail ?? data?.error ?? data?.message);
        if (text) return text;
    } catch (_) { /* body is not JSON */ }
    if (/text\/html/i.test(contentType) || /^\s*</.test(body)) {
        return [502, 503, 504].includes(status) ? API_NOT_ANSWERING : '';
    }
    return body;
}

/**
 * The error text of a rejected API request (see errorBodyText).
 * @param {Response} res
 */
export async function formatApiError(res) {
    const body = await res.text().catch(() => '');
    return apiErrorText(res.status, errorBodyText(res.status, body, res.headers?.get?.('content-type') || ''), res.statusText);
}

/** GET a summary route; null when the server no longer holds the job or run (404). */
async function _getSummary(path) {
    const res = await fetch(`${BASE_URL}${path}`, { headers: getAuthHeaders() });
    if (res.status === 404) return null;
    if (!res.ok) throw new Error(await formatApiError(res));
    return await res.json();
}

/**
 * The report, with the server's verdicts attached when it does not record them (analysis
 * versions before divergence-2026.10.27.1, or an analysis that failed): from the job's summary
 * while the server holds the job, the saved run's summary for a run from History, else
 * POST /summary with the fields it reads. Throws when the verdicts cannot be fetched.
 * @param {any} report
 * @param {{ jobId?: string|null, runId?: string|null }} [source]
 */
export async function withVerdicts(report, { jobId = null, runId = null } = {}) {
    if (!lacksVerdicts(report)) return report;
    let summary = null;
    if (jobId) summary = await _getSummary(`/jobs/${encodeURIComponent(jobId)}/summary`);
    if (!summary && runId) summary = await _getSummary(`/history/runs/${encodeURIComponent(runId)}/summary`);
    if (!summary) {
        const body = summaryInput(report);
        const limit = getState().maxRequestBytes;
        if (typeof limit === 'number' && jsonBytes(body) > limit) {
            throw new Error(`The verdicts of this report could not be fetched: its pair records are ${formatBytes(jsonBytes(body))}, `
                + `over the server's upload limit of ${formatBytes(limit)}.`);
        }
        const res = await fetch(`${BASE_URL}/summary`, {
            method: 'POST',
            headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error(`The verdicts of this report could not be fetched: ${await formatApiError(res)}`);
        summary = await res.json();
    }
    attachSummary(report, summary);
    return report;
}

let _stopPolling = false;
/** @type {Set<() => void>} */
const _activePolls = new Set();

/** Stop the poll in progress now, rejecting it with `stopped: true`; the job keeps running.
 * Stays set until resetStopPolling(), so a press between two planned runs also stops the second. */
export function stopPolling() {
    _stopPolling = true;
    [..._activePolls].forEach(stop => stop());
}

/** Clear a Stop waiting request before starting new runs. */
export function resetStopPolling() {
    _stopPolling = false;
}

/** Whether Stop waiting was pressed since the last resetStopPolling(). */
export function pollingStopped() {
    return _stopPolling;
}

/** Milliseconds between polls of a job that is running. */
export const POLL_EVERY_MS = 3000;
/** How long the page keeps polling while the server gives no answer (no connection, or HTTP 502,
 * 503 or 504 from a proxy) or answers with an error status: 5 minutes, longer than an API restart. */
export const POLL_OUTAGE_PATIENCE_MS = 5 * 60 * 1000;
const POLL_BACKOFF_MAX_MS = 30000;
const MAX_HANDLING_ERRORS = 4;

/** The wait before the next poll after `failures` failed polls in a row: 3, 6, 12, 24, then 30 s. */
export function pollRetryDelay(failures) {
    return Math.min(POLL_EVERY_MS * 2 ** Math.max(0, failures - 1), POLL_BACKOFF_MAX_MS);
}

/** The message of a job the server no longer has; `afterOutage` when polls failed before the 404. */
export function lostJobText(afterOutage) {
    return afterOutage
        ? 'The server did not answer for a while and now has no record of this job: it restarted, and a restart '
            + 'loses every job in progress. Submit the run again.'
        : 'The server has no record of this job. It may have expired or the server may have restarted.';
}

/** The message when the page stops polling after `minutes` without an answer; `last` is the last failure. */
export function outageText(minutes, last) {
    return `The server did not answer for ${minutes} minutes (last: ${last}). The job may still be running there: `
        + 'reload this page when the server is back, and Earlier runs from this browser offers the job again.';
}

/**
 * Poll GET /jobs/{id} until the job finishes: every POLL_EVERY_MS while it runs. A poll with no
 * answer or an error status is repeated after pollRetryDelay, and the page shows that it is
 * waiting for the server; after POLL_OUTAGE_PATIENCE_MS of failures in a row it stops waiting.
 * A 404 ends the wait as terminal (lostJobText).
 * @param {string} jobId
 */
export async function pollJobStatus(jobId) {
    return new Promise((outerResolve, outerReject) => {
        let failures = 0;
        let failingSince = null;
        let handlingErrors = 0;
        let timer = null;
        let settled = false;
        const finish = (fn, value) => {
            if (settled) return;
            settled = true;
            clearTimeout(timer);
            _activePolls.delete(stop);
            fn(value);
        };
        const resolve = value => finish(outerResolve, value);
        const reject = err => finish(outerReject, err);
        const stop = () => reject(Object.assign(new Error('Stopped waiting. The job keeps running on the server.'), { stopped: true }));
        const setTimeout = (fn, ms) => { timer = globalThis.setTimeout(fn, ms); };
        _activePolls.add(stop);

        /** @param {string} what */
        const failed = what => {
            failures++;
            const now = Date.now();
            if (failingSince === null) failingSince = now;
            if (now - failingSince >= POLL_OUTAGE_PATIENCE_MS) {
                reject(new Error(outageText(Math.round(POLL_OUTAGE_PATIENCE_MS / 60000), what)));
                return;
            }
            const delay = pollRetryDelay(failures);
            console.warn(`[poll] No answer for job ${jobId} (${what}); polling again in ${delay / 1000} s.`);
            setRunKicker(`Waiting for the server (${what}); checking again in ${delay / 1000} s`);
            setTimeout(checkStatus, delay);
        };

        const checkStatus = async () => {
            if (settled) return;
            if (_stopPolling) {
                stop();
                return;
            }
            let res;
            try {
                res = await fetch(`${BASE_URL}/jobs/${jobId}`, {
                    headers: getAuthHeaders()
                });
            } catch (_) {
                failed('no connection');
                return;
            }
            if (settled) return;
            if (res.status === 404) {
                reject(Object.assign(new Error(lostJobText(failures > 0)), { terminal: true }));
                return;
            }
            if (!res.ok) {
                const body = await res.text().catch(() => '');
                const text = errorBodyText(res.status, body, res.headers?.get?.('content-type') || '');
                failed(`HTTP ${res.status}${text && text !== API_NOT_ANSWERING ? `: ${text.slice(0, 200)}` : ''}`);
                return;
            }
            let data;
            try {
                data = await res.json();
            } catch (_) {
                failed('an answer that is not JSON');
                return;
            }
            if (settled) return;
            failures = 0;
            failingSince = null;
            try {
                updateJobPhase(data.phase);
                if (data.runner_statuses) {
                    updateRunnerStatuses(data.runner_statuses);
                }

                renderBatchProgress(data.progress);

                if (data.status === "completed") {
                    resolve(await withVerdicts(data.results, { jobId }));
                } else if (data.status === "failed") {
                    const r = data.results;
                    const hasResults = r && ((Array.isArray(r.raw_results) && r.raw_results.length > 0)
                        || (Array.isArray(r.benchmark_summary) && r.benchmark_summary.length > 0));
                    if (hasResults) {
                        resolve(await withVerdicts({ ...r, job_error: data.error || 'Every backend failed on this circuit.' }, { jobId }));
                    } else {
                        reject(Object.assign(new Error(data.error || data.results?.error || 'The job failed on the server without an error message.'), { terminal: true }));
                    }
                } else {
                    handlingErrors = 0;
                    const executionMode = getState().executionMode;
                    const targetName = executionMode === 'local' ? "this server's runners"
                        : executionMode === 'kubernetes' ? 'the Kubernetes cluster' : 'the server';
                    setRunKicker(`Running on ${targetName}`);
                    setTimeout(checkStatus, POLL_EVERY_MS);
                }
            } catch (err) {
                handlingErrors++;
                if (handlingErrors <= MAX_HANDLING_ERRORS) {
                    console.warn(`[poll] Job ${jobId}: ${err.message} (attempt ${handlingErrors}/${MAX_HANDLING_ERRORS})`);
                    setTimeout(checkStatus, POLL_EVERY_MS);
                } else {
                    reject(err);
                }
            }
        };
        setTimeout(checkStatus, 1500);
    });
}

export async function fetchMQTBench(algorithm, qubits) {
    const res = await fetch(`${BASE_URL}/benchmarks/mqt?algorithm=${encodeURIComponent(algorithm)}&qubits=${encodeURIComponent(qubits)}`, {
        headers: getAuthHeaders()
    });
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(apiDetailText(errorData.detail) || `Failed to fetch MQT Bench: ${res.status}`);
    }
    return await res.json();
}

export async function fetchQASMBench(circuit) {
    const res = await fetch(`${BASE_URL}/benchmarks/qasmbench?circuit=${encodeURIComponent(circuit)}`, {
        headers: getAuthHeaders()
    });
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(apiDetailText(errorData.detail) || `Failed to fetch QASMBench: ${res.status}`);
    }
    return await res.json();
}

export async function fetchMQTList() {
    const res = await fetch(`${BASE_URL}/benchmarks/mqt/list`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error(`Failed to fetch MQT list: ${res.status}`);
    return await res.json();
}

export async function fetchQASMBenchList() {
    const res = await fetch(`${BASE_URL}/benchmarks/qasmbench/list`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error(`Failed to fetch QASMBench list: ${res.status}`);
    return await res.json();
}