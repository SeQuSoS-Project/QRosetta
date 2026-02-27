// --- FIX: Define BASE_URL ---
let BASE_URL = '';
if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    BASE_URL = 'https://rosetta-api-qrosetta.2.rahtiapp.fi';
}

// --- GLOBAL STATE ---
let authToken = localStorage.getItem('rosetta_token') || null;
let isProcessing = false;
let currentSuiteData = null;
let currentSuiteTitle = '';
let batchQueue = []; // Playlist
let allAlgorithms = []; // Metadata
let currentOptLevel = 0;
let currentAlgoName = "Custom";
let currentRunnerConfig = {}; // For persistence across detailed views

function getAuthHeaders(extraHeaders = {}) {
    const headers = { ...extraHeaders };
    if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
    }
    return headers;
}

const OPT_CAPS = {
    "default": 3,
    "qulacs": 2, "braket": 2, "quest": 2, "projectq": 2, "cirq": 2, // Pytket caps
    "pennylane-lightning": 3, "pennylane-default": 3, "qiskit": 3
};

// --- FIX: Declare DOM elements here, define them in window.onload ---
let qasmInput, loader, tabNav, welcomeMessage, backButtonContainer, jsonOutput;
let playlistSection, queueList, queueCount;
let panelElements = {};
let allButtons = [];

// --- INIT ---
window.onload = async () => {
    // --- FIX: Define all DOM elements inside onload ---
    qasmInput = document.getElementById('qasm-input');
    loader = document.getElementById('loader');
    tabNav = document.getElementById('tab-nav');
    welcomeMessage = document.getElementById('welcome-message');
    backButtonContainer = document.getElementById('back-button-container');
    jsonOutput = document.getElementById('json-output');

    playlistSection = document.getElementById('playlist-section');
    queueList = document.getElementById('queue-list');
    queueCount = document.getElementById('queue-count');

    panelElements = {
        'summary': document.getElementById('summary-panel'),
        'performance': document.getElementById('performance-panel'),
        'resources': document.getElementById('resources-panel'),
        'divergence': document.getElementById('divergence-panel'),
        'raw': document.getElementById('raw-panel'),
        'suite-summary': document.getElementById('suite-summary-panel'),
        'visualizer': document.getElementById('visualizer-panel')
    };

    allButtons = [
        document.getElementById('btn-run'),
        document.getElementById('btn-batch-run')
    ];

    updateAuthUI();
    verifySession();
    // --- END FIX ---

    try {
        // --- FIX: Use BASE_URL for fetch ---
        const response = await fetch(`${BASE_URL}/algorithms`, {
            headers: getAuthHeaders()
        });
        if (!response.ok) throw new Error('Failed to fetch algorithms');
        allAlgorithms = await response.json();

        const select = document.getElementById('algo-select');
        select.innerHTML = '';
        allAlgorithms.forEach(algo => {
            const option = document.createElement('option');
            option.value = algo.id;
            option.textContent = algo.name;
            select.appendChild(option);
        });

        select.addEventListener('change', updateQubitConstraints);
        updateQubitConstraints();

        // --- NEW: Context Bar Init ---
        qasmInput.addEventListener('input', () => {
            currentAlgoName = "Custom / Modified";
            updateContextBar();
        });
        updateContextBar();

    } catch (error) {
        console.error("Failed to load algorithms:", error);
        // Display error to user
        welcomeMessage.innerHTML = `<div class="p-4 bg-red-100 text-red-700 rounded"><strong>Connection Error:</strong> Could not load algorithms from ${BASE_URL}. Is the server running?</div>`;
        welcomeMessage.classList.remove('text-gray-500');
    }
    // Set initial UI states for both blocks
    toggleSingleMode();
    toggleBatchMode();
    // Only generate circuit if algorithms loaded
    // Only generate circuit if algorithms loaded
    if (allAlgorithms.length > 0) {
        generateCircuit();
    }
    renderBatchQueue();
};

// --- METADATA UI LOGIC ---
function getDynamicMaxQubits() {
    const mode = document.querySelector('input[name="mode-single"]:checked')?.value || 'statevector';
    return mode === 'statevector' ? 18 : 24;
}

function updateQubitConstraints() {
    const algoId = document.getElementById('algo-select').value;
    const selectedAlgo = allAlgorithms.find(a => a.id === algoId);
    const input = document.getElementById('algo-qubits');

    if (selectedAlgo) {
        if (selectedAlgo.min_qubits !== undefined) input.min = selectedAlgo.min_qubits;
        input.max = Math.min(selectedAlgo.max_qubits || 24, getDynamicMaxQubits());
        if (selectedAlgo.default_qubits !== undefined) input.value = selectedAlgo.default_qubits;

        if (selectedAlgo.min_qubits === selectedAlgo.max_qubits) {
            input.disabled = true;
        } else {
            input.disabled = false;
        }
    }
}

// --- GENERATOR & PLAYLIST LOGIC ---

const PRESETS = {
    "sanity": [
        { algorithm: "bell", qubits: 2, name: "Bell State (Simple)" },
        { algorithm: "ghz", qubits: 5, name: "GHZ State (Entanglement)" },
        { algorithm: "qft", qubits: 5, name: "Quantum Fourier Transform" },
        { algorithm: "grover", qubits: 5, name: "Grover Search (Oracle)" },
        { algorithm: "random", qubits: 5, name: "Random Circuit" }
    ],
    "scaling": [
        { algorithm: "ghz", qubits: 5, name: "GHZ State (Entanglement)" },
        { algorithm: "ghz", qubits: 10, name: "GHZ State (Entanglement)" },
        { algorithm: "ghz", qubits: 15, name: "GHZ State (Entanglement)" },
        { algorithm: "ghz", qubits: 20, name: "GHZ State (Entanglement)" }
    ],
    "stress": [
        { algorithm: "random", qubits: 20, name: "Random Circuit" },
        { algorithm: "bv", qubits: 20, name: "Bernstein-Vazirani" },
        { algorithm: "vqe", qubits: 20, name: "VQE Ansatz" }
    ]
};

async function applyPreset() {
    const val = document.getElementById('preset-select').value;
    if (PRESETS[val]) {
        if (batchQueue.length > 0 && !confirm("This will replace your current playlist. Continue?")) return;

        const selectedPreset = JSON.parse(JSON.stringify(PRESETS[val]));

        setLoading(true, `Loading Preset: ${val}...`);
        try {
            for (let i = 0; i < selectedPreset.length; i++) {
                const item = selectedPreset[i];
                let qasmText = null;
                const response = await fetch(`${BASE_URL}/generate_circuit`, {
                    method: 'POST',
                    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
                    body: JSON.stringify({ algorithm: item.algorithm, qubits: item.qubits })
                });
                if (response.ok) {
                    const data = await response.json();
                    qasmText = data.qasm;
                } else {
                    console.warn(`Failed to pre-generate QASM for ${item.name}`);
                }
                item.qasm_string = qasmText;
            }
            batchQueue = selectedPreset;
            renderBatchQueue();
        } catch (e) {
            console.error("Preset loading failed", e);
            alert("Preset loading failed: " + e.message);
        } finally {
            setLoading(false);
        }
    }
}

async function generateCircuit() {
    if (isProcessing) return;
    const algoId = document.getElementById('algo-select').value;
    const qubits = parseInt(document.getElementById('algo-qubits').value);

    if (!algoId || isNaN(qubits)) {
        alert("Please select an algorithm and specify a valid number of qubits.");
        return;
    }

    isProcessing = true;
    setLoading(true, "Generating Circuit...");
    try {
        // --- FIX: Use BASE_URL for fetch ---
        const response = await fetch(`${BASE_URL}/generate_circuit`, {
            method: 'POST',
            headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ algorithm: algoId, qubits: qubits })
        });
        const data = await response.json();
        if (response.ok) {
            qasmInput.value = data.qasm;
            // Update Context
            const selectElement = document.getElementById('algo-select');
            currentAlgoName = selectElement.options[selectElement.selectedIndex].text + ` (${qubits}q)`;
            updateContextBar();
        } else {
            throw new Error(data.error || "Failed to generate circuit.");
        }
    } catch (error) {
        console.error("Circuit generation failed:", error);
        alert("Circuit generation failed: " + error.message);
    } finally {
        setLoading(false);
        isProcessing = false;
    }
}

function addToBatch() {
    const algoId = document.getElementById('algo-select').value;
    const qubits = parseInt(document.getElementById('algo-qubits').value);

    // Explicitly grab the custom name and QASM content right now
    const algoName = document.getElementById('ctx-algo-name').value || "Custom Circuit";
    const currentQasm = qasmInput.value.trim();

    if (!algoId || isNaN(qubits)) return;

    batchQueue.push({
        algorithm: algoId,
        qubits: qubits,
        name: algoName,
        qasm_string: currentQasm || null
    });
    renderBatchQueue();

    if (playlistSection.classList.contains('hidden')) {
        playlistSection.classList.remove('hidden');
    }
}

function togglePlaylist() {
    if (playlistSection.classList.contains('hidden')) {
        playlistSection.classList.remove('hidden');
    } else {
        playlistSection.classList.add('hidden');
    }
}

function renderBatchQueue() {
    // --- FIX: Check if queueCount is defined (it might not be if onload failed) ---
    if (queueCount) {
        queueCount.textContent = batchQueue.length;
    }
    if (queueList) {
        queueList.innerHTML = '';

        if (batchQueue.length === 0) {
            queueList.innerHTML = '<li class="text-gray-400 italic text-center py-2 text-xs">Playlist is empty.</li>';
            return;
        }

        batchQueue.forEach((item, index) => {
            const li = document.createElement('li');
            li.className = "flex justify-between items-center bg-yellow-100 px-2 py-1 rounded";
            li.innerHTML = `
                        <span class="truncate flex-1 text-xs font-mono">${item.name} (${item.qubits}q)</span>
                        <div class="flex space-x-1 ml-2">
                            <button onclick="viewBatchItem(${index})" title="Load QASM to Editor" class="text-blue-600 hover:text-blue-800 font-bold px-1">{ }</button>
                            <button onclick="removeFromBatch(${index})" title="Remove" class="text-yellow-700 hover:text-red-600 font-bold px-1">&times;</button>
                        </div>
                    `;
            queueList.appendChild(li);
        });
    }
}

async function viewBatchItem(index) {
    if (isProcessing) return;
    const item = batchQueue[index];
    if (!item) return;

    if (item.qasm_string) {
        qasmInput.value = item.qasm_string;
        const sel = document.getElementById('algo-select');
        if (sel.querySelector(`option[value="${item.algorithm}"]`)) {
            sel.value = item.algorithm;
            document.getElementById('algo-qubits').value = item.qubits;
        }
        // Update Context
        document.getElementById('ctx-algo-name').value = item.name;
        currentAlgoName = item.name;
        updateContextBar();
        return;
    }

    qasmInput.value = "// Loading preview from playlist...";

    try {
        isProcessing = true;
        setLoading(true, "Loading Preview...");
        // --- FIX: Use BASE_URL for fetch ---
        const response = await fetch(`${BASE_URL}/generate_circuit`, {
            method: 'POST',
            headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ algorithm: item.algorithm, qubits: item.qubits })
        });
        const data = await response.json();
        if (response.ok) {
            qasmInput.value = data.qasm;
            const sel = document.getElementById('algo-select');
            if (sel.querySelector(`option[value="${item.algorithm}"]`)) {
                sel.value = item.algorithm;
                document.getElementById('algo-qubits').value = item.qubits;
            }
            // Update Context
            document.getElementById('ctx-algo-name').value = item.name + ` (${item.qubits}q)`;
            currentAlgoName = item.name + ` (${item.qubits}q)`;
            updateContextBar();
        } else {
            qasmInput.value = "// Error loading preview: " + data.error;
        }
    } catch (e) {
        qasmInput.value = "// Error: " + e.message;
    } finally {
        setLoading(false);
        isProcessing = false;
    }
}

function removeFromBatch(index) {
    batchQueue.splice(index, 1);
    renderBatchQueue();
}

function clearBatch() {
    batchQueue = [];
    renderBatchQueue();
}

async function runBatchQueue() {
    clearHistoryState();
    if (isProcessing) return;
    if (batchQueue.length === 0) return;

    const mode = document.querySelector('input[name="mode-batch"]:checked').value;
    const shots = parseInt(document.getElementById('shots-batch').value) || 1024;
    const globalOpt = parseInt(document.getElementById('opt-global')?.value || 0);
    const timeout = parseInt(document.getElementById('timeout-input')?.value || 60);
    const runNameInput = document.getElementById('batch-run-name')?.value.trim();
    currentRunnerConfig = getRunnerConfig();

    const targetSims = getTargetSimulators();
    if (targetSims.length === 0) {
        alert("Please select at least one simulator from the Config Panel to run.");
        return;
    }

    const payload = {
        tasks: batchQueue,
        mode: mode,
        n_shots: shots,
        optimization_level: globalOpt,
        timeout_seconds: timeout,
        runner_config: currentRunnerConfig,
        target_simulators: targetSims
    };

    setLoading(true, `Running Batch of ${batchQueue.length} Circuits...`);
    clearReport();

    try {
        isProcessing = true;
        // --- FIX: Use BASE_URL for fetch ---
        const res = await fetch(`${BASE_URL}/run_batch_suite`, {
            method: 'POST',
            headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const errorText = await res.text();
            throw new Error(`HTTP error! Status: ${res.status}. Details: ${errorText}`);
        }

        const data = await res.json();
        currentSuiteData = data;
        currentSuiteTitle = "Playlist Batch Report";
        renderSuiteSummary(data, currentSuiteTitle);

        // Save to History using the newly integrated API
        if (runNameInput) data.run_name = runNameInput;
        await saveRunToHistory(data);

    } catch (e) {
        console.error(e);
        renderSuiteSummary({ error: e.message }, "Batch Error");
    } finally {
        setLoading(false);
        isProcessing = false;
    }
}

// --- UI FIX: Decoupled Mode Toggles ---

function toggleSingleMode() {
    const mode = document.querySelector('input[name="mode-single"]:checked').value;
    const shotsContainer = document.getElementById('shots-container-single');
    if (mode === 'measured') {
        shotsContainer.classList.remove('hidden');
    } else {
        shotsContainer.classList.add('hidden');
    }
    updateQubitConstraints();
}

function toggleBatchMode() {
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
// --- END FIX ---

function handleRun() {
    const mode = document.querySelector('input[name="mode-single"]:checked').value;
    const shots = parseInt(document.getElementById('shots-single').value) || 1024;
    runComparison(mode, shots);
}


// --- AUTO-GENERATOR LOGIC ---
function openGeneratorModal() {
    const list = document.getElementById('gen-algo-list');
    list.innerHTML = '';
    allAlgorithms.forEach(algo => {
        const div = document.createElement('div');
        div.className = "flex items-center";
        div.innerHTML = `
                    <input type="checkbox" value="${algo.id}" checked class="h-4 w-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500">
                    <label class="ml-2 block text-gray-900">${algo.name}</label>
                `;
        list.appendChild(div);
    });
    document.getElementById('gen-modal').classList.remove('hidden');
}

function closeGeneratorModal() {
    document.getElementById('gen-modal').classList.add('hidden');
}

// --- CONFIG PANEL LOGIC ---

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
        { id: "projectq", name: "ProjectQ" },
        { id: "pennylane-lightning", name: "PL Lightning" },
        { id: "pennylane-default", name: "PL Default" }
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
    // Check if ALL are currently checked
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);

    // If all are checked, uncheck all. Otherwise (some or none checked), check all.
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
            nameSpan.value = currentAlgoName;
        } else {
            nameSpan.textContent = currentAlgoName;
        }
    }
    if (optSpan) optSpan.textContent = `Global Opt: ${level}`;
}

async function runAutoGeneration() {
    const checkboxes = document.querySelectorAll('#gen-algo-list input:checked');
    const selectedAlgos = Array.from(checkboxes).map(cb => cb.value);
    const minQ = parseInt(document.getElementById('gen-min').value);
    const maxQ = parseInt(document.getElementById('gen-max').value);
    const count = parseInt(document.getElementById('gen-count').value);

    if (selectedAlgos.length === 0) { alert("Select at least one algorithm."); return; }
    if (minQ > maxQ) { alert("Min qubits cannot be greater than Max qubits."); return; }

    setLoading(true, `Generating ${count} Circuits for Playlist...`);
    try {
        for (let i = 0; i < count; i++) {
            const algoId = selectedAlgos[Math.floor(Math.random() * selectedAlgos.length)];
            const algoMeta = allAlgorithms.find(a => a.id === algoId);

            const safeMin = Math.max(minQ, algoMeta.min_qubits || 2);
            const safeMax = Math.min(maxQ, algoMeta.max_qubits || 20);

            if (safeMin <= safeMax) {
                const q = Math.floor(Math.random() * (safeMax - safeMin + 1)) + safeMin;

                // Fetch literal QASM string from the backend for the generated task
                let qasmText = null;
                const response = await fetch(`${BASE_URL}/generate_circuit`, {
                    method: 'POST',
                    headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
                    body: JSON.stringify({ algorithm: algoId, qubits: q })
                });
                if (response.ok) {
                    const data = await response.json();
                    qasmText = data.qasm;
                } else {
                    console.warn(`Failed to pre-generate QASM for ${algoMeta.name} (${q}q)`);
                }

                batchQueue.push({
                    algorithm: algoId,
                    qubits: q,
                    name: algoMeta.name,
                    qasm_string: qasmText
                });
            }
        }
        renderBatchQueue();
        closeGeneratorModal();
    } catch (e) {
        console.error("Auto-generation failed", e);
        alert("Auto-generation failed: " + e.message);
    } finally {
        setLoading(false);
    }
}

// --- API CALLS (Single Run & Legacy) ---

async function runComparison(type, shots) {
    clearHistoryState();
    if (isProcessing) return;
    const qasm = qasmInput.value.trim();
    if (!qasm) { alert("Please enter QASM code."); return; }

    const globalOpt = parseInt(document.getElementById('opt-global')?.value || 0);
    const timeout = parseInt(document.getElementById('timeout-input')?.value || 60);
    const runNameInput = document.getElementById('single-run-name')?.value.trim();
    currentRunnerConfig = getRunnerConfig();

    const endpoint = type === 'statevector' ? '/compare' : '/compare_measured';
    const targetSims = getTargetSimulators();
    if (targetSims.length === 0) {
        alert("Please select at least one simulator from the Config Panel to run.");
        return;
    }

    const payload = {
        qasm_string: qasm,
        optimization_level: globalOpt,
        timeout_seconds: timeout,
        runner_config: currentRunnerConfig,
        target_simulators: targetSims
    };

    if (type === 'measured') {
        payload.n_shots = shots;
    }

    const title = type === 'statevector' ? 'Editor Run (Statevector)' : `Editor Run (Measured, ${shots} shots)`;

    setLoading(true, "Running Simulation...");
    clearReport();

    try {
        isProcessing = true;
        // --- FIX: Use BASE_URL for fetch ---
        const res = await fetch(`${BASE_URL}${endpoint}`, {
            method: 'POST',
            headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const errorText = await res.text();
            throw new Error(`HTTP error! Status: ${res.status} ${res.statusText}. Details: ${errorText}`);
        }

        const data = await res.json();
        currentSuiteData = data; // FIX: Set global data for single runs
        renderDetailReport(data, title, currentRunnerConfig);

        // Save to History using the newly integrated API
        if (runNameInput) data.run_name = runNameInput;
        await saveRunToHistory(data);
    } catch (e) {
        console.error(e);
        renderDetailReport({ error: e.message }, "Error");
    } finally {
        setLoading(false);
        isProcessing = false;
    }
}

// --- AUTH LOGIC ---

function openAuthModal() {
    document.getElementById('auth-modal').classList.remove('hidden');
    toggleAuthMode('login');
}

function closeAuthModal() {
    document.getElementById('auth-modal').classList.add('hidden');
    document.getElementById('login-email').value = '';
    document.getElementById('login-password').value = '';
    document.getElementById('register-email').value = '';
    document.getElementById('register-password').value = '';
    document.getElementById('login-error').classList.add('hidden');
    document.getElementById('register-error').classList.add('hidden');
}

function toggleAuthMode(mode) {
    if (mode === 'login') {
        document.getElementById('login-form-container').classList.remove('hidden');
        document.getElementById('register-form-container').classList.add('hidden');
    } else {
        document.getElementById('login-form-container').classList.add('hidden');
        document.getElementById('register-form-container').classList.remove('hidden');
    }
}

function updateAuthUI() {
    const loginBtn = document.getElementById('btn-login-modal');
    const userProfile = document.getElementById('user-profile');
    const emailDisplay = document.getElementById('user-email-display');

    if (authToken) {
        if (loginBtn) loginBtn.classList.add('hidden');
        if (userProfile) userProfile.classList.remove('hidden');
        try {
            const payload = JSON.parse(atob(authToken.split('.')[1]));
            if (emailDisplay) emailDisplay.textContent = payload.sub || 'User';
        } catch (e) {
            if (emailDisplay) emailDisplay.textContent = 'User (Logged In)';
        }
    } else {
        if (loginBtn) loginBtn.classList.remove('hidden');
        if (userProfile) userProfile.classList.add('hidden');
        if (emailDisplay) emailDisplay.textContent = '';
    }
}

async function handleLoginSubmit() {
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value.trim();
    const errorDiv = document.getElementById('login-error');

    if (!email || !password) {
        errorDiv.textContent = "Email and password are required.";
        errorDiv.classList.remove('hidden');
        return;
    }

    setLoading(true, "Logging in...");
    errorDiv.classList.add('hidden');

    try {
        const formData = new URLSearchParams();
        formData.append('username', email); // OAuth2 expects username
        formData.append('password', password);

        const res = await fetch(`${BASE_URL}/auth/token`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: formData.toString()
        });

        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.detail || "Login failed.");
        }

        authToken = data.access_token;
        localStorage.setItem('rosetta_token', authToken);
        updateAuthUI();
        closeAuthModal();

    } catch (e) {
        errorDiv.textContent = e.message;
        errorDiv.classList.remove('hidden');
    } finally {
        setLoading(false);
    }
}

async function handleRegisterSubmit() {
    const email = document.getElementById('register-email').value.trim();
    const password = document.getElementById('register-password').value.trim();
    const errorDiv = document.getElementById('register-error');

    if (!email || !password) {
        errorDiv.textContent = "Email and password are required.";
        errorDiv.classList.remove('hidden');
        return;
    }

    setLoading(true, "Creating account...");
    errorDiv.classList.add('hidden');

    try {
        const payload = { email: email, password: password };
        const res = await fetch(`${BASE_URL}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.detail || "Registration failed.");
        }

        // Auto-login after successful registration
        toggleAuthMode('login');
        document.getElementById('login-email').value = email;
        document.getElementById('login-password').value = password;
        await handleLoginSubmit();

    } catch (e) {
        errorDiv.textContent = e.message;
        errorDiv.classList.remove('hidden');
    } finally {
        setLoading(false);
    }
}

function handleLogout() {
    authToken = null;
    localStorage.removeItem('rosetta_token');
    updateAuthUI();
}

async function verifySession() {
    if (!authToken) return;
    try {
        const res = await fetch(`${BASE_URL}/auth/me`, {
            headers: getAuthHeaders()
        });
        if (!res.ok) {
            handleLogout();
        }
    } catch (e) {
        console.error("Session verification failed", e);
    }
}

async function handleDeleteAccount() {
    if (!confirm("Are you sure you want to permanently delete your account? This action cannot be undone.")) {
        return;
    }

    setLoading(true, "Deleting account...");
    try {
        const res = await fetch(`${BASE_URL}/auth/me`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });

        if (!res.ok) {
            throw new Error("Failed to delete account");
        }

        alert("Your account has been securely deleted.");
        handleLogout();
    } catch (e) {
        console.error("Account deletion failed:", e);
        alert("Error deleting account: " + e.message);
    } finally {
        setLoading(false);
    }
}

// --- HISTORY LOGIC ---

async function saveRunToHistory(payload) {
    if (!authToken) return;
    try {
        await fetch(`${BASE_URL}/history/runs`, {
            method: 'POST',
            headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(payload)
        });
    } catch (e) {
        console.error("Failed to save run to history:", e);
    }
}

async function openHistoryModal() {
    document.getElementById('history-modal').classList.remove('hidden');
    const list = document.getElementById('history-list');
    list.innerHTML = '<li class="py-4 text-center text-sm text-gray-500">Loading history...</li>';

    if (!authToken) {
        list.innerHTML = '<li class="py-4 text-center text-sm text-gray-500">Please login to view history.</li>';
        return;
    }

    try {
        const response = await fetch(`${BASE_URL}/history/runs`, {
            headers: getAuthHeaders()
        });
        if (!response.ok) throw new Error("Failed to fetch history");

        const runs = await response.json();
        if (runs.length === 0) {
            list.innerHTML = '<li class="py-4 text-center text-sm text-gray-500">No previous runs found.</li>';
            return;
        }

        // Sort descending by created_at natively via JS
        runs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

        list.innerHTML = '';
        runs.forEach(run => {
            const dateStr = new Date(run.created_at).toLocaleString();
            const li = document.createElement('li');
            li.className = "py-4 flex items-center justify-between";
            const runName = run.run_name || run.id.substring(0, 8);
            li.innerHTML = `
                <div class="flex items-center flex-1 min-w-0 pr-4">
                    <input type="checkbox" class="history-checkbox mr-4 h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded" value="${run.id}">
                    <div class="flex flex-col flex-1 min-w-0">
                        <div class="flex items-center">
                            <span id="run-name-text-${run.id}" class="text-sm font-medium text-indigo-600 truncate mr-2">${runName}</span>
                            <span class="text-xs text-gray-400 font-mono bg-gray-100 px-1 rounded border border-gray-200">${run.id.substring(0, 8)}</span>
                            <input id="run-name-input-${run.id}" type="text" class="hidden text-sm border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 w-full max-w-xs px-2 py-1" value="${runName}">
                            <button onclick="toggleEditRunName('${run.id}')" id="run-name-edit-btn-${run.id}" class="ml-2 text-xs text-gray-400 hover:text-gray-600">✏️</button>
                            <button onclick="saveRunName('${run.id}')" id="run-name-save-btn-${run.id}" class="hidden ml-2 text-xs font-medium text-green-600 hover:text-green-800">Save</button>
                            <button onclick="cancelEditRunName('${run.id}', '${runName}')" id="run-name-cancel-btn-${run.id}" class="hidden ml-2 text-xs font-medium text-red-600 hover:text-red-800">Cancel</button>
                        </div>
                        <span class="text-xs text-gray-500">${dateStr}</span>
                    </div>
                </div>
                <button onclick="loadHistoricalRun('${run.id}', '${runName.replace(/'/g, "\\'")}', '${run.created_at}')" class="text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-700 px-3 py-1.5 rounded-md shadow-sm transition-colors whitespace-nowrap">
                    View Results
                </button>
            `;
            list.appendChild(li);
        });
    } catch (e) {
        list.innerHTML = `<li class="py-4 text-center text-sm text-red-500">Error: ${e.message}</li>`;
    }
}

function clearHistoryState() {
    const banner = document.getElementById('history-active-banner');
    if (banner) {
        banner.remove();
    }
}

function toggleSelectAllHistory() {
    const selectAll = document.getElementById('history-select-all');
    const checkboxes = document.querySelectorAll('.history-checkbox');
    checkboxes.forEach(cb => cb.checked = selectAll.checked);
}

function toggleEditRunName(runId) {
    document.getElementById(`run-name-text-${runId}`).classList.add('hidden');
    document.getElementById(`run-name-edit-btn-${runId}`).classList.add('hidden');
    document.getElementById(`run-name-input-${runId}`).classList.remove('hidden');
    document.getElementById(`run-name-save-btn-${runId}`).classList.remove('hidden');
    document.getElementById(`run-name-cancel-btn-${runId}`).classList.remove('hidden');
    document.getElementById(`run-name-input-${runId}`).focus();
}

function cancelEditRunName(runId, originalName) {
    document.getElementById(`run-name-input-${runId}`).value = originalName;
    document.getElementById(`run-name-text-${runId}`).classList.remove('hidden');
    document.getElementById(`run-name-edit-btn-${runId}`).classList.remove('hidden');
    document.getElementById(`run-name-input-${runId}`).classList.add('hidden');
    document.getElementById(`run-name-save-btn-${runId}`).classList.add('hidden');
    document.getElementById(`run-name-cancel-btn-${runId}`).classList.add('hidden');
}

async function saveRunName(runId) {
    const input = document.getElementById(`run-name-input-${runId}`);
    const newName = input.value.trim();
    if (!newName) return;

    try {
        const res = await fetch(`${BASE_URL}/history/runs/${runId}`, {
            method: 'PATCH',
            headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ run_name: newName })
        });
        if (!res.ok) throw new Error("Failed to update run name");

        document.getElementById(`run-name-text-${runId}`).textContent = newName;
        document.getElementById(`run-name-cancel-btn-${runId}`).setAttribute('onclick', `cancelEditRunName('${runId}', '${newName}')`);
        cancelEditRunName(runId, newName);
    } catch (e) {
        console.error(e);
        alert("Failed to save run name.");
    }
}

async function deleteSelectedHistory() {
    const checkboxes = document.querySelectorAll('.history-checkbox:checked');
    const runIds = Array.from(checkboxes).map(cb => cb.value);
    if (runIds.length === 0) return;
    if (!confirm(`Are you sure you want to delete ${runIds.length} run(s)?`)) return;

    try {
        const res = await fetch(`${BASE_URL}/history/runs`, {
            method: 'DELETE',
            headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ run_ids: runIds })
        });
        if (!res.ok) throw new Error("Failed to delete runs");
        openHistoryModal(); // Refresh modal content
    } catch (e) {
        console.error(e);
        alert("Failed to delete runs.");
    }
}

async function downloadSelectedHistory() {
    const checkboxes = document.querySelectorAll('.history-checkbox:checked');
    const runIds = Array.from(checkboxes).map(cb => cb.value);
    if (runIds.length === 0) return;

    setLoading(true, "Downloading histories...");
    try {
        const fetches = runIds.map(id => fetch(`${BASE_URL}/history/runs/${id}`, { headers: getAuthHeaders() }).then(res => res.json()));
        const results = await Promise.all(fetches);

        const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `qrosetta_runs_batch_${Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (e) {
        console.error(e);
        alert("Failed to download runs.");
    } finally {
        setLoading(false);
    }
}

function closeHistoryModal() {
    document.getElementById('history-modal').classList.add('hidden');
}

async function loadHistoricalRun(runId, runName, createdAt) {
    if (!authToken) return;
    closeHistoryModal();
    setLoading(true, "Loading Past Run...");
    clearReport();

    try {
        const response = await fetch(`${BASE_URL}/history/runs/${runId}`, {
            headers: getAuthHeaders()
        });
        if (!response.ok) throw new Error("Failed to load historical run details.");

        const data = await response.json();
        currentSuiteData = data;

        // Show context header notifying user they are in historical view
        const historyBanner = document.createElement('div');
        historyBanner.id = "history-active-banner";
        historyBanner.className = "p-3 bg-yellow-50 border-b border-yellow-200 text-yellow-800 text-sm flex justify-between items-center";

        const displayDate = createdAt ? new Date(createdAt).toLocaleString() : new Date(data.created_at || Date.now()).toLocaleString();
        const displayTitle = runName ? `<strong>Viewing Past Run:</strong> ${runName} <span class="text-xs font-mono ml-2 opacity-75">(${runId.substring(0, 8)})</span> <span class="ml-2">- ${displayDate}</span>` : `<strong>Viewing Past Run:</strong> ${displayDate}`;

        historyBanner.innerHTML = `
            <div>${displayTitle}</div>
            <button onclick="clearHistoryView()" class="text-yellow-600 hover:text-yellow-900 font-bold underline">Close Results & Return to Editor</button>
        `;

        // Prepend banner to top of right panel UI
        const tabNav = document.getElementById('tab-nav');
        if (!document.getElementById('history-active-banner')) {
            tabNav.parentNode.insertBefore(historyBanner, tabNav);
        }

        const isBatch = !!data.benchmark_summary;
        if (isBatch) {
            currentSuiteTitle = "Historical Batch Run";
            renderSuiteSummary(data, currentSuiteTitle);
        } else {
            renderDetailReport(data, "Historical Single Run", {});
        }
    } catch (e) {
        console.error("Historical load fail:", e);
        renderDetailReport({ error: e.message }, "Error Loading History");
    } finally {
        setLoading(false);
    }
}

function clearHistoryView() {
    clearReport();
    const banner = document.getElementById('history-active-banner');
    if (banner) banner.remove();
}
