// The workspace: which circuits, which runs and which settings one press of Run uses; the
// Run button's label; submitting the planned jobs one after another; showing their results
// with a switcher when there are several; resuming a job after a reload.

import { BASE_URL, formatApiError, getAuthHeaders, pollJobStatus, pollingStopped, resetStopPolling, stopPolling } from './api.js';
import { autosaveRun } from './autosave.js';
import { getCompilerSelection } from './compilers_config.js';
import {
    _parseQasmStats, getEnabledRunnerIds, getRunnerConfig, getRunnerPhases, getTargetSimulators, loadRunners,
    runCountProblems, runnerSelectionProblem, updateContextBar,
} from './config.js';
import { qasmInput } from './dom.js';
import { renderExperimentResult } from './experiment.js';
import { clearHistoryState, saveRunToHistory } from './history.js';
import { confirmUnsavedRun, signedInAccount } from './auth.js';
import { clearReport, renderDetailReport, renderSuiteSummary, showTab } from './renderers.js';
import { planRuns, runButtonLabel, runLimitProblems } from './run_plan.js';
import { labelProblem, printableLabel } from './request_limits.js';
import { showRunErrors, validateRunInputs } from './run_inputs.js';
import { FINISHED_KEEP_MS, forgetJob, forgetSignedInJobs, isJobsStorageKey, listJobs, markJobFinished, markJobStopped, recordJob, saveEditorCircuit, saveRunModes } from './session_store.js';
import { dispatch, getState } from './state.js';
import { getAgreementThresholds, getSeed, setLoading } from './utils.js';
import { batchItemLabel, renderBatchQueue } from './batch.js';
import { exampleOptions } from './circuit_sources.js';
import { emptyStateModel, renderEmptyState } from './empty_state.js';
import { setRunKicker, startRunView } from './status_cards.js';
import { _displayRunnerName } from './render_helpers.js';
import { compareRunnerKeys, plannedRunKeys } from './runner_key.js';
import { announce, firstSentence, focusHeading, focusIsLost } from './announce.js';

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
        runName: printableLabel(/** @type {HTMLInputElement|null} */ (document.getElementById('single-run-name'))?.value, getState().maxLabelLength),
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
        limits: { maxLabelLength: getState().maxLabelLength },
    };
}

/** The server limits runLimitProblems() checks, from GET /config. */
function _requestLimits() {
    const st = getState();
    return { maxRequestBytes: st.maxRequestBytes, maxQasmSize: st.maxQasmSize,
             maxExperimentCells: st.maxExperimentCells, executionMode: st.executionMode };
}

/** Run button colours by what it runs: the editor circuit blue, the playlist yellow, an experiment emerald. */
const RUN_THEMES = {
    editor: ['bg-blue-600', 'hover:bg-blue-700', 'focus:ring-blue-500'],
    batch: ['bg-yellow-600', 'hover:bg-yellow-700', 'focus:ring-yellow-500'],
    experiment: ['bg-emerald-600', 'hover:bg-emerald-700', 'focus:ring-emerald-500'],
};

/** Refresh everything that depends on the workspace: shots field, compiler line, counts, Run label. */
let _lastModes = '';
export function updateWorkspace() {
    const ws = readWorkspace({ shots: 1 });
    const modes = JSON.stringify(ws.modes);
    if (modes !== _lastModes) {
        _lastModes = modes;
        saveRunModes(ws.modes);
        updateContextBar();
    }
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
        _showRunBlocked(button, (ws.modes.statevector || ws.modes.measured) ? runCountProblems() : []);
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

/** Disable Run and say why while the multi-run counts cannot be sent; a run in progress keeps its own state. */
function _showRunBlocked(button, problems) {
    const box = document.getElementById('run-blocked-msg');
    if (box) {
        box.textContent = problems.length ? `Run is unavailable until the Backends chip's multi-run counts are fixed: ${problems.join(' ')}` : '';
        box.classList.toggle('hidden', !problems.length);
    }
    if (getState().isProcessing) return;
    button.disabled = problems.length > 0;
    if (problems.length) button.setAttribute('aria-describedby', 'run-blocked-msg');
    else button.removeAttribute('aria-describedby');
}

/** The results area before a result: what Run will do and the table it will fill. */
function _renderEmptyState(ws) {
    renderEmptyState(document.getElementById('empty-state'), _emptyModel(ws), {
        onExample: value => document.dispatchEvent(new CustomEvent('open-circuit', { detail: value })),
    });
}

/** The screen-before-a-run model of the workspace `ws`. */
function _emptyModel(ws) {
    return emptyStateModel({
        source: ws.source,
        circuitName: ws.editor.name,
        playlist: ws.list.map(batchItemLabel),
        modes: ws.modes,
        preprocessing: ws.preprocessing,
        compilerCount: Object.values(ws.compilers).reduce((n, levels) => n + levels.length, 0),
        backends: plannedRunKeys(ws.common.target_simulators, ws.common.runner_config).sort(compareRunnerKeys).map(key => ({ key, name: _displayRunnerName(key) })),
        backendsLoaded: getEnabledRunnerIds().length > 0,
        examples: exampleOptions(),
    });
}

const _TABS_BY_KIND = { batch: ['Suite Summary', 'Exports'], experiment: [] };

/** Show the running view for one planned run: the tabs and table of the screen before it. */
function _startRunView(ws, run) {
    const model = _emptyModel({
        ...ws,
        modes: { statevector: run.mode === 'statevector', measured: run.mode === 'measured' },
        preprocessing: run.kind === 'experiment' ? 'both' : ws.preprocessing,
    });
    const tabs = _TABS_BY_KIND[run.kind] ?? model.tabs;
    startRunView({ tabs, table: model.table, compilerIds: Object.keys(ws.compilers), nameOf: _displayRunnerName });
}

/** Above this many qubits a measured run is likely to hit the timeout on several backends. */
export const SLOW_MEASURED_QUBITS = 22;

/** The pre-run warning for a measured circuit of `qubits` qubits above SLOW_MEASURED_QUBITS. */
export function slowMeasuredWarning(qubits, timeout, timeoutMax) {
    return `Measured runs of more than ${SLOW_MEASURED_QUBITS} qubits take minutes on several backends: at 24 qubits about half `
        + `of them did not finish within the ${timeoutMax} s maximum timeout, and some used about 1 GiB of memory. `
        + `Expect timeouts for this ${qubits}-qubit circuit at the current timeout of ${timeout ?? '—'} s.`;
}

const _timeoutSeconds = () => {
    const v = Number(/** @type {HTMLInputElement|null} */ (document.getElementById('timeout-input'))?.value);
    return Number.isFinite(v) ? v : null;
};

/** Warn before a run when the circuits exceed a ticked mode's qubit limit. */
function _showLimitWarning(ws) {
    const box = document.getElementById('run-limit-warning');
    if (!box) return;
    const qubits = ws.source === 'list'
        ? Math.max(0, ...ws.list.map(item => parseInt(item.qubits) || 0))
        : _parseQasmStats(ws.editor.qasm).qubits;
    const { maxQubitsStatevector: sv, maxQubitsMeasured: ms, maxQubitsCompile: cp } = getState();
    const what = ws.source === 'list' ? `The largest playlist circuit has ${qubits} qubits` : `This circuit has ${qubits} qubits`;
    const notes = [];
    if (ws.modes.statevector && qubits > sv) notes.push(`statevector runs allow ${sv}`);
    if (ws.modes.measured && qubits > ms) notes.push(`measured runs allow ${ms}`);
    if (!ws.modes.statevector && !ws.modes.measured && qubits > cp) notes.push(`compile-only runs allow ${cp}`);
    const lines = notes.length ? [`${what}; ${notes.join(' and ')}.`] : [];
    if (ws.modes.measured && qubits > SLOW_MEASURED_QUBITS && qubits <= ms) lines.push(slowMeasuredWarning(qubits, _timeoutSeconds(), getState().timeoutMax));
    const cells = getState().maxExperimentCells;
    const circuits = ws.source === 'list' ? ws.list.length : 1;
    if (ws.preprocessing === 'both' && (ws.modes.statevector || ws.modes.measured) && !ws.common.bypass_limits && circuits * 2 > cells) {
        lines.push(`SDK Preprocessing Both runs each circuit twice: ${circuits} circuits make ${circuits * 2} experiment runs; the server allows ${cells}.`);
    }
    box.textContent = lines.join(' ');
    box.classList.toggle('hidden', !lines.length);
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
        markJobFinished(job.job_id);
        if (job.run_name) results.run_name = job.run_name;
        if (job.circuit_name && !results.circuit_name) results.circuit_name = job.circuit_name;
        let historyRunId = null;
        if (job.kind !== 'experiment') {
            historyRunId = await saveRunToHistory(job.job_id, job.run_name || null);
            autosaveRun(results, job.run_name || job.title);
        }
        return { job, results, historyRunId };
    } catch (e) {
        if (e && e.stopped) {
            markJobStopped(job.job_id);
            return { job, error: e.message, stopped: true };
        }
        console.error(e);
        if (e && e.terminal) forgetJob(job.job_id);
        return { job, error: e.message, stopped: false };
    }
}

let _finished = [];
let _shownIndex = -1;

const _clock = ms => new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

function _el(tag, className = '', text = '') {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
}

/** The results panel after Stop waiting: the job id, what was not started, and a way back to the results. */
function _renderStopped(entry) {
    const { job } = entry;
    clearReport();
    document.getElementById('back-button-container')?.classList.add('hidden');
    const panel = document.getElementById('summary-panel');
    if (!panel) return;
    const box = _el('div', 'p-4 bg-gray-50 border border-gray-300 rounded text-sm text-gray-800 space-y-2');
    box.setAttribute('role', 'status');
    box.appendChild(_el('h3', 'text-base font-semibold text-gray-900', 'Stopped waiting'));
    box.appendChild(_el('p', '', `${job.title}: the job keeps running on the server, which keeps its results for 30 minutes after it finishes. `
        + 'Show results waits for it again; reopening this page also offers it.'));
    const id = _el('p', 'text-xs text-gray-600', 'Job ID: ');
    id.appendChild(_el('code', 'font-mono select-all', job.job_id));
    box.appendChild(id);
    if (Array.isArray(job.remaining) && job.remaining.length) {
        box.appendChild(_el('p', 'text-xs text-gray-600', `Not started: ${job.remaining.join('; ')}.`));
    }
    const show = _el('button', 'px-3 py-1 rounded border border-indigo-300 bg-white text-indigo-700 hover:bg-indigo-50 text-xs font-medium', 'Show results');
    show.setAttribute('type', 'button');
    show.addEventListener('click', () => { if (!getState().isProcessing) resumeJob(job); });
    box.appendChild(show);
    panel.replaceChildren(box);
    panel.classList.remove('hidden');
}

/** Show one finished entry in the results panel. */
function _show(index) {
    const entry = _finished[index];
    if (!entry) return;
    _shownIndex = index;
    const { job } = entry;
    clearHistoryState();
    dispatch('SET_JOB_ID', entry.results ? job.job_id : null);
    dispatch('SET_HISTORY_RUN_ID', entry.historyRunId ?? null);
    if (entry.stopped) {
        dispatch('SET_SUITE_DATA', null);
        _renderStopped(entry);
    } else if (job.kind === 'experiment') {
        dispatch('SET_SUITE_DATA', null);
        const panel = document.getElementById('experiment-panel');
        if (panel) {
            if (entry.results) {
                renderExperimentResult(entry.results, panel, { jobId: job.job_id, name: job.run_name || job.title, title: job.title,
                                                               compilers: job.compilers, compilersWith: job.compilers_with });
            }
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
        b.textContent = `${entry.job.title}${entry.stopped ? ' (stopped waiting)' : entry.error ? ' (error)' : ''}`;
        b.onclick = () => {
            _show(i);
            /** @type {HTMLElement|undefined} */ (host.querySelectorAll('button')[i])?.focus();
        };
        host.appendChild(b);
    });
}

/** The heading of the results now on screen: the visible panel's first heading. */
function _shownHeading() {
    const panel = Array.from(document.querySelectorAll('#tab-content > [id$="-panel"]')).find(p => !p.classList.contains('hidden'));
    return panel?.querySelector('h2, h3') || null;
}

/** After a run or a resumed job: say what arrived, and move focus to the results heading when
 * focus is on the Run button or nowhere. */
function _announceShown(entry) {
    if (!entry) return;
    const run = document.getElementById('btn-run');
    if (focusIsLost(run) || document.getElementById('loader')?.contains(document.activeElement)) focusHeading(_shownHeading());
    const { job } = entry;
    if (entry.stopped) { announce(`Stopped waiting for ${job.title}. The job keeps running on the server.`); return; }
    if (!entry.results) { announce(`The run failed: ${job.title}. ${entry.error || ''}`); return; }
    const err = entry.results.error || entry.results.job_error;
    if (err) { announce(`The run failed: ${job.title}. ${typeof err === 'string' ? err : ''}`); return; }
    const lines = Array.from(document.querySelectorAll('#summary-panel section[aria-label="Result"] p.text-sm')).slice(0, 2);
    const headline = lines.map(p => firstSentence(p.textContent)).join(' ');
    announce(`Results ready: ${job.title}.${headline ? ` ${headline}` : ''}`);
}

/** On a narrow screen, where the results follow the workspace, scroll to them. */
function _revealResults() {
    if (window.matchMedia?.('(max-width: 1023px)').matches) {
        document.getElementById('results-column')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

/** Run every planned job of the workspace `ws`, one after another, then show the first. */
async function _runAll(runs, ws) {
    _finished = [];
    resetStopPolling();
    clearReport();
    _revealResults();
    dispatch('SET_JOB_ID', null);
    dispatch('SET_PROCESSING', true);
    try {
        for (let i = 0; i < runs.length; i++) {
            if (pollingStopped()) break;
            const run = runs[i];
            const step = runs.length > 1 ? ` (${i + 1} of ${runs.length})` : '';
            _startRunView(ws, run);
            setLoading(true, `${run.title}${step}`);
            let jobId;
            try {
                jobId = await _submit(run.endpoint, run.payload);
            } catch (e) {
                _finished.push({ job: { kind: run.kind, title: run.title, job_id: null }, error: e.message });
                continue;
            }
            const job = { job_id: jobId, kind: run.kind, title: run.title, run_name: _historyName(ws.runName, run, runs),
                          circuit_name: run.kind === 'single' ? _editorCircuitName() : null,
                          runner_config: run.payload.runner_config || {}, submitted_at: Date.now(),
                          remaining: runs.slice(i + 1).map(r => r.title), account: signedInAccount(),
                          ...(run.kind === 'experiment' ? _experimentCompilers(run, runs) : {}) };
            recordJob(job);
            setRunKicker('Running');
            setLoading(true, `${run.title}${step}`, { startedAt: job.submitted_at });
            const entry = await _await(job);
            _finished.push(entry);
            if (entry.stopped) break;
        }
    } finally {
        setLoading(false);
        dispatch('SET_PROCESSING', false);
        updateWorkspace();
    }
    const first = _finished.findIndex(e => e.results);
    _show(first >= 0 ? first : 0);
    _announceShown(_finished[first >= 0 ? first : 0]);
    offerRecentJobs({ unfinishedOnly: true });
}

/** For an experiment run: the compile-only levels it carries, or the title of the run of the same
 * press of Run that carries them. */
function _experimentCompilers(run, runs) {
    const levels = c => Object.values(c || {}).reduce((n, l) => n + (Array.isArray(l) ? l.length : 0), 0);
    if (levels(run.payload.compilers)) return { compilers: run.payload.compilers };
    const other = runs.find(r => r !== run && levels(r.payload?.compilers));
    return other ? { compilers_with: other.title } : {};
}

/** The name a run is saved to History under: the Run Name, with the mode added when one press of
 * Run starts a run per mode, so the History rows differ; null without a Run Name. */
function _historyName(runName, run, runs) {
    if (!runName) return null;
    const modes = new Set(runs.map(r => r.mode).filter(Boolean));
    if (modes.size < 2 || !run.mode) return runName;
    const suffix = ` (${run.mode === 'measured' ? 'Measured' : 'Statevector'})`;
    const max = getState().maxLabelLength;
    const room = Math.max(1, max - suffix.length);
    const base = Array.from(runName).length > room ? Array.from(runName).slice(0, room).join('').trim() : runName;
    return `${base}${suffix}`;
}

/** The problems that keep the workspace from being submitted, or [] when Run would submit it.
 * `v` is the result of validateRunInputs(). Shows nothing. */
function _submitProblems(v) {
    const ws = readWorkspace(v);
    const problems = [];
    const nameProblem = labelProblem(_rawRunName(), getState().maxLabelLength, 'The run name');
    if (nameProblem) problems.push(`Run Name: ${nameProblem}`);
    const { runs, error } = planRuns(ws);
    if (error) return [...problems, error];
    return [...problems, ...runLimitProblems(runs, _requestLimits())];
}

const _rawRunName = () => /** @type {HTMLInputElement|null} */ (document.getElementById('single-run-name'))?.value.trim() || '';

let _refusalShown = false;

/** Show the reasons Run refused the workspace, or clear them when there are none. */
function _showRefusal(problems) {
    _refusalShown = problems.length > 0;
    showRunErrors('single-validation-msg', problems);
}

/** After a refused press of Run: check the workspace again, so the box lists only what still blocks it. */
function _refreshRefusal() {
    if (!_refusalShown) return;
    const draft = readWorkspace();
    const v = validateRunInputs({ shotsId: 'shots-single', measured: draft.modes.measured });
    const problems = v.ok ? _submitProblems(v) : v.errors;
    const backends = (draft.modes.statevector || draft.modes.measured) ? runnerSelectionProblem() : null;
    _showRefusal(backends ? [backends, ...problems] : problems);
}

/** Validate the workspace, plan its jobs and run them. */
export async function runWorkspace() {
    if (getState().isProcessing) return;
    clearHistoryState();
    if (!confirmUnsavedRun()) return;
    const draft = readWorkspace();
    const simulating = draft.modes.statevector || draft.modes.measured;
    const v = validateRunInputs({ shotsId: 'shots-single', measured: draft.modes.measured });
    if (!v.ok) { _showRefusal(v.errors); return; }
    if (simulating) {
        await loadRunners();
        const problem = runnerSelectionProblem();
        if (problem) { _showRefusal([problem]); return; }
        const countProblems = runCountProblems();
        if (countProblems.length) { _showRefusal(countProblems); return; }
        dispatch('SET_RUNNER_CONFIG', getRunnerConfig());
    }
    const problems = _submitProblems(v);
    if (problems.length) { _showRefusal(problems); return; }
    _showRefusal([]);
    const ws = readWorkspace(v);
    const { runs } = planRuns(ws);
    if (ws.source === 'editor') saveEditorCircuit(qasmInput.value, getState().currentAlgoName);
    document.getElementById('resume-job-banner')?.classList.add('hidden');
    await _runAll(runs, ws);
}

/** Stop waiting for the job in progress; it keeps running and can be resumed. */
export function stopWaiting() {
    stopPolling();
}

/** Wait for a job submitted earlier (before a reload, or before Stop waiting) and show its results. */
export async function resumeJob(job) {
    if (getState().isProcessing) return;
    _finished = [];
    resetStopPolling();
    clearReport();
    clearHistoryState();
    document.getElementById('resume-job-banner')?.classList.add('hidden');
    _revealResults();
    dispatch('SET_PROCESSING', true);
    startRunView({ tabs: _TABS_BY_KIND[job.kind] ?? ['Summary', 'Agreement', 'Performance', 'Circuits', 'Exports'], nameOf: _displayRunnerName });
    setRunKicker('Running');
    setLoading(true, job.title, { startedAt: job.submitted_at });
    if (focusIsLost()) focusHeading(document.getElementById('loader-text'));
    try {
        _finished.push(await _await(job));
    } finally {
        setLoading(false);
        dispatch('SET_PROCESSING', false);
        updateWorkspace();
    }
    _show(0);
    _announceShown(_finished[0]);
    offerRecentJobs({ unfinishedOnly: true });
}

/** One row of the recent-jobs offer: what the job is, its state, and Show results / Dismiss. */
function _recentJobRow(job) {
    const li = _el('li', 'flex flex-wrap items-center gap-2');
    const name = job.run_name || job.title;
    const short = `job ${job.job_id.slice(0, 8)}`;
    const text = job.state === 'finished'
        ? `${name} (${short}) finished at ${_clock(job.finished_at)}; the server keeps its results until ${_clock(job.finished_at + FINISHED_KEEP_MS)}.`
        : job.state === 'stopped'
            ? `${name} (${short}), submitted at ${_clock(job.submitted_at)}: you stopped waiting for it.`
            : `${name} (${short}), submitted at ${_clock(job.submitted_at)}: its results were not shown yet.`;
    const notStarted = job.state !== 'finished' && Array.isArray(job.remaining) && job.remaining.length
        ? ` Not started: ${job.remaining.join('; ')}.` : '';
    li.appendChild(_el('span', 'flex-1 min-w-0', `${text}${notStarted}`));
    const show = _el('button', 'px-2 py-1 rounded border border-amber-300 bg-white hover:bg-amber-100 text-xs font-medium', 'Show results');
    show.setAttribute('type', 'button');
    show.addEventListener('click', () => { if (!getState().isProcessing) resumeJob(job); });
    const dismiss = _el('button', 'px-2 py-1 rounded border border-amber-200 hover:bg-amber-100 text-xs', 'Dismiss');
    dismiss.setAttribute('type', 'button');
    dismiss.addEventListener('click', () => {
        forgetJob(job.job_id);
        li.remove();
        if (!document.querySelector('#resume-job-list li')) document.getElementById('resume-job-banner')?.classList.add('hidden');
    });
    li.append(show, dismiss);
    return li;
}

/** Whether the server still has job `jobId`: false on 404, true otherwise (also when it cannot be
 * reached). Reads the status line only; the body is not downloaded. */
async function _serverHasJob(jobId) {
    const controller = new AbortController();
    try {
        const res = await fetch(`${BASE_URL}/jobs/${encodeURIComponent(jobId)}`, { signal: controller.signal, headers: getAuthHeaders() });
        controller.abort();
        return res.status !== 404;
    } catch (_) {
        return true;
    }
}

let _offerOptions = { unfinishedOnly: false };

/**
 * Offer the jobs this browser submitted whose results can still be fetched: unfinished ones
 * (the page was closed, or Stop waiting was pressed) and, unless `unfinishedOnly`, finished
 * ones the server still keeps. The jobs on screen are left out, and a job the server no longer
 * has (it answers 404, for example after a restart) is dropped from the list and forgotten.
 */
export function offerRecentJobs({ unfinishedOnly = false } = {}) {
    _offerOptions = { unfinishedOnly };
    const banner = document.getElementById('resume-job-banner');
    const list = document.getElementById('resume-job-list');
    if (!banner || !list) return;
    const now = Date.now();
    const onScreen = new Set(_finished.filter(e => !e.stopped).map(e => e.job.job_id));
    const jobs = listJobs(now).filter(j => !onScreen.has(j.job_id) && (!unfinishedOnly || j.state !== 'finished'));
    const rows = jobs.map(job => _recentJobRow(job));
    list.replaceChildren(...rows);
    banner.classList.toggle('hidden', jobs.length === 0);
    jobs.forEach(async (job, i) => {
        if (await _serverHasJob(job.job_id)) return;
        forgetJob(job.job_id);
        rows[i].remove();
        if (!list.querySelector('li')) banner.classList.add('hidden');
    });
}

window.addEventListener?.('storage', e => {
    if (isJobsStorageKey(e.key) && !getState().isProcessing) offerRecentJobs(_offerOptions);
});

/** Forget what the signed-out account had on screen: its runs, their results and its recorded jobs. */
function _forgetAccountView() {
    forgetSignedInJobs();
    if (_finished.some(e => e.job.account)) {
        _finished = [];
        _shownIndex = -1;
        _renderSwitcher(-1);
        dispatch('SET_JOB_ID', null);
        dispatch('SET_SUITE_DATA', null);
        dispatch('SET_HISTORY_RUN_ID', null);
        clearReport();
        document.getElementById('welcome-message')?.classList.remove('hidden');
        updateWorkspace();
    }
    offerRecentJobs();
}

/** A saved run was deleted from History: the run on screen loses its History link. */
function _historyRunsDeleted(ids) {
    const entry = _finished[_shownIndex];
    if (!entry || !entry.historyRunId || !ids.includes(entry.historyRunId)) return;
    entry.historyRunId = null;
    _show(_shownIndex);
}

document.addEventListener('workspace-change', () => { updateWorkspace(); _refreshRefusal(); });
document.addEventListener('signed-out', () => _forgetAccountView());
document.addEventListener('history-runs-deleted', e => _historyRunsDeleted(/** @type {CustomEvent} */ (e).detail || []));
document.addEventListener('circuit-list-added', () => selectListSource());
document.addEventListener('editor-loaded', e => {
    const editorRadio = /** @type {HTMLInputElement|null} */ (document.querySelector('input[name="run-source"][value="editor"]'));
    if (editorRadio) editorRadio.checked = true;
    updateContextBar();
    updateWorkspace();
    if (/** @type {CustomEvent} */ (e).detail?.initial) return;
    const stats = document.getElementById('ctx-circuit-stats')?.textContent || '';
    announce(`Loaded into the editor: ${getState().currentAlgoName}${stats ? `, ${stats.replace(' · ', ', ')}` : ''}.`);
    if (focusIsLost()) focusHeading(document.getElementById('ws-editor'));
});

