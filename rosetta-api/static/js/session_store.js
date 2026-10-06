// localStorage records that survive a page reload: the job submitted last (until its
// results are shown), the circuit in the editor and the batch queue. Leaf module: no imports.

const PENDING_KEY = 'rosetta_pending_job';
const EDITOR_KEY = 'rosetta_editor_circuit';
const BATCH_KEY = 'rosetta_batch_queue';
const PENDING_MAX_AGE_MS = 6 * 60 * 60 * 1000;

function _read(key) {
    try {
        const v = JSON.parse(localStorage.getItem(key) || 'null');
        return v && typeof v === 'object' ? v : null;
    } catch (_) {
        return null;
    }
}

/** @returns {boolean} false when the browser refused to store the value */
function _write(key, value) {
    try {
        if (value === null) localStorage.removeItem(key);
        else localStorage.setItem(key, JSON.stringify(value));
        return true;
    } catch (_) {
        return false;
    }
}

/**
 * @typedef {{ job_id: string, kind: 'single'|'batch', title: string, run_name?: string|null,
 *             circuit_name?: string|null,
 *             runner_config?: object, submitted_at: number }} PendingJob
 */

/** @param {PendingJob} job */
export function savePendingJob(job) {
    _write(PENDING_KEY, job);
}

/** @returns {PendingJob|null} the recorded job, or null if none or older than six hours */
export function loadPendingJob() {
    const job = _read(PENDING_KEY);
    if (!job || typeof job.job_id !== 'string') return null;
    if (typeof job.submitted_at !== 'number' || Date.now() - job.submitted_at > PENDING_MAX_AGE_MS) {
        _write(PENDING_KEY, null);
        return null;
    }
    return job;
}

/** Forget the recorded job, or only the given one if another has replaced it. */
export function clearPendingJob(jobId) {
    const job = _read(PENDING_KEY);
    if (!job || jobId === undefined || job.job_id === jobId) _write(PENDING_KEY, null);
}

/** @param {string} qasm @param {string} name */
export function saveEditorCircuit(qasm, name) {
    _write(EDITOR_KEY, { qasm, name, saved_at: Date.now() });
}

/** @returns {{ qasm: string, name: string }|null} */
export function loadEditorCircuit() {
    const v = _read(EDITOR_KEY);
    if (!v || typeof v.qasm !== 'string' || v.qasm.trim() === '') return null;
    return { qasm: v.qasm, name: typeof v.name === 'string' ? v.name : 'Custom / Modified' };
}

/** @param {Array<object>} queue @returns {boolean} false when the queue could not be stored */
export function saveBatchQueue(queue) {
    return _write(BATCH_KEY, queue.length ? { queue, saved_at: Date.now() } : null);
}

/** @returns {Array<object>} the stored batch queue, or [] */
export function loadBatchQueue() {
    const v = _read(BATCH_KEY);
    return v && Array.isArray(v.queue) ? v.queue.filter(item => item && typeof item === 'object') : [];
}
