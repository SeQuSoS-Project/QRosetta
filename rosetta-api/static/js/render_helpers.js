// Low-level DOM render helpers shared by renderers.js and tables_renderer.js: template
// cloning, status-style tokens, tooltips, and the optimization-level badge. Kept in a
// leaf module (no imports from either) so the two report-rendering modules can share
// them without importing each other.

import { getRunnerOptInfo } from './config.js';
import { parseRunnerKey } from './runner_key.js';

export const METRIC_DEFINITIONS = {
    "compilation": "<b>Compilation Time:</b> Time taken to parse QASM, apply transforms (e.g. Rebase), and convert to the backend's native format. A uniform, disclosed warm-up run precedes every timed measurement (same for all backends), so this excludes one-time import/JIT overhead.",
    "simulation": "<b>Simulation Time:</b> Time taken for the backend to execute the circuit (matrix multiplication) and retrieve results, after the same uniform warm-up.",
    "total_time": "<b>Total Execution Time:</b> Sum of Compilation and Simulation. Represents end-to-end latency.",
    "cpu_time": "<b>CPU Time:</b> User+system CPU time (resource.getrusage) consumed by the whole isolated run, including compilation and the warm-up. Unlike wall-clock time, this is not affected by contention from other concurrent runs.",
    "gate_count": "<b>Gate Count:</b> Number of gate-application statements in the backend's own transpiled QASM.",
    "circuit_depth": "<b>Depth:</b> Greedy-layering circuit depth computed from the backend's own transpiled QASM.",
    "proc_peak_rss": "<b>Process Peak RSS:</b> The kernel-reported (resource.getrusage ru_maxrss) peak memory of the whole isolated run, including compilation and the warm-up. Resources are ranked by this column.",
    "mem_delta": "<b>Memory Delta:</b> RAM added to the process during the simulation window only (End RSS - Start RSS), reported by the backend's own MemoryMonitor with 10ms polling — may undercount short-lived C++ allocations and excludes compilation. Shown for continuity; ranking uses Process Peak RSS.",
    "proc_peak": "<b>Process Peak (legacy):</b> The maximum RAM observed by the backend's own 10ms-polling MemoryMonitor during the simulation window only. Shown for continuity; ranking uses Process Peak RSS, the kernel-reported peak of the whole run.",
    "theoretical_sv": "<b>Theoretical SV:</b> The absolute minimum memory required to store the full statevector (2^N × 16 bytes for complex128). Tensor-network simulators (e.g. Quimb) natively use less and map to 'None'.",
    "fidelity_matrix": "<b>Fidelity Matrix:</b> Pairwise comparison of state overlap. 1.0 = Identical states.",
    "relative_phase_matrix": "<b>Relative Phase Matrix:</b> Comparison of global phase differences. Non-zero means states differ by a constant phase factor.",
    "statistical_distance_matrix (js_divergence)": "<b>JS Divergence:</b> Jensen-Shannon divergence between probability distributions. 0.0 = Identical.",
    "hellinger_distance_matrix": "<b>Hellinger Distance:</b> Geometric distance between distributions. 0.0 = Identical.",
    "pairwise_agreement": "<b>Explained-Cause Agreement:</b> Each backend pair is classified over a registered-transform lattice (direct → global phase → bit reversal → qubit permutation → residual). Each label reports the transform that explains the pair and its numerical effect, with full provenance.",
    "statistical_test": "<b>Shot-Noise Test:</b> Homogeneity test (chi-square + G-test) on measured counts, with effect size and power, computed on the same transform basis the label selected. Reported alongside the descriptive label.",
    "execution_time_sec": "<b>Execution Time:</b> The total time taken for the simulation.",
    "memory_usage_mb": "<b>Memory Usage:</b> The memory consumed by the simulation."
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
        // Self-comparison key carries its own opt level — config has no entry for it.
        optLevel = parsed.optLevel;
    } else {
        let cv = config[simulator];
        if (Array.isArray(cv)) cv = cv.length ? cv[0] : 0;   // single-job multi-run entry
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
