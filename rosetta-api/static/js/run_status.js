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
 * The runner's dispatch_status, or for reports without one, a classification of the
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

/**
 * The basis ('direct' or 'bit_reversal') in which a pair matches although its declared
 * qubit orderings imply the other one, or null.
 * @returns {string|null}
 */
export function unalignedBasis(p) {
    const v = p?.metrics?.unaligned_basis_match ?? p?.unaligned_basis_match;
    if (typeof v === 'string' && v) return v;
    return v === true || p?.agreement === 'unaligned_basis_match' ? 'unrecorded' : null;
}

/** True when a pair matches only in a basis its declared qubit orderings do not imply. */
export function unalignedBasisMatch(p) {
    return unalignedBasis(p) !== null;
}

/**
 * Group of a statevector pair: 'agree' (directly, up to a global phase, or after
 * normalisation), 'bit_order' (after the bit reversal the declared orderings imply),
 * 'disagree' (residual, only after an undeclared qubit permutation, or only in an
 * unaligned basis), 'not_comparable', or 'other'.
 * @returns {'agree'|'bit_order'|'disagree'|'not_comparable'|'other'}
 */
export function statevectorGroup(p) {
    if (p?.agreement === 'not_comparable') return 'not_comparable';
    if (unalignedBasisMatch(p)) return 'disagree';
    const label = effectiveAgreement(p);
    if (label === 'residual_disagreement' || label === 'agree_after_qubit_permutation') return 'disagree';
    if (label === 'agree_directly' || label === 'agree_up_to_global_phase') return 'agree';
    if (label === 'agree_after_bit_reversal') return 'bit_order';
    return 'other';
}

/** True when the pair's outputs disagree by the evidence the report records. */
export function isDisagreement(p) {
    if (p?.mode === 'measured') {
        if (p.marginal_assessment === 'marginal_distinguishable') return true;
        const a = measuredAssessment(p);
        if (a) return a === 'distinguishable';
        return p.agreement === 'distance_exceeds_threshold';
    }
    return statevectorGroup(p) === 'disagree';
}

/** Power of the pair's shot-noise test to detect the target total-variation gap, or null. */
export function pairPower(p) {
    const v = p?.metrics?.statistical_test?.power?.power_to_detect_delta_at_observed_shots;
    return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

/**
 * Significance level the power figure was computed at, the pair-family size, the
 * Benjamini–Yekutieli constant c_m and the run's α, as far as the pair records them.
 * @returns {{ alphaUsed: number|null, m: number|null, alpha: number|null, cm: number|null }}
 */
export function pairPowerLevel(p) {
    const st = p?.metrics?.statistical_test || {};
    const power = st.power || {};
    const num = v => (typeof v === 'number' && Number.isFinite(v) ? v : null);
    const cm = num(power.c_m ?? power.by_constant ?? power.harmonic_constant);
    return { alphaUsed: num(power.alpha_used), m: num(power.m_pairs), alpha: num(st.alpha), cm };
}

/** Whether more shots can resolve an inconclusive pair: true, false, or null when not recorded. */
export function resolvableByMoreShots(p) {
    const st = p?.metrics?.statistical_test || {};
    const v = st.resolvable_by_more_shots ?? st.power?.resolvable_by_more_shots;
    return typeof v === 'boolean' ? v : null;
}

/** Shots per backend the power model recommends for a pair, and whether that exceeds the shots used. */
export function pairRecommendation(p) {
    const st = p?.metrics?.statistical_test || {};
    const power = st.power || {};
    const pick = [power.recommended_shots_per_backend, st.recommended_shots_per_backend,
        p?.recommended_shots_per_backend, power.shots_per_backend_for_target_power];
    const shots = pick.find(n => typeof n === 'number' && Number.isFinite(n)) ?? null;
    let exceeds = [power.recommended_exceeds_actual, st.recommended_exceeds_actual, p?.recommended_exceeds_actual]
        .find(v => typeof v === 'boolean');
    if (exceeds === undefined) {
        const used = Object.values(st.n_shots || {}).filter(n => typeof n === 'number');
        exceeds = shots !== null && used.length > 0 && shots > Math.min(...used);
    }
    return { shots, exceeds };
}

/** Largest recommended shots-per-backend across the pairs whose recommendation exceeds the shots used, or null. */
export function recommendedShots(pairs) {
    let best = null;
    (pairs || []).forEach(p => {
        const { shots, exceeds } = pairRecommendation(p);
        if (exceeds && shots !== null && (best === null || shots > best)) best = shots;
    });
    return best;
}

/** @type {Array<[RegExp, string]>} */
const OPERATOR_HINTS = [
    [/\s*Server operators can check whether its service is running\.?/gi, ' The backend may be restarting; try again in a minute. If it keeps happening, tell the administrator of this server.'],
    [/\s*Server operators can see details in the runner( pod)? logs\.?/gi, ' If it happens again, tell the administrator of this server.'],
    [/raise the timeout\./g, 'raise the timeout in the Execution chip.'],
    [/\s*Check the \S+ container logs( to confirm)?\.?/gi, ' If it happens again, tell the administrator of this server.'],
    [/\s*Check container logs in your Kubernetes cluster\.?/gi, ' If it happens again, tell the administrator of this server.'],
    [/\s*Check that its container is running\.?/gi, ' The backend may be restarting; try again in a minute.'],
];

/** A runner error message with server-operator instructions replaced by ones a UI user can act on. */
export function userFacingError(msg) {
    if (msg === null || msg === undefined) return msg;
    let text = String(msg);
    OPERATOR_HINTS.forEach(([re, repl]) => { text = text.replace(re, repl); });
    return text;
}

/**
 * Short name of the multiple-testing correction a report or pair records: 'BY'
 * (Benjamini–Yekutieli) or 'BH' (Benjamini–Hochberg). Reports without a correction field
 * show 'BH'.
 */
export function correctionName(...records) {
    for (const r of records) {
        const c = r?.correction;
        const list = Array.isArray(c) ? c : (c ? [c] : []);
        const text = list.map(v => String(v).toLowerCase()).join(' ');
        if (/\bby\b|yekutieli/.test(text)) return 'BY';
        if (/\bbh\b|hochberg/.test(text)) return 'BH';
    }
    return 'BH';
}

/** The correction's full name for prose. */
export function correctionLongName(short) {
    return short === 'BY' ? 'Benjamini–Yekutieli' : 'Benjamini–Hochberg';
}

/** Multiplicity-adjusted p-value of one test block (chi2 or g_test). */
export function adjustedPValue(test) {
    return test?.p_value_adjusted ?? test?.p_value_by ?? test?.p_value_bh;
}

/** Whether one test block is significant after the multiplicity adjustment. */
export function adjustedSignificant(test) {
    return test?.significant_adjusted ?? test?.significant_by ?? test?.significant_bh;
}
