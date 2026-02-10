// --- FIX: Define BASE_URL ---
const BASE_URL = '';

// --- GLOBAL STATE ---
let currentSuiteData = null;
let currentSuiteTitle = '';
let batchQueue = []; // Playlist
let allAlgorithms = []; // Metadata
let currentOptLevel = 0;
let currentAlgoName = "Custom";

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
        'suite-summary': document.getElementById('suite-summary-panel')
    };

    allButtons = [
        document.getElementById('btn-run'),
        document.getElementById('btn-batch-run')
    ];
    // --- END FIX ---

    try {
        // --- FIX: Use BASE_URL for fetch ---
        const response = await fetch(`${BASE_URL}/algorithms`);
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
    if (allAlgorithms.length > 0) {
        generateCircuit();
    }
    renderBatchQueue();
};

// --- METADATA UI LOGIC ---
function updateQubitConstraints() {
    const algoId = document.getElementById('algo-select').value;
    const selectedAlgo = allAlgorithms.find(a => a.id === algoId);
    const input = document.getElementById('algo-qubits');

    if (selectedAlgo) {
        if (selectedAlgo.min_qubits !== undefined) input.min = selectedAlgo.min_qubits;
        if (selectedAlgo.max_qubits !== undefined) input.max = selectedAlgo.max_qubits;
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

function applyPreset() {
    const val = document.getElementById('preset-select').value;
    if (PRESETS[val]) {
        if (batchQueue.length > 0 && !confirm("This will replace your current playlist. Continue?")) return;
        batchQueue = JSON.parse(JSON.stringify(PRESETS[val]));
        renderBatchQueue();
    }
}

async function generateCircuit() {
    const algoId = document.getElementById('algo-select').value;
    const qubits = parseInt(document.getElementById('algo-qubits').value);

    if (!algoId || isNaN(qubits)) {
        alert("Please select an algorithm and specify a valid number of qubits.");
        return;
    }

    setLoading(true);
    try {
        // --- FIX: Use BASE_URL for fetch ---
        const response = await fetch(`${BASE_URL}/generate_circuit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
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
    }
}

function addToBatch() {
    const algoId = document.getElementById('algo-select').value;
    const qubits = parseInt(document.getElementById('algo-qubits').value);
    const selectElement = document.getElementById('algo-select');
    const algoName = selectElement.options[selectElement.selectedIndex].text;

    if (!algoId || isNaN(qubits)) return;

    batchQueue.push({
        algorithm: algoId,
        qubits: qubits,
        name: algoName
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
    const item = batchQueue[index];
    if (!item) return;

    qasmInput.value = "// Loading preview from playlist...";

    try {
        setLoading(true);
        // --- FIX: Use BASE_URL for fetch ---
        const response = await fetch(`${BASE_URL}/generate_circuit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
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
            currentAlgoName = item.name + ` (${item.qubits}q)`;
            updateContextBar();
        } else {
            qasmInput.value = "// Error loading preview: " + data.error;
        }
    } catch (e) {
        qasmInput.value = "// Error: " + e.message;
    } finally {
        setLoading(false);
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
    if (batchQueue.length === 0) return;

    const mode = document.querySelector('input[name="mode-batch"]:checked').value;
    const shots = parseInt(document.getElementById('shots-batch').value) || 1024;

    const payload = {
        tasks: batchQueue,
        mode: mode,
        mode: mode,
        n_shots: shots,
        optimization_level: currentOptLevel
    };

    setLoading(true);
    clearReport();

    try {
        // --- FIX: Use BASE_URL for fetch ---
        const res = await fetch(`${BASE_URL}/run_batch_suite`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
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

    } catch (e) {
        console.error(e);
        renderSuiteSummary({ error: e.message }, "Batch Error");
    } finally {
        setLoading(false);
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

// --- NEW: Config Modal Logic ---
function openConfigModal() {
    document.getElementById('opt-level-select').value = currentOptLevel;
    document.getElementById('config-modal').classList.remove('hidden');
}

function closeConfigModal() {
    document.getElementById('config-modal').classList.add('hidden');
}

function saveConfig() {
    const val = parseInt(document.getElementById('opt-level-select').value);
    currentOptLevel = val;
    updateContextBar();
    closeConfigModal();
}

function updateContextBar() {
    const nameSpan = document.getElementById('ctx-algo-name');
    const optSpan = document.getElementById('ctx-opt-level');
    if (nameSpan) nameSpan.textContent = currentAlgoName;
    if (optSpan) optSpan.textContent = `Opt Level: ${currentOptLevel}`;
}

function runAutoGeneration() {
    const checkboxes = document.querySelectorAll('#gen-algo-list input:checked');
    const selectedAlgos = Array.from(checkboxes).map(cb => cb.value);
    const minQ = parseInt(document.getElementById('gen-min').value);
    const maxQ = parseInt(document.getElementById('gen-max').value);
    const count = parseInt(document.getElementById('gen-count').value);

    if (selectedAlgos.length === 0) { alert("Select at least one algorithm."); return; }
    if (minQ > maxQ) { alert("Min qubits cannot be greater than Max qubits."); return; }

    for (let i = 0; i < count; i++) {
        const algoId = selectedAlgos[Math.floor(Math.random() * selectedAlgos.length)];
        const algoMeta = allAlgorithms.find(a => a.id === algoId);

        const safeMin = Math.max(minQ, algoMeta.min_qubits || 2);
        const safeMax = Math.min(maxQ, algoMeta.max_qubits || 20);

        if (safeMin <= safeMax) {
            const q = Math.floor(Math.random() * (safeMax - safeMin + 1)) + safeMin;
            batchQueue.push({ algorithm: algoId, qubits: q, name: algoMeta.name });
        }
    }

    renderBatchQueue();
    closeGeneratorModal();
}

// --- API CALLS (Single Run & Legacy) ---

async function runComparison(type, shots) {
    const qasm = qasmInput.value.trim();
    if (!qasm) { alert("Please enter QASM code."); return; }

    const endpoint = type === 'statevector' ? '/compare' : '/compare_measured';
    const payload = type === 'statevector' ?
        { qasm_string: qasm, optimization_level: currentOptLevel } :
        { qasm_string: qasm, n_shots: shots, optimization_level: currentOptLevel };
    const title = type === 'statevector' ? 'Editor Run (Statevector)' : `Editor Run (Measured, ${shots} shots)`;

    setLoading(true);
    clearReport();

    try {
        // --- FIX: Use BASE_URL for fetch ---
        const res = await fetch(`${BASE_URL}${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!res.ok) {
            const errorText = await res.text();
            throw new Error(`HTTP error! Status: ${res.status} ${res.statusText}. Details: ${errorText}`);
        }

        const data = await res.json();
        currentSuiteData = data; // FIX: Set global data for single runs
        renderDetailReport(data, title);
    } catch (e) {
        console.error(e);
        renderDetailReport({ error: e.message }, "Error");
    } finally {
        setLoading(false);
    }
}
