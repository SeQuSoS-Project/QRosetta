// Per-backend counts over a report's pair records (how many backends each one differs from,
// is inconclusive with on the full-distribution test, or could not be compared with), and
// the headline built from them. Disagreement is isDisagreement() only, so these counts match
// the pair badges; a measured pair can be inconclusive and differ in a marginal at once.
// A measured pair flagged only under Benjamini–Yekutieli (not under Holm, no differing
// marginal) is counted apart as "BY only" and does not shape the headline groups.

import { isDisagreement, measuredAssessment, runnerStatus, statevectorGroup } from './run_status.js';
import { parseRunnerKey } from './runner_key.js';

/**
 * @typedef {{ key: string, status: string, compared: number, differs: number, differsFull: number,
 *             differsMarginal: number, differsByOnly: number, inconclusive: number, notComparable: number,
 *             differsWith: string[], byOnlyWith: string[], agreesWith: string[], comparedWith: string[],
 *             bitOrder: string|null }} BackendVerdict
 */

/** True for a measured pair whose only disagreement evidence is significance under BY but not under Holm. */
export function isByOnlyDisagreement(p) {
    if (p?.mode !== 'measured' || !isDisagreement(p)) return false;
    if (p.marginal_assessment === 'marginal_distinguishable') return false;
    return p.metrics?.statistical_test?.significant_fwer === false;
}

/** True when the pair agrees (statevector, bit order as declared included) or is consistent within shot noise. */
function _agrees(p) {
    if (p.mode === 'measured') return measuredAssessment(p) === 'consistent_within_shot_noise' && !isDisagreement(p);
    const g = statevectorGroup(p);
    return g === 'agree' || g === 'bit_order';
}

/** @returns {{ mode: string, backends: BackendVerdict[], pairs: number, disagreeing: number,
 *              byOnly: number, byOnlyPairs: string[][], inconclusive: number, notComparable: number,
 *              marginalTested: boolean, multiRun: boolean }} */
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
            byKey.set(key, { key, status: 'ok', compared: 0, differs: 0, differsFull: 0, differsMarginal: 0, differsByOnly: 0,
                             inconclusive: 0, notComparable: 0, differsWith: [], byOnlyWith: [], agreesWith: [],
                             comparedWith: [], bitOrder: ordering[key] ?? null });
        }
        return byKey.get(key);
    };
    raws.forEach(r => { if (r && typeof r.simulator === 'string') entry(r.simulator).status = runnerStatus(r); });
    (Array.isArray(div.simulators) ? div.simulators : []).forEach(entry);

    let disagreeing = 0, inconclusive = 0, notComparable = 0;
    const byOnlyPairs = [];
    pairs.forEach(p => {
        const sims = Array.isArray(p.simulators) && p.simulators.length === 2 ? p.simulators : null;
        if (!sims) return;
        const [a, b] = sims.map(entry);
        if (p.agreement === 'not_comparable') {
            a.notComparable++; b.notComparable++; notComparable++;
            return;
        }
        a.compared++; b.compared++;
        a.comparedWith.push(b.key); b.comparedWith.push(a.key);
        const assessment = p.mode === 'measured' ? measuredAssessment(p) : null;
        if (assessment === 'inconclusive_low_shots' || assessment === 'ambiguous') {
            inconclusive++;
            a.inconclusive++; b.inconclusive++;
        }
        if (_agrees(p)) { a.agreesWith.push(b.key); b.agreesWith.push(a.key); }
        if (isDisagreement(p)) {
            disagreeing++;
            a.differs++; b.differs++;
            if (isByOnlyDisagreement(p)) {
                a.differsByOnly++; b.differsByOnly++;
                a.byOnlyWith.push(b.key); b.byOnlyWith.push(a.key);
                byOnlyPairs.push([a.key, b.key]);
            } else {
                a.differsWith.push(b.key); b.differsWith.push(a.key);
            }
            if (p.mode === 'measured') {
                if (measuredAssessment(p) === 'distinguishable') { a.differsFull++; b.differsFull++; }
                if (p.marginal_assessment === 'marginal_distinguishable') { a.differsMarginal++; b.differsMarginal++; }
            }
        }
    });

    const marginalTested = pairs.some(p => p.mode === 'measured' && !!p.metrics?.marginal_test
        && !['not_applicable', 'not_tested'].includes(p.marginal_assessment));
    const backends = [...byKey.values()];
    return { mode: measured ? 'measured' : 'statevector', backends, pairs: pairs.length, disagreeing,
             byOnly: byOnlyPairs.length, byOnlyPairs, inconclusive, notComparable, marginalTested,
             multiRun: backends.some(b => parseRunnerKey(b.key).isMulti) };
}

/** Groups of successful backends linked by pairs that agree (or are consistent within shot noise), largest first. */
function _agreementGroups(ok) {
    const byKey = new Map(ok.map(b => [b.key, b]));
    const seen = new Set();
    const groups = [];
    ok.forEach(start => {
        if (seen.has(start.key)) return;
        const members = [];
        const stack = [start.key];
        seen.add(start.key);
        while (stack.length) {
            const k = stack.pop();
            members.push(k);
            byKey.get(k).agreesWith.forEach(n => {
                if (byKey.has(n) && !seen.has(n)) { seen.add(n); stack.push(n); }
            });
        }
        groups.push(members.sort());
    });
    return groups.sort((x, y) => y.length - x.length || x[0].localeCompare(y[0]));
}

/**
 * Headline model. `failed` lists failed backends by status. `differing` are the backends that
 * differ from at least one other (BY-only pairs left out), most first; `outliers` differ from
 * every backend they were compared with. `groups` partitions the successful backends into
 * groups linked by agreeing pairs; `main` is the largest group when no other is as large, and
 * `others` the remaining groups that differ from a backend, each with `differsFrom` (backends
 * outside it that a member differs from), `comparedOutside`, and `internalPairs`. `clean` is
 * true when the groups explain every disagreement except those inside `main`. `flagged` are
 * the backends the headline names as differing; `rest` the others and `residualPairs` the
 * pairs among `rest` that differ.
 */
export function headlineModel(verdicts) {
    const failed = { offline: [], error: [], timeout: [] };
    verdicts.backends.forEach(b => { if (b.status !== 'ok' && failed[b.status]) failed[b.status].push(b.key); });
    const ok = verdicts.backends.filter(b => b.status === 'ok');
    const byKey = new Map(ok.map(b => [b.key, b]));
    const robust = b => b.differsWith.length;
    const differing = ok.filter(b => robust(b) > 0)
        .sort((x, y) => (robust(y) / y.compared) - (robust(x) / x.compared) || robust(y) - robust(x) || x.key.localeCompare(y.key));
    const outliers = differing.filter(b => robust(b) === b.compared);
    const outlierKeys = new Set(outliers.map(b => b.key));
    const explainedByOutliers = outliers.length > 0 && differing.every(b =>
        outlierKeys.has(b.key) || b.differsWith.every(k => outlierKeys.has(k)));

    const groups = _agreementGroups(ok);
    const describe = members => {
        const set = new Set(members);
        const differsFrom = new Set(), comparedOutside = new Set();
        const internalPairs = [];
        let everyOutsidePair = true;
        members.forEach(k => {
            const b = byKey.get(k);
            b.differsWith.forEach(o => {
                if (!set.has(o)) differsFrom.add(o);
                else if (k < o) internalPairs.push([k, o]);
            });
            const outside = b.comparedWith.filter(o => !set.has(o) && byKey.has(o));
            outside.forEach(o => comparedOutside.add(o));
            if (outside.some(o => !b.differsWith.includes(o))) everyOutsidePair = false;
        });
        return { members, differsFrom: [...differsFrom].sort(), comparedOutside: comparedOutside.size,
                 differsFromAll: everyOutsidePair && differsFrom.size > 0, internalPairs };
    };
    const unique = groups.length === 1 || (groups.length > 1 && groups[0].length > groups[1].length);
    const main = unique && groups[0].length >= 2 ? describe(groups[0]) : null;
    const others = (main ? groups.slice(1) : groups).map(describe)
        .filter(g => g.differsFrom.length || g.internalPairs.length)
        .sort((x, y) => (y.differsFrom.length / Math.max(1, y.comparedOutside)) - (x.differsFrom.length / Math.max(1, x.comparedOutside))
            || y.members.length - x.members.length || x.members[0].localeCompare(y.members[0]));
    const clean = !!main && others.every(g => g.internalPairs.length === 0);

    let flagged;
    if (clean) flagged = others.flatMap(g => g.members);
    else if (outliers.length) flagged = outliers.map(b => b.key);
    else flagged = differing.filter(b => robust(b) * 2 > b.compared).map(b => b.key);
    if (!flagged.length) flagged = differing.map(b => b.key);

    const rest = clean && main ? main.members.map(k => byKey.get(k)) : ok.filter(b => !outlierKeys.has(b.key));
    const restKeys = new Set(rest.map(b => b.key));
    const residualPairs = [];
    rest.forEach(b => b.differsWith.forEach(k => {
        if (restKeys.has(k) && b.key < k) residualPairs.push([b.key, k]);
    }));
    return { failed, ok: ok.length, differing, outliers, explainedByOutliers, rest, residualPairs,
             groups, main, others, clean, flagged };
}
