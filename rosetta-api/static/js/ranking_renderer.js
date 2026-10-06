// Performance and resource tables: ranked successful runs, then unranked runs with the
// reason they are not ranked. Reads the report without modifying it.

import {
    QUEUE_WAIT_SHOWN_SEC, TAG_AMBER, TAG_GRAY, _applyLegendDots, _cloneTemplate, _displayRunnerName,
    _makeStatusCell, _tag, cpuQuotaPhrase, deviceTitle, executionTags, fmtInt, fmtNum, getOptBadge, isGpuRun, coreClasses, mixedCoresText, outsideProcessText, precisionTag, simulationCoreSpeeds, unstableText, queueWaitText, throttleText,
    renderTooltip,
} from './render_helpers.js';
import { RUNNER_STATUS_LABEL, RUNNER_STATUS_STYLE, runnerStatus, userFacingError } from './run_status.js';

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
    runner_timeout: 'the run timed out',
    runner_offline: 'the runner was unreachable',
    missing_timing: 'the run returned no execution_time_sec',
    missing_process_peak_rss: 'the run returned no process_peak_rss_mb',
    gpu_memory_not_measured: 'it ran on a GPU, whose device memory is not measured',
};

/**
 * Ranked and unranked rows of a performance or resource report, as new arrays.
 * Reports without `unranked` carry failed runs inside `ranking`; those are moved to
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
    executionTags(raw, { device: false }).forEach(tag => td.appendChild(tag));
    const wait = queueWaitText(raw);
    if (wait) td.appendChild(_tag('queued', TAG_AMBER, wait.charAt(0).toUpperCase() + wait.slice(1)));
    const throttled = throttleText(raw);
    if (throttled) td.appendChild(_tag('throttled', TAG_AMBER, throttled.charAt(0).toUpperCase() + throttled.slice(1)));
    const unstable = unstableText(raw);
    if (unstable) td.appendChild(_tag('unstable', TAG_AMBER, unstable.charAt(0).toUpperCase() + unstable.slice(1)));
    const mixed = mixedCoresText(raw);
    if (mixed) td.appendChild(_tag('mixed cores', TAG_AMBER, mixed.charAt(0).toUpperCase() + mixed.slice(1)));
    const outside = outsideProcessText(raw);
    if (outside) td.appendChild(_tag('outside process', TAG_AMBER, outside.charAt(0).toUpperCase() + outside.slice(1)));
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

const UNSTABLE_LABEL = '1.3×';

/** Conditions in this run that can bias a timing comparison, as short phrases. */
function _timingCaveats(rawResults) {
    const ok = (rawResults || []).filter(r => r && !r.error);
    const caveats = [];
    if (ok.some(r => typeof r.overlapping_runs === 'number' && r.overlapping_runs > 0)) caveats.push('backends ran at the same time');
    if (!ok.every(r => r.exclusive === true) && ok.some(r => typeof r.server_overlapping_runs === 'number' && r.server_overlapping_runs > 0)) caveats.push('other jobs ran on the server');
    if (ok.some(r => throttleText(r))) caveats.push('some runs were throttled by the CPU quota');
    if (ok.some(r => unstableText(r))) caveats.push('some timed runs were unstable');
    if (coreClasses(new Set(ok.flatMap(simulationCoreSpeeds))).length > 1) caveats.push('runs used CPUs of different speeds');
    if (ok.some(r => outsideProcessText(r))) caveats.push('some work ran outside the measured process');
    if (ok.length && ok.every(r => _timingCount(r) === 1)) caveats.push('one timed run per backend (n=1)');
    return caveats;
}

function _timingNote(rawResults) {
    const ok = (rawResults || []).filter(r => r && !r.error);
    const samples = new Set(ok.map(_timingCount));
    let note = (samples.size === 1 && samples.has(1))
        ? 'Each value is one timed run (n=1) after one discarded warm-up run.'
        : `Timed runs per backend: ${[...samples].sort((a, b) => a - b).join(', ')}, after one discarded warm-up run. `
            + 'With more than one, a value is the median of the timed runs ± their sample standard deviation, with n; '
            + 'Total is median compilation + median simulation (execution_time_sec) ± the standard deviation of the per-run totals. '
            + 'Memory fields and outputs come from the first timed run; the per-run samples are in the raw JSON.';
    const quota = cpuQuotaPhrase(ok);
    const limit = quota ? `${quota} (cgroup quota) and 1 thread` : '1 thread (quota not reported)';
    note += ok.some(isGpuRun)
        ? ` CPU runners: ${limit} each. GPU runners run kernels on the GPU with `
            + 'host-side work under the same quota; times across devices compare different hardware.'
        : ` Each runner is limited to ${limit}.`;
    const throttled = ok.filter(r => throttleText(r)).length;
    if (!(samples.size === 1 && samples.has(1))) note += ' A ≈ next to a rank means its per-run totals overlap those of the next rank.';
    const classes = coreClasses(new Set(ok.flatMap(simulationCoreSpeeds)));
    if (classes.length > 1) {
        note += ` The simulation windows ran on CPUs of different speed classes (maximum ${classes.map(c => c.map(s => fmtInt(s)).join('/') + ' MHz').join(' vs ')}), `
            + 'so part of a difference between backends can be the core they ran on (tag "mixed cores" when one backend\'s own runs mixed them).';
    }
    const heldBack = Math.max(0, ...ok.filter(r => r.exclusive !== true).map(r => (typeof r.gate_wait_sec === 'number' ? r.gate_wait_sec : 0)));
    if (heldBack >= 1) note += ` This job waited ${fmtNum(heldBack, 1)} s while an exclusive run held the server (gate_wait_sec); the wait is not in the timings.`;
    if (ok.length && ok.every(r => r.exclusive === true)) {
        note += ' Exclusive run: the backends ran one at a time with no other run in flight on this server.';
    } else {
        const others = ok.filter(r => typeof r.server_overlapping_runs === 'number' && r.server_overlapping_runs > 0).length;
        if (others) note += ` ${others} run(s) overlapped with runs of other jobs on this server (server_overlapping_runs); for timings meant for comparison, use an exclusive run.`;
    }
    const unstableRuns = ok.filter(r => unstableText(r)).length;
    if (unstableRuns) note += ` ${unstableRuns} run(s) had timed runs spreading by more than ${UNSTABLE_LABEL} (tag "unstable").`;
    const overlapping = Math.max(0, ...ok.map(r => (typeof r.overlapping_runs === 'number' ? r.overlapping_runs : 0)));
    if (overlapping > 0) {
        note += ` Runs overlapped in time (up to ${overlapping} other run(s) of this job while one was running) and competed for the host's cores and memory bandwidth, `
            + 'which can slow some backends more than others; for timings meant for comparison, use the Sequential ordering or an exclusive run.';
    }
    const outside = ok.filter(r => outsideProcessText(r)).length;
    if (outside) note += ` ${outside} run(s) did part of their simulation work outside the measured process (tag "outside process").`;
    if (throttled) note += ` ${throttled} run(s) were held by the CPU quota during the simulation window (tag "throttled"); that wait is in their timings.`;
    const waited = (rawResults || []).filter(r => typeof r?.queue_wait_sec === 'number' && r.queue_wait_sec >= QUEUE_WAIT_SHOWN_SEC).length;
    if (waited) note += ` ${waited} run(s) waited ${QUEUE_WAIT_SHOWN_SEC} s or more for their runner to finish another run (tag "queued"); the wait is not in these timings.`;
    return note;
}

function _memoryNote(rawResults, unranked) {
    const gpu = (rawResults || []).filter(r => r && !r.error && isGpuRun(r));
    if (!gpu.length) return '';
    const unrankedIds = new Set(unranked.map(r => r.simulator));
    const names = gpu.map(r => _displayRunnerName(r.simulator)).join(', ');
    return gpu.every(r => unrankedIds.has(r.simulator))
        ? ` Memory fields are host RSS. GPU device memory is not measured, so the GPU run of ${names} is not ranked by memory; its host-side values are listed after the ranked runs.`
        : ` Memory fields are host RSS. GPU device memory is not measured, so the rank and memory values of the GPU run of ${names} describe host memory only.`;
}

function _deviceCell(raw) {
    const td = document.createElement('td');
    td.className = 'px-4 py-3 text-sm text-gray-700';
    if (!raw?.device) {
        td.textContent = '—';
        return td;
    }
    td.textContent = String(raw.device);
    td.title = deviceTitle(raw);
    if (isGpuRun(raw)) {
        td.className += ' font-medium text-amber-800';
        if (raw.gpu_name) {
            const sub = document.createElement('div');
            sub.className = 'text-[11px] font-normal text-gray-500';
            sub.textContent = String(raw.gpu_name);
            td.appendChild(sub);
        }
    }
    return td;
}

const TH_CLASS = 'px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase';
const TD_CLASS = 'px-4 py-3 text-sm text-gray-500 font-mono';

function _th(text, tooltipKey) {
    const th = document.createElement('th');
    th.className = TH_CLASS;
    th.appendChild(tooltipKey ? renderTooltip(tooltipKey, text) : document.createTextNode(text));
    return th;
}

/** Number of timed runs behind a result's timing fields. */
function _timingCount(raw) {
    const n = raw?.timing_samples ?? raw?.timing_repeats;
    if (Number.isInteger(n) && n > 0) return n;
    return Array.isArray(raw?.simulation_time_samples) ? raw.simulation_time_samples.length || 1 : 1;
}

function _median(xs) {
    const s = [...xs].sort((a, b) => a - b);
    const mid = Math.floor(s.length / 2);
    return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

function _stdev(xs) {
    if (xs.length < 2) return 0;
    const mean = xs.reduce((a, b) => a + b, 0) / xs.length;
    return Math.sqrt(xs.reduce((a, b) => a + (b - mean) ** 2, 0) / (xs.length - 1));
}

/** Per-run samples of one timing stage ('compilation', 'simulation' or 'execution'), or null. */
function _stageSamples(raw, stage) {
    const num = a => (Array.isArray(a) && a.length && a.every(v => typeof v === 'number') ? a : null);
    if (stage !== 'execution') return num(raw?.[`${stage}_time_samples`]);
    const exec = num(raw?.execution_time_samples);
    if (exec) return exec;
    const c = num(raw?.compilation_time_samples), s = num(raw?.simulation_time_samples);
    return c && s && c.length === s.length ? c.map((v, i) => v + s[i]) : null;
}

/** A timing cell: the value, or median ± sample standard deviation (n) over several timed runs. */
function _timingValue(r, raw, stage) {
    const field = `${stage}_time_sec`;
    const value = r[field] ?? raw?.[field];
    const n = _timingCount(raw);
    if (n <= 1) return fmtNum(value, 6);
    const samples = _stageSamples(raw, stage);
    const pick = (...keys) => keys.map(k => raw?.[k]).find(v => typeof v === 'number');
    const median = stage === 'execution'
        ? (r.execution_time_sec_median ?? value)
        : pick(`${stage}_time_sec_median`, `${stage}_time_median_sec`) ?? (samples ? _median(samples) : value);
    const sd = pick(`${stage}_time_sec_stdev`, `${stage}_time_stdev_sec`) ?? (samples ? _stdev(samples) : null);
    return `${fmtNum(median, 6)}${sd !== null ? ` ± ${fmtNum(sd, 6)}` : ''} (n=${n})`;
}

const TIME_COLUMNS = [
    { key: 'compilation', label: 'Compilation (s)', value: (r, raw) => _timingValue(r, raw, 'compilation') },
    { key: 'simulation', label: 'Simulation (s)', value: (r, raw) => _timingValue(r, raw, 'simulation') },
    { key: 'total_time', label: 'Total (s)', value: (r, raw) => _timingValue(r, raw, 'execution'), strong: true },
    { key: 'sim_cpu_time', label: 'Sim CPU (s)', value: (r, raw) => _timingValue({}, raw, 'simulation_cpu') },
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
    if (['error', 'timeout', 'offline'].includes(entry.status)) return entry.status;
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
    const note = isMemory ? _memoryNote(rawResults, unranked) : _timingNote(rawResults);
    const otherUnranked = isMemory ? unranked.filter(r => r.reason !== 'gpu_memory_not_measured') : unranked;
    const caveats = isMemory ? [] : _timingCaveats(rawResults);
    hFrag.querySelector('.tpl-summary-text').textContent = `${report.summary || ''}`
        + (caveats.length ? ` Before comparing times: ${caveats.join('; ')}.` : '')
        + (otherUnranked.length ? ` ${otherUnranked.length} ${otherUnranked.length === 1 ? 'run is' : 'runs are'} not ranked; `
            + `${otherUnranked.length === 1 ? 'it is' : 'they are'} listed after the ranked runs.` : '');
    panel.appendChild(hFrag);
    if (note.trim()) {
        const how = document.createElement('details');
        how.className = 'mb-4 text-sm text-gray-700';
        const sum = document.createElement('summary');
        sum.className = 'cursor-pointer select-none text-xs font-semibold text-gray-600';
        sum.textContent = isMemory ? 'About these memory values' : 'How these times are measured, and what affected them in this run';
        how.appendChild(sum);
        const p = document.createElement('p');
        p.className = 'mt-1 text-xs leading-snug';
        p.textContent = note.trim();
        how.appendChild(p);
        panel.appendChild(how);
    }

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
    hr.appendChild(_th('Device'));
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
        if (r.overlaps_next === true && ranked[i + 1]) {
            rankTd.appendChild(_tag('≈', TAG_AMBER, `Overlaps rank ${i + 2} (${_displayRunnerName(ranked[i + 1].simulator)}): `
                + 'this backend\'s slowest timed run took at least as long as that backend\'s fastest, so these runs do not separate the two. '
                + 'It reflects the spread within this job only: medians also move between jobs (about 3% on this host), so ranks without ≈ can still swap.'));
        }
        tr.appendChild(rankTd);
        const simTd = document.createElement('td');
        simTd.className = 'px-4 py-3 text-sm font-medium text-gray-900';
        _fillSimulatorCell(simTd, r.simulator, config, raw, { memory: isMemory });
        tr.appendChild(simTd);
        tr.appendChild(_deviceCell(raw));
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
        tr.appendChild(_deviceCell(raw));
        columns.forEach((c, idx) => {
            const td = document.createElement('td');
            td.className = TD_CLASS;
            if (status !== 'ok') {
                if (idx === 0) {
                    td.appendChild(_makeStatusCell(RUNNER_STATUS_STYLE[status], RUNNER_STATUS_LABEL[status],
                        userFacingError(r.error || raw?.error) || undefined));
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
