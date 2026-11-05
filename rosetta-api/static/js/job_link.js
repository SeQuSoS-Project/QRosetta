// The page's link to a job, /#job=<id>: the job id from the URL fragment, and the kind and
// title of a job this browser did not submit, read from its GET /jobs/{id} envelope. Pure.
// share.html keeps its token in its own fragment; this page reads only the job= form.

export const JOB_LINK_PREFIX = '#job=';
const JOB_ID = /^[A-Za-z0-9][A-Za-z0-9-]{7,63}$/;

/** The job id of a `#job=<id>` fragment, or null for any other fragment. */
export function linkedJobId(hash) {
    if (typeof hash !== 'string' || !hash.startsWith(JOB_LINK_PREFIX)) return null;
    let id;
    try {
        id = decodeURIComponent(hash.slice(JOB_LINK_PREFIX.length));
    } catch (_) {
        return null;
    }
    return JOB_ID.test(id) ? id : null;
}

/** 'experiment', 'batch' or 'single', from a job envelope (null when it could not be read). */
export function linkedJobKind(envelope) {
    const results = envelope && typeof envelope === 'object' ? envelope.results : null;
    if (results && typeof results === 'object') {
        if (results.experiment_summary) return 'experiment';
        if (Array.isArray(results.benchmark_summary)) return 'batch';
        return 'single';
    }
    return envelope && envelope.progress ? 'batch' : 'single';
}

/** The run's name from its report, else "Job <first 8 characters>". */
export function linkedJobTitle(envelope, jobId) {
    const results = envelope && typeof envelope === 'object' ? envelope.results : null;
    for (const key of ['run_name', 'circuit_name', 'task_name']) {
        const value = results && typeof results === 'object' ? results[key] : null;
        if (typeof value === 'string' && value.trim()) return value;
    }
    return `Job ${String(jobId).slice(0, 8)}`;
}

/** What the page says when the server has no job `jobId`; `keptFor` is the retention as text. */
export function missingJobText(jobId, keptFor) {
    return `The server has no job ${String(jobId).slice(0, 8)}. It keeps a finished job for up to ${keptFor} `
        + 'after it finishes and forgets every job when it restarts, so this link has expired. '
        + 'A run made with the qrosetta command saved its results on that machine: '
        + `qrosetta show summary --result job:${String(jobId).slice(0, 8)}`;
}
