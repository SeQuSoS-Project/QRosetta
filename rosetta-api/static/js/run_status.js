// Per-runner outcome (ok / error / timeout / offline) and pair verdicts. The verdicts come from
// the server: a report records them (pair_verdict, divergence_report.backend_verdicts), and for
// one that does not, the server's summary is attached here. Leaf module: no imports.

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

const _pairVerdicts = new WeakMap();
const _reportVerdicts = new WeakMap();

/**
 * @typedef {{ verdict: string, differs: boolean, differs_by_only: boolean, differs_full: boolean,
 *             differs_marginal: boolean, agrees: boolean, inconclusive: boolean, assessment: any,
 *             statevector_group: 'agree'|'bit_order'|'disagree'|'not_comparable'|'other',
 *             effective_agreement: any, unaligned_basis: string|null }} PairVerdict
 */

/**
 * A pair's verdict record: its recorded pair_verdict, else the one the server's summary gave
 * for it (attachSummary). Throws for a pair that has neither.
 * @returns {PairVerdict}
 */
export function pairVerdict(p) {
    const recorded = p?.pair_verdict;
    if (recorded && typeof recorded === 'object' && typeof recorded.differs === 'boolean') return recorded;
    const attached = p && typeof p === 'object' ? _pairVerdicts.get(p) : undefined;
    if (attached) return attached;
    throw new Error('A pair of this report has no verdict from the server.');
}

/** The pair's verdict record, or null when it has none. */
export function pairVerdictOrNull(p) {
    try { return pairVerdict(p); } catch { return null; }
}

/** A single-circuit report's per-backend counts as the server records them (snake_case):
 * divergence_report.backend_verdicts, else the server's summary attached to the report. */
export function reportBackendVerdicts(report) {
    const recorded = report?.divergence_report?.backend_verdicts;
    if (recorded && typeof recorded === 'object' && Array.isArray(recorded.backends)
        && recorded.headline_model && typeof recorded.headline_model === 'object') return recorded;
    const attached = report && typeof report === 'object' ? _reportVerdicts.get(report) : undefined;
    if (attached) return attached;
    throw new Error('This report has no per-backend verdicts from the server.');
}

/** The circuit reports of a playlist report, else the report itself. */
function _tasks(report) {
    return Array.isArray(report?.benchmark_summary) ? report.benchmark_summary : [report];
}

function _pairsOf(task) {
    const pairs = task?.divergence_report?.pairwise_agreement;
    return Array.isArray(pairs) ? pairs : [];
}

function _hasVerdicts(task) {
    if (!task || typeof task !== 'object') return true;
    const pairs = _pairsOf(task);
    if (!pairs.length && !(Array.isArray(task.raw_results) && task.raw_results.length)) return true;
    if (pairs.some(p => p && typeof p === 'object' && pairVerdictOrNull(p) === null)) return false;
    try { reportBackendVerdicts(task); return true; } catch { return false; }
}

/** True when some circuit of the report has results or pairs but no verdicts from the server. */
export function lacksVerdicts(report) {
    return !_tasks(report).every(_hasVerdicts);
}

/**
 * Attach a summary (GET /jobs/{id}/summary, GET /history/runs/{id}/summary or POST /summary)
 * to the report it was computed from, so pairVerdict and reportBackendVerdicts read it. The
 * report itself is not changed.
 */
export function attachSummary(report, summary) {
    const tasks = _tasks(report);
    const parts = Array.isArray(summary?.benchmark_summary) ? summary.benchmark_summary : [summary];
    if (parts.length !== tasks.length) throw new Error('The verdict summary does not match this report.');
    tasks.forEach((task, i) => {
        if (!task || typeof task !== 'object') return;
        const pairs = _pairsOf(task);
        const verdicts = Array.isArray(parts[i]?.pair_verdicts) ? parts[i].pair_verdicts : [];
        if (verdicts.length !== pairs.length) throw new Error('The verdict summary does not match this report.');
        pairs.forEach((p, j) => { if (p && typeof p === 'object') _pairVerdicts.set(p, verdicts[j]); });
        if (parts[i]?.backend_verdicts) _reportVerdicts.set(task, parts[i].backend_verdicts);
    });
}

/** @param {any} obj @param {string[]} keys */
const _pick = (obj, keys) => Object.fromEntries(keys.filter(k => k in obj).map(k => [k, obj[k]]));

/** The fields of one circuit's report that POST /summary reads. */
function _summaryTask(r) {
    if (!r || typeof r !== 'object' || Array.isArray(r)) return r;
    const out = _pick(r, ['n_shots', 'analysis_version']);
    if (Array.isArray(r.raw_results)) {
        out.raw_results = r.raw_results.map(x => (x && typeof x === 'object' && !Array.isArray(x)
            ? _pick(x, ['simulator', 'dispatch_status', 'error']) : x));
    } else if ('raw_results' in r) out.raw_results = r.raw_results;
    const div = r.divergence_report;
    if (div && typeof div === 'object' && !Array.isArray(div)) {
        out.divergence_report = _pick(div, ['analysis_version', 'simulators', 'ordering_map', 'pairwise_agreement']);
    } else if ('divergence_report' in r) out.divergence_report = div;
    return out;
}

/** The body of POST /summary for a report: the fields the verdicts read, without statevectors,
 * counts or circuit texts. */
export function summaryInput(report) {
    if (Array.isArray(report?.benchmark_summary)) return { results: { benchmark_summary: report.benchmark_summary.map(_summaryTask) } };
    return { results: _summaryTask(report) };
}

/** The pair's agreement label, or for agree_after_normalization the label its normalised vectors received. */
export function effectiveAgreement(p) {
    return pairVerdict(p).effective_agreement;
}

/**
 * Shot-noise assessment of a pair, as the server reads it from the record.
 * @returns {'consistent_within_shot_noise'|'inconclusive_low_shots'|'distinguishable'|'ambiguous'|'not_comparable'|null}
 */
export function measuredAssessment(p) {
    return pairVerdict(p).assessment;
}

/**
 * The basis ('direct' or 'bit_reversal') in which a pair matches although its declared
 * qubit orderings imply the other one, 'unrecorded', or null.
 * @returns {string|null}
 */
export function unalignedBasis(p) {
    return pairVerdict(p).unaligned_basis;
}

/** True when a pair matches only in a basis its declared qubit orderings do not imply. */
export function unalignedBasisMatch(p) {
    return unalignedBasis(p) !== null;
}

/**
 * Group of a statevector pair: 'agree' (directly, up to a global phase, or after
 * normalisation), 'bit_order' (after the bit reversal the declared orderings imply),
 * 'disagree', 'not_comparable', or 'other'.
 * @returns {'agree'|'bit_order'|'disagree'|'not_comparable'|'other'}
 */
export function statevectorGroup(p) {
    return pairVerdict(p).statevector_group;
}

/** Global phase offset (rad) of a statevector pair in the basis its declared orderings imply, or null. */
export function alignedPhase(p) {
    const m = p?.metrics || {};
    const pick = [m.label_aligned_relative_phase_rad, m.label_aligned_relative_phase,
        m.label_aligned_basis === 'bit_reversal' ? m.bit_reversed_relative_phase_rad : m.direct_relative_phase_rad];
    const v = pick.find(x => typeof x === 'number' && Number.isFinite(x));
    return v === undefined ? null : v;
}

/** True when a statevector pair differs by a global phase larger than its phase tolerance in the basis its declared orderings imply. */
export function hasPhaseOffset(p) {
    if (!p || p.mode === 'measured') return false;
    if (typeof p.transform_effect?.global_phase_aligned === 'boolean') return p.transform_effect.global_phase_aligned;
    if (effectiveAgreement(p) === 'agree_up_to_global_phase') return true;
    const phase = alignedPhase(p);
    const tol = p.metrics?.phase_tolerance;
    return phase !== null && typeof tol === 'number' && Math.abs(phase) > tol;
}

/** Fidelity of a statevector pair in the basis its declared orderings imply, and whether that basis is bit-reversed. */
export function alignedFidelity(p) {
    const m = p?.metrics || {};
    const reversed = m.label_aligned_basis === 'bit_reversal';
    const value = m.label_aligned_fidelity ?? (reversed ? m.bit_reversed_fidelity : m.direct_fidelity);
    return { value, reversed };
}

/** True when the pair is a disagreement. */
export function isDisagreement(p) {
    return pairVerdict(p).differs;
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
    [/\s*Server operators can check whether its service is running\.?/gi, ' The {subject} may be restarting; try again in a minute. If it keeps happening, tell the administrator of this server.'],
    [/\s*Server operators can see details in the (runner|compiler)( pod)? logs\.?/gi, ' If it happens again, tell the administrator of this server.'],
    [/raise the timeout\./g, 'raise the timeout in the Execution chip.'],
    [/\s*Check the \S+ container logs( to confirm)?\.?/gi, ' If it happens again, tell the administrator of this server.'],
    [/\s*Check container logs in your Kubernetes cluster\.?/gi, ' If it happens again, tell the administrator of this server.'],
    [/\s*Check that its container is running\.?/gi, ' The {subject} may be restarting; try again in a minute.'],
];

/** A runner or compiler error message with server-operator instructions replaced by ones a UI
 * user can act on; `subject` names what failed ('backend', 'compile-only service'). */
export function userFacingError(msg, subject = 'backend') {
    if (msg === null || msg === undefined) return msg;
    let text = String(msg);
    OPERATOR_HINTS.forEach(([re, repl]) => { text = text.replace(re, repl.replace('{subject}', subject)); });
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
