// Report layout: tabs, the single-circuit detail report, the batch suite summary, the
// Exports tab and the Quirk visualizer.

import { backButtonContainer, jsonOutput, panelElements, tabNav, welcomeMessage } from './dom.js';

import { BASE_URL, apiDetailText, getAuthHeaders } from './api.js';
import { renderArtifactsPanel } from './artifacts_renderer.js';
import { renderRankingTable, splitRanking } from './ranking_renderer.js';
import {
    TAG_AMBER, TAG_GRAY, _applyLegendDots, _cloneTemplate, _displayRunnerName, _makeStatusBadge, _tag, deviceTitle, isGpuRun,
} from './render_helpers.js';
import {
    RUNNER_STATUS_LABEL, RUNNER_STATUS_STYLE, isDisagreement, measuredAssessment, runnerStatus, statevectorGroup,
} from './run_status.js';
import { getState } from './state.js';
import { renderSummaryPanel } from './summary_renderer.js';
import { renderAgreementPanel, renderDivergenceTables } from './tables_renderer.js';
import { copyText, downloadBlob } from './utils.js';

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

// The Exports tab's JSON dump is stringified when the tab is first opened.
export let _rawTabData = null;
export let _rawTabRendered = false;

export function _reportHasTruncatedSv(data) {
    const scan = (arr) => Array.isArray(arr) && arr.some(r => r?.statevector_omitted_for_display
        || (typeof r?.statevector === 'string' && r.statevector.startsWith('<Statevector too large')));
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

/** Optimization level per runner from each result's optimization_level, else the override map. */
export function _effectiveOptMap(data, fallbackConfig = {}) {
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

/** Show or hide the Exports-tab truncation notice and the server-copy download button. */
function _updateExportNotices(data) {
    const warningBanner = document.getElementById('truncation-warning');
    const downloadButton = document.getElementById('download-btn');
    const live = !!getState().currentJobId;
    if (warningBanner) {
        warningBanner.classList.toggle('hidden', !_reportHasTruncatedSv(data));
        const text = warningBanner.querySelector('.tpl-truncation-text');
        if (text) {
            text.textContent = live
                ? 'Statevectors of circuits over 14 qubits are not in this browser copy. The server keeps the full report for 30 minutes after the job completes: use "Download full report" or export the RO-Crate with statevectors.'
                : 'Statevectors of circuits over 14 qubits are not in this copy, and this report did not come from a job run in this session, so no server copy is available.';
        }
    }
    if (downloadButton) downloadButton.classList.toggle('hidden', !live);
}

export function renderDetailReport(data, title, config = getState().currentRunnerConfig) {
    renderTabs(['summary', 'performance', 'resources', 'divergence', 'agreement', 'artifacts', 'raw']);
    _setRawTabData(data);
    _updateExportNotices(data);

    renderSummaryPanel(data, title);
    if (!data.error) {
        const optMap = _effectiveOptMap(data, config);
        const raws = data.raw_results || [];
        if (data.performance_report) renderRankingTable(data.performance_report, 'execution_time_sec', 's', panelElements.performance, optMap, raws);
        if (data.resource_report) renderRankingTable(data.resource_report, 'memory_usage_mb', 'MiB', panelElements.resources, optMap, raws);
        if (data.divergence_report) renderDivergenceTables(data.divergence_report, panelElements.divergence, optMap, raws);
        if (data.divergence_report) renderAgreementPanel(data.divergence_report, panelElements.agreement, optMap);
        renderArtifactsPanel(data, panelElements.artifacts);
    }

    showTab('summary');
}

/** A suite Fastest/Lightest cell: the backend name and its device tag. */
function _fillWinnerCell(td, entry, rawResults, next = null) {
    if (!td) return;
    if (!entry) {
        td.textContent = '-';
        return;
    }
    td.textContent = _displayRunnerName(entry.simulator);
    const raw = (Array.isArray(rawResults) ? rawResults : []).find(r => r && r.simulator === entry.simulator);
    if (typeof entry.timing_samples === 'number') td.appendChild(document.createTextNode(` (n=${entry.timing_samples})`));
    if (entry.overlaps_next === true && next) {
        td.appendChild(_tag('≈', TAG_AMBER, `Not separated from ${_displayRunnerName(next.simulator)}: their per-run totals overlap.`));
    }
    const device = raw?.device ?? entry.device;
    if (device) {
        const run = raw || entry;
        td.appendChild(_tag(String(device), isGpuRun(run) ? TAG_AMBER : TAG_GRAY, deviceTitle(run)));
    }
}

/** Agreement badge for a task whose pairs show no disagreement: measured pairs by assessment, statevector pairs by label group. */
function _agreementBadge(comparable) {
    const measured = comparable.filter(p => p.mode === 'measured');
    if (measured.length) {
        const assessments = measured.map(measuredAssessment);
        if (assessments.every(a => a === 'consistent_within_shot_noise')) {
            return _makeStatusBadge('success', 'All pairs consistent');
        }
        if (assessments.some(a => a === 'inconclusive_low_shots' || a === 'ambiguous')) {
            return _makeStatusBadge('offline', 'Inconclusive');
        }
        return _makeStatusBadge('offline', 'No shot-noise test');
    }
    const groups = comparable.map(statevectorGroup);
    if (groups.every(g => g === 'agree')) return _makeStatusBadge('success', 'All pairs agree');
    if (groups.every(g => g === 'agree' || g === 'bit_order')) {
        return _makeStatusBadge('success', 'All pairs agree (bit order as declared)');
    }
    return _makeStatusBadge('divergence', 'Other labels');
}

/** Status badges for one batch task: its agreement outcome plus one badge per failed-run status. */
function _taskBadges(item) {
    if (item.error) return [_makeStatusBadge('error', 'Error')];
    const raws = item.raw_results || [];
    const failures = {};
    raws.forEach(r => {
        const st = runnerStatus(r);
        if (st !== 'ok') failures[st] = (failures[st] || 0) + 1;
    });
    const nOk = raws.filter(r => runnerStatus(r) === 'ok').length;
    const pairs = item.divergence_report?.pairwise_agreement || [];
    const comparable = pairs.filter(p => p.agreement !== 'not_comparable');

    const badges = [];
    if (nOk < 2) {
        badges.push(_makeStatusBadge('offline', 'Not compared'));
    } else if (pairs.length === 0) {
        const n = item.divergence_report?.divergences_found?.length || 0;
        badges.push(n ? _makeStatusBadge('divergence', `${n} divergence(s)`) : _makeStatusBadge('offline', 'No pair records'));
    } else if (comparable.some(isDisagreement)) {
        badges.push(_makeStatusBadge('anomaly', 'Anomaly'));
    } else if (!comparable.length) {
        badges.push(_makeStatusBadge('offline', 'Not comparable'));
    } else {
        badges.push(_agreementBadge(comparable));
    }
    Object.entries(failures).forEach(([st, n]) => {
        badges.push(_makeStatusBadge(RUNNER_STATUS_STYLE[st], `${RUNNER_STATUS_LABEL[st]} ×${n}`));
    });
    return badges;
}

export function renderSuiteSummary(data, title) {
    clearReport();
    renderTabs(['suite-summary', 'raw']);
    _setRawTabData(data);
    _updateExportNotices(data);

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
        errDiv.textContent = data.error;
        errDiv.classList.add('whitespace-pre-wrap');
        panel.appendChild(errFrag);
    } else {
        if (data.job_error) {
            const errFrag = _cloneTemplate('tpl-suite-api-error');
            const errDiv = errFrag.querySelector('.tpl-error-text');
            errDiv.classList.remove('tpl-error-text');
            errDiv.classList.add('mb-4');
            errDiv.textContent = `The job failed: ${data.job_error}`;
            panel.appendChild(errFrag);
        }
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
            _taskBadges(item).forEach((badge, i) => {
                if (i) badge.classList.add('ml-1');
                statusCell.appendChild(badge);
            });

            const timeRanked = splitRanking(item.performance_report, 'execution_time_sec').ranked;
            const fastest = timeRanked[0];
            const lightest = splitRanking(item.resource_report, 'process_peak_rss_mb').ranked[0];
            _fillWinnerCell(rowFrag.querySelector('.tpl-fastest'), fastest, item.raw_results, timeRanked[1]);
            _fillWinnerCell(rowFrag.querySelector('.tpl-lightest'), lightest, item.raw_results);

            const detailsBtn = rowFrag.querySelector('.tpl-details-btn');
            detailsBtn.classList.remove('tpl-details-btn');
            detailsBtn.addEventListener('click', () => viewDetail(idx));

            tbody.appendChild(rowFrag);
        });

        panel.appendChild(tableFrag);
    }

    showTab('suite-summary');
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
            throw new Error(apiDetailText(data.detail) || data.error || 'Failed to generate visualizer URL');
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