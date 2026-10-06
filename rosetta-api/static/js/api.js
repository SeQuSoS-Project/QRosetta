// Frontend logic for api functionality.

import { getState } from './state.js';
import { renderBatchProgress, setRunKicker, updateRunnerStatuses } from './status_cards.js';

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

/** FastAPI `detail` as text: a string as is, validation errors as "field: message" lines. */
export function apiDetailText(detail) {
    if (detail === undefined || detail === null) return '';
    if (Array.isArray(detail)) {
        return detail.map(d => {
            const loc = Array.isArray(d?.loc) ? d.loc.filter(x => x !== 'body').join('.') : '';
            const msg = typeof d?.msg === 'string' ? d.msg.replace(/^(Value|Assertion) error,\s*/i, '') : JSON.stringify(d);
            return `${loc ? `${loc}: ` : ''}${msg}`;
        }).join('\n');
    }
    return typeof detail === 'string' ? detail.replace(/^(Value|Assertion) error,\s*/i, '') : JSON.stringify(detail);
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
    const kind = res.status === 400 || res.status === 422 ? 'The server rejected the request'
        : res.status === 429 ? 'Too many requests' : 'Request failed';
    return `${kind} (HTTP ${res.status}): ${message || res.statusText}`;
}

let _stopPolling = false;

/** Make the poll in progress stop at its next check, rejecting with `stopped: true`; the job keeps running. */
export function stopPolling() {
    _stopPolling = true;
}

export async function pollJobStatus(jobId) {
    _stopPolling = false;
    return new Promise((resolve, reject) => {
        let networkErrorCount = 0;
        const MAX_NETWORK_ERRORS = 4;

        const checkStatus = async () => {
            if (_stopPolling) {
                reject(Object.assign(new Error('Stopped waiting. The job keeps running on the server.'), { stopped: true }));
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
                networkErrorCount = 0;

                if (data.runner_statuses) {
                    updateRunnerStatuses(data.runner_statuses);
                }

                renderBatchProgress(data.progress);

                if (data.status === "completed") {
                    resolve(data.results);
                } else if (data.status === "failed") {
                    const r = data.results;
                    const hasResults = r && ((Array.isArray(r.raw_results) && r.raw_results.length > 0)
                        || (Array.isArray(r.benchmark_summary) && r.benchmark_summary.length > 0));
                    if (hasResults) {
                        resolve({ ...r, job_error: data.error || 'Every backend failed on this circuit.' });
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