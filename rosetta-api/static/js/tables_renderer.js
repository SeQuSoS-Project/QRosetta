// Frontend logic for tables_renderer functionality.

function _makeStatusCell(styleKey, text) {
    const span = document.createElement('span');
    STATUS_STYLES[styleKey].cell.split(' ').forEach(c => span.classList.add(c));
    span.textContent = text;
    return span;
}

function _displayRunnerName(key) {
    const nameMap = typeof RUNNER_DISPLAY_NAMES !== 'undefined' ? RUNNER_DISPLAY_NAMES : null;
    return typeof formatRunnerLabel === 'function' ? formatRunnerLabel(key, nameMap) : key;
}

function _fillSimulatorCell(td, simulatorName, config) {
    td.classList.remove('tpl-simulator');
    td.appendChild(document.createTextNode(_displayRunnerName(simulatorName)));

    const suiteData = getState()?.currentSuiteData;
    let rawItem = null;
    if (suiteData && suiteData.raw_results) {
        rawItem = suiteData.raw_results.find(r => r.simulator === simulatorName);
    }

    if (rawItem && rawItem.qubit_ordering) {
        const span = document.createElement('span');
        span.className = 'ml-2 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-100 text-gray-600 border border-gray-200';
        span.textContent = rawItem.qubit_ordering.toUpperCase();
        span.title = 'Qubit Ordering';
        td.appendChild(span);
    }

    if (rawItem && rawItem.sampling_method) {
        const smMap = {
            'native': { label: 'Native', color: 'bg-green-100 text-green-700 border-green-200', title: 'Native: Simulation backend sampled shots directly.' },
            'sv_sample': { label: 'SV-Sample', color: 'bg-blue-100 text-blue-700 border-blue-200', title: 'SV-Sample: Counts derived from statevector via multinomial sampling.' },
            'tn_sample': { label: 'TN-Sample', color: 'bg-orange-100 text-orange-700 border-orange-200', title: 'TN-Sample: Counts sampled from tensor-network amplitudes.' },
            'probability_rounding': { label: 'Prob-Round', color: 'bg-purple-100 text-purple-700 border-purple-200', title: 'Prob-Round: Probabilities rounded to nearest shot integers.' }
        };
        const cfg = smMap[rawItem.sampling_method];
        if (cfg) {
            const span = document.createElement('span');
            span.className = `ml-1 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border ${cfg.color}`;
            span.textContent = cfg.label;
            span.title = `Sampling Method: ${cfg.title}`;
            td.appendChild(span);
        }
    }

    const badge = getOptBadge(simulatorName, config);
    if (badge) td.appendChild(badge);
}

function renderRankingTable(report, key, unit, panel, config = {}) {
    if (!panel) return;
    panel.innerHTML = '';

    const hFrag = _cloneTemplate('tpl-ranking-section-header');
    hFrag.querySelector('.tpl-summary-text').textContent = report.summary;
    panel.appendChild(hFrag);

    const legendFrag = _cloneTemplate('tpl-legend-ranking');
    _applyLegendDots(legendFrag);
    panel.appendChild(legendFrag);

    const offlineSims = new Set();
    if (getState().currentSuiteData && getState().currentSuiteData.raw_results) {
        getState().currentSuiteData.raw_results.forEach(r => {
            if (r.error && isConnectionError(r.error)) offlineSims.add(r.simulator);
        });
    }

    if (key === 'memory_usage_mb') {

        report.ranking.sort((a, b) => {
            if (a.status !== 'success') return 1;
            if (b.status !== 'success') return -1;
            return (a.process_peak_rss_mb || 0) - (b.process_peak_rss_mb || 0);
        });

        const tblFrag = _cloneTemplate('tpl-ranking-header-memory');

        const thProcPeakRss = tblFrag.querySelector('.tpl-th-proc-peak-rss');
        thProcPeakRss.classList.remove('tpl-th-proc-peak-rss');
        thProcPeakRss.innerHTML = '';
        thProcPeakRss.appendChild(renderTooltip('proc_peak_rss', 'Process Peak RSS (MiB)'));

        const thMemDelta = tblFrag.querySelector('.tpl-th-mem-delta');
        thMemDelta.classList.remove('tpl-th-mem-delta');
        thMemDelta.innerHTML = '';
        thMemDelta.appendChild(renderTooltip('mem_delta', 'Mem Delta (MiB)'));

        const thProcPeak = tblFrag.querySelector('.tpl-th-proc-peak');
        thProcPeak.classList.remove('tpl-th-proc-peak');
        thProcPeak.innerHTML = '';
        thProcPeak.appendChild(renderTooltip('proc_peak', 'Process Peak (MiB)'));

        const thTheoretical = tblFrag.querySelector('.tpl-th-theoretical');
        if (thTheoretical) {
            thTheoretical.classList.remove('tpl-th-theoretical');
            thTheoretical.innerHTML = '';
            thTheoretical.appendChild(renderTooltip('theoretical_sv', 'Theoretical SV (MiB)'));
        }

        const tbody = tblFrag.querySelector('.tpl-tbody');
        tbody.classList.remove('tpl-tbody');

        report.ranking.forEach((r, i) => {
            const rowFrag = _cloneTemplate('tpl-ranking-row-memory');

            rowFrag.querySelector('.tpl-rank').textContent = i + 1;
            _fillSimulatorCell(rowFrag.querySelector('.tpl-simulator'), r.simulator, config);

            const procPeakRssTd = rowFrag.querySelector('.tpl-proc-peak-rss');
            procPeakRssTd.classList.remove('tpl-proc-peak-rss');
            const memDeltaTd = rowFrag.querySelector('.tpl-mem-delta');
            memDeltaTd.classList.remove('tpl-mem-delta');
            const procPeakTd = rowFrag.querySelector('.tpl-proc-peak');
            procPeakTd.classList.remove('tpl-proc-peak');
            const theoreticalTd = rowFrag.querySelector('.tpl-theoretical');
            if (theoreticalTd) theoreticalTd.classList.remove('tpl-theoretical');

            if (r.status === 'success') {
                procPeakRssTd.textContent = r.process_peak_rss_mb != null ? r.process_peak_rss_mb.toFixed(1) : '';
                memDeltaTd.textContent = r.memory_usage_mb != null ? r.memory_usage_mb.toFixed(4) : '';
                procPeakTd.textContent = r.process_peak_mb != null ? r.process_peak_mb.toFixed(1) : '';
                if (theoreticalTd) {
                    theoreticalTd.textContent = r.theoretical_statevector_mb != null ? r.theoretical_statevector_mb.toFixed(4) : (r.theoretical_statevector_mb === null ? 'N/A' : '');
                }
            } else if (offlineSims.has(r.simulator)) {
                procPeakRssTd.appendChild(_makeStatusCell('offline', 'Offline'));
                memDeltaTd.appendChild(_makeStatusCell('offline', 'Offline'));
                procPeakTd.appendChild(_makeStatusCell('offline', 'Offline'));
                if (theoreticalTd) theoreticalTd.appendChild(_makeStatusCell('offline', 'Offline'));
            } else {
                procPeakRssTd.appendChild(_makeStatusCell('anomaly', 'Anomaly'));
                memDeltaTd.appendChild(_makeStatusCell('anomaly', 'Anomaly'));
                procPeakTd.appendChild(_makeStatusCell('anomaly', 'Anomaly'));
                if (theoreticalTd) theoreticalTd.appendChild(_makeStatusCell('anomaly', 'Anomaly'));
            }

            tbody.appendChild(rowFrag);
        });

        panel.appendChild(tblFrag);

    } else if (key === 'execution_time_sec') {

        const tblFrag = _cloneTemplate('tpl-ranking-header-time');

        const thComp = tblFrag.querySelector('.tpl-th-compilation');
        thComp.classList.remove('tpl-th-compilation');
        thComp.innerHTML = '';
        thComp.appendChild(renderTooltip('compilation', 'Compilation (s)'));

        const thSim = tblFrag.querySelector('.tpl-th-simulation');
        thSim.classList.remove('tpl-th-simulation');
        thSim.innerHTML = '';
        thSim.appendChild(renderTooltip('simulation', 'Simulation (s)'));

        const thTotal = tblFrag.querySelector('.tpl-th-total');
        thTotal.classList.remove('tpl-th-total');
        thTotal.innerHTML = '';
        thTotal.appendChild(renderTooltip('total_time', 'Total (s)'));

        const thCpu = tblFrag.querySelector('.tpl-th-cpu');
        thCpu.classList.remove('tpl-th-cpu');
        thCpu.innerHTML = '';
        thCpu.appendChild(renderTooltip('cpu_time', 'CPU (s)'));

        const thGateCount = tblFrag.querySelector('.tpl-th-gate-count');
        thGateCount.classList.remove('tpl-th-gate-count');
        thGateCount.innerHTML = '';
        thGateCount.appendChild(renderTooltip('gate_count', 'Gate Count'));

        const thDepth = tblFrag.querySelector('.tpl-th-depth');
        thDepth.classList.remove('tpl-th-depth');
        thDepth.innerHTML = '';
        thDepth.appendChild(renderTooltip('circuit_depth', 'Depth'));

        const tbody = tblFrag.querySelector('.tpl-tbody');
        tbody.classList.remove('tpl-tbody');

        report.ranking.forEach((r, i) => {
            const rowFrag = _cloneTemplate('tpl-ranking-row-time');

            rowFrag.querySelector('.tpl-rank').textContent = i + 1;
            _fillSimulatorCell(rowFrag.querySelector('.tpl-simulator'), r.simulator, config);

            const compTd = rowFrag.querySelector('.tpl-comp');
            compTd.classList.remove('tpl-comp');
            const simTd = rowFrag.querySelector('.tpl-sim');
            simTd.classList.remove('tpl-sim');
            const totalTd = rowFrag.querySelector('.tpl-total');
            totalTd.classList.remove('tpl-total');
            const cpuTd = rowFrag.querySelector('.tpl-cpu');
            cpuTd.classList.remove('tpl-cpu');
            const gateCountTd = rowFrag.querySelector('.tpl-gate-count');
            gateCountTd.classList.remove('tpl-gate-count');
            const depthTd = rowFrag.querySelector('.tpl-depth');
            depthTd.classList.remove('tpl-depth');

            if (r.status === 'success') {
                compTd.textContent = r.compilation_time_sec != null ? r.compilation_time_sec.toFixed(6) : '-';
                simTd.textContent  = r.simulation_time_sec  != null ? r.simulation_time_sec.toFixed(6)  : '-';
                totalTd.textContent = r.execution_time_sec  != null ? r.execution_time_sec.toFixed(6)   : '-';
                cpuTd.textContent = r.cpu_time_sec != null ? r.cpu_time_sec.toFixed(6) : '-';
                gateCountTd.textContent = r.gate_count != null ? r.gate_count : '-';
                depthTd.textContent = r.circuit_depth != null ? r.circuit_depth : '-';
            } else if (offlineSims.has(r.simulator)) {
                compTd.appendChild(_makeStatusCell('offline', 'Offline'));
                simTd.appendChild(_makeStatusCell('offline', 'Offline'));
                totalTd.appendChild(_makeStatusCell('offline', 'Offline'));
                cpuTd.appendChild(_makeStatusCell('offline', 'Offline'));
                gateCountTd.appendChild(_makeStatusCell('offline', 'Offline'));
                depthTd.appendChild(_makeStatusCell('offline', 'Offline'));
            } else {
                compTd.appendChild(document.createTextNode('-'));
                simTd.appendChild(document.createTextNode('-'));
                totalTd.appendChild(_makeStatusCell('anomaly', 'Anomaly'));
                cpuTd.appendChild(document.createTextNode('-'));
                gateCountTd.appendChild(document.createTextNode('-'));
                depthTd.appendChild(document.createTextNode('-'));
            }

            tbody.appendChild(rowFrag);
        });

        panel.appendChild(tblFrag);

    } else {

        const tblFrag = _cloneTemplate('tpl-ranking-header-generic');

        const thVal = tblFrag.querySelector('.tpl-th-value');
        thVal.classList.remove('tpl-th-value');
        thVal.innerHTML = '';
        thVal.appendChild(renderTooltip(key, 'Value'));

        const tbody = tblFrag.querySelector('.tpl-tbody');
        tbody.classList.remove('tpl-tbody');

        report.ranking.forEach((r, i) => {
            const rowFrag = _cloneTemplate('tpl-ranking-row-generic');

            rowFrag.querySelector('.tpl-rank').textContent = i + 1;
            _fillSimulatorCell(rowFrag.querySelector('.tpl-simulator'), r.simulator, config);

            const valTd = rowFrag.querySelector('.tpl-value');
            valTd.classList.remove('tpl-value');

            if (r.status === 'success' && r[key] !== null) {
                valTd.textContent = `${r[key].toFixed(6)} ${unit}`;
            } else if (offlineSims.has(r.simulator)) {
                valTd.appendChild(_makeStatusCell('offline', 'Offline'));
            } else {
                valTd.appendChild(_makeStatusCell('anomaly', 'Anomaly'));
            }

            tbody.appendChild(rowFrag);
        });

        panel.appendChild(tblFrag);
    }
}

function renderDivergenceTables(report, panel, config = {}) {
    if (!panel) return;
    panel.innerHTML = '';

    const outerDiv = document.createElement('div');
    outerDiv.className = 'space-y-8';

    const legendFrag = _cloneTemplate('tpl-legend-divergence');
    _applyLegendDots(legendFrag);
    outerDiv.appendChild(legendFrag);

    const offlineSims = new Set();
    if (getState().currentSuiteData && getState().currentSuiteData.raw_results) {
        getState().currentSuiteData.raw_results.forEach(r => {
            if (r.error && isConnectionError(r.error)) offlineSims.add(r.simulator);
        });
    }

    let found = false;

    const renderMat = (key, title) => {
        if (!report[key]) return;
        found = true;

        const secFrag = _cloneTemplate('tpl-div-matrix-section');

        const h3 = secFrag.querySelector('.tpl-title');
        h3.classList.remove('tpl-title');
        h3.appendChild(renderTooltip(key, title));

        const theadRow = secFrag.querySelector('thead tr');
        report.simulators.forEach(s => {
            const thFrag = _cloneTemplate('tpl-div-matrix-header-cell');
            const th = thFrag.querySelector('th');
            th.appendChild(document.createTextNode(_displayRunnerName(s)));
            const badge = getOptBadge(s, config);
            if (badge) th.appendChild(badge);
            theadRow.appendChild(thFrag);
        });

        const tbody = secFrag.querySelector('.tpl-tbody');
        tbody.classList.remove('tpl-tbody');

        report.simulators.forEach((s1, i) => {
            const tr = document.createElement('tr');

            const rhFrag = _cloneTemplate('tpl-div-matrix-row-header');
            const rowTh = rhFrag.querySelector('th');
            rowTh.appendChild(document.createTextNode(_displayRunnerName(s1)));
            const rBadge = getOptBadge(s1, config);
            if (rBadge) rowTh.appendChild(rBadge);
            tr.appendChild(rhFrag);

            report[key][i].forEach((val, j) => {
                const cellFrag = _cloneTemplate('tpl-div-matrix-cell');
                const td = cellFrag.querySelector('td');

                let cellText = val.toFixed(4);
                let bgClasses = STATUS_STYLES.divergence.cell;

                if (i === j) {
                    bgClasses = STATUS_STYLES.neutral.cell;
                    cellText = '-';
                } else if (offlineSims.has(s1) || offlineSims.has(report.simulators[j])) {
                    cellText = 'OFF';
                    bgClasses = STATUS_STYLES.offline.cell;
                } else {
                    const epsilon = 1e-9;
                    let isPerfectMatch = false;
                    if (key.includes('fidelity') && Math.abs(val - 1.0) < epsilon) isPerfectMatch = true;
                    if (key.includes('phase') && (Math.abs(val - 1.0) < epsilon || Math.abs(val) < epsilon)) isPerfectMatch = true;
                    if ((key.includes('js_divergence') || key.includes('hellinger')) && Math.abs(val) < epsilon) isPerfectMatch = true;

                    if (isPerfectMatch) {
                        bgClasses = STATUS_STYLES.success.cell;
                        if (key.includes('js_divergence') || key.includes('hellinger') || (key.includes('phase') && Math.abs(val) < epsilon)) {
                            cellText = '0.000';
                        } else {
                            cellText = '1.000';
                        }
                    } else if (val === -1.0) {
                        cellText = 'ERR';
                        bgClasses = STATUS_STYLES.anomaly.cell;
                    }
                }

                bgClasses.split(' ').forEach(c => td.classList.add(c));
                td.textContent = cellText;
                tr.appendChild(cellFrag);
            });

            tbody.appendChild(tr);
        });

        outerDiv.appendChild(secFrag);
    };

    renderMat('fidelity_matrix', 'Fidelity Matrix');
    renderMat('relative_phase_matrix', 'Relative Phase Matrix');
    renderMat('statistical_distance_matrix (js_divergence)', 'JS Divergence Matrix');
    renderMat('hellinger_distance_matrix', 'Hellinger Distance Matrix (Geometric)');

    // The explained-cause agreement taxonomy + shot-noise statistical test now live in
    // their own "Agreement" tab (renderAgreementPanel); the Divergence tab is the raw
    // numeric matrices only.

    if (!found) {
        const p = document.createElement('p');
        p.className = 'text-gray-500 mt-4';
        p.textContent = 'No matrices available.';
        outerDiv.appendChild(p);
    }

    panel.appendChild(outerDiv);
}

// ---- Explained-cause agreement taxonomy + shot-noise statistical test ----

const AGREEMENT_STYLE = {
    agree_directly: 'success',
    agree_up_to_global_phase: 'success',
    distance_within_threshold: 'success',
    agree_after_bit_reversal: 'divergence',
    agree_after_qubit_permutation: 'divergence',
    residual_disagreement: 'anomaly',
    distance_exceeds_threshold: 'anomaly',
    not_comparable: 'offline',
};

const VERDICT_STYLE = {
    consistent: 'success',
    distinguishable: 'anomaly',
    inconclusive_low_shots: 'offline',
    ambiguous: 'divergence',
};

function _chip(badgeClasses, text, title) {
    const span = document.createElement('span');
    span.className = 'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border';
    badgeClasses.split(' ').forEach(c => span.classList.add(c));
    span.textContent = text;
    if (title) span.title = title;
    return span;
}

function _fmtNum(v, digits = 4) {
    if (v === null || v === undefined) return '—';
    if (typeof v === 'number') return Number.isNaN(v) ? '—' : v.toFixed(digits);
    return String(v);
}

function _kvGrid(rows) {
    const grid = document.createElement('div');
    grid.className = 'grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-0.5';
    rows.forEach(([k, v]) => {
        if (v === undefined) return;
        // min-w-0 lets the grid cell shrink below its content width so long
        // values wrap instead of overflowing the card (grid items default to
        // min-width:auto). break-words breaks the long unspaced SDK-version
        // JSON blobs so they stay inside the box.
        const row = document.createElement('div');
        row.className = 'min-w-0';
        const kSpan = document.createElement('span');
        kSpan.className = 'text-gray-400';
        kSpan.textContent = `${k}: `;
        const vSpan = document.createElement('span');
        vSpan.className = 'text-gray-800 font-mono break-words';
        vSpan.textContent = (v === null ? '—' : String(v));
        row.appendChild(kSpan);
        row.appendChild(vSpan);
        grid.appendChild(row);
    });
    return grid;
}

function _kvMap(obj) {
    if (!obj) return '—';
    return Object.entries(obj)
        .map(([k, v]) => `${k}=${v === null ? 'null' : (typeof v === 'object' ? JSON.stringify(v) : v)}`)
        .join(', ');
}

function _sectionLabel(text) {
    const d = document.createElement('div');
    d.className = 'font-semibold text-gray-500 mb-1';
    d.textContent = text;
    return d;
}

function _agreementMetricsBlock(p) {
    const m = p.metrics || {};
    const wrap = document.createElement('div');

    if (p.agreement === 'not_comparable') {
        wrap.appendChild(_sectionLabel('Not comparable'));
        wrap.appendChild(_kvGrid([
            ['reason', m.reason || '—'],
            ['details', m.details ? _kvMap(m.details) : '—'],
        ]));
        return wrap;
    }

    wrap.appendChild(_sectionLabel('Descriptive metrics (raw + registered transforms)'));
    const qp = m.qubit_permutation || {};
    let rows;
    if (p.mode === 'statevector') {
        rows = [
            ['direct fidelity', _fmtNum(m.direct_fidelity)],
            ['direct phase (rad)', _fmtNum(m.direct_relative_phase_rad)],
            ['bit-reversed fidelity', _fmtNum(m.bit_reversed_fidelity)],
            ['perm attempted', qp.attempted ? 'yes' : `no (${qp.reason || '—'})`],
            ['perm', qp.permutation ? JSON.stringify(qp.permutation) : '—'],
            ['perm fidelity', _fmtNum(qp.fidelity)],
        ];
    } else {
        rows = [
            ['JS divergence', _fmtNum(m.js_divergence)],
            ['Hellinger', _fmtNum(m.hellinger_distance)],
            ['bit-rev JS', _fmtNum(m.bit_reversed_js_divergence)],
            ['bit-rev Hellinger', _fmtNum(m.bit_reversed_hellinger_distance)],
            ['perm attempted', qp.attempted ? 'yes' : `no (${qp.reason || '—'})`],
            ['n_shots', m.n_shots],
        ];
    }
    wrap.appendChild(_kvGrid(rows));
    return wrap;
}

function _statisticalTestBlock(st) {
    const wrap = document.createElement('div');
    wrap.appendChild(_sectionLabel(`Shot-noise statistical test (basis: ${st.basis})`));
    const ef = st.effect_size || {};
    const pw = st.power || {};
    const chi2 = st.chi2 || {};
    const gt = st.g_test || {};
    wrap.appendChild(_kvGrid([
        ['χ² p', _fmtNum(chi2.p_value)],
        ['χ² p (BH)', _fmtNum(chi2.p_value_bh)],
        ['χ² significant', chi2.significant_bh ? 'yes' : 'no'],
        ['G-test p', _fmtNum(gt.p_value)],
        ['G-test p (BH)', _fmtNum(gt.p_value_bh)],
        ['G-test significant', gt.significant_bh ? 'yes' : 'no'],
        ['total variation', _fmtNum(ef.total_variation)],
        ["Cramér's V", _fmtNum(ef.cramers_v)],
        [`power@obs (δ=${pw.delta_tv})`, _fmtNum(pw.power_to_detect_delta_at_observed_shots, 3)],
        ['shots/backend for power', pw.shots_per_backend_for_target_power],
        ['low-count warning', st.low_count_warning ? 'yes ⚠' : 'no'],
    ]));
    const model = document.createElement('div');
    model.className = 'text-[11px] text-gray-400 mt-1';
    model.textContent = `Power model: ${pw.model}. The statistical verdict is reported alongside the descriptive label.`;
    wrap.appendChild(model);
    return wrap;
}

function _provenanceBlock(prov) {
    const wrap = document.createElement('div');
    if (!prov) return wrap;
    const rows = [
        ['qubit ordering', _kvMap(prov.qubit_ordering)],
        ['seed', prov.seed ? _kvMap(prov.seed) : undefined],
        ['sampling method', prov.sampling_method ? _kvMap(prov.sampling_method) : undefined],
        ['SDK versions', _kvMap(prov.sdk_versions)],
    ];
    const header = document.createElement('div');
    header.className = 'flex items-center gap-2';
    header.appendChild(_sectionLabel('Provenance'));
    if (typeof makeCopyIconButton === 'function') {
        const asText = () => rows.filter(r => r[1] !== undefined)
            .map(([k, v]) => `${k}: ${v}`).join('\n');
        header.appendChild(makeCopyIconButton(asText, 'Copy provenance'));
    }
    wrap.appendChild(header);
    wrap.appendChild(_kvGrid(rows));
    return wrap;
}

// Saturated agreement-class colours (validated dataviz palette) for the heatmap cells +
// legend swatches — the old bg-*-50 pastels were too dim against white. Gray = neutral
// not-comparable state.
const AGREEMENT_HEX = {
    agree_directly: '#008300', distance_within_threshold: '#008300',
    agree_up_to_global_phase: '#1baf7a', agree_after_bit_reversal: '#2a78d6',
    agree_after_qubit_permutation: '#4a3aa7',
    residual_disagreement: '#e34948', distance_exceeds_threshold: '#e34948',
    not_comparable: '#898781',
};

// Severity order for the pair table: most interesting (disagreement) first.
const _AGREEMENT_SEVERITY = {
    residual_disagreement: 0, distance_exceeds_threshold: 0,
    agree_after_qubit_permutation: 1, agree_after_bit_reversal: 2,
    agree_up_to_global_phase: 3, agree_directly: 4, distance_within_threshold: 4,
    not_comparable: 5,
};

function _pairLookup(pairs) {
    // key on the unordered pair so heatmap cell (i,j) resolves regardless of record order.
    const map = {};
    pairs.forEach(p => {
        const s = p.simulators || [];
        if (s.length === 2) map[[s[0], s[1]].sort().join('')] = p;
    });
    return map;
}

function _agreementLegend(present) {
    const wrap = document.createElement('div');
    wrap.className = 'flex flex-wrap gap-x-3 gap-y-1 mt-2 text-[11px]';
    present.forEach(label => {
        const item = document.createElement('span');
        item.className = 'inline-flex items-center gap-1';
        const sw = document.createElement('span');
        sw.className = 'inline-block w-3 h-3 rounded-sm border border-gray-300';
        sw.style.backgroundColor = AGREEMENT_HEX[label] || '#898781';
        item.appendChild(sw);
        item.appendChild(document.createTextNode(label));
        wrap.appendChild(item);
    });
    return wrap;
}

function _agreementSummaryStrip(report, pairs) {
    const strip = document.createElement('div');
    strip.className = 'flex flex-wrap gap-2 mb-4';

    const counts = {};
    pairs.forEach(p => { counts[p.agreement] = (counts[p.agreement] || 0) + 1; });
    Object.keys(counts)
        .sort((a, b) => (_AGREEMENT_SEVERITY[a] ?? 9) - (_AGREEMENT_SEVERITY[b] ?? 9))
        .forEach(label => {
            const pill = _chip(STATUS_STYLES[AGREEMENT_STYLE[label] || 'offline'].badge,
                `${label} · ${counts[label]}`, 'Agreement class count');
            strip.appendChild(pill);
        });

    const st = report.statistical_test_summary;
    if (st && st.verdict_counts) {
        const sep = document.createElement('span');
        sep.className = 'w-px bg-gray-200 mx-1';
        strip.appendChild(sep);
        Object.entries(st.verdict_counts).forEach(([v, n]) => {
            strip.appendChild(_chip(STATUS_STYLES[VERDICT_STYLE[v] || 'offline'].badge,
                `stat: ${v} · ${n}`, `Shot-noise verdict (α=${st.alpha}, ${(st.correction || []).join('+')})`));
        });
    }
    return strip;
}

function _agreementHeatmap(report, pairs, config) {
    const sims = report.simulators || [];
    if (sims.length < 2) return null;
    const lookup = _pairLookup(pairs);
    const wrap = document.createElement('div');
    wrap.className = 'mb-6 overflow-x-auto';

    const h = document.createElement('h4');
    h.className = 'text-sm font-semibold text-gray-700 mb-2';
    h.textContent = 'Agreement class by pair';
    wrap.appendChild(h);

    const table = document.createElement('table');
    table.className = 'matrix-table border-collapse text-xs';
    const thead = document.createElement('thead');
    const hrow = document.createElement('tr');
    hrow.appendChild(document.createElement('th'));
    sims.forEach(s => {
        const th = document.createElement('th');
        th.className = 'sim-header px-1 text-gray-600 font-medium align-bottom';
        th.textContent = _displayRunnerName(s);
        hrow.appendChild(th);
    });
    thead.appendChild(hrow);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    sims.forEach((s1, i) => {
        const tr = document.createElement('tr');
        const rh = document.createElement('th');
        rh.className = 'px-2 text-right text-gray-600 font-medium whitespace-nowrap';
        rh.textContent = _displayRunnerName(s1);
        tr.appendChild(rh);
        sims.forEach((s2, j) => {
            const td = document.createElement('td');
            td.className = 'w-6 h-6 text-center border border-white';
            if (i === j) {
                td.classList.add('bg-gray-100');
            } else {
                const rec = lookup[[s1, s2].sort().join('')];
                if (rec) {
                    td.style.backgroundColor = AGREEMENT_HEX[rec.agreement] || '#898781';
                    td.style.color = '#ffffff';
                    td.title = `${_displayRunnerName(s1)} × ${_displayRunnerName(s2)}: ${rec.agreement}`;
                    td.style.cursor = 'pointer';
                    td.onclick = () => {
                        const row = document.getElementById(`agr-row-${_agrRowId(rec)}`);
                        if (row) { row.open = true; row.scrollIntoView({ block: 'center' }); }
                    };
                } else {
                    td.classList.add('bg-gray-50');
                }
            }
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);

    const present = [...new Set(pairs.map(p => p.agreement))]
        .sort((a, b) => (_AGREEMENT_SEVERITY[a] ?? 9) - (_AGREEMENT_SEVERITY[b] ?? 9));
    wrap.appendChild(_agreementLegend(present));
    return wrap;
}

function _agrRowId(p) {
    const s = p.simulators || ['?', '?'];
    return `${s[0]}-${s[1]}`.replace(/[^a-zA-Z0-9-]/g, '_');
}

function _agreementPairTable(pairs) {
    const wrap = document.createElement('div');
    const h = document.createElement('h4');
    h.className = 'text-sm font-semibold text-gray-700 mb-2';
    h.textContent = 'Pairwise evidence';
    wrap.appendChild(h);

    // Filter chips (All + each present class).
    const present = [...new Set(pairs.map(p => p.agreement))]
        .sort((a, b) => (_AGREEMENT_SEVERITY[a] ?? 9) - (_AGREEMENT_SEVERITY[b] ?? 9));
    const filters = document.createElement('div');
    filters.className = 'flex flex-wrap gap-1.5 mb-2';
    const rows = [];
    const setFilter = (label) => {
        rows.forEach(r => { r.style.display = (!label || r.dataset.agreement === label) ? '' : 'none'; });
        filters.querySelectorAll('button').forEach(b => b.classList.toggle('ring-2', b.dataset.f === (label || '')));
    };
    const mkFilterBtn = (label, text) => {
        const b = document.createElement('button');
        b.dataset.f = label || '';
        b.className = 'px-2 py-0.5 rounded text-xs border border-gray-300 hover:bg-gray-100 ring-blue-400';
        b.textContent = text;
        b.onclick = () => setFilter(label);
        return b;
    };
    filters.appendChild(mkFilterBtn('', `All (${pairs.length})`));
    present.forEach(label => filters.appendChild(mkFilterBtn(label, label)));
    wrap.appendChild(filters);

    const list = document.createElement('div');
    list.className = 'space-y-1';

    const sorted = [...pairs].sort((a, b) =>
        (_AGREEMENT_SEVERITY[a.agreement] ?? 9) - (_AGREEMENT_SEVERITY[b.agreement] ?? 9));

    sorted.forEach(p => {
        const det = document.createElement('details');
        det.id = `agr-row-${_agrRowId(p)}`;
        det.dataset.agreement = p.agreement;
        det.className = 'rounded border border-gray-200 bg-white';
        rows.push(det);

        const sum = document.createElement('summary');
        sum.className = 'grid grid-cols-[minmax(140px,1fr)_auto_auto_auto] items-center gap-2 px-3 py-1.5 cursor-pointer text-sm select-none';

        const name = document.createElement('span');
        name.className = 'font-medium text-gray-800 truncate';
        const sims = p.simulators || ['?', '?'];
        name.textContent = `${_displayRunnerName(sims[0])} × ${_displayRunnerName(sims[1])}`;
        sum.appendChild(name);

        sum.appendChild(_chip(STATUS_STYLES[AGREEMENT_STYLE[p.agreement] || 'offline'].badge,
            p.agreement, 'Explained-cause label'));

        const metric = document.createElement('span');
        metric.className = 'text-xs text-gray-500 font-mono text-right';
        const m = p.metrics || {};
        metric.textContent = p.mode === 'statevector'
            ? `F=${_fmtNum(m.direct_fidelity)}` : `JS=${_fmtNum(m.js_divergence)}`;
        sum.appendChild(metric);

        const st = p.metrics && p.metrics.statistical_test;
        const vslot = document.createElement('span');
        if (st && st.verdict) {
            vslot.appendChild(_chip(STATUS_STYLES[VERDICT_STYLE[st.verdict] || 'offline'].badge,
                st.verdict, 'Shot-noise statistical verdict'));
        }
        sum.appendChild(vslot);
        det.appendChild(sum);

        const body = document.createElement('div');
        body.className = 'px-3 pb-3 pt-2 text-xs text-gray-600 space-y-2 border-t border-gray-100';
        body.appendChild(_agreementMetricsBlock(p));
        if (st) body.appendChild(_statisticalTestBlock(st));
        body.appendChild(_provenanceBlock(p.provenance));
        det.appendChild(body);
        list.appendChild(det);
    });
    wrap.appendChild(list);
    return wrap;
}

function renderAgreementPanel(report, panel, config = {}) {
    if (!panel) return;
    panel.innerHTML = '';

    const h3 = document.createElement('h3');
    h3.className = 'text-lg font-semibold text-gray-900 mb-4';
    // The hover tooltip on the title already carries the description, so no subtitle here.
    h3.appendChild(renderTooltip('pairwise_agreement', 'Explained-Cause Agreement'));
    panel.appendChild(h3);

    const pairs = report.pairwise_agreement;
    if (!Array.isArray(pairs) || pairs.length === 0) {
        const empty = document.createElement('p');
        empty.className = 'text-sm text-gray-500 italic';
        empty.textContent = 'No explained-cause agreement evidence in this report (older schema, single backend, or no comparable pairs).';
        panel.appendChild(empty);
        return;
    }

    panel.appendChild(_agreementSummaryStrip(report, pairs));
    const heat = _agreementHeatmap(report, pairs, config);
    if (heat) panel.appendChild(heat);
    panel.appendChild(_agreementPairTable(pairs));
}

function viewDetail(index) {
    const item = getState().currentSuiteData.benchmark_summary[index];
    const fname = item.task_name || (item.benchmark_file ? item.benchmark_file.replace('circuits/', '') : 'Unknown');

    clearReport();
    backButtonContainer.classList.remove('hidden');
    renderDetailReport(item, `Detail: ${fname}`, getState().currentRunnerConfig);
}