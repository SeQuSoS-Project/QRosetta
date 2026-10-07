// Export views: a figure and/or table (or text) shown together, its parameters, their
// validation, the file-name slug and the crate paths. Mirrors services/publication/views.py
// and registry.item_paths; tests/unit/test_artifacts_parity.py compares the two. No DOM.

import { _artFull, _artSlug } from './artifact_formats.js';

const COLOUR = ['choice', ['backend', 'highlight'], 'backend'];
const REF = ['backend', null];
const COMMON_PARAMS = { backends: ['backends', null] };
const FIGURE_PARAMS = { size: ['choice', ['auto', 'single', 'double', 'slide'], 'auto'], title: ['bool', true] };
const MAX_MARGINAL_BITS = 6;

const VIEWS = [
    { id: 'agreement_distribution', figure: 'agreement_distribution', params: {} },
    { id: 'agreement', table: 'agreement', params: {} },
    { id: 'statistical_test', table: 'statistical_test', params: {} },
    { id: 'counts', figure: 'counts_overview', table: 'counts_table', params: {
        layout: ['choice', ['overlay', 'panels', 'diff', 'heatmap'], 'overlay'],
        ref: REF,
        outcomes: ['choice', ['top', 'threshold', 'bits'], 'top'],
        top: ['int', [1, 64], 16],
        threshold: ['float', [0.0, 1.0], 0.01],
        bits: ['bits', null],
        other: ['bool', true],
        sort: ['choice', ['probability', 'bitstring', 'hamming'], 'probability'],
        yscale: ['choice', ['linear', 'log'], 'linear'],
        band: ['bool', true],
        keyorder: ['choice', ['msb', 'lsb'], 'msb'],
        colour: COLOUR,
    } },
    { id: 'marginals', figure: 'qubit_marginals', table: 'qubit_marginals_table', params: {
        layout: ['choice', ['lines', 'diff'], 'lines'], ref: REF, errorbars: ['bool', true], colour: COLOUR,
    } },
    { id: 'hamming', figure: 'hamming_weight', table: 'hamming_weight_table', params: {
        layout: ['choice', ['bars', 'lines', 'diff'], 'bars'], ref: REF, colour: COLOUR,
    } },
    { id: 'rank', figure: 'rank_probability', table: 'rank_probability_table', params: {
        xscale: ['choice', ['log', 'linear'], 'log'], ref: REF, colour: COLOUR,
    } },
    { id: 'fidelity_heatmap', figure: 'fidelity_heatmap', table: 'matrix_fidelity', params: {} },
    { id: 'js_divergence_heatmap', figure: 'js_divergence_heatmap', table: 'matrix_js', params: {} },
    { id: 'hellinger_heatmap', figure: 'hellinger_heatmap', table: 'matrix_hellinger', params: {} },
    { id: 'execution_time', figure: 'performance_time', table: 'performance', params: {
        stage: ['choice', ['stacked', 'simulation', 'compilation'], 'stacked'],
        xscale: ['choice', ['linear', 'log'], 'linear'],
    } },
    { id: 'resource_usage', figure: 'resource_memory', table: 'resources', params: {
        metric: ['choice', ['process_peak', 'memory_delta'], 'process_peak'],
    } },
    { id: 'metadata', table: 'metadata', params: {} },
    { id: 'glossary', text: 'glossary', params: {} },
];
export const VIEW_BY_ID = Object.fromEntries(VIEWS.map(v => [v.id, v]));
export const VIEW_OF_ARTIFACT = Object.fromEntries(VIEWS.flatMap(v =>
    ['figure', 'table', 'text'].filter(k => k in v).map(k => [v[k], v.id])));

/** Ordered {name: spec} of every parameter the view takes. */
function viewParamSpecs(viewId) {
    const v = VIEW_BY_ID[viewId];
    return Object.assign({}, COMMON_PARAMS, v.params, 'figure' in v ? FIGURE_PARAMS : {});
}

/** The view's parameters at their defaults. */
export function viewDefaults(viewId) {
    const out = {};
    Object.entries(viewParamSpecs(viewId)).forEach(([k, s]) => { out[k] = s[s.length - 1]; });
    return out;
}

/** Backends in divergence-report order, then any others present in raw_results. */
export function reportBackends(results) {
    const order = ((results.divergence_report || {}).simulators || []).slice();
    const seen = new Set(order);
    (results.raw_results || []).forEach(r => {
        const s = r.simulator;
        if (s && !seen.has(s)) { order.push(s); seen.add(s); }
    });
    return order;
}

/** Length of the longest counts key in the report (0 without counts). */
function countBits(results) {
    let n = 0;
    (results.raw_results || []).forEach(r => {
        const c = r.counts;
        if (c && typeof c === 'object' && !Array.isArray(c)) Object.keys(c).forEach(k => { n = Math.max(n, String(k).length); });
    });
    return n;
}

/** Backends with a result carrying non-empty counts, in report order (views.py counted_backends). */
function countedBackends(results) {
    const counted = new Set((results.raw_results || [])
        .filter(r => r.counts && typeof r.counts === 'object' && !Array.isArray(r.counts) && Object.keys(r.counts).length)
        .map(r => r.simulator));
    return reportBackends(results).filter(s => counted.has(s));
}

const _isInt = v => typeof v === 'number' && Number.isInteger(v);
function _check(cond, msg) { if (!cond) throw new Error(msg); }

/**
 * Validate `params` for `viewId` against `results` and fill in defaults (views.py
 * normalize_params). `backends` becomes null when it lists every backend; `ref` the first
 * selected backend with counts when null. Throws for an unknown view or parameter or a bad value.
 */
export function normalizeParams(viewId, params, results) {
    _check(viewId in VIEW_BY_ID, `unknown view '${viewId}'`);
    const specs = viewParamSpecs(viewId);
    const given = Object.assign({}, params || {});
    const unknown = Object.keys(given).filter(k => !(k in specs)).sort();
    _check(!unknown.length, `unknown parameter(s) for '${viewId}': ${unknown.join(', ')}`);
    const out = viewDefaults(viewId);
    const everyone = reportBackends(results);
    Object.entries(specs).forEach(([key, spec]) => {
        if (!(key in given) || given[key] === null || given[key] === undefined) return;
        let v = given[key];
        const kind = spec[0];
        if (kind === 'choice') {
            _check(spec[1].includes(v), `${key} must be one of ${spec[1].join(', ')}`);
        } else if (kind === 'bool') {
            _check(typeof v === 'boolean', `${key} must be true or false`);
        } else if (kind === 'int') {
            _check(_isInt(v) && spec[1][0] <= v && v <= spec[1][1], `${key} must be an integer from ${spec[1][0]} to ${spec[1][1]}`);
        } else if (kind === 'float') {
            _check(typeof v === 'number' && Number.isFinite(v) && spec[1][0] <= v && v <= spec[1][1],
                `${key} must be a number from ${_artFull(spec[1][0])} to ${_artFull(spec[1][1])}`);
        } else if (kind === 'backends') {
            _check(Array.isArray(v) && v.every(s => typeof s === 'string'), 'backends must be a list of backend ids');
            const missing = v.filter(s => !everyone.includes(s));
            _check(!missing.length, `backends not in this report: ${missing.join(', ')}`);
            v = everyone.filter(s => v.includes(s));
            _check(v.length >= 1, 'select at least one backend');
            if (v.length === everyone.length) v = null;
        } else if (kind === 'backend') {
            _check(typeof v === 'string', `${key} must be a backend id`);
        } else if (kind === 'bits') {
            const n = countBits(results);
            _check(Array.isArray(v) && v.every(_isInt), 'bits must be a list of classical bit indices');
            _check(v.length >= 1 && v.length <= MAX_MARGINAL_BITS && new Set(v).size === v.length,
                `bits must list 1 to ${MAX_MARGINAL_BITS} distinct classical bits`);
            _check(v.every(b => b >= 0 && b < n), `bits must lie between 0 and ${n - 1}`);
            v = v.slice();
        }
        out[key] = v;
    });
    if ('ref' in specs) {
        const selected = out.backends || everyone;
        const counted = countedBackends(results).filter(s => selected.includes(s));
        if (out.ref === null) out.ref = counted.length ? counted[0] : null;
        else {
            _check(selected.includes(out.ref), 'ref must be one of the selected backends');
            _check(counted.includes(out.ref), `ref must be a backend with counts; ${out.ref} has none`);
        }
    }
    if ('bits' in specs && out.bits === null) out.bits = [...Array(Math.min(3, countBits(results))).keys()];
    return out;
}

const _same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

/** File-name stem for a view: its id plus each non-default parameter (views.py view_slug). */
export function viewSlug(viewId, params, results) {
    const defaults = viewDefaults(viewId);
    if ('ref' in defaults) {
        const selected = params.backends || reportBackends(results);
        defaults.ref = countedBackends(results).find(s => selected.includes(s)) ?? null;
    }
    if ('bits' in defaults) defaults.bits = [...Array(Math.min(3, countBits(results))).keys()];
    const parts = [viewId];
    const specs = viewParamSpecs(viewId);
    Object.keys(specs).forEach(key => {
        const v = params[key];
        if (_same(v, defaults[key])) return;
        if (key === 'backends') parts.push(`${v.length}-backends`);
        else if (typeof v === 'boolean') parts.push(v ? key : `no-${key}`);
        else if (Array.isArray(v)) parts.push(`${key}-` + v.map(String).join('-'));
        else if (specs[key][0] === 'float') parts.push(`${key}-${_artSlug(_artFull(v))}`);
        else parts.push(`${key}-${_artSlug(String(v))}`);
    });
    return parts.join('_');
}

/** Append -2, -3, ... to repeated slugs, in order. */
export function dedupeSlugs(slugs) {
    const seen = {};
    return slugs.map(s => {
        seen[s] = (seen[s] || 0) + 1;
        return seen[s] === 1 ? s : `${s}-${seen[s]}`;
    });
}

const ITEM_EXTENSIONS = { latex: 'tex', markdown: 'md', text: 'txt' };
const ITEM_FIGURE_FORMATS = ['svg', 'png', 'pdf'];
const ITEM_TABLE_FORMATS = ['latex', 'csv', 'html', 'markdown', 'xlsx'];
const ITEM_TEXT_FORMATS = ['markdown', 'text'];

/** Crate paths of one export item (registry.py item_paths). */
export function itemPaths(viewId, slug, formats) {
    const view = VIEW_BY_ID[viewId];
    const paths = [];
    const figs = formats.filter(f => 'figure' in view && ITEM_FIGURE_FORMATS.includes(f));
    figs.forEach(f => paths.push(`figures/${slug}.${f}`));
    if (figs.length) paths.push(`figures/${slug}.spec.json`);
    formats.forEach(f => {
        if ('table' in view && ITEM_TABLE_FORMATS.includes(f)) paths.push(`tables/${slug}.${ITEM_EXTENSIONS[f] || f}`);
        else if ('text' in view && ITEM_TEXT_FORMATS.includes(f)) paths.push(`reference/${slug}.${ITEM_EXTENSIONS[f] || f}`);
    });
    return paths;
}
