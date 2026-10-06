// What one press of Run sends: the requests built from the workspace (which circuits, which
// modes, compile-only services, preprocessing, the shared settings). Pure: no DOM, no network.

/** A circuit name without a trailing qubit-count suffix such as " (4q)". */
export function bareCircuitName(name) {
    return String(name ?? '').replace(/(\s*\(\d+q\))+\s*$/, '').trim();
}

/** A circuit-list item as a BenchmarkTask: only the fields the server defines. */
export function toBatchTask(item) {
    const task = { algorithm: String(item.algorithm || 'custom'), qubits: parseInt(item.qubits) || 0 };
    const name = bareCircuitName(item.name);
    if (name && name !== task.algorithm) task.name = name.slice(0, 200);
    if (item.qasm_string) task.qasm_string = item.qasm_string;
    if (item.source) task.source = item.source;
    return task;
}

/** A circuit-list item as an ExperimentCircuit; benchmark items stay references. */
export function toExperimentCircuit(item) {
    if (item.source === 'mqt' || item.source === 'qasmbench') {
        return { source: item.source, algorithm: item.algorithm, qubits: parseInt(item.qubits) || 0,
                 name: bareCircuitName(item.name) || item.algorithm };
    }
    const qasm = item.qasm_string || item.qasm;
    if (qasm) {
        return { source: 'qasm', qasm_string: qasm, name: bareCircuitName(item.name) || item.algorithm || 'circuit',
                 qubits: parseInt(item.qubits) || 0 };
    }
    return { source: 'preset', algorithm: item.algorithm, qubits: parseInt(item.qubits) || 0,
             name: bareCircuitName(item.name) || null };
}

const MODE_LABEL = { statevector: 'Statevector', measured: 'Measured' };

/**
 * @typedef {{ endpoint: string, payload: object, title: string, kind: string, mode: string|null }} PlannedRun
 * @param {{ source: 'editor'|'list', editor: { qasm: string, name: string }, list: object[],
 *           modes: { statevector: boolean, measured: boolean }, compilers: object,
 *           preprocessing: 'on'|'off'|'both', runName: string, shots: number, seed: number|null,
 *           common: object }} ws
 * @returns {{ runs: PlannedRun[], error: string|null }}
 */
export function planRuns(ws) {
    const modes = ['statevector', 'measured'].filter(m => ws.modes?.[m]);
    const compilers = ws.compilers && Object.keys(ws.compilers).length ? ws.compilers : null;
    const fromList = ws.source === 'list';
    const circuits = fromList ? (ws.list || []) : [];
    if (fromList && !circuits.length) return { runs: [], error: 'The playlist is empty. Add circuits, or run the editor code.' };
    if (!fromList && !String(ws.editor?.qasm || '').trim()) {
        return { runs: [], error: 'The editor is empty. Enter, open or generate an OpenQASM 2.0 circuit.' };
    }
    if (!modes.length && !compilers) return { runs: [], error: 'Choose at least one of Statevector, Measured or Compile-only services.' };
    const what = fromList ? `Playlist of ${circuits.length} circuit${circuits.length === 1 ? '' : 's'}` : (bareCircuitName(ws.editor?.name) || 'Editor Run');
    const base = ws.runName ? ws.runName : what;
    const common = ws.common || {};

    if (!modes.length) {
        if (ws.preprocessing === 'both') return { runs: [], error: 'A compile-only run uses one preprocessing setting. Choose on or off.' };
        const shared = { optimization_level: common.optimization_level ?? 0, timeout_seconds: common.timeout_seconds,
                         execution_target: common.execution_target, bypass_limits: !!common.bypass_limits,
                         apply_preprocessing: ws.preprocessing !== 'off', compilers, simulate: false };
        return { error: null, runs: [fromList
            ? { endpoint: '/run_batch_suite', kind: 'batch', mode: null, title: `${base} (compile only)`,
                payload: { ...shared, mode: 'statevector', tasks: circuits.map(toBatchTask) } }
            : { endpoint: '/compare', kind: 'single', mode: null, title: `${base} (compile only)`,
                payload: { ...shared, qasm_string: ws.editor.qasm } }] };
    }

    const runs = modes.map((mode, i) => {
        const measured = mode === 'measured';
        const payload = { ...common, compilers: i === 0 && compilers ? compilers : {} };
        if (measured) {
            payload.n_shots = ws.shots;
            payload.seed = ws.seed ?? null;
        }
        const title = `${base} (${MODE_LABEL[mode]}${measured ? `, ${ws.shots} shots` : ''})`;
        if (ws.preprocessing === 'both') {
            const list = fromList ? circuits.map(toExperimentCircuit)
                : [{ source: 'qasm', qasm_string: ws.editor.qasm, name: bareCircuitName(ws.editor.name) || 'editor circuit' }];
            return { endpoint: '/experiments', kind: 'experiment', mode,
                     title: `${title} · preprocessing on and off`,
                     payload: { ...payload, mode, circuits: list, preprocessing_modes: [true, false],
                                label: ws.runName || null } };
        }
        payload.apply_preprocessing = ws.preprocessing !== 'off';
        if (fromList) {
            return { endpoint: '/run_batch_suite', kind: 'batch', mode, title,
                     payload: { ...payload, mode, tasks: circuits.map(toBatchTask) } };
        }
        return { endpoint: measured ? '/compare_measured' : '/compare', kind: 'single', mode, title,
                 payload: { ...payload, qasm_string: ws.editor.qasm } };
    });
    return { runs, error: null };
}

/** The Run button's label for a workspace. */
export function runButtonLabel(ws, backendCount) {
    const modes = ['statevector', 'measured'].filter(m => ws.modes?.[m]);
    const compilers = ws.compilers && Object.keys(ws.compilers).length;
    const n = (ws.list || []).length;
    const list = ws.source === 'list';
    const what = list ? `Batch (${n} circuit${n === 1 ? '' : 's'})` : 'Editor Code';
    if (!modes.length) return compilers ? `Compile ${list ? 'Playlist' : 'Editor Code'}` : 'Choose a mode';
    const verb = ws.preprocessing === 'both' ? `Run Experiment: ${list ? `${n} circuit${n === 1 ? '' : 's'}` : 'Editor Code'}` : `Run ${what}`;
    const modeText = modes.map(m => MODE_LABEL[m]).join(' + ');
    const both = ws.preprocessing === 'both' ? ', preprocessing on and off' : '';
    return `${verb} · ${modeText}${both} · ${backendCount} backend${backendCount === 1 ? '' : 's'}`;
}
