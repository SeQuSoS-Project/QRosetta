// The circuit texts one run recorded, as panes for the Circuits view: the submitted
// circuit, each dispatch group's circuit, each backend's executed circuit and, when the run
// had compile-only services, their input and outputs. Pure, no imports beyond the
// runner-key parser.

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

function _gateCounts(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return [];
    return Object.entries(value).filter(([name, n]) => typeof name === 'string' && Number.isInteger(n));
}

function _nativeComponents(value) {
    if (!Array.isArray(value)) return [];
    return value.filter(c => c && typeof c === 'object' && typeof c.name === 'string' && typeof c.version === 'string')
        .map(c => ({ name: c.name, version: c.version, sourceSha256: typeof c.source_sha256 === 'string' ? c.source_sha256 : null }));
}

function _compiledPane(record, index) {
    const key = typeof record.compiler === 'string' ? record.compiler : `compiler ${index + 1}`;
    return {
        id: `compiled:${key}`,
        kind: 'compiled',
        key,
        compilerId: typeof record.compiler_id === 'string' ? record.compiler_id : parseRunnerKey(key).simId,
        compilerName: typeof record.compiler_name === 'string' ? record.compiler_name : null,
        level: typeof record.optimization_level === 'number' ? record.optimization_level : null,
        text: typeof record.transpiled_qasm === 'string' ? record.transpiled_qasm : null,
        status: typeof record.dispatch_status === 'string' ? record.dispatch_status : null,
        passes: _strings(record.passes_applied),
        reason: typeof record.refusal === 'string' ? record.refusal
            : typeof record.error === 'string' ? record.error : null,
        refusalKind: record.refusal_kind === 'input' || record.refusal_kind === 'output_check' ? record.refusal_kind : null,
        nativeComponents: _nativeComponents(record.native_components),
        gateCount: typeof record.gate_count === 'number' ? record.gate_count : null,
        depth: typeof record.circuit_depth === 'number' ? record.circuit_depth : null,
        multiQubitGateCount: typeof record.multi_qubit_gate_count === 'number' ? record.multi_qubit_gate_count : null,
        gateCounts: _gateCounts(record.gate_counts),
        metrics: metricsSource(record),
        sdkVersions: record.sdk_versions && typeof record.sdk_versions === 'object' ? record.sdk_versions : null,
    };
}

/**
 * Panes in display order: submitted, dispatched (per group), executed (per result key),
 * then the compile input and each compiled circuit.
 */
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
    const compileInput = report.compile_input;
    if (compileInput && typeof compileInput === 'object' && typeof compileInput.qasm === 'string') {
        panes.push({ id: 'compile-input', kind: 'compile-input', key: null, group: null, text: compileInput.qasm,
                     apiNotes: _strings(compileInput.api_preprocessing_applied) });
    }
    (Array.isArray(report.compiled_circuits) ? report.compiled_circuits : []).forEach((record, index) => {
        if (record && typeof record === 'object') panes.push(_compiledPane(record, index));
    });
    return panes;
}

/**
 * The pane a pane's text was derived from: dispatched for executed, the compile input for
 * compiled, submitted for dispatched and for the compile input.
 */
export function sourcePaneId(pane, panes) {
    if (pane.kind === 'compiled' && panes.some(p => p.id === 'compile-input')) return 'compile-input';
    if (pane.kind === 'executed' && pane.group) {
        const id = `dispatched:${pane.group}`;
        if (panes.some(p => p.id === id)) return id;
    }
    if (pane.kind !== 'input' && panes.some(p => p.id === 'input')) return 'input';
    return null;
}
