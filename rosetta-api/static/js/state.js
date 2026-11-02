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
        quickLoadSets: /** @type {{ id: string, label: string, items: { algorithm: string, qubits: number, name: string }[] }[]} */ ([]),
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
        maxBatchTasks: 400,
        prepMaxMib: 1024,
        prepTimeoutSec: 120,
        jobStorageMaxMib: 10240,
        jobStorageMinFreeMib: 1024,
        jobTtlSec: 1800,
        bundledOverPrepLimit: /** @type {{ source: string, algorithm: string, qubits: number }[]} */ ([]),
        bypassRequiresAccount: false,
        maxExportItems: 60,
        maxLabelLength: 200,
        maxSavedRuns: 1000,
        emailMaxLength: 254,
        passwordMinChars: 8,
        passwordMaxBytes: 72,
        executionMode: null,
        timeoutMin: 10,
        timeoutMax: 300,
        timeoutDefault: 60,
        timingRepeatsMax: 10,
        defaultOptimizationLevel: 0,
        defaultTimingRepeats: 1,
        defaultExclusive: false,
        defaultPreprocessing: 'on',
        defaultBypassLimits: false,
        defaultShots: 8200,
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
            case 'SET_QUICK_LOAD_SETS':
                this.state.quickLoadSets = Array.isArray(payload) ? payload : [];
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
                const requests = payload.request_defaults?.requests || {};
                const filled = (kind, field) => {
                    const entry = requests[kind]?.fields?.[field];
                    return entry && entry.server_fills ? entry.default : undefined;
                };
                const bool = v => (typeof v === 'boolean' ? v : undefined);
                this.state.timeoutDefault = num(filled('compare', 'timeout_seconds')) ?? num(limits.timeout_default) ?? this.state.timeoutDefault;
                this.state.defaultOptimizationLevel = num(filled('compare', 'optimization_level')) ?? this.state.defaultOptimizationLevel;
                this.state.defaultTimingRepeats = num(filled('compare', 'timing_repeats')) ?? this.state.defaultTimingRepeats;
                this.state.defaultExclusive = bool(filled('compare', 'exclusive')) ?? this.state.defaultExclusive;
                const preprocessing = bool(filled('compare', 'apply_preprocessing'));
                if (preprocessing !== undefined) this.state.defaultPreprocessing = preprocessing ? 'on' : 'off';
                this.state.defaultBypassLimits = bool(filled('compare', 'bypass_limits')) ?? this.state.defaultBypassLimits;
                this.state.defaultShots = num(filled('compare_measured', 'n_shots')) ?? num(payload.default_n_shots) ?? this.state.defaultShots;
                this.state.timingRepeatsMax = num(limits.timing_repeats_max) ?? this.state.timingRepeatsMax;
                this.state.maxRequestBytes = num(limits.max_request_bytes) ?? this.state.maxRequestBytes;
                this.state.maxQasmSize = num(payload.max_qasm_size) ?? this.state.maxQasmSize;
                this.state.maxExperimentCells = num(limits.max_experiment_cells) ?? this.state.maxExperimentCells;
                this.state.maxBatchTasks = num(limits.max_batch_tasks) ?? this.state.maxBatchTasks;
                this.state.prepMaxMib = num(limits.prep_max_mib) ?? this.state.prepMaxMib;
                this.state.prepTimeoutSec = num(limits.prep_timeout_sec) ?? this.state.prepTimeoutSec;
                this.state.jobStorageMaxMib = num(limits.job_storage_max_mib) ?? this.state.jobStorageMaxMib;
                this.state.jobStorageMinFreeMib = num(limits.job_storage_min_free_mib) ?? this.state.jobStorageMinFreeMib;
                this.state.jobTtlSec = num(limits.job_ttl_sec) ?? this.state.jobTtlSec;
                if (Array.isArray(payload.bundled_over_prep_limit)) this.state.bundledOverPrepLimit = payload.bundled_over_prep_limit;
                if (typeof payload.bypass_limits_requires_account === 'boolean') {
                    this.state.bypassRequiresAccount = payload.bypass_limits_requires_account;
                } else if (typeof payload.execution_mode === 'string') {
                    this.state.bypassRequiresAccount = payload.execution_mode !== 'local';
                }
                this.state.maxExportItems = num(limits.max_export_items) ?? this.state.maxExportItems;
                this.state.maxLabelLength = num(limits.max_label_length) ?? this.state.maxLabelLength;
                this.state.maxSavedRuns = num(limits.max_saved_runs) ?? this.state.maxSavedRuns;
                this.state.emailMaxLength = num(limits.email_max_length) ?? this.state.emailMaxLength;
                this.state.passwordMinChars = num(limits.password_min_chars) ?? this.state.passwordMinChars;
                this.state.passwordMaxBytes = num(limits.password_max_bytes) ?? this.state.passwordMaxBytes;
                if (typeof payload.exclusive?.enabled === 'boolean') this.state.exclusiveEnabled = payload.exclusive.enabled;
                const thresholds = payload.request_defaults?.agreement_thresholds ?? payload.agreement_threshold_defaults;
                if (thresholds && typeof thresholds === 'object') this.state.thresholdDefaults = { ...thresholds };
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