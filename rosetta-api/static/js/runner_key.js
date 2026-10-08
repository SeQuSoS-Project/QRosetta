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
