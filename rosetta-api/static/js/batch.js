// Frontend logic for batch functionality.

import { qasmInput, queueCount, queueList } from './dom.js';
import { BASE_URL, fetchMQTBench, fetchQASMBench, getAuthHeaders } from './api.js';
import { _parseQasmStats, updateContextBar } from './config.js';
import { closeDrawers, isDrawerOpen, openDrawer } from './drawers.js';
import { dispatch, getState } from './state.js';
import { setLoading } from './utils.js';

export const PRESETS = {
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
        { algorithm: "ghz", qubits: 18, name: "GHZ State (Entanglement)" }
    ],
    "stress": [
        { algorithm: "random", qubits: 18, name: "Random Circuit" },
        { algorithm: "bv", qubits: 18, name: "Bernstein-Vazirani" },
        { algorithm: "vqe", qubits: 18, name: "VQE Ansatz" }
    ]
};

export async function applyPreset() {
    const val = document.getElementById('preset-select').value;
    if (PRESETS[val]) {
        if (getState().batchQueue.length > 0 && !confirm("This will replace your current playlist. Continue?")) return;

        const cap = getState().maxQubitsStatevector;
        const selectedPreset = JSON.parse(JSON.stringify(PRESETS[val]))
            .map(item => ({ ...item, qubits: Math.min(item.qubits, cap) }));

        setLoading(true, `Loading Preset: ${val}...`, { overlay: false });
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

const _PLACEHOLDER_NAMES = new Set(['', 'no circuit loaded', 'custom / modified', 'custom circuit']);

/** A circuit name without a trailing qubit-count suffix such as " (4q)". */
export function bareCircuitName(name) {
    return String(name ?? '').replace(/(\s*\(\d+q\))+\s*$/, '').trim();
}

/** Queue label: the circuit's name followed by its qubit count, once. */
export function batchItemLabel(item) {
    const name = bareCircuitName(item.name) || item.algorithm || 'custom';
    return `${name} (${item.qubits}q)`;
}

/** A queue item as a BenchmarkTask: only the fields the server defines. */
export function toBatchTask(item) {
    const task = { algorithm: String(item.algorithm || 'custom'), qubits: parseInt(item.qubits) || 0 };
    if (item.qasm_string) task.qasm_string = item.qasm_string;
    if (item.source) task.source = item.source;
    return task;
}

export function addToBatch() {
    const algoId = document.getElementById('algo-select').value;
    const selectorQubits = parseInt(document.getElementById('algo-qubits').value);
    const currentQasm = qasmInput.value.trim();

    const selEl = /** @type {HTMLSelectElement} */ (document.getElementById('algo-select'));
    const selLabel = selEl.selectedIndex >= 0 ? selEl.options[selEl.selectedIndex].text : '';
    const loadedName = getState().currentAlgoName || '';
    const editorHoldsOtherPreset = !!algoId && !isNaN(selectorQubits) && /\(\d+q\)$/.test(loadedName)
        && loadedName !== `${selLabel} (${selectorQubits}q)`;

    let newItem;
    if (currentQasm && !editorHoldsOtherPreset) {
        const qubits = _parseQasmStats(currentQasm).qubits;
        const typed = bareCircuitName(document.getElementById('ctx-algo-name').value);
        const sel = /** @type {HTMLSelectElement} */ (document.getElementById('algo-select'));
        const algoLabel = sel.selectedIndex >= 0 ? sel.options[sel.selectedIndex].text : '';
        const fromGenerator = !!algoId && getState().currentAlgoName === `${algoLabel} (${qubits}q)`;
        const userName = _PLACEHOLDER_NAMES.has(typed.toLowerCase()) ? '' : typed;
        newItem = fromGenerator
            ? { algorithm: algoId, qubits, name: algoLabel, qasm_string: currentQasm }
            : { algorithm: userName || 'custom', qubits, name: userName || 'custom', qasm_string: currentQasm };
    } else {
        if (!algoId || isNaN(selectorQubits)) return;
        const sel = /** @type {HTMLSelectElement} */ (document.getElementById('algo-select'));
        newItem = { algorithm: algoId, qubits: selectorQubits, name: sel.options[sel.selectedIndex].text, qasm_string: null };
    }
    dispatch('SET_BATCH_QUEUE', [...getState().batchQueue, newItem]);
    renderBatchQueue();
    openDrawer('playlist-section');
}

export function togglePlaylist() {
    if (isDrawerOpen('playlist-section')) closeDrawers();
    else openDrawer('playlist-section');
}

export function renderBatchQueue() {
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
            const label = document.createElement('span');
            label.className = 'truncate flex-1 text-xs font-mono';
            label.textContent = batchItemLabel(item);
            const actions = document.createElement('div');
            actions.className = 'flex space-x-1 ml-2';
            const view = document.createElement('button');
            view.type = 'button';
            view.title = 'Load QASM to Editor';
            view.className = 'text-blue-600 hover:text-blue-800 font-bold px-1';
            view.textContent = '{ }';
            view.addEventListener('click', () => viewBatchItem(index));
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.title = 'Remove';
            remove.className = 'text-yellow-700 hover:text-red-600 font-bold px-1';
            remove.textContent = '\u00d7';
            remove.addEventListener('click', () => removeFromBatch(index));
            actions.append(view, remove);
            li.append(label, actions);
            queueList.appendChild(li);
        });
    }
}

export async function viewBatchItem(index) {
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

        document.getElementById('ctx-algo-name').value = batchItemLabel(item);
        dispatch('SET_CURRENT_ALGO_NAME', batchItemLabel(item));
        updateContextBar();
        return;
    }

    if (item.source === 'mqt' || item.source === 'qasmbench') {
        qasmInput.value = "";
        try {
            dispatch('SET_PROCESSING', true);
            setLoading(true, "Loading Preview...", { overlay: false });
            const data = item.source === 'mqt'
                ? await fetchMQTBench(item.algorithm, item.qubits)
                : await fetchQASMBench(item.algorithm);
            qasmInput.value = data.qasm || "";
            document.getElementById('ctx-algo-name').value = batchItemLabel(item);
            dispatch('SET_CURRENT_ALGO_NAME', batchItemLabel(item));
            updateContextBar();
        } catch (e) {
            qasmInput.value = "";
        } finally {
            setLoading(false);
            dispatch('SET_PROCESSING', false);
        }
        return;
    }

    qasmInput.value = "";

    try {
        dispatch('SET_PROCESSING', true);
        setLoading(true, "Loading Preview...", { overlay: false });
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

            document.getElementById('ctx-algo-name').value = batchItemLabel(item);
            dispatch('SET_CURRENT_ALGO_NAME', batchItemLabel(item));
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

export function removeFromBatch(index) {
    const newQ = [...getState().batchQueue]; newQ.splice(index, 1); dispatch('SET_BATCH_QUEUE', newQ);
    renderBatchQueue();
}

export function clearBatch() {
    dispatch('SET_BATCH_QUEUE', []);
    renderBatchQueue();
}

// Coerce one imported playlist entry to the fields the batch runner reads, so an
// uploaded file cannot introduce unexpected types or extra keys into the queue.
export function _normalizePlaylistItem(raw) {
    if (!raw || typeof raw !== 'object') return null;
    const str = (v) => (v === undefined || v === null ? '' : String(v));
    const qubits = Number.parseInt(raw.qubits, 10);
    return {
        name: bareCircuitName(str(raw.name)),
        algorithm: str(raw.algorithm),
        source: str(raw.source),
        qasm_string: str(raw.qasm_string),
        qubits: Number.isFinite(qubits) ? qubits : 0,
    };
}

export function importPlaylist(inputElement) {
    const file = inputElement.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function (e) {
        try {
            const loaded = JSON.parse(String(e.target.result));
            if (Array.isArray(loaded)) {
                const items = loaded.map(_normalizePlaylistItem).filter(Boolean);
                if (items.length !== loaded.length) {
                    alert(`Skipped ${loaded.length - items.length} malformed playlist entries.`);
                }
                dispatch('SET_BATCH_QUEUE', items);
                renderBatchQueue();
            } else {
                alert("Invalid playlist file format. Expected a JSON array.");
            }
        } catch (err) {
            console.error(err);
            alert("Error reading file: " + err.message);
        }
        inputElement.value = '';
    };
    reader.readAsText(file);
}

export function openGeneratorModal() {
    const list = document.getElementById('gen-algo-list');
    if (list && list.children.length === 0) {
        getState().allAlgorithms.forEach(algo => {
            const div = document.createElement('div');
            div.className = "flex items-center";
            div.innerHTML = `
                        <input type="checkbox" value="${algo.id}" checked class="h-4 w-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500">
                        <label class="ml-2 block text-gray-900">${algo.name}</label>
                    `;
            list.appendChild(div);
        });
    }
    document.getElementById('gen-modal').classList.remove('hidden');
}

export function closeGeneratorModal() {
    document.getElementById('gen-modal').classList.add('hidden');
}

export async function runAutoGeneration() {
    const checkboxes = document.querySelectorAll('#gen-algo-list input:checked');
    const selectedAlgos = Array.from(checkboxes).map(cb => cb.value);
    const minQ = parseInt(document.getElementById('gen-min').value);
    const maxQ = parseInt(document.getElementById('gen-max').value);
    const count = parseInt(document.getElementById('gen-count').value);

    if (selectedAlgos.length === 0) { alert("Select at least one algorithm."); return; }
    if (minQ > maxQ) { alert("Min qubits cannot be greater than Max qubits."); return; }

    setLoading(true, `Generating ${count} Circuits for Playlist...`, { overlay: false });
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