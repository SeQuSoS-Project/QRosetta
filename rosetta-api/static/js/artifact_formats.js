// Publication-artifact number formatting, text builders and catalog. Mirrors
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
        const s = (v === null || v === undefined) ? '' : String(v);
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

// ---- glossaries (theme.py) ----
export const AGREEMENT_GLOSSARY = [
    ['agree_directly', 'Outputs match directly, no transform needed.'],
    ['agree_up_to_global_phase', 'Match after removing the global phase offset arg⟨a|b⟩ between the two states, which is unobservable. An offset within phase_tolerance is reported as 0 and the pair agrees directly.'],
    ['agree_after_bit_reversal', 'Match after reversing qubit/bit order (an endianness convention). A measured pair whose declared bit orders differ (lsb vs msb) is checked in the bit-reversed basis first.'],
    ['agree_after_qubit_permutation', 'Match after a bounded qubit permutation (≤7 qubits).'],
    ['agree_after_normalization', 'At least one input statevector has a norm differing from 1 by more than norm_tolerance; the normalised vectors agree. metrics.normalized_agreement holds the label the normalised pair receives. The default norm_tolerance (1e-4) lies above complex64 rounding, which leaves norms about 2e-6 from 1.'],
    ['residual_disagreement', 'Statevector disagreement not explained by any registered transform.'],
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
    ['consistent', 'Neither the chi-square test nor the G-test is significant after BH (FDR) correction, and the power to detect a total-variation gap of 0.05 at the observed shots is at least 0.8.'],
    ['distinguishable', 'Both tests are significant after BH (FDR) correction. At FDR q = 0.05 the expected share of false discoveries among flagged pairs is at most q, so a few flagged pairs are expected by chance.'],
    ['inconclusive_low_shots', 'Expected counts stay below 5 after pooling rare outcomes (inconclusive_reason = low_expected_counts), or neither test is significant and the power to detect a total-variation gap of 0.05 is below 0.8 (inconclusive_reason = low_power). power.recommended_exceeds_actual is true when the recommended shots per backend exceed the shots used.'],
    ['ambiguous', 'Exactly one of the chi-square test and the G-test is significant after BH (FDR) correction.'],
];
export const ASSESSMENT_GLOSSARY = [
    ['consistent_within_shot_noise', 'The shot-noise verdict is consistent: neither test separates the distributions at a shot count with power of at least 0.8, whatever the distance label.'],
    ['distinguishable', 'The shot-noise verdict is distinguishable: the distributions differ beyond sampling noise, subject to the FDR share of false discoveries.'],
    ['ambiguous', 'Exactly one of the two tests is significant.'],
    ['inconclusive_low_shots', 'The shot count cannot separate the distributions: expected counts stay below 5 after pooling, or the test is not significant at power below 0.8.'],
    ['not_comparable', 'At least one side lacks usable counts.'],
];
export const UNRANKED_GLOSSARY = [
    ['runner_error', 'The run failed; Status gives the dispatch status (error, timeout or offline) and its metrics are shown as —.'],
    ['missing_timing', 'The run returned no execution_time_sec.'],
    ['missing_process_peak_rss', 'The run returned no process_peak_rss_mb.'],
];
export const MEASUREMENT_NOTES = [
    'Global phase offset arg⟨a|b⟩: the phase of the inner product of two normalised statevectors. It is a global-phase difference between the states, not a relative phase between components of one superposition. The JSON fields relative_phase_matrix and *relative_phase* keep their names for compatibility.',
    "Label-aligned basis: for a measured pair whose declared counts bit orders differ (lsb vs msb) the second backend's keys are bit-reversed; otherwise the keys are compared directly. The statistical tests and the label-aligned distances use this basis; the direct distances are recorded as well.",
    'Outcomes with an expected count below 5 are pooled into one bin before the chi-square and G-tests; statistical_test.pooled_outcomes gives how many were pooled.',
];
export const THRESHOLD_DEFAULTS = 'fidelity_tolerance = 1e-5, phase_tolerance = 1e-6 rad, '
    + 'norm_tolerance = 1e-4, js_threshold = 0.01 nats, hellinger_threshold = 0.1';

// ---- table builders (tables.py) ----
/** One row per backend pair: label, transform, key metric(s), verdict and assessment (measured), reason. */
export function _dataAgreement(div, mode) {
    const measured = mode === 'measured';
    const headers = ['Pair', 'Agreement', 'Registered transform'];
    if (measured) headers.push(`JS, direct (${JS_UNIT})`, `JS, label-aligned basis (${JS_UNIT})`, 'Stat verdict', 'Measured assessment');
    else headers.push('Direct fidelity');
    headers.push('Not-comparable reason');
    const rows = _artPairwise(div).map(r => {
        const m = r.metrics || {};
        const metric = r.mode === 'statevector' ? m.direct_fidelity : m.js_divergence;
        const row = [_artPairKey(r), _artText(r.agreement), _artText(r.registered_transform), _artNum(metric)];
        if (measured) row.push(_artNum(m.label_aligned_js_divergence), _artText((m.statistical_test || {}).verdict), _artText(r.measured_assessment));
        row.push(r.agreement === 'not_comparable' ? _artText(m.reason) : '—');
        return row;
    });
    const metricNote = measured
        ? `JS, direct is the Jensen–Shannon divergence in ${JS_UNIT} of the keys as reported; JS, label-aligned basis bit-reverses the second backend's keys when the two declared bit orders differ (lsb vs msb) and equals the direct value otherwise`
        : 'Direct fidelity is |<a|b>|^2 of the normalised vectors before any transform';
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
    const rows = labels.map((s1, i) => [s1].concat(labels.map((_, j) => {
        const v = mat[i][j];
        return (i === j || v === null || v === undefined || v === -1.0) ? '—' : _artNum(v);
    })));
    return { headers, rows, title, caption: `${title} (raw metric; not-compared pairs and the diagonal shown as —). Symmetric matrix.` };
}
/** Per-backend timings: ranked runs by total time, then unranked runs with the reason. */
export function _dataPerformance(results) {
    return {
        headers: ['Rank', 'Simulator', 'Compilation (s)', 'Simulation (s)', 'Total (s)',
            'Simulation CPU (s)', 'Process CPU (s)', 'Gate count', 'Depth', 'Status'],
        rows: _artReportRows(results, 'performance_report').map(row => [row.rank,
            _artText(row.entry.simulator),
            _artNum(_artField(row, 'compilation_time_sec'), 6),
            _artNum(_artField(row, 'simulation_time_sec'), 6),
            _artNum(_artField(row, 'execution_time_sec'), 6),
            _artNum(_artField(row, 'simulation_cpu_time_sec'), 6),
            _artNum(_artField(row, 'cpu_time_sec'), 6),
            _artInt(_artField(row, 'gate_count')), _artInt(_artField(row, 'circuit_depth')),
            row.status]),
        title: 'Execution timing',
        caption: `Wall-clock times of the timed run, n=${_artTimingSamples(results)} timing sample(s) `
            + 'per backend; a warm-up run precedes it and is not included. Total = compilation '
            + '+ simulation. Simulation CPU is process CPU time over the simulation window. '
            + 'Process CPU is getrusage CPU time of the whole isolated runner process, '
            + 'including interpreter start, imports and the warm-up. Ranked by total time, '
            + 'fastest first; runs without a rank follow with the reason in Status. Gate '
            + "count and depth are taken from each backend's transpiled QASM.",
    };
}
/** Per-backend memory: ranked runs by process peak RSS, then unranked runs with the reason. */
export function _dataResources(results) {
    return {
        headers: ['Rank', 'Simulator', 'Process peak RSS (MiB)', 'Sim-window peak RSS (MiB)',
            'Sim-window RSS delta (MiB)', 'Theoretical SV (MiB)', 'Precision', 'Status'],
        rows: _artReportRows(results, 'resource_report').map(row => [row.rank,
            _artText(row.entry.simulator),
            _artNum(_artField(row, 'process_peak_rss_mb'), 1),
            _artNum(_artField(row, 'process_peak_mb'), 1),
            _artNum(_artField(row, 'memory_usage_mb')),
            _artNum(_artField(row, 'theoretical_statevector_mb')),
            _artText(_artField(row, 'precision')), row.status]),
        title: 'Resource usage',
        caption: 'Process peak RSS is the peak resident memory of the simulating process over its '
            + 'whole life (interpreter start, imports, warm-up and timed run); method: '
            + `${_artDistinct(results, 'process_peak_rss_method')}. Rows are ranked by it, lowest `
            + 'first; runs without a rank follow with the reason in Status. Sim-window peak RSS '
            + 'and RSS delta (peak minus RSS at monitor entry) cover the pre-execute step and '
            + `simulation window of the timed run; method: ${_artDistinct(results, 'memory_method')}. `
            + 'Theoretical SV is 2^n × 16 bytes for the declared qubit count. 1 MiB = 1024^2 bytes. '
            + 'For small circuits process peak RSS is dominated by the SDK import footprint; '
            + "the sim-window RSS delta is the simulation's own allocation.",
    };
}
/** The verdict, followed by the inconclusive reason in parentheses when one is set. */
function _artVerdictText(st) {
    const verdict = _artText(st.verdict);
    return st.inconclusive_reason ? `${verdict} (${st.inconclusive_reason})` : verdict;
}
/** Per-pair chi-square and G-test p-values, effect sizes, power and verdict. */
export function _dataStatistical(div) {
    const recs = _artPairwise(div).filter(r => (r.metrics || {}).statistical_test);
    return {
        headers: ['Pair', 'Basis', 'chi2 p', 'chi2 p (BH)', 'G-test p', 'G-test p (BH)',
            'Total variation', "Cramér's V", 'Power@obs', 'Shots/backend for power',
            'Pooled outcomes', 'Verdict'],
        rows: recs.map(r => {
            const st = r.metrics.statistical_test, ef = st.effect_size || {}, pw = st.power || {},
                c = st.chi2 || {}, g = st.g_test || {};
            return [_artPairKey(r), _artText(st.basis), _artP(c.p_value), _artP(c.p_value_bh),
                _artP(g.p_value), _artP(g.p_value_bh), _artNum(ef.total_variation), _artNum(ef.cramers_v),
                _artNum(pw.power_to_detect_delta_at_observed_shots, 3),
                _artInt(pw.shots_per_backend_for_target_power), _artInt(st.pooled_outcomes),
                _artVerdictText(st)];
        }),
        title: 'Shot-noise statistical test',
        caption: 'Shot-noise-aware homogeneity tests (chi-square + G-test) in the label-aligned '
            + 'basis (bit-reversed when the declared bit orders differ), with BH-corrected '
            + 'p-values, effect size and prospective power for a total-variation gap of 0.05. '
            + 'Outcomes with an expected count below 5 are pooled into one bin. At FDR q = 0.05 '
            + 'the expected share of false discoveries among flagged pairs is at most q, so a '
            + 'few flagged pairs are expected by chance. A non-significant pair with power '
            + 'below 0.8 is inconclusive_low_shots.',
    };
}
/** Per-backend SDK versions, ordering and sampling labels, opt level and status. */
export function _dataMetadata(results, mode) {
    const rows = (results.raw_results || []).map(r => {
        const sdk = Object.entries(r.sdk_versions || {}).map(([k, v]) => `${k}=${_artText(v)}`).join(', ') || '—';
        const status = r.dispatch_status || r.status || ((r.error !== null && r.error !== undefined) ? 'error' : 'ok');
        return [_artText(r.simulator), sdk, _artText(r.qubit_ordering), _artText(r.sampling_method),
            _artInt(r.optimization_level), _artText(status)];
    });
    let run = `mode=${mode}`;
    if (results.n_shots !== undefined && results.n_shots !== null) run += `, n_shots=${_artInt(results.n_shots)}`;
    if (results.seed !== undefined && results.seed !== null) run += `, seed=${_artInt(results.seed)}`;
    return { headers: ['Simulator', 'SDK versions', 'Qubit ordering', 'Sampling method', 'Opt level', 'Status'],
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
    out.push('', `Default thresholds: ${THRESHOLD_DEFAULTS}. A run may override them; the values applied are recorded in each pairwise record. JS divergence is in ${JS_UNIT} (maximum ln 2).`,
        '', 'Each label names the registered transform that explains the pair and reports its numerical effect; the per-pair records carry full provenance.');
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
    if ((perf.ranking || []).length || (perf.unranked || []).length) {
        image('performance_time', 'Execution-time chart', 'Performance',
            'Stacked compilation + simulation wall-clock time per backend (raw), '
            + `n=${_artTimingSamples(results)} timing sample(s) per backend; ` + unrankedNote);
        table('performance', 'Execution-time table', 'Performance', () => _dataPerformance(results),
            'Per-backend compilation, simulation and total wall-clock time, simulation and process CPU time, and status (raw).');
    }
    const res = results.resource_report || {};
    if ((res.ranking || []).length || (res.unranked || []).length) {
        image('resource_memory', 'Process peak RSS chart', 'Resources',
            "Peak RSS of each backend's simulating process over its whole life (interpreter start, imports, warm-up and timed run), in MiB; method: "
            + `${_artDistinct(results, 'process_peak_rss_method')}. Ranked lowest first; ` + unrankedNote);
        table('resources', 'Resource-usage table', 'Resources', () => _dataResources(results),
            'Per-backend process peak RSS, sim-window peak RSS and RSS delta, theoretical statevector size, precision and status (raw).');
    }
    if (mode === 'measured') {
        if (pairwise.some(r => (r.metrics || {}).statistical_test)) {
            table('statistical_test', 'Statistical-test table', 'Statistical', () => _dataStatistical(div),
                'Chi-square + G-test p-values (raw + BH) in the label-aligned basis, effect size, power and pooled outcomes per pair.');
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
            'Backends, SDK versions, qubit-ordering & sampling labels, opt level, run params.');
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
