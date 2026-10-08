// Browser storage records that survive a page reload: the jobs this browser submitted (until
// their results expire on the server), the circuit in the editor and the ticked run modes (per
// tab, with the last tab's values for a new tab), the playlist and small per-browser
// preferences. Leaf module: no imports.

const JOBS_KEY = 'rosetta_jobs';
const LEGACY_PENDING_KEY = 'rosetta_pending_job';
const EDITOR_KEY = 'rosetta_editor_circuit';
const MODES_KEY = 'rosetta_run_modes';
const SELECTION_KEY = 'rosetta_loaded_selection';
const BATCH_KEY = 'rosetta_batch_queue';

/** An unfinished job is offered for this long after it was submitted. */
export const UNFINISHED_MAX_AGE_MS = 6 * 60 * 60 * 1000;
/** A finished job is offered for as long as the server keeps its results (JOB_TTL_SEC). */
export const FINISHED_KEEP_MS = 30 * 60 * 1000;
const MAX_JOBS = 12;

function _area(kind) {
    try {
        return kind === 'session' ? globalThis.sessionStorage : globalThis.localStorage;
    } catch (_) {
        return undefined;
    }
}

function _read(key, kind = 'local') {
    try {
        const v = JSON.parse(_area(kind)?.getItem(key) || 'null');
        return v && typeof v === 'object' ? v : null;
    } catch (_) {
        return null;
    }
}

/** @returns {boolean} false when the browser refused to store the value */
function _write(key, value, kind = 'local') {
    try {
        const area = _area(kind);
        if (!area) return false;
        if (value === null) area.removeItem(key);
        else area.setItem(key, JSON.stringify(value));
        return true;
    } catch (_) {
        return false;
    }
}

/** A stored string preference, or `fallback` when none is stored or storage is unavailable. */
export function readPref(key, fallback = '') {
    try { return localStorage.getItem(key) ?? fallback; } catch (_) { return fallback; }
}

/** @returns {boolean} false when the browser refused to store the value */
export function writePref(key, value) {
    try {
        if (value === null || value === '') localStorage.removeItem(key);
        else localStorage.setItem(key, value);
        return true;
    } catch (_) {
        return false;
    }
}

/**
 * @typedef {{ job_id: string, kind: 'single'|'batch'|'experiment', title: string,
 *             run_name?: string|null, circuit_name?: string|null, runner_config?: object,
 *             remaining?: string[], account?: string|null, submitted_at: number,
 *             state?: 'pending'|'stopped'|'finished', finished_at?: number }} StoredJob
 */

function _expired(job, now) {
    if (job.state === 'finished') return !(typeof job.finished_at === 'number' && now - job.finished_at <= FINISHED_KEEP_MS);
    return now - job.submitted_at > UNFINISHED_MAX_AGE_MS;
}

function _valid(job) {
    return !!job && typeof job.job_id === 'string' && typeof job.submitted_at === 'number';
}

/** @returns {StoredJob[]} every stored job, expired ones included */
function _allJobs() {
    const v = _read(JOBS_KEY);
    const list = v && Array.isArray(v.jobs) ? v.jobs.filter(_valid) : [];
    const legacy = _read(LEGACY_PENDING_KEY);
    if (legacy) {
        _write(LEGACY_PENDING_KEY, null);
        if (_valid(legacy) && !list.some(j => j.job_id === legacy.job_id)) list.push({ ...legacy, state: 'pending' });
    }
    return list;
}

function _saveJobs(list) {
    const sorted = [...list].sort((a, b) => b.submitted_at - a.submitted_at).slice(0, MAX_JOBS);
    _write(JOBS_KEY, sorted.length ? { jobs: sorted } : null);
}

/** Record a submitted job as pending; other recorded jobs are kept.
 * @param {StoredJob} job @param {number} [now] */
export function recordJob(job, now = Date.now()) {
    const list = _allJobs().filter(j => j.job_id !== job.job_id && !_expired(j, now));
    _saveJobs([...list, { ...job, state: 'pending' }]);
}

function _update(jobId, change, now) {
    const list = _allJobs().filter(j => !_expired(j, now));
    const i = list.findIndex(j => j.job_id === jobId);
    if (i < 0) return;
    list[i] = { ...list[i], ...change };
    _saveJobs(list);
}

/** The user stopped waiting for `jobId`; it keeps running on the server. */
export function markJobStopped(jobId, now = Date.now()) {
    _update(jobId, { state: 'stopped' }, now);
}

/** `jobId` finished; its results are offered until the server drops them. */
export function markJobFinished(jobId, now = Date.now()) {
    _update(jobId, { state: 'finished', finished_at: now }, now);
}

/** Forget `jobId`. */
export function forgetJob(jobId) {
    _saveJobs(_allJobs().filter(j => j.job_id !== jobId));
}

/** Forget every job submitted while signed in. */
export function forgetSignedInJobs() {
    _saveJobs(_allJobs().filter(j => !j.account));
}

/** @returns {StoredJob[]} the recorded jobs whose results can still be fetched, newest first */
export function listJobs(now = Date.now()) {
    const all = _allJobs();
    const live = all.filter(j => !_expired(j, now));
    if (live.length !== all.length) _saveJobs(live);
    return live.sort((a, b) => b.submitted_at - a.submitted_at);
}

/** @param {string} qasm @param {string} name */
export function saveEditorCircuit(qasm, name) {
    const value = { qasm, name, saved_at: Date.now() };
    _write(EDITOR_KEY, value, 'session');
    _write(EDITOR_KEY, value);
}

/** This tab's editor circuit, else the one saved last in any tab.
 * @returns {{ qasm: string, name: string }|null} */
export function loadEditorCircuit() {
    for (const kind of ['session', 'local']) {
        const v = _read(EDITOR_KEY, kind);
        if (v && typeof v.qasm === 'string' && v.qasm.trim() !== '') {
            return { qasm: v.qasm, name: typeof v.name === 'string' ? v.name : 'Custom / Modified' };
        }
    }
    return null;
}

/** The Generate Circuits choice that Load last put in the editor.
 * @param {{ value: string, qubits: number|null }|null} selection */
export function saveLoadedSelection(selection) {
    _write(SELECTION_KEY, selection, 'session');
    _write(SELECTION_KEY, selection);
}

/** This tab's last loaded Generate Circuits choice, else the last one in any tab, else null.
 * @returns {{ value: string, qubits: number|null }|null} */
export function loadLoadedSelection() {
    for (const kind of ['session', 'local']) {
        const v = _read(SELECTION_KEY, kind);
        if (v && typeof v.value === 'string') return { value: v.value, qubits: Number.isFinite(v.qubits) ? v.qubits : null };
    }
    return null;
}

/** @param {{ statevector: boolean, measured: boolean }} modes */
export function saveRunModes(modes) {
    const value = { statevector: !!modes.statevector, measured: !!modes.measured };
    _write(MODES_KEY, value, 'session');
    _write(MODES_KEY, value);
}

/** This tab's ticked modes, else the ones ticked last in any tab, else null.
 * @returns {{ statevector: boolean, measured: boolean }|null} */
export function loadRunModes() {
    for (const kind of ['session', 'local']) {
        const v = _read(MODES_KEY, kind);
        if (v && typeof v.statevector === 'boolean' && typeof v.measured === 'boolean') {
            return { statevector: v.statevector, measured: v.measured };
        }
    }
    return null;
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
