// =============================================================================
// tables_renderer.js — Tabular Data Rendering
// Responsibility: Rendering ranking tables (performance/resource) and the
//                 divergence matrix tables. These are complex DOM-heavy
//                 functions split from renderers.js to comply with the 300-line
//                 god-file rule (design_guidelines.txt §7.2).
// Depends on: STATUS_STYLES, renderTooltip, getOptBadge, _cloneTemplate,
//             _applyLegendDots (renderers.js),
//             isConnectionError (utils.js), getState().currentSuiteData,
//             getState().currentRunnerConfig, panelElements, backButtonContainer (app.js globals),
//             clearReport, renderDetailReport (renderers.js)
// Uses HTML <template> cloning — NO innerHTML string concatenation.
// =============================================================================

// --- PRIVATE HELPERS ---

/**
 * Creates a status-coloured <span> for a cell value (e.g. "Offline", "Anomaly")
 * using recognised STATUS_STYLES cell class keys.
 */
function _makeStatusCell(styleKey, text) {
    const span = document.createElement('span');
    STATUS_STYLES[styleKey].cell.split(' ').forEach(c => span.classList.add(c));
    span.textContent = text;
    return span;
}

/**
 * Populates the Simulator <td> with the simulator name text node
 * plus the optional optimisation badge Element from getOptBadge().
 */
function _fillSimulatorCell(td, simulatorName, config) {
    td.classList.remove('tpl-simulator');
    td.appendChild(document.createTextNode(simulatorName));
    
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

// --- PUBLIC RENDERERS ---

function renderRankingTable(report, key, unit, panel, config = {}) {
    if (!panel) return;
    panel.innerHTML = '';

    // Section heading
    const hFrag = _cloneTemplate('tpl-ranking-section-header');
    hFrag.querySelector('.tpl-summary-text').textContent = report.summary;
    panel.appendChild(hFrag);

    // Legend
    const legendFrag = _cloneTemplate('tpl-legend-ranking');
    _applyLegendDots(legendFrag);
    panel.appendChild(legendFrag);

    // Collect offline simulators
    const offlineSims = new Set();
    if (getState().currentSuiteData && getState().currentSuiteData.raw_results) {
        getState().currentSuiteData.raw_results.forEach(r => {
            if (r.error && isConnectionError(r.error)) offlineSims.add(r.simulator);
        });
    }

    if (key === 'memory_usage_mb') {
        // Sort: successful first, ordered by process_peak_mb ascending
        report.ranking.sort((a, b) => {
            if (a.status !== 'success') return 1;
            if (b.status !== 'success') return -1;
            return (a.process_peak_mb || 0) - (b.process_peak_mb || 0);
        });

        // Table wrapper with memory columns
        const tblFrag = _cloneTemplate('tpl-ranking-header-memory');

        // Apply tooltip to column headers
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

            const memDeltaTd = rowFrag.querySelector('.tpl-mem-delta');
            memDeltaTd.classList.remove('tpl-mem-delta');
            const procPeakTd = rowFrag.querySelector('.tpl-proc-peak');
            procPeakTd.classList.remove('tpl-proc-peak');
            const theoreticalTd = rowFrag.querySelector('.tpl-theoretical');
            if (theoreticalTd) theoreticalTd.classList.remove('.tpl-theoretical');

            if (r.status === 'success') {
                memDeltaTd.textContent = r.memory_usage_mb != null ? r.memory_usage_mb.toFixed(4) : '';
                procPeakTd.textContent = r.process_peak_mb != null ? r.process_peak_mb.toFixed(1) : '';
                if (theoreticalTd) {
                    theoreticalTd.textContent = r.theoretical_statevector_mb != null ? r.theoretical_statevector_mb.toFixed(4) : (r.theoretical_statevector_mb === null ? 'N/A' : '');
                }
            } else if (offlineSims.has(r.simulator)) {
                memDeltaTd.appendChild(_makeStatusCell('offline', 'Offline'));
                procPeakTd.appendChild(_makeStatusCell('offline', 'Offline'));
                if (theoreticalTd) theoreticalTd.appendChild(_makeStatusCell('offline', 'Offline'));
            } else {
                memDeltaTd.appendChild(_makeStatusCell('anomaly', 'Anomaly'));
                procPeakTd.appendChild(_makeStatusCell('anomaly', 'Anomaly'));
                if (theoreticalTd) theoreticalTd.appendChild(_makeStatusCell('anomaly', 'Anomaly'));
            }

            tbody.appendChild(rowFrag);
        });

        panel.appendChild(tblFrag);

    } else if (key === 'execution_time_sec') {
        // Table wrapper with time columns
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

            if (r.status === 'success') {
                compTd.textContent = r.compilation_time_sec != null ? r.compilation_time_sec.toFixed(6) : '-';
                simTd.textContent  = r.simulation_time_sec  != null ? r.simulation_time_sec.toFixed(6)  : '-';
                totalTd.textContent = r.execution_time_sec  != null ? r.execution_time_sec.toFixed(6)   : '-';
            } else if (offlineSims.has(r.simulator)) {
                compTd.appendChild(_makeStatusCell('offline', 'Offline'));
                simTd.appendChild(_makeStatusCell('offline', 'Offline'));
                totalTd.appendChild(_makeStatusCell('offline', 'Offline'));
            } else {
                compTd.appendChild(document.createTextNode('-'));
                simTd.appendChild(document.createTextNode('-'));
                totalTd.appendChild(_makeStatusCell('anomaly', 'Anomaly'));
            }

            tbody.appendChild(rowFrag);
        });

        panel.appendChild(tblFrag);

    } else {
        // Generic fallback table
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

    // Outer wrapper div
    const outerDiv = document.createElement('div');
    outerDiv.className = 'space-y-8';

    // Legend
    const legendFrag = _cloneTemplate('tpl-legend-divergence');
    _applyLegendDots(legendFrag);
    outerDiv.appendChild(legendFrag);

    // Collect offline simulators
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

        // Title cell — supports tooltip
        const h3 = secFrag.querySelector('.tpl-title');
        h3.classList.remove('tpl-title');
        h3.appendChild(renderTooltip(key, title));

        // Column headers row
        const theadRow = secFrag.querySelector('thead tr');
        report.simulators.forEach(s => {
            const thFrag = _cloneTemplate('tpl-div-matrix-header-cell');
            const th = thFrag.querySelector('th');
            th.appendChild(document.createTextNode(s));
            const badge = getOptBadge(s, config);
            if (badge) th.appendChild(badge);
            theadRow.appendChild(thFrag);
        });

        // Body rows
        const tbody = secFrag.querySelector('.tpl-tbody');
        tbody.classList.remove('tpl-tbody');

        report.simulators.forEach((s1, i) => {
            const tr = document.createElement('tr');

            // Row header
            const rhFrag = _cloneTemplate('tpl-div-matrix-row-header');
            const rowTh = rhFrag.querySelector('th');
            rowTh.appendChild(document.createTextNode(s1));
            const rBadge = getOptBadge(s1, config);
            if (rBadge) rowTh.appendChild(rBadge);
            tr.appendChild(rhFrag);

            // Data cells
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

    if (!found) {
        const p = document.createElement('p');
        p.className = 'text-gray-500 mt-4';
        p.textContent = 'No matrices available.';
        outerDiv.appendChild(p);
    }

    panel.appendChild(outerDiv);
}

function viewDetail(index) {
    const item = getState().currentSuiteData.benchmark_summary[index];
    const fname = item.task_name || (item.benchmark_file ? item.benchmark_file.replace('circuits/', '') : 'Unknown');

    clearReport();
    backButtonContainer.classList.remove('hidden');
    renderDetailReport(item, `Detail: ${fname}`, getState().currentRunnerConfig);
}
