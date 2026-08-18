// Frontend logic for renderers functionality.

import { backButtonContainer, jsonOutput, panelElements, tabNav, welcomeMessage } from './dom.js';

import { BASE_URL, getAuthHeaders } from './api.js';
import { renderArtifactsPanel } from './artifacts_renderer.js';
import { _applyLegendDots, _cloneTemplate, _makeStatusBadge } from './render_helpers.js';
import { getState } from './state.js';
import { renderAgreementPanel, renderDivergenceTables, renderRankingTable } from './tables_renderer.js';
import { _escapeHtml, copyText, downloadBlob, isConnectionError } from './utils.js';

export function clearReport() {
    welcomeMessage.classList.add('hidden');
    tabNav.innerHTML = '';
    backButtonContainer.classList.add('hidden');

    Object.entries(panelElements).forEach(([key, panel]) => {
        if (key !== 'raw' && key !== 'visualizer') {
            if (panel) panel.innerHTML = '';
        }
        if (panel) panel.classList.add('hidden');
    });
    _setRawTabData(null);

    const authorNameInput = document.getElementById('export-author-name');
    const authorAffiliationInput = document.getElementById('export-author-affiliation');
    const includeSvCheckbox = document.getElementById('export-include-sv');
    if (authorNameInput) authorNameInput.value = '';
    if (authorAffiliationInput) authorAffiliationInput.value = '';
    if (includeSvCheckbox) includeSvCheckbox.checked = false;
}

// The Exports/raw tab holds a pretty-printed dump of the whole report. Stringifying it
// eagerly on every render is wasteful for large reports, so defer it until the tab is
// first opened.
export let _rawTabData = null;
export let _rawTabRendered = false;

export function _reportHasTruncatedSv(data) {
    const scan = (arr) => Array.isArray(arr) && arr.some(
        r => typeof r?.statevector === 'string' && r.statevector.startsWith('<Statevector too large'));
    if (scan(data?.raw_results)) return true;
    if (Array.isArray(data?.benchmark_summary)) {
        return data.benchmark_summary.some(task => scan(task?.raw_results));
    }
    return false;
}

export function _setRawTabData(data) {
    _rawTabData = data;
    _rawTabRendered = false;
    if (jsonOutput) jsonOutput.textContent = '';
}

export function _renderRawTabIfNeeded() {
    if (_rawTabRendered || !_rawTabData || !jsonOutput) return;
    jsonOutput.textContent = JSON.stringify(_rawTabData, null, 2);
    _rawTabRendered = true;
}

export function showTab(tabName) {
    welcomeMessage.classList.add('hidden');
    Object.values(panelElements).forEach(panel => { if (panel) panel.classList.add('hidden') });

    if (tabName === 'raw') _renderRawTabIfNeeded();

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

export function renderTabs(tabList) {
    tabNav.innerHTML = '';
    tabList.forEach(tabName => {
        const button = document.createElement('button');
        button.className = 'ml-4 px-3 py-3 font-medium text-sm border-b-2 border-transparent text-gray-500 hover:text-gray-700';
        button.textContent = tabName.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase());
        if (tabName === 'raw') button.textContent = "Exports";
        button.dataset.tab = tabName;
        button.onclick = () => showTab(tabName);
        tabNav.appendChild(button);
    });
}

export function _effectiveOptMap(data, fallbackConfig = {}) {
    // Ground-truth effective optimization level per runner, as actually executed.
    // The dispatcher stamps result.optimization_level (clamped, global-or-override
    // resolved), so this reflects what ran — including global-level runs that have no
    // entry in the per-runner override map. Falls back to the override map only for
    // older reports (e.g. saved history) that predate optimization_level stamping.
    const map = { ...fallbackConfig };
    const collect = (arr) => {
        if (!Array.isArray(arr)) return;
        for (const r of arr) {
            if (r && r.simulator !== undefined && r.optimization_level !== undefined && r.optimization_level !== null) {
                map[r.simulator] = r.optimization_level;
            }
        }
    };
    collect(data?.raw_results);
    if (Array.isArray(data?.benchmark_summary)) {
        for (const task of data.benchmark_summary) collect(task?.raw_results);
    }
    return map;
}

export function renderDetailReport(data, title, config = getState().currentRunnerConfig) {
    renderTabs(['summary', 'performance', 'resources', 'divergence', 'agreement', 'artifacts', 'raw']);
    _setRawTabData(data);

    const warningBanner = document.getElementById('truncation-warning');
    const downloadButton = document.getElementById('download-btn');
    if (_reportHasTruncatedSv(data)) {
        warningBanner.classList.remove('hidden');
        downloadButton.classList.remove('hidden');
    } else {
        warningBanner.classList.add('hidden');
        downloadButton.classList.add('hidden');
    }

    renderSummaryPanel(data, title);
    if (!data.error) {
        const optMap = _effectiveOptMap(data, config);
        if (data.performance_report) renderRankingTable(data.performance_report, 'execution_time_sec', 's', panelElements.performance, optMap);
        if (data.resource_report) renderRankingTable(data.resource_report, 'memory_usage_mb', 'MiB', panelElements.resources, optMap);
        if (data.divergence_report) renderDivergenceTables(data.divergence_report, panelElements.divergence, optMap);
        if (data.divergence_report) renderAgreementPanel(data.divergence_report, panelElements.agreement, optMap);
        renderArtifactsPanel(data, panelElements.artifacts);
    }

    showTab('summary');
}

export function renderSuiteSummary(data, title) {
    clearReport();
    renderTabs(['suite-summary', 'raw']);
    _setRawTabData(data);

    const panel = panelElements['suite-summary'];
    if (!panel) return;
    panel.innerHTML = '';

    const h2 = document.createElement('h2');
    h2.className = 'text-xl font-semibold text-gray-900 mb-4';
    h2.textContent = title;
    panel.appendChild(h2);

    const legendFrag = _cloneTemplate('tpl-legend-suite');
    _applyLegendDots(legendFrag);
    panel.appendChild(legendFrag);

    if (data.error) {

        const errFrag = _cloneTemplate('tpl-suite-api-error');
        const errDiv = errFrag.querySelector('.tpl-error-text');
        errDiv.classList.remove('tpl-error-text');
        errDiv.textContent = `API Error: ${data.error}`;
        panel.appendChild(errFrag);
    } else {
        const summary = data.benchmark_summary || [];
        const errors = summary.filter(r => r.error).length;

        const statsFrag = _cloneTemplate('tpl-suite-stats-bar');
        statsFrag.querySelector('.tpl-count').textContent = summary.length;
        statsFrag.querySelector('.tpl-errors').textContent = errors;
        panel.appendChild(statsFrag);

        const tableFrag = _cloneTemplate('tpl-suite-table-wrapper');
        const tbody = tableFrag.querySelector('.tpl-tbody');
        tbody.classList.remove('tpl-tbody');

        summary.forEach((item, idx) => {
            const fname = item.task_name || (item.benchmark_file ? item.benchmark_file.replace('circuits/', '') : 'Unknown');
            const rowFrag = _cloneTemplate('tpl-suite-summary-row');

            rowFrag.querySelector('.tpl-task-name').textContent = fname;

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

export function renderSummaryPanel(data, title) {
    const panel = panelElements.summary;
    if (!panel) return;
    panel.innerHTML = '';

    const h2 = document.createElement('h2');
    h2.className = 'text-xl font-semibold text-gray-900 mb-4';
    h2.textContent = title;
    panel.appendChild(h2);

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
        const crossGroup = divergences.filter(d => d.is_cross_group);
        const withinGroup = divergences.filter(d => !d.is_cross_group);

        if (crossGroup.length > 0) {
            const frag = _cloneTemplate('tpl-summary-divergence-block');
            const heading = frag.querySelector('.tpl-heading');
            heading.textContent = `Qubit Ordering Divergences (${crossGroup.length})`;
            heading.parentElement.classList.remove('bg-red-50', 'text-red-700', 'border-red-200');
            heading.parentElement.classList.add('bg-yellow-50', 'text-yellow-700', 'border-yellow-200');

            const list = frag.querySelector('.tpl-list');
            list.classList.remove('tpl-list');
            const liFrag = _cloneTemplate('tpl-summary-list-item');
            const li = liFrag.querySelector('li');
            li.innerHTML = `Detected <b>${crossGroup.length}</b> pairwise divergences caused by mixed LSB vs MSB ordering conventions. These are expected and mathematically explained.`;

            const details = document.createElement('details');
            details.className = 'mt-2 text-xs text-yellow-800 cursor-pointer';
            const summary = document.createElement('summary');
            summary.className = 'font-semibold hover:text-yellow-600 outline-none py-1';
            summary.textContent = 'View Affected Simulators (Grouped)';
            details.appendChild(summary);

            const pairsList = document.createElement('ul');
            pairsList.className = 'list-none ml-2 mt-1 space-y-2 opacity-90';

            const processed = new Set();
            crossGroup.forEach(d => {
                const [s1, s2] = d.simulators;
                if (!processed.has(s1)) {
                    const partners = crossGroup
                        .filter(dx => dx.simulators.includes(s1))
                        .map(dx => ({
                            name: dx.simulators.find(sx => sx !== s1),
                            type: dx.type,
                            fidelity: dx.fidelity,
                            js: dx.js_divergence
                        }));

                    const subDetails = document.createElement('details');
                    subDetails.className = 'text-xs text-yellow-700';

                    const subSummary = document.createElement('summary');
                    subSummary.className = 'font-bold cursor-pointer hover:text-yellow-900 outline-none';
                    subSummary.innerHTML = `${_escapeHtml(s1)} <span class="font-normal opacity-60">&times; ${partners.length} partners</span>`;
                    subDetails.appendChild(subSummary);

                    const subUl = document.createElement('ul');
                    subUl.className = 'list-disc ml-4 mt-1 space-y-0.5 opacity-80';
                    partners.forEach(p => {
                        const liPartner = document.createElement('li');
                        let info = "";
                        if (p.fidelity !== undefined) info = ` (Fidelity: ${p.fidelity.toFixed(4)})`;
                        if (p.js !== undefined) info = ` (JS Div: ${p.js.toFixed(4)})`;
                        liPartner.innerHTML = `vs <b>${_escapeHtml(p.name)}</b>${info}`;
                        subUl.appendChild(liPartner);
                    });
                    subDetails.appendChild(subUl);

                    const pLi = document.createElement('li');
                    pLi.appendChild(subDetails);
                    pairsList.appendChild(pLi);

                    processed.add(s1);

                    partners.forEach(p => processed.add(p.name));
                }
            });

            details.appendChild(pairsList);
            li.appendChild(details);
            list.appendChild(liFrag);
            panel.appendChild(frag);
        }

        if (withinGroup.length > 0) {
            const frag = _cloneTemplate('tpl-summary-divergence-block');
            frag.querySelector('.tpl-heading').textContent = `True Numerical Divergences (${withinGroup.length})`;
            const list = frag.querySelector('.tpl-list');
            list.classList.remove('tpl-list');
            withinGroup.forEach(d => {
                const liFrag = _cloneTemplate('tpl-summary-list-item');
                let info = "";
                if (d.fidelity !== undefined) info = ` (Fidelity: ${d.fidelity.toFixed(4)})`;
                if (d.js_divergence !== undefined) info = ` (JS Div: ${d.js_divergence.toFixed(4)})`;

                liFrag.querySelector('li').innerHTML = `<b>${_escapeHtml(d.simulators.join(' & '))}</b>: ${_escapeHtml(d.type)}${info}`;
                list.appendChild(liFrag);
            });
            panel.appendChild(frag);
        }
    } else {
        const frag = _cloneTemplate('tpl-summary-success-banner');
        const msg = data.n_shots
            ? "All measurement distributions are statistically identical."
            : "All statevectors are identical (1.0 Fidelity).";
        frag.querySelector('.tpl-msg').textContent = msg;
        panel.appendChild(frag);
    }
}

export function viewDetail(index) {
    const item = getState().currentSuiteData.benchmark_summary[index];
    const fname = item.task_name || (item.benchmark_file ? item.benchmark_file.replace('circuits/', '') : 'Unknown');

    clearReport();
    backButtonContainer.classList.remove('hidden');
    renderDetailReport(item, `Detail: ${fname}`, getState().currentRunnerConfig);
}

export function copyRawJson(btn) {
    _renderRawTabIfNeeded();
    copyText(jsonOutput.textContent, btn);
}

export function downloadRawJson() {
    _renderRawTabIfNeeded();
    const jsonString = jsonOutput.textContent;
    if (!jsonString || jsonString.trim() === '') {
        alert("No JSON content to download.");
        return;
    }
    downloadBlob(new Blob([jsonString], { type: 'application/json' }), "rosetta_raw_report.json");
}

export function showVisualizerTab() {
    const welcome = document.getElementById('welcome-message');
    if (welcome) welcome.classList.add('hidden');
    Object.values(panelElements).forEach(panel => {
        if (panel) panel.classList.add('hidden');
    });
    if (panelElements['visualizer']) panelElements['visualizer'].classList.remove('hidden');

    const tabNavEl = document.getElementById('tab-nav');
    if (tabNavEl) {
        tabNavEl.querySelectorAll('button').forEach(btn => {
            btn.classList.remove('border-blue-600', 'text-blue-600');
            btn.classList.add('border-transparent', 'text-gray-500', 'hover:text-gray-700');
        });
    }
}

export async function generateAndVisualize() {
    const qasmText = document.getElementById('qasm-input').value;
    if (!qasmText || qasmText.trim() === '') {
        alert("No QASM code to visualize.");
        return;
    }

    const btn = document.getElementById('btn-visualize');
    let originalText = "📊 Visualize";
    if (btn) {
        originalText = btn.innerHTML;
        btn.innerHTML = `<span class="inline-block animate-spin mr-1 border-2 border-purple-600 border-t-transparent rounded-full w-3 h-3"></span> Loading`;
        btn.disabled = true;
    }

    try {
        const response = await fetch(`${BASE_URL}/visualize/quirk`, {
            method: 'POST',
            headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ qasm_string: qasmText })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to generate visualizer URL');
        }

        document.getElementById('quirk-iframe').src = data.url;
        showVisualizerTab();
    } catch (err) {
        console.error("Visualizer API Error:", err);
        alert("Could not auto-generate Quirk visualizer for this specific circuit.\nDetails: " + err.message);
    } finally {
        if (btn) {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    }
}

export function closeVisualizer() {
    if (panelElements['visualizer']) panelElements['visualizer'].classList.add('hidden');
    const suiteData = getState().currentSuiteData;
    if (suiteData) {
        showTab(suiteData.benchmark_summary ? 'suite-summary' : 'summary');
    } else {
        const welcome = document.getElementById('welcome-message');
        if (welcome) welcome.classList.remove('hidden');
        const tabNavEl = document.getElementById('tab-nav');
        if (tabNavEl) {
            tabNavEl.querySelectorAll('button').forEach(btn => {
                btn.classList.remove('border-blue-600', 'text-blue-600');
                btn.classList.add('border-transparent', 'text-gray-500', 'hover:text-gray-700');
            });
        }
    }
}