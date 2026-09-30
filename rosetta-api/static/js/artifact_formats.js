// Publication-artifact number and column formatting, text builders and catalog. Mirrors
// services/publication (formats.py, selectors.py, tables.py, theme.py glossaries,
// registry.py catalog); tests/unit/test_artifacts_parity.py compares the two. No DOM, no
// network.

const _SCI_BELOW = 1e-3;
const _SCI_ABOVE = 1e15;
const _MAX_DIGITS = 17;
export const JS_UNIT = 'nats';
export const MAX_HISTOGRAM_PAIRS = 12;
export const COMMON_KEY_ORDER_NOTE = 'keys in msb order (classical bit 0 leftmost); lsb-declared backends bit-reversed';

/** Scientific notation with 3 significant digits and a signed 2+ digit exponent. */
function _artSci(x) {
    const [mant, exp] = x.toExponential(2).split('e');
    const e = parseInt(exp, 10);
    return `${mant}e${e < 0 ? '-' : '+'}${String(Math.abs(e)).padStart(2, '0')}`;
}

/** Format a real-valued metric (same rules as formats.py _fmt_num). */
export function _artNum(v, d = 4) {
    if (v === null || v === undefined) return '—';
    if (typeof v === 'boolean') return v ? 'true' : 'false';
    if (typeof v !== 'number') return String(v);
    if (Number.isNaN(v)) return '—';
    if (!Number.isFinite(v)) return v > 0 ? 'inf' : '-inf';
    if (v === 0) return (0).toFixed(d);
    if (Math.abs(v) < _SCI_BELOW || Math.abs(v) >= _SCI_ABOVE) return _artSci(v);
    let s = v.toFixed(d);
    if (parseFloat(s) === 0) return _artSci(v);
    let digits = d;
    while (v !== 1 && parseFloat(s) === 1 && digits < _MAX_DIGITS) {
        digits += 1;
        s = v.toFixed(digits);
    }
    return s;
}

export const P_VALUE_FLOOR = '<1e-300';

/** Format a p-value as _artNum, except an exact 0 (floating-point underflow) -> "<1e-300". */
export function _artP(v) {
    if (typeof v === 'number' && v === 0) return P_VALUE_FLOOR;
    return _artNum(v);
}

/** Format a count-like value: integral numbers without decimals, else as _artNum. */
export function _artInt(v) {
    if (typeof v === 'number' && Number.isInteger(v) && Math.abs(v) < _SCI_ABOVE) return String(v);
    return _artNum(v);
}

/** Shortest round-trip text of a finite number (formats.py _full). */
export function _artFull(x) {
    if (x === 0) return '0';
    if (Number.isInteger(x) && Math.abs(x) < _SCI_ABOVE) return String(x);
    const [mant, exp] = Math.abs(x).toExponential().split('e');
    const e = parseInt(exp, 10);
    const digits = mant.replace('.', '').replace(/0+$/, '') || '0';
    const sign = x < 0 ? '-' : '';
    if (Math.abs(x) >= _SCI_BELOW && Math.abs(x) < _SCI_ABOVE) {
        let whole, frac;
        if (e >= 0) {
            whole = digits.slice(0, e + 1).padEnd(e + 1, '0');
            frac = digits.slice(e + 1);
        } else {
            whole = '0';
            frac = '0'.repeat(-e - 1) + digits;
        }
        return sign + whole + (frac ? '.' + frac : '');
    }
    const m = digits[0] + (digits.length > 1 ? '.' + digits.slice(1) : '');
    return `${sign}${m}e${e < 0 ? '-' : '+'}${String(Math.abs(e)).padStart(2, '0')}`;
}

/** A table cell's display text; `csv` holds the text written to CSV. */
class _ArtCell {
    constructor(text, csv) { this.text = text; this.csv = csv; }
    toString() { return this.text; }
}
/** A numeric cell awaiting column formatting: `digits` places, or a p-value. */
class _ArtNumSpec {
    constructor(v, digits = 4, p = false) { this.v = v; this.digits = digits; this.p = p; }
}
const _n = (v, d = 4) => new _ArtNumSpec(v, d);
const _pn = v => new _ArtNumSpec(v, 4, true);
const _finiteNum = v => typeof v === 'number' && Number.isFinite(v);

function _needsSci(n) {
    if (!_finiteNum(n.v) || n.v === 0) return false;
    return _artNum(n.v, n.digits).includes('e');
}
function _renderNum(n, sci) {
    if (n.p && typeof n.v === 'number' && n.v === 0) return new _ArtCell(P_VALUE_FLOOR, P_VALUE_FLOOR);
    if (!_finiteNum(n.v)) {
        const text = _artNum(n.v, n.digits);
        return new _ArtCell(text, text);
    }
    return new _ArtCell(sci ? _artSci(n.v) : _artNum(n.v, n.digits), _artFull(n.v));
}
/** Column formatting (formats.py _format_columns). */
export function _formatColumns(rows) {
    const sciCols = new Set();
    rows.forEach(r => r.forEach((cell, c) => {
        if (cell instanceof _ArtNumSpec && !sciCols.has(c) && _needsSci(cell)) sciCols.add(c);
    }));
    return rows.map(r => r.map((cell, c) => (cell instanceof _ArtNumSpec ? _renderNum(cell, sciCols.has(c)) : cell)));
}

/** Format a label: null/undefined/"" -> "—", else String(v). */
export function _artText(v) {
    if (v === null || v === undefined || v === '') return '—';
    return String(v);
}

export const _ART_LATEX_ESC = {
    '\\': '\\textbackslash{}', '&': '\\&', '%': '\\%', '$': '\\$', '#': '\\#',
    '_': '\\_', '{': '\\{', '}': '\\}', '~': '\\textasciitilde{}', '^': '\\textasciicircum{}',
};
/** Escape LaTeX special characters. */
export function _artLatexEscape(s) {
    return String(s).split('').map(c => _ART_LATEX_ESC[c] || c).join('');
}
/** Python html.escape(quote=True), apostrophe as &#x27;. */
export function _artHtmlEscape(s) {
    return String(s).replace(/[&<>"']/g, c =>
        ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#x27;' }[c]));
}
/** Lower-case, each non-alphanumeric -> '-', trimmed (basename_slug). */
export function _artSlug(s) {
    return String(s).toLowerCase().replace(/[^a-z0-9]/g, '-').replace(/^-+|-+$/g, '');
}

/** booktabs LaTeX table. */
export function _artLatex({ headers, rows, title, caption }) {
    const spec = 'l'.repeat(headers.length);
    const lines = ['% Requires \\usepackage{booktabs}', '\\begin{table}[htbp]', '  \\centering',
        `  \\caption{${_artLatexEscape(title)}. ${_artLatexEscape(caption)}}`,
        `  \\label{tab:${_artSlug(title)}}`, `  \\begin{tabular}{${spec}}`, '    \\toprule',
        '    ' + headers.map(_artLatexEscape).join(' & ') + ' \\\\', '    \\midrule'];
    rows.forEach(r => lines.push('    ' + r.map(_artLatexEscape).join(' & ') + ' \\\\'));
    lines.push('    \\bottomrule', '  \\end{tabular}', '\\end{table}', '');
    return lines.join('\n');
}
/** CSV with CRLF rows (Python csv module defaults). */
export function _artCsv({ headers, rows }) {
    const esc = v => {
        const s = (v === null || v === undefined) ? '' : String(v instanceof _ArtCell ? v.csv : v);
        return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    };
    return [headers, ...rows].map(r => r.map(esc).join(',')).join('\r\n') + '\r\n';
}
/** Standalone HTML table. */
export function _artHtml({ headers, rows, title, caption }) {
    const head = headers.map(h => `<th>${_artHtmlEscape(h)}</th>`).join('');
    const body = rows.map(r => '<tr>' + r.map(c => `<td>${_artHtmlEscape(c)}</td>`).join('') + '</tr>').join('');
    return "<!doctype html><meta charset='utf-8'>"
        + "<style>body{font-family:system-ui,sans-serif;color:#0b0b0b;margin:1rem}"
        + "table{border-collapse:collapse;font-size:13px}"
        + "caption{caption-side:top;text-align:left;font-weight:600;margin-bottom:.4rem}"
        + "th,td{border-bottom:1px solid #e1e0d9;padding:4px 10px;text-align:left}"
        + "thead th{border-bottom:2px solid #c3c2b7}.cap{color:#52514e;font-weight:400;font-size:12px}</style>"
        + `<table><caption>${_artHtmlEscape(title)}<div class='cap'>${_artHtmlEscape(caption)}</div></caption>`
        + `<thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}
/** Markdown table preceded by a bold title line. */
export function _artMarkdown({ headers, rows, title, caption }) {
    const esc = v => String(v).replace(/\|/g, '\\|');
    const lines = [`**${title}** — ${caption}`, '',
        '| ' + headers.map(esc).join(' | ') + ' |',
        '| ' + headers.map(() => '---').join(' | ') + ' |'];
    rows.forEach(r => lines.push('| ' + r.map(esc).join(' | ') + ' |'));
    lines.push('');
    return lines.join('\n');
}
/** Render table data in `fmt`. */
export function _renderTable(fmt, data) {
    return { latex: _artLatex, csv: _artCsv, html: _artHtml, markdown: _artMarkdown }[fmt](data);
}

// ---- report accessors (selectors.py) ----
/** "a × b" for a pairwise record. */
export function _artPairKey(rec) {
    const s = rec.simulators || ['?', '?'];
    return `${s[0]} × ${s[1]}`;
}
/** The pairwise_agreement list, or []. */
export function _artPairwise(div) { return Array.isArray(div.pairwise_agreement) ? div.pairwise_agreement : []; }

/** Map simulator -> its first raw result. */
function _artRawBySim(results) {
    const out = {};
    (results.raw_results || []).forEach(r => {
        const sim = r.simulator;
        if (sim !== null && sim !== undefined && !(sim in out)) out[sim] = r;
    });
    return out;
}

const _FAILED_STATUSES = ['error', 'timeout', 'offline'];

/** Ranked entries in rank order, then unranked entries, as {entry, raw, ranked, failed, rank, status}. */
export function _artReportRows(results, reportKey) {
    const report = results[reportKey] || {};
    const raw = _artRawBySim(results);
    const rows = [];
    [[true, report.ranking || []], [false, report.unranked || []]].forEach(([ranked, entries]) => {
        entries.forEach((e, i) => {
            const r = raw[e.simulator] || {};
            let status = r.dispatch_status || r.status || e.status || '—';
            if (status === 'success') status = 'ok';
            const failed = !ranked && _FAILED_STATUSES.includes(status);
            let rank = '—';
            if (ranked) rank = _artInt((e.rank !== null && e.rank !== undefined) ? e.rank : i + 1);
            else if (e.reason && e.reason !== 'runner_error') status = `${status} (${e.reason})`;
            else if (!failed) status = `${status} (${e.reason || 'unranked'})`;
            rows.push({ entry: e, raw: r, ranked, failed, rank, status });
        });
    });
    return rows;
}

/** `key` from the report entry, falling back to the raw result; null for failed runs. */
function _artField(row, key) {
    if (row.failed) return null;
    const v = row.entry[key];
    return (v === null || v === undefined) ? row.raw[key] : v;
}

export const DEVICE_NOTE = 'Device is the hardware the simulation ran on (CPU when the run reports '
    + 'none). CPU runners are limited to 0.5 CPU and 1 thread each; GPU runners '
    + 'execute kernels on the GPU while their host-side work is under the same 0.5-CPU '
    + 'quota, so timings across devices compare different hardware.';
export const GPU_MEMORY_NOTE = 'Memory fields are host RSS and do not include GPU device memory; GPU runs '
    + 'are not ranked (gpu_memory_not_measured).';

/** The row's device from the report entry, else the raw result, upper-cased; "CPU" when neither records one. */
export function _artDevice(row) {
    for (const src of [row.entry || {}, row.raw || {}]) {
        const v = src.device;
        if (v !== null && v !== undefined && v !== '') return String(v).toUpperCase();
    }
    return 'CPU';
}

/** Distinct non-empty values of `key` across raw results, comma-joined, or "not recorded". */
export function _artDistinct(results, key) {
    const seen = [];
    (results.raw_results || []).forEach(r => {
        const v = r[key];
        if (v !== null && v !== undefined && v !== '' && !seen.includes(_artText(v))) seen.push(_artText(v));
    });
    return seen.length ? seen.join(', ') : 'not recorded';
}

/** Timing samples per backend: results.timing_samples, else the raw results' values, else 1. */
export function _artTimingSamples(results) {
    const top = results.timing_samples;
    if (top !== null && top !== undefined) return _artInt(top);
    const vals = [];
    (results.raw_results || []).forEach(r => {
        const v = r.timing_samples;
        if (v !== null && v !== undefined && !vals.includes(_artInt(v))) vals.push(_artInt(v));
    });
    return vals.length ? vals.join('/') : '1';
}

// ---- repeated timing (services/analysis/timing.py) ----
const _TIMING_BASES = ['compilation_time', 'simulation_time', 'execution_time'];
const _isFiniteNum = v => typeof v === 'number' && Number.isFinite(v);

function _artListedSamples(res, base) {
    for (const key of [`${base}_samples`, `${base}_sec_samples`]) {
        const v = res[key];
        if (Array.isArray(v) && v.length && v.every(_isFiniteNum)) return v.slice();
    }
    return null;
}
/** Per-run samples of `base` on a result, or null (timing.py timing_samples). */
export function _artTimingSampleList(res, base) {
    let samples = _artListedSamples(res, base);
    if (samples === null && base === 'execution_time') {
        const comp = _artListedSamples(res, 'compilation_time');
        const sim = _artListedSamples(res, 'simulation_time');
        if (comp && sim && comp.length === sim.length) samples = comp.map((c, i) => c + sim[i]);
    }
    return samples;
}
function _artQuantile(ordered, q) {
    const pos = (ordered.length - 1) * q;
    const lo = Math.floor(pos);
    const hi = Math.min(lo + 1, ordered.length - 1);
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo);
}
/** {n, median, q1, q3, iqr, stdev} of a sample list (timing.py summarize). */
export function _artSummarize(samples) {
    const ordered = samples.slice().sort((a, b) => a - b);
    const n = ordered.length;
    let total = 0.0;
    for (const x of ordered) total += x;
    const mean = total / n;
    let ss = 0.0;
    for (const x of ordered) { const d = x - mean; ss += d * d; }
    const q1 = _artQuantile(ordered, 0.25), q3 = _artQuantile(ordered, 0.75);
    const mid = Math.floor(n / 2);
    const median = n % 2 ? ordered[mid] : (ordered[mid - 1] + ordered[mid]) / 2;
    return { n, median, q1, q3, iqr: q3 - q1,
        stdev: n > 1 ? Math.sqrt(ss / (n - 1)) : 0.0 };
}
/** _artSummarize of the result's `base` samples when it has at least two, else null. */
export function _artTimingSummary(res, base) {
    const samples = _artTimingSampleList(res, base);
    if (samples === null || samples.length < 2) return null;
    return _artSummarize(samples);
}
function _artTimingStats(row, key) {
    const base = key.endsWith('_sec') ? key.slice(0, -4) : key;
    if (row.failed || !_TIMING_BASES.includes(base)) return null;
    return _artTimingSummary(row.raw || {}, base);
}
/** Median of `base` over two or more samples, else null; total = median compilation + median simulation (timing.py stage_median). */
export function _artStageMedian(res, base) {
    if (base === 'execution_time') {
        const comp = _artTimingSummary(res, 'compilation_time');
        const sim = _artTimingSummary(res, 'simulation_time');
        if (comp && sim) return comp.median + sim.median;
    }
    const stats = _artTimingSummary(res, base);
    return stats ? stats.median : null;
}
function _artTimingValue(row, key) {
    const base = key.endsWith('_sec') ? key.slice(0, -4) : key;
    if (!row.failed && _TIMING_BASES.includes(base)) {
        const median = _artStageMedian(row.raw || {}, base);
        if (median !== null) return median;
    }
    return _artField(row, key);
}
/** True when any successful result has two or more total-time samples. */
export function _artTimingRepeated(results) {
    return (results.raw_results || []).some(r => r && typeof r === 'object'
        && (r.error === null || r.error === undefined || r.error === '')
        && _artTimingSummary(r, 'execution_time') !== null);
}

// ---- glossaries (theme.py) ----
export const AGREEMENT_GLOSSARY = [
    ['agree_directly', 'Outputs match directly, no transform needed. For a statevector pair this requires the same declared qubit ordering, or a one-qubit circuit, where bit reversal is the identity.'],
    ['agree_up_to_global_phase', 'Match after removing the global phase offset arg⟨a|b⟩ between the two states, which is unobservable. An offset within phase_tolerance is reported as 0 and the pair agrees directly.'],
    ['agree_after_bit_reversal', 'Match after reversing qubit/bit order, the transform the declared orderings imply when one backend is lsb and the other msb. A statevector pair gets this label only for such a pair; transform_effect.global_phase_aligned is true when a global phase offset remains after the reversal. For a measured pair whose declared bit orders differ the label means the pair agrees in the label-aligned (bit-reversed) basis; it is used by convention even when the direct distances are equal too, as for GHZ-type outcomes that bit reversal leaves unchanged.'],
    ['agree_after_qubit_permutation', 'Disagreement: agrees only after an undeclared qubit permutation (searched up to ≤7 qubits). No declared ordering implies the permutation, so the pair is counted as a disagreement.'],
    ['agree_after_normalization', 'At least one input statevector has a norm differing from 1 by more than norm_tolerance; the normalised vectors agree. metrics.normalized_agreement holds the label the normalised pair receives. The default norm_tolerance (1e-4) lies above complex64 rounding, which leaves norms about 2e-6 from 1.'],
    ['residual_disagreement', 'Statevector disagreement in the label-aligned basis that no registered transform explains. metrics.unaligned_basis_match is "direct" or "bit_reversal" when the pair matches only in the basis its declared orderings do not imply, as when an lsb and an msb backend return equal vectors for an asymmetric state.'],
    ['distance_within_threshold', 'Measured distributions within the JS-divergence and Hellinger thresholds without a bit-order transform (descriptive, configurable; the shot-noise statistical test gives the significance verdict).'],
    ['distance_exceeds_threshold', 'Measured distributions exceed the (descriptive, configurable) thresholds after registered transforms; see the statistical test for significance.'],
    ['not_comparable', 'At least one side lacks usable output; the pair cannot be compared. metrics.reason names the cause.'],
];
export const NOT_COMPARABLE_GLOSSARY = [
    ['missing_statevector', 'A run returned no statevector.'],
    ['statevector_parse_error', 'A returned statevector could not be decoded.'],
    ['empty_statevector', 'A statevector has no amplitudes.'],
    ['nonfinite_statevector', 'A statevector contains NaN or infinite amplitudes.'],
    ['zero_norm_statevector', 'A statevector has norm 0.'],
    ['shape_mismatch', 'The two statevectors have different lengths.'],
    ['missing_counts', 'A run returned no counts.'],
    ['empty_counts', 'A counts dictionary is empty.'],
    ['invalid_bitstring_key', 'A counts key is not a non-empty string.'],
    ['non_numeric_counts', 'A count value is not a real number (strings and booleans included).'],
    ['nonfinite_counts', 'A count value is NaN or infinite.'],
    ['negative_counts', 'A count value is negative.'],
    ['zero_total_counts', 'A counts dictionary sums to 0.'],
    ['nonfinite_metric', 'A distance metric evaluated to NaN or infinity.'],
    ['comparison_error', 'The comparison raised an exception; metrics.details.error holds the message.'],
];
export const VERDICT_GLOSSARY = [
    ['consistent', "Neither the chi-square test nor the G-test is significant after Benjamini-Yekutieli (BY, FDR) correction over the m comparable pairs, and the power to detect a total-variation gap of 0.05 at the observed shots is at least 0.8. Power is that of the chi-square test at alpha/(m·c_m) (power.alpha_used, power.m_pairs, power.c_m; c_m = 1 + 1/2 + ... + 1/m), the threshold BY applies to a single discovery, on df = tested outcome bins - 1 with Cohen's w = 0.05: a lower bound for detecting one wrong backend."],
    ['distinguishable', "Both tests are significant after BY (FDR) correction. BY keeps the expected share of false discoveries among flagged pairs at most q = 0.05 under any dependence between the tests, including pairs that share one backend's sample; a flagged pair can still be a false discovery."],
    ['inconclusive_low_shots', 'Expected counts stay below 5 after pooling rare outcomes (inconclusive_reason = low_expected_counts), or neither test is significant and the power at alpha/(m·c_m) to detect a total-variation gap of 0.05 is below 0.8 (inconclusive_reason = low_power). resolvable_by_more_shots is false when no shot count up to the platform maximum would give a testable table (low_expected_counts) or the target power (low_power); shots_per_backend_for_expected_counts gives the count that would. power.recommended_exceeds_actual is true when the recommended shots per backend exceed the shots used.'],
    ['ambiguous', 'Exactly one of the chi-square test and the G-test is significant after BY (FDR) correction.'],
];
export const ASSESSMENT_GLOSSARY = [
    ['consistent_within_shot_noise', 'The shot-noise verdict is consistent: neither test separates the distributions at a shot count with power of at least 0.8, whatever the distance label.'],
    ['distinguishable', 'The shot-noise verdict is distinguishable: the distributions differ beyond sampling noise, subject to the FDR share of false discoveries.'],
    ['ambiguous', 'Exactly one of the two tests is significant.'],
    ['inconclusive_low_shots', 'The shot count cannot separate the distributions: expected counts stay below 5 after pooling, or the test is not significant at power below 0.8 (evaluated at alpha/(m·c_m)).'],
    ['not_comparable', 'At least one side lacks usable counts.'],
];
export const UNRANKED_GLOSSARY = [
    ['runner_error', 'The run failed; Status gives the dispatch status (error, timeout or offline) and its metrics are shown as —.'],
    ['missing_timing', 'The run returned no execution_time_sec.'],
    ['missing_process_peak_rss', 'The run returned no process_peak_rss_mb.'],
    ['gpu_memory_not_measured', 'The run executed on a GPU. The memory fields are host RSS and do not include GPU device memory, so the run is not ranked by memory.'],
];
export const MEASUREMENT_NOTES = [
    'Global phase offset arg⟨a|b⟩: the phase of the inner product of two normalised statevectors. It is a global-phase difference between the states, not a relative phase between components of one superposition. The JSON fields relative_phase_matrix and *relative_phase* keep their names for compatibility.',
    "Label-aligned basis: for a pair whose declared qubit orderings differ (lsb vs msb) the second backend's output is bit-reversed (statevector amplitudes or counts keys); otherwise it is compared directly, and on a one-qubit circuit bit reversal is the identity. Statevector labels, the statistical tests and the label-aligned distances use this basis; the direct values are recorded as well.",
    'Outcomes with an expected count below 5 are pooled into one bin before the chi-square and G-tests; statistical_test.pooled_outcomes gives how many were pooled.',
    'Benjamini-Yekutieli controls the false discovery rate at q = alpha under arbitrary dependence between the p-values; pairs that share a backend reuse its sample and are dependent. Its threshold is alpha·i/(m·c_m) with c_m = 1 + 1/2 + ... + 1/m. BH-adjusted p-values are recorded for reference (p_value_bh) and do not set the verdict.',
];
export const ANALYSIS_VERSION = 'divergence-2026.09.30.2';
export const ANALYSIS_VERSION_NOTE = `Analysis version ${ANALYSIS_VERSION} (analysis_version in each divergence report). The `
    + 'labels and verdicts are a function of the outputs and of the analysis rules; verdicts '
    + 'computed under different analysis versions may differ for identical counts.';
export const THRESHOLD_DEFAULTS = 'fidelity_tolerance = 1e-5, phase_tolerance = 1e-6 rad, '
    + 'norm_tolerance = 1e-4, js_threshold = 0.01 nats, hellinger_threshold = 0.1';

// ---- table builders (tables.py) ----
/** One row per backend pair: label, transform, key metric(s), verdict and assessment (measured), reason. */
export function _dataAgreement(div, mode) {
    const measured = mode === 'measured';
    const headers = ['Pair', 'Agreement', 'Registered transform'];
    if (measured) headers.push(`JS, direct (${JS_UNIT})`, `JS, label-aligned basis (${JS_UNIT})`, 'Stat verdict', 'Measured assessment');
    else headers.push('Direct fidelity', 'Fidelity, label-aligned basis', 'Unaligned-basis match');
    headers.push('Not-comparable reason');
    const rows = _formatColumns(_artPairwise(div).map(r => {
        const m = r.metrics || {};
        const metric = r.mode === 'statevector' ? m.direct_fidelity : m.js_divergence;
        const row = [_artPairKey(r), _artText(r.agreement), _artText(r.registered_transform), _n(metric)];
        if (measured) row.push(_n(m.label_aligned_js_divergence), _artText((m.statistical_test || {}).verdict), _artText(r.measured_assessment));
        else row.push(_n(m.label_aligned_fidelity), _artText(m.unaligned_basis_match));
        row.push(r.agreement === 'not_comparable' ? _artText(m.reason) : '—');
        return row;
    }));
    const metricNote = measured
        ? `JS, direct is the Jensen–Shannon divergence in ${JS_UNIT} of the keys as reported; JS, label-aligned basis bit-reverses the second backend's keys when the two declared bit orders differ (lsb vs msb) and equals the direct value otherwise`
        : 'Direct fidelity is |<a|b>|^2 of the normalised vectors before any transform; '
            + 'the label-aligned basis bit-reverses the second vector when the two declared '
            + 'qubit orderings differ (lsb vs msb) and the label is assigned in it. '
            + 'Unaligned-basis match names the other basis when the pair matches only there, '
            + 'which is a disagreement';
    let caption = 'Classification over the registered-transform lattice; each label reports the '
        + `transform whose numerical effect explains the pair. ${metricNote}.`;
    if (measured) {
        caption += ' Measured assessment combines the descriptive label with the shot-noise '
            + 'verdict: a pair over the distance thresholds whose verdict is consistent '
            + 'is consistent_within_shot_noise.';
    }
    return { headers, rows, title: 'Pairwise explained-cause agreement', caption };
}
/** The N×N matrix `key` with the diagonal and not-compared (null) cells shown as "—". */
export function _dataMatrix(div, key, title) {
    const labels = div.simulators || [];
    const mat = div[key];
    const headers = [''].concat(labels);
    const rows = _formatColumns(labels.map((s1, i) => [s1].concat(labels.map((_, j) => {
        const v = mat[i][j];
        return (i === j || v === null || v === undefined || v === -1.0) ? '—' : _n(v);
    }))));
    return { headers, rows, title, caption: `${title} (raw metric; not-compared pairs and the diagonal shown as —). Symmetric matrix.` };
}
/** Per-backend timings: ranked runs by total time, then unranked runs with the reason. */
export function _dataPerformance(results) {
    if (_artTimingRepeated(results)) return _dataPerformanceRepeated(results);
    return {
        headers: ['Rank', 'Simulator', 'Device', 'Compilation (s)', 'Simulation (s)', 'Total (s)',
            'Simulation CPU (s)', 'Process CPU (s)', 'Gate count', 'Depth', 'Status'],
        rows: _formatColumns(_artReportRows(results, 'performance_report').map(row => [row.rank,
            _artText(row.entry.simulator), _artDevice(row),
            _n(_artField(row, 'compilation_time_sec'), 6),
            _n(_artField(row, 'simulation_time_sec'), 6),
            _n(_artField(row, 'execution_time_sec'), 6),
            _n(_artField(row, 'simulation_cpu_time_sec'), 6),
            _n(_artField(row, 'cpu_time_sec'), 6),
            _artInt(_artField(row, 'gate_count')), _artInt(_artField(row, 'circuit_depth')),
            row.status])),
        title: 'Execution timing',
        caption: `Wall-clock times of the timed run, n=${_artTimingSamples(results)} timing sample(s) `
            + 'per backend; a warm-up run precedes it and is not included. Total = compilation '
            + '+ simulation. Simulation CPU is process CPU time over the simulation window. '
            + 'Process CPU is getrusage CPU time of the whole isolated runner process, '
            + 'including interpreter start, imports and the warm-up. Ranked by total time, '
            + 'fastest first; runs without a rank follow with the reason in Status. Gate '
            + "count and depth are taken from each backend's transpiled QASM. "
            + DEVICE_NOTE,
    };
}
/** _dataPerformance with median stage times and the spread of total time. */
function _dataPerformanceRepeated(results) {
    return {
        headers: ['Rank', 'Simulator', 'Device', 'Compilation median (s)', 'Simulation median (s)',
            'Total median (s)', 'Total IQR (s)', 'Total stdev (s)', 'n',
            'Simulation CPU (s)', 'Process CPU (s)', 'Gate count', 'Depth', 'Status'],
        rows: _formatColumns(_artReportRows(results, 'performance_report').map(row => {
            const total = _artTimingStats(row, 'execution_time_sec');
            const n = total ? total.n : (row.failed ? null : 1);
            return [row.rank, _artText(row.entry.simulator), _artDevice(row),
                _n(_artTimingValue(row, 'compilation_time_sec'), 6),
                _n(_artTimingValue(row, 'simulation_time_sec'), 6),
                _n(_artTimingValue(row, 'execution_time_sec'), 6),
                _n(total ? total.iqr : null, 6),
                _n(total ? total.stdev : null, 6),
                _artInt(n),
                _n(_artField(row, 'simulation_cpu_time_sec'), 6),
                _n(_artField(row, 'cpu_time_sec'), 6),
                _artInt(_artField(row, 'gate_count')), _artInt(_artField(row, 'circuit_depth')),
                row.status];
        })),
        title: 'Execution timing',
        caption: 'Median wall-clock times over the n timed runs of each backend (column n); a '
            + 'warm-up run precedes them and is not included. Total median = compilation '
            + 'median + simulation median, the reported execution_time_sec. Total IQR is the '
            + 'interquartile range (Q3 - Q1, linear interpolation) and Total stdev the sample '
            + 'standard deviation (n - 1) of the per-run totals (compilation + simulation); '
            + 'both are — for a backend with one run. Simulation CPU and process CPU '
            + 'are from the last timed run; process CPU is getrusage CPU time of the whole '
            + 'isolated runner process, including interpreter start, imports and the '
            + 'warm-up. Ranked by median total time, fastest first; runs without a rank '
            + 'follow with the reason in Status. Gate count and depth are taken from each '
            + `backend's transpiled QASM. ${DEVICE_NOTE}`,
    };
}
/** Per-backend memory: ranked runs by process peak RSS, then unranked runs with the reason. */
export function _dataResources(results) {
    return {
        headers: ['Rank', 'Simulator', 'Device', 'Process peak RSS (MiB)',
            'Sim-window peak RSS (MiB)', 'Sim-window RSS delta (MiB)', 'Theoretical SV (MiB)',
            'Precision', 'Status'],
        rows: _formatColumns(_artReportRows(results, 'resource_report').map(row => [row.rank,
            _artText(row.entry.simulator), _artDevice(row),
            _n(_artField(row, 'process_peak_rss_mb'), 1),
            _n(_artField(row, 'process_peak_mb'), 1),
            _n(_artField(row, 'memory_usage_mb')),
            _n(_artField(row, 'theoretical_statevector_mb')),
            _artText(_artField(row, 'precision')), row.status])),
        title: 'Resource usage',
        caption: 'Process peak RSS is the peak resident memory of the simulating process over its '
            + 'whole life (interpreter start, imports, warm-up and timed run); method: '
            + `${_artDistinct(results, 'process_peak_rss_method')}. Rows are ranked by it, lowest `
            + 'first; runs without a rank follow with the reason in Status. Sim-window peak RSS '
            + 'and RSS delta (peak minus RSS at monitor entry) cover the pre-execute step and '
            + `simulation window of the timed run; method: ${_artDistinct(results, 'memory_method')}. `
            + 'Theoretical SV is 2^n × 16 bytes for the declared qubit count. 1 MiB = 1024^2 bytes. '
            + 'For small circuits process peak RSS is dominated by the SDK import footprint; '
            + "the sim-window RSS delta is the simulation's own allocation. "
            + `${GPU_MEMORY_NOTE} ${DEVICE_NOTE}`,
    };
}
/** The verdict, followed by the inconclusive reason in parentheses when one is set. */
function _artVerdictText(st) {
    const verdict = _artText(st.verdict);
    let reason = st.inconclusive_reason;
    if (!reason) return verdict;
    if (st.resolvable_by_more_shots === false) reason += '; not resolvable by more shots';
    return `${verdict} (${reason})`;
}
/** " = <alpha_used> (m = <m_pairs>, c_m = <c_m>)" from the first record that records them, else "". */
function _artPowerAlphaText(recs) {
    for (const r of recs) {
        const pw = r.metrics.statistical_test.power || {};
        const has = v => v !== null && v !== undefined;
        if (has(pw.alpha_used) && has(pw.m_pairs)) {
            const cm = has(pw.c_m) ? `, c_m = ${_artNum(pw.c_m)}` : '';
            return ` = ${_artNum(pw.alpha_used)} (m = ${_artInt(pw.m_pairs)}${cm})`;
        }
    }
    return '';
}
/** Per-pair chi-square and G-test p-values, effect sizes, power and verdict. */
export function _dataStatistical(div) {
    const recs = _artPairwise(div).filter(r => (r.metrics || {}).statistical_test);
    return {
        headers: ['Pair', 'Basis', 'chi2 p', 'chi2 p (BY)', 'G-test p', 'G-test p (BY)',
            'Total variation', "Cramér's V", 'Power@obs', 'Shots/backend for power',
            'Pooled outcomes', 'Verdict'],
        rows: _formatColumns(recs.map(r => {
            const st = r.metrics.statistical_test, ef = st.effect_size || {}, pw = st.power || {},
                c = st.chi2 || {}, g = st.g_test || {};
            return [_artPairKey(r), _artText(st.basis), _pn(c.p_value), _pn(c.p_value_by),
                _pn(g.p_value), _pn(g.p_value_by), _n(ef.total_variation), _n(ef.cramers_v),
                _n(pw.power_to_detect_delta_at_observed_shots, 3),
                _artInt(pw.shots_per_backend_for_target_power), _artInt(st.pooled_outcomes),
                _artVerdictText(st)];
        })),
        title: 'Shot-noise statistical test',
        caption: 'Shot-noise-aware homogeneity tests (chi-square + G-test) in the label-aligned '
            + 'basis (bit-reversed when the declared bit orders differ), with '
            + 'Benjamini-Yekutieli (BY) adjusted p-values and effect size. A pair is '
            + 'distinguishable only when both tests are significant after BY over the m '
            + 'comparable pairs. BY controls the false discovery rate at q = 0.05 under any '
            + "dependence between the tests, including pairs that share one backend's "
            + 'sample; a flagged pair can still be a false discovery. Power@obs is the power '
            + 'of the chi-square test to detect a total-variation gap of 0.05 at '
            + `alpha/(m·c_m)${_artPowerAlphaText(recs)}, the threshold BY applies to a `
            + 'single discovery: a lower bound for detecting one wrong backend. Outcomes with '
            + 'an expected count below 5 are pooled into one bin. A non-significant pair with '
            + 'power below 0.8 is inconclusive_low_shots.',
    };
}
/** Per-backend SDK versions, ordering and sampling labels, opt level and status. */
export function _dataMetadata(results, mode) {
    const rows = (results.raw_results || []).map(r => {
        const sdk = Object.entries(r.sdk_versions || {}).map(([k, v]) => `${k}=${_artText(v)}`).join(', ') || '—';
        const status = r.dispatch_status || r.status || ((r.error !== null && r.error !== undefined) ? 'error' : 'ok');
        let device = _artDevice({ entry: {}, raw: r });
        if (r.gpu_name) device += ` (${_artText(r.gpu_name)})`;
        return [_artText(r.simulator), device, sdk, _artText(r.qubit_ordering), _artText(r.sampling_method),
            _artInt(r.optimization_level), _artText(status)];
    });
    let run = `mode=${mode}`;
    if (results.n_shots !== undefined && results.n_shots !== null) run += `, n_shots=${_artInt(results.n_shots)}`;
    if (results.seed !== undefined && results.seed !== null) run += `, seed=${_artInt(results.seed)}`;
    return { headers: ['Simulator', 'Device', 'SDK versions', 'Qubit ordering', 'Sampling method', 'Opt level', 'Status'],
        rows, title: 'Run and provenance metadata',
        caption: `Run + provenance metadata (${run}). Ground-truth executed versions and endpoint labels.` };
}
/** The transpiled QASM `runner` executed, with a two-line comment header. */
export function _txtExecutedQasm(results, runner) {
    const r = (results.raw_results || []).find(x => x.simulator === runner);
    if (!r) return `// no result for runner ${runner}`;
    const header = `// Executed (transpiled) OpenQASM for backend: ${runner}\n`
        + `// This is the exact circuit the ${runner} adapter ran (after preprocessing).\n`;
    return header + (r.transpiled_qasm || '// (no transpiled QASM recorded for this runner)');
}
/** Markdown glossary of agreement labels, not-comparable reasons and (measured) verdicts. */
export function _txtGlossary(mode) {
    const out = ['# QRosetta agreement taxonomy — glossary', '', 'Agreement classes (registered-transform lattice):', ''];
    AGREEMENT_GLOSSARY.forEach(([l, d]) => out.push(`- **${l}** — ${d}`));
    out.push('', 'Not-comparable reasons (metrics.reason):', '');
    NOT_COMPARABLE_GLOSSARY.forEach(([l, d]) => out.push(`- **${l}** — ${d}`));
    if (mode === 'measured') {
        out.push('', 'Shot-noise statistical verdicts (reported alongside the descriptive label):', '');
        VERDICT_GLOSSARY.forEach(([l, d]) => out.push(`- **${l}** — ${d}`));
        out.push('', 'Measured assessment (measured_assessment, from the verdict):', '');
        ASSESSMENT_GLOSSARY.forEach(([l, d]) => out.push(`- **${l}** — ${d}`));
    }
    out.push('', 'Measurement notes:', '');
    MEASUREMENT_NOTES.forEach(n => out.push(`- ${n}`));
    out.push('', 'Unranked runs in the timing and resource tables (reason):', '');
    UNRANKED_GLOSSARY.forEach(([l, d]) => out.push(`- **${l}** — ${d}`));
    out.push('', `Default thresholds: ${THRESHOLD_DEFAULTS}. A run may override them; the values applied are recorded in each pairwise record and in the divergence report's agreement_thresholds. JS divergence is in ${JS_UNIT} (maximum ln 2).`,
        '', ANALYSIS_VERSION_NOTE, '', 'Each label names the registered transform that explains the pair and reports its numerical effect; the per-pair records carry full provenance.');
    return out.join('\n');
}

// ---- catalog (registry.py _iter_artifacts) ----
/** "measured" when the report has n_shots, else "statevector". */
export function _artifactMode(results) { return ('n_shots' in results) ? 'measured' : 'statevector'; }

/** Artifacts available for `results`: {id, label, group, view, formats, legend[, getText]}. */
export function buildArtifactCatalog(results) {
    const div = results.divergence_report || {};
    const mode = _artifactMode(results);
    const items = [];
    const table = (id, label, group, dataFn, legend) => items.push({
        id, label, group, view: 'text', formats: ['latex', 'csv', 'html', 'markdown'], legend,
        getText: fmt => _renderTable(fmt, dataFn()),
    });
    const blob = (id, label, group, formats, textFn, legend) => items.push({
        id, label, group, view: 'text', formats, legend, getText: () => textFn(),
    });
    const image = (id, label, group, legend) => items.push({
        id, label, group, view: 'image', formats: ['svg', 'png', 'pdf'], legend,
    });

    const pairwise = _artPairwise(div);
    if (pairwise.length) {
        image('agreement_distribution', 'Agreement class distribution', 'Agreement',
            'Bar chart of how many backend pairs fall into each agreement label (transform-explained, residual or not comparable)' + (mode === 'measured' ? ' and shot-noise verdict' : '') + '.');
        table('agreement', 'Pairwise agreement table', 'Agreement', () => _dataAgreement(div, mode),
            `One row per backend pair: explained-cause label, registered transform, key metric (direct fidelity, or JS divergence in ${JS_UNIT} direct and in the label-aligned basis), statistical verdict and measured assessment (measured) and not-comparable reason.`);
    }
    const heat = mode === 'statevector'
        ? [['fidelity_matrix', 'Raw statevector fidelity (no transform)', 'fidelity']]
        : [['statistical_distance_matrix (js_divergence)', `Raw Jensen–Shannon divergence (${JS_UNIT})`, 'js_divergence'],
           ['hellinger_distance_matrix', 'Raw Hellinger distance', 'hellinger']];
    const multi = (div.simulators || []).length >= 2;
    heat.forEach(([key, title, base]) => {
        if (multi && Array.isArray(div[key]) && div[key].length) {
            const short = title.split('(')[0].trim();
            image(`${base}_heatmap`, `${short} heatmap`, 'Divergence',
                `${title}: N×N heatmap; darker = larger value. Not-compared pairs and the diagonal shown neutral.`);
            const mid = { fidelity: 'matrix_fidelity', js_divergence: 'matrix_js', hellinger: 'matrix_hellinger' }[base];
            table(mid, `${short} matrix (table)`, 'Divergence', () => _dataMatrix(div, key, title),
                `${title} as a copyable N×N matrix table (raw metric).`);
        }
    });
    const unrankedNote = 'runs without a rank are listed with their status and reason and have no bar.';
    const perf = results.performance_report || {};
    const repeated = _artTimingRepeated(results);
    if ((perf.ranking || []).length || (perf.unranked || []).length) {
        image('performance_time', 'Execution-time chart', 'Performance',
            'Stacked compilation + simulation wall-clock time per backend '
            + (repeated ? '(median of each stage over the timed runs), ' : '(raw), ')
            + `n=${_artTimingSamples(results)} timing sample(s) per backend; GPU runs are labelled (GPU); ` + unrankedNote);
        table('performance', 'Execution-time table', 'Performance', () => _dataPerformance(results),
            'Per-backend device, compilation, simulation and total wall-clock time'
            + (repeated ? ' (medians, with the IQR, stdev and n of total time)' : '')
            + ', simulation and process CPU time, and status (raw).');
    }
    const res = results.resource_report || {};
    if ((res.ranking || []).length || (res.unranked || []).length) {
        image('resource_memory', 'Process peak RSS chart', 'Resources',
            "Peak RSS of each backend's simulating process over its whole life (interpreter start, imports, warm-up and timed run), in MiB; method: "
            + `${_artDistinct(results, 'process_peak_rss_method')}. Ranked lowest first; GPU runs are labelled (GPU) and not ranked because GPU device memory is not measured; ` + unrankedNote);
        table('resources', 'Resource-usage table', 'Resources', () => _dataResources(results),
            'Per-backend device, process peak RSS, sim-window peak RSS and RSS delta, theoretical statevector size, precision and status (raw).');
    }
    if (mode === 'measured') {
        if (pairwise.some(r => (r.metrics || {}).statistical_test)) {
            table('statistical_test', 'Statistical-test table', 'Statistical', () => _dataStatistical(div),
                'Chi-square + G-test p-values (raw + BY) in the label-aligned basis, effect size, power and pooled outcomes per pair.');
        }
        const rawCounts = {};
        (results.raw_results || []).forEach(r => {
            const c = r.counts;
            if (c && typeof c === 'object' && !Array.isArray(c) && Object.keys(c).length) rawCounts[r.simulator] = c;
        });
        const missing = [];
        (results.raw_results || []).forEach(r => {
            const sim = r.simulator;
            if (sim && !(sim in rawCounts) && !missing.includes(sim)) missing.push(sim);
        });
        const missingNote = missing.length ? ` Backends without counts are not drawn: ${missing.join(', ')}.` : '';
        if (Object.keys(rawCounts).length >= 2) {
            image('counts_overview', 'Count overview (all backends)', 'Statistical',
                `Clustered bar histogram of measured probabilities, one colour per backend over the top outcomes (Qiskit plot_histogram convention), ${COMMON_KEY_ORDER_NOTE}; low-probability outcomes are folded into 'other' (disclosed in-figure).` + missingNote);
            image('counts_overview_heatmap', 'Count overview heatmap (optional)', 'Statistical',
                `Optional compact view: outcome × backend probability heatmap, ${COMMON_KEY_ORDER_NOTE}; a uniform row = agreement, a varying row = disagreement. Scales to many backends.` + missingNote);
        }
        const eligible = pairwise.filter(rec => {
            const [a, b] = rec.simulators || [null, null];
            return rawCounts[a] && rawCounts[b];
        });
        const capNote = eligible.length > MAX_HISTOGRAM_PAIRS
            ? ` Histograms are generated for the first ${MAX_HISTOGRAM_PAIRS} of ${eligible.length} backend pairs with counts.`
            : '';
        eligible.slice(0, MAX_HISTOGRAM_PAIRS).forEach(rec => {
            const [a, b] = rec.simulators;
            image(`histogram_${_artSlug(a + '_' + b)}`, `Count histogram: ${a} vs ${b}`, 'Statistical',
                `Measured probability distributions for ${a} vs ${b}, ${COMMON_KEY_ORDER_NOTE}.` + capNote);
        });
    }
    if ((results.raw_results || []).length) {
        table('metadata', 'Run + provenance metadata', 'Metadata', () => _dataMetadata(results, mode),
            'Backends, device, SDK versions, qubit-ordering & sampling labels, opt level, run params.');
        (results.raw_results || []).forEach(r => {
            if (r.simulator && r.transpiled_qasm) {
                blob(`circuit_${_artSlug(r.simulator)}`, `Executed QASM: ${r.simulator}`, 'Circuits',
                    ['qasm', 'text'], () => _txtExecutedQasm(results, r.simulator),
                    `The exact transpiled OpenQASM executed by the ${r.simulator} adapter.`);
            }
        });
    }
    const terms = ['agreement class', 'not-comparable reason'];
    if (mode === 'measured') terms.push('statistical verdict');
    terms.push('unranked reason');
    blob('glossary', 'Taxonomy glossary', 'Reference', ['markdown', 'text'], () => _txtGlossary(mode),
        'Definitions of every ' + terms.join(', ') + ', plus the default thresholds.');
    return items;
}

// ---- backend subset ----
/** Backends in divergence-report order, then any others present in raw_results. */
export function _artBackends(results) {
    const order = (results.divergence_report || {}).simulators || [];
    const seen = new Set(order);
    const extra = (results.raw_results || []).map(r => r.simulator)
        .filter(s => s && !seen.has(s));
    return order.concat(extra);
}
/**
 * Copy of `results` restricted to the `selected` backends: square N×N matrices sliced,
 * pairwise records, raw results, ranking and unranked lists filtered, verdict counts
 * recomputed. Does not mutate `results`.
 */
export function _subsetResults(results, selected) {
    const div = results.divergence_report || {};
    const allSims = div.simulators || [];
    const keepIdx = [];
    allSims.forEach((s, i) => { if (selected.has(s)) keepIdx.push(i); });
    const newDiv = Object.assign({}, div);
    newDiv.simulators = keepIdx.map(i => allSims[i]);
    Object.keys(div).forEach(k => {
        const v = div[k];
        if (Array.isArray(v) && v.length === allSims.length
            && v.every(row => Array.isArray(row) && row.length === allSims.length)) {
            newDiv[k] = keepIdx.map(i => keepIdx.map(j => v[i][j]));
        }
    });
    if (Array.isArray(div.pairwise_agreement)) {
        newDiv.pairwise_agreement = div.pairwise_agreement.filter(r => {
            const s = r.simulators || [];
            return s.length === 2 && selected.has(s[0]) && selected.has(s[1]);
        });
    }
    const summary = div.statistical_test_summary;
    if (summary && summary.verdict_counts) {
        const vc = {};
        (newDiv.pairwise_agreement || []).forEach(r => {
            const v = ((r.metrics || {}).statistical_test || {}).verdict;
            if (v) vc[v] = (vc[v] || 0) + 1;
        });
        newDiv.statistical_test_summary = Object.assign({}, summary, { verdict_counts: vc });
    }
    const out = Object.assign({}, results, { divergence_report: newDiv });
    if (Array.isArray(results.raw_results)) {
        out.raw_results = results.raw_results.filter(r => selected.has(r.simulator));
    }
    ['performance_report', 'resource_report'].forEach(rep => {
        const report = results[rep];
        if (!report) return;
        const patch = {};
        ['ranking', 'unranked'].forEach(k => {
            if (Array.isArray(report[k])) patch[k] = report[k].filter(r => selected.has(r.simulator));
        });
        out[rep] = Object.assign({}, report, patch);
    });
    return out;
}
