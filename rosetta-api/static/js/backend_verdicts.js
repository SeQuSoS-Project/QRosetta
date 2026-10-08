// Per-backend counts over a report's pair records (how many backends each one differs from,
// is inconclusive with on the full-distribution test, or could not be compared with), and
// the headline model built from them. Disagreement is isDisagreement() only, so these counts
// match the pair badges; a measured pair can be inconclusive and differ in a marginal at once.
// A measured pair flagged only under Benjamini–Yekutieli (not under Holm, no differing
// marginal) is counted apart as "BY only" and does not shape the headline. Each backend keeps
// the size of every compared pair (total variation or fidelity) so a difference can be sized
// against the backends the headline does not name.

import { isDisagreement, measuredAssessment, runnerStatus, statevectorGroup } from './run_status.js';
import { parseRunnerKey } from './runner_key.js';

/**
 * @typedef {{ key: string, status: string, compared: number, differs: number, differsFull: number,
 *             differsMarginal: number, differsByOnly: number, inconclusive: number, notComparable: number,
 *             differsWith: string[], byOnlyWith: string[], agreesWith: string[], comparedWith: string[],
 *             worstFidelity: number|null, largestTv: number|null, bitOrder: string|null,
 *             sizeWith: Object<string, number> }} BackendVerdict
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

const _num = x => (typeof x === 'number' && Number.isFinite(x) ? x : null);

/** Size of a pair's difference: label-aligned fidelity (statevector) or total variation (measured). */
function _magnitude(p) {
    const m = p.metrics || {};
    if (p.mode === 'measured') return { tv: _num(m.statistical_test?.effect_size?.total_variation), fidelity: null };
    return { tv: null, fidelity: _num(m.label_aligned_fidelity) ?? _num(m.direct_fidelity) };
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
                             comparedWith: [], worstFidelity: null, largestTv: null, bitOrder: ordering[key] ?? null,
                             sizeWith: {} });
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
        const size = _magnitude(p);
        const value = p.mode === 'measured' ? size.tv : size.fidelity;
        if (value !== null) { a.sizeWith[b.key] = value; b.sizeWith[a.key] = value; }
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
                const { tv, fidelity } = _magnitude(p);
                [a, b].forEach(x => {
                    if (fidelity !== null && (x.worstFidelity === null || fidelity < x.worstFidelity)) x.worstFidelity = fidelity;
                    if (tv !== null && (x.largestTv === null || tv > x.largestTv)) x.largestTv = tv;
                });
                if (p.mode === 'measured') {
                    if (measuredAssessment(p) === 'distinguishable') { a.differsFull++; b.differsFull++; }
                    if (p.marginal_assessment === 'marginal_distinguishable') { a.differsMarginal++; b.differsMarginal++; }
                }
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

export const MAX_NAMED = 4;
export const MAX_GROUPS = 4;

/** Every vertex cover of the smallest size up to `limit` of the graph with these edges, or []. */
export function minimumCovers(edges, limit = MAX_NAMED) {
    for (let k = 1; k <= limit; k++) {
        const found = new Map();
        const search = (chosen, depth) => {
            const open = edges.find(([u, v]) => !chosen.has(u) && !chosen.has(v));
            if (!open) {
                const cover = [...chosen].sort();
                found.set(cover.join('\u0000'), cover);
                return;
            }
            if (depth === k) return;
            open.forEach(x => search(new Set([...chosen, x]), depth + 1));
        };
        search(new Set(), 0);
        if (found.size) return [...found.values()].filter(c => c.length === k);
    }
    return [];
}

/** Connected components of `keys` under the symmetric relation `linked`, largest first. */
function _components(keys, linked) {
    const seen = new Set();
    const groups = [];
    keys.forEach(start => {
        if (seen.has(start)) return;
        const members = [];
        const stack = [start];
        seen.add(start);
        while (stack.length) {
            const k = stack.pop();
            members.push(k);
            keys.forEach(n => { if (!seen.has(n) && linked(k, n)) { seen.add(n); stack.push(n); } });
        }
        groups.push(members.sort());
    });
    return groups.sort((x, y) => y.length - x.length || x[0].localeCompare(y[0]));
}

/**
 * Headline model, built from the pairs that differ (BY-only pairs left out). Inconclusive and
 * not-comparable pairs count as neither agreement nor difference.
 *
 * `kind` is one of:
 * - 'none': no pair differs;
 * - 'named': one smallest set of at most MAX_NAMED backends, fewer than half, appears in every
 *   pair that differs; `named` lists it as groups of members that agree with each other, each
 *   with `differsFrom` (backends outside it a member differs from) and `comparedOutside`; `rest`
 *   are the other backends, among which no pair differs;
 * - 'camps': with the backends that differ from none (`neutral`) set aside, the others split into
 *   2 to MAX_GROUPS groups, at least two of them with two or more members, with no differing pair
 *   inside a group and every compared pair between groups differing; `camps` lists them,
 *   `largest` is the unique largest group or null;
 * - 'pairs': at most MAX_NAMED pairs differ and none of the above applies; `pairs` lists them;
 * - 'spread': anything else; the backends that differ from more than half of those they were
 *   compared with are split into groups that agree with each other, ranked by the size of their
 *   difference from the other backends (lowest fidelity, or median total variation), then by the
 *   share of pairs that differ; `named` lists the first groups up to MAX_NAMED backends (at least
 *   one group) and `unnamed` the rest of these backends. With no such backend, `named` lists the
 *   MAX_NAMED backends that differ most, one per group. `rest` are the other backends and `pairs`
 *   the differing pairs among `rest`.
 *
 * `flagged` are the backends the headline names as differing; `reference` are the backends a
 * named backend or group is sized against ('named' and 'spread': `rest`; otherwise empty);
 * `chance` are the named single backends of a measured report that differ from fewer than half
 * of the backends they were compared with and are consistent with all the others, a pattern one
 * unusual sample can produce; `byOnlyHub` is the backend in every BY-only pair when there are
 * two or more such pairs.
 */
export function headlineModel(verdicts) {
    const failed = { offline: [], error: [], timeout: [] };
    verdicts.backends.forEach(b => { if (b.status !== 'ok' && failed[b.status]) failed[b.status].push(b.key); });
    const ok = verdicts.backends.filter(b => b.status === 'ok');
    const byKey = new Map(ok.map(b => [b.key, b]));
    const keys = ok.map(b => b.key).sort();
    const differs = (x, y) => byKey.get(x).differsWith.includes(y);
    const ratio = b => b.differsWith.length / Math.max(1, b.compared);
    const differing = ok.filter(b => b.differsWith.length > 0)
        .sort((x, y) => ratio(y) - ratio(x) || y.differsWith.length - x.differsWith.length || x.key.localeCompare(y.key));
    const edges = [];
    keys.forEach(k => byKey.get(k).differsWith.forEach(o => { if (byKey.has(o) && k < o) edges.push([k, o]); }));

    const byOnly = verdicts.byOnlyPairs || [];
    const hubs = byOnly.length >= 2 ? byOnly.reduce((acc, pair) => acc.filter(k => pair.includes(k)), byOnly[0]) : [];
    const base = { failed, ok: ok.length, differing, edges, byOnlyHub: hubs.length === 1 ? hubs[0] : null,
                   named: [], rest: [], camps: [], largest: null, neutral: [], pairs: [], flagged: [],
                   unnamed: [], reference: [], chance: [] };
    const chance = groups => verdicts.mode !== 'measured' ? [] : groups
        .filter(g => g.members.length === 1)
        .map(g => byKey.get(g.members[0]))
        .filter(b => b.differsWith.length * 2 < b.compared && b.differsWith.length + b.agreesWith.length === b.compared)
        .map(b => b.key);
    if (!edges.length) return { ...base, kind: 'none' };

    const describe = members => {
        const set = new Set(members);
        const differsFrom = new Set(), comparedOutside = new Set();
        members.forEach(k => {
            const b = byKey.get(k);
            b.differsWith.forEach(o => { if (!set.has(o)) differsFrom.add(o); });
            b.comparedWith.forEach(o => { if (!set.has(o) && byKey.has(o)) comparedOutside.add(o); });
        });
        return { members, differsFrom: [...differsFrom].sort(), comparedOutside: comparedOutside.size,
                 differsFromAll: differsFrom.size > 0 && differsFrom.size === comparedOutside.size };
    };

    const covers = minimumCovers(edges);
    if (covers.length === 1 && covers[0].length * 2 < ok.length && edges.length > 1) {
        const cover = covers[0];
        const agree = (x, y) => byKey.get(x).agreesWith.includes(y);
        const named = _components(cover, agree).map(describe)
            .sort((x, y) => y.differsFrom.length - x.differsFrom.length || x.members[0].localeCompare(y.members[0]));
        const rest = keys.filter(k => !cover.includes(k));
        return { ...base, kind: 'named', named, rest, flagged: cover, reference: rest, chance: chance(named) };
    }

    const neutral = keys.filter(k => byKey.get(k).differsWith.length === 0);
    const active = keys.filter(k => !neutral.includes(k));
    const camps = _components(active, (x, y) => !differs(x, y));
    const consistent = camps.every(c => c.every(x => c.every(y => !differs(x, y))));
    if (camps.length >= 2 && camps.length <= MAX_GROUPS && consistent && camps[1].length >= 2) {
        const largest = camps[0].length > camps[1].length ? camps[0] : null;
        return { ...base, kind: 'camps', camps: camps.map(describe), largest, neutral,
                 flagged: camps.filter(c => c !== largest).flat() };
    }

    if (edges.length <= MAX_NAMED) {
        return { ...base, kind: 'pairs', pairs: edges, flagged: [...new Set(edges.flat())].sort() };
    }

    const majority = differing.filter(b => b.differsWith.length * 2 > b.compared).map(b => b.key);
    let groups, unnamed = [];
    if (majority.length) {
        const others = keys.filter(k => !majority.includes(k));
        const agree = (x, y) => byKey.get(x).agreesWith.includes(y);
        const measured = verdicts.mode === 'measured';
        const score = members => {
            const values = sizesBetween(verdicts, members, others);
            if (!values.length) return Infinity;
            return measured ? -median(values) : Math.min(...values);
        };
        const share = members => Math.max(...members.map(k => ratio(byKey.get(k))));
        const ranked = _components(majority, agree).map(m => ({ m, score: score(m), share: share(m) }))
            .sort((x, y) => (x.score === y.score ? 0 : x.score < y.score ? -1 : 1)
                || y.share - x.share || y.m.length - x.m.length || x.m[0].localeCompare(y.m[0]));
        groups = [];
        let count = 0;
        ranked.forEach(({ m }) => {
            if (!groups.length || count + m.length <= MAX_NAMED) { groups.push(describe(m)); count += m.length; }
            else unnamed.push(...m);
        });
        unnamed.sort();
    } else {
        groups = differing.slice(0, MAX_NAMED).map(b => describe([b.key]));
    }
    const named = groups.flatMap(g => g.members);
    const flagged = [...named, ...unnamed];
    const rest = keys.filter(k => !flagged.includes(k));
    return { ...base, kind: 'spread', named: groups, unnamed, rest, reference: rest, chance: chance(groups),
             pairs: edges.filter(([x, y]) => !flagged.includes(x) && !flagged.includes(y)), flagged };
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
