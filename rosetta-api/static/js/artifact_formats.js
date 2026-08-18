// Publication-artifact data + text builders. Pure (no DOM, no network) so this file is the
// exact browser-side parity surface with services/publication.py, imported directly by
// tests/unit/artifacts_parity_harness.mjs. artifacts_renderer.js (DOM/viewers) imports from
// here rather than duplicating any of it.

// ---- number + escaping helpers (match publication.py _fmt_num / escapers) ------------
export function _artNum(v, d = 4) {
    if (v === null || v === undefined) return '—';
    if (typeof v === 'number') return Number.isNaN(v) ? '—' : v.toFixed(d);
    return String(v);
}
export const _ART_LATEX_ESC = {
    '\\': '\\textbackslash{}', '&': '\\&', '%': '\\%', '$': '\\$', '#': '\\#',
    '_': '\\_', '{': '\\{', '}': '\\}', '~': '\\textasciitilde{}', '^': '\\textasciicircum{}',
};
export function _artLatexEscape(s) {
    return String(s).split('').map(c => _ART_LATEX_ESC[c] || c).join('');
}
// Mirrors Python's html.escape (quote=True), including the &#x27; form for apostrophes.
// Kept separate from utils.js _escapeHtml, which emits &#39; — merging them would break
// byte-for-byte parity with services/publication.py.
export function _artHtmlEscape(s) {
    return String(s).replace(/[&<>"']/g, c =>
        ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#x27;' }[c]));
}
// Mirrors publication.basename_slug: each non-alphanumeric -> '-' (no run collapsing), trimmed.
export function _artSlug(s) {
    return String(s).toLowerCase().replace(/[^a-z0-9]/g, '-').replace(/^-+|-+$/g, '');
}

// ---- generic table renderers ---------------------------------------------------------
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
export function _artCsv({ headers, rows }) {
    const esc = v => {
        const s = (v === null || v === undefined) ? '' : String(v);
        return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    };
    return [headers, ...rows].map(r => r.map(esc).join(',')).join('\r\n') + '\r\n';
}
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
export function _artMarkdown({ headers, rows, title, caption }) {
    const esc = v => String(v).replace(/\|/g, '\\|');
    const lines = [`**${title}** — ${caption}`, '',
        '| ' + headers.map(esc).join(' | ') + ' |',
        '| ' + headers.map(() => '---').join(' | ') + ' |'];
    rows.forEach(r => lines.push('| ' + r.map(esc).join(' | ') + ' |'));
    lines.push('');
    return lines.join('\n');
}
export function _renderTable(fmt, data) {
    return { latex: _artLatex, csv: _artCsv, html: _artHtml, markdown: _artMarkdown }[fmt](data);
}

// ---- data builders (mirror publication.py) -------------------------------------------
export function _artPairKey(rec) {
    const s = rec.simulators || ['?', '?'];
    return `${s[0]} × ${s[1]}`;
}
export function _artPairwise(div) { return Array.isArray(div.pairwise_agreement) ? div.pairwise_agreement : []; }

export function _dataAgreement(div, mode) {
    const measured = mode === 'measured';
    const headers = ['Pair', 'Agreement', 'Registered transform', measured ? 'JS divergence' : 'Fidelity'];
    if (measured) headers.push('Stat verdict');
    const rows = _artPairwise(div).map(r => {
        const m = r.metrics || {};
        const metric = measured ? m.js_divergence : m.direct_fidelity;
        const row = [_artPairKey(r), r.agreement || '—', r.registered_transform || '—', _artNum(metric)];
        if (measured) row.push((m.statistical_test || {}).verdict || '—');
        return row;
    });
    return { headers, rows, title: 'Pairwise explained-cause agreement',
        caption: 'Classification over the registered-transform lattice; each label reports the transform whose numerical effect explains the pair.' };
}
export function _dataMatrix(div, key, title) {
    const labels = div.simulators || [];
    const mat = div[key];
    const headers = [''].concat(labels);
    const rows = labels.map((s1, i) => [s1].concat(labels.map((_, j) => {
        const v = mat[i][j];
        return (i === j || v === -1.0) ? '—' : _artNum(v);
    })));
    return { headers, rows, title, caption: `${title} (raw metric; −1 / diagonal shown as —). Symmetric matrix.` };
}
export function _dataPerformance(results) {
    const ranking = (results.performance_report || {}).ranking || [];
    return {
        headers: ['Rank', 'Simulator', 'Compilation (s)', 'Simulation (s)', 'Total (s)', 'CPU (s)',
            'Gate count', 'Depth', 'Status'],
        rows: ranking.map((r, i) => [i + 1, r.simulator || '—', _artNum(r.compilation_time_sec, 6),
            _artNum(r.simulation_time_sec, 6), _artNum(r.execution_time_sec, 6),
            _artNum(r.cpu_time_sec, 6), _artNum(r.gate_count, 0), _artNum(r.circuit_depth, 0),
            r.status || '—']),
        title: 'Execution timing',
        caption: 'Wall-clock and CPU timings measured by QRosetta (raw), after a uniform ' +
            'disclosed warm-up run precedes every timed measurement. Gate count/depth are ' +
            "derived from each backend's own transpiled QASM.",
    };
}
export function _dataResources(results) {
    const ranking = (results.resource_report || {}).ranking || [];
    return {
        headers: ['Rank', 'Simulator', 'Process peak RSS (MiB)', 'Mem delta (MiB)',
            'Process peak (MiB)', 'Theoretical SV (MiB)', 'Status'],
        rows: ranking.map((r, i) => [i + 1, r.simulator || '—', _artNum(r.process_peak_rss_mb, 1),
            _artNum(r.memory_usage_mb), _artNum(r.process_peak_mb, 1),
            _artNum(r.theoretical_statevector_mb), r.status || '—']),
        title: 'Resource usage',
        caption: 'Process peak RSS (raw, resource.getrusage) is the kernel-reported peak of the ' +
            'whole isolated run, including compilation and the warm-up; ranking is by this ' +
            "column. Mem delta / Process peak are each backend's own sim-window measurement.",
    };
}
export function _dataStatistical(div) {
    const recs = _artPairwise(div).filter(r => (r.metrics || {}).statistical_test);
    return {
        headers: ['Pair', 'Basis', 'chi2 p', 'chi2 p (BH)', 'G-test p', 'G-test p (BH)',
            'Total variation', "Cramér's V", 'Power@obs', 'Shots/backend for power', 'Verdict'],
        rows: recs.map(r => {
            const st = r.metrics.statistical_test, ef = st.effect_size || {}, pw = st.power || {},
                c = st.chi2 || {}, g = st.g_test || {};
            return [_artPairKey(r), st.basis || '—', _artNum(c.p_value), _artNum(c.p_value_bh),
                _artNum(g.p_value), _artNum(g.p_value_bh), _artNum(ef.total_variation), _artNum(ef.cramers_v),
                _artNum(pw.power_to_detect_delta_at_observed_shots, 3),
                pw.shots_per_backend_for_target_power ?? '—', st.verdict || '—'];
        }),
        title: 'Shot-noise statistical test',
        caption: 'Shot-noise-aware homogeneity tests (chi-square + G-test) with BH-corrected p-values, effect size, and prospective power, reported alongside the descriptive label.',
    };
}
export function _dataMetadata(results, mode) {
    const rows = (results.raw_results || []).map(r => {
        const sdk = Object.entries(r.sdk_versions || {}).map(([k, v]) => `${k}=${v}`).join(', ') || '—';
        return [r.simulator || '—', sdk, r.qubit_ordering || '—', r.sampling_method || '—',
            r.optimization_level ?? '—', r.error ? 'error' : 'completed'];
    });
    let run = `mode=${mode}`;
    if (results.n_shots !== undefined && results.n_shots !== null) run += `, n_shots=${results.n_shots}`;
    if (results.seed !== undefined && results.seed !== null) run += `, seed=${results.seed}`;
    return { headers: ['Simulator', 'SDK versions', 'Qubit ordering', 'Sampling method', 'Opt level', 'Status'],
        rows, title: 'Run and provenance metadata',
        caption: `Run + provenance metadata (${run}). Ground-truth executed versions and endpoint labels.` };
}
export function _txtExecutedQasm(results, runner) {
    const r = (results.raw_results || []).find(x => x.simulator === runner);
    const header = `// Executed (transpiled) OpenQASM for backend: ${runner}\n`
        + `// This is the exact circuit the ${runner} adapter ran (after preprocessing).\n`;
    return header + ((r && r.transpiled_qasm) || '// (no transpiled QASM recorded for this runner)');
}
export function _txtGlossary(mode) {
    const agr = [
        ['agree_directly', 'Outputs match directly, no transform needed.'],
        ['agree_up_to_global_phase', 'Match after removing an overall (unobservable) global phase.'],
        ['agree_after_bit_reversal', 'Match after reversing qubit/bit order (an endianness convention).'],
        ['agree_after_qubit_permutation', 'Match after a bounded qubit permutation (≤6 qubits).'],
        ['residual_disagreement', 'Statevector disagreement not explained by any registered transform.'],
        ['distance_within_threshold', 'Measured distributions within the JS/Hellinger thresholds (heuristic, configurable; the shot-noise statistical test is the rigorous verdict).'],
        ['distance_exceeds_threshold', 'Measured distributions exceed the (heuristic, configurable) thresholds after registered transforms; see the statistical test for significance.'],
        ['not_comparable', 'At least one side lacks usable output; the pair cannot be compared.'],
    ];
    const ver = [
        ['consistent', 'Shot-noise test finds no significant difference (after FDR correction).'],
        ['distinguishable', 'Both tests find a significant difference after FDR correction.'],
        ['inconclusive_low_shots', 'Expected counts too low for a reliable test.'],
        ['ambiguous', 'The chi-square and G-test disagree (rare).'],
    ];
    let out = ['# QRosetta agreement taxonomy — glossary', '', 'Agreement classes (registered-transform lattice):', ''];
    agr.forEach(([l, d]) => out.push(`- **${l}** — ${d}`));
    if (mode === 'measured') {
        out.push('', 'Shot-noise statistical verdicts (reported alongside the descriptive label):', '');
        ver.forEach(([l, d]) => out.push(`- **${l}** — ${d}`));
    }
    out.push('', 'Each label names the registered transform that explains the pair and reports its numerical effect; the per-pair records carry full provenance.');
    return out.join('\n');
}

// ---- catalog (mirrors publication.py _iter_artifacts availability) -------------------
export function _artifactMode(results) { return ('n_shots' in results) ? 'measured' : 'statevector'; }

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
            'Bar chart of how many backend pairs fall into each explained-cause class' + (mode === 'measured' ? ' and shot-noise verdict' : '') + '.');
        table('agreement', 'Pairwise agreement table', 'Agreement', () => _dataAgreement(div, mode),
            'One row per backend pair: explained-cause label, registered transform, key metric, and (measured) verdict. Analysis, not verification.');
    }
    const heat = mode === 'statevector'
        ? [['fidelity_matrix', 'Raw statevector fidelity (no transform)', 'fidelity']]
        : [['statistical_distance_matrix (js_divergence)', 'Raw Jensen–Shannon divergence', 'js_divergence'],
           ['hellinger_distance_matrix', 'Raw Hellinger distance', 'hellinger']];
    const multi = (div.simulators || []).length >= 2;  // heatmap/matrix needs a pair
    heat.forEach(([key, title, base]) => {
        if (multi && Array.isArray(div[key]) && div[key].length) {
            const short = title.split('(')[0].trim();
            image(`${base}_heatmap`, `${short} heatmap`, 'Divergence',
                `${title}: N×N heatmap; darker = larger value. −1/diagonal shown neutral.`);
            const mid = { fidelity: 'matrix_fidelity', js_divergence: 'matrix_js', hellinger: 'matrix_hellinger' }[base];
            table(mid, `${short} matrix (table)`, 'Divergence', () => _dataMatrix(div, key, title),
                `${title} as a copyable N×N matrix table (raw metric).`);
        }
    });
    if (((results.performance_report || {}).ranking || []).length) {
        image('performance_time', 'Execution-time chart', 'Performance', 'Stacked compilation + simulation time per backend (raw).');
        table('performance', 'Execution-time table', 'Performance', () => _dataPerformance(results), 'Per-backend compilation/simulation/total time and status (raw).');
    }
    if (((results.resource_report || {}).ranking || []).length) {
        image('resource_memory', 'Process-peak memory chart', 'Resources', 'Peak process memory per backend (raw).');
        table('resources', 'Resource-usage table', 'Resources', () => _dataResources(results), 'Per-backend memory delta, process peak, theoretical SV, status (raw).');
    }
    if (mode === 'measured') {
        if (pairwise.some(r => (r.metrics || {}).statistical_test)) {
            table('statistical_test', 'Statistical-test table', 'Statistical', () => _dataStatistical(div),
                'Chi-square + G-test p-values (raw + BH), effect size, power per pair.');
        }
        const rawCounts = {};
        (results.raw_results || []).forEach(r => {
            if (r.counts && Object.keys(r.counts).length) rawCounts[r.simulator] = r.counts;
        });
        // Total count figure: one compact outcome × backend heatmap over all backends with
        // counts (mirrors publication.py counts_overview availability: >= 2 such backends).
        if (Object.keys(rawCounts).length >= 2) {
            image('counts_overview', 'Count overview (all backends)', 'Statistical',
                'Clustered bar histogram of raw measured probabilities, one colour per backend over the top outcomes (Qiskit plot_histogram convention); low-probability outcomes are folded into "other" (disclosed in-figure).');
            image('counts_overview_heatmap', 'Count overview heatmap (optional)', 'Statistical',
                'Optional compact view: outcome × backend probability heatmap; a uniform row = agreement, a varying row = disagreement. Scales to many backends.');
        }
        let n = 0;
        pairwise.forEach(rec => {
            const [a, b] = rec.simulators || [];
            if (n < 12 && rawCounts[a] && rawCounts[b]) {
                n++;
                image(`histogram_${_artSlug(a + '_' + b)}`, `Count histogram: ${a} vs ${b}`, 'Statistical',
                    `Raw measured probability distributions for ${a} vs ${b}.`);
            }
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
    blob('glossary', 'Taxonomy glossary', 'Reference', ['markdown', 'text'], () => _txtGlossary(mode),
        'Definitions of every agreement class' + (mode === 'measured' ? ' and statistical verdict' : '') + '.');
    return items;
}

// ---- backend subset transform --------------------------------------------------------
// Filter a report down to a chosen set of backends so every figure/table in the tab can
// be scoped to "which vs which". Pure (no mutation): slices the N×N matrices, filters the
// pairwise records / raw results / rankings, and recomputes the shot-noise verdict counts.
// Figures then POST the sliced (stripped) report, so the server builders need no changes.
export function _artBackends(results) {
    const order = (results.divergence_report || {}).simulators || [];
    const seen = new Set(order);
    const extra = (results.raw_results || []).map(r => r.simulator)
        .filter(s => s && !seen.has(s));
    return order.concat(extra);
}
export function _subsetResults(results, selected) {
    const div = results.divergence_report || {};
    const allSims = div.simulators || [];
    const keepIdx = [];
    allSims.forEach((s, i) => { if (selected.has(s)) keepIdx.push(i); });
    const newDiv = Object.assign({}, div);
    newDiv.simulators = keepIdx.map(i => allSims[i]);
    // Slice any square N×N matrix indexed by `simulators` (fidelity/phase/js/hellinger),
    // detected structurally so we don't depend on the exact key names.
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
        if (results[rep] && Array.isArray(results[rep].ranking)) {
            out[rep] = Object.assign({}, results[rep], {
                ranking: results[rep].ranking.filter(r => selected.has(r.simulator)),
            });
        }
    });
    return out;
}
