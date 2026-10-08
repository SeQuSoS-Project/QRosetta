// Report layout: tabs, the single-circuit detail report, the batch suite summary, the
// Exports tab and the Quirk visualizer.

import { backButtonContainer, panelElements, tabNav, welcomeMessage } from './dom.js';

import { BASE_URL, apiDetailText, getAuthHeaders } from './api.js';
import { renderExportTab, showExportTab } from './artifacts_renderer.js';
import { renderCircuitExplorer } from './circuit_explorer_renderer.js';
import { circuitPanes } from './circuit_panes.js';
import { backendVerdicts, headlineModel } from './backend_verdicts.js';
import { renderShareControls } from './share_links.js';
import { renderRankingTable, splitRanking } from './ranking_renderer.js';
import {
    TAG_AMBER, TAG_GRAY, _applyLegendDots, _cloneTemplate, _displayRunnerName, _makeStatusBadge, _tag, deviceTitle, isGpuRun,
} from './render_helpers.js';
import {
    RUNNER_STATUS_LABEL, RUNNER_STATUS_STYLE, isDisagreement, measuredAssessment, runnerStatus, statevectorGroup,
} from './run_status.js';
import { getState } from './state.js';
import { renderCompileSuiteTable, renderSummaryPanel } from './summary_renderer.js';
import { renderAgreementPanel, renderDivergenceTables } from './tables_renderer.js';

export function clearReport() {
    welcomeMessage.classList.add('hidden');
    tabNav.innerHTML = '';
    backButtonContainer.classList.add('hidden');

    Object.entries(panelElements).forEach(([key, panel]) => {
        if (key !== 'visualizer') {
            if (panel) panel.innerHTML = '';
        }
        if (panel) panel.classList.add('hidden');
    });
}

/** Panels each tab shows, in order, and the tab's label. */
const TAB_PANELS = {
    summary: ['summary'], agreement: ['agreement', 'divergence'], performance: ['performance', 'resources'],
    circuits: ['circuits'], export: ['export'], 'suite-summary': ['suite-summary'],
};
const TAB_LABELS = {
    summary: 'Summary', agreement: 'Agreement', performance: 'Performance', circuits: 'Circuits',
    export: 'Exports', 'suite-summary': 'Suite Summary',
};

export function showTab(tabName) {
    welcomeMessage.classList.add('hidden');
    Object.values(panelElements).forEach(panel => { if (panel) panel.classList.add('hidden') });

    const panels = TAB_PANELS[tabName] || [tabName];
    panels.forEach(key => panelElements[key]?.classList.remove('hidden'));
    if (panels.includes('export')) showExportTab();

    tabNav.querySelectorAll('[role="tab"]').forEach(btn => {
        const active = btn.getAttribute('data-tab') === tabName;
        btn.setAttribute('aria-selected', String(active));
        btn.tabIndex = active ? 0 : -1;
        btn.classList.toggle('border-blue-600', active);
        btn.classList.toggle('text-blue-600', active);
        btn.classList.toggle('border-transparent', !active);
        btn.classList.toggle('text-gray-500', !active);
        btn.classList.toggle('hover:text-gray-700', !active);
    });
}

export function renderTabs(tabList) {
    tabNav.innerHTML = '';
    tabNav.setAttribute('role', 'tablist');
    tabNav.setAttribute('aria-label', 'Result views');
    tabList.forEach(tabName => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'ml-4 px-3 py-3 font-medium text-sm border-b-2 border-transparent text-gray-500 hover:text-gray-700';
        button.textContent = TAB_LABELS[tabName] || tabName;
        button.dataset.tab = tabName;
        button.id = `tab-${tabName}`;
        button.setAttribute('role', 'tab');
        button.setAttribute('aria-selected', 'false');
        button.setAttribute('aria-controls', (TAB_PANELS[tabName] || [tabName]).map(k => panelElements[k]?.id).filter(Boolean).join(' '));
        button.tabIndex = -1;
        button.onclick = () => showTab(tabName);
        button.addEventListener('keydown', e => {
            const tabs = Array.from(tabNav.querySelectorAll('[role="tab"]'));
            const i = tabs.indexOf(button);
            const next = e.key === 'ArrowRight' ? tabs[(i + 1) % tabs.length]
                : e.key === 'ArrowLeft' ? tabs[(i - 1 + tabs.length) % tabs.length]
                : e.key === 'Home' ? tabs[0] : e.key === 'End' ? tabs[tabs.length - 1] : null;
            if (!next) return;
            e.preventDefault();
            next.focus();
            showTab(next.getAttribute('data-tab'));
        });
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

export function renderDetailReport(data, title, config = getState().currentRunnerConfig) {
    const hasCircuits = circuitPanes(data).length > 0;
    renderTabs(data.error ? ['summary', ...(hasCircuits ? ['circuits'] : []), 'export']
        : data.simulated === false ? ['summary', 'circuits', 'export']
        : ['summary', 'agreement', 'performance', 'circuits', 'export']);
    renderSummaryPanel(data, title);
    if (!data.error) {
        const optMap = _effectiveOptMap(data, config);
        const raws = data.raw_results || [];
        if (data.performance_report) renderRankingTable(data.performance_report, 'execution_time_sec', 's', panelElements.performance, optMap, raws);
        if (data.resource_report) renderRankingTable(data.resource_report, 'memory_usage_mb', 'MiB', panelElements.resources, optMap, raws);
        if (data.divergence_report) renderDivergenceTables(data.divergence_report, panelElements.divergence, optMap, raws);
        if (data.divergence_report) renderAgreementPanel(data.divergence_report, panelElements.agreement, optMap);
    }
    const suite = getState().currentSuiteData;
    const inPlaylist = suite && suite !== data && Array.isArray(suite.benchmark_summary);
    renderExportTab(data, panelElements.export, {
        scope: data.error && !(data.raw_results || []).length ? 'error' : inPlaylist ? 'task' : 'report',
        crateResults: inPlaylist ? suite : data,
    });
    renderCircuitExplorer(data, panelElements.circuits, {
        extraControls: renderShareControls,
        uploaded: data.saved_from === 'upload',
        filePrefix: typeof data.task_name === 'string' ? data.task_name : '',
    });

    showTab('summary');
}

/** A suite Fastest/Lightest cell: the backend name and its device tag. */
function _fillWinnerCell(td, entry, rawResults, next = null) {
    if (!td) return;
    if (!entry) {
        td.textContent = '—';
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
            return _makeStatusBadge('inconclusive', 'Inconclusive');
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
    if (item.simulated === false) return [_makeStatusBadge('offline', 'Compile only')];
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
        const h = headlineModel(backendVerdicts(item));
        const lead = h.flagged.slice(0, 2).map(_displayRunnerName);
        const more = h.flagged.length - lead.length;
        badges.push(lead.length
            ? _makeStatusBadge('anomaly', `Anomaly: ${lead.join(', ')}${more > 0 ? ` +${more}` : ''}`)
            : _makeStatusBadge('inconclusive', 'Significant under BY only'));
    } else if (!comparable.length) {
        badges.push(_makeStatusBadge('offline', 'Not comparable'));
    } else {
        badges.push(_agreementBadge(comparable));
    }
    Object.entries(failures).forEach(([st, n]) => {
        const badge = _makeStatusBadge(RUNNER_STATUS_STYLE[st], `${RUNNER_STATUS_LABEL[st]} ×${n}`);
        badge.classList.add('whitespace-nowrap');
        badges.push(badge);
    });
    return badges;
}

export function renderSuiteSummary(data, title) {
    clearReport();
    renderTabs(['suite-summary', 'export']);
    renderExportTab(data, panelElements.export, { scope: data.error ? 'error' : 'suite' });

    const panel = panelElements['suite-summary'];
    if (!panel) return;
    panel.innerHTML = '';

    const h2 = document.createElement('h2');
    h2.className = 'text-xl font-semibold text-gray-900 mb-4';
    h2.textContent = title;
    panel.appendChild(h2);

    const items = Array.isArray(data.benchmark_summary) ? data.benchmark_summary : [];
    const compileOnly = data.simulated === false || (items.some(item => item.simulated === false) && items.every(item => item.simulated === false || item.error));
    if (!compileOnly) {
        const legendFrag = _cloneTemplate('tpl-legend-suite');
        _applyLegendDots(legendFrag);
        panel.appendChild(legendFrag);
    }

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
        if (compileOnly) {
            const note = document.createElement('p');
            note.className = 'mb-3 text-sm text-gray-700';
            note.textContent = 'Compile only: no simulator was run. Details opens a circuit\'s compiled outputs, their passes and the reasons for the ones that did not compile.';
            panel.appendChild(note);
            panel.appendChild(renderCompileSuiteTable(summary, viewDetail));
            showTab('suite-summary');
            return;
        }

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
            const fastestCell = rowFrag.querySelector('.tpl-fastest');
            _fillWinnerCell(fastestCell, fastest, item.raw_results, timeRanked[1]);
            const rawOf = e => (item.raw_results || []).find(r => r && r.simulator === e.simulator) || e;
            if (fastest && fastestCell && isGpuRun(rawOf(fastest))) {
                const cpu = timeRanked.find(e => !isGpuRun(rawOf(e)));
                if (cpu) {
                    const sub = document.createElement('div');
                    sub.className = 'text-[11px] text-gray-500';
                    sub.textContent = `fastest CPU: ${_displayRunnerName(cpu.simulator)}`;
                    fastestCell.appendChild(sub);
                }
            }
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

/** Show the Quirk view as a full-page overlay above the results, which stay as they are. */
export function showVisualizerTab() {
    const overlay = panelElements['visualizer'];
    if (!overlay) return;
    overlay.classList.remove('hidden');
    overlay.classList.add('flex');
    document.getElementById('visualizer-close')?.focus();
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
        const link = /** @type {HTMLAnchorElement|null} */ (document.getElementById('quirk-open-link'));
        if (link) link.href = data.url;
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

/** Close the Quirk overlay; focus returns to the Visualize button. */
export function closeVisualizer() {
    const overlay = panelElements['visualizer'];
    if (!overlay || overlay.classList.contains('hidden')) return;
    overlay.classList.add('hidden');
    overlay.classList.remove('flex');
    document.getElementById('btn-visualize')?.focus();
}

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeVisualizer();
});
