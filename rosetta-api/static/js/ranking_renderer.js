// Performance and resource tables: ranked successful runs, then unranked runs with the
// reason they are not ranked. Reads the report without modifying it.

import {
    TAG_AMBER, TAG_GRAY, _applyLegendDots, _cloneTemplate, _displayRunnerName,
    _makeStatusCell, _tag, fmtInt, fmtNum, getOptBadge, precisionTag, renderTooltip,
} from './render_helpers.js';
import { RUNNER_STATUS_LABEL, RUNNER_STATUS_STYLE, runnerStatus } from './run_status.js';

const SAMPLING_TAGS = {
    native: { label: 'Native', color: 'bg-green-100 text-green-700 border-green-200', title: 'The backend sampled the shots itself.' },
    sv_sample: { label: 'SV-Sample', color: 'bg-blue-100 text-blue-700 border-blue-200', title: 'Shots drawn from the computed statevector (multinomial).' },
    tn_sample: { label: 'TN-Sample', color: 'bg-orange-100 text-orange-700 border-orange-200', title: 'Shots sampled from tensor-network amplitudes.' },
};

const MISSING_METRIC_REASON = {
    execution_time_sec: 'missing_timing',
    process_peak_rss_mb: 'missing_process_peak_rss',
};

const UNRANKED_REASON_TEXT = {
    runner_error: 'the run returned an error',
    missing_timing: 'the run returned no execution_time_sec',
    missing_process_peak_rss: 'the run returned no process_peak_rss_mb',
};

/**
 * Ranked and unranked rows of a performance or resource report, as new arrays.
 * Reports that predate `unranked` carry failed runs inside `ranking`; those are moved to
 * the unranked list here.
 */
export function splitRanking(report, metric) {
    const all = Array.isArray(report?.ranking) ? report.ranking : [];
    const isRanked = r => r && r.status === 'success' && typeof r[metric] === 'number';
    const ranked = all.filter(isRanked).sort((a, b) => a[metric] - b[metric]);
    const legacyUnranked = all.filter(r => !isRanked(r)).map(r => ({
        ...r,
        reason: r.reason || (r.status === 'success' ? MISSING_METRIC_REASON[metric] : 'runner_error'),
    }));
    const unranked = [...(Array.isArray(report?.unranked) ? report.unranked : []), ...legacyUnranked];
    return { ranked, unranked };
}

function _rawIndex(rawResults) {
    const map = new Map();
    (Array.isArray(rawResults) ? rawResults : []).forEach(r => { if (r) map.set(r.simulator, r); });
    return map;
}

function _fillSimulatorCell(td, simulatorName, config, raw, { memory = false } = {}) {
    td.appendChild(document.createTextNode(_displayRunnerName(simulatorName)));
    if (raw?.qubit_ordering) {
        td.appendChild(_tag(String(raw.qubit_ordering).toUpperCase(), TAG_GRAY,
            'Qubit ordering declared by the runner'));
    }
    if (raw?.sampling_method) {
        const cfg = SAMPLING_TAGS[raw.sampling_method];
        td.appendChild(cfg
            ? _tag(cfg.label, cfg.color, `Sampling method: ${cfg.title}`)
            : _tag(String(raw.sampling_method), TAG_GRAY, 'Sampling method'));
    }
    const prec = precisionTag(raw?.precision);
    if (prec) td.appendChild(prec);
    if (memory && raw?.memory_method && raw.memory_method !== 'vmhwm') {
        td.appendChild(_tag(raw.memory_method, TAG_AMBER,
            `Window memory measured by ${raw.memory_method} RSS polling instead of the kernel high-water mark; short peaks can be missed.`));
    }
    if (memory && raw?.process_peak_rss_method && raw.process_peak_rss_method !== 'vmhwm') {
        td.appendChild(_tag(raw.process_peak_rss_method, TAG_AMBER,
            `Process Peak RSS from ${raw.process_peak_rss_method} (ru_maxrss), which in a spawned child also includes the parent's peak.`));
    }
    const badge = getOptBadge(simulatorName, config);
    if (badge) td.appendChild(badge);
}

function _timingNote(rawResults) {
    const samples = new Set((rawResults || []).filter(r => r && !r.error)
        .map(r => r.timing_samples).filter(n => Number.isInteger(n)));
    if (samples.size === 0 || (samples.size === 1 && samples.has(1))) {
        return 'Each value is one timed run (n=1) after one discarded warm-up run.';
    }
    return `Timed runs per backend: ${[...samples].sort().join(', ')}; the columns show the last run (mean and stdev are in the raw JSON).`;
}

const TH_CLASS = 'px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase';
const TD_CLASS = 'px-4 py-3 text-sm text-gray-500 font-mono';

function _th(text, tooltipKey) {
    const th = document.createElement('th');
    th.className = TH_CLASS;
    th.appendChild(tooltipKey ? renderTooltip(tooltipKey, text) : document.createTextNode(text));
    return th;
}

const TIME_COLUMNS = [
    { key: 'compilation', label: 'Compilation (s)', value: (r) => fmtNum(r.compilation_time_sec, 6) },
    { key: 'simulation', label: 'Simulation (s)', value: (r) => fmtNum(r.simulation_time_sec, 6) },
    { key: 'total_time', label: 'Total (s)', value: (r) => fmtNum(r.execution_time_sec, 6), strong: true },
    { key: 'sim_cpu_time', label: 'Sim CPU (s)', value: (r, raw) => fmtNum(raw?.simulation_cpu_time_sec, 6) },
    { key: 'cpu_time', label: 'CPU, whole process (s)', value: (r, raw) => fmtNum(r.cpu_time_sec ?? raw?.cpu_time_sec, 6) },
    { key: 'gate_count', label: 'Gate Count', value: (r, raw) => fmtInt(r.gate_count ?? raw?.gate_count) },
    { key: 'circuit_depth', label: 'Depth', value: (r, raw) => fmtInt(r.circuit_depth ?? raw?.circuit_depth) },
];

const MEMORY_COLUMNS = [
    { key: 'proc_peak_rss', label: 'Process Peak RSS (MiB)', value: (r) => fmtNum(r.process_peak_rss_mb, 1), strong: true },
    { key: 'mem_delta', label: 'Sim-window RSS delta (MiB)', value: (r) => fmtNum(r.memory_usage_mb, 4) },
    { key: 'proc_peak', label: 'Sim-window peak RSS (MiB)', value: (r) => fmtNum(r.process_peak_mb, 1) },
    {
        key: 'theoretical_sv', label: 'Theoretical SV (MiB)',
        value: (r, raw) => {
            const v = r.theoretical_statevector_mb !== undefined ? r.theoretical_statevector_mb : raw?.theoretical_statevector_mb;
            return v === null ? 'N/A' : fmtNum(v, 4);
        },
    },
];

function _statusOf(entry, raw) {
    if (raw) return runnerStatus(raw);
    if (entry.error) return runnerStatus(entry);
    return 'ok';
}

/** Render a performance (execution_time_sec) or resource (memory_usage_mb) report. */
export function renderRankingTable(report, key, unit, panel, config = {}, rawResults = []) {
    if (!panel) return;
    panel.innerHTML = '';

    const isMemory = key === 'memory_usage_mb';
    const metric = isMemory ? 'process_peak_rss_mb' : 'execution_time_sec';
    const columns = isMemory ? MEMORY_COLUMNS : TIME_COLUMNS;
    const raws = _rawIndex(rawResults);
    const { ranked, unranked } = splitRanking(report, metric);

    const hFrag = _cloneTemplate('tpl-ranking-section-header');
    const note = isMemory ? '' : ` ${_timingNote(rawResults)}`;
    hFrag.querySelector('.tpl-summary-text').textContent =
        `${report.summary || ''}${note}${unranked.length ? ` ${unranked.length} run(s) are not ranked; they are listed after the ranked runs.` : ''}`;
    panel.appendChild(hFrag);

    const legendFrag = _cloneTemplate('tpl-legend-ranking');
    _applyLegendDots(legendFrag);
    panel.appendChild(legendFrag);

    const wrap = document.createElement('div');
    wrap.className = 'overflow-x-auto border rounded-lg';
    const table = document.createElement('table');
    table.className = 'min-w-full divide-y divide-gray-200';
    const thead = document.createElement('thead');
    thead.className = 'bg-gray-50';
    const hr = document.createElement('tr');
    hr.appendChild(_th('Rank'));
    hr.appendChild(_th('Simulator'));
    columns.forEach(c => hr.appendChild(_th(c.label, c.key)));
    thead.appendChild(hr);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    tbody.className = 'bg-white divide-y divide-gray-200';

    ranked.forEach((r, i) => {
        const raw = raws.get(r.simulator);
        const tr = document.createElement('tr');
        const rankTd = document.createElement('td');
        rankTd.className = 'px-4 py-3 text-sm text-gray-500';
        rankTd.textContent = String(r.rank ?? i + 1);
        tr.appendChild(rankTd);
        const simTd = document.createElement('td');
        simTd.className = 'px-4 py-3 text-sm font-medium text-gray-900';
        _fillSimulatorCell(simTd, r.simulator, config, raw, { memory: isMemory });
        tr.appendChild(simTd);
        columns.forEach(c => {
            const td = document.createElement('td');
            td.className = c.strong ? 'px-4 py-3 text-sm text-gray-900 font-mono font-medium' : TD_CLASS;
            td.textContent = c.value(r, raw);
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });

    unranked.forEach(r => {
        const raw = raws.get(r.simulator);
        const status = _statusOf(r, raw);
        const tr = document.createElement('tr');
        tr.className = 'bg-gray-50';
        const rankTd = document.createElement('td');
        rankTd.className = 'px-4 py-3 text-xs text-gray-400';
        rankTd.textContent = 'not ranked';
        tr.appendChild(rankTd);
        const simTd = document.createElement('td');
        simTd.className = 'px-4 py-3 text-sm font-medium text-gray-900';
        _fillSimulatorCell(simTd, r.simulator, config, raw, { memory: isMemory });
        const reason = document.createElement('div');
        reason.className = 'text-[11px] font-normal text-gray-500';
        reason.textContent = `reason: ${r.reason || 'not recorded'}${UNRANKED_REASON_TEXT[r.reason] ? ` (${UNRANKED_REASON_TEXT[r.reason]})` : ''}`;
        simTd.appendChild(reason);
        tr.appendChild(simTd);
        columns.forEach((c, idx) => {
            const td = document.createElement('td');
            td.className = TD_CLASS;
            if (status !== 'ok') {
                if (idx === 0) {
                    td.appendChild(_makeStatusCell(RUNNER_STATUS_STYLE[status], RUNNER_STATUS_LABEL[status],
                        r.error || raw?.error || undefined));
                } else {
                    td.textContent = '—';
                }
            } else {
                td.textContent = c.value(r, raw);
            }
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    wrap.appendChild(table);
    panel.appendChild(wrap);
}
