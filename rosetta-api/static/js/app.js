// Frontend logic for app functionality.

import { BASE_URL, getAuthHeaders, pollJobStatus } from './api.js';
import { updateAuthUI, verifySession } from './auth.js';
import { autosaveRun, initAutosave } from './autosave.js';
import { renderBatchQueue } from './batch.js';
import { bmLoadChecklist, populateBenchmarkSelectors } from './benchmarks_select.js';
import { checkRunCountLimits, getDynamicMaxQubits, getRunnerConfig, getRunnerPhases, getTargetSimulators, updateContextBar } from './config.js';
import { clearHistoryState, saveRunToHistory } from './history.js';
import { clearReport, renderDetailReport, renderSuiteSummary } from './renderers.js';
import { initDomRefs, qasmInput, setAllButtons, welcomeMessage } from './dom.js';
import { dispatch, getState } from './state.js';
import { getAgreementThresholds, getSeed, setLoading } from './utils.js';

window.onload = async () => {

    initDomRefs();
    setAllButtons([
        document.getElementById('btn-run'),
        document.getElementById('btn-batch-run')
    ]);

    updateAuthUI();
    verifySession();

    try {
        const [algorithmsResponse, configResponse] = await Promise.all([
            fetch(`${BASE_URL}/algorithms`, { headers: getAuthHeaders() }),
            fetch(`${BASE_URL}/config`),
        ]);
        if (!algorithmsResponse.ok) throw new Error('Failed to fetch algorithms');
        dispatch('SET_ALGORITHMS', await algorithmsResponse.json());
        if (configResponse.ok) {
            const config = await configResponse.json();
            dispatch('SET_CONFIG_LIMITS', config);
            // "Bypass API Safety Limits" is honoured by the API only in local mode;
            // hide it elsewhere so it cannot imply an effect it does not have.
            if (config.execution_mode !== 'local') {
                const bypassContainer = document.getElementById('bypass-limits-container');
                if (bypassContainer) bypassContainer.classList.add('hidden');
                const bypassCheckbox = document.getElementById('bypass-limits-checkbox');
                if (bypassCheckbox) bypassCheckbox.checked = false;
            }
        }

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

    toggleSingleMode();
    toggleBatchMode();
    populateBenchmarkSelectors();
    if (typeof bmLoadChecklist === 'function') bmLoadChecklist();

    if (getState().allAlgorithms.length > 0) {
        generateCircuit();
    }
    renderBatchQueue();
    if (typeof initAutosave === 'function') initAutosave();
};

export function updateQubitConstraints(e) {
    const algoId = document.getElementById('algo-select').value;
    const selectedAlgo = getState().allAlgorithms.find(a => a.id === algoId);
    const input = document.getElementById('algo-qubits');

    if (selectedAlgo) {
        if (selectedAlgo.min_qubits !== undefined) input.min = selectedAlgo.min_qubits;
        input.max = Math.min(selectedAlgo.max_qubits || 24, getDynamicMaxQubits());
        
        const isAlgoChange = e && e.type === 'change';
        if (isAlgoChange || !input.value) {
            if (selectedAlgo.default_qubits !== undefined) input.value = selectedAlgo.default_qubits;
        } else {
            let val = parseInt(input.value);
            if (!isNaN(val)) {
                if (val > input.max) input.value = input.max;
                if (val < input.min) input.value = input.min;
            }
        }

        if (selectedAlgo.min_qubits === selectedAlgo.max_qubits) {
            input.disabled = true;
        } else {
            input.disabled = false;
        }
    }
}

export async function generateCircuit() {
    if (getState().isProcessing) return;
    const algoId = document.getElementById('algo-select').value;
    const qubits = parseInt(document.getElementById('algo-qubits').value);

    if (!algoId || isNaN(qubits)) {
        alert("Please select an algorithm and specify a valid number of qubits.");
        return;
    }

    dispatch('SET_PROCESSING', true);
    setLoading(true, "Generating Circuit...", { overlay: false });
    try {
        const response = await fetch(`${BASE_URL}/generate_circuit`, {
            method: 'POST',
            headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ algorithm: algoId, qubits: qubits })
        });
        const data = await response.json();
        if (response.ok) {
            qasmInput.value = data.qasm;

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

export function toggleSingleMode() {
    const mode = document.querySelector('input[name="mode-single"]:checked').value;
    const shotsContainer = document.getElementById('shots-container-single');
    if (mode === 'measured') {
        shotsContainer.classList.remove('hidden');
    } else {
        shotsContainer.classList.add('hidden');
    }
    updateQubitConstraints();
}

export function toggleBatchMode() {
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

export function handleRun() {
    const mode = document.querySelector('input[name="mode-single"]:checked').value;
    const shots = parseInt(document.getElementById('shots-single').value) || 1024;
    runComparison(mode, shots);
}

export async function runComparison(type, shots) {
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
    const executionTarget = document.getElementById('execution-target-select')?.value || 'kubernetes';
    const bypassLimits = document.getElementById('bypass-limits-checkbox')?.checked || false;
    const applyPreprocessing = document.getElementById('apply-preprocessing-checkbox')?.checked ?? true;

    if (targetSims.length === 0) {
        alert("Please select at least one simulator from the Config Panel to run.");
        return;
    }

    if (!checkRunCountLimits(getState().currentRunnerConfig)) return;

    const payload = {
        qasm_string: qasm,
        optimization_level: globalOpt,
        timeout_seconds: timeout,
        runner_config: getState().currentRunnerConfig,
        runner_phases: getRunnerPhases(),
        target_simulators: targetSims,
        execution_target: executionTarget,
        bypass_limits: bypassLimits,
        apply_preprocessing: applyPreprocessing,
        thresholds: getAgreementThresholds()
    };

    if (type === 'measured') {
        payload.n_shots = shots;
        payload.seed = getSeed();  // null => backend generates and records a seed
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

        dispatch('SET_JOB_ID', jobData.job_id);
        dispatch('SET_SUITE_DATA', results);
        renderDetailReport(results, title, getState().currentRunnerConfig);

        if (runNameInput) results.run_name = runNameInput;
        const historyRunId = await saveRunToHistory(results);
        dispatch('SET_HISTORY_RUN_ID', historyRunId);
        if (typeof autosaveRun === 'function') autosaveRun(results, runNameInput || title);
    } catch (e) {
        console.error(e);
        renderDetailReport({ error: e.message }, "Error");
    } finally {
        setLoading(false);
        dispatch('SET_PROCESSING', false);
    }
}

export async function runBatchQueue() {
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
    const executionTarget = document.getElementById('execution-target-select')?.value || 'kubernetes';
    const bypassLimits = document.getElementById('bypass-limits-checkbox')?.checked || false;
    const applyPreprocessing = document.getElementById('apply-preprocessing-checkbox')?.checked ?? true;

    if (targetSims.length === 0) {
        alert("Please select at least one simulator from the Config Panel to run.");
        return;
    }

    if (!checkRunCountLimits(getState().currentRunnerConfig)) return;

    const payload = {
        tasks: getState().batchQueue,
        mode: mode,
        n_shots: shots,
        optimization_level: globalOpt,
        timeout_seconds: timeout,
        runner_config: getState().currentRunnerConfig,
        runner_phases: getRunnerPhases(),
        target_simulators: targetSims,
        execution_target: executionTarget,
        bypass_limits: bypassLimits,
        apply_preprocessing: applyPreprocessing,
        thresholds: getAgreementThresholds(),
        seed: getSeed()  // null => backend generates and records one global seed for the suite
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

        dispatch('SET_JOB_ID', jobData.job_id);
        dispatch('SET_SUITE_DATA', results);
        dispatch('SET_SUITE_TITLE', "Playlist Batch Report");
        renderSuiteSummary(results, getState().currentSuiteTitle);

        if (runNameInput) results.run_name = runNameInput;
        const historyRunId = await saveRunToHistory(results);
        dispatch('SET_HISTORY_RUN_ID', historyRunId);
        if (typeof autosaveRun === 'function') autosaveRun(results, runNameInput || 'batch');

    } catch (e) {
        console.error(e);
        renderSuiteSummary({ error: e.message }, "Batch Error");
    } finally {
        setLoading(false);
        dispatch('SET_PROCESSING', false);
    }
}
