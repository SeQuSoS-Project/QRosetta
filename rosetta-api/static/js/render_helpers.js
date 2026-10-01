// DOM and number-format helpers shared by the report renderers: template cloning,
// status styles, metric tooltips, the optimization-level badge and number formatting.

import { RUNNER_DISPLAY_NAMES, getRunnerOptInfo } from './config.js';
import { formatRunnerLabel, parseRunnerKey } from './runner_key.js';

export const METRIC_DEFINITIONS = {
    "compilation": "<b>Compilation Time:</b> Wall clock from t0 to t1 of a timed run: parse the QASM, apply this backend's transforms and build its native circuit (Qulacs, QuEST, qsim and Qiskit Aer convert the circuit into their own form inside the simulation call instead; see the manual). After one discarded warm-up run; with Timing repeats above 1, the median of the timed runs, with their spread and n.",
    "simulation": "<b>Simulation Time:</b> Wall clock from t2 to t3 of a timed run: execute the circuit and return the statevector or draw the shots. Building the counts histogram from drawn shots is outside this window. After one discarded warm-up run; with Timing repeats above 1, the median of the timed runs, with their spread and n.",
    "total_time": "<b>Total:</b> Compilation + Simulation. With Timing repeats above 1, median compilation + median simulation, ± the standard deviation of the per-run totals. Backends are ranked by this column.",
    "cpu_time": "<b>CPU Time:</b> User+system CPU time of the whole isolated runner process: interpreter start, SDK import, warm-up and every timed run, so it grows with Timing repeats. It covers more than the wall-clock columns.",
    "sim_cpu_time": "<b>Simulation CPU:</b> Process CPU time (all threads) from t2 to t3; with Timing repeats above 1, the median of the timed runs. Every runner is started with OMP_NUM_THREADS, MKL_NUM_THREADS, OPENBLAS_NUM_THREADS, NUMEXPR_NUM_THREADS and NUMBA_NUM_THREADS set to 1 (see thread_env in the raw JSON).",
    "gate_count": "<b>Gate Count:</b> Number of gate statements in the circuit this backend executed (its transpiled_qasm).",
    "circuit_depth": "<b>Depth:</b> Greedy-layering depth of the circuit this backend executed (its transpiled_qasm).",
    "proc_peak_rss": "<b>Process Peak RSS:</b> Peak RSS of the simulating process over its whole life: interpreter start, SDK import, warm-up and every timed run. Kernel high-water mark (VmHWM); a getrusage badge marks the ru_maxrss fallback. Resources are ranked by this column.",
    "mem_delta": "<b>Mem Delta:</b> Peak RSS minus baseline RSS during the simulation window (pre-execute setup plus t2..t3 of the first timed run). Memory the warm-up freed but the process kept can be reused, so a state smaller than the SDK's cached memory can read near 0. Kernel high-water mark (VmHWM, reset when the window opens); a sampled badge marks 10 ms RSS polling, which can miss short peaks.",
    "proc_peak": "<b>Window Peak:</b> Absolute peak RSS during the simulation window of the first timed run, measured the same way as Mem Delta.",
    "theoretical_sv": "<b>Theoretical SV:</b> Size of a dense statevector for the declared qubits: 2^N × 16 bytes for complex128 backends, 2^N × 8 bytes for complex64 backends. quimb (tensor network) holds no dense statevector; its value is computed the same way from the precision it reports, for comparison.",
    "fidelity_matrix": "<b>Fidelity Matrix:</b> |⟨ψi|ψj⟩|² between the normalised statevectors, unrounded. Green when F ≥ 1 − the fidelity tolerance recorded with the pair. A value other than 1 is printed with enough decimals to differ from 1.",
    "relative_phase_matrix": "<b>Global phase offset arg⟨a|b⟩:</b> arg⟨ψi|ψj⟩ in radians. Green when |phase| ≤ the phase tolerance recorded with the pair. A non-zero value with fidelity at 1 means the two states differ only by a global phase.",
    "statistical_distance_matrix (js_divergence)": "<b>JS Divergence:</b> Jensen–Shannon divergence between the two count distributions, each normalised by its observed total, in nats (maximum ln 2 ≈ 0.693). Green when ≤ the JS threshold recorded with the pair.",
    "hellinger_distance_matrix": "<b>Hellinger Distance:</b> Hellinger distance between the two normalised count distributions (0 to 1). Green when ≤ the Hellinger threshold recorded with the pair.",
    "pairwise_agreement": "<b>Explained-Cause Agreement:</b> Each statevector pair is compared in the basis its declared qubit orderings imply. Agreement: agree_directly, agree_up_to_global_phase, agree_after_bit_reversal (the reversal the declared orderings imply). Disagreement: residual_disagreement, agree_after_qubit_permutation (agrees only after an undeclared qubit permutation, searched up to 7 qubits), and pairs that match only in the basis the declared orderings do not imply. Measured pairs are judged by their shot-noise assessment; their distance label is descriptive. agree_after_normalization marks an agreeing pair whose input norm differed from 1 by more than the norm tolerance. not_comparable pairs carry a reason.",
    "statistical_test": "<b>Shot-Noise Test:</b> Pearson chi-square (no continuity correction) and G-test of homogeneity on the counts, in the basis chosen from the declared orderings, with Benjamini–Yekutieli correction across all pairs, effect size and power at α/(m·c_m).",
    "execution_time_sec": "<b>Execution Time:</b> Compilation + Simulation (medians when Timing repeats is above 1).",
    "memory_usage_mb": "<b>Memory:</b> Peak RSS minus baseline RSS during the simulation window."
};

export const STATUS_STYLES = {
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
    error: {
        badge: "bg-orange-100 text-orange-800 border-orange-300",
        cell: "bg-orange-50 text-orange-900 font-bold",
        legendDot: "bg-orange-100 border-orange-300"
    },
    timeout: {
        badge: "bg-purple-100 text-purple-800 border-purple-300",
        cell: "bg-purple-50 text-purple-900 font-bold",
        legendDot: "bg-purple-100 border-purple-300"
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

export function _cloneTemplate(id) {
    const tpl = document.getElementById(id);
    if (!tpl) throw new Error(`Missing <template id="${id}">`);
    return tpl.content.cloneNode(true);
}

export function _applyLegendDots(fragment) {
    const dotMap = {
        'tpl-dot-success': STATUS_STYLES.success.legendDot,
        'tpl-dot-divergence': STATUS_STYLES.divergence.legendDot,
        'tpl-dot-offline': STATUS_STYLES.offline.legendDot,
        'tpl-dot-anomaly': STATUS_STYLES.anomaly.legendDot,
        'tpl-dot-error': STATUS_STYLES.error.legendDot,
        'tpl-dot-timeout': STATUS_STYLES.timeout.legendDot,
    };
    for (const [placeholder, classes] of Object.entries(dotMap)) {
        fragment.querySelectorAll(`.${placeholder}`).forEach(el => {
            el.classList.remove(placeholder);
            classes.split(' ').forEach(c => el.classList.add(c));
        });
    }
}

export function renderTooltip(key, label) {
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

export function getOptBadge(simulator, config) {
    const parsed = parseRunnerKey(simulator);

    let optLevel;
    if (parsed.isMulti) {
        optLevel = parsed.optLevel;
    } else {
        let cv = config[simulator];
        if (Array.isArray(cv)) cv = cv.length ? cv[0] : 0;
        optLevel = cv !== undefined ? cv : 0;
    }

    if (optLevel > 0) {
        const frag = _cloneTemplate('tpl-opt-badge');
        const span = frag.querySelector('span');
        span.textContent = `L${optLevel}`;

        const runnerInfo = getRunnerOptInfo(parsed.simId);
        const desc = runnerInfo.optimization_levels?.[String(optLevel)];
        span.title = desc
            ? `Optimization Level ${optLevel}: ${desc}`
            : `Optimization Level ${optLevel}`;
        return span;
    }
    return null;
}

export function _makeStatusBadge(styleKey, label) {
    const frag = _cloneTemplate('tpl-status-badge');
    const span = frag.querySelector('span');
    STATUS_STYLES[styleKey].badge.split(' ').forEach(c => span.classList.add(c));
    span.textContent = label;
    return span;
}

function _sci(x) {
    const [mant, exp] = x.toExponential(2).split('e');
    const e = parseInt(exp, 10);
    return `${mant}e${e < 0 ? '-' : '+'}${String(Math.abs(e)).padStart(2, '0')}`;
}

/**
 * A real-valued metric for display, with the rules of the publication tables: 0 prints as
 * d zeros; 0 < |v| < 1e-3, |v| >= 1e15, or a value that would print as zero uses
 * scientific notation with 3 significant digits; a value other than 1 that would print
 * as 1 gets more decimals (up to 17) until it does not.
 */
export function fmtNum(v, d = 4) {
    if (v === null || v === undefined) return '—';
    if (typeof v === 'boolean') return v ? 'true' : 'false';
    if (typeof v !== 'number') return String(v);
    if (Number.isNaN(v)) return '—';
    if (!Number.isFinite(v)) return v > 0 ? 'inf' : '-inf';
    if (v === 0) return (0).toFixed(d);
    if (Math.abs(v) < 1e-3 || Math.abs(v) >= 1e15) return _sci(v);
    let s = v.toFixed(d);
    if (parseFloat(s) === 0) return _sci(v);
    let digits = d;
    while (v !== 1 && parseFloat(s) === 1 && digits < 17) {
        digits += 1;
        s = v.toFixed(digits);
    }
    return s;
}

/** A p-value: fmtNum, with an underflowed 0 shown as below the smallest double. */
export function fmtPValue(v) {
    if (v === 0) return '<1e-300';
    return fmtNum(v);
}

/** A probability such as test power: 3 decimals, with values that would round to 1 or 0 shown as bounds. */
export function fmtProb(v) {
    if (typeof v !== 'number' || !Number.isFinite(v)) return fmtNum(v);
    if (v >= 0.9995) return '> 0.999';
    if (v <= 0.0005) return '< 0.001';
    return v.toFixed(3);
}

/** A count-like value (gate count, depth, shots, seed): integers without decimals. */
export function fmtInt(v) {
    if (typeof v === 'number' && Number.isInteger(v) && Math.abs(v) < 1e15) return String(v);
    return fmtNum(v);
}

export function _displayRunnerName(key) {
    return formatRunnerLabel(key, RUNNER_DISPLAY_NAMES);
}

export function _makeStatusCell(styleKey, text, title) {
    const span = document.createElement('span');
    STATUS_STYLES[styleKey].cell.split(' ').forEach(c => span.classList.add(c));
    span.textContent = text;
    if (title) span.title = title;
    return span;
}

export function _chip(badgeClasses, text, title) {
    const span = document.createElement('span');
    span.className = 'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border';
    badgeClasses.split(' ').forEach(c => span.classList.add(c));
    span.textContent = text;
    if (title) span.title = title;
    return span;
}

/** A small inline tag, e.g. a precision or sampling-method badge next to a runner name. */
export function _tag(text, colorClasses, title) {
    const span = document.createElement('span');
    span.className = `ml-1 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border ${colorClasses}`;
    span.textContent = text;
    if (title) span.title = title;
    return span;
}

export const TAG_GRAY = 'bg-gray-100 text-gray-600 border-gray-200';
export const TAG_AMBER = 'bg-amber-100 text-amber-800 border-amber-300';

/** A backend's precision tag; complex64 is highlighted. */
export function precisionTag(precision) {
    if (!precision) return null;
    return _tag(precision, precision === 'complex64' ? TAG_AMBER : TAG_GRAY,
        `Amplitude precision the backend simulated in: ${precision}`);
}

/** True when the run reports that it simulated on a GPU. */
export function isGpuRun(r) {
    return String(r?.device ?? '').toUpperCase() === 'GPU';
}

/** Tooltip for a run's device tag: the device, and for a GPU run its name and whether cuStateVec was on. */
export function deviceTitle(r) {
    if (!isGpuRun(r)) return `Device the simulation ran on: ${r?.device}`;
    const parts = [`Simulated on a GPU${r.gpu_name ? `: ${r.gpu_name}` : ''}.`];
    if (typeof r.custatevec_enabled === 'boolean') parts.push(`cuStateVec ${r.custatevec_enabled ? 'enabled' : 'not enabled'}.`);
    parts.push('Host-side work runs under the same CPU quota as the CPU runners; GPU device memory is not measured.');
    return parts.join(' ');
}

/**
 * Device / simulator-backend / simulation-method tags a runner reported, e.g. CPU · qiskit-aer · statevector.
 * @param {any} r
 * @param {{ device?: boolean }} [opts] device: false omits the device tag (for tables with a Device column)
 */
export function executionTags(r, { device = true } = {}) {
    const tags = [];
    if (!r) return tags;
    if (r.device && device) {
        tags.push(_tag(String(r.device), isGpuRun(r) ? TAG_AMBER : TAG_GRAY, deviceTitle(r)));
    }
    if (isGpuRun(r) && r.custatevec_enabled === true) {
        tags.push(_tag('cuStateVec', TAG_AMBER, deviceTitle(r)));
    }
    if (r.simulator_backend) {
        tags.push(_tag(String(r.simulator_backend), TAG_GRAY, `Simulator library that executed the circuit: ${r.simulator_backend}`));
    }
    if (r.simulation_method) {
        tags.push(_tag(String(r.simulation_method), TAG_GRAY, `Simulation method: ${r.simulation_method}`));
    }
    return tags;
}

/** Smallest share of the simulation window held by the CPU quota that the UI tags. */
export const THROTTLE_SHOWN_SHARE = 0.01;

/** Time the CPU quota held a run during its simulation window, as a note, or null when under THROTTLE_SHOWN_SHARE of the window. */
export function throttleText(r) {
    const t = r?.simulation_throttled_sec;
    if (typeof t !== 'number' || !(t > 0)) return null;
    const sim = r?.simulation_time_sec;
    if (typeof sim === 'number' && sim > 0 && t < THROTTLE_SHOWN_SHARE * sim) return null;
    const share = typeof sim === 'number' && sim > 0 ? ` (${fmtNum(100 * t / sim, 0)}% of the simulation window)` : '';
    return `the CPU quota held this runner for ${fmtNum(t, 4)} s${share}; that wait is part of simulation_time_sec`;
}

/** Smallest gap between container and process CPU time over the simulation window that the UI reports. */
export const OUTSIDE_PROCESS_SHOWN_SEC = 0.005;

/** Note for a run whose container used more CPU than its simulating process during the window, or null. */
export function outsideProcessText(r) {
    const cg = r?.simulation_cgroup_cpu_time_sec;
    const own = r?.simulation_cpu_time_sec;
    if (typeof cg !== 'number' || typeof own !== 'number') return null;
    const gap = cg - own;
    if (!(gap >= OUTSIDE_PROCESS_SHOWN_SEC && gap >= 0.1 * cg)) return null;
    return `the runner container used ${fmtNum(cg, 4)} s of CPU during the simulation window, `
        + `the simulating process ${fmtNum(own, 4)} s: ${fmtNum(gap, 4)} s of work ran outside the measured process, `
        + 'so its CPU time and memory fields leave that work out';
}

/** Distinct maximum frequencies (MHz) of the CPUs a run's simulation windows were on, ascending. */
export function simulationCoreSpeeds(r) {
    const mhz = r?.cpu_environment?.cpu_max_mhz || {};
    const speeds = new Set((Array.isArray(r?.simulation_cpus) ? r.simulation_cpus : [])
        .map(c => mhz[c]).filter(v => typeof v === 'number'));
    return [...speeds].sort((a, b) => a - b);
}

/** Maximum frequencies grouped into core classes: a class starts where a frequency exceeds the previous one by more than 10%. */
export function coreClasses(speeds) {
    const classes = [];
    [...speeds].sort((a, b) => a - b).forEach(s => {
        const last = classes[classes.length - 1];
        if (last && s <= last[last.length - 1] * 1.1) last.push(s);
        else classes.push([s]);
    });
    return classes;
}

/** Note for a run whose timed runs were on CPUs of different core classes (see coreClasses), or null. */
export function mixedCoresText(r) {
    const classes = coreClasses(simulationCoreSpeeds(r));
    if (classes.length < 2) return null;
    return `its timed runs were on CPUs of different speed classes (maximum ${classes.map(c => c.map(s => `${fmtInt(s)}`).join('/') + ' MHz').join(' vs ')}), `
        + 'so its samples mix faster and slower cores; simulation_cpus_samples in the raw JSON gives the CPUs of each run';
}

/** Ratio of the slowest to the fastest simulation sample above which the UI marks a run's repeats as unstable. */
export const UNSTABLE_SPREAD = 1.3;

/** Note for a run with three or more timed runs whose simulation times spread by more than UNSTABLE_SPREAD, or null. */
export function unstableText(r) {
    const s = Array.isArray(r?.simulation_time_samples) ? r.simulation_time_samples.filter(v => typeof v === 'number') : [];
    if (s.length < 3) return null;
    const lo = Math.min(...s), hi = Math.max(...s);
    if (!(lo > 0) || hi / lo <= UNSTABLE_SPREAD) return null;
    return `its timed runs ranged from ${fmtNum(lo, 4)} to ${fmtNum(hi, 4)} s (${fmtNum(hi / lo, 2)}×), so something else on the host `
        + 'probably competed with some of them; the median is less reliable than its n suggests';
}

/** The distinct CPU quotas (cores) reported by the runs, as a readable phrase, or null when none reported one. */
export function cpuQuotaPhrase(results) {
    const quotas = new Set();
    let unlimited = false;
    (results || []).forEach(r => {
        const env = r?.cpu_environment;
        if (!env || !('cpu_quota_cores' in env)) return;
        if (typeof env.cpu_quota_cores === 'number') quotas.add(env.cpu_quota_cores);
        else unlimited = true;
    });
    const parts = [...quotas].sort((a, b) => a - b).map(q => `${fmtNum(q, 2)} CPU`);
    if (unlimited) parts.push('no CPU quota');
    return parts.length ? parts.join(' / ') : null;
}

/** Shortest queue wait the UI reports; shorter waits are dispatch overhead. */
export const QUEUE_WAIT_SHOWN_SEC = 0.5;

/** Queue-wait note for a run that waited for its runner, or null. */
export function queueWaitText(r) {
    const w = r?.queue_wait_sec;
    if (typeof w !== 'number' || !(w >= QUEUE_WAIT_SHOWN_SEC)) return null;
    return `waited ${fmtNum(w, 1)} s for the runner to finish another run; not included in timings`;
}

/**
 * A preprocessing_applied list. Entries starting "API:" were applied by the API before
 * dispatch and are tagged API; the rest were applied by the runner.
 */
export function renderPreprocessingList(entries) {
    const ul = document.createElement('ul');
    ul.className = 'list-none space-y-0.5';
    const list = Array.isArray(entries) ? entries : [];
    if (list.length === 0) {
        const li = document.createElement('li');
        li.className = 'text-gray-400';
        li.textContent = 'none recorded';
        ul.appendChild(li);
        return ul;
    }
    list.forEach(entry => {
        const text = String(entry);
        const isApi = text.startsWith('API:');
        const li = document.createElement('li');
        li.className = 'break-words';
        const tag = document.createElement('span');
        tag.className = `mr-1 inline-flex items-center px-1 rounded text-[10px] font-semibold border ${isApi ? 'bg-blue-100 text-blue-800 border-blue-300' : TAG_GRAY}`;
        tag.textContent = isApi ? 'API' : 'runner';
        tag.title = isApi ? 'Applied by the API before dispatch' : 'Applied by the runner';
        li.appendChild(tag);
        li.appendChild(document.createTextNode(isApi ? text.slice(4).trim() : text));
        ul.appendChild(li);
    });
    return ul;
}
