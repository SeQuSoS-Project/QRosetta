// The workspace: which circuits, which runs and which settings one press of Run uses; the
// Run button's label; submitting the planned jobs one after another; showing their results
// with a switcher when there are several; resuming a job after a reload.

import { BASE_URL, formatApiError, getAuthHeaders, pollJobStatus, stopPolling } from './api.js';
import { autosaveRun } from './autosave.js';
import { getCompilerSelection } from './compilers_config.js';
import {
    _parseQasmStats, checkRunCountLimits, getEnabledRunnerIds, getRunnerConfig, getRunnerPhases, getTargetSimulators, loadRunners,
    runnerSelectionProblem, updateContextBar,
} from './config.js';
import { qasmInput } from './dom.js';
import { renderExperimentResult } from './experiment.js';
import { clearHistoryState, saveRunToHistory } from './history.js';
import { clearReport, renderDetailReport, renderSuiteSummary, showTab } from './renderers.js';
import { planRuns, runButtonLabel } from './run_plan.js';
import { showRunErrors, validateRunInputs } from './run_inputs.js';
import { clearPendingJob, saveEditorCircuit, savePendingJob } from './session_store.js';
import { dispatch, getState } from './state.js';
import { getAgreementThresholds, getSeed, setLoading } from './utils.js';
import { batchItemLabel, renderBatchQueue } from './batch.js';
import { exampleOptions } from './circuit_sources.js';
import { emptyStateModel, renderEmptyState } from './empty_state.js';
import { _displayRunnerName } from './render_helpers.js';

const _checked = id => !!/** @type {HTMLInputElement|null} */ (document.getElementById(id))?.checked;
const _radio = name => /** @type {HTMLInputElement|null} */ (document.querySelector(`input[name="${name}"]:checked`))?.value;

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

/** The workspace as planRuns() reads it; `shots` and `timeout` come from validated inputs. */
export function readWorkspace(validated = null) {
    const compilers = getCompilerSelection();
    return {
        source: /** @type {'list'|'editor'} */ (_radio('run-source') === 'list' ? 'list' : 'editor'),
        editor: { qasm: qasmInput?.value || '', name: getState().currentAlgoName || '' },
        list: getState().batchQueue || [],
        modes: { statevector: _checked('mode-statevector'), measured: _checked('mode-measured') },
        compilers,
        preprocessing: /** @type {'on'|'off'|'both'} */ (_radio('preprocessing') || 'on'),
        runName: /** @type {HTMLInputElement|null} */ (document.getElementById('single-run-name'))?.value.trim() || '',
        shots: validated?.shots ?? null,
        seed: getSeed(),
        common: {
            optimization_level: parseInt(/** @type {HTMLSelectElement|null} */ (document.getElementById('opt-global'))?.value || '0', 10),
            timeout_seconds: validated?.timeout,
            timing_repeats: validated?.timingRepeats ?? 1,
            exclusive: _checked('exclusive-checkbox'),
            runner_config: getRunnerConfig(),
            runner_phases: getRunnerPhases(),
            target_simulators: getTargetSimulators(),
            execution_target: _executionTarget(),
            bypass_limits: _checked('bypass-limits-checkbox'),
            thresholds: getAgreementThresholds(),
        },
    };
}

/** Run button colours, as the separate run buttons had them: editor blue, batch yellow, experiment emerald. */
const RUN_THEMES = {
    editor: ['bg-blue-600', 'hover:bg-blue-700', 'focus:ring-blue-500'],
    batch: ['bg-yellow-600', 'hover:bg-yellow-700', 'focus:ring-yellow-500'],
    experiment: ['bg-emerald-600', 'hover:bg-emerald-700', 'focus:ring-emerald-500'],
};

/** Refresh everything that depends on the workspace: shots field, compiler line, counts, Run label. */
export function updateWorkspace() {
    const ws = readWorkspace({ shots: 1 });
    document.getElementById('shots-container-single')?.classList.toggle('hidden', !ws.modes.measured);
    const count = document.getElementById('run-source-count');
    if (count) count.textContent = String(ws.list.length);
    const listRadio = /** @type {HTMLInputElement|null} */ (document.querySelector('input[name="run-source"][value="list"]'));
    if (listRadio) listRadio.disabled = ws.list.length === 0;
    if (ws.list.length === 0 && ws.source === 'list') {
        const editorRadio = /** @type {HTMLInputElement|null} */ (document.querySelector('input[name="run-source"][value="editor"]'));
        if (editorRadio) editorRadio.checked = true;
        ws.source = 'editor';
    }
    const button = document.getElementById('btn-run');
    if (button) {
        button.textContent = runButtonLabel(ws, ws.common.target_simulators.length);
        const theme = ws.preprocessing === 'both' ? RUN_THEMES.experiment : ws.source === 'list' ? RUN_THEMES.batch : RUN_THEMES.editor;
        Object.values(RUN_THEMES).flat().forEach(c => button.classList.remove(c));
        theme.forEach(c => button.classList.add(c));
    }
    const note = document.getElementById('run-save-note');
    if (note) {
        note.textContent = getState().authToken
            ? 'Runs are saved to your History.'
            : 'Not signed in: results are kept for 30 minutes.';
    }
    _showLimitWarning(ws);
    _renderEmptyState(ws);
}

/** The results area before a result: what Run will do and the table it will fill. */
function _renderEmptyState(ws) {
    const model = emptyStateModel({
        source: ws.source,
        circuitName: ws.editor.name,
        playlist: ws.list.map(batchItemLabel),
        modes: ws.modes,
        preprocessing: ws.preprocessing,
        compilerCount: Object.values(ws.compilers).reduce((n, levels) => n + levels.length, 0),
        backends: [...ws.common.target_simulators].sort().map(_displayRunnerName),
        backendsLoaded: getEnabledRunnerIds().length > 0,
        examples: exampleOptions(),
    });
    renderEmptyState(document.getElementById('empty-state'), model, {
        onExample: value => document.dispatchEvent(new CustomEvent('open-circuit', { detail: value })),
    });
}

/** Warn before a run when the circuits exceed a ticked mode's qubit limit. */
function _showLimitWarning(ws) {
    const box = document.getElementById('run-limit-warning');
    if (!box) return;
    const qubits = ws.source === 'list'
        ? Math.max(0, ...ws.list.map(item => parseInt(item.qubits) || 0))
        : _parseQasmStats(ws.editor.qasm).qubits;
    const { maxQubitsStatevector: sv, maxQubitsMeasured: ms } = getState();
    const what = ws.source === 'list' ? `The largest playlist circuit has ${qubits} qubits` : `This circuit has ${qubits} qubits`;
    const notes = [];
    if (ws.modes.statevector && qubits > sv) notes.push(`statevector runs allow ${sv}`);
    if (ws.modes.measured && qubits > ms) notes.push(`measured runs allow ${ms}`);
    box.textContent = notes.length ? `${what}; ${notes.join(' and ')}.` : '';
    box.classList.toggle('hidden', !notes.length);
}

/** Select the playlist as what runs, once it has circuits. */
export function selectListSource() {
    const listRadio = /** @type {HTMLInputElement|null} */ (document.querySelector('input[name="run-source"][value="list"]'));
    if (listRadio && (getState().batchQueue || []).length) listRadio.checked = true;
    updateWorkspace();
    const label = document.getElementById('run-source-list-label');
    if (label) {
        label.classList.add('ring-2', 'ring-yellow-400');
        setTimeout(() => label.classList.remove('ring-2', 'ring-yellow-400'), 900);
    }
}

async function _submit(endpoint, payload) {
    const res = await fetch(`${BASE_URL}${endpoint}`, {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await formatApiError(res));
    const jobData = await res.json();
    if (jobData.status === 'failed') throw new Error(jobData.error || 'The server rejected the job without an error message.');
    return jobData.job_id;
}

/** Wait for one job and turn it into a finished entry: {job, results} or {job, error, stopped}. */
async function _await(job) {
    try {
        const results = await pollJobStatus(job.job_id);
        clearPendingJob(job.job_id);
        if (job.run_name) results.run_name = job.run_name;
        if (job.circuit_name && !results.circuit_name) results.circuit_name = job.circuit_name;
        let historyRunId = null;
        if (job.kind !== 'experiment') {
            historyRunId = await saveRunToHistory(job.job_id, job.run_name || null);
            autosaveRun(results, job.run_name || job.title);
        }
        return { job, results, historyRunId };
    } catch (e) {
        console.error(e);
        if (e && e.terminal) clearPendingJob(job.job_id);
        return { job, error: e.message, stopped: !!(e && e.stopped) };
    }
}

let _finished = [];

/** Show one finished entry in the results panel. */
function _show(index) {
    const entry = _finished[index];
    if (!entry) return;
    const { job } = entry;
    dispatch('SET_JOB_ID', entry.results ? job.job_id : null);
    dispatch('SET_HISTORY_RUN_ID', entry.historyRunId ?? null);
    if (job.kind === 'experiment') {
        dispatch('SET_SUITE_DATA', null);
        const panel = document.getElementById('experiment-panel');
        if (panel) {
            if (entry.results) renderExperimentResult(entry.results, panel, { jobId: job.job_id, name: job.run_name || job.title, title: job.title });
            else panel.textContent = entry.error;
        }
        document.getElementById('tab-nav')?.replaceChildren();
        document.getElementById('back-button-container')?.classList.add('hidden');
        showTab('experiment');
    } else if (job.kind === 'batch') {
        dispatch('SET_SUITE_DATA', entry.results || null);
        dispatch('SET_SUITE_TITLE', job.title);
        renderSuiteSummary(entry.results || { error: entry.error }, entry.results ? job.title : `${job.title}: error`);
    } else {
        dispatch('SET_SUITE_DATA', entry.results || null);
        renderDetailReport(entry.results || { error: entry.error }, entry.results ? job.title : 'Error', job.runner_config || {});
    }
    _renderSwitcher(index);
}

function _renderSwitcher(active) {
    const host = document.getElementById('run-switcher');
    if (!host) return;
    host.replaceChildren();
    host.classList.toggle('hidden', _finished.length < 2);
    if (_finished.length < 2) return;
    const label = document.createElement('span');
    label.className = 'text-gray-500';
    label.textContent = 'Runs started together:';
    host.appendChild(label);
    _finished.forEach((entry, i) => {
        const b = document.createElement('button');
        b.type = 'button';
        b.setAttribute('aria-pressed', String(i === active));
        b.className = `px-2 py-1 rounded border ${i === active ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'}`;
        b.textContent = `${entry.job.title}${entry.error ? ' (error)' : ''}`;
        b.onclick = () => _show(i);
        host.appendChild(b);
    });
}

/** Run every planned job, one after another, then show the first. */
async function _runAll(runs) {
    _finished = [];
    clearReport();
    dispatch('SET_JOB_ID', null);
    dispatch('SET_PROCESSING', true);
    try {
        for (let i = 0; i < runs.length; i++) {
            const run = runs[i];
            const step = runs.length > 1 ? ` (${i + 1} of ${runs.length})` : '';
            setLoading(true, `Submitting ${run.title}${step}...`);
            let jobId;
            try {
                jobId = await _submit(run.endpoint, run.payload);
            } catch (e) {
                _finished.push({ job: { kind: run.kind, title: run.title, job_id: null }, error: e.message });
                continue;
            }
            const job = { job_id: jobId, kind: run.kind, title: run.title, run_name: readWorkspace().runName || null,
                          circuit_name: run.kind === 'single' ? _editorCircuitName() : null,
                          runner_config: run.payload.runner_config || {}, submitted_at: Date.now(),
                          remaining: runs.slice(i + 1).map(r => r.title) };
            savePendingJob(job);
            setLoading(true, `Running ${run.title}${step}...`, { startedAt: job.submitted_at });
            const entry = await _await(job);
            _finished.push(entry);
            if (entry.stopped) break;
        }
    } finally {
        setLoading(false);
        dispatch('SET_PROCESSING', false);
    }
    const first = _finished.findIndex(e => e.results);
    _show(first >= 0 ? first : 0);
}

/** Validate the workspace, plan its jobs and run them. */
export async function runWorkspace() {
    clearHistoryState();
    if (getState().isProcessing) return;
    const draft = readWorkspace();
    const simulating = draft.modes.statevector || draft.modes.measured;
    const v = validateRunInputs({ shotsId: 'shots-single', measured: draft.modes.measured });
    if (!v.ok) { showRunErrors('single-validation-msg', v.errors); return; }
    if (simulating) {
        await loadRunners();
        const problem = runnerSelectionProblem();
        if (problem) { showRunErrors('single-validation-msg', [problem]); return; }
        dispatch('SET_RUNNER_CONFIG', getRunnerConfig());
        if (!checkRunCountLimits(getState().currentRunnerConfig)) return;
    }
    const ws = readWorkspace(v);
    const { runs, error } = planRuns(ws);
    if (error) { showRunErrors('single-validation-msg', [error]); return; }
    showRunErrors('single-validation-msg', []);
    if (ws.source === 'editor') saveEditorCircuit(qasmInput.value, getState().currentAlgoName);
    document.getElementById('resume-job-banner')?.classList.add('hidden');
    await _runAll(runs);
}

/** Stop waiting for the job in progress; it keeps running and can be resumed after a reload. */
export function stopWaiting() {
    stopPolling();
}

/** Resume a job recorded before a reload. */
export async function resumeJob(job) {
    _finished = [];
    clearReport();
    dispatch('SET_PROCESSING', true);
    setLoading(true, `Running ${job.title}...`, { startedAt: job.submitted_at });
    try {
        _finished.push(await _await(job));
    } finally {
        setLoading(false);
        dispatch('SET_PROCESSING', false);
    }
    _show(0);
}

document.addEventListener('workspace-change', () => updateWorkspace());
document.addEventListener('circuit-list-added', () => selectListSource());
document.addEventListener('editor-loaded', () => {
    const editorRadio = /** @type {HTMLInputElement|null} */ (document.querySelector('input[name="run-source"][value="editor"]'));
    if (editorRadio) editorRadio.checked = true;
    updateContextBar();
    updateWorkspace();
});

