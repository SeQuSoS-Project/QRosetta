// What one press of Run sends: the requests built from the workspace (which circuits, which
// modes, compile-only services, preprocessing, the shared settings), and the server limits
// those requests would exceed. Pure: no DOM, no network.

import { charCount, formatBytes, groupDigits, jsonBytes, printableLabel } from './request_limits.js';
import { plannedRunKeys } from './runner_key.js';

/** A circuit name without a trailing qubit-count suffix such as " (4q)". */
export function bareCircuitName(name) {
    return String(name ?? '').replace(/(\s*\(\d+q\))+\s*$/, '').trim();
}

/** A circuit-list item as a BenchmarkTask: only the fields the server defines. Names, and the
 * algorithm of a literal circuit (only a label then), are printable and at most `maxLabel` long. */
export function toBatchTask(item, maxLabel = 200) {
    const qasm = item.qasm_string || item.qasm;
    const algorithm = qasm ? printableLabel(item.algorithm || 'custom', maxLabel) || 'custom' : String(item.algorithm || 'custom');
    const task = { algorithm, qubits: parseInt(item.qubits) || 0 };
    const name = printableLabel(bareCircuitName(item.name), maxLabel);
    if (name && name !== task.algorithm) task.name = name;
    if (qasm) task.qasm_string = qasm;
    if (item.source) task.source = item.source;
    return task;
}

/** A circuit-list item as an ExperimentCircuit; benchmark items stay references. */
export function toExperimentCircuit(item, maxLabel = 200) {
    const label = text => printableLabel(text, maxLabel) || null;
    if (item.source === 'mqt' || item.source === 'qasmbench') {
        return { source: item.source, algorithm: item.algorithm, qubits: parseInt(item.qubits) || 0,
                 name: label(bareCircuitName(item.name)) || label(item.algorithm) };
    }
    const qasm = item.qasm_string || item.qasm;
    if (qasm) {
        return { source: 'qasm', qasm_string: qasm, name: label(bareCircuitName(item.name) || item.algorithm) || 'circuit',
                 qubits: parseInt(item.qubits) || 0 };
    }
    return { source: 'preset', algorithm: item.algorithm, qubits: parseInt(item.qubits) || 0,
             name: label(bareCircuitName(item.name)) };
}

const MODE_LABEL = { statevector: 'Statevector', measured: 'Measured' };

/**
 * @typedef {{ endpoint: string, payload: object, title: string, kind: string, mode: string|null }} PlannedRun
 * @param {{ source: 'editor'|'list', editor: { qasm: string, name: string }, list: object[],
 *           modes: { statevector: boolean, measured: boolean }, compilers: object,
 *           preprocessing: 'on'|'off'|'both', runName: string, shots: number, seed: number|null,
 *           common: object, limits?: { maxLabelLength?: number } }} ws
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
    const maxLabel = ws.limits?.maxLabelLength ?? 200;

    if (!modes.length) {
        if (ws.preprocessing === 'both') return { runs: [], error: 'A compile-only run uses one preprocessing setting. Choose on or off.' };
        const shared = { optimization_level: common.optimization_level ?? 0, timeout_seconds: common.timeout_seconds,
                         execution_target: common.execution_target, bypass_limits: !!common.bypass_limits,
                         apply_preprocessing: ws.preprocessing !== 'off', compilers, simulate: false };
        return { error: null, runs: [fromList
            ? { endpoint: '/run_batch_suite', kind: 'batch', mode: null, title: `${base} (compile only)`,
                payload: { ...shared, mode: 'statevector', tasks: circuits.map(c => toBatchTask(c, maxLabel)) } }
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
            const list = fromList ? circuits.map(c => toExperimentCircuit(c, maxLabel))
                : [{ source: 'qasm', qasm_string: ws.editor.qasm, name: printableLabel(bareCircuitName(ws.editor.name), maxLabel) || 'editor circuit' }];
            return { endpoint: '/experiments', kind: 'experiment', mode,
                     title: `${title} · preprocessing on and off`,
                     payload: { ...payload, mode, circuits: list, preprocessing_modes: [true, false],
                                label: printableLabel(ws.runName, maxLabel) || null } };
        }
        payload.apply_preprocessing = ws.preprocessing !== 'off';
        if (fromList) {
            return { endpoint: '/run_batch_suite', kind: 'batch', mode, title,
                     payload: { ...payload, mode, tasks: circuits.map(c => toBatchTask(c, maxLabel)) } };
        }
        return { endpoint: measured ? '/compare_measured' : '/compare', kind: 'single', mode, title,
                 payload: { ...payload, qasm_string: ws.editor.qasm } };
    });
    return { runs, error: null };
}

/** The Run button's label for a workspace. With countsInvalid (the multi-run counts cannot be sent) it names no run count. */
export function runButtonLabel(ws, backendCount, { countsInvalid = false } = {}) {
    const modes = ['statevector', 'measured'].filter(m => ws.modes?.[m]);
    const compilers = ws.compilers && Object.keys(ws.compilers).length;
    const n = (ws.list || []).length;
    const list = ws.source === 'list';
    const what = list ? `Batch (${n} circuit${n === 1 ? '' : 's'})` : 'Editor Code';
    if (!modes.length) return compilers ? `Compile ${list ? 'Playlist' : 'Editor Code'}` : 'Choose a mode';
    const verb = ws.preprocessing === 'both' ? `Run Experiment: ${list ? `${n} circuit${n === 1 ? '' : 's'}` : 'Editor Code'}` : `Run ${what}`;
    const modeText = modes.map(m => MODE_LABEL[m]).join(' + ');
    const both = ws.preprocessing === 'both' ? ', preprocessing on and off' : '';
    const backends = `${backendCount} backend${backendCount === 1 ? '' : 's'}`;
    const runs = plannedRunKeys(ws.common?.target_simulators || [], ws.common?.runner_config || {}).length;
    const targets = countsInvalid ? 'multi-run counts to fix' : runs > backendCount ? `${runs} runs on ${backends}` : backends;
    return `${verb} · ${modeText}${both} · ${targets}`;
}

/** The literal circuits of a planned request: [name, qasm] pairs. */
function _literalCircuits(payload) {
    if (typeof payload.qasm_string === 'string') return [['The editor circuit', payload.qasm_string]];
    const list = payload.tasks || payload.circuits || [];
    return list.filter(c => typeof c.qasm_string === 'string')
        .map(c => [`Circuit "${c.name || c.algorithm || 'custom'}"`, c.qasm_string]);
}

/**
 * Why the server would refuse a planned request before running it: an experiment with more
 * circuit-axis runs than allowed, a circuit text over the size limit, or a request body over
 * the upload limit. bypass_limits lifts the first two as the server does (the circuit size only
 * in local mode, where the option is offered); the body limit always applies.
 * @param {PlannedRun[]} runs
 * @param {{ maxRequestBytes?: number, maxQasmSize?: number, maxExperimentCells?: number, executionMode?: string|null }} limits
 * @returns {string[]}
 */
export function runLimitProblems(runs, limits = {}) {
    const problems = [];
    for (const run of runs) {
        const p = run.payload || {};
        const bypass = !!p.bypass_limits;
        if (run.kind === 'experiment' && limits.maxExperimentCells && !bypass) {
            const n = (p.circuits || []).length;
            const axes = (p.preprocessing_modes || []).length;
            if (n * axes > limits.maxExperimentCells) {
                problems.push(`${run.title}: SDK Preprocessing Both runs every circuit once per setting, so ${n} circuits make `
                    + `${n * axes} experiment runs; the server allows ${limits.maxExperimentCells}. Run at most `
                    + `${Math.floor(limits.maxExperimentCells / axes)} circuits at a time, or choose preprocessing On or Off.`);
            }
        }
        if (limits.maxQasmSize && !(bypass && limits.executionMode === 'local')) {
            for (const [what, qasm] of _literalCircuits(p)) {
                const n = charCount(qasm);
                if (n > limits.maxQasmSize) {
                    problems.push(`${what} has ${groupDigits(n)} characters; the server accepts circuits of up to ${groupDigits(limits.maxQasmSize)}.`);
                }
            }
        }
        if (limits.maxRequestBytes) {
            const bytes = jsonBytes(p);
            if (bytes > limits.maxRequestBytes) {
                const literal = _literalCircuits(p);
                const why = literal.length > 1
                    ? `The ${literal.length} circuits from the editor or from files travel in this one request. Split the playlist `
                      + `(Import/Export JSON keeps a copy) and run the parts one after another.`
                    : 'Line breaks and quotes in the circuit text take two bytes each in the request. Shorten the circuit, '
                      + 'for example by removing comments and blank lines.';
                problems.push(`${run.title}: the request is ${formatBytes(bytes)}, over the server's upload limit of `
                    + `${formatBytes(limits.maxRequestBytes)}. ${why}`);
            }
        }
    }
    return [...new Set(problems)];
}
