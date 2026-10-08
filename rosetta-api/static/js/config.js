// Frontend logic for config functionality.

import { BASE_URL } from './api.js';
import { getState } from './state.js';
import { _escapeHtml } from './utils.js';
import { announceWorkspaceChange } from './dom.js';
import { qasmGateMetrics } from './qasm_text.js';
import { RUNNER_DISPLAY_NAMES } from './runner_key.js';

/** Qubit cap of the run the mode boxes describe: statevector, measured, or compile-only when
 * neither is ticked. */
export function getDynamicMaxQubits() {
    const statevector = /** @type {HTMLInputElement|null} */ (document.getElementById('mode-statevector'))?.checked ?? true;
    const measured = /** @type {HTMLInputElement|null} */ (document.getElementById('mode-measured'))?.checked ?? false;
    if (statevector) return getState().maxQubitsStatevector;
    return measured ? getState().maxQubitsMeasured : getState().maxQubitsCompile;
}

export let _runnerOptInfo = {};

/** Multi-run mode (Backends popover): each runner runs N times across opt levels. Off by default. */
export let _multiRunEnabled = false;
/** Custom ordering (Backends popover): runners dispatched in phases one after another. Off by default. */
export let _orderingEnabled = false;

export function getRunnerOptInfo(runnerId) {
    return _runnerOptInfo[runnerId] || { max_level: 0, optimization_levels: {} };
}

export { RUNNER_DISPLAY_NAMES };

const DESELECTED_KEY = 'rosetta_deselected_runners';

function _loadDeselected() {
    try {
        const v = JSON.parse(localStorage.getItem(DESELECTED_KEY) || '[]');
        return new Set(Array.isArray(v) ? v : []);
    } catch (_) {
        return new Set();
    }
}

function _saveDeselected() {
    const off = [];
    document.querySelectorAll('.sim-checkbox:not([data-locked])').forEach(cb => {
        const el = /** @type {HTMLInputElement} */ (cb);
        if (!el.checked) off.push(el.dataset.sim);
    });
    try { localStorage.setItem(DESELECTED_KEY, JSON.stringify(off)); } catch (_) { /* storage unavailable */ }
}

let _runnersPromise = null;
let _runnersLoadError = null;

/** Fetch GET /runners once and render the backend selection; resolves to the runner list. */
export function loadRunners() {
    if (!_runnersPromise) {
        _runnersPromise = (async () => {
            let runners = [];
            try {
                const resp = await fetch(`${BASE_URL}/runners`);
                if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                runners = await resp.json();
                _runnersLoadError = null;
            } catch (e) {
                _runnersLoadError = e instanceof Error ? e.message : String(e);
                _runnersPromise = null;
            }
            renderConfigPanel(runners);
            return runners;
        })();
    }
    return _runnersPromise;
}

/** Canonical IDs of the runners the server has enabled, from GET /runners. */
export function getEnabledRunnerIds() {
    return Object.values(_runnerOptInfo).filter(r => r.enabled !== false && r.available !== false).map(r => r.id);
}

/** Why no backend can be selected, or null. */
export function runnerSelectionProblem() {
    if (Object.keys(_runnerOptInfo).length === 0) {
        return `The backend list could not be loaded from the server${_runnersLoadError ? ` (${_runnersLoadError})` : ''}. Reload the page to try again.`;
    }
    if (getTargetSimulators().length === 0) {
        return _multiRunEnabled
            ? 'No backend has a run count. Open the Backends chip above the run button and set a count of at least 1 for one backend.'
            : 'No backend is selected. Open the Backends chip above the run button and check at least one.';
    }
    return null;
}

/** Update every "Backends: N of M selected" line. */
export function updateBackendSelectionSummary() {
    const enabled = getEnabledRunnerIds();
    const selected = getTargetSimulators();
    let text;
    if (enabled.length === 0) {
        text = _runnersLoadError ? 'Backends: list not loaded' : 'Backends: loading…';
    } else if (_multiRunEnabled) {
        text = `Backends: ${selected.length} of ${enabled.length} enabled (multi-run counts)`;
    } else if (selected.length === enabled.length) {
        text = `Backends: all ${enabled.length} enabled backends selected`;
    } else {
        text = `Backends: ${selected.length} of ${enabled.length} enabled backends selected`;
    }
    document.querySelectorAll('.backend-selection-summary').forEach(el => { el.textContent = text; });
    _showRunCountProblems();
    announceWorkspaceChange();
}

export function _buildOptTooltip(optLevels) {
    if (!optLevels || Object.keys(optLevels).length === 0) return 'No optimization levels defined.';
    return Object.entries(optLevels)
        .sort(([a], [b]) => Number(a) - Number(b))
        .map(([lvl, desc]) => `L${lvl}: ${desc}`)
        .join('\n');
}

/** One .qr-section block of the Backends popover. */
function _section() {
    const div = document.createElement('div');
    div.className = 'qr-section';
    return div;
}

const ROW_CLASS = 'flex items-center gap-2';
const LEVEL_COLUMN = 'w-40 flex-shrink-0';

/** The popover header's Toggle All button, wired to this render. */
function _toggleAllButton() {
    const button = document.createElement('button');
    button.type = 'button';
    button.id = 'backends-toggle-all';
    button.className = 'qr-action';
    button.textContent = 'Toggle All';
    button.addEventListener('click', toggleAllSimulators);
    return button;
}

export function renderConfigPanel(runners) {
    const grid = document.getElementById('config-grid');
    if (!grid) return;

    grid.innerHTML = '';

    _runnerOptInfo = {};
    runners.forEach(r => { _runnerOptInfo[r.id] = r; });

    document.getElementById('backends-toggle-all')?.replaceWith(_toggleAllButton());

    const modes = _section();
    modes.innerHTML = `
        <label class="qr-option"><input type="checkbox" id="multirun-toggle" ${_multiRunEnabled ? 'checked' : ''}>
            <span>Multi-run mode (self-comparison)<span id="multirun-note" class="qr-option-help">Each count is one separate run in its own process, compared with every other run like another
            backend. The counts decide what runs; a backend with all counts 0 does not run. For a more stable time
            within one run, use Timing repeats instead.</span></span></label>
        <p id="run-count-problems" role="alert" class="hidden pl-6 text-xs text-red-700"></p>
        <label class="qr-option"><input type="checkbox" id="ordering-toggle" ${_orderingEnabled ? 'checked' : ''}>
            <span>Custom ordering (phases)<span class="qr-option-help">Lower phase number runs first; the same number runs together.</span></span></label>
        <div id="ordering-presets" class="pl-6 flex gap-2 ${_orderingEnabled ? '' : 'hidden'}">
            <button type="button" data-ordering="concurrent" class="qr-action">All concurrent</button>
            <button type="button" data-ordering="sequential" class="qr-action">Sequential</button>
        </div>
    `;
    const multiRunToggle = /** @type {HTMLInputElement} */ (modes.querySelector('#multirun-toggle'));
    const orderingToggle = /** @type {HTMLInputElement} */ (modes.querySelector('#ordering-toggle'));
    multiRunToggle.addEventListener('change', () => toggleMultiRunMode(multiRunToggle));
    orderingToggle.addEventListener('change', () => toggleOrderingMode(orderingToggle));
    modes.querySelector('[data-ordering="concurrent"]').addEventListener('click', setOrderingConcurrent);
    modes.querySelector('[data-ordering="sequential"]').addEventListener('click', setOrderingSequential);
    grid.appendChild(modes);

    const maxGlobal = Math.max(...runners.map(r => r.max_level ?? 0), 0);
    let globalOpts = '';
    const GLOBAL_LABELS = ['None', 'Light', 'Medium', 'Heavy'];
    for (let i = 0; i <= Math.min(maxGlobal, 3); i++) {
        globalOpts += `<option value="${i}">${i} — ${GLOBAL_LABELS[i] ?? i}</option>`;
    }
    const global = _section();
    global.innerHTML = `
        <label class="qr-label" for="opt-global">Global Optimization Level</label>
        <select id="opt-global" class="qr-input">${globalOpts}</select>
        <p class="qr-help">Applied to all runners — each runner uses the nearest level it supports. Override per runner below. Each runner has 1 CPU, 1 thread and 1 GiB memory.</p>
    `;
    global.querySelector('#opt-global').addEventListener('change', () => { updateContextBar(); announceWorkspaceChange(); });
    grid.appendChild(global);

    const list = _section();
    list.innerHTML = `<div class="flex items-center justify-between gap-2">
        <span class="qr-section-title">Backends (checked ones run)</span>
        <span class="backend-selection-summary text-xs text-gray-500"></span></div>`;
    grid.appendChild(list);

    if (runners.length === 0) {
        const p = document.createElement('p');
        p.className = 'text-xs text-red-700';
        p.textContent = 'The backend list could not be loaded from the server. Reload the page to try again.';
        list.appendChild(p);
    }

    const deselected = _loadDeselected();
    const orderedIds = Object.keys(RUNNER_DISPLAY_NAMES);
    const runnerMap = Object.fromEntries(runners.map(r => [r.id, r]));
    const orderedRunners = [
        ...orderedIds.filter(id => runnerMap[id]).map(id => runnerMap[id]),
        ...runners.filter(r => !orderedIds.includes(r.id))
    ];
    const levelColumns = Math.max(1, ...orderedRunners.map(r => (r.max_level ?? 0) + 1));

    const table = document.createElement('div');
    table.setAttribute('role', 'table');
    table.setAttribute('aria-label', 'Backends');
    table.className = 'text-xs';
    const levelHeads = Array.from({ length: levelColumns }, (_, i) => `<span class="qr-cell text-center">L${i}</span>`).join('');
    table.innerHTML = `
        <div role="row" class="${ROW_CLASS} sticky top-0 z-10 bg-white border-b border-gray-200 py-1 text-[11px] font-medium text-gray-500">
            <span role="columnheader" class="flex-1">Backend</span>
            <span role="columnheader" class="runner-phase-wrap hidden w-12 text-center">Phase</span>
            <span role="columnheader" class="opt-single-wrap ${LEVEL_COLUMN}">Optimization level</span>
            <span role="columnheader" class="multi-run-wrap hidden ${LEVEL_COLUMN}" title="Runs at each optimization level">
                <span class="grid grid-cols-4 gap-1">${levelHeads}</span></span>
        </div>`;
    list.appendChild(table);
    let anyLocked = false;

    orderedRunners.forEach(r => {
        const max = r.max_level ?? 0;
        const name = RUNNER_DISPLAY_NAMES[r.id] || r.id;
        const tooltip = _buildOptTooltip(r.optimization_levels);
        const isUnavailable = r.enabled !== false && r.available === false;
        const isDisabled = r.enabled === false || isUnavailable;
        const lockedNote = r.enabled === false ? 'Disabled on this server'
            : isUnavailable ? `Unavailable${r.unavailable_reason ? `: ${r.unavailable_reason}` : ' on this server'}` : '';
        if (isDisabled) anyLocked = true;
        const isDefaultChecked = !deselected.has(r.id);

        let optionsHtml = '<option value="-1">Use Global</option>';
        if (max === 0) {
            optionsHtml += `<option value="0" title="${_escapeHtml(r.optimization_levels?.['0'] || 'No optimization')}">0 — Not supported</option>`;
        } else {
            for (let i = 0; i <= max; i++) {
                const desc = r.optimization_levels?.[String(i)] || '';
                optionsHtml += `<option value="${i}" title="${_escapeHtml(desc)}">${i}${desc ? ` — ${_escapeHtml(desc.split(':')[0])}` : ''}</option>`;
            }
        }

        let countsHtml = '';
        for (let i = 0; i < levelColumns; i++) {
            const desc = r.optimization_levels?.[String(i)] || '';
            countsHtml += i > max ? '<span class="qr-cell"></span>' : `
                <input type="number" class="runner-count-input qr-input-small qr-cell" title="${_escapeHtml(desc || ('Optimization level ' + i))}"
                       aria-label="${_escapeHtml(name)}: runs at level ${i}" data-runner="${_escapeHtml(r.id)}" data-level="${i}"
                       value="0" min="0" max="${getState().maxRunsPerRunner || 16}" step="1" ${isDisabled ? 'disabled' : ''}>`;
        }

        const row = document.createElement('div');
        row.setAttribute('role', 'row');
        row.className = `${ROW_CLASS} py-0.5 rounded hover:bg-gray-50`;
        row.innerHTML = `
            <label role="cell" class="qr-option text-xs flex-1 min-w-0 items-center ${isDisabled ? 'cursor-not-allowed text-gray-400' : ''}" title="${_escapeHtml(lockedNote || name)}">
                <input type="checkbox" class="sim-checkbox mt-0" aria-label="Run ${_escapeHtml(name)}"
                       data-sim="${_escapeHtml(r.id)}" ${isDefaultChecked && !isDisabled ? 'checked' : ''} ${isDisabled ? 'disabled data-locked="1"' : ''}>
                <span class="truncate ${isDisabled ? 'line-through' : ''}">${_escapeHtml(name)}</span>
            </label>
            <span role="cell" class="runner-phase-wrap hidden w-12">
                <input type="number" class="runner-phase-input qr-input-small w-full" aria-label="${_escapeHtml(name)}: phase"
                       data-runner="${_escapeHtml(r.id)}" value="1" min="1" ${isDisabled ? 'disabled' : ''}></span>
            <span role="cell" class="opt-single-wrap ${LEVEL_COLUMN}">
                <select data-runner="${_escapeHtml(r.id)}" class="runner-opt-select qr-input py-0.5 text-xs" aria-label="${_escapeHtml(name)}: optimization level"
                        title="${_escapeHtml(tooltip)}" ${max === 0 || isDisabled ? 'disabled' : ''}>
                    ${optionsHtml}
                </select>
            </span>
            <span role="cell" class="multi-run-wrap hidden ${LEVEL_COLUMN}"><span class="grid grid-cols-4 gap-1">${countsHtml}</span></span>
        `;
        table.appendChild(row);
    });

    if (anyLocked) {
        const note = document.createElement('p');
        note.className = 'qr-help pt-1';
        note.textContent = 'Struck through: disabled or unavailable on this server; hover a name for the reason.';
        list.appendChild(note);
    }

    grid.querySelectorAll('.sim-checkbox').forEach(cb => cb.addEventListener('change', () => {
        _saveDeselected();
        updateBackendSelectionSummary();
    }));
    grid.querySelectorAll('.runner-count-input').forEach(inp => inp.addEventListener('input', updateBackendSelectionSummary));

    applyConfigModes();
}

export function applyConfigModes() {
    document.querySelectorAll('.opt-single-wrap').forEach(el => el.classList.toggle('hidden', _multiRunEnabled));
    document.querySelectorAll('.multi-run-wrap').forEach(el => el.classList.toggle('hidden', !_multiRunEnabled));
    document.querySelectorAll('.runner-phase-wrap').forEach(el => el.classList.toggle('hidden', !_orderingEnabled));

    // In multi-run mode the per-level counts decide what runs, so the include checkboxes are
    // hidden (backends the server disabled stay locked off).
    document.querySelectorAll('.sim-checkbox:not([data-locked])').forEach(node => {
        const cb = /** @type {HTMLInputElement} */ (node);
        cb.disabled = _multiRunEnabled;
        cb.classList.toggle('invisible', _multiRunEnabled);
    });
    document.getElementById('backends-toggle-all')?.classList.toggle('hidden', _multiRunEnabled);
    const presets = document.getElementById('ordering-presets');
    if (presets) presets.classList.toggle('hidden', !_orderingEnabled);
    updateBackendSelectionSummary();
}

export function toggleMultiRunMode(cb) {
    _multiRunEnabled = cb.checked;
    if (_multiRunEnabled) _seedRunCounts();
    applyConfigModes();
}

/** On entering independent-runs mode, give each ticked backend with no counts one run at its current level. */
function _seedRunCounts() {
    const globalLevel = parseInt(/** @type {HTMLSelectElement|null} */ (document.getElementById('opt-global'))?.value || '0', 10);
    document.querySelectorAll('.sim-checkbox:checked:not([data-locked])').forEach(node => {
        const sim = /** @type {HTMLElement} */ (node).dataset.sim;
        const counts = Array.from(document.querySelectorAll(`.runner-count-input[data-runner="${sim}"]`));
        if (!counts.length || counts.some(c => parseInt(/** @type {HTMLInputElement} */ (c).value, 10) > 0)) return;
        const select = /** @type {HTMLSelectElement|null} */ (document.querySelector(`.runner-opt-select[data-runner="${sim}"]`));
        const chosen = select && parseInt(select.value, 10) >= 0 ? parseInt(select.value, 10) : globalLevel;
        const level = Math.min(chosen, counts.length - 1);
        /** @type {HTMLInputElement} */ (counts[level]).value = '1';
    });
}

export function toggleOrderingMode(cb) {
    _orderingEnabled = cb.checked;
    applyConfigModes();
}

export function setOrderingConcurrent() {
    document.querySelectorAll('.runner-phase-input').forEach(inp => { inp.value = 1; });
}

export function setOrderingSequential() {
    const targets = new Set(getTargetSimulators());
    let phase = 1;
    document.querySelectorAll('.runner-phase-input').forEach(inp => {
        if (targets.has(inp.dataset.runner)) inp.value = phase++;
    });
}


export function getRunnerConfig() {
    const config = {};

    if (_multiRunEnabled) {
        // Build a per-runner list of opt levels from the count inputs (repeats allowed).
        const cap = (getState().maxRunsPerRunner || 16) + 1;
        document.querySelectorAll('.runner-count-input').forEach(inp => {
            const runner = inp.getAttribute('data-runner');
            const level = parseInt(inp.getAttribute('data-level'));
            const count = parseRunCount(/** @type {HTMLInputElement} */ (inp).value) || 0;
            if (count > 0 && !/** @type {HTMLInputElement} */ (inp).disabled) {
                if (!config[runner]) config[runner] = [];
                for (let k = 0; k < Math.min(count, cap) && config[runner].length < cap; k++) config[runner].push(level);
            }
        });
        return config;
    }

    const selectable = new Set(getEnabledRunnerIds());
    const selects = document.querySelectorAll('.runner-opt-select');
    selects.forEach(s => {
        if (!selectable.has(s.getAttribute('data-runner'))) return;
        const val = parseInt(s.value);
        if (val !== -1) {
            config[s.getAttribute('data-runner')] = val;
        }
    });
    return config;
}

/** A run count typed in multi-run mode: a whole number of runs, 0 for an empty field, NaN otherwise
 * ("1e1", "2.5" and "-1" are not counts). */
export function parseRunCount(raw) {
    const text = String(raw ?? '').trim();
    if (text === '') return 0;
    return /^\d+$/.test(text) ? Number(text) : NaN;
}

/**
 * Why the multi-run counts cannot be sent, or [] when they can: a count that is not a whole
 * number, a backend over `perRunner` runs, or more than `totalMax` runs in all.
 * @param {Array<{ runner: string, level: number, raw: string }>} cells
 * @param {number} perRunner @param {number} totalMax @param {Record<string, string>} [names]
 */
export function runCountProblemsFor(cells, perRunner, totalMax, names = {}) {
    const problems = [];
    const perBackend = new Map();
    cells.forEach(({ runner, level, raw }) => {
        const n = parseRunCount(raw);
        const name = names[runner] || runner;
        if (Number.isNaN(n)) {
            problems.push(`${name}, level ${level}: "${String(raw).trim()}" is not a whole number of runs.`);
            return;
        }
        perBackend.set(runner, (perBackend.get(runner) || 0) + n);
    });
    let total = 0;
    perBackend.forEach((count, runner) => {
        total += count;
        if (count > perRunner) problems.push(`${names[runner] || runner} has ${count} runs; the limit is ${perRunner} per backend.`);
    });
    if (total > totalMax) problems.push(`${total} runs in all; the limit is ${totalMax}.`);
    return problems;
}

/** Why the multi-run counts in the Backends popover cannot be sent, or [] (always [] outside multi-run mode). */
export function runCountProblems() {
    if (!_multiRunEnabled) return [];
    const cells = Array.from(document.querySelectorAll('.runner-count-input'))
        .filter(inp => !/** @type {HTMLInputElement} */ (inp).disabled)
        .map(inp => ({ runner: inp.getAttribute('data-runner') || '', level: parseInt(inp.getAttribute('data-level') || '0', 10),
                       raw: /** @type {HTMLInputElement} */ (inp).value }));
    return runCountProblemsFor(cells, getState().maxRunsPerRunner || 16, getState().maxTotalRuns || 48, RUNNER_DISPLAY_NAMES);
}

/** Show the multi-run count problems in the Backends popover. */
function _showRunCountProblems() {
    const box = document.getElementById('run-count-problems');
    if (!box) return;
    const problems = runCountProblems();
    box.textContent = problems.join(' ');
    box.classList.toggle('hidden', problems.length === 0);
}

export function getRunnerPhases() {
    if (!_orderingEnabled) return {};
    const phases = {};
    const targets = new Set(getTargetSimulators());
    document.querySelectorAll('.runner-phase-input').forEach(inp => {
        const runner = inp.getAttribute('data-runner');
        if (!targets.has(runner)) return;
        const p = parseInt(inp.value);
        if (!isNaN(p) && p >= 1) phases[runner] = p;
    });
    return phases;
}

export function toggleAllSimulators() {
    const checkboxes = document.querySelectorAll('.sim-checkbox:not(:disabled)');

    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
    checkboxes.forEach(cb => cb.checked = !allChecked);
    _saveDeselected();
    updateBackendSelectionSummary();
    announceWorkspaceChange();
}

export function getTargetSimulators() {
    // In multi-run mode, selection is whatever has a non-zero run count.
    if (_multiRunEnabled) {
        return Object.keys(getRunnerConfig());
    }

    const checked = [];
    document.querySelectorAll('.sim-checkbox:checked:not(:disabled)').forEach(cb => {
        checked.push(cb.getAttribute('data-sim'));
    });
    return checked;
}

export function _parseQasmStats(qasm) {
    let qubits = 0;
    for (const line of qasm.split('\n')) {
        const t = line.trim();
        if (!t || t.startsWith('//')) continue;
        const m = t.match(/^qreg\s+\w+\[(\d+)\]/);
        if (m) qubits += parseInt(m[1]);
    }
    return { qubits, gates: qasmGateMetrics(qasm).gateCount };
}

export function updateContextBar() {
    const nameInput = /** @type {HTMLInputElement|null} */ (document.getElementById('ctx-algo-name'));
    const statsSpan = document.getElementById('ctx-circuit-stats');
    if (nameInput && document.activeElement !== nameInput) nameInput.value = getState().currentAlgoName;

    if (statsSpan) {
        const qasmEl = document.getElementById('qasm-input');
        const qasm = qasmEl ? qasmEl.value.trim() : '';
        if (qasm) {
            const { qubits, gates } = _parseQasmStats(qasm);
            const maxQ = getDynamicMaxQubits();
            statsSpan.textContent = `${qubits} qubits · ${gates} gates`;
            statsSpan.className = `text-xs whitespace-nowrap ${qubits > maxQ ? 'text-red-600 font-semibold' : 'text-gray-500'}`;
        } else {
            statsSpan.textContent = '';
        }
    }
}

/** True when the editor holds text the user typed or changed, or a circuit the user named,
 * which loading another circuit would replace. */
export function editorHasEdits() {
    const named = /** @type {HTMLInputElement|null} */ (document.getElementById('ctx-algo-name'))?.dataset.typed === '1';
    const text = /** @type {HTMLTextAreaElement|null} */ (document.getElementById('qasm-input'))?.value.trim() || '';
    return text !== '' && (named || /^Custom\b/.test(getState().currentAlgoName || ''));
}
