// Frontend logic for config functionality.

let _runnerOptInfo = {};

// Both opt-in. Off = the default panel behavior (single opt-level select per runner,
// all runners dispatched concurrently). See applyConfigModes() for show/hide wiring.
let _multiRunEnabled = false;   // self-comparison: run a runner N times across opt levels
let _orderingEnabled = false;   // phased dispatch: assign runners to sequential phase waves

function getRunnerOptInfo(runnerId) {
    return _runnerOptInfo[runnerId] || { max_level: 0, optimization_levels: {} };
}

const RUNNER_DISPLAY_NAMES = {
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

const DEFAULT_CHECKED_RUNNERS = new Set(['pennylane-default', 'qiskit', 'cirq', 'qulacs']);

function _buildOptTooltip(optLevels) {
    if (!optLevels || Object.keys(optLevels).length === 0) return 'No optimization levels defined.';
    return Object.entries(optLevels)
        .sort(([a], [b]) => Number(a) - Number(b))
        .map(([lvl, desc]) => `L${lvl}: ${desc}`)
        .join('\n');
}

function renderConfigPanel(runners) {
    const grid = document.getElementById('config-grid');
    if (!grid) return;

    grid.innerHTML = '';

    _runnerOptInfo = {};
    runners.forEach(r => { _runnerOptInfo[r.id] = r; });

    const btnDiv = document.createElement('div');
    btnDiv.className = "col-span-1 sm:col-span-2 flex justify-end space-x-2 mb-2 border-b border-indigo-200 pb-2";
    btnDiv.innerHTML = `<button onclick="toggleAllSimulators()" class="text-xs text-indigo-600 hover:text-indigo-800 font-medium bg-indigo-100 px-3 py-1 rounded border border-indigo-300 shadow-sm transition-colors duration-200">Toggle All</button>`;
    grid.appendChild(btnDiv);

    const modesDiv = document.createElement('div');
    modesDiv.className = "col-span-1 sm:col-span-2 p-2 bg-white rounded border border-indigo-200 mb-2 space-y-2";
    modesDiv.innerHTML = `
        <label class="flex items-center space-x-2 cursor-pointer">
            <input type="checkbox" id="multirun-toggle" onchange="toggleMultiRunMode(this)" ${_multiRunEnabled ? 'checked' : ''}
                   class="h-3 w-3 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500">
            <span class="text-xs font-bold text-indigo-800 uppercase">Multi-run mode (self-comparison)</span>
        </label>
        <p id="multirun-note" class="text-xs text-indigo-600 pl-5 ${_multiRunEnabled ? '' : 'hidden'}">
            Set a run count per optimization level below — each count spawns one independent run.
            Selection is driven by counts; the checkboxes above are ignored. Runners with all-zero counts do not run.
        </p>
        <label class="flex items-center space-x-2 cursor-pointer pt-1 border-t border-indigo-50">
            <input type="checkbox" id="ordering-toggle" onchange="toggleOrderingMode(this)" ${_orderingEnabled ? 'checked' : ''}
                   class="h-3 w-3 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500">
            <span class="text-xs font-bold text-indigo-800 uppercase">Custom ordering (phases)</span>
        </label>
        <div id="ordering-presets" class="pl-5 space-x-2 ${_orderingEnabled ? '' : 'hidden'}">
            <span class="text-xs text-indigo-600">Lower phase number runs first; same number runs together.</span>
            <button type="button" onclick="setOrderingConcurrent()" class="text-xs text-indigo-600 hover:text-indigo-800 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200">All concurrent</button>
            <button type="button" onclick="setOrderingSequential()" class="text-xs text-indigo-600 hover:text-indigo-800 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200">Sequential</button>
        </div>
    `;
    grid.appendChild(modesDiv);

    const maxGlobal = Math.max(...runners.map(r => r.max_level ?? 0), 0);
    let globalOpts = '';
    const GLOBAL_LABELS = ['None', 'Light', 'Medium', 'Heavy'];
    for (let i = 0; i <= Math.min(maxGlobal, 3); i++) {
        globalOpts += `<option value="${i}">${i} — ${GLOBAL_LABELS[i] ?? i}</option>`;
    }
    const globalDiv = document.createElement('div');
    globalDiv.className = "col-span-1 sm:col-span-2 p-2 bg-indigo-100 rounded border border-indigo-200 mb-2";
    globalDiv.innerHTML = `
        <label class="block text-xs font-bold text-indigo-800 uppercase mb-1">Global Optimization Level</label>
        <select id="opt-global" onchange="updateContextBar()" class="block w-full text-xs border-indigo-300 rounded p-1 focus:ring-indigo-500 focus:border-indigo-500">
            ${globalOpts}
        </select>
        <p class="text-xs text-indigo-600 mt-1">Applied to all runners — each runner uses the nearest level it supports. Override per-runner below.</p>
    `;
    grid.appendChild(globalDiv);

    const sysDiv = document.createElement('div');
    sysDiv.className = "col-span-1 sm:col-span-2 p-2 bg-gray-50 rounded border border-gray-200 mb-2 flex justify-between items-center text-xs";
    sysDiv.innerHTML = `
        <span class="font-bold text-gray-500">⚡ System Limits:</span>
        <div class="space-x-2">
            <span class="text-gray-600 font-mono">Memory: 512 MiB (local) / 1 GiB (K8s)</span>
            <span class="text-gray-300">|</span>
            <div class="flex items-center space-x-1">
                <label for="timeout-input" class="text-xs text-gray-500">Timeout (s):</label>
                <input type="number" id="timeout-input" min="1" max="300" value="300"
                       onchange="if(this.value < 1) this.value=1; if(this.value > 300) this.value=300;"
                       class="w-16 text-xs border-gray-300 rounded p-1 focus:ring-indigo-500 focus:border-indigo-500 text-right">
            </div>
        </div>
    `;
    grid.appendChild(sysDiv);

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
        const isDefaultChecked = DEFAULT_CHECKED_RUNNERS.has(r.id);
        const isDisabled = r.enabled === false;

        let optionsHtml = '<option value="-1">Use Global</option>';
        if (max === 0) {
            optionsHtml += `<option value="0" title="${r.optimization_levels?.['0'] || 'No optimization'}">0 — Not supported</option>`;
        } else {
            for (let i = 0; i <= max; i++) {
                const desc = r.optimization_levels?.[String(i)] || '';
                optionsHtml += `<option value="${i}" title="${desc}">${i}${desc ? ` — ${desc.split(':')[0]}` : ''}</option>`;
            }
        }

        let countsHtml = '';
        for (let i = 0; i <= max; i++) {
            const desc = r.optimization_levels?.[String(i)] || '';
            countsHtml += `
                <label class="inline-flex flex-col items-center mr-1 mb-1" title="${desc || ('Optimization level ' + i)}">
                    <span class="text-[10px] text-gray-400">L${i}</span>
                    <input type="number" class="runner-count-input w-9 text-xs border-gray-300 rounded p-0.5 text-center"
                           data-runner="${r.id}" data-level="${i}" value="0" min="0" max="8" ${isDisabled ? 'disabled' : ''}>
                </label>`;
        }

        const div = document.createElement('div');
        div.className = "space-y-1";
        div.innerHTML = `
            <div class="flex items-center justify-between mb-1">
                <label class="flex items-center space-x-2 cursor-pointer ${isDisabled ? 'opacity-40 cursor-not-allowed line-through text-red-400' : ''}">
                    <input type="checkbox" class="sim-checkbox h-3 w-3 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500"
                           data-sim="${r.id}" ${isDefaultChecked && !isDisabled ? 'checked' : ''} ${isDisabled ? 'disabled' : ''} ${isDisabled ? 'data-locked="1"' : ''}>
                    <span class="block text-xs font-medium text-gray-600">${name}</span>
                </label>
                <label class="runner-phase-wrap hidden flex items-center space-x-1 text-[10px] text-gray-400">
                    <span>Phase</span>
                    <input type="number" class="runner-phase-input w-9 text-xs border-gray-300 rounded p-0.5 text-center"
                           data-runner="${r.id}" value="1" min="1" ${isDisabled ? 'disabled' : ''}>
                </label>
            </div>
            <div class="opt-single-wrap">
                <select data-runner="${r.id}" class="runner-opt-select block w-full text-xs border-gray-300 rounded p-1 shadow-sm"
                        title="${tooltip}" ${max === 0 ? 'disabled' : ''}>
                    ${optionsHtml}
                </select>
            </div>
            <div class="multi-run-wrap hidden flex flex-wrap">
                ${countsHtml}
            </div>
        `;
        grid.appendChild(div);
    });

    applyConfigModes();
}

function applyConfigModes() {
    document.querySelectorAll('.opt-single-wrap').forEach(el => el.classList.toggle('hidden', _multiRunEnabled));
    document.querySelectorAll('.multi-run-wrap').forEach(el => el.classList.toggle('hidden', !_multiRunEnabled));
    document.querySelectorAll('.runner-phase-wrap').forEach(el => el.classList.toggle('hidden', !_orderingEnabled));

    // In multi-run mode the per-level counts decide what runs, so the include
    // checkboxes are disabled (genuinely-disabled runners stay locked off).
    document.querySelectorAll('.sim-checkbox:not([data-locked])').forEach(cb => {
        cb.disabled = _multiRunEnabled;
        const label = cb.closest('label');
        if (label) label.classList.toggle('opacity-40', _multiRunEnabled);
    });

    const note = document.getElementById('multirun-note');
    if (note) note.classList.toggle('hidden', !_multiRunEnabled);
    const presets = document.getElementById('ordering-presets');
    if (presets) presets.classList.toggle('hidden', !_orderingEnabled);
}

function toggleMultiRunMode(cb) {
    _multiRunEnabled = cb.checked;
    applyConfigModes();
}

function toggleOrderingMode(cb) {
    _orderingEnabled = cb.checked;
    applyConfigModes();
}

function setOrderingConcurrent() {
    document.querySelectorAll('.runner-phase-input').forEach(inp => { inp.value = 1; });
}

function setOrderingSequential() {
    const targets = new Set(getTargetSimulators());
    let phase = 1;
    document.querySelectorAll('.runner-phase-input').forEach(inp => {
        if (targets.has(inp.dataset.runner)) inp.value = phase++;
    });
}

async function toggleConfigPanel() {
    const panel = document.getElementById('config-panel');
    if (panel.classList.contains('hidden')) {
        let runners = [];
        try {
            const resp = await fetch(`${BASE_URL}/runners`);
            if (resp.ok) runners = await resp.json();
        } catch (_) {}
        renderConfigPanel(runners);
        panel.classList.remove('hidden');
    } else {
        panel.classList.add('hidden');
    }
}

function getRunnerConfig() {
    const config = {};

    if (_multiRunEnabled) {
        // Build a per-runner list of opt levels from the count inputs (repeats allowed).
        document.querySelectorAll('.runner-count-input').forEach(inp => {
            const runner = inp.getAttribute('data-runner');
            const level = parseInt(inp.getAttribute('data-level'));
            const count = parseInt(inp.value) || 0;
            if (count > 0) {
                if (!config[runner]) config[runner] = [];
                for (let k = 0; k < count; k++) config[runner].push(level);
            }
        });
        return config;
    }

    const selects = document.querySelectorAll('.runner-opt-select');
    selects.forEach(s => {
        const val = parseInt(s.value);
        if (val !== -1) {
            config[s.getAttribute('data-runner')] = val;
        }
    });
    return config;
}

function checkRunCountLimits(runnerConfig) {
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

function getRunnerPhases() {
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

function toggleAllSimulators() {
    const checkboxes = document.querySelectorAll('.sim-checkbox:not(:disabled)');

    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
    checkboxes.forEach(cb => cb.checked = !allChecked);
}

function getTargetSimulators() {
    // In multi-run mode, selection is whatever has a non-zero run count.
    if (_multiRunEnabled) {
        return Object.keys(getRunnerConfig());
    }

    const checkboxes = document.querySelectorAll('.sim-checkbox:not(:disabled)');
    if (checkboxes.length === 0) {
        return ['pennylane-default', 'qiskit', 'cirq', 'qulacs'];
    }

    const checked = [];
    document.querySelectorAll('.sim-checkbox:checked:not(:disabled)').forEach(cb => {
        checked.push(cb.getAttribute('data-sim'));
    });
    return checked;
}

function _parseQasmStats(qasm) {
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

function updateContextBar() {
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
            const maxQ = typeof getDynamicMaxQubits === 'function' ? getDynamicMaxQubits() : 24;
            statsSpan.textContent = `${qubits}q / ${gates} gates`;
            statsSpan.className = qubits > maxQ ? 'text-red-600 font-semibold' : 'text-gray-500';
        } else {
            statsSpan.textContent = '';
        }
    }
}