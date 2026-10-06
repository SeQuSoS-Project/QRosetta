// Per-backend counts over a report's pair records (how many backends each one differs from,
// is inconclusive with on the full-distribution test, or could not be compared with), and
// the headline built from them. Disagreement is isDisagreement() only, so these counts match
// the pair badges; a measured pair can be inconclusive and differ in a marginal at once.

import { isDisagreement, measuredAssessment, runnerStatus } from './run_status.js';

/**
 * @typedef {{ key: string, status: string, compared: number, differs: number, differsFull: number,
 *             differsMarginal: number, inconclusive: number, notComparable: number,
 *             differsWith: string[], bitOrder: string|null }} BackendVerdict
 */

/** @returns {{ mode: string, backends: BackendVerdict[], pairs: number, disagreeing: number,
 *              inconclusive: number, notComparable: number }} */
export function backendVerdicts(report) {
    const div = report?.divergence_report || {};
    const pairs = Array.isArray(div.pairwise_agreement) ? div.pairwise_agreement : [];
    const raws = Array.isArray(report?.raw_results) ? report.raw_results : [];
    const measured = !!report?.n_shots || pairs.some(p => p.mode === 'measured');
    const ordering = div.ordering_map || {};

    /** @type {Map<string, BackendVerdict>} */
    const byKey = new Map();
    const entry = key => {
        if (!byKey.has(key)) {
            byKey.set(key, { key, status: 'ok', compared: 0, differs: 0, differsFull: 0, differsMarginal: 0,
                             inconclusive: 0, notComparable: 0, differsWith: [], bitOrder: ordering[key] ?? null });
        }
        return byKey.get(key);
    };
    raws.forEach(r => { if (r && typeof r.simulator === 'string') entry(r.simulator).status = runnerStatus(r); });
    (Array.isArray(div.simulators) ? div.simulators : []).forEach(entry);

    let disagreeing = 0, inconclusive = 0, notComparable = 0;
    pairs.forEach(p => {
        const sims = Array.isArray(p.simulators) && p.simulators.length === 2 ? p.simulators : null;
        if (!sims) return;
        const [a, b] = sims.map(entry);
        if (p.agreement === 'not_comparable') {
            a.notComparable++; b.notComparable++; notComparable++;
            return;
        }
        a.compared++; b.compared++;
        const assessment = p.mode === 'measured' ? measuredAssessment(p) : null;
        if (assessment === 'inconclusive_low_shots' || assessment === 'ambiguous') {
            inconclusive++;
            a.inconclusive++; b.inconclusive++;
        }
        if (isDisagreement(p)) {
            disagreeing++;
            a.differs++; b.differs++;
            a.differsWith.push(b.key); b.differsWith.push(a.key);
            if (p.mode === 'measured') {
                if (measuredAssessment(p) === 'distinguishable') { a.differsFull++; b.differsFull++; }
                if (p.marginal_assessment === 'marginal_distinguishable') { a.differsMarginal++; b.differsMarginal++; }
            }
        }
    });

    return { mode: measured ? 'measured' : 'statevector', backends: [...byKey.values()],
             pairs: pairs.length, disagreeing, inconclusive, notComparable };
}

/**
 * Headline model: the failed backends by status, the backends that differ from at least one
 * other (most first), and whether every disagreeing pair involves a backend that differs
 * from all the backends it was compared with.
 */
export function headlineModel(verdicts) {
    const failed = { offline: [], error: [], timeout: [] };
    verdicts.backends.forEach(b => { if (b.status !== 'ok' && failed[b.status]) failed[b.status].push(b.key); });
    const ok = verdicts.backends.filter(b => b.status === 'ok');
    const differing = ok.filter(b => b.differs > 0).sort((x, y) => (y.differs / y.compared) - (x.differs / x.compared) || y.differs - x.differs);
    const outliers = differing.filter(b => b.differs === b.compared);
    const outlierKeys = new Set(outliers.map(b => b.key));
    const explainedByOutliers = outliers.length > 0 && differing.every(b =>
        outlierKeys.has(b.key) || b.differsWith.every(k => outlierKeys.has(k)));
    const rest = ok.filter(b => !outlierKeys.has(b.key));
    const residualPairs = [];
    rest.forEach(b => b.differsWith.forEach(k => {
        if (!outlierKeys.has(k) && b.key < k) residualPairs.push([b.key, k]);
    }));
    return { failed, ok: ok.length, differing, outliers, explainedByOutliers, rest, residualPairs };
}
