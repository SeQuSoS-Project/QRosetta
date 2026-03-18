// --- CONSTANTS & DEFINITIONS ---

const METRIC_DEFINITIONS = {
    "compilation": "<b>Compilation Time:</b> Time taken to parse QASM, apply transforms (e.g. Rebase), and convert to the backend's native format.",
    "simulation": "<b>Simulation Time:</b> Time taken for the backend to execute the circuit (matrix multiplication) and retrieve results.",
    "total_time": "<b>Total Execution Time:</b> Sum of Compilation and Simulation. Represents end-to-end latency.",
    "mem_delta": "<b>Memory Delta:</b> RAM added to the process during execution (End RSS - Start RSS). Isolates circuit cost from container overhead.",
    "proc_peak": "<b>Process Peak:</b> The absolute maximum RAM reached by the container. Hitting the limit (512MB) causes crashes.",
    "fidelity_matrix": "<b>Fidelity Matrix:</b> Pairwise comparison of state overlap. 1.0 = Identical states.",
    "relative_phase_matrix": "<b>Relative Phase Matrix:</b> Comparison of global phase differences. Non-zero means states differ by a constant phase factor.",
    "statistical_distance_matrix (js_divergence)": "<b>JS Divergence:</b> Jensen-Shannon divergence between probability distributions. 0.0 = Identical.",
    "hellinger_distance_matrix": "<b>Hellinger Distance:</b> Geometric distance between distributions. 0.0 = Identical.",
    "execution_time_sec": "<b>Execution Time:</b> The total time taken for the simulation.",
    "memory_usage_mb": "<b>Memory Usage:</b> The memory consumed by the simulation."
};

const STATUS_STYLES = {
    success: {
        badge: "bg-green-100 text-green-800 border-green-300",
        cell: "bg-green-50 text-gray-900",
        legendDot: "bg-green-100 border-green-300"
    },
    divergence: {
        badge: "bg-yellow-100 text-yellow-800 border-yellow-300",
        cell: "bg-yellow-50 text-gray-900",
        legendDot: "bg-yellow-100 border-yellow-300"
    },
    anomaly: {
        badge: "bg-red-100 text-red-800 border-red-300",
        cell: "bg-red-50 text-red-900 font-bold",
        legendDot: "bg-red-100 border-red-300"
    },
    offline: {
        badge: "bg-gray-100 text-gray-600 border-gray-300",
        cell: "bg-gray-100 text-gray-400 italic",
        legendDot: "bg-gray-100 border-gray-300"
    },
    neutral: {
        cell: "bg-white text-gray-900"
    }
};

// --- HELPER FUNCTIONS ---

function isConnectionError(err) {
    if (!err) return false;
    const msg = err.toLowerCase();
    return msg.includes("failed to fetch") || msg.includes("load resource") || msg.includes("service unavailable") || msg.includes("connection refused");
}

function renderTooltip(key, label) {
    const def = METRIC_DEFINITIONS[key];
    if (def) {
        const plainText = def.replace(/<b>/g, '').replace(/<\/b>/g, '');
        return `<span style="cursor: help; text-decoration: underline dotted;" title="${plainText}">${label}</span>`;
    }
    return label;
}

function clearReport() {
    welcomeMessage.classList.add('hidden');
    tabNav.innerHTML = '';
    backButtonContainer.classList.add('hidden');

    Object.entries(panelElements).forEach(([key, panel]) => {
        if (key !== 'raw' && key !== 'visualizer') {
            if (panel) panel.innerHTML = '';
        }
        if (panel) panel.classList.add('hidden');
    });
    if (jsonOutput) jsonOutput.textContent = '';
}

function showTab(tabName) {
    welcomeMessage.classList.add('hidden');
    Object.values(panelElements).forEach(panel => { if (panel) panel.classList.add('hidden') });

    const panel = panelElements[tabName];
    if (panel) panel.classList.remove('hidden');

    tabNav.querySelectorAll('button').forEach(btn => {
        btn.classList.remove('border-blue-600', 'text-blue-600');
        btn.classList.add('border-transparent', 'text-gray-500', 'hover:text-gray-700');
    });
    const activeBtn = tabNav.querySelector(`[data-tab="${tabName}"]`);
    if (activeBtn) {
        activeBtn.classList.add('border-blue-600', 'text-blue-600');
        activeBtn.classList.remove('border-transparent', 'text-gray-500', 'hover:text-gray-700');
    }
}

function renderTabs(tabList) {
    tabNav.innerHTML = '';
    tabList.forEach(tabName => {
        const button = document.createElement('button');
        button.className = 'ml-4 px-3 py-3 font-medium text-sm border-b-2 border-transparent text-gray-500 hover:text-gray-700';
        button.textContent = tabName.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase());
        if (tabName === 'raw') button.textContent = "Raw JSON";
        button.dataset.tab = tabName;
        button.onclick = () => showTab(tabName);
        tabNav.appendChild(button);
    });
}

function getOptBadge(simulator, config) {
    const optLevel = config[simulator] !== undefined ? config[simulator] : 0;
    if (optLevel > 0) {
        return `<span class="ml-2 inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800" title="Optimization Level ${optLevel}">L${optLevel}</span>`;
    }
    return '';
}

function renderDetailReport(data, title, config = getState().currentRunnerConfig) {
    renderTabs(['summary', 'performance', 'resources', 'divergence', 'raw']);
    const jsonString = JSON.stringify(data, null, 2);
    jsonOutput.textContent = jsonString;

    const warningBanner = document.getElementById('truncation-warning');
    const downloadButton = document.getElementById('download-btn');
    if (jsonString.includes("<Statevector too large for display")) {
        warningBanner.classList.remove('hidden');
        downloadButton.classList.remove('hidden');
    } else {
        warningBanner.classList.add('hidden');
        downloadButton.classList.add('hidden');
    }

    renderSummaryPanel(data, title);
    if (!data.error) {
        if (data.performance_report) renderRankingTable(data.performance_report, 'execution_time_sec', 's', panelElements.performance, config);
        if (data.resource_report) renderRankingTable(data.resource_report, 'memory_usage_mb', 'MiB', panelElements.resources, config);
        if (data.divergence_report) renderDivergenceTables(data.divergence_report, panelElements.divergence, config);
    }

    showTab('summary');
}

function renderSuiteSummary(data, title) {
    clearReport();
    renderTabs(['suite-summary', 'raw']);
    jsonOutput.textContent = JSON.stringify(data, null, 2);
    let html = `<h2 class="text-xl font-semibold text-gray-900 mb-4">${title}</h2>`;

    // Unified Legend
    html += `<div class="flex justify-start items-center space-x-4 text-xs text-gray-600 mb-4 p-2 bg-gray-50 rounded-lg border">
                <span class="font-bold">Legend:</span>
                <span class="flex items-center"><span class="w-3 h-3 inline-block rounded-full ${STATUS_STYLES.success.legendDot} mr-1.5"></span>Success</span>
                <span class="flex items-center"><span class="w-3 h-3 inline-block rounded-full ${STATUS_STYLES.divergence.legendDot} mr-1.5"></span>Divergence</span>
                <span class="flex items-center"><span class="w-3 h-3 inline-block rounded-full ${STATUS_STYLES.offline.legendDot} mr-1.5"></span>Offline</span>
                <span class="flex items-center"><span class="w-3 h-3 inline-block rounded-full ${STATUS_STYLES.anomaly.legendDot} mr-1.5"></span>Anomaly</span>
            </div>`;

    if (data.error) {
        html += `<div class="p-4 bg-red-50 text-red-700 rounded border border-red-200">API Error: ${data.error}</div>`;
    } else {
        const summary = data.benchmark_summary || [];
        const errors = summary.filter(r => r.error).length;
        html += `<div class="mb-4 p-4 bg-white border rounded shadow-sm">Processed <b>${summary.length}</b> tasks with <b>${errors}</b> errors.</div>`;
        html += `<div class="overflow-x-auto border rounded-lg"><table class="min-w-full divide-y divide-gray-200"><thead class="bg-gray-50"><tr>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Task</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Fastest</th>
                    <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Lightest</th>
                    <th></th>
                </tr></thead><tbody class="bg-white divide-y divide-gray-200">`;
        summary.forEach((item, idx) => {
            const fname = item.task_name || (item.benchmark_file ? item.benchmark_file.replace('benchmarks/', '') : 'Unknown');

            let status = `<span class="px-2 py-1 text-xs rounded border ${STATUS_STYLES.success.badge}">Success</span>`;
            if (item.error) {
                if (isConnectionError(item.error)) {
                    status = `<span class="px-2 py-1 text-xs rounded border ${STATUS_STYLES.offline.badge}">Offline</span>`;
                } else {
                    status = `<span class="px-2 py-1 text-xs rounded border ${STATUS_STYLES.anomaly.badge}">Anomaly</span>`;
                }
            }
            else if (item.divergence_report && item.divergence_report.divergences_found.length > 0) {
                status = `<span class="px-2 py-1 text-xs rounded border ${STATUS_STYLES.divergence.badge}">Divergence</span>`;
            }

            const fast = item.performance_report?.ranking[0]?.simulator || '-';
            const light = item.resource_report?.ranking[0]?.simulator || '-';

            html += `<tr>
                        <td class="px-4 py-3 text-sm font-medium text-gray-900">${fname}</td>
                        <td class="px-4 py-3">${status}</td>
                        <td class="px-4 py-3 text-sm text-gray-500">${fast}</td>
                        <td class="px-4 py-3 text-sm text-gray-500">${light}</td>
                        <td class="px-4 py-3 text-right"><button onclick="viewDetail(${idx})" class="text-blue-600 hover:text-blue-900 text-sm font-medium">Details</button></td>
                    </tr>`;
        });
        html += `</tbody></table></div>`;
    }

    if (panelElements['suite-summary']) {
        panelElements['suite-summary'].innerHTML = html;
    }
    showTab('suite-summary');
}

function renderSummaryPanel(data, title) {
    let html = `<h2 class="text-xl font-semibold text-gray-900 mb-4">${title}</h2>`;
    // Unified Legend
    html += `<div class="flex justify-start items-center space-x-4 text-xs text-gray-600 mb-4 p-2 bg-gray-50 rounded-lg border">
                <span class="font-bold">Legend:</span>
                <span class="flex items-center"><span class="w-3 h-3 inline-block rounded-full ${STATUS_STYLES.success.legendDot} mr-1.5"></span>Success</span>
                <span class="flex items-center"><span class="w-3 h-3 inline-block rounded-full ${STATUS_STYLES.divergence.legendDot} mr-1.5"></span>Divergence</span>
                <span class="flex items-center"><span class="w-3 h-3 inline-block rounded-full ${STATUS_STYLES.offline.legendDot} mr-1.5"></span>Offline</span>
                <span class="flex items-center"><span class="w-3 h-3 inline-block rounded-full ${STATUS_STYLES.anomaly.legendDot} mr-1.5"></span>Anomaly</span>
            </div>`;

    if (data.error) {
        html += `<div class="p-4 bg-red-50 text-red-700 border border-red-200 rounded"><h3 class="font-bold">API Error</h3><pre class="mt-2 text-xs">${data.error}</pre></div>`;
    } else {
        const allErrors = data.raw_results ? data.raw_results.filter(r => r.error) : [];
        const offlineErrors = allErrors.filter(e => isConnectionError(e.error));
        const criticalErrors = allErrors.filter(e => !isConnectionError(e.error));

        const divergences = data.divergence_report ? data.divergence_report.divergences_found : [];
        if (offlineErrors.length > 0) {
            html += `<div class="p-4 bg-gray-50 text-gray-700 border border-gray-200 rounded mb-4"><h3 class="font-bold">Offline Runners (${offlineErrors.length})</h3><ul class="list-disc ml-5 mt-2 text-sm text-gray-600">${offlineErrors.map(e => `<li><b>${e.simulator}</b>: service unavailable</li>`).join('')}</ul></div>`;
        }

        if (criticalErrors.length > 0) {
            html += `<div class="p-4 bg-red-50 text-red-700 border border-red-200 rounded mb-4"><h3 class="font-bold">Critical Errors (${criticalErrors.length})</h3><ul class="list-disc ml-5 mt-2 text-sm">${criticalErrors.map(e => `<li><b>${e.simulator}</b>: ${e.error}</li>`).join('')}</ul></div>`;
        } else if (divergences.length > 0) {
            html += `<div class="p-4 bg-yellow-50 text-yellow-800 border border-yellow-200 rounded"><h3 class="font-bold">Divergences Found (${divergences.length})</h3><ul class="list-disc ml-5 mt-2 text-sm">${divergences.map(d => `<li>${d.type} between ${d.simulators.join(' & ')}</li>`).join('')}</ul></div>`;
        } else {
            const msg = data.n_shots ? "All measurement distributions are statistically identical." : "All statevectors are identical (1.0 Fidelity).";
            html += `<div class="p-4 bg-green-50 text-green-800 border border-green-200 rounded flex items-center"><svg class="w-6 h-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>${msg}</div>`;
        }
    }
    if (panelElements.summary) {
        panelElements.summary.innerHTML = html;
    }
}

// renderRankingTable, renderDivergenceTables, and viewDetail moved to tables_renderer.js
