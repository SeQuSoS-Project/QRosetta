// DOM and number-format helpers shared by the report renderers: template cloning,
// status styles, metric tooltips, the optimization-level badge and number formatting.

import { RUNNER_DISPLAY_NAMES, getRunnerOptInfo } from './config.js';
import { formatRunnerLabel, parseRunnerKey } from './runner_key.js';
import { setTip } from './tooltip.js';

export const METRIC_DEFINITIONS = {
    "compilation": "<b>Compilation Time:</b> t0 to t1: parse, apply this backend's transforms and build its native circuit; for Qulacs, QuEST, qsim, Qiskit and cuQuantum also the conversion to the simulator's own form. Median over timed runs, after one warm-up.",
    "simulation": "<b>Simulation Time:</b> t2 to t3: execute and return the statevector or draw the shots; tallying counts is outside. Median over timed runs, after one warm-up.",
    "total_time": "<b>Total:</b> Compilation + simulation (medians), ± standard deviation of the per-run totals. Ranking column.",
    "cpu_time": "<b>CPU Time:</b> User + system CPU of the whole runner process, including start-up, SDK import and warm-up.",
    "sim_cpu_time": "<b>Simulation CPU:</b> Process CPU time (all threads) from t2 to t3, median over timed runs. Runners run with one BLAS/OpenMP thread.",
    "gate_count": "<b>Gate Count:</b> Gate statements in the executed circuit (transpiled_qasm).",
    "circuit_depth": "<b>Depth:</b> Greedy-layering depth of the executed circuit (transpiled_qasm).",
    "executed_gate_count": "<b>Gates:</b> The runner's gate_count for the executed circuit; its basis (text or executed tape) is in the pane's note.",
    "executed_depth": "<b>Depth:</b> The runner's circuit_depth, counted like Gates.",
    "text_gate_count": "<b>Gates:</b> Top-level gate statements in this text, as for compiled circuits; barriers, measurements and resets not counted, register-wide statements once per index.",
    "text_depth": "<b>Depth:</b> Greedy-layering depth of this text, one layer per gate statement; barriers not counted.",
    "compiled_gate_count": "<b>Gates:</b> Top-level gate statements in the compiled text. Compilers use different gate sets, so this count is not comparable across compilers.",
    "compiled_multi_qubit_gate_count": "<b>On 2+ qubits:</b> Gate statements acting on two or more qubits. Comparable across compilers that use the same multi-qubit gates.",
    "compiled_depth": "<b>Depth:</b> Greedy-layering depth of the compiled text, one layer per gate statement; barriers not counted.",
    "proc_peak_rss": "<b>Process Peak RSS:</b> Lifetime peak RSS of the simulating process (VmHWM), including SDK import and warm-up. Ranking column.",
    "mem_delta": "<b>Mem Delta:</b> Peak minus baseline RSS during the simulation window (VmHWM). Can read near 0 when the warm-up's freed memory is reused.",
    "proc_peak": "<b>Window Peak:</b> Absolute peak RSS during the simulation window.",
    "theoretical_sv": "<b>Theoretical SV:</b> Dense statevector size for the declared qubits: 2^N × 16 bytes (complex128) or × 8 bytes (complex64).",
    "fidelity_matrix": "<b>Fidelity Matrix:</b> |⟨ψi|ψj⟩|² of the normalised statevectors. Green when F ≥ 1 − fidelity tolerance.",
    "relative_phase_matrix": "<b>Global phase offset arg⟨a|b⟩:</b> arg⟨ψi|ψj⟩ in radians. Green when within the phase tolerance.",
    "statistical_distance_matrix (js_divergence)": "<b>JS Divergence:</b> Jensen–Shannon divergence of the count distributions, in nats (maximum ln 2). Green when within the JS threshold.",
    "hellinger_distance_matrix": "<b>Hellinger Distance:</b> Hellinger distance of the count distributions (0 to 1). Green when within the Hellinger threshold.",
    "pairwise_agreement": "<b>Explained-Cause Agreement:</b> Statevector pairs agree directly, up to a global phase or after the declared bit reversal; anything else is a disagreement. Measured pairs are judged by the shot-noise test.",
    "statistical_test": "<b>Shot-Noise Test:</b> Chi-square and G-test of homogeneity per pair, Benjamini–Yekutieli corrected, with effect size and power.",
    "execution_time_sec": "<b>Execution Time:</b> Compilation + simulation (medians).",
    "memory_usage_mb": "<b>Memory:</b> Peak minus baseline RSS during the simulation window."
};

export const STATUS_STYLES = {
    success: {
        badge: "bg-green-100 text-green-800 border-green-300",
        cell: "bg-green-50 text-gray-900",
        legendDot: "bg-green-100 border-green-300"
    },
    explained: {
        badge: "bg-blue-100 text-blue-800 border-blue-300",
        cell: "bg-blue-50 text-gray-900",
        legendDot: "bg-blue-100 border-blue-300"
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
        cell: "bg-gray-100 text-gray-600 italic",
        legendDot: "bg-gray-100 border-gray-300"
    },
    inconclusive: {
        badge: "bg-sky-50 text-sky-800 border-sky-300",
        cell: "bg-sky-50 text-gray-900",
        legendDot: "bg-sky-50 border-sky-300"
    },
    neutral: {
        cell: "bg-white text-gray-900"
    }
};

/** A new element with `className` and, when given, text. */
export function makeEl(tag, className = '', text = undefined) {
    const e = document.createElement(tag);
    if (className) e.className = className;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
}

/** A type="button" button: an optional trusted icon SVG followed by its label. */
export function makeButton(className, label, icon = '') {
    const b = makeEl('button', className);
    b.type = 'button';
    b.innerHTML = icon;
    if (label) b.append(document.createTextNode(label));
    return b;
}

export function _cloneTemplate(id) {
    const tpl = document.getElementById(id);
    if (!tpl) throw new Error(`Missing <template id="${id}">`);
    return tpl.content.cloneNode(true);
}

export function _applyLegendDots(fragment) {
    const dotMap = {
        'tpl-dot-success': STATUS_STYLES.success.legendDot,
        'tpl-dot-divergence': STATUS_STYLES.divergence.legendDot,
        'tpl-dot-explained': STATUS_STYLES.explained.legendDot,
        'tpl-dot-offline': STATUS_STYLES.offline.legendDot,
        'tpl-dot-anomaly': STATUS_STYLES.anomaly.legendDot,
        'tpl-dot-error': STATUS_STYLES.error.legendDot,
        'tpl-dot-timeout': STATUS_STYLES.timeout.legendDot,
        'tpl-dot-inconclusive': STATUS_STYLES.inconclusive.legendDot,
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
        span.textContent = label;
        return setTip(span, plainText);
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
    if (title) setTip(span, title);
    return span;
}

export function _chip(badgeClasses, text, title) {
    const span = document.createElement('span');
    span.className = 'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border';
    badgeClasses.split(' ').forEach(c => span.classList.add(c));
    span.textContent = text;
    if (title) setTip(span, title);
    return span;
}

/** A small inline tag, e.g. a precision or sampling-method badge next to a runner name. */
export function _tag(text, colorClasses, title) {
    const span = document.createElement('span');
    span.className = `ml-1 inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium border ${colorClasses}`;
    span.textContent = text;
    if (title) setTip(span, title);
    return span;
}

// Tag colours describe a run; none of them reuses a status colour (green agree, blue agreement
// after the declared bit reversal, red disagree, orange error, purple timeout). Gray: a plain fact. Amber: a condition
// worth checking. Each fact with a few values has its own hue, and its values differ by fill:
// sky for bit order, slate for the sampling method.
export const TAG_GRAY = 'bg-gray-100 text-gray-600 border-gray-200';
export const TAG_AMBER = 'bg-amber-100 text-amber-800 border-amber-300';

const BIT_ORDER_TAGS = {
    lsb: { label: 'LSB', color: 'bg-sky-100 text-sky-800 border-sky-300',
           title: 'LSB: qubit 0 is the rightmost bit (Qiskit\'s order). Compared with MSB backends after bit reversal.' },
    msb: { label: 'MSB', color: 'bg-white text-sky-800 border-sky-300',
           title: 'MSB: qubit 0 is the leftmost bit. Compared with LSB backends after bit reversal.' },
};

const SAMPLING_TAGS = {
    native: { label: 'Native', color: 'bg-white text-slate-700 border-slate-400', title: 'The backend sampled the shots itself.' },
    sv_sample: { label: 'SV-Sample', color: 'bg-slate-200 text-slate-800 border-slate-400', title: 'Shots drawn from the computed statevector (multinomial).' },
    tn_sample: { label: 'TN-Sample', color: 'bg-slate-600 text-white border-slate-600', title: 'Shots sampled from tensor-network amplitudes.' },
};

/** The bit order a backend declares, LSB and MSB told apart by colour. */
export function bitOrderTag(order) {
    if (!order) return null;
    const cfg = BIT_ORDER_TAGS[String(order).toLowerCase()];
    return cfg ? _tag(cfg.label, cfg.color, cfg.title) : _tag(String(order), TAG_GRAY, 'Qubit ordering declared by the runner');
}

/** How a measured run's shots were drawn. */
export function samplingTag(method) {
    if (!method) return null;
    const cfg = SAMPLING_TAGS[method];
    return cfg ? _tag(cfg.label, cfg.color, `Sampling method: ${cfg.title}`) : _tag(String(method), TAG_GRAY, 'Sampling method');
}

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
    parts.push('Host-side work under the CPU quota; GPU memory not measured.');
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
    if (r.simulator_backend || r.simulation_method) {
        const library = r.simulator_backend ? String(r.simulator_backend).split(/[\s(]/)[0] : '';
        const text = [library, r.simulation_method].filter(Boolean).join(' · ');
        const title = [r.simulator_backend && `Simulator library that executed the circuit: ${r.simulator_backend}.`,
            r.simulation_method && `Simulation method: ${r.simulation_method}.`].filter(Boolean).join(' ');
        tags.push(_tag(text, TAG_GRAY, title));
    }
    return tags;
}

const _derivedCaveats = new WeakMap();

/** Records the timing caveats POST /timing-caveats derived for results stored without them:
 * each result's list, and the report-level list under the results array itself. */
export function registerTimingCaveats(rawResults, derived) {
    if (!Array.isArray(rawResults)) return;
    rawResults.forEach((r, i) => {
        if (r && typeof r === 'object') _derivedCaveats.set(r, derived?.results?.[i] || []);
    });
    _derivedCaveats.set(rawResults, Array.isArray(derived?.report) ? derived.report : []);
}

/** The server's timing caveats of one result: its recorded list, else the derived one, else null. */
export function timingCaveatsOf(r) {
    if (!r || typeof r !== 'object') return null;
    if (Array.isArray(r.timing_caveats)) return r.timing_caveats;
    return _derivedCaveats.get(r) ?? null;
}

/** The server's report-level timing caveats: the report's own list, else the one derived for its results, else null. */
export function reportTimingCaveats(report) {
    if (Array.isArray(report?.timing_caveats)) return report.timing_caveats;
    return _derivedCaveats.get(report?.raw_results) ?? null;
}

/** True when some result of `rawResults` has no recorded or derived timing caveats. */
export function needsTimingCaveats(rawResults) {
    return Array.isArray(rawResults) && rawResults.some(r => r && typeof r === 'object' && timingCaveatsOf(r) === null);
}

/** The server's caveat `code` on result `r`, or null. */
export function timingCaveat(r, code) {
    return (timingCaveatsOf(r) || []).find(c => c && c.code === code) || null;
}

/** Note for a run the server tagged throttled (CPU quota held it during the simulation window), or null. */
export function throttleText(r) {
    if (!timingCaveat(r, 'throttled')) return null;
    const t = r.simulation_throttled_sec;
    const sim = r.simulation_time_sec;
    const share = typeof sim === 'number' && sim > 0 ? ` (${fmtNum(100 * t / sim, 0)}% of the simulation window)` : '';
    return `held by the CPU quota for ${fmtNum(t, 4)} s${share}, included in simulation_time_sec`;
}

/** Note for a run the server tagged outside_process (its container used more CPU than its simulating process during the window), or null. */
export function outsideProcessText(r) {
    if (!timingCaveat(r, 'outside_process')) return null;
    const cg = r.simulation_cgroup_cpu_time_sec;
    const own = r.simulation_cpu_time_sec;
    return `container CPU ${fmtNum(cg, 4)} s vs process ${fmtNum(own, 4)} s in the simulation window: `
        + `${fmtNum(cg - own, 4)} s outside the measured process`;
}

/** Note for a run the server tagged host_load (host-load notices of the qrosetta command open during the run), or null. */
export function hostLoadText(r) {
    if (!timingCaveat(r, 'host_load')) return null;
    const n = r.server_overlapping_host_load;
    return `${fmtInt(n)} interval(s) of qrosetta container activity on this host during the run`;
}

/** Core speed classes (MHz) as text, e.g. "4000/4100 MHz vs 5300 MHz". */
export function coreClassesText(classes) {
    return classes.map(c => c.map(s => `${fmtInt(s)}`).join('/') + ' MHz').join(' vs ');
}

/** Note for a run the server tagged mixed_cores (timed runs on CPUs of different speed classes), or null. */
export function mixedCoresText(r) {
    const classes = timingCaveat(r, 'mixed_cores')?.detail?.classes_mhz;
    if (!Array.isArray(classes)) return null;
    return `timed runs on CPUs of different speed classes (maximum ${coreClassesText(classes)})`;
}

/** Note for a run the server tagged unstable_repeats (simulation samples spread by more than 1.3×), or null. */
export function unstableText(r) {
    const detail = timingCaveat(r, 'unstable_repeats')?.detail;
    if (!detail) return null;
    const lo = detail.min_sec, hi = detail.max_sec;
    return `timed runs ranged from ${fmtNum(lo, 4)} to ${fmtNum(hi, 4)} s (${fmtNum(hi / lo, 2)}×); the median is less reliable than its n suggests`;
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
    return `queued ${fmtNum(w, 1)} s behind another run (not in the timings)`;
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
        li.className = 'text-gray-500';
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
