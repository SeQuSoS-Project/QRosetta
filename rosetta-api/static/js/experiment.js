// Reproducible experiment runner — front end.
//
// Runs the batch queue (presets / benchmarks / uploaded QASM) over one or more preprocessing
// axes via POST /experiments, then downloads the frozen artifact bundle from
// GET /experiments/{id}/bundle. The "Run Experiment" button routes here; "Run Batch" is
// separate. The conformance and prevalence outputs are reported separately.

import { BASE_URL, formatApiError, getAuthHeaders, pollJobStatus } from './api.js';
import { checkRunCountLimits, getRunnerConfig, getRunnerPhases, getTargetSimulators, loadRunners, runnerSelectionProblem } from './config.js';
import { showRunErrors, validateRunInputs } from './run_inputs.js';
import { clearReport } from './renderers.js';
import { dispatch, getState } from './state.js';
import { _escapeHtml, downloadBlob, getAgreementThresholds, getSeed, setLoading } from './utils.js';

export let _lastExperimentJobId = null;
export let _lastExperimentName = 'experiment';

export function toggleExperimentMode() {
    const on = document.getElementById('experiment-toggle')?.checked;
    const controls = document.getElementById('experiment-controls');
    if (controls) controls.classList.toggle('hidden', !on);
}

// Map a batch-queue item to an ExperimentCircuit. Items are benchmark refs
// ({source:'mqt'|'qasmbench', algorithm, qubits}), literal QASM ({qasm_string}/{qasm}), or
// presets ({algorithm, qubits}). Benchmark refs stay references so the server resolves them.
export function _queueItemToCircuit(item) {
    if (item.source === 'mqt' || item.source === 'qasmbench') {
        return {
            source: item.source, algorithm: item.algorithm,
            qubits: parseInt(item.qubits) || 0, name: item.name || item.algorithm,
        };
    }
    const qasm = item.qasm_string || item.qasm;
    if (qasm) {
        return {
            source: 'qasm', qasm_string: qasm,
            name: item.name || item.algorithm || 'circuit',
            qubits: parseInt(item.qubits) || 0,
        };
    }
    return {
        source: 'preset', algorithm: item.algorithm,
        qubits: parseInt(item.qubits) || 0, name: item.name || null,
    };
}

export async function runExperiment() {
    if (getState().isProcessing) return;
    const queue = getState().batchQueue || [];
    if (queue.length === 0) { alert('Add circuits to the batch queue first.'); return; }

    const axes = [];
    if (document.getElementById('exp-axis-on')?.checked) axes.push(true);
    if (document.getElementById('exp-axis-off')?.checked) axes.push(false);
    if (axes.length === 0) { alert('Select at least one preprocessing axis.'); return; }

    const mode = document.querySelector('input[name="mode-batch"]:checked').value;
    const v = validateRunInputs({ shotsId: 'shots-batch', measured: mode === 'measured' });
    if (!v.ok) { showRunErrors('batch-validation-msg', v.errors); return; }
    await loadRunners();
    const problem = runnerSelectionProblem();
    if (problem) { showRunErrors('batch-validation-msg', [problem]); return; }
    showRunErrors('batch-validation-msg', []);

    const targetSims = getTargetSimulators();
    const shots = mode === 'measured' ? v.shots : undefined;
    const globalOpt = parseInt(document.getElementById('opt-global')?.value || 0);
    const timeout = v.timeout;
    const executionTarget = /** @type {HTMLSelectElement|null} */ (document.getElementById('execution-target-select'))?.value
        || getState().executionMode || undefined;
    const bypassLimits = document.getElementById('bypass-limits-checkbox')?.checked || false;
    const label = document.getElementById('experiment-name')?.value.trim() || null;

    dispatch('SET_RUNNER_CONFIG', getRunnerConfig());
    if (!checkRunCountLimits(getState().currentRunnerConfig)) return;

    const circuits = queue.map(_queueItemToCircuit);
    const payload = {
        circuits,
        mode,
        n_shots: shots,
        optimization_level: globalOpt,
        runner_config: getState().currentRunnerConfig,
        runner_phases: getRunnerPhases(),
        timeout_seconds: timeout,
        target_simulators: targetSims,
        execution_target: executionTarget,
        bypass_limits: bypassLimits,
        preprocessing_modes: axes,
        seed: getSeed(),                 // null => backend generates + records one shared seed
        thresholds: getAgreementThresholds(),
        label,
    };

    _lastExperimentName = label ? label.replace(/[^A-Za-z0-9_-]+/g, '_') : 'experiment';
    _hideExperimentResult();
    setLoading(true, `Running experiment: ${circuits.length} circuit(s) × ${axes.length} axis(es)…`);
    clearReport();

    try {
        dispatch('SET_PROCESSING', true);
        const res = await fetch(`${BASE_URL}/experiments`, {
            method: 'POST',
            headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error(await formatApiError(res));
        const jobData = await res.json();
        if (jobData.status === 'failed') throw new Error(jobData.error);

        const results = await pollJobStatus(jobData.job_id);
        _lastExperimentJobId = jobData.job_id;
        renderExperimentResult(results);
    } catch (e) {
        console.error(e);
        alert(`Experiment failed: ${e.message}`);
    } finally {
        dispatch('SET_PROCESSING', false);
        setLoading(false);
    }
}

export function _hideExperimentResult() {
    document.getElementById('experiment-result')?.classList.add('hidden');
}

export function renderExperimentResult(results) {
    const summary = results && results.experiment_summary;
    const box = document.getElementById('experiment-result');
    const line = document.getElementById('experiment-summary-line');
    if (!summary || !box || !line) return;

    const nCircuits = (summary.circuits || []).length;
    const nAxes = (summary.axes || []).length;
    const nErr = summary.error_count || 0;
    const nResolve = (summary.resolution_errors || []).length;

    // Prevalence rollup across axes (kept SEPARATE from the conformance/error counts above).
    const prev = {};
    for (const r of (summary.prevalence || [])) {
        prev[r.agreement_class] = (prev[r.agreement_class] || 0) + r.pair_count;
    }
    const prevText = Object.keys(prev).length
        ? Object.entries(prev).map(([k, v]) => `${k}: ${v}`).join(' · ')
        : 'none';

    line.innerHTML =
        `<div class="font-medium mb-1">Experiment complete — ${summary.cells} circuit-axis run(s), `
        + `${nCircuits} circuit(s) × ${nAxes} axis(es).</div>`
        + `<div><span class="font-medium">Agreement prevalence:</span> ${_escapeHtml(prevText)}</div>`
        + `<div><span class="font-medium">Errors to triage:</span> ${nErr}`
        + (nResolve ? ` &nbsp;·&nbsp; resolution errors: ${nResolve}` : '')
        + `</div>`
        + `<div class="text-[11px] text-yellow-700 mt-1">Each error signature carries a `
        + `triage='untriaged' marker; classify it as adapter / SDK / by-design / resource.</div>`;
    box.classList.remove('hidden');
}

export async function downloadExperimentBundle() {
    if (!_lastExperimentJobId) { alert('Run an experiment first.'); return; }
    try {
        const res = await fetch(`${BASE_URL}/experiments/${_lastExperimentJobId}/bundle`, {
            headers: getAuthHeaders(),
        });
        if (!res.ok) {
            throw new Error(`Download failed: ${res.status}. ${await res.text()}`);
        }
        downloadBlob(await res.blob(), `${_lastExperimentName || 'experiment'}.zip`);
    } catch (e) {
        console.error(e);
        alert(e.message);
    }
}

