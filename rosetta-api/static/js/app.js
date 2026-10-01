// Page bootstrap, single-circuit and batch run orchestration, and circuit generation.

import { BASE_URL, apiDetailText, formatApiError, getAuthHeaders, pollJobStatus } from './api.js';
import { updateAuthUI, verifySession } from './auth.js';
import { autosaveRun, initAutosave } from './autosave.js';
import { getCompilerSelection, loadCompilers } from './compilers_config.js';
import { renderBatchQueue, toBatchTask } from './batch.js';
import { closeDrawers } from './drawers.js';
import { bmLoadChecklist, populateBenchmarkSelectors } from './benchmarks_select.js';
import {
    checkRunCountLimits, getDynamicMaxQubits, getRunnerConfig, getRunnerPhases, getTargetSimulators,
    loadRunners, runnerSelectionProblem, updateContextBar,
} from './config.js';
import { clearHistoryState, saveRunToHistory, showHistoryNotice } from './history.js';
import { clearReport, renderDetailReport, renderSuiteSummary } from './renderers.js';
import { initDomRefs, qasmInput, setAllButtons, welcomeMessage } from './dom.js';
import { shotsRange, showRunErrors, timeoutRange, validateRunInputs } from './run_inputs.js';
import { clearPendingJob, loadEditorCircuit, loadPendingJob, saveEditorCircuit, savePendingJob } from './session_store.js';
import { dispatch, getState } from './state.js';
import { getAgreementThresholds, getSeed, resetAgreementThresholds, setLoading } from './utils.js';

const EXECUTION_MODE_LABELS = {
    local: 'This server: local runner services',
    kubernetes: 'This server: Kubernetes Jobs',
};

/** Execution-target menu, timeout and shots bounds, and threshold defaults from GET /config. */
function _applyServerConfig(config) {
    const mode = getState().executionMode;
    const select = /** @type {HTMLSelectElement|null} */ (document.getElementById('execution-target-select'));
    if (select && mode) {
        select.innerHTML = '';
        const opt = document.createElement('option');
        opt.value = mode;
        opt.textContent = EXECUTION_MODE_LABELS[mode] || mode;
        select.appendChild(opt);
        select.value = mode;
        select.disabled = true;
    }

    const { min: tMin, max: tMax } = timeoutRange();
    const tInput = /** @type {HTMLInputElement|null} */ (document.getElementById('timeout-input'));
    if (tInput) {
        tInput.min = String(tMin);
        tInput.max = String(tMax);
        const current = Number(tInput.value);
        if (!Number.isFinite(current) || current > tMax) tInput.value = String(tMax);
    }
    const tHelp = document.getElementById('timeout-help');
    if (tHelp) {
        tHelp.textContent = `This value is sent with every run from this page. It covers process start, SDK import, `
            + `the warm-up run and the timed runs of each backend. Allowed: ${tMin}–${tMax} s.`
            + (typeof config?.queue_max_wait_sec === 'number' && mode === 'local'
                ? ` Time spent waiting for a busy runner is not part of it; a run waits at most ${config.queue_max_wait_sec} s to start.`
                : '');
    }

    const { min: sMin, max: sMax } = shotsRange();
    ['shots-single', 'shots-batch'].forEach(id => {
        const el = /** @type {HTMLInputElement|null} */ (document.getElementById(id));
        if (!el) return;
        el.min = String(sMin);
        if (sMax !== null && sMax !== undefined) el.max = String(sMax);
        const dflt = config?.default_n_shots ?? config?.limits?.default_n_shots;
        if (typeof dflt === 'number' && Number.isInteger(dflt) && el.value === el.defaultValue) {
            el.value = String(dflt);
            el.defaultValue = String(dflt);
        }
    });

    if (config.agreement_threshold_defaults) resetAgreementThresholds();
}

/** The execution target to send: the server's mode, or undefined when it is not known. */
function _executionTarget() {
    const v = /** @type {HTMLSelectElement|null} */ (document.getElementById('execution-target-select'))?.value;
    return v || getState().executionMode || undefined;
}

/** Name of the circuit in the editor for report figures, or null for an unnamed custom circuit. */
function _editorCircuitName() {
    const name = getState().currentAlgoName;
    return name && !/^Custom\b/.test(name) ? name : null;
}

let _editorSaveTimer = null;
function _saveEditorSoon() {
    if (_editorSaveTimer) clearTimeout(_editorSaveTimer);
    _editorSaveTimer = setTimeout(() => {
        saveEditorCircuit(qasmInput.value, getState().currentAlgoName);
    }, 400);
}

function _restoreEditorCircuit() {
    const saved = loadEditorCircuit();
    if (!saved) return false;
    qasmInput.value = saved.qasm;
    dispatch('SET_CURRENT_ALGO_NAME', saved.name);
    updateContextBar();
    return true;
}

function _hideResumeBanner() {
    document.getElementById('resume-job-banner')?.classList.add('hidden');
}

function _offerPendingJob() {
    const job = loadPendingJob();
    const banner = document.getElementById('resume-job-banner');
    if (!job || !banner) return;
    const when = new Date(job.submitted_at).toLocaleTimeString();
    const what = job.kind === 'batch' ? 'A batch run' : 'A run';
    const text = document.getElementById('resume-job-text');
    if (text) text.textContent = `${what} submitted at ${when} (${job.run_name || job.title}) had not finished loading when the page was closed.`;
    banner.classList.remove('hidden');
    document.getElementById('resume-job-btn')?.addEventListener('click', () => {
        _hideResumeBanner();
        if (getState().isProcessing) return;
        if (job.kind === 'batch') _finishBatchRun(job);
        else _finishSingleRun(job);
    }, { once: true });
    document.getElementById('resume-job-discard')?.addEventListener('click', () => {
        clearPendingJob(job.job_id);
        _hideResumeBanner();
    }, { once: true });
}

window.onload = async () => {

    initDomRefs();
    document.getElementById('history-save-notice-close')?.addEventListener('click', () => showHistoryNotice(''));
    setAllButtons([
        document.getElementById('btn-run'),
        document.getElementById('btn-batch-run')
    ]);

    updateAuthUI();
    verifySession();

    let restored = false;
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
            _applyServerConfig(config);
            // The API honours bypass_limits only in local mode.
            if (config.execution_mode !== 'local') {
                const bypassContainer = document.getElementById('bypass-limits-container');
                if (bypassContainer) bypassContainer.classList.add('hidden');
                const bypassCheckbox = document.getElementById('bypass-limits-checkbox');
                if (bypassCheckbox) bypassCheckbox.checked = false;
            }
        }
        loadRunners();
        loadCompilers();

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
            _saveEditorSoon();
        });
        restored = _restoreEditorCircuit();
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

    if (!restored && getState().allAlgorithms.length > 0) {
        generateCircuit();
    }
    renderBatchQueue();
    if (typeof initAutosave === 'function') initAutosave();
    _offerPendingJob();
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
            saveEditorCircuit(qasmInput.value, getState().currentAlgoName);
        } else {
            throw new Error(apiDetailText(data.detail) || data.error || "Failed to generate circuit.");
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
    runComparison(mode);
}

/** Validate the inputs and the backend selection; shows the problems next to the run button. */
async function _checkBeforeRun(messageId, shotsId, measured) {
    const v = validateRunInputs({ shotsId, measured });
    if (!v.ok) {
        showRunErrors(messageId, v.errors);
        return null;
    }
    await loadRunners();
    const problem = runnerSelectionProblem();
    if (problem) {
        showRunErrors(messageId, [problem]);
        return null;
    }
    showRunErrors(messageId, []);
    return v;
}

async function _finishSingleRun(job) {
    setLoading(true, "Running Simulation...", { startedAt: job.submitted_at });
    clearReport();
    dispatch('SET_PROCESSING', true);
    dispatch('SET_JOB_ID', job.job_id);
    try {
        const results = await pollJobStatus(job.job_id);
        clearPendingJob(job.job_id);
        if (job.run_name) results.run_name = job.run_name;
        if (job.circuit_name && !results.circuit_name) results.circuit_name = job.circuit_name;
        dispatch('SET_SUITE_DATA', results);
        renderDetailReport(results, job.title, job.runner_config || {});

        const historyRunId = await saveRunToHistory(job.job_id, job.run_name || null);
        dispatch('SET_HISTORY_RUN_ID', historyRunId);
        if (typeof autosaveRun === 'function') autosaveRun(results, job.run_name || job.title);
    } catch (e) {
        console.error(e);
        if (e && e.terminal) clearPendingJob(job.job_id);
        dispatch('SET_JOB_ID', null);
        renderDetailReport({ error: e.message }, "Error");
    } finally {
        setLoading(false);
        dispatch('SET_PROCESSING', false);
    }
}

async function _finishBatchRun(job) {
    setLoading(true, 'Running Batch...', { startedAt: job.submitted_at });
    clearReport();
    dispatch('SET_PROCESSING', true);
    dispatch('SET_JOB_ID', job.job_id);
    try {
        const results = await pollJobStatus(job.job_id);
        clearPendingJob(job.job_id);
        if (job.run_name) results.run_name = job.run_name;
        dispatch('SET_SUITE_DATA', results);
        dispatch('SET_SUITE_TITLE', job.title);
        renderSuiteSummary(results, getState().currentSuiteTitle);

        const historyRunId = await saveRunToHistory(job.job_id, job.run_name || null);
        dispatch('SET_HISTORY_RUN_ID', historyRunId);
        if (typeof autosaveRun === 'function') autosaveRun(results, job.run_name || 'batch');
    } catch (e) {
        console.error(e);
        if (e && e.terminal) clearPendingJob(job.job_id);
        dispatch('SET_JOB_ID', null);
        renderSuiteSummary({ error: e.message }, "Batch Error");
    } finally {
        setLoading(false);
        dispatch('SET_PROCESSING', false);
    }
}

/** POST a run; returns the job id, or throws with the server's error text. */
async function _submit(endpoint, payload) {
    const res = await fetch(`${BASE_URL}${endpoint}`, {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error(await formatApiError(res));
    const jobData = await res.json();
    if (jobData.status === "failed") throw new Error(jobData.error || 'The server rejected the job without an error message.');
    return jobData.job_id;
}

export async function runComparison(type) {
    clearHistoryState();
    if (getState().isProcessing) return;
    const qasm = qasmInput.value.trim();
    if (!qasm) {
        showRunErrors('single-validation-msg', ['The editor is empty. Enter or generate an OpenQASM 2.0 circuit.']);
        return;
    }

    const v = await _checkBeforeRun('single-validation-msg', 'shots-single', type === 'measured');
    if (!v) return;

    const globalOpt = parseInt(document.getElementById('opt-global')?.value || 0);
    const runNameInput = document.getElementById('single-run-name')?.value.trim();
    dispatch('SET_RUNNER_CONFIG', getRunnerConfig());

    const endpoint = type === 'statevector' ? '/compare' : '/compare_measured';
    const targetSims = getTargetSimulators();
    const bypassLimits = document.getElementById('bypass-limits-checkbox')?.checked || false;
    const applyPreprocessing = document.getElementById('apply-preprocessing-checkbox')?.checked ?? true;

    if (!checkRunCountLimits(getState().currentRunnerConfig)) return;

    const payload = {
        qasm_string: qasm,
        optimization_level: globalOpt,
        timeout_seconds: v.timeout,
        timing_repeats: v.timingRepeats,
        exclusive: /** @type {HTMLInputElement | null} */ (document.getElementById('exclusive-checkbox'))?.checked || false,
        runner_config: getState().currentRunnerConfig,
        runner_phases: getRunnerPhases(),
        target_simulators: targetSims,
        execution_target: _executionTarget(),
        bypass_limits: bypassLimits,
        apply_preprocessing: applyPreprocessing,
        thresholds: getAgreementThresholds(),
        compilers: getCompilerSelection()
    };

    if (type === 'measured') {
        payload.n_shots = v.shots;
        payload.seed = getSeed();
    }

    const modeText = type === 'statevector' ? 'Statevector' : `Measured, ${v.shots} shots`;
    const title = `${runNameInput || 'Editor Run'} (${modeText})`;
    saveEditorCircuit(qasmInput.value, getState().currentAlgoName);
    _hideResumeBanner();
    closeDrawers();

    setLoading(true, "Running Simulation...");
    clearReport();
    dispatch('SET_JOB_ID', null);

    let jobId;
    try {
        dispatch('SET_PROCESSING', true);
        jobId = await _submit(endpoint, payload);
    } catch (e) {
        console.error(e);
        renderDetailReport({ error: e.message }, "Error");
        setLoading(false);
        dispatch('SET_PROCESSING', false);
        return;
    }
    const job = {
        job_id: jobId, kind: /** @type {'single'} */ ('single'), title, run_name: runNameInput || null,
        circuit_name: _editorCircuitName(), runner_config: getState().currentRunnerConfig, submitted_at: Date.now(),
    };
    savePendingJob(job);
    await _finishSingleRun(job);
}

export async function runBatchQueue() {
    clearHistoryState();
    if (getState().isProcessing) return;
    if (getState().batchQueue.length === 0) {
        showRunErrors('batch-validation-msg', ['The batch queue is empty. Add circuits first.']);
        return;
    }

    const mode = document.querySelector('input[name="mode-batch"]:checked').value;
    const v = await _checkBeforeRun('batch-validation-msg', 'shots-batch', mode === 'measured');
    if (!v) return;

    const globalOpt = parseInt(document.getElementById('opt-global')?.value || 0);
    const runNameInput = document.getElementById('batch-run-name')?.value.trim();
    dispatch('SET_RUNNER_CONFIG', getRunnerConfig());
    const targetSims = getTargetSimulators();
    const bypassLimits = document.getElementById('bypass-limits-checkbox')?.checked || false;
    const applyPreprocessing = document.getElementById('apply-preprocessing-checkbox')?.checked ?? true;

    if (!checkRunCountLimits(getState().currentRunnerConfig)) return;

    const payload = {
        tasks: getState().batchQueue.map(toBatchTask),
        mode: mode,
        optimization_level: globalOpt,
        timeout_seconds: v.timeout,
        timing_repeats: v.timingRepeats,
        exclusive: /** @type {HTMLInputElement | null} */ (document.getElementById('exclusive-checkbox'))?.checked || false,
        runner_config: getState().currentRunnerConfig,
        runner_phases: getRunnerPhases(),
        target_simulators: targetSims,
        execution_target: _executionTarget(),
        bypass_limits: bypassLimits,
        apply_preprocessing: applyPreprocessing,
        thresholds: getAgreementThresholds(),
        seed: getSeed(),
        compilers: getCompilerSelection()
    };
    if (mode === 'measured') payload.n_shots = v.shots;

    _hideResumeBanner();
    closeDrawers();
    setLoading(true, `Running Batch of ${getState().batchQueue.length} Circuits...`);
    clearReport();
    dispatch('SET_JOB_ID', null);

    let jobId;
    try {
        dispatch('SET_PROCESSING', true);
        jobId = await _submit('/run_batch_suite', payload);
    } catch (e) {
        console.error(e);
        renderSuiteSummary({ error: e.message }, "Batch Error");
        setLoading(false);
        dispatch('SET_PROCESSING', false);
        return;
    }
    const job = {
        job_id: jobId, kind: /** @type {'batch'} */ ('batch'), title: runNameInput || 'Playlist Batch Report',
        run_name: runNameInput || null, runner_config: getState().currentRunnerConfig, submitted_at: Date.now(),
    };
    savePendingJob(job);
    await _finishBatchRun(job);
}
