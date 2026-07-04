// Artifacts tab — publication-ready figures + tables.
//
// Text artifacts (tables, matrices, executed QASM, glossary) are generated ENTIRELY in
// the browser (no upload) from the report the page already holds. Only matplotlib
// figures need the server: they are rendered on demand via POST /publication/render with
// the statevector-stripped report (tiny), and nothing is stored. The data builders below
// mirror services/publication.py so the tab and the RO-Crate export agree.

const ARTIFACT_SCALES = [1, 2, 3, 5];
const ARTIFACT_SCALE_LABELS = ['Screen (1×)', 'High (2×)', 'Print (3×)', 'Very High (5×)'];
const _TEXT_EXT = { latex: 'tex', csv: 'csv', html: 'html', markdown: 'md', qasm: 'qasm', text: 'txt' };
const _IMG_MIME = { svg: 'image/svg+xml', png: 'image/png', pdf: 'application/pdf' };

// ---- number + escaping helpers (match publication.py _fmt_num / escapers) ------------
function _artNum(v, d = 4) {
    if (v === null || v === undefined) return '—';
    if (typeof v === 'number') return Number.isNaN(v) ? '—' : v.toFixed(d);
    return String(v);
}
const _ART_LATEX_ESC = {
    '\\': '\\textbackslash{}', '&': '\\&', '%': '\\%', '$': '\\$', '#': '\\#',
    '_': '\\_', '{': '\\{', '}': '\\}', '~': '\\textasciitilde{}', '^': '\\textasciicircum{}',
};
function _artLatexEscape(s) {
    return String(s).split('').map(c => _ART_LATEX_ESC[c] || c).join('');
}
function _artHtmlEscape(s) {
    return String(s).replace(/[&<>"']/g, c =>
        ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function _artSlug(s) {
    return String(s).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
}

// ---- generic table renderers ---------------------------------------------------------
function _artLatex({ headers, rows, title, caption }) {
    const spec = 'l'.repeat(headers.length);
    const lines = ['% Requires \\usepackage{booktabs}', '\\begin{table}[htbp]', '  \\centering',
        `  \\caption{${_artLatexEscape(title)}. ${_artLatexEscape(caption)}}`,
        `  \\label{tab:${_artSlug(title)}}`, `  \\begin{tabular}{${spec}}`, '    \\toprule',
        '    ' + headers.map(_artLatexEscape).join(' & ') + ' \\\\', '    \\midrule'];
    rows.forEach(r => lines.push('    ' + r.map(_artLatexEscape).join(' & ') + ' \\\\'));
    lines.push('    \\bottomrule', '  \\end{tabular}', '\\end{table}', '');
    return lines.join('\n');
}
function _artCsv({ headers, rows }) {
    const esc = v => {
        const s = (v === null || v === undefined) ? '' : String(v);
        return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    };
    return [headers, ...rows].map(r => r.map(esc).join(',')).join('\r\n') + '\r\n';
}
function _artHtml({ headers, rows, title, caption }) {
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
function _artMarkdown({ headers, rows, title, caption }) {
    const esc = v => String(v).replace(/\|/g, '\\|');
    const lines = [`**${title}** — ${caption}`, '',
        '| ' + headers.map(esc).join(' | ') + ' |',
        '| ' + headers.map(() => '---').join(' | ') + ' |'];
    rows.forEach(r => lines.push('| ' + r.map(esc).join(' | ') + ' |'));
    lines.push('');
    return lines.join('\n');
}
function _renderTable(fmt, data) {
    return { latex: _artLatex, csv: _artCsv, html: _artHtml, markdown: _artMarkdown }[fmt](data);
}

// ---- data builders (mirror publication.py) -------------------------------------------
function _artPairKey(rec) {
    const s = rec.simulators || ['?', '?'];
    return `${s[0]} × ${s[1]}`;
}
function _artPairwise(div) { return Array.isArray(div.pairwise_agreement) ? div.pairwise_agreement : []; }

function _dataAgreement(div, mode) {
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
        caption: 'Analysis over the registered-transform lattice; each label reports the transform whose numerical effect explains the pair. Not a ground-truth verification.' };
}
function _dataMatrix(div, key, title) {
    const labels = div.simulators || [];
    const mat = div[key];
    const headers = [''].concat(labels);
    const rows = labels.map((s1, i) => [s1].concat(labels.map((_, j) => {
        const v = mat[i][j];
        return (i === j || v === -1.0) ? '—' : _artNum(v);
    })));
    return { headers, rows, title, caption: `${title} (raw metric; −1 / diagonal shown as —). Symmetric matrix.` };
}
function _dataPerformance(results) {
    const ranking = (results.performance_report || {}).ranking || [];
    return {
        headers: ['Rank', 'Simulator', 'Compilation (s)', 'Simulation (s)', 'Total (s)', 'Status'],
        rows: ranking.map((r, i) => [i + 1, r.simulator || '—', _artNum(r.compilation_time_sec, 6),
            _artNum(r.simulation_time_sec, 6), _artNum(r.execution_time_sec, 6), r.status || '—']),
        title: 'Execution timing', caption: 'Wall-clock timings measured by QRosetta (raw).',
    };
}
function _dataResources(results) {
    const ranking = (results.resource_report || {}).ranking || [];
    return {
        headers: ['Rank', 'Simulator', 'Mem delta (MiB)', 'Process peak (MiB)', 'Theoretical SV (MiB)', 'Status'],
        rows: ranking.map((r, i) => [i + 1, r.simulator || '—', _artNum(r.memory_usage_mb),
            _artNum(r.process_peak_mb, 1), _artNum(r.theoretical_statevector_mb), r.status || '—']),
        title: 'Resource usage', caption: 'Memory measured by QRosetta (raw).',
    };
}
function _dataStatistical(div) {
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
        caption: 'Chi-square + G-test p-values (raw + BH), effect size, and prospective power per pair. Parallel evidence; does not override the label.',
    };
}
function _dataMetadata(results, mode) {
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
function _txtExecutedQasm(results, runner) {
    const r = (results.raw_results || []).find(x => x.simulator === runner);
    const header = `// Executed (transpiled) OpenQASM for backend: ${runner}\n`
        + `// This is the exact circuit the ${runner} adapter ran (after preprocessing).\n`;
    return header + ((r && r.transpiled_qasm) || '// (no transpiled QASM recorded for this runner)');
}
function _txtGlossary(mode) {
    const agr = [
        ['agree_directly', 'Outputs match directly, no transform needed.'],
        ['agree_up_to_global_phase', 'Match after removing an overall (unobservable) global phase.'],
        ['agree_after_bit_reversal', 'Match after reversing qubit/bit order (an endianness convention).'],
        ['agree_after_qubit_permutation', 'Match after a bounded qubit permutation (≤6 qubits).'],
        ['residual_disagreement', 'Statevector disagreement not explained by any registered transform.'],
        ['distance_within_threshold', 'Measured distributions within the JS/Hellinger thresholds.'],
        ['distance_exceeds_threshold', 'Measured distributions exceed thresholds after registered transforms.'],
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
        out.push('', 'Shot-noise statistical verdicts (parallel evidence; do not override the label):', '');
        ver.forEach(([l, d]) => out.push(`- **${l}** — ${d}`));
    }
    out.push('', 'Every registered transform is reported with its numerical effect and provenance; QRosetta never silently alters runner outputs, and agreement analysis is not ground-truth verification.');
    return out.join('\n');
}

// ---- catalog (mirrors publication.py _iter_artifacts availability) -------------------
function _artifactMode(results) { return ('n_shots' in results) ? 'measured' : 'statevector'; }

function buildArtifactCatalog(results) {
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
        ? [['fidelity_matrix', 'Statevector fidelity', 'fidelity']]
        : [['statistical_distance_matrix (js_divergence)', 'Jensen–Shannon divergence', 'js_divergence'],
           ['hellinger_distance_matrix', 'Hellinger distance', 'hellinger']];
    heat.forEach(([key, title, base]) => {
        if (Array.isArray(div[key]) && div[key].length) {
            image(`${base}_heatmap`, `${title} heatmap`, 'Divergence',
                `${title}: N×N heatmap; darker = larger value. −1/diagonal shown neutral.`);
            const mid = { fidelity: 'matrix_fidelity', js_divergence: 'matrix_js', hellinger: 'matrix_hellinger' }[base];
            table(mid, `${title} matrix (table)`, 'Divergence', () => _dataMatrix(div, key, title),
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
        (results.raw_results || []).forEach(r => { if (r.counts) rawCounts[r.simulator] = r.counts; });
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

// ---- figure rendering (server) -------------------------------------------------------
async function _fetchFigureBlob(stripped, id, fmt, scale) {
    const resp = await fetch(`${BASE_URL}/publication/render`, {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ results: stripped, artifact_id: id, format: fmt, scale }),
    });
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }));
        throw new Error(err.detail || `HTTP ${resp.status}`);
    }
    return await resp.blob();
}

function _downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ---- viewers -------------------------------------------------------------------------
// Render format-toggle buttons into `host`, re-rendering in place on pick.
function _mountFmtSwitcher(host, formats, getCurrent, setCurrent) {
    host.innerHTML = '';
    host.className = 'flex flex-wrap gap-1';
    formats.forEach(f => {
        const b = document.createElement('button');
        b.textContent = f.toUpperCase();
        b.className = 'px-2 py-0.5 rounded text-xs border transition-all '
            + (f === getCurrent() ? 'bg-indigo-600 text-white border-indigo-600'
                                  : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-100');
        b.onclick = () => { setCurrent(f); _mountFmtSwitcher(host, formats, getCurrent, setCurrent); };
        host.appendChild(b);
    });
}

function _legendLine(text) {
    const p = document.createElement('p');
    p.className = 'text-xs text-gray-500 mt-2 leading-snug';
    p.innerHTML = `<span class="font-semibold text-gray-600">Legend:</span> ${_artHtmlEscape(text)}`;
    return p;
}

function _renderTextViewer(container, art) {
    container.innerHTML = '';
    const state = { fmt: art.formats[0] };
    const title = document.createElement('h3');
    title.className = 'text-base font-semibold text-gray-900 mb-2';
    title.textContent = art.label;
    container.appendChild(title);

    const bar = document.createElement('div');
    bar.className = 'flex items-center gap-2 mb-2 flex-wrap';
    const pre = document.createElement('pre');
    pre.className = 'text-xs bg-gray-50 border border-gray-200 rounded p-3 overflow-auto max-h-[52vh] whitespace-pre-wrap break-words';
    pre.setAttribute('readonly', 'true');

    const paint = () => { pre.textContent = art.getText(state.fmt); };
    const swHost = document.createElement('div');
    _mountFmtSwitcher(swHost, art.formats, () => state.fmt, f => { state.fmt = f; paint(); });
    bar.appendChild(swHost);

    const copyBtn = makeCopyIconButton(() => pre.textContent, 'Copy text');
    bar.appendChild(copyBtn);
    const dl = document.createElement('button');
    dl.className = 'inline-flex items-center gap-1 text-xs text-gray-600 hover:text-gray-900 bg-gray-100 hover:bg-gray-200 border border-gray-300 rounded-md px-2 py-1';
    dl.textContent = '⬇ Download';
    dl.onclick = () => _downloadBlob(new Blob([pre.textContent], { type: 'text/plain' }),
        `${art.id}.${_TEXT_EXT[state.fmt] || 'txt'}`);
    bar.appendChild(dl);

    container.appendChild(bar);
    container.appendChild(pre);
    container.appendChild(_legendLine(art.legend));
    paint();
}

function _renderImageViewer(container, art, stripped) {
    container.innerHTML = '';
    const state = { fmt: 'png', scaleIdx: 0 };
    const title = document.createElement('h3');
    title.className = 'text-base font-semibold text-gray-900 mb-2';
    title.textContent = art.label;
    container.appendChild(title);

    // Preview (SVG at screen scale — crisp and cheap).
    const preview = document.createElement('div');
    preview.className = 'bg-white border border-gray-200 rounded p-2 mb-3 overflow-auto max-h-[46vh] flex items-center justify-center';
    preview.textContent = 'Rendering preview…';
    container.appendChild(preview);
    _fetchFigureBlob(stripped, art.id, 'svg', 1).then(blob => {
        const img = document.createElement('img');
        img.src = URL.createObjectURL(blob);
        img.className = 'max-w-full h-auto';
        img.alt = art.label;
        preview.innerHTML = ''; preview.appendChild(img);
    }).catch(e => { preview.textContent = `Preview failed: ${e.message}`; });

    // Controls: format + resolution slider + download + copy image.
    const controls = document.createElement('div');
    controls.className = 'space-y-2';

    const fmtRow = document.createElement('div');
    fmtRow.className = 'flex items-center gap-2 flex-wrap';
    const fmtLabel = document.createElement('span');
    fmtLabel.className = 'text-xs text-gray-500'; fmtLabel.textContent = 'Format:';
    fmtRow.appendChild(fmtLabel);
    const swHost = document.createElement('div');
    _mountFmtSwitcher(swHost, art.formats, () => state.fmt, f => { state.fmt = f; });
    fmtRow.appendChild(swHost);
    controls.appendChild(fmtRow);

    const sliderRow = document.createElement('div');
    sliderRow.className = 'flex items-center gap-3';
    const sLabel = document.createElement('span');
    sLabel.className = 'text-xs text-gray-500 whitespace-nowrap'; sLabel.textContent = 'Resolution:';
    const slider = document.createElement('input');
    slider.type = 'range'; slider.min = '0'; slider.max = String(ARTIFACT_SCALES.length - 1);
    slider.step = '1'; slider.value = '0'; slider.className = 'flex-1 accent-indigo-600';
    const sVal = document.createElement('span');
    sVal.className = 'text-xs font-medium text-gray-700 whitespace-nowrap min-w-[130px] text-right';
    const updateSliderLabel = () => {
        const dpi = 150 * ARTIFACT_SCALES[state.scaleIdx];
        sVal.textContent = `${ARTIFACT_SCALE_LABELS[state.scaleIdx]} · ${dpi} dpi`;
    };
    slider.oninput = () => { state.scaleIdx = parseInt(slider.value, 10); updateSliderLabel(); };
    updateSliderLabel();
    sliderRow.append(sLabel, slider, sVal);
    controls.appendChild(sliderRow);
    const note = document.createElement('p');
    note.className = 'text-[11px] text-gray-400';
    note.textContent = 'Preview is at Screen resolution; the chosen resolution applies to Download / Copy (SVG & PDF are vector — resolution-independent).';
    controls.appendChild(note);

    const btnRow = document.createElement('div');
    btnRow.className = 'flex items-center gap-2 flex-wrap';
    const dl = document.createElement('button');
    dl.className = 'inline-flex items-center gap-1 text-xs text-white bg-indigo-600 hover:bg-indigo-700 rounded-md px-3 py-1.5';
    dl.textContent = '⬇ Download';
    dl.onclick = async () => {
        const scale = ARTIFACT_SCALES[state.scaleIdx];
        dl.disabled = true; const old = dl.textContent; dl.textContent = 'Rendering…';
        try {
            const blob = await _fetchFigureBlob(stripped, art.id, state.fmt, scale);
            _downloadBlob(blob, `${art.id}.${state.fmt}`);
        } catch (e) { alert(`Download failed: ${e.message}`); }
        finally { dl.disabled = false; dl.textContent = old; }
    };
    btnRow.appendChild(dl);
    const copyImg = document.createElement('button');
    copyImg.className = 'inline-flex items-center gap-1 text-gray-600 hover:text-gray-900 bg-gray-100 hover:bg-gray-200 border border-gray-300 rounded-md px-2 py-1.5';
    copyImg.innerHTML = COPY_ICON_SVG + '<span class="text-xs">PNG</span>';
    copyImg.title = 'Copy PNG to clipboard';
    copyImg.onclick = async () => {
        try {
            const blob = await _fetchFigureBlob(stripped, art.id, 'png', ARTIFACT_SCALES[state.scaleIdx]);
            await copyImageToClipboard(blob, copyImg);
        } catch (e) { alert(`Copy failed: ${e.message}`); }
    };
    btnRow.appendChild(copyImg);
    controls.appendChild(btnRow);

    container.appendChild(controls);
    container.appendChild(_legendLine(art.legend));
}

// ---- panel ---------------------------------------------------------------------------
function renderArtifactsPanel(results, panel) {
    if (!panel) return;
    panel.innerHTML = '';

    const h2 = document.createElement('h2');
    h2.className = 'text-lg font-semibold text-gray-900 mb-1';
    h2.textContent = 'Artifacts';
    panel.appendChild(h2);
    const sub = document.createElement('p');
    sub.className = 'text-xs text-gray-500 mb-4';
    sub.textContent = 'Publication-ready figures and tables. Tables generate instantly in your browser; figures render on demand. Nothing is uploaded except a small (statevector-free) copy of this report for figure rendering.';
    panel.appendChild(sub);

    const catalog = buildArtifactCatalog(results);
    if (!catalog.length) {
        const empty = document.createElement('p');
        empty.className = 'text-sm text-gray-500 italic';
        empty.textContent = 'No artifacts available for this report.';
        panel.appendChild(empty);
        return;
    }
    const stripped = (typeof _stripStatevectors === 'function') ? _stripStatevectors(results) : results;

    const layout = document.createElement('div');
    layout.className = 'flex flex-col md:flex-row gap-4';
    const left = document.createElement('div');
    left.className = 'md:w-64 flex-shrink-0 space-y-3 md:max-h-[70vh] md:overflow-y-auto';
    const right = document.createElement('div');
    right.className = 'flex-1 min-w-0 border border-gray-200 rounded-lg p-4 bg-white';
    right.innerHTML = '<p class="text-sm text-gray-400">Select an artifact on the left.</p>';
    layout.append(left, right);
    panel.appendChild(layout);

    // Group catalog.
    const groups = {};
    catalog.forEach(a => { (groups[a.group] = groups[a.group] || []).push(a); });
    let activeBtn = null;
    Object.entries(groups).forEach(([group, arts]) => {
        const gl = document.createElement('div');
        gl.className = 'text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-1';
        gl.textContent = group;
        left.appendChild(gl);
        arts.forEach(art => {
            const b = document.createElement('button');
            b.className = 'w-full text-left text-sm px-2 py-1.5 rounded hover:bg-gray-100 flex items-center gap-2';
            const dot = document.createElement('span');
            dot.className = 'text-[10px] px-1 rounded ' + (art.view === 'image'
                ? 'bg-indigo-100 text-indigo-700' : 'bg-gray-100 text-gray-600');
            dot.textContent = art.view === 'image' ? 'IMG' : 'TXT';
            const lbl = document.createElement('span');
            lbl.className = 'truncate'; lbl.textContent = art.label;
            b.append(dot, lbl);
            b.onclick = () => {
                if (activeBtn) activeBtn.classList.remove('bg-indigo-50', 'ring-1', 'ring-indigo-200');
                activeBtn = b; b.classList.add('bg-indigo-50', 'ring-1', 'ring-indigo-200');
                if (art.view === 'image') _renderImageViewer(right, art, stripped);
                else _renderTextViewer(right, art);
            };
            left.appendChild(b);
        });
    });
}
