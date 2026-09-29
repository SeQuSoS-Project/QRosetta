// Frontend logic for state functionality.

export const Store = {
    state: {
        authToken: localStorage.getItem('rosetta_token') || null,
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
        maxRunsPerRunner: 16,
        maxTotalRuns: 48,
        executionMode: null,
        timeoutMin: 10,
        timeoutMax: 300,
        shotsMin: 1,
        shotsMax: null,
        thresholdDefaults: null,
    },

    dispatch(action, payload) {

        switch (action) {
            case 'SET_AUTH_TOKEN':
                this.state.authToken = payload;
                if (payload) {
                    localStorage.setItem('rosetta_token', payload);
                } else {
                    localStorage.removeItem('rosetta_token');
                }
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
                this.state.timeoutMin = num(limits.timeout_min) ?? this.state.timeoutMin;
                this.state.timeoutMax = num(limits.timeout_max) ?? this.state.timeoutMax;
                this.state.shotsMin = num(limits.shots_min) ?? this.state.shotsMin;
                this.state.shotsMax = num(limits.shots_max) ?? this.state.shotsMax;
                if (payload.agreement_threshold_defaults && typeof payload.agreement_threshold_defaults === 'object') {
                    this.state.thresholdDefaults = { ...payload.agreement_threshold_defaults };
                }
                if (payload.max_runs_per_runner !== undefined) this.state.maxRunsPerRunner = payload.max_runs_per_runner;
                if (payload.max_total_runs !== undefined) this.state.maxTotalRuns = payload.max_total_runs;
                if (payload.execution_mode !== undefined) this.state.executionMode = payload.execution_mode;
                break;
            }
            default:
                console.warn(`[State] Unknown action: ${action}`);
        }
    },

    getState() {
        // A shallow frozen copy. Reads stay cheap, but `getState().x = 1` now throws in
        // strict mode instead of quietly bypassing the reducer. Nested objects and arrays
        // are still the live references, so callers that need to change one build a new
        // value and dispatch it, as they already do.
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