// =============================================================================
// app.js — Application Controller (The Bootstrap)
// Responsibility: Global state, DOM references, window.onload initialization,
//                 circuit generation, run mode toggles, and core run dispatching.
// Depends on: api.js, config.js, batch.js, auth.js, history.js, utils.js, renderers.js
// =============================================================================

// --- FIX: Declare DOM elements here, define them in window.onload ---
let qasmInput, loader, tabNav, welcomeMessage, backButtonContainer, jsonOutput;
let playlistSection, queueList, queueCount;
let panelElements = {};
let allButtons = [];

// --- INIT ---
window.onload = async () => {
    // --- FIX: Define all DOM elements inside onload ---
    qasmInput = document.getElementById('qasm-input');
    loader = document.getElementById('loader');
    tabNav = document.getElementById('tab-nav');
    welcomeMessage = document.getElementById('welcome-message');
    backButtonContainer = document.getElementById('back-button-container');
    jsonOutput = document.getElementById('json-output');

    playlistSection = document.getElementById('playlist-section');
    queueList = document.getElementById('queue-list');
    queueCount = document.getElementById('queue-count');

    panelElements = {
        'summary': document.getElementById('summary-panel'),
        'performance': document.getElementById('performance-panel'),
        'resources': document.getElementById('resources-panel'),
        'divergence': document.getElementById('divergence-panel'),
        'raw': document.getElementById('raw-panel'),
        'suite-summary': document.getElementById('suite-summary-panel'),
        'visualizer': document.getElementById('visualizer-panel')
    };

    allButtons = [
        document.getElementById('btn-run'),
        document.getElementById('btn-batch-run')
    ];

    updateAuthUI();
    verifySession();

    try {
        const response = await fetch(`${BASE_URL}/algorithms`, {
            headers: getAuthHeaders()
        });
        if (!response.ok) throw new Error('Failed to fetch algorithms');
        dispatch('SET_ALGORITHMS', await response.json());

        const select = document.getElementById('algo-select');
        select.innerHTML = '';
        getState().allAlgorithms.forEach(algo => {
            const option = document.createElement('option');
            option.value = algo.id;
            option.textContent = algo.name;
            select.appendChild(option);
        });

        select.addEventListener('change', updateQubitConstraints);
        updateQubitConstraints();

        // Context Bar Init
        qasmInput.addEventListener('input', () => {
            dispatch('SET_CURRENT_ALGO_NAME', "Custom / Modified");
            updateContextBar();
        });
        updateContextBar();

    } catch (error) {
        console.error("Failed to load algorithms:", error);
        welcomeMessage.innerHTML = `<div class="p-4 bg-red-100 text-red-700 rounded"><strong>Connection Error:</strong> Could not load algorithms from ${BASE_URL}. Is the server running?</div>`;
        welcomeMessage.classList.remove('text-gray-500');
    }

    // Set initial UI states for both blocks
    toggleSingleMode();
    toggleBatchMode();
    // Only generate circuit if algorithms loaded
    if (getState().allAlgorithms.length > 0) {
        generateCircuit();
    }
    renderBatchQueue();
};

// --- METADATA UI LOGIC ---
function getDynamicMaxQubits() {
    const mode = document.querySelector('input[name="mode-single"]:checked')?.value || 'statevector';
    return mode === 'statevector' ? 18 : 24;
}

function updateQubitConstraints() {
    const algoId = document.getElementById('algo-select').value;
    const selectedAlgo = getState().allAlgorithms.find(a => a.id === algoId);
    const input = document.getElementById('algo-qubits');

    if (selectedAlgo) {
        if (selectedAlgo.min_qubits !== undefined) input.min = selectedAlgo.min_qubits;
        input.max = Math.min(selectedAlgo.max_qubits || 24, getDynamicMaxQubits());
        if (selectedAlgo.default_qubits !== undefined) input.value = selectedAlgo.default_qubits;

        if (selectedAlgo.min_qubits === selectedAlgo.max_qubits) {
            input.disabled = true;
        } else {
            input.disabled = false;
        }
    }
}

// --- CIRCUIT GENERATION ---
async function generateCircuit() {
    if (getState().isProcessing) return;
    const algoId = document.getElementById('algo-select').value;
    const qubits = parseInt(document.getElementById('algo-qubits').value);

    if (!algoId || isNaN(qubits)) {
        alert("Please select an algorithm and specify a valid number of qubits.");
        return;
    }

    dispatch('SET_PROCESSING', true);
    setLoading(true, "Generating Circuit...");
    try {
        const response = await fetch(`${BASE_URL}/generate_circuit`, {
            method: 'POST',
            headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ algorithm: algoId, qubits: qubits })
        });
        const data = await response.json();
        if (response.ok) {
            qasmInput.value = data.qasm;
            // Update Context
            const selectElement = document.getElementById('algo-select');
            dispatch('SET_CURRENT_ALGO_NAME', selectElement.options[selectElement.selectedIndex].text + ` (${qubits}q)`);
            updateContextBar();
        } else {
            throw new Error(data.error || "Failed to generate circuit.");
        }
    } catch (error) {
        console.error("Circuit generation failed:", error);
        alert("Circuit generation failed: " + error.message);
    } finally {
        setLoading(false);
        dispatch('SET_PROCESSING', false);
    }
}

// --- UI MODE TOGGLES ---
function toggleSingleMode() {
    const mode = document.querySelector('input[name="mode-single"]:checked').value;
    const shotsContainer = document.getElementById('shots-container-single');
    if (mode === 'measured') {
        shotsContainer.classList.remove('hidden');
    } else {
        shotsContainer.classList.add('hidden');
    }
    updateQubitConstraints();
}

function toggleBatchMode() {
    const mode = document.querySelector('input[name="mode-batch"]:checked').value;
    const shotsContainer = document.getElementById('shots-container-batch');
    const batchBtn = document.getElementById('btn-batch-run');

    if (mode === 'measured') {
        shotsContainer.classList.remove('hidden');
        batchBtn.textContent = "Run Batch (Measured)";
    } else {
        shotsContainer.classList.add('hidden');
        batchBtn.textContent = "Run Batch (Statevector)";
    }
}

function handleRun() {
    const mode = document.querySelector('input[name="mode-single"]:checked').value;
    const shots = parseInt(document.getElementById('shots-single').value) || 1024;
    runComparison(mode, shots);
}

// --- CORE RUN LOGIC ---
async function runComparison(type, shots) {
    clearHistoryState();
    if (getState().isProcessing) return;
    const qasm = qasmInput.value.trim();
    if (!qasm) { alert("Please enter QASM code."); return; }

    const globalOpt = parseInt(document.getElementById('opt-global')?.value || 0);
    const timeout = parseInt(document.getElementById('timeout-input')?.value || 300);
    const runNameInput = document.getElementById('single-run-name')?.value.trim();
    dispatch('SET_RUNNER_CONFIG', getRunnerConfig());

    const endpoint = type === 'statevector' ? '/compare' : '/compare_measured';
    const targetSims = getTargetSimulators();
    const executionTarget = document.getElementById('execution-target-select')?.value || 'rahti';

    if (targetSims.length === 0) {
        alert("Please select at least one simulator from the Config Panel to run.");
        return;
    }

    const payload = {
        qasm_string: qasm,
        optimization_level: globalOpt,
        timeout_seconds: timeout,
        runner_config: getState().currentRunnerConfig,
        target_simulators: targetSims,
        execution_target: executionTarget
    };

    if (type === 'measured') {
        payload.n_shots = shots;
    }

    const title = type === 'statevector' ? 'Editor Run (Statevector)' : `Editor Run (Measured, ${shots} shots)`;

    setLoading(true, "Running Simulation...");
    clearReport();

    try {
        dispatch('SET_PROCESSING', true);
        const res = await fetch(`${BASE_URL}${endpoint}`, {
            method: 'POST',
            headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const errorText = await res.text();
            throw new Error(`HTTP error! Status: ${res.status} ${res.statusText}. Details: ${errorText}`);
        }

        const jobData = await res.json();

        if (jobData.status === "failed") {
            throw new Error(jobData.error);
        }

        const results = await pollJobStatus(jobData.job_id);

        dispatch('SET_SUITE_DATA', results);
        renderDetailReport(results, title, getState().currentRunnerConfig);

        // Save to History
        if (runNameInput) results.run_name = runNameInput;
        await saveRunToHistory(results);
    } catch (e) {
        console.error(e);
        renderDetailReport({ error: e.message }, "Error");
    } finally {
        setLoading(false);
        dispatch('SET_PROCESSING', false);
    }
}

async function runBatchQueue() {
    clearHistoryState();
    if (getState().isProcessing) return;
    if (getState().batchQueue.length === 0) return;

    const mode = document.querySelector('input[name="mode-batch"]:checked').value;
    const shots = parseInt(document.getElementById('shots-batch').value) || 1024;
    const globalOpt = parseInt(document.getElementById('opt-global')?.value || 0);
    const timeout = parseInt(document.getElementById('timeout-input')?.value || 300);
    const runNameInput = document.getElementById('batch-run-name')?.value.trim();
    dispatch('SET_RUNNER_CONFIG', getRunnerConfig());
    const targetSims = getTargetSimulators();
    const executionTarget = document.getElementById('execution-target-select')?.value || 'rahti';

    if (targetSims.length === 0) {
        alert("Please select at least one simulator from the Config Panel to run.");
        return;
    }

    const payload = {
        tasks: getState().batchQueue,
        mode: mode,
        n_shots: shots,
        optimization_level: globalOpt,
        timeout_seconds: timeout,
        runner_config: getState().currentRunnerConfig,
        target_simulators: targetSims,
        execution_target: executionTarget
    };

    setLoading(true, `Running Batch of ${getState().batchQueue.length} Circuits...`);
    clearReport();

    try {
        dispatch('SET_PROCESSING', true);
        const res = await fetch(`${BASE_URL}/run_batch_suite`, {
            method: 'POST',
            headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const errorText = await res.text();
            throw new Error(`HTTP error! Status: ${res.status}. Details: ${errorText}`);
        }

        const jobData = await res.json();

        if (jobData.status === "failed") {
            throw new Error(jobData.error);
        }

        const results = await pollJobStatus(jobData.job_id);

        dispatch('SET_SUITE_DATA', results);
        dispatch('SET_SUITE_TITLE', "Playlist Batch Report");
        renderSuiteSummary(results, getState().currentSuiteTitle);

        // Save to History
        if (runNameInput) results.run_name = runNameInput;
        await saveRunToHistory(results);

    } catch (e) {
        console.error(e);
        renderSuiteSummary({ error: e.message }, "Batch Error");
    } finally {
        setLoading(false);
        dispatch('SET_PROCESSING', false);
    }
}
