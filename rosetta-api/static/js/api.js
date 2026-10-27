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

/**
 * The error text of a rejected API request: FastAPI's `detail` (a string, or a list of
 * validation errors with their field paths), else `error`, else the raw body.
 * @param {Response} res
 */
export async function formatApiError(res) {
    const body = await res.text().catch(() => '');
    let message = body;
    try {
        const data = JSON.parse(body);
        message = apiDetailText(data?.detail ?? data?.error ?? data?.message) || body;
    } catch (_) { /* body is not JSON */ }
    return apiErrorText(res.status, message, res.statusText);
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

export async function pollJobStatus(jobId) {
    return new Promise((outerResolve, outerReject) => {
        let networkErrorCount = 0;
        const MAX_NETWORK_ERRORS = 4;
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

        const checkStatus = async () => {
            if (settled) return;
            if (_stopPolling) {
                stop();
                return;
            }
            try {
                const res = await fetch(`${BASE_URL}/jobs/${jobId}`, {
                    headers: getAuthHeaders()
                });
                if (res.status === 404) {
                    reject(Object.assign(new Error('The server has no record of this job. It may have expired or the server may have restarted.'), { terminal: true }));
                    return;
                }
                if (!res.ok) {
                    throw new Error(`Failed to fetch job status: ${res.status}`);
                }
                const data = await res.json();
                if (settled) return;
                networkErrorCount = 0;

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

                    const executionMode = getState().executionMode;
                    const targetName = executionMode === 'local' ? "this server's runners"
                        : executionMode === 'kubernetes' ? 'the Kubernetes cluster' : 'the server';
                    setRunKicker(`Running on ${targetName}`);
                    setTimeout(checkStatus, 3000);
                }
            } catch (err) {
                networkErrorCount++;
                if (networkErrorCount <= MAX_NETWORK_ERRORS) {
                    console.warn(`[poll] Network error for job ${jobId} (attempt ${networkErrorCount}/${MAX_NETWORK_ERRORS}):`, err.message);
                    setTimeout(checkStatus, 3000);
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