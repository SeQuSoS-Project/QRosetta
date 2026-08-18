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

export function formatRunnerLabel(key, nameMap) {
    const { simId, optLevel, runIndex, isMulti } = parseRunnerKey(key);
    const base = (nameMap && nameMap[simId]) || simId;
    return isMulti ? `${base} · L${optLevel} #${runIndex}` : base;
}
