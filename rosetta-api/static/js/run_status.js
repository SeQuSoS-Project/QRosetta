// Per-runner outcome (ok / error / timeout / offline) and agreement-label groups.
// Leaf module: no imports.

export function isConnectionError(errorMsg) {
    if (!errorMsg) return false;
    const msg = String(errorMsg).toLowerCase();
    return msg.includes("connection refused") ||
        msg.includes("name or service not known") ||
        msg.includes("failed to connect") ||
        msg.includes("failed to fetch") ||
        msg.includes("load resource") ||
        msg.includes("failed to get response") ||
        msg.includes("502 bad gateway") ||
        msg.includes("service unavailable") ||
        msg.includes("failed to decode json");
}

const DISPATCH_STATUSES = new Set(['ok', 'error', 'timeout', 'offline']);

/**
 * The runner's dispatch_status, or for reports that predate it, a classification of the
 * error text.
 * @returns {'ok'|'error'|'timeout'|'offline'}
 */
export function runnerStatus(result) {
    if (!result) return 'offline';
    if (DISPATCH_STATUSES.has(result.dispatch_status)) return result.dispatch_status;
    if (!result.error) return 'ok';
    if (isConnectionError(result.error)) return 'offline';
    if (/time(d)?\s?out/i.test(String(result.error))) return 'timeout';
    return 'error';
}

export const RUNNER_STATUS_LABEL = { ok: 'OK', error: 'Error', timeout: 'Timeout', offline: 'Offline' };

/** STATUS_STYLES key for a runner status. */
export const RUNNER_STATUS_STYLE = { ok: 'success', error: 'error', timeout: 'timeout', offline: 'offline' };

/** simulator key -> runner status, for every entry of a report's raw_results. */
export function statusBySimulator(rawResults) {
    const map = new Map();
    (Array.isArray(rawResults) ? rawResults : []).forEach(r => {
        if (r && r.simulator !== undefined) map.set(r.simulator, runnerStatus(r));
    });
    return map;
}

export const DIRECT_AGREEMENT = new Set(['agree_directly', 'agree_up_to_global_phase', 'distance_within_threshold']);
export const TRANSFORM_AGREEMENT = new Set(['agree_after_bit_reversal', 'agree_after_qubit_permutation', 'agree_after_normalization']);
export const UNEXPLAINED = new Set(['residual_disagreement', 'distance_exceeds_threshold']);
