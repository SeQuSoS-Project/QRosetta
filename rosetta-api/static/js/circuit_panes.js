// The circuit texts one run recorded, as panes for the Circuits view: the submitted
// circuit, each dispatch group's circuit and each backend's executed circuit. Pure, no
// imports beyond the runner-key parser.

import { parseRunnerKey } from './runner_key.js';

export const GATE_METRICS_FROM_QASM = 'top-level gate statements of transpiled_qasm; depth by greedy layering';

const API_NOTE = /^API:/;

function _strings(list) {
    return Array.isArray(list) ? list.filter(item => typeof item === 'string') : [];
}

/** Where an executed pane's gate count and depth come from, relative to its text. */
export function metricsSource(result) {
    const basis = typeof result?.gate_metrics_basis === 'string' ? result.gate_metrics_basis : null;
    if (basis === null) return { fromText: null, basis: null };
    return { fromText: basis === GATE_METRICS_FROM_QASM, basis };
}

function _executedPane(result, index) {
    const key = typeof result.simulator === 'string' ? result.simulator : `result ${index + 1}`;
    const notes = _strings(result.preprocessing_applied);
    return {
        id: `executed:${key}`,
        kind: 'executed',
        key,
        simId: parseRunnerKey(key).simId,
        group: typeof result.dispatch_group === 'string' ? result.dispatch_group : null,
        text: typeof result.transpiled_qasm === 'string' ? result.transpiled_qasm : null,
        status: typeof result.dispatch_status === 'string' ? result.dispatch_status : null,
        apiNotes: notes.filter(note => API_NOTE.test(note)),
        runnerNotes: notes.filter(note => !API_NOTE.test(note)),
        gateCount: typeof result.gate_count === 'number' ? result.gate_count : null,
        depth: typeof result.circuit_depth === 'number' ? result.circuit_depth : null,
        metrics: metricsSource(result),
        sdkVersions: result.sdk_versions && typeof result.sdk_versions === 'object' ? result.sdk_versions : null,
    };
}

/** Panes in display order: submitted, dispatched (per group), executed (per result key). */
export function circuitPanes(report) {
    if (!report || typeof report !== 'object') return [];
    const panes = [];
    if (typeof report.input_qasm === 'string') {
        panes.push({ id: 'input', kind: 'input', key: null, group: null, text: report.input_qasm });
    }
    for (const record of Array.isArray(report.dispatched_circuits) ? report.dispatched_circuits : []) {
        if (!record || typeof record.group !== 'string' || typeof record.qasm !== 'string') continue;
        panes.push({
            id: `dispatched:${record.group}`,
            kind: 'dispatched',
            key: null,
            group: record.group,
            text: record.qasm,
            apiNotes: _strings(record.api_preprocessing_applied),
            runners: _strings(record.runners),
        });
    }
    (Array.isArray(report.raw_results) ? report.raw_results : []).forEach((result, index) => {
        if (result && typeof result === 'object') panes.push(_executedPane(result, index));
    });
    return panes;
}

/** The pane a pane's text was derived from: dispatched for executed, submitted for dispatched. */
export function sourcePaneId(pane, panes) {
    if (pane.kind === 'executed' && pane.group) {
        const id = `dispatched:${pane.group}`;
        if (panes.some(p => p.id === id)) return id;
    }
    if (pane.kind !== 'input' && panes.some(p => p.id === 'input')) return 'input';
    return null;
}
