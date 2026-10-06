// Frontend logic for config functionality.

import { BASE_URL } from './api.js';
import { getState } from './state.js';
import { _escapeHtml } from './utils.js';

export function getDynamicMaxQubits() {
    const statevector = /** @type {HTMLInputElement|null} */ (document.getElementById('mode-statevector'))?.checked ?? true;
    return statevector ? getState().maxQubitsStatevector : getState().maxQubitsMeasured;
}

export let _runnerOptInfo = {};

// Both opt-in. Off = the default panel behavior (single opt-level select per runner,
// all runners dispatched concurrently). See applyConfigModes() for show/hide wiring.
export let _multiRunEnabled = false;   // self-comparison: run a runner N times across opt levels
export let _orderingEnabled = false;   // phased dispatch: assign runners to sequential phase waves

export function getRunnerOptInfo(runnerId) {
    return _runnerOptInfo[runnerId] || { max_level: 0, optimization_levels: {} };
}

export const RUNNER_DISPLAY_NAMES = {
    "qiskit": "Qiskit (IBM)",
    "qulacs": "Qulacs",
    "braket": "Braket (AWS)",
    "quest": "QuEST",
    "cirq": "Cirq (Google)",
    "qsim-cirq": "qsim (Google)",
    "qibo": "Qibo",
    "qrisp": "Qrisp",
    "myqlm": "myQLM (Eviden)",
    "pyquil": "PyQuil (Rigetti)",
    "projectq": "ProjectQ",
    "pennylane-lightning": "PL Lightning",
    "pennylane-default": "PL Default",
    "torchquantum": "TorchQuantum",
    "quimb": "Quimb (TN)",
    "cuquantum": "cuQuantum (NVIDIA)"
};

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
        return 'No backend is selected. Open the Backends chip above the run button and check at least one.';
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
    document.dispatchEvent(new Event('workspace-change'));
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
    const mode = getState().executionMode;
    const memText = mode === 'local' || mode === 'kubernetes' ? '1 GiB' : '1 GiB locally, 1 GiB on Kubernetes';
    const global = _section();
    global.innerHTML = `
        <label class="qr-label" for="opt-global">Global Optimization Level</label>
        <select id="opt-global" class="qr-input">${globalOpts}</select>
        <p class="qr-help">Applied to all runners — each runner uses the nearest level it supports. Override per runner below. Each runner has 1 CPU, 1 thread and ${memText} memory.</p>
    `;
    global.querySelector('#opt-global').addEventListener('change', () => { updateContextBar(); document.dispatchEvent(new Event('workspace-change')); });
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

    orderedRunners.forEach(r => {
        const max = r.max_level ?? 0;
        const name = RUNNER_DISPLAY_NAMES[r.id] || r.id;
        const tooltip = _buildOptTooltip(r.optimization_levels);
        const isUnavailable = r.enabled !== false && r.available === false;
        const isDisabled = r.enabled === false || isUnavailable;
        const lockedNote = r.enabled === false ? ' (disabled on this server)'
            : isUnavailable ? ` (unavailable${r.unavailable_reason ? `: ${r.unavailable_reason}` : ' on this server'})` : '';
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
        for (let i = 0; i <= max; i++) {
            const desc = r.optimization_levels?.[String(i)] || '';
            countsHtml += `
                <label class="inline-flex items-center gap-0.5 text-[11px] text-gray-500" title="${_escapeHtml(desc || ('Optimization level ' + i))}">L${i}
                    <input type="number" class="runner-count-input qr-input-small w-8" aria-label="${_escapeHtml(name)}: runs at level ${i}"
                           data-runner="${_escapeHtml(r.id)}" data-level="${i}" value="0" min="0" max="8" ${isDisabled ? 'disabled' : ''}></label>`;
        }

        const row = document.createElement('div');
        row.className = "grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-2 py-0.5";
        row.innerHTML = `
            <label class="qr-option text-xs min-w-0 items-center ${isDisabled ? 'cursor-not-allowed text-gray-400' : ''}" title="${_escapeHtml(name + lockedNote)}">
                <input type="checkbox" class="sim-checkbox mt-0"
                       data-sim="${_escapeHtml(r.id)}" ${isDefaultChecked && !isDisabled ? 'checked' : ''} ${isDisabled ? 'disabled data-locked="1"' : ''}>
                <span class="truncate ${r.enabled === false ? 'line-through' : ''}">${_escapeHtml(name)}${lockedNote ? `<span class="text-[11px] text-gray-400">${_escapeHtml(lockedNote)}</span>` : ''}</span>
            </label>
            <div class="flex items-center justify-end gap-2">
                <label class="runner-phase-wrap hidden inline-flex items-center gap-1 text-[11px] text-gray-500">Phase
                    <input type="number" class="runner-phase-input qr-input-small w-10" aria-label="${_escapeHtml(name)}: phase"
                           data-runner="${_escapeHtml(r.id)}" value="1" min="1" ${isDisabled ? 'disabled' : ''}></label>
                <div class="opt-single-wrap">
                    <select data-runner="${_escapeHtml(r.id)}" class="runner-opt-select qr-input w-40 py-0.5 text-xs" aria-label="${_escapeHtml(name)}: optimization level"
                            title="${_escapeHtml(tooltip)}" ${max === 0 || isDisabled ? 'disabled' : ''}>
                        ${optionsHtml}
                    </select>
                </div>
                <div class="multi-run-wrap hidden grid grid-cols-4 gap-1.5">${countsHtml}</div>
            </div>
        `;
        list.appendChild(row);
    });

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
        document.querySelectorAll('.runner-count-input').forEach(inp => {
            const runner = inp.getAttribute('data-runner');
            const level = parseInt(inp.getAttribute('data-level'));
            const count = parseInt(inp.value) || 0;
            if (count > 0 && !/** @type {HTMLInputElement} */ (inp).disabled) {
                if (!config[runner]) config[runner] = [];
                for (let k = 0; k < count; k++) config[runner].push(level);
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

export function checkRunCountLimits(runnerConfig) {
    const perRunner = getState().maxRunsPerRunner || 16;
    const totalMax = getState().maxTotalRuns || 48;
    let total = 0;
    for (const [name, val] of Object.entries(runnerConfig || {})) {
        const count = Array.isArray(val) ? val.length : 1;
        if (count > perRunner) {
            alert(`'${name}' is configured to run ${count} times, over the per-runner limit of ${perRunner}. Lower the counts in the Config panel.`);
            return false;
        }
        total += count;
    }
    if (total > totalMax) {
        alert(`You've configured ${total} total runs, over the limit of ${totalMax}. Lower the run counts in multi-run mode.`);
        return false;
    }
    return true;
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
    let qubits = 0, gates = 0;
    for (const line of qasm.split('\n')) {
        const t = line.trim();
        if (!t || t.startsWith('//')) continue;
        const m = t.match(/^qreg\s+\w+\[(\d+)\]/);
        if (m) { qubits += parseInt(m[1]); continue; }
        if (t.startsWith('OPENQASM') || t.startsWith('include') || t.startsWith('creg')) continue;
        if (t.endsWith(';')) gates++;
    }
    return { qubits, gates };
}

export function updateContextBar() {
    const nameSpan = document.getElementById('ctx-algo-name');
    const optSpan = document.getElementById('ctx-opt-level');
    const statsSpan = document.getElementById('ctx-circuit-stats');
    const globalSelect = document.getElementById('opt-global');
    const level = globalSelect ? globalSelect.value : 0;

    if (nameSpan) {
        if (nameSpan.tagName === 'INPUT') {
            nameSpan.value = getState().currentAlgoName;
        } else {
            nameSpan.textContent = getState().currentAlgoName;
        }
    }
    if (optSpan) optSpan.textContent = `Global Opt: ${level}`;

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