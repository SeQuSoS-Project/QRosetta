// =============================================================================
// config.js — Config Panel & Runner Selection
// Responsibility: Rendering the config panel, optimizer levels per runner,
//                 target simulator selection, and the context bar.
// Depends on: panelElements (app.js globals), getState().currentAlgoName (app.js)
// =============================================================================

const OPT_CAPS = {
    "default": 3,
    "qulacs": 2, "braket": 2, "quest": 2, "projectq": 2, "cirq": 2, "qsim-cirq": 2, "pyquil": 2, // Pytket caps
    "qibo": 0, "myqlm": 0, "qrisp": 0, "torchquantum": 0, "quimb": 0, "cuquantum": 0, // Own QASM parsers, pytket optimization not applicable
    "pennylane-lightning": 3, "pennylane-default": 3, "qiskit": 3
};

function renderConfigPanel() {
    const grid = document.getElementById('config-grid');
    if (!grid) return;

    grid.innerHTML = '';

    // Toggle All Button
    const btnDiv = document.createElement('div');
    btnDiv.className = "col-span-1 sm:col-span-2 flex justify-end space-x-2 mb-2 border-b border-indigo-200 pb-2";
    btnDiv.innerHTML = `
        <button onclick="toggleAllSimulators()" class="text-xs text-indigo-600 hover:text-indigo-800 font-medium bg-indigo-100 px-3 py-1 rounded border border-indigo-300 shadow-sm transition-colors duration-200">Toggle All</button>
    `;
    grid.appendChild(btnDiv);

    // Global Control First
    const globalDiv = document.createElement('div');
    globalDiv.className = "col-span-1 sm:col-span-2 p-2 bg-indigo-100 rounded border border-indigo-200 mb-2";
    globalDiv.innerHTML = `
        <label class="block text-xs font-bold text-indigo-800 uppercase mb-1">Global Default Level</label>
        <select id="opt-global" onchange="updateContextBar()" class="block w-full text-xs border-indigo-300 rounded p-1 focus:ring-indigo-500 focus:border-indigo-500">
            <option value="0" selected>0 (None)</option>
            <option value="1">1 (Light)</option>
            <option value="2">2 (Heavy)</option>
            <option value="3">3 (Aggressive)</option>
        </select>
    `;
    grid.appendChild(globalDiv);

    // System Info Section (Static)
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

    const runners = [
        { id: "qiskit", name: "Qiskit (IBM)" },
        { id: "qulacs", name: "Qulacs" },
        { id: "braket", name: "Braket (AWS)" },
        { id: "quest", name: "QuEST" },
        { id: "cirq", name: "Cirq (Google)" },
        { id: "qsim-cirq", name: "qsim (Google)" },
        { id: "qibo", name: "Qibo" },
        { id: "qrisp", name: "Qrisp" },
        { id: "myqlm", name: "myQLM (Eviden)" },
        { id: "pyquil", name: "PyQuil (Rigetti)" },
        { id: "projectq", name: "ProjectQ" },
        { id: "pennylane-lightning", name: "PL Lightning" },
        { id: "pennylane-default", name: "PL Default" },
        { id: "torchquantum", name: "TorchQuantum" },
        { id: "quimb", name: "Quimb (TN)" },
        { id: "cuquantum", name: "cuQuantum (NVIDIA)" }
    ];

    runners.forEach(r => {
        const max = OPT_CAPS[r.id] || 3;
        const div = document.createElement('div');
        div.className = "space-y-1";

        let optionsHtml = '';
        for (let i = 0; i <= max; i++) {
            optionsHtml += `<option value="${i}">${i}</option>`;
        }

        const isDefaultChecked = ['pennylane-default', 'qiskit', 'cirq', 'qulacs'].includes(r.id);
        div.innerHTML = `
            <div class="flex items-center justify-between mb-1">
                <label class="flex items-center space-x-2 cursor-pointer">
                    <input type="checkbox" class="sim-checkbox h-3 w-3 text-indigo-600 rounded border-gray-300 focus:ring-indigo-500" data-sim="${r.id}" ${isDefaultChecked ? 'checked' : ''}>
                    <span class="block text-xs font-medium text-gray-600">${r.name}</span>
                </label>
            </div>
            <select data-runner="${r.id}" class="runner-opt-select block w-full text-xs border-gray-300 rounded p-1 shadow-sm">
                <option value="-1">Use Global</option>
                ${optionsHtml}
            </select>
        `;
        grid.appendChild(div);
    });
}

function toggleConfigPanel() {
    const panel = document.getElementById('config-panel');
    if (panel.classList.contains('hidden')) {
        renderConfigPanel();
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
    const checkboxes = document.querySelectorAll('.sim-checkbox');
    // If all are checked, uncheck all. Otherwise (some or none checked), check all.
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
    checkboxes.forEach(cb => cb.checked = !allChecked);
}

function getTargetSimulators() {
    const checkboxes = document.querySelectorAll('.sim-checkbox');
    if (checkboxes.length === 0) {
        return ['pennylane-default', 'qiskit', 'cirq', 'qulacs'];
    }

    const checked = [];
    document.querySelectorAll('.sim-checkbox:checked').forEach(cb => {
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
