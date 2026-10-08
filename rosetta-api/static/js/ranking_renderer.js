// Performance and resource tables: ranked successful runs, then unranked runs with the
// reason they are not ranked. Reads the report without modifying it.

import {
    QUEUE_WAIT_SHOWN_SEC, TAG_AMBER, TAG_GRAY, _applyLegendDots, _cloneTemplate, _displayRunnerName,
    _makeStatusCell, _tag, bitOrderTag, cpuQuotaPhrase, executionTags, fmtInt, fmtNum, getOptBadge, isGpuRun, coreClasses, mixedCoresText, outsideProcessText, precisionTag, samplingTag, simulationCoreSpeeds, unstableText, queueWaitText, throttleText,
    renderTooltip,
} from './render_helpers.js';
import { RUNNER_STATUS_LABEL, RUNNER_STATUS_STYLE, runnerStatus, userFacingError } from './run_status.js';

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

/** The backend's name, then its tags on one wrapping line below it. */
function _fillSimulatorCell(cell, simulatorName, config, raw, { memory = false } = {}) {
    cell.appendChild(document.createTextNode(_displayRunnerName(simulatorName)));
    const td = document.createElement('div');
    td.className = 'mt-1 flex flex-wrap gap-1 font-normal [&>*]:ml-0';
    const order = bitOrderTag(raw?.qubit_ordering);
    if (order) td.appendChild(order);
    const sampling = samplingTag(raw?.sampling_method);
    if (sampling) td.appendChild(sampling);
    const prec = precisionTag(raw?.precision);
    if (prec) td.appendChild(prec);
    executionTags(raw, { device: isGpuRun(raw) }).forEach(tag => td.appendChild(tag));
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
    if (td.childElementCount) cell.appendChild(td);
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

const TH_CLASS = 'px-2 py-2 text-left text-[11px] leading-tight font-medium text-gray-500 align-bottom';
const TD_CLASS = 'px-2 py-2 text-xs text-gray-500 font-mono whitespace-nowrap align-top';

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

/** A timing value: the value, or with several timed runs the median, its sample standard deviation and n. */
function _timingValue(r, raw, stage) {
    const field = `${stage}_time_sec`;
    const value = r[field] ?? raw?.[field];
    const n = _timingCount(raw);
    if (n <= 1) return { value, sd: null, n };
    const samples = _stageSamples(raw, stage);
    const pick = (...keys) => keys.map(k => raw?.[k]).find(v => typeof v === 'number');
    const median = stage === 'execution'
        ? (r.execution_time_sec_median ?? value)
        : pick(`${stage}_time_sec_median`, `${stage}_time_median_sec`) ?? (samples ? _median(samples) : value);
    const sd = pick(`${stage}_time_sec_stdev`, `${stage}_time_stdev_sec`) ?? (samples ? _stdev(samples) : null);
    return { value: median, sd, n };
}

const _plain = v => ({ value: v, sd: null, n: 1 });

const TIME_COLUMNS = [
    { key: 'compilation', label: 'Compilation (s)', value: (r, raw) => _timingValue(r, raw, 'compilation') },
    { key: 'simulation', label: 'Simulation (s)', value: (r, raw) => _timingValue(r, raw, 'simulation') },
    { key: 'total_time', label: 'Total (s)', value: (r, raw) => _timingValue(r, raw, 'execution'), strong: true },
    { key: 'sim_cpu_time', label: 'Sim CPU (s)', value: (r, raw) => _timingValue({}, raw, 'simulation_cpu') },
    { key: 'cpu_time', label: 'CPU, whole process (s)', value: (r, raw) => _plain(r.cpu_time_sec ?? raw?.cpu_time_sec) },
    { key: 'gate_count', label: 'Gate Count', value: (r, raw) => _plain(r.gate_count ?? raw?.gate_count), int: true },
    { key: 'circuit_depth', label: 'Depth', value: (r, raw) => _plain(r.circuit_depth ?? raw?.circuit_depth), int: true },
];

const MEMORY_COLUMNS = [
    { key: 'proc_peak_rss', label: 'Process Peak RSS (MiB)', value: (r) => _plain(r.process_peak_rss_mb), strong: true },
    { key: 'mem_delta', label: 'Sim-window RSS delta (MiB)', value: (r) => _plain(r.memory_usage_mb) },
    { key: 'proc_peak', label: 'Sim-window peak RSS (MiB)', value: (r) => _plain(r.process_peak_mb) },
    {
        key: 'theoretical_sv', label: 'Theoretical SV (MiB)',
        value: (r, raw) => _plain(r.theoretical_statevector_mb !== undefined ? r.theoretical_statevector_mb : raw?.theoretical_statevector_mb),
        nullText: 'N/A',
    },
];

/**
 * One number format for a whole column: fixed decimals chosen so the smallest non-zero value
 * shows three significant digits (1 to 8 decimals), or scientific notation with three
 * significant digits throughout when a value is below 1e-6 or at least 1e9.
 * @param {Array<number|null|undefined>} values
 * @returns {{ sci: boolean, decimals: number }}
 */
export function columnFormat(values) {
    const mags = values.filter(v => typeof v === 'number' && Number.isFinite(v) && v !== 0).map(Math.abs);
    if (!mags.length) return { sci: false, decimals: 1 };
    const lo = Math.min(...mags), hi = Math.max(...mags);
    if (lo < 1e-6 || hi >= 1e9) return { sci: true, decimals: 2 };
    return { sci: false, decimals: Math.min(8, Math.max(1, Math.ceil(-Math.log10(lo)) + 2)) };
}

/** A number in a column's format (see columnFormat); "—" when missing. */
export function fmtColumn(v, fmt) {
    if (typeof v !== 'number' || !Number.isFinite(v)) return fmtNum(v);
    return fmt.sci ? v.toExponential(fmt.decimals) : v.toFixed(fmt.decimals);
}

/** Table cell content: the value, with "± sd" (and "n=N" when backends had different numbers of timed runs) on a second line when several timed runs are behind it. */
function _fillValueCell(td, cell, column, fmt) {
    if (column.int) { td.textContent = fmtInt(cell.value); return; }
    if (cell.value === null && column.nullText) { td.textContent = column.nullText; return; }
    td.textContent = fmtColumn(cell.value, fmt);
    if (cell.n > 1) {
        const sub = document.createElement('div');
        sub.className = 'text-[10px] font-sans font-normal text-gray-400';
        const sd = cell.sd !== null && cell.sd !== undefined ? `± ${fmtColumn(cell.sd, fmt)}` : '';
        sub.textContent = fmt.showN === false ? sd : [sd, `n=${cell.n}`].filter(Boolean).join(' · ');
        td.appendChild(sub);
    }
}

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
    const okCounts = new Set((rawResults || []).filter(r => r && !r.error).map(_timingCount));
    const uniformRuns = okCounts.size === 1 ? [...okCounts][0] : 0;
    const allCpu = (rawResults || []).some(r => r && r.device) && !(rawResults || []).some(isGpuRun);

    const hFrag = _cloneTemplate('tpl-ranking-section-header');
    const note = isMemory ? _memoryNote(rawResults, unranked) : _timingNote(rawResults);
    const otherUnranked = isMemory ? unranked.filter(r => r.reason !== 'gpu_memory_not_measured') : unranked;
    const caveats = isMemory ? [] : _timingCaveats(rawResults);
    hFrag.querySelector('.tpl-summary-text').textContent = `${report.summary || ''}`
        + (caveats.length ? ` Before comparing times: ${caveats.join('; ')}.` : '')
        + (allCpu ? ' Every run was on a CPU.' : (rawResults || []).some(isGpuRun) ? ' Runs tagged GPU simulated on a GPU; the others on a CPU.' : '')
        + (!isMemory && uniformRuns > 1 ? ` Each backend had ${uniformRuns} timed runs; ± is their standard deviation.` : '')
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
    columns.forEach(c => hr.appendChild(_th(c.label, c.key)));
    thead.appendChild(hr);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    tbody.className = 'bg-white divide-y divide-gray-200';

    /** @type {Map<any, any[]>} */
    const cells = new Map();
    const cellOf = (r, idx) => {
        if (!cells.has(r)) cells.set(r, columns.map(col => col.value(r, raws.get(r.simulator))));
        return cells.get(r)[idx];
    };
    const shown = [...ranked, ...unranked.filter(r => _statusOf(r, raws.get(r.simulator)) === 'ok')];
    const runCounts = new Set(shown.map(r => _timingCount(raws.get(r.simulator))));
    const showN = runCounts.size > 1;
    const formats = columns.map((_, idx) => ({ ...columnFormat(shown.map(r => cellOf(r, idx).value)), showN }));

    ranked.forEach((r, i) => {
        const raw = raws.get(r.simulator);
        const tr = document.createElement('tr');
        const rankTd = document.createElement('td');
        rankTd.className = 'px-2 py-2 text-sm text-gray-500 whitespace-nowrap align-top';
        rankTd.textContent = String(r.rank ?? i + 1);
        if (r.overlaps_next === true && ranked[i + 1]) {
            rankTd.appendChild(_tag('≈', `${TAG_AMBER} !ml-0.5`, `Overlaps rank ${i + 2} (${_displayRunnerName(ranked[i + 1].simulator)}): `
                + 'this backend\'s slowest timed run took at least as long as that backend\'s fastest, so these runs do not separate the two. '
                + 'It reflects the spread within this job only: medians also move between jobs (about 3% on this host), so ranks without ≈ can still swap.'));
        }
        tr.appendChild(rankTd);
        const simTd = document.createElement('td');
        simTd.className = 'px-2 py-2 text-sm font-medium text-gray-900 min-w-[8rem] align-top';
        _fillSimulatorCell(simTd, r.simulator, config, raw, { memory: isMemory });
        tr.appendChild(simTd);
        columns.forEach((c, idx) => {
            const td = document.createElement('td');
            td.className = c.strong ? `${TD_CLASS} text-gray-900 font-medium` : TD_CLASS;
            _fillValueCell(td, cellOf(r, idx), c, formats[idx]);
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
        rankTd.className = 'px-2 py-2 text-xs text-gray-400 align-top';
        rankTd.textContent = 'not ranked';
        tr.appendChild(rankTd);
        const simTd = document.createElement('td');
        simTd.className = 'px-2 py-2 text-sm font-medium text-gray-900 min-w-[8rem] align-top';
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
                        userFacingError(r.error || raw?.error) || undefined));
                } else {
                    td.textContent = '—';
                }
            } else {
                _fillValueCell(td, cellOf(r, idx), c, formats[idx]);
            }
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });

    table.appendChild(tbody);
    wrap.appendChild(table);
    panel.appendChild(wrap);
}
