// The results area while a run is in progress: the tabs and table of the screen before a run
// (empty_state.js), with each backend's live status in the Status column and every other cell
// "—"; compile-only services and playlist circuits get tables of their own. api.js updates it
// on every poll tick. Leaf module.

import { BACKEND_COLUMNS, greyTabs, placeholderTable } from './empty_state.js';
import { compareRunnerKeys, formatRunnerLabel, parseRunnerKey } from './runner_key.js';

export const _STATUS_CFG = {
    queued:   { color: 'bg-gray-300',    text: 'text-gray-500',   label: 'QUEUED',    pulse: false, terminal: false, untimed: true,
                hint: 'Not started yet. Its time starts when it does.' },
    spawning: { color: 'bg-amber-400',   text: 'text-amber-700',  label: 'SPAWNING',  pulse: true,  terminal: false },
    running:  { color: 'bg-blue-500',    text: 'text-blue-700',   label: 'SENT',      pulse: true,  terminal: false,
                hint: 'Sent to the backend. Each backend runs one request at a time, so this includes any wait behind another job; the wait is recorded as queue_wait_sec.' },
    done:     { color: 'bg-green-500',   text: 'text-green-700',  label: 'DONE',      pulse: false, terminal: true  },
    error:    { color: 'bg-orange-500',  text: 'text-orange-700', label: 'ERROR',     pulse: false, terminal: true  },
    timeout:  { color: 'bg-purple-500',  text: 'text-purple-700', label: 'TIMEOUT',   pulse: false, terminal: true  },
    offline:  { color: 'bg-gray-400',    text: 'text-gray-600',   label: 'OFFLINE',   pulse: false, terminal: true,
                hint: 'The backend could not be reached.' },
};

const _ANALYSING = { color: 'bg-indigo-500', text: 'text-indigo-700', label: 'ANALYSING', pulse: true, terminal: false,
                    hint: 'Every backend has returned; the server is comparing the results. Measured runs with many outcomes can take tens of seconds here.' };

const _TASK_CFG = {
    queued:  _STATUS_CFG.queued,
    running: { color: 'bg-blue-500', text: 'text-blue-700', label: 'RUNNING', pulse: true, terminal: false },
    analysing: _ANALYSING,
    done:    _STATUS_CFG.done,
    error:   _STATUS_CFG.error,
};

export const _RUNNER_NAMES = {
    "qiskit": "Qiskit", "cirq": "Cirq", "qulacs": "Qulacs", "braket": "Braket",
    "projectq": "ProjectQ", "quest": "QuEST", "pennylane-lightning": "PL Lightning",
    "pennylane-default": "PL Default", "qsim-cirq": "qsim-Cirq", "qibo": "Qibo",
    "qrisp": "Qrisp", "myqlm": "myQLM", "pyquil": "PyQuil",
    "torchquantum": "TorchQuantum", "quimb": "Quimb", "cuquantum": "cuQuantum",
    "bqskit": "BQSKit (compile)", "pyzx": "PyZX (compile)", "qmap": "QMAP (compile)",
    "cirq-transformers": "Cirq (compile)", "staq": "staq (compile)", "qsynth": "Q-Synth (compile)",
    "quartz": "Quartz (compile)",
    "synthetiq": "Synthetiq (compile)",
};

const COMPILE_SUFFIX = ' (compile)';
const COMPILER_COLUMNS = ['Compile-only service', 'Status'];

/** The view of the run in progress, or null. */
let _view = null;

const _el = id => document.getElementById(id);

function _isCompiler(simId) {
    return _view.compilerIds.has(simId) || (_RUNNER_NAMES[simId] || '').endsWith(COMPILE_SUFFIX);
}

function _compilerName(key) {
    const { simId, optLevel, isMulti } = parseRunnerKey(key);
    const name = (_RUNNER_NAMES[simId] || simId).replace(COMPILE_SUFFIX, '');
    return isMulti ? `${name} level ${optLevel}` : name;
}

/** Status chip: coloured dot, label, and seconds in this status (frozen once finished). */
function _chip(cfg, seconds, key) {
    const wrap = document.createElement('span');
    wrap.className = `inline-flex items-center gap-1.5 font-medium ${cfg.text}`;
    if (cfg.hint) wrap.title = cfg.hint;
    const dot = document.createElement('span');
    dot.className = `w-2 h-2 rounded-full ${cfg.color}${cfg.pulse ? ' animate-pulse' : ''}`;
    const label = document.createElement('span');
    label.textContent = cfg.label;
    wrap.append(dot, label);
    if (cfg.untimed) return wrap;
    const time = document.createElement('span');
    time.className = 'text-gray-400 font-normal';
    time.textContent = `${seconds} s`;
    if (!cfg.terminal) time.dataset.since = key;
    wrap.append(time);
    return wrap;
}

/** Make sure `group`'s table has a row for every key, rebuilding it in key order when not.
 * A planned backend row gives way to that backend's multi-run rows (`<id>~opt<L>~run<N>`). */
function _ensureRows(group, keys) {
    const t = _view.tables[group];
    const known = t ? new Set(t.keys) : new Set();
    if (t && keys.every(k => known.has(k))) return;
    const runOf = new Set(keys.filter(k => k.includes('~')).map(k => parseRunnerKey(k).simId));
    const all = [...new Set([...known, ...keys])].filter(k => k.includes('~') || !runOf.has(k)).sort(compareRunnerKeys);
    const spec = group === 'compile'
        ? { caption: 'Compile-only services', columns: COMPILER_COLUMNS, keys: all, rows: all.map(k => [_compilerName(k), '—']) }
        : { caption: _view.backendCaption, columns: _view.backendColumns, keys: all,
            rows: all.map(k => [_view.nameOf(k), ..._view.backendColumns.slice(1).map(() => '—')]) };
    const node = placeholderTable(spec);
    if (t) t.node.replaceWith(node);
    else _el('runner-status-grid')?.appendChild(node);
    _view.tables[group] = { node, keys: all };
}

function _setStatus(tableNode, key, chip) {
    const cell = tableNode.querySelector(`tr[data-key="${CSS.escape(key)}"] .qr-status-cell`);
    if (!cell) return;
    cell.classList.remove('text-gray-300');
    cell.replaceChildren(chip);
}

/** Seconds `key` has been in `status`, keeping the time a finished run reached. */
function _seconds(key, status, cfg) {
    const now = Date.now();
    const prev = _view.phases[key];
    if (!prev || prev.status !== status) {
        const reached = prev ? Math.floor((now - prev.since) / 1000) : 0;
        _view.phases[key] = { status, since: now, frozen: cfg.terminal ? reached : null };
    }
    const phase = _view.phases[key];
    return phase.frozen ?? Math.floor((now - phase.since) / 1000);
}

function _tick() {
    if (!_view) return;
    const now = Date.now();
    document.querySelectorAll('#loader [data-since]').forEach(node => {
        const phase = _view.phases[/** @type {HTMLElement} */ (node).dataset.since];
        if (phase) node.textContent = `${Math.floor((now - phase.since) / 1000)} s`;
    });
}

function _finishedText(statuses, keys, noun) {
    const done = keys.filter(k => (_STATUS_CFG[statuses[k]] || _STATUS_CFG.queued).terminal).length;
    return `${done} of ${keys.length} ${noun}${keys.length === 1 ? '' : 's'} finished`;
}

/** True when every backend and compile has finished. Once a circuit's runs were seen in progress
 * and all have finished, the server is analysing its results (it reports no status of its own
 * for this; a playlist keeps the previous circuit's statuses until the next one dispatches). */
export function allRunsFinished(statuses) {
    const keys = Object.keys(statuses || {});
    return keys.length > 0 && keys.every(k => (_STATUS_CFG[statuses[k]] || _STATUS_CFG.queued).terminal);
}

function _renderProgress() {
    const host = _el('loader-progress');
    if (!host || !_view) return;
    const current = _view.progress ? _view.progress.current_index : 'single';
    const finished = allRunsFinished(_view.statuses);
    if (!finished && Object.keys(_view.statuses).length) _view.activeFor = current;
    const analysing = finished && _view.activeFor === current;
    if (analysing !== _view.analysing) {
        _view.analysing = analysing;
        setRunKicker(analysing ? 'Analysing results' : 'Running');
        if (_view.progress) _renderTasks();
    }
    const parts = [];
    const p = _view.progress;
    if (p) parts.push(`${p.completed || 0} of ${p.total || p.tasks.length} circuits finished`);
    const s = _view.statuses;
    const backends = Object.keys(s).filter(k => !_isCompiler(parseRunnerKey(k).simId));
    const compiles = Object.keys(s).filter(k => _isCompiler(parseRunnerKey(k).simId));
    const noun = backends.some(k => parseRunnerKey(k).isMulti) ? 'run' : 'backend';
    if (backends.length) parts.push(`${_finishedText(s, backends, noun)}${p ? ' on the current circuit' : ''}`);
    if (compiles.length) parts.push(_finishedText(s, compiles, 'compile'));
    if (analysing) parts.push('analysing results');
    host.textContent = parts.length ? `${parts.join(' · ')} ·` : '';
}

/**
 * Show the run view: `tabs` (greyed), `table` (the Backends or Playlist table of the screen
 * before the run, from emptyStateModel), the planned compile-only service ids, and `nameOf`
 * for a backend key. Missing pieces are built from the statuses as they arrive.
 */
export function startRunView({ tabs = [], table = null, compilerIds = [], nameOf = key => formatRunnerLabel(key, _RUNNER_NAMES) } = {}) {
    endRunView();
    const playlist = table?.caption === 'Playlist';
    _view = {
        nameOf, compilerIds: new Set(compilerIds), tables: {}, phases: {}, statuses: {}, progress: null, analysing: false, activeFor: null,
        backendCaption: playlist ? 'Backends (current circuit)' : 'Backends',
        backendColumns: !table || playlist ? BACKEND_COLUMNS : table.columns,
        timer: setInterval(_tick, 1000),
    };
    _el('loader-tabs')?.replaceChildren(...(tabs.length ? [greyTabs(tabs)] : []));
    if (table && playlist) {
        const node = placeholderTable(table);
        _el('batch-progress')?.replaceChildren(node);
        _view.tables.tasks = { node, keys: table.keys };
    } else if (table) {
        const node = placeholderTable(table);
        _el('runner-status-grid')?.appendChild(node);
        _view.tables.backends = { node, keys: table.keys };
    }
    setRunKicker('Submitting');
    _renderProgress();
}

/** The small line above the title: what the run is doing now. */
export function setRunKicker(text) {
    const kicker = _el('loader-kicker');
    if (kicker) kicker.textContent = text;
}

/** Clear the run view. */
export function endRunView() {
    if (_view) clearInterval(_view.timer);
    _view = null;
    ['loader-tabs', 'runner-status-grid', 'batch-progress', 'loader-progress', 'loader-kicker'].forEach(id => _el(id)?.replaceChildren());
}

/** Each runner key's live status (`queued`, `running`, `done`, ...), from the job poll. */
export function updateRunnerStatuses(statuses) {
    if (!statuses || typeof statuses !== 'object') return;
    if (!_view) startRunView();
    _view.statuses = statuses;
    const keys = Object.keys(statuses);
    const groups = { backends: keys.filter(k => !_isCompiler(parseRunnerKey(k).simId)), compile: keys.filter(k => _isCompiler(parseRunnerKey(k).simId)) };
    for (const [group, groupKeys] of Object.entries(groups)) {
        if (!groupKeys.length) continue;
        _ensureRows(group, groupKeys);
        groupKeys.forEach(key => {
            const cfg = _STATUS_CFG[statuses[key]] || _STATUS_CFG.queued;
            _setStatus(_view.tables[group].node, key, _chip(cfg, _seconds(key, statuses[key], cfg), key));
        });
    }
    _renderProgress();
}

/** Each playlist circuit's status, from the job poll of a batch or experiment run. */
export function renderBatchProgress(progress) {
    if (!progress || !Array.isArray(progress.tasks) || !progress.tasks.length) return;
    if (!_view) startRunView();
    _view.progress = progress;
    _renderTasks();
    _renderProgress();
}

/** The playlist table's Status cells; the running circuit reads ANALYSING once all its runs finished. */
function _renderTasks() {
    const progress = _view.progress;
    const keys = progress.tasks.map((_, i) => String(i));
    let t = _view.tables.tasks;
    if (!t || t.keys.length !== keys.length) {
        const node = placeholderTable({ caption: 'Circuits', columns: ['Task', 'Status'], keys, rows: progress.tasks.map(task => [task.name || '', '—']) });
        _el('batch-progress')?.replaceChildren(node);
        t = _view.tables.tasks = { node, keys };
    }
    progress.tasks.forEach((task, i) => {
        const status = task.status === 'running' && _view.analysing ? 'analysing' : (task.status || 'queued');
        const cfg = _TASK_CFG[status] || _TASK_CFG.queued;
        _setStatus(t.node, String(i), _chip(cfg, _seconds(`task:${i}`, status, cfg), `task:${i}`));
    });
}
