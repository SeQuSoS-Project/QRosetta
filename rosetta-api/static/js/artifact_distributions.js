// Measured-distribution views (count comparison, single-bit marginals, Hamming weight,
// outcome spread): data, tables and captions. Mirrors services/publication/distributions.py;
// tests/unit/test_artifacts_parity.py compares the two. No DOM, no network.

import { _artFull, _artInt, _artMsbCounts, _artRunLabel, _formatColumns, _n } from './artifact_formats.js';
import { reportBackends } from './artifact_views.js';

const _byLabel = (a, b) => (a.label < b.label ? -1 : a.label > b.label ? 1 : 0);
const _sortedKeys = obj => Object.keys(obj).sort();
const _weight = key => key.split('').filter(c => c === '1').length;

const _memoByReport = new WeakMap();
/** `compute()` cached per report object and key: a figure caption, its table and the
 * builder's checks read the same data. */
function _memo(results, key, compute) {
    let cache = _memoByReport.get(results);
    if (!cache) { cache = new Map(); _memoByReport.set(results, cache); }
    if (!cache.has(key)) cache.set(key, compute());
    return cache.get(key);
}

/** {sims, counts, totals, prob, missing}: backends with counts in report order, their
 * msb-order counts and totals, prob(sim, key) and the backends without counts. */
export function countProbabilities(results) {
    return _memo(results, 'counts', () => _countProbabilities(results));
}

function _countProbabilities(results) {
    const counts = _artMsbCounts(results);
    const sims = reportBackends(results).filter(s => s in counts);
    const totals = {};
    sims.forEach(s => { totals[s] = Object.values(counts[s]).reduce((a, b) => a + b, 0); });
    const missing = reportBackends(results).filter(s => !(s in counts));
    const prob = (s, o) => (totals[s] ? (counts[s][o] || 0) / totals[s] : 0.0);
    return { sims, counts, totals, prob, missing };
}

function missingNote(cp) {
    return cp.missing.length ? ` Backends without counts are not drawn: ${cp.missing.join(', ')}.` : '';
}

function highlightNote(p) {
    return p.colour === 'highlight'
        ? ` Coloured: backends whose pair with ${p.ref} is a disagreement (shot-noise verdict or a single-bit marginal); grey: the rest.`
        : '';
}

/** The outcomes the count comparison shows (distributions.py count_selection). */
export function countSelection(results, p) {
    return _memo(results, 'selection' + JSON.stringify(p), () => _countSelection(results, p));
}

function _countSelection(results, p) {
    const cp = countProbabilities(results);
    const { sims, prob } = cp;
    const lsb = p.keyorder === 'lsb';
    /** @type {{key: string|null, label?: string, vals: number[]}[]} */
    let rows;
    let other = null, observed = null, rest = [], note, keyNote;
    if (p.outcomes === 'bits') {
        const bits = p.bits, k = bits.length;
        const marg = {};
        sims.forEach(s => {
            marg[s] = {};
            _sortedKeys(cp.counts[s]).forEach(o => {
                const lab = bits.map(b => (b < o.length ? o[b] : '0')).join('');
                marg[s][lab] = (marg[s][lab] || 0.0) + prob(s, o);
            });
        });
        const keys = [...Array(2 ** k).keys()].map(i => i.toString(2).padStart(k, '0'));
        rows = keys.map(key => ({ key, vals: sims.map(s => marg[s][key] || 0.0) }));
        const order = lsb ? bits.slice().reverse() : bits.slice();
        note = `the marginal distribution over classical bits ${bits.join(', ')}: all ${2 ** k} outcomes, the other bits summed out`;
        keyNote = 'keys read ' + order.map(b => `c[${b}]`).join(' ') + ' from left to right';
    } else {
        const score = new Map();
        sims.forEach(s => Object.keys(cp.counts[s]).forEach(o => {
            const v = prob(s, o);
            if (v > (score.has(o) ? score.get(o) : -1.0)) score.set(o, v);
        }));
        observed = [...score.keys()].sort();
        const ranked = observed.slice().sort((a, b) => score.get(b) - score.get(a));
        const kept = p.outcomes === 'top' ? ranked.slice(0, p.top) : ranked.filter(o => score.get(o) >= p.threshold);
        const keptSet = new Set(kept);
        rest = observed.filter(o => !keptSet.has(o));
        rows = kept.map(o => ({ key: o, vals: sims.map(s => prob(s, o)) }));
        if (rest.length) {
            const ov = sims.map(s => {
                let total = 0.0;
                _sortedKeys(cp.counts[s]).forEach(o => { if (!keptSet.has(o)) total += prob(s, o); });
                return total;
            });
            let mean = 0.0;
            ov.forEach(v => { mean += v; });
            mean = ov.length ? mean / ov.length : 0.0;
            other = { vals: ov, share: (mean * 100).toFixed(1) };
        }
        if (!rest.length) note = `all ${observed.length} observed outcomes`;
        else if (p.outcomes === 'top') note = `the ${kept.length} outcomes with the largest probability on any backend, of ${observed.length} observed`;
        else note = `the ${kept.length} of ${observed.length} observed outcomes with probability ≥ ${_artFull(p.threshold)} on any backend`;
        if (rest.length) note += `; the other ${rest.length} (${other.share}% of shots on average) are ` + (p.other ? "summed into 'other'" : 'not shown');
        keyNote = lsb ? 'keys in lsb order (classical bit 0 rightmost)' : 'keys in msb order (classical bit 0 leftmost)';
    }
    rows.forEach(r => { r.label = lsb ? r.key.split('').reverse().join('') : r.key; });
    if (p.sort === 'bitstring') rows.sort(_byLabel);
    else if (p.sort === 'hamming') rows.sort((a, b) => (_weight(a.key) - _weight(b.key)) || _byLabel(a, b));
    else if (p.outcomes === 'bits') rows.sort((a, b) => Math.max(...b.vals, -Infinity) - Math.max(...a.vals, -Infinity));
    if (other && p.other) rows.push({ key: null, label: `other (+${rest.length})`, vals: other.vals });
    return { cp, rows, other, observed, rest, note, keyNote };
}

const _COUNT_LEADS = {
    overlay: 'Clustered bars of measured probabilities, one colour per backend',
    heatmap: 'Outcome × backend heatmap of measured probabilities; a uniform row is agreement, a varying row is disagreement',
};

/** Caption of the count comparison figure. */
export function countsLegend(results, p) {
    const sel = countSelection(results, p);
    let lead;
    if (p.layout === 'panels') lead = `One panel per backend; black ticks mark ${p.ref}`;
    else if (p.layout === 'diff') {
        lead = `Measured probability of each backend minus ${p.ref}`;
        if (p.band) lead += '; the shaded band is ±2σ shot noise of the difference of two independent samples at the reference probability and shot count';
    } else lead = _COUNT_LEADS[p.layout];
    let text = `${lead}, for ${sel.cp.sims.length} backend(s), ${_artRunLabel(results)}. Shows `
        + `${sel.note}; ${sel.keyNote}; lsb-declared backends are bit-reversed to one order first.`;
    if (p.yscale === 'log' && (p.layout === 'overlay' || p.layout === 'panels')) text += ' Logarithmic probability axis.';
    return text + highlightNote(p) + missingNote(sel.cp);
}

export function dataCounts(results, p) {
    const sel = countSelection(results, p);
    return {
        headers: ['Outcome'].concat(sel.cp.sims),
        rows: _formatColumns(sel.rows.map(r => /** @type {any[]} */ ([r.label]).concat(r.vals.map(v => _n(v))))),
        title: 'Measured outcome probabilities',
        caption: `Measured probability of each outcome (rows) for each backend (columns), ${_artRunLabel(results)}. `
            + `Shows ${sel.note}; ${sel.keyNote}; lsb-declared backends are bit-reversed to one order first.` + missingNote(sel.cp),
    };
}

/** {cp, n, m: {sim: [P(c[j] = 1) for j]}}. */
export function marginals(results) {
    return _memo(results, 'marginals', () => _marginals(results));
}

function _marginals(results) {
    const cp = countProbabilities(results);
    let n = 0;
    cp.sims.forEach(s => Object.keys(cp.counts[s]).forEach(o => { n = Math.max(n, o.length); }));
    const m = {};
    cp.sims.forEach(s => {
        const vals = new Array(n).fill(0.0);
        _sortedKeys(cp.counts[s]).forEach(o => {
            const pr = cp.prob(s, o);
            o.split('').forEach((ch, j) => { if (ch === '1') vals[j] += pr; });
        });
        m[s] = vals;
    });
    return { cp, n, m };
}

export function marginalsLegend(results, p) {
    const d = marginals(results);
    const k = d.cp.sims.length;
    let text;
    if (p.layout === 'diff') {
        text = `P(c[j] = 1) of each backend minus ${p.ref}, for ${k} backend(s), ${_artRunLabel(results)}`;
        if (p.errorbars) text += '; the shaded band is ±2σ shot noise of the difference at the reference value';
    } else {
        text = `Probability that each classical bit reads 1, P(c[j] = 1), for ${k} backend(s), ${_artRunLabel(results)}`;
        if (p.errorbars) text += '; error bars are ±2σ binomial shot noise';
    }
    return text + '. The single-bit marginal tests compare these probabilities pair by pair (Holm across all tested bits).'
        + highlightNote(p) + missingNote(d.cp);
}

export function dataMarginals(results) {
    const d = marginals(results);
    const sims = d.cp.sims;
    return {
        headers: ['Classical bit'].concat(sims),
        rows: _formatColumns([...Array(d.n).keys()].map(j => [`c[${j}]`].concat(sims.map(s => _n(d.m[s][j]))))),
        title: 'Single-bit marginals P(c[j] = 1)',
        caption: `Probability that classical bit j reads 1 for each backend, ${_artRunLabel(results)}; lsb-declared backends are bit-reversed to one order first, so c[j] is the same bit for every backend.`
            + missingNote(d.cp),
    };
}

/** {cp, n, h: {sim: [P(weight = w) for w in 0..n]}}. */
export function hamming(results) {
    return _memo(results, 'hamming', () => _hamming(results));
}

function _hamming(results) {
    const cp = countProbabilities(results);
    let n = 0;
    cp.sims.forEach(s => Object.keys(cp.counts[s]).forEach(o => { n = Math.max(n, o.length); }));
    const h = {};
    cp.sims.forEach(s => {
        const vals = new Array(n + 1).fill(0.0);
        _sortedKeys(cp.counts[s]).forEach(o => { vals[_weight(o)] += cp.prob(s, o); });
        h[s] = vals;
    });
    return { cp, n, h };
}

export function hammingLegend(results, p) {
    const d = hamming(results);
    const k = d.cp.sims.length;
    let text;
    if (p.layout === 'diff') {
        text = `Probability of Hamming weight w for each backend minus ${p.ref}, for ${k} backend(s), ${_artRunLabel(results)}; the shaded band is ±2σ shot noise of the difference at the reference probability`;
    } else {
        const each = p.layout === 'lines' ? 'one line per backend' : 'one colour per backend';
        text = `Probability of measuring w ones (Hamming weight w = 0 to ${d.n}), ${each}, for ${k} backend(s), ${_artRunLabel(results)}`;
    }
    return text + '. Independent of bit order.' + highlightNote(p) + missingNote(d.cp);
}

export function dataHamming(results) {
    const d = hamming(results);
    const sims = d.cp.sims;
    return {
        headers: ['Hamming weight'].concat(sims),
        rows: _formatColumns([...Array(d.n + 1).keys()].map(w => [String(w)].concat(sims.map(s => _n(d.h[s][w]))))),
        title: 'Hamming-weight distribution',
        caption: `Probability of measuring w ones in the ${d.n}-bit outcome for each backend, ${_artRunLabel(results)}.` + missingNote(d.cp),
    };
}

/** Per backend: shots, observed outcomes, largest probability and the fewest outcomes
 * covering 50% and 90% of the shots (distributions.py spread). */
export function spread(results) {
    return _memo(results, 'spread', () => _spread(results));
}

function _spread(results) {
    const cp = countProbabilities(results);
    const rows = {};
    cp.sims.forEach(s => {
        const c = /** @type {number[]} */ (Object.values(cp.counts[s])).slice().sort((a, b) => b - a);
        const total = cp.totals[s];
        const cover = {};
        /** @type {[string, number, number][]} */ ([['half', 1, 2], ['ninety', 9, 10]]).forEach(([name, num, den]) => {
            let cum = 0, k = 0;
            while (k < c.length && cum * den < num * total) { cum += c[k]; k += 1; }
            cover[name] = k;
        });
        rows[s] = { shots: total, observed: c.length, sorted: total ? c.map(v => v / total) : [],
            largest: total && c.length ? c[0] / total : null, half: cover.half, ninety: cover.ninety };
    });
    return { cp, rows };
}

export function rankLegend(results, p) {
    const d = spread(results);
    const axes = 'logarithmic probability axis' + (p.xscale === 'log' ? ', logarithmic rank axis' : '');
    return `Observed outcome probabilities of each backend sorted from largest to smallest (${axes}), for ${d.cp.sims.length} backend(s), ${_artRunLabel(results)}. `
        + 'The smallest observable probability is 1/shots; outcomes never observed are absent.' + highlightNote(p) + missingNote(d.cp);
}

export function dataRank(results) {
    const d = spread(results);
    return {
        headers: ['Backend', 'Shots', 'Observed outcomes', 'Largest probability', 'Outcomes for 50% of shots', 'Outcomes for 90% of shots'],
        rows: _formatColumns(Object.entries(d.rows).map(([s, r]) => [s, _artInt(r.shots), _artInt(r.observed), _n(r.largest), _artInt(r.half), _artInt(r.ninety)])),
        title: 'Outcome spread',
        caption: 'Per backend: shots, distinct outcomes observed, the largest outcome probability and the fewest outcomes whose counts add up to 50% and 90% of the shots, '
            + `${_artRunLabel(results)}.` + missingNote(d.cp),
    };
}
