// =============================================================================
// config.js — Config Panel & Runner Selection
// Responsibility: Rendering the config panel, optimizer levels per runner,
//                 target simulator selection, and the context bar.
// Depends on: panelElements (app.js globals), getState().currentAlgoName (app.js)
//
// Runner opt data is fetched from /runners at panel-open time — config.py is
// the single source of truth. OPT_CAPS is intentionally absent here.
// =============================================================================

// Cache of runner info fetched from /runners: { id -> {max_level, optimization_levels, enabled} }
let _runnerOptInfo = {};

/** Returns the optimization_levels dict for a runner, or {} if unknown. */
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

    // Cache runner opt info for use by renderers.js badge tooltips
    _runnerOptInfo = {};
    runners.forEach(r => { _runnerOptInfo[r.id] = r; });

    // Toggle All Button
    const btnDiv = document.createElement('div');
    btnDiv.className = "col-span-1 sm:col-span-2 flex justify-end space-x-2 mb-2 border-b border-indigo-200 pb-2";
    btnDiv.innerHTML = `<button onclick="toggleAllSimulators()" class="text-xs text-indigo-600 hover:text-indigo-800 font-medium bg-indigo-100 px-3 py-1 rounded border border-indigo-300 shadow-sm transition-colors duration-200">Toggle All</button>`;
    grid.appendChild(btnDiv);

    // Global optimization selector
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

    // System Info
    const sysDiv = document.createElement('div');
    sysDiv.className = "col-span-1 sm:col-span-2 p-2 bg-gray-50 rounded border border-gray-200 mb-2 flex justify-between items-center text-xs";
    sysDiv.innerHTML = `
        <span class="font-bold text-gray-500">⚡ System Limits:</span>
        <div class="space-x-2">
            <span class="text-gray-600 font-mono">Memory: 512MB (Fixed)</span>
            <span class="text-gray-300">|</span>
            <div class="flex items-center space-x-1">
                <label for="timeout-input" class="text-xs text-gray-500">Timeout (s):</label>
                <input type="number" id="timeout-input" min="1" max="300" value="60"
                       onchange="if(this.value < 1) this.value=1; if(this.value > 300) this.value=300;"
                       class="w-16 text-xs border-gray-300 rounded p-1 focus:ring-indigo-500 focus:border-indigo-500 text-right">
            </div>
        </div>
    `;
    grid.appendChild(sysDiv);

    // Per-runner rows — ordered by display name list, falling back to API order
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

        const div = document.createElement('div');
        div.className = "space-y-1";
        div.innerHTML = `
            <div class="flex items-center justify-between mb-1">
                <label class="flex items-center space-x-2 cursor-pointer ${isDisabled ? 'opacity-40 cursor-not-allowed line-through text-red-400' : ''}">
                    <input type="checkbox" class="sim-checkbox h-3 w-3 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500"
                           data-sim="${r.id}" ${isDefaultChecked && !isDisabled ? 'checked' : ''} ${isDisabled ? 'disabled' : ''}>
                    <span class="block text-xs font-medium text-gray-600">${name}</span>
                </label>
            </div>
            <select data-runner="${r.id}" class="runner-opt-select block w-full text-xs border-gray-300 rounded p-1 shadow-sm"
                    title="${tooltip}" ${max === 0 ? 'disabled' : ''}>
                ${optionsHtml}
            </select>
        `;
        grid.appendChild(div);
    });
}

async function toggleConfigPanel() {
    const panel = document.getElementById('config-panel');
    if (panel.classList.contains('hidden')) {
        let runners = [];
        try {
            const resp = await fetch('/runners');
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
    const selects = document.querySelectorAll('.runner-opt-select');
    selects.forEach(s => {
        const val = parseInt(s.value);
        if (val !== -1) {
            config[s.getAttribute('data-runner')] = val;
        }
    });
    return config;
}

function toggleAllSimulators() {
    const checkboxes = document.querySelectorAll('.sim-checkbox:not(:disabled)');
    // If all enabled are checked, uncheck all. Otherwise (some or none checked), check all enabled.
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
    checkboxes.forEach(cb => cb.checked = !allChecked);
}

function getTargetSimulators() {
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

function updateContextBar() {
    const nameSpan = document.getElementById('ctx-algo-name');
    const optSpan = document.getElementById('ctx-opt-level');
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
}
