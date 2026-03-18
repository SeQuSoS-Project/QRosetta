// =============================================================================
// tables_renderer.js — Tabular Data Rendering
// Responsibility: Rendering ranking tables (performance/resource) and the
//                 divergence matrix tables. These are complex DOM-heavy
//                 functions split from renderers.js to comply with the 300-line
//                 god-file rule (design_guidelines.txt §7.2).
// Depends on: STATUS_STYLES, renderTooltip, getOptBadge (renderers.js),
//             isConnectionError (utils.js), getState().currentSuiteData, getState().currentRunnerConfig,
//             panelElements, backButtonContainer (app.js globals),
//             clearReport, renderDetailReport (renderers.js)
// =============================================================================

function renderRankingTable(report, key, unit, panel, config = {}) {
    if (!panel) return;
    let html = `<h3 class="font-semibold text-gray-900 mt-4 mb-2">${report.summary}</h3>`;

    // Unified Legend
    html += `<div class="flex justify-start items-center space-x-4 text-xs text-gray-600 mb-4 p-2 bg-gray-50 rounded-lg border">
                <span class="font-bold">Legend:</span>
                <span class="flex items-center"><span class="w-3 h-3 inline-block rounded-full ${STATUS_STYLES.success.legendDot} mr-1.5"></span>Success</span>
                <span class="flex items-center"><span class="w-3 h-3 inline-block rounded-full ${STATUS_STYLES.offline.legendDot} mr-1.5"></span>Offline</span>
                <span class="flex items-center"><span class="w-3 h-3 inline-block rounded-full ${STATUS_STYLES.anomaly.legendDot} mr-1.5"></span>Anomaly</span>
            </div>`;

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
            return (a.process_peak_mb || 0) - (b.process_peak_mb || 0);
        });
        html += `<div class="overflow-x-auto border rounded-lg"><table class="min-w-full divide-y divide-gray-200"><thead class="bg-gray-50"><tr>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Rank</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Simulator</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">${renderTooltip('mem_delta', 'Mem Delta (MiB)')}</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">${renderTooltip('proc_peak', 'Process Peak (MiB)')}</th>
                </tr></thead><tbody class="bg-white divide-y divide-gray-200">`;
        report.ranking.forEach((r, i) => {
            let mem_delta_display = `<span class="text-red-600">Anomaly</span>`;
            let proc_peak_display = `<span class="text-red-600">Anomaly</span>`;

            if (r.status === 'success') {
                mem_delta_display = r.memory_usage_mb != null ? r.memory_usage_mb.toFixed(4) : mem_delta_display;
                proc_peak_display = r.process_peak_mb != null ? r.process_peak_mb.toFixed(1) : proc_peak_display;
            } else if (offlineSims.has(r.simulator)) {
                mem_delta_display = `<span class="${STATUS_STYLES.offline.cell}">Offline</span>`;
                proc_peak_display = `<span class="${STATUS_STYLES.offline.cell}">Offline</span>`;
            }

            html += `<tr>
                        <td class="px-4 py-3 text-sm text-gray-500">${i + 1}</td>
                        <td class="px-4 py-3 text-sm font-medium text-gray-900">${r.simulator}${getOptBadge(r.simulator, config)}</td>
                        <td class="px-4 py-3 text-sm text-gray-500 font-mono">${mem_delta_display}</td>
                        <td class="px-4 py-3 text-sm text-gray-500 font-mono">${proc_peak_display}</td>
                    </tr>`;
        });
        html += `</tbody></table></div>`;

    } else if (key === 'execution_time_sec') {
        html += `<div class="overflow-x-auto border rounded-lg"><table class="min-w-full divide-y divide-gray-200"><thead class="bg-gray-50"><tr>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Rank</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Simulator</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">${renderTooltip('compilation', 'Compilation (s)')}</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">${renderTooltip('simulation', 'Simulation (s)')}</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">${renderTooltip('total_time', 'Total (s)')}</th>
                </tr></thead><tbody class="bg-white divide-y divide-gray-200">`;
        report.ranking.forEach((r, i) => {
            let comp_display = `<span class="text-gray-400">-</span>`;
            let sim_display = `<span class="text-gray-400">-</span>`;
            let total_display = `<span class="text-gray-400">-</span>`;

            if (r.status === 'success') {
                if (r.execution_time_sec != null) total_display = r.execution_time_sec.toFixed(6);
                if (r.compilation_time_sec != null) comp_display = r.compilation_time_sec.toFixed(6);
                if (r.simulation_time_sec != null) sim_display = r.simulation_time_sec.toFixed(6);
            } else if (offlineSims.has(r.simulator)) {
                total_display = `<span class="${STATUS_STYLES.offline.cell}">Offline</span>`;
            } else {
                total_display = `<span class="text-red-600">Anomaly</span>`;
            }

            html += `<tr>
                        <td class="px-4 py-3 text-sm text-gray-500">${i + 1}</td>
                        <td class="px-4 py-3 text-sm font-medium text-gray-900">${r.simulator}${getOptBadge(r.simulator, config)}</td>
                        <td class="px-4 py-3 text-sm text-gray-500 font-mono">${comp_display}</td>
                        <td class="px-4 py-3 text-sm text-gray-500 font-mono">${sim_display}</td>
                        <td class="px-4 py-3 text-sm text-gray-900 font-mono font-medium">${total_display}</td>
                    </tr>`;
        });
        html += `</tbody></table></div>`;

    } else {
        // Fallback — Generic Table for any other metric
        html += `<div class="overflow-x-auto border rounded-lg"><table class="min-w-full divide-y divide-gray-200"><thead class="bg-gray-50"><tr>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Rank</th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Simulator</th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">${renderTooltip(key, 'Value')}</th>
            </tr></thead><tbody class="bg-white divide-y divide-gray-200">`;
        report.ranking.forEach((r, i) => {
            let val_display = `<span class="text-red-600">Anomaly</span>`;
            if (r.status === 'success' && r[key] !== null) {
                val_display = `${r[key].toFixed(6)} ${unit}`;
            } else if (offlineSims.has(r.simulator)) {
                val_display = `<span class="${STATUS_STYLES.offline.cell}">Offline</span>`;
            }
            html += `<tr><td class="px-4 py-3 text-sm text-gray-500">${i + 1}</td><td class="px-4 py-3 text-sm font-medium text-gray-900">${r.simulator}${getOptBadge(r.simulator, config)}</td><td class="px-4 py-3 text-sm text-gray-500 font-mono">${val_display}</td></tr>`;
        });
        html += `</tbody></table></div>`;
    }
    panel.innerHTML = html;
}

function renderDivergenceTables(report, panel, config = {}) {
    if (!panel) return;
    let html = `<div class="space-y-8">`;
    let found = false;
    const offlineSims = new Set();
    if (getState().currentSuiteData && getState().currentSuiteData.raw_results) {
        getState().currentSuiteData.raw_results.forEach(r => {
            if (r.error && isConnectionError(r.error)) offlineSims.add(r.simulator);
        });
    }

    // Unified Legend
    html += `<div class="flex justify-start items-center space-x-4 text-xs text-gray-600 mb-4 p-2 bg-gray-50 rounded-lg border">
                <span class="font-bold">Legend:</span>
                <span class="flex items-center"><span class="w-3 h-3 inline-block rounded-full ${STATUS_STYLES.success.legendDot} mr-1.5"></span>Perfect Match</span>
                <span class="flex items-center"><span class="w-3 h-3 inline-block rounded-full ${STATUS_STYLES.divergence.legendDot} mr-1.5"></span>Divergence</span>
                <span class="flex items-center"><span class="w-3 h-3 inline-block rounded-full ${STATUS_STYLES.offline.legendDot} mr-1.5"></span>Offline</span>
                <span class="flex items-center"><span class="w-3 h-3 inline-block rounded-full ${STATUS_STYLES.anomaly.legendDot} mr-1.5"></span>Anomaly</span>
                <span class="flex items-center"><span class="w-3 h-3 inline-block rounded-full bg-white border border-dashed border-gray-300 mr-1.5"></span>N/A (Self)</span>
            </div>`;

    const renderMat = (key, title) => {
        if (!report[key]) return;
        found = true;
        html += `<div><h3 class="font-semibold text-gray-900 mt-4 mb-2">${renderTooltip(key, title)}</h3><div class="overflow-x-auto"><table class="matrix-table border-collapse border border-gray-300"><thead class="bg-gray-50"><tr><th class="border p-2"></th>${report.simulators.map(s => `<th class="sim-header border p-2 text-xs text-gray-500">${s}${getOptBadge(s, config)}</th>`).join('')}</tr></thead><tbody>`;
        report.simulators.forEach((s1, i) => {
            html += `<tr><th class="border p-2 text-xs text-left text-gray-500">${s1}${getOptBadge(s1, config)}</th>`;
            report[key][i].forEach((val, j) => {
                let bg = STATUS_STYLES.divergence.cell;
                let txt = val.toFixed(4);

                if (offlineSims.has(s1) || offlineSims.has(report.simulators[j])) {
                    txt = "OFF";
                    bg = STATUS_STYLES.offline.cell;
                } else {
                    const epsilon = 1e-9;
                    let isPerfectMatch = false;
                    if (key.includes('fidelity') && Math.abs(val - 1.0) < epsilon) isPerfectMatch = true;
                    if (key.includes('phase') && (Math.abs(val - 1.0) < epsilon || Math.abs(val) < epsilon)) isPerfectMatch = true;
                    if ((key.includes('js_divergence') || key.includes('hellinger')) && Math.abs(val) < epsilon) isPerfectMatch = true;

                    if (isPerfectMatch) {
                        bg = STATUS_STYLES.success.cell;
                        if (key.includes('js_divergence') || key.includes('hellinger') || (key.includes('phase') && Math.abs(val) < epsilon)) {
                            txt = "0.000";
                        } else {
                            txt = "1.000";
                        }
                    } else if (val === -1.0) {
                        txt = "ERR";
                        bg = STATUS_STYLES.anomaly.cell;
                    }
                }

                if (i === j) {
                    bg = STATUS_STYLES.neutral.cell;
                    txt = "-";
                }
                html += `<td class="border p-2 text-xs text-center font-mono ${bg}">${txt}</td>`;
            });
            html += `</tr>`;
        });
        html += `</tbody></table></div></div>`;
    };

    renderMat('fidelity_matrix', 'Fidelity Matrix');
    renderMat('relative_phase_matrix', 'Relative Phase Matrix');
    renderMat('statistical_distance_matrix (js_divergence)', 'JS Divergence Matrix');
    renderMat('hellinger_distance_matrix', 'Hellinger Distance Matrix (Geometric)');

    if (!found) html += `<p class="text-gray-500 mt-4">No matrices available.</p>`;
    html += `</div>`;
    panel.innerHTML = html;
}

function viewDetail(index) {
    const item = getState().currentSuiteData.benchmark_summary[index];
    const fname = item.task_name || (item.benchmark_file ? item.benchmark_file.replace('benchmarks/', '') : 'Unknown');

    clearReport();
    backButtonContainer.classList.remove('hidden');
    renderDetailReport(item, `Detail: ${fname}`, getState().currentRunnerConfig);
}
