// =============================================================================
// renderers.js — Core Rendering Helpers & Panel Builders
// Responsibility: Constants, helper utilities (tooltip, tabs, optBadge),
//                 and the three main panel renderers:
//                   renderSuiteSummary, renderSummaryPanel, renderDetailReport
// Uses HTML <template> cloning — NO innerHTML string concatenation.
// =============================================================================

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

// --- PRIVATE TEMPLATE UTILITY ---

/**
 * Clones a <template> by ID and returns the live DocumentFragment.
 * Throws a descriptive error if the template is missing (helps catch typos).
 */
function _cloneTemplate(id) {
    const tpl = document.getElementById(id);
    if (!tpl) throw new Error(`Missing <template id="${id}">`);
    return tpl.content.cloneNode(true);
}

/**
 * Walk the cloned fragment and replace placeholder class tokens (tpl-dot-*)
 * with the real Tailwind classes from STATUS_STYLES.
 * This is called once after cloning any legend template.
 */
function _applyLegendDots(fragment) {
    const dotMap = {
        'tpl-dot-success': STATUS_STYLES.success.legendDot,
        'tpl-dot-divergence': STATUS_STYLES.divergence.legendDot,
        'tpl-dot-offline': STATUS_STYLES.offline.legendDot,
        'tpl-dot-anomaly': STATUS_STYLES.anomaly.legendDot,
    };
    for (const [placeholder, classes] of Object.entries(dotMap)) {
        fragment.querySelectorAll(`.${placeholder}`).forEach(el => {
            el.classList.remove(placeholder);
            classes.split(' ').forEach(c => el.classList.add(c));
        });
    }
}

// --- HELPER FUNCTIONS ---

function isConnectionError(err) {
    if (!err) return false;
    const msg = err.toLowerCase();
    return msg.includes("failed to fetch") || msg.includes("load resource") || msg.includes("service unavailable") || msg.includes("connection refused");
}

/**
 * Returns a <span> Element with a tooltip (title attribute) wrapping label.
 * Falls back to a plain Text node when no definition exists.
 */
function renderTooltip(key, label) {
    const def = METRIC_DEFINITIONS[key];
    if (def) {
        const plainText = def.replace(/<b>/g, '').replace(/<\/b>/g, '');
        const span = document.createElement('span');
        span.style.cursor = 'help';
        span.style.textDecoration = 'underline dotted';
        span.title = plainText;
        span.textContent = label;
        return span;
    }
    return document.createTextNode(label);
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

/**
 * Returns a DOM Element for the optimization badge, or null if optLevel === 0.
 * NOTE: callers receive an Element (not a string) and must use appendChild.
 */
function getOptBadge(simulator, config) {
    const optLevel = config[simulator] !== undefined ? config[simulator] : 0;
    if (optLevel > 0) {
        const frag = _cloneTemplate('tpl-opt-badge');
        const span = frag.querySelector('span');
        span.textContent = `L${optLevel}`;
        span.title = `Optimization Level ${optLevel}`;
        return span;
    }
    return null;
}

// --- PRIVATE STATUS BADGE BUILDER ---

/**
 * Clones tpl-status-badge and applies the correct style + label.
 * Returns a live <span> Element.
 */
function _makeStatusBadge(styleKey, label) {
    const frag = _cloneTemplate('tpl-status-badge');
    const span = frag.querySelector('span');
    STATUS_STYLES[styleKey].badge.split(' ').forEach(c => span.classList.add(c));
    span.textContent = label;
    return span;
}

// --- MAIN PANEL RENDERERS ---

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

    const panel = panelElements['suite-summary'];
    if (!panel) return;
    panel.innerHTML = '';

    // Title
    const h2 = document.createElement('h2');
    h2.className = 'text-xl font-semibold text-gray-900 mb-4';
    h2.textContent = title;
    panel.appendChild(h2);

    // Legend
    const legendFrag = _cloneTemplate('tpl-legend-suite');
    _applyLegendDots(legendFrag);
    panel.appendChild(legendFrag);

    if (data.error) {
        // API error block
        const errFrag = _cloneTemplate('tpl-suite-api-error');
        const errDiv = errFrag.querySelector('.tpl-error-text');
        errDiv.classList.remove('tpl-error-text');
        errDiv.textContent = `API Error: ${data.error}`;
        panel.appendChild(errFrag);
    } else {
        const summary = data.benchmark_summary || [];
        const errors = summary.filter(r => r.error).length;

        // Stats bar
        const statsFrag = _cloneTemplate('tpl-suite-stats-bar');
        statsFrag.querySelector('.tpl-count').textContent = summary.length;
        statsFrag.querySelector('.tpl-errors').textContent = errors;
        panel.appendChild(statsFrag);

        // Table
        const tableFrag = _cloneTemplate('tpl-suite-table-wrapper');
        const tbody = tableFrag.querySelector('.tpl-tbody');
        tbody.classList.remove('tpl-tbody');

        summary.forEach((item, idx) => {
            const fname = item.task_name || (item.benchmark_file ? item.benchmark_file.replace('benchmarks/', '') : 'Unknown');
            const rowFrag = _cloneTemplate('tpl-suite-summary-row');

            rowFrag.querySelector('.tpl-task-name').textContent = fname;

            // Status badge
            const statusCell = rowFrag.querySelector('.tpl-status');
            statusCell.classList.remove('tpl-status');
            let badge;
            if (item.error) {
                badge = isConnectionError(item.error)
                    ? _makeStatusBadge('offline', 'Offline')
                    : _makeStatusBadge('anomaly', 'Anomaly');
            } else if (item.divergence_report && item.divergence_report.divergences_found.length > 0) {
                badge = _makeStatusBadge('divergence', 'Divergence');
            } else {
                badge = _makeStatusBadge('success', 'Success');
            }
            statusCell.appendChild(badge);

            rowFrag.querySelector('.tpl-fastest').textContent = item.performance_report?.ranking[0]?.simulator || '-';
            rowFrag.querySelector('.tpl-lightest').textContent = item.resource_report?.ranking[0]?.simulator || '-';

            const detailsBtn = rowFrag.querySelector('.tpl-details-btn');
            detailsBtn.classList.remove('tpl-details-btn');
            detailsBtn.addEventListener('click', () => viewDetail(idx));

            tbody.appendChild(rowFrag);
        });

        panel.appendChild(tableFrag);
    }

    showTab('suite-summary');
}

function renderSummaryPanel(data, title) {
    const panel = panelElements.summary;
    if (!panel) return;
    panel.innerHTML = '';

    // Title
    const h2 = document.createElement('h2');
    h2.className = 'text-xl font-semibold text-gray-900 mb-4';
    h2.textContent = title;
    panel.appendChild(h2);

    // Legend
    const legendFrag = _cloneTemplate('tpl-legend-suite');
    _applyLegendDots(legendFrag);
    panel.appendChild(legendFrag);

    if (data.error) {
        const errFrag = _cloneTemplate('tpl-summary-api-error');
        errFrag.querySelector('.tpl-error-text').textContent = data.error;
        panel.appendChild(errFrag);
        return;
    }

    const allErrors = data.raw_results ? data.raw_results.filter(r => r.error) : [];
    const offlineErrors = allErrors.filter(e => isConnectionError(e.error));
    const criticalErrors = allErrors.filter(e => !isConnectionError(e.error));
    const divergences = data.divergence_report ? data.divergence_report.divergences_found : [];

    if (offlineErrors.length > 0) {
        const frag = _cloneTemplate('tpl-summary-offline-block');
        frag.querySelector('.tpl-heading').textContent = `Offline Runners (${offlineErrors.length})`;
        const list = frag.querySelector('.tpl-list');
        list.classList.remove('tpl-list');
        offlineErrors.forEach(e => {
            const liFrag = _cloneTemplate('tpl-summary-list-item');
            const li = liFrag.querySelector('li');
            const b = document.createElement('b');
            b.textContent = e.simulator;
            li.appendChild(b);
            li.appendChild(document.createTextNode(': service unavailable'));
            list.appendChild(liFrag);
        });
        panel.appendChild(frag);
    }

    if (criticalErrors.length > 0) {
        const frag = _cloneTemplate('tpl-summary-critical-block');
        frag.querySelector('.tpl-heading').textContent = `Critical Errors (${criticalErrors.length})`;
        const list = frag.querySelector('.tpl-list');
        list.classList.remove('tpl-list');
        criticalErrors.forEach(e => {
            const liFrag = _cloneTemplate('tpl-summary-list-item');
            const li = liFrag.querySelector('li');
            const b = document.createElement('b');
            b.textContent = e.simulator;
            li.appendChild(b);
            li.appendChild(document.createTextNode(`: ${e.error}`));
            list.appendChild(liFrag);
        });
        panel.appendChild(frag);
    } else if (divergences.length > 0) {
        const frag = _cloneTemplate('tpl-summary-divergence-block');
        frag.querySelector('.tpl-heading').textContent = `Divergences Found (${divergences.length})`;
        const list = frag.querySelector('.tpl-list');
        list.classList.remove('tpl-list');
        divergences.forEach(d => {
            const liFrag = _cloneTemplate('tpl-summary-list-item');
            liFrag.querySelector('li').textContent = `${d.type} between ${d.simulators.join(' & ')}`;
            list.appendChild(liFrag);
        });
        panel.appendChild(frag);
    } else {
        const frag = _cloneTemplate('tpl-summary-success-banner');
        const msg = data.n_shots
            ? "All measurement distributions are statistically identical."
            : "All statevectors are identical (1.0 Fidelity).";
        frag.querySelector('.tpl-msg').textContent = msg;
        panel.appendChild(frag);
    }
}

// renderRankingTable, renderDivergenceTables, and viewDetail are in tables_renderer.js
