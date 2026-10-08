// Self-comparison virtual keys look like "<simId>~opt<L>~run<N>". A plain canonical
// id (e.g. "qiskit", "pennylane-default") parses as a single, non-multi run. Pure, no
// imports, so every module that needs a runner display label can depend on it directly.

export function parseRunnerKey(key) {
    const m = /^(.+)~opt(\d+)~run(\d+)$/.exec(key || '');
    if (m) {
        return { simId: m[1], optLevel: parseInt(m[2]), runIndex: parseInt(m[3]), isMulti: true };
    }
    return { simId: key, optLevel: null, runIndex: null, isMulti: false };
}

/**
 * The result keys a request will produce, as the API's expand_runner_jobs names them: a
 * backend whose runner_config entry is a list of levels gets one key per element
 * (`<id>~opt<L>~run<N>`) when it has two or more, else its canonical id.
 * @param {string[]} targets
 * @param {Record<string, number|number[]>} [runnerConfig]
 * @returns {string[]}
 */
export function plannedRunKeys(targets, runnerConfig = {}) {
    const keys = [];
    (targets || []).forEach(id => {
        const cfg = runnerConfig?.[id];
        const levels = Array.isArray(cfg) ? cfg : [cfg];
        if (!levels.length) return;
        if (levels.length === 1) { keys.push(id); return; }
        const perLevel = new Map();
        levels.forEach(level => {
            const n = (perLevel.get(level) || 0) + 1;
            perLevel.set(level, n);
            keys.push(`${id}~opt${level}~run${n}`);
        });
    });
    return keys;
}

export function formatRunnerLabel(key, nameMap) {
    const { simId, optLevel, runIndex, isMulti } = parseRunnerKey(key);
    const base = (nameMap && nameMap[simId]) || simId;
    return isMulti ? `${base} · L${optLevel} #${runIndex}` : base;
}

/** Order runner keys by backend id, then optimization level and run number as numbers
 * (`~run2` before `~run10`); plain ids before their multi-run keys. */
export function compareRunnerKeys(a, b) {
    const x = parseRunnerKey(a);
    const y = parseRunnerKey(b);
    if (x.simId !== y.simId) return x.simId < y.simId ? -1 : 1;
    if (x.isMulti !== y.isMulti) return x.isMulti ? 1 : -1;
    return (x.optLevel ?? 0) - (y.optLevel ?? 0) || (x.runIndex ?? 0) - (y.runIndex ?? 0);
}

/** Long, vendor-qualified backend names: the Backends popover, the results tables and figure
 * legends (mirrored by services/publication/theme.py BACKEND_DISPLAY_NAMES). */
export const RUNNER_DISPLAY_NAMES = {
    "qiskit": "Qiskit (IBM)",
    "qulacs": "Qulacs",
    "braket": "Braket (AWS)",
    "quest": "QuEST",
    "cirq": "Cirq (Google)",
    "qsim-cirq": "qsim (Google)",
    "qibo": "Qibo",
    "qrisp": "Qrisp",
    "myqlm": "myQLM (Eviden)",
    "pyquil": "PyQuil (Rigetti)",
    "projectq": "ProjectQ",
    "pennylane-lightning": "PL Lightning",
    "pennylane-default": "PL Default",
    "torchquantum": "TorchQuantum",
    "quimb": "Quimb (TN)",
    "cuquantum": "cuQuantum (NVIDIA)"
};

/** The long name of a runner key (services/publication/theme.py backend_label). */
export function backendLabel(key) {
    return formatRunnerLabel(key, RUNNER_DISPLAY_NAMES);
}
