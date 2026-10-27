// Per-backend counts over a report's pair verdicts (how many backends each one differs from,
// is inconclusive with on the full-distribution test, or could not be compared with) and the
// headline model built from them, both as the server computes them
// (services/analysis/divergence/verdicts.py and headline.py), with camelCase field names. A
// measured pair flagged only under Benjamini–Yekutieli (not under Holm, no differing marginal)
// is counted apart as "BY only" and does not shape the headline. Each backend keeps the size of
// every compared pair (total variation or fidelity) so a difference can be sized against the
// backends the headline does not name.

import { reportBackendVerdicts } from './run_status.js';

/**
 * @typedef {{ key: string, status: string, compared: number, differs: number, differsFull: number,
 *             differsMarginal: number, differsByOnly: number, inconclusive: number, notComparable: number,
 *             differsWith: string[], byOnlyWith: string[], agreesWith: string[], comparedWith: string[],
 *             worstFidelity: number|null, largestTv: number|null, bitOrder: string|null,
 *             sizeWith: Object<string, number> }} BackendVerdict
 */

/** @param {string} key */
const _camel = key => key.replace(/_([a-z])/g, (_, c) => c.toUpperCase());

/** @param {Object<string, any>} record */
function _camelKeys(record) {
    return Object.fromEntries(Object.entries(record).map(([k, v]) => [_camel(k), v]));
}

/**
 * The report's per-backend counts, as the server records them (divergence_report.backend_verdicts,
 * or its summary for a report that does not).
 * @returns {{ mode: string, backends: BackendVerdict[], pairs: number, disagreeing: number,
 *             byOnly: number, byOnlyPairs: string[][], inconclusive: number, notComparable: number,
 *             marginalTested: boolean, multiRun: boolean, headlineModel: Object<string, any> }}
 */
export function backendVerdicts(report) {
    const recorded = reportBackendVerdicts(report);
    const out = _camelKeys(recorded);
    out.backends = recorded.backends.map(_camelKeys);
    return /** @type {any} */ (out);
}

export const MAX_NAMED = 4;

/**
 * The headline model the server built from these counts (headline.py describes `kind`, the
 * groups and the lists), with camelCase field names; `differing` holds the backend records of
 * `verdicts.backends`.
 */
export function headlineModel(verdicts) {
    const m = verdicts.headlineModel;
    const byKey = new Map(verdicts.backends.map(b => [b.key, b]));
    /** @param {any} g */
    const group = g => ({ members: g.members, differsFrom: g.differs_from, comparedOutside: g.compared_outside,
                          differsFromAll: g.differs_from_all });
    return {
        kind: m.kind, failed: m.failed, ok: m.ok, differing: m.differing.map(k => byKey.get(k)), edges: m.edges,
        byOnlyHub: m.by_only_hub, named: m.named.map(group), rest: m.rest, camps: m.camps.map(group),
        largest: m.largest, neutral: m.neutral, pairs: m.pairs, flagged: m.flagged, unnamed: m.unnamed,
        reference: m.reference, chance: m.chance,
    };
}

/** Recorded sizes (total variation or fidelity) of the compared pairs between `members` and `others`. */
export function sizesBetween(verdicts, members, others) {
    const byKey = new Map(verdicts.backends.map(b => [b.key, b]));
    const out = [];
    members.forEach(k => {
        const b = byKey.get(k);
        if (!b) return;
        others.forEach(o => {
            if (o !== k && Object.prototype.hasOwnProperty.call(b.sizeWith, o)) out.push(b.sizeWith[o]);
        });
    });
    return out;
}

/** Median of a non-empty list of numbers. */
export function median(xs) {
    const s = [...xs].sort((a, b) => a - b);
    const mid = Math.floor(s.length / 2);
    return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}
