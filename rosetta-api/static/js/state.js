// Frontend logic for state functionality.

const Store = {
    state: {
        authToken: localStorage.getItem('rosetta_token') || null,
        isProcessing: false,
        currentSuiteData: null,
        currentSuiteTitle: '',
        batchQueue: [],
        allAlgorithms: [],
        currentOptLevel: 0,
        currentAlgoName: "Custom",
        currentRunnerConfig: {}
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
            case 'SET_OPT_LEVEL':
                this.state.currentOptLevel = payload;
                break;
            case 'SET_CURRENT_ALGO_NAME':
                this.state.currentAlgoName = payload;
                break;
            case 'SET_RUNNER_CONFIG':
                this.state.currentRunnerConfig = payload;
                break;
            default:
                console.warn(`[State] Unknown action: ${action}`);
        }
    },

    getState() {
        return this.state;
    }
};

window.dispatch = (action, payload) => Store.dispatch(action, payload);
window.getState = () => Store.getState();