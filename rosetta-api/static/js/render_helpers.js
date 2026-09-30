// DOM and number-format helpers shared by the report renderers: template cloning,
// status styles, metric tooltips, the optimization-level badge and number formatting.

import { RUNNER_DISPLAY_NAMES, getRunnerOptInfo } from './config.js';
import { formatRunnerLabel, parseRunnerKey } from './runner_key.js';

export const METRIC_DEFINITIONS = {
    "compilation": "<b>Compilation Time:</b> Wall clock from t0 to t1 of the timed run: parse the QASM, apply this backend's transforms and build its native circuit. One timed run (n=1), after one discarded warm-up run.",
    "simulation": "<b>Simulation Time:</b> Wall clock from t2 to t3 of the timed run: execute the circuit and return the statevector or draw the shots. Building the counts histogram from drawn shots is outside this window. One timed run (n=1), after one discarded warm-up run.",
    "total_time": "<b>Total:</b> Compilation + Simulation of the same timed run (n=1). Backends are ranked by this column.",
    "cpu_time": "<b>CPU Time:</b> User+system CPU time of the whole isolated runner process: interpreter start, SDK import, warm-up and the timed run. It covers more than the wall-clock columns.",
    "sim_cpu_time": "<b>Simulation CPU:</b> Process CPU time (all threads) from t2 to t3 of the timed run only. Every runner is started with OMP/MKL/OpenBLAS/NumExpr thread counts set to 1 (see thread_env in the raw JSON).",
    "gate_count": "<b>Gate Count:</b> Number of gate statements in the circuit this backend executed (its transpiled_qasm).",
    "circuit_depth": "<b>Depth:</b> Greedy-layering depth of the circuit this backend executed (its transpiled_qasm).",
    "proc_peak_rss": "<b>Process Peak RSS:</b> Peak RSS of the simulating process over its whole life: interpreter start, SDK import, warm-up and the timed run. Kernel high-water mark (VmHWM); a getrusage badge marks the ru_maxrss fallback. Resources are ranked by this column.",
    "mem_delta": "<b>Mem Delta:</b> Peak RSS minus baseline RSS during the simulation window (pre-execute setup plus t2..t3 of the timed run). Kernel high-water mark (VmHWM, reset when the window opens); a sampled badge marks 10 ms RSS polling, which can miss short peaks.",
    "proc_peak": "<b>Window Peak:</b> Absolute peak RSS during the simulation window of the timed run, measured the same way as Mem Delta.",
    "theoretical_sv": "<b>Theoretical SV:</b> 2^N × 16 bytes, a dense complex128 statevector for the declared qubits (complex64 needs half). N/A for tensor-network backends (quimb).",
    "fidelity_matrix": "<b>Fidelity Matrix:</b> |⟨ψi|ψj⟩|² between the normalised statevectors, unrounded. Green when F ≥ 1 − the fidelity tolerance recorded with the pair. A value other than 1 is printed with enough decimals to differ from 1.",
    "relative_phase_matrix": "<b>Global phase offset arg⟨a|b⟩:</b> arg⟨ψi|ψj⟩ in radians. Green when |phase| ≤ the phase tolerance recorded with the pair. A non-zero value with fidelity at 1 means the two states differ only by a global phase.",
    "statistical_distance_matrix (js_divergence)": "<b>JS Divergence:</b> Jensen–Shannon divergence between the two count distributions, each normalised by its observed total, in nats (maximum ln 2 ≈ 0.693). Green when ≤ the JS threshold recorded with the pair.",
    "hellinger_distance_matrix": "<b>Hellinger Distance:</b> Hellinger distance between the two normalised count distributions (0 to 1). Green when ≤ the Hellinger threshold recorded with the pair.",
    "pairwise_agreement": "<b>Explained-Cause Agreement:</b> Each backend pair gets the first registered transform under which it agrees: direct → global phase → bit reversal → qubit permutation (up to 7 qubits). Otherwise residual_disagreement (statevector) or distance_exceeds_threshold (measured). agree_after_normalization marks an agreeing pair whose input norm differed from 1 by more than the norm tolerance. not_comparable pairs carry a reason.",
    "statistical_test": "<b>Shot-Noise Test:</b> Pearson chi-square (no continuity correction) and G-test of homogeneity on the counts, on the transform basis the label selected, with Benjamini–Hochberg correction across all pairs, effect size and power.",
    "execution_time_sec": "<b>Execution Time:</b> Compilation + Simulation of the timed run (n=1).",
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

/** Device / simulator-backend / simulation-method tags a runner reported, e.g. CPU · qiskit-aer · statevector. */
export function executionTags(r) {
    const tags = [];
    if (!r) return tags;
    if (r.device) {
        tags.push(_tag(String(r.device), String(r.device).toUpperCase() === 'GPU' ? TAG_AMBER : TAG_GRAY,
            `Device the simulation ran on: ${r.device}`));
    }
    if (r.simulator_backend) {
        tags.push(_tag(String(r.simulator_backend), TAG_GRAY, `Simulator library that executed the circuit: ${r.simulator_backend}`));
    }
    if (r.simulation_method) {
        tags.push(_tag(String(r.simulation_method), TAG_GRAY, `Simulation method: ${r.simulation_method}`));
    }
    return tags;
}

/** Queue-wait note for a run that waited for its runner, or null. */
export function queueWaitText(r) {
    const w = r?.queue_wait_sec;
    if (typeof w !== 'number' || !(w >= 0.5)) return null;
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
