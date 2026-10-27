// What one press of Run asks POST /plan for (the circuits, modes, compile-only services,
// preprocessing and shared settings of the workspace), the page's wording of the problems the
// plan returns, and the Run button's label. Pure: no DOM, no network.

import { formatBytes, groupDigits } from './request_limits.js';
import { plannedRunKeys } from './runner_key.js';

/** A circuit name without a trailing qubit-count suffix such as " (4q)". */
export function bareCircuitName(name) {
    return String(name ?? '').replace(/(\s*\(\d+q\))+\s*$/, '').trim();
}

const MODE_LABEL = { statevector: 'Statevector', measured: 'Measured' };

/**
 * @typedef {{ endpoint: string, payload: object, title: string, kind: string, mode: string|null, sources?: object }} PlannedRun
 * The POST /plan body for a workspace: the circuits (the playlist, or the editor circuit), the
 * ticked modes, preprocessing, compile-only services, the run name as typed, and every shared
 * setting the page sends, with source 'flag'. The server plans the requests from it.
 * @param {{ source: 'editor'|'list', editor: { qasm: string, name: string }, list: object[],
 *           modes: { statevector: boolean, measured: boolean }, compilers: object,
 *           preprocessing: 'on'|'off'|'both', shots: number|null, seed: number|null, common: object }} ws
 * @param {string} runName the Run Name field as typed
 */
export function planRequest(ws, runName) {
    const fromList = ws.source === 'list';
    const values = { ...(ws.common || {}), n_shots: ws.shots, seed: ws.seed ?? null };
    const settings = Object.fromEntries(Object.entries(values)
        .filter(([, value]) => value !== undefined)
        .map(([field, value]) => [field, { value, source: 'flag' }]));
    return {
        source: fromList ? 'playlist' : 'single',
        circuits: fromList ? (ws.list || []) : [{ qasm_string: ws.editor?.qasm ?? '', name: ws.editor?.name ?? '' }],
        modes: ['statevector', 'measured'].filter(m => ws.modes?.[m]),
        preprocessing: ws.preprocessing,
        compilers: ws.compilers || {},
        name: runName,
        settings,
    };
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

/** The page's wording of a plan-level problem code from POST /plan. */
const PLAN_ERROR_TEXT = {
    playlist_empty: 'The playlist is empty. Add circuits, or run the editor code.',
    editor_empty: 'The editor is empty. Enter, open or generate an OpenQASM 2.0 circuit.',
    no_mode: 'Choose at least one of Statevector, Measured or Compile-only services.',
    compile_only_needs_one_setting: 'A compile-only run uses one preprocessing setting. Choose on or off.',
};

/**
 * The page's wording of the problems POST /plan returned for `runs` (its planned runs), without
 * duplicates: the plan-level codes and the server limits. Any other code (invalid_request,
 * bypass_needs_account, circuit_refused) is left out, and the run route answers it as before.
 * @param {{ code: string, params?: any, run_index?: number|null }[]} problems
 * @param {{ title: string }[]} runs
 * @returns {string[]}
 */
export function planProblemTexts(problems, runs) {
    const out = [];
    for (const problem of problems || []) {
        const p = problem.params || {};
        const title = runs?.[problem.run_index ?? -1]?.title;
        switch (problem.code) {
        case 'playlist_too_long':
            out.push(`${title}: the playlist has ${groupDigits(p.circuits)} circuits; the server runs at most `
                + `${groupDigits(p.max)} in one run. Split the playlist (Import/Export JSON keeps a copy) and run `
                + `the parts one after another.`);
            break;
        case 'bundled_over_prep_limit': {
            const heavy = p.circuits || [];
            const names = heavy.map(c => (c.source === 'qasmbench' || !c.qubits) ? c.algorithm : `${c.algorithm} (${c.qubits}q)`);
            const shown = names.length > 5 ? `${names.slice(0, 5).join(', ')} and ${names.length - 5} more` : names.join(', ');
            const limit = p.prep_max_mib ? `the server's ${groupDigits(p.prep_max_mib)} MiB limit` : "the server's limit";
            out.push(`${title}: with SDK Preprocessing on, preparing ${shown} takes more memory than ${limit} `
                + `for circuit preparation. Remove ${heavy.length === 1 ? 'it' : 'them'}, or set SDK Preprocessing to Off.`);
            break;
        }
        case 'experiment_too_many_cells':
            out.push(`${title}: SDK Preprocessing Both runs every circuit once per setting, so ${p.circuits} circuits make `
                + `${p.cells} experiment runs; the server allows ${p.max}. Run at most `
                + `${Math.floor(p.max / p.settings)} circuits at a time, or choose preprocessing On or Off.`);
            break;
        case 'circuit_too_large': {
            const what = p.circuit == null ? 'The editor circuit' : `Circuit "${p.circuit}"`;
            out.push(`${what} has ${groupDigits(p.characters)} characters; the server accepts circuits of up to ${groupDigits(p.max)}.`);
            break;
        }
        case 'request_too_large': {
            const why = p.literal_circuits > 1
                ? `The ${p.literal_circuits} circuits from the editor or from files travel in this one request. Split the playlist `
                  + `(Import/Export JSON keeps a copy) and run the parts one after another.`
                : 'Line breaks and quotes in the circuit text take two bytes each in the request. Shorten the circuit, '
                  + 'for example by removing comments and blank lines.';
            out.push(`${title}: the request is ${formatBytes(p.bytes)}, over the server's upload limit of `
                + `${formatBytes(p.max)}. ${why}`);
            break;
        }
        default:
            if (PLAN_ERROR_TEXT[problem.code]) out.push(PLAN_ERROR_TEXT[problem.code]);
        }
    }
    return [...new Set(out)];
}
