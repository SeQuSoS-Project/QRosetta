// Frontend logic for batch functionality.

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
        if (getState().batchQueue.length > 0 && !confirm("This will replace your current playlist. Continue?")) return;

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
            dispatch('SET_BATCH_QUEUE', selectedPreset);
            renderBatchQueue();
        } catch (e) {
            console.error("Preset loading failed", e);
            alert("Preset loading failed: " + e.message);
        } finally {
            setLoading(false);
        }
    }
}

function addToBatch() {
    const algoId = document.getElementById('algo-select').value;
    const qubits = parseInt(document.getElementById('algo-qubits').value);

    const algoName = document.getElementById('ctx-algo-name').value || "Custom Circuit";
    const currentQasm = qasmInput.value.trim();

    if (!algoId || isNaN(qubits)) return;
    const newItem = {
        algorithm: algoId,
        qubits: qubits,
        name: algoName,
        qasm_string: currentQasm || null
    };
    dispatch('SET_BATCH_QUEUE', [...getState().batchQueue, newItem]);
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
    if (queueCount) {
        queueCount.textContent = getState().batchQueue.length;
    }
    if (queueList) {
        queueList.innerHTML = '';

        if (getState().batchQueue.length === 0) {
            queueList.innerHTML = '<li class="text-gray-400 italic text-center py-2 text-xs">Playlist is empty.</li>';
            return;
        }

        getState().batchQueue.forEach((item, index) => {
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
    if (getState().isProcessing) return;
    const item = getState().batchQueue[index];
    if (!item) return;

    if (item.qasm_string) {
        qasmInput.value = item.qasm_string;
        const sel = document.getElementById('algo-select');
        if (sel.querySelector(`option[value="${item.algorithm}"]`)) {
            sel.value = item.algorithm;
            document.getElementById('algo-qubits').value = item.qubits;
        }

        document.getElementById('ctx-algo-name').value = item.name;
        dispatch('SET_CURRENT_ALGO_NAME', item.name);
        updateContextBar();
        return;
    }

    qasmInput.value = "";

    try {
        dispatch('SET_PROCESSING', true);
        setLoading(true, "Loading Preview...");
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

            document.getElementById('ctx-algo-name').value = item.name + ` (${item.qubits}q)`;
            dispatch('SET_CURRENT_ALGO_NAME', item.name + ` (${item.qubits}q)`);
            updateContextBar();
        } else {
            qasmInput.value = "";
        }
    } catch (e) {
        qasmInput.value = "";
    } finally {
        setLoading(false);
        dispatch('SET_PROCESSING', false);
    }
}

function removeFromBatch(index) {
    const newQ = [...getState().batchQueue]; newQ.splice(index, 1); dispatch('SET_BATCH_QUEUE', newQ);
    renderBatchQueue();
}

function clearBatch() {
    dispatch('SET_BATCH_QUEUE', []);
    renderBatchQueue();
}

function openGeneratorModal() {
    const list = document.getElementById('gen-algo-list');
    list.innerHTML = '';
    getState().allAlgorithms.forEach(algo => {
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
            const algoMeta = getState().allAlgorithms.find(a => a.id === algoId);

            const safeMin = Math.max(minQ, algoMeta.min_qubits || 2);
            const safeMax = Math.min(maxQ, algoMeta.max_qubits || 20);

            if (safeMin <= safeMax) {
                const q = Math.floor(Math.random() * (safeMax - safeMin + 1)) + safeMin;

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
                const newItem = {
                    algorithm: algoId,
                    qubits: q,
                    name: algoMeta.name,
                    qasm_string: qasmText
                };
                dispatch('SET_BATCH_QUEUE', [...getState().batchQueue, newItem]);
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