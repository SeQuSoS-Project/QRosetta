// The app's single state object and the dispatch() reducer that changes it.

import { readPref, writePref } from './session_store.js';

export const Store = {
    state: {
        authToken: readPref('rosetta_token', '') || null,
        isProcessing: false,
        currentSuiteData: null,
        currentSuiteTitle: '',
        batchQueue: [],
        allAlgorithms: [],
        currentAlgoName: "Custom",
        currentRunnerConfig: {},
        currentJobId: null,
        currentHistoryRunId: null,
        maxQubitsStatevector: 18,
        maxQubitsMeasured: 24,
        maxQubitsCompile: 24,
        maxRunsPerRunner: 16,
        maxTotalRuns: 48,
        maxRequestBytes: 1048576,
        maxQasmSize: 1000000,
        maxExperimentCells: 200,
        maxExportItems: 60,
        maxLabelLength: 200,
        emailMaxLength: 254,
        passwordMinChars: 8,
        passwordMaxBytes: 72,
        executionMode: null,
        timeoutMin: 10,
        timeoutMax: 300,
        timeoutDefault: 60,
        timingRepeatsMax: 10,
        exclusiveEnabled: true,
        shotsMin: 1,
        shotsMax: null,
        thresholdDefaults: null,
        exportItems: [],
        exportPreset: readPref('rosetta_export_preset', 'paper') || 'paper',
        exportCustomised: false,
    },

    dispatch(action, payload) {

        switch (action) {
            case 'SET_AUTH_TOKEN':
                this.state.authToken = payload;
                writePref('rosetta_token', payload || null);
                break;
            case 'SET_PROCESSING':
                this.state.isProcessing = payload;
                break;
            case 'SET_SUITE_DATA':
                this.state.currentSuiteData = payload;
                break;
            case 'SET_SUITE_TITLE':
                this.state.currentSuiteTitle = payload;
                break;
            case 'SET_BATCH_QUEUE':
                this.state.batchQueue = payload;
                break;
            case 'SET_ALGORITHMS':
                this.state.allAlgorithms = payload;
                break;
            case 'SET_CURRENT_ALGO_NAME':
                this.state.currentAlgoName = payload;
                break;
            case 'SET_RUNNER_CONFIG':
                this.state.currentRunnerConfig = payload;
                break;
            case 'SET_JOB_ID':
                this.state.currentJobId = payload;
                break;
            case 'SET_HISTORY_RUN_ID':
                this.state.currentHistoryRunId = payload;
                break;
            case 'SET_CONFIG_LIMITS': {
                const limits = payload.limits || {};
                const num = v => (typeof v === 'number' && Number.isFinite(v) ? v : undefined);
                this.state.maxQubitsStatevector = num(limits.max_qubits_statevector) ?? num(payload.max_qubits_statevector) ?? this.state.maxQubitsStatevector;
                this.state.maxQubitsMeasured = num(limits.max_qubits_measured) ?? num(payload.max_qubits_measured) ?? this.state.maxQubitsMeasured;
                this.state.maxQubitsCompile = num(limits.max_qubits_compile) ?? num(payload.max_qubits_compile) ?? this.state.maxQubitsCompile;
                this.state.timeoutMin = num(limits.timeout_min) ?? this.state.timeoutMin;
                this.state.timeoutMax = num(limits.timeout_max) ?? this.state.timeoutMax;
                this.state.shotsMin = num(limits.shots_min) ?? this.state.shotsMin;
                this.state.shotsMax = num(limits.shots_max) ?? this.state.shotsMax;
                this.state.timeoutDefault = num(limits.timeout_default) ?? this.state.timeoutDefault;
                this.state.timingRepeatsMax = num(limits.timing_repeats_max) ?? this.state.timingRepeatsMax;
                this.state.maxRequestBytes = num(limits.max_request_bytes) ?? this.state.maxRequestBytes;
                this.state.maxQasmSize = num(payload.max_qasm_size) ?? this.state.maxQasmSize;
                this.state.maxExperimentCells = num(limits.max_experiment_cells) ?? this.state.maxExperimentCells;
                this.state.maxExportItems = num(limits.max_export_items) ?? this.state.maxExportItems;
                this.state.maxLabelLength = num(limits.max_label_length) ?? this.state.maxLabelLength;
                this.state.emailMaxLength = num(limits.email_max_length) ?? this.state.emailMaxLength;
                this.state.passwordMinChars = num(limits.password_min_chars) ?? this.state.passwordMinChars;
                this.state.passwordMaxBytes = num(limits.password_max_bytes) ?? this.state.passwordMaxBytes;
                if (typeof payload.exclusive?.enabled === 'boolean') this.state.exclusiveEnabled = payload.exclusive.enabled;
                if (payload.agreement_threshold_defaults && typeof payload.agreement_threshold_defaults === 'object') {
                    this.state.thresholdDefaults = { ...payload.agreement_threshold_defaults };
                }
                if (payload.max_runs_per_runner !== undefined) this.state.maxRunsPerRunner = payload.max_runs_per_runner;
                if (payload.max_total_runs !== undefined) this.state.maxTotalRuns = payload.max_total_runs;
                if (payload.execution_mode !== undefined) this.state.executionMode = payload.execution_mode;
                break;
            }
            case 'SET_EXPORT_ITEMS':
                this.state.exportItems = payload.items;
                this.state.exportCustomised = !!payload.customised;
                break;
            case 'SET_EXPORT_PRESET':
                this.state.exportPreset = payload;
                writePref('rosetta_export_preset', payload);
                break;
            default:
                console.warn(`[State] Unknown action: ${action}`);
        }
    },

    /** A shallow frozen copy: assigning to it throws in strict mode. Nested objects and
     * arrays are the live values; to change one, build a new value and dispatch it. */
    getState() {
        return Object.freeze({ ...this.state });
    }
};

// Exported for modules; also published on window because index.html's inline
// handlers and the browser console both reach for them by name.
export function dispatch(action, payload) {
    Store.dispatch(action, payload);
}

export function getState() {
    return Store.getState();
}

window.dispatch = dispatch;
window.getState = getState;