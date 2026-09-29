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
export const TRANSFORM_AGREEMENT = new Set(['agree_after_bit_reversal', 'agree_after_qubit_permutation']);
export const UNEXPLAINED = new Set(['residual_disagreement', 'distance_exceeds_threshold']);

/**
 * The label a pair would carry without the normalisation note: for
 * agree_after_normalization, the label the normalised vectors received.
 */
export function effectiveAgreement(p) {
    if (p?.agreement === 'agree_after_normalization') return p.metrics?.normalized_agreement || 'agree_directly';
    return p?.agreement;
}

const VERDICT_TO_ASSESSMENT = {
    consistent: 'consistent_within_shot_noise',
    inconclusive_low_shots: 'inconclusive_low_shots',
    distinguishable: 'distinguishable',
    ambiguous: 'ambiguous',
};

/**
 * Shot-noise assessment of a measured pair: measured_assessment when the report has it,
 * else derived from the statistical-test verdict; null when neither is recorded.
 * @returns {'consistent_within_shot_noise'|'inconclusive_low_shots'|'distinguishable'|'ambiguous'|'not_comparable'|null}
 */
export function measuredAssessment(p) {
    if (!p) return null;
    const recorded = p.measured_assessment ?? p.metrics?.measured_assessment;
    if (recorded) return recorded;
    if (p.agreement === 'not_comparable') return 'not_comparable';
    const verdict = p.metrics?.statistical_test?.verdict;
    return VERDICT_TO_ASSESSMENT[verdict] || null;
}

/** True when the pair's outputs disagree by the evidence the report records. */
export function isDisagreement(p) {
    if (p?.mode === 'measured') {
        const a = measuredAssessment(p);
        if (a) return a === 'distinguishable';
        return p.agreement === 'distance_exceeds_threshold';
    }
    return p?.agreement === 'residual_disagreement';
}

/** Largest shots-per-backend the power model recommends across these pairs, or null. */
export function recommendedShots(pairs) {
    let best = null;
    (pairs || []).forEach(p => {
        const n = p?.metrics?.statistical_test?.power?.shots_per_backend_for_target_power;
        if (typeof n === 'number' && Number.isFinite(n) && (best === null || n > best)) best = n;
    });
    return best;
}

/** @type {Array<[RegExp, string]>} */
const OPERATOR_HINTS = [
    [/\s*Check the \S+ container logs( to confirm)?\.?/gi, ' If it happens again, report it to the administrator of this server.'],
    [/\s*Check container logs in your Kubernetes cluster\.?/gi, ' If it happens again, report it to the administrator of this server.'],
    [/\s*Check that its container is running\.?/gi, ' The runner may be restarting; try again in a minute.'],
];

/** A runner error message with server-operator instructions replaced by ones a UI user can act on. */
export function userFacingError(msg) {
    if (msg === null || msg === undefined) return msg;
    let text = String(msg);
    OPERATOR_HINTS.forEach(([re, repl]) => { text = text.replace(re, repl); });
    return text;
}
