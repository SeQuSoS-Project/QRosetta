// Frontend logic for batch functionality.

import { qasmInput, queueCount, queueList } from './dom.js';
import { BASE_URL, fetchMQTBench, fetchQASMBench, getAuthHeaders } from './api.js';
import { _parseQasmStats, updateContextBar } from './config.js';
import { playlistItemFor, selectionFor } from './circuit_sources.js';
import { saveBatchQueue } from './session_store.js';
import { dispatch, getState } from './state.js';
import { setLoading } from './utils.js';

/** Quick Load sets as preset references; the server generates each circuit when the batch runs. */
export function presetItems(key, algorithms, cap) {
    const meta = id => algorithms.find(a => a.id === id) || { id, name: id };
    const item = (id, qubits) => {
        const m = meta(id);
        const lo = m.min_qubits ?? 1;
        const hi = Math.min(m.max_qubits ?? cap, cap);
        return { algorithm: id, qubits: Math.max(lo, Math.min(qubits, hi)), name: m.name || id };
    };
    if (key === 'each') return algorithms.map(a => item(a.id, 5));
    if (key === 'scaling') return [...new Set([5, 10, 15, cap])].filter(q => q <= cap).map(q => item('ghz', q));
    if (key === 'largest') return ['random', 'bv', 'vqe'].map(id => item(id, cap));
    return [];
}

export function applyPreset() {
    const val = document.getElementById('preset-select').value;
    const st = getState();
    const items = presetItems(val, st.allAlgorithms || [], st.maxQubitsStatevector);
    if (!items.length) return;
    if (st.batchQueue.length > 0 && !confirm("This will replace your current playlist. Continue?")) return;
    dispatch('SET_BATCH_QUEUE', items);
    renderBatchQueue();
    document.dispatchEvent(new Event('circuit-list-added'));
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
    const name = bareCircuitName(item.name);
    if (name && name !== task.algorithm) task.name = name.slice(0, 200);
    if (item.qasm_string) task.qasm_string = item.qasm_string;
    if (item.source) task.source = item.source;
    return task;
}

/** + Add: the selected circuit (an algorithm or MQT Bench algorithm at the chosen qubit count, an example or a QASMBench circuit) added to the playlist. */
export async function addToBatch() {
    const menu = /** @type {HTMLSelectElement} */ (document.getElementById('algo-select'));
    const value = menu.value;
    if (!value) return;
    const sel = selectionFor(value);
    const qubits = parseInt(/** @type {HTMLInputElement} */ (document.getElementById('algo-qubits')).value, 10);
    let item;
    if (sel.kind === 'algorithm') {
        if (isNaN(qubits)) return;
        item = { algorithm: value, qubits, name: menu.options[menu.selectedIndex].text, qasm_string: null };
    } else {
        try {
            item = await playlistItemFor(sel, qubits);
        } catch (e) {
            alert(`The circuit was not added. ${e.message}`);
            return;
        }
    }
    dispatch('SET_BATCH_QUEUE', [...getState().batchQueue, item]);
    renderBatchQueue();
    document.dispatchEvent(new Event('circuit-list-added'));
}

/** + Add to Playlist in the Editor: the circuit in the editor, under its name. */
export function addEditorToPlaylist() {
    const qasm = qasmInput.value.trim();
    if (!qasm) { alert('The editor is empty.'); return; }
    const typed = bareCircuitName(/** @type {HTMLInputElement} */ (document.getElementById('ctx-algo-name')).value);
    const name = _PLACEHOLDER_NAMES.has(typed.toLowerCase()) ? 'custom' : typed;
    const item = { algorithm: name, qubits: _parseQasmStats(qasm).qubits, name, qasm_string: qasm };
    dispatch('SET_BATCH_QUEUE', [...getState().batchQueue, item]);
    renderBatchQueue();
    document.dispatchEvent(new Event('circuit-list-added'));
}

export function renderBatchQueue() {
    const stored = saveBatchQueue(getState().batchQueue);
    document.dispatchEvent(new Event('workspace-change'));
    if (queueCount) {
        queueCount.textContent = getState().batchQueue.length;
    }
    if (queueList) {
        queueList.innerHTML = '';

        const empty = getState().batchQueue.length === 0;
        queueList.classList.toggle('hidden', empty);
        document.getElementById('playlist-empty-hint')?.classList.toggle('hidden', !empty);
        if (empty) return;

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
            view.title = 'Show this circuit in the editor';
            view.className = 'text-xs text-blue-600 hover:text-blue-800 px-1';
            view.textContent = 'Open';
            view.addEventListener('click', () => viewBatchItem(index));
            const remove = document.createElement('button');
            remove.type = 'button';
            remove.title = 'Remove from the playlist';
            remove.setAttribute('aria-label', `Remove ${batchItemLabel(item)} from the playlist`);
            remove.className = 'text-yellow-700 hover:text-red-600 font-bold px-1';
            remove.textContent = '\u00d7';
            remove.addEventListener('click', () => removeFromBatch(index));
            actions.append(view, remove);
            li.append(label, actions);
            queueList.appendChild(li);
        });
        if (!stored) {
            const note = document.createElement('li');
            note.className = 'text-xs text-amber-700 py-1';
            note.textContent = 'This browser could not store the batch, so it will be empty after a reload.';
            queueList.appendChild(note);
        }
    }
}

/** Show a playlist item's source in the Quantum Algorithms menu when the menu has it. */
function _selectInMenu(item) {
    const menu = /** @type {HTMLSelectElement} */ (document.getElementById('algo-select'));
    const value = item.source === 'mqt' ? `mqt:${item.algorithm}`
        : item.source === 'qasmbench' ? `qasmbench:${item.algorithm}` : String(item.algorithm);
    if (!Array.from(menu.options).some(o => o.value === value)) return;
    menu.value = value;
    menu.dispatchEvent(new Event('change'));
    const qubits = /** @type {HTMLInputElement} */ (document.getElementById('algo-qubits'));
    if (!qubits.disabled && item.qubits) qubits.value = String(item.qubits);
}

export async function viewBatchItem(index) {
    if (getState().isProcessing) return;
    const item = getState().batchQueue[index];
    if (!item) return;

    _selectInMenu(item);
    if (item.qasm_string) {
        qasmInput.value = item.qasm_string;

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

export function runAutoGeneration() {
    const checkboxes = document.querySelectorAll('#gen-algo-list input:checked');
    const selectedAlgos = Array.from(checkboxes).map(cb => cb.value);
    const minQ = parseInt(document.getElementById('gen-min').value);
    const maxQ = parseInt(document.getElementById('gen-max').value);
    const count = parseInt(document.getElementById('gen-count').value);

    if (selectedAlgos.length === 0) { alert("Select at least one algorithm."); return; }
    if (minQ > maxQ) { alert("Min qubits cannot be greater than Max qubits."); return; }

    const st = getState();
    const measured = !(/** @type {HTMLInputElement|null} */ (document.getElementById('mode-statevector'))?.checked);
    const cap = measured ? st.maxQubitsMeasured : st.maxQubitsStatevector;
    const added = [];
    for (let i = 0; i < count; i++) {
        const algoId = selectedAlgos[Math.floor(Math.random() * selectedAlgos.length)];
        const algoMeta = st.allAlgorithms.find(a => a.id === algoId);
        const safeMin = Math.max(minQ, algoMeta.min_qubits || 2);
        const safeMax = Math.min(maxQ, algoMeta.max_qubits || cap, cap);
        if (safeMin <= safeMax) {
            const q = Math.floor(Math.random() * (safeMax - safeMin + 1)) + safeMin;
            added.push({ algorithm: algoId, qubits: q, name: algoMeta.name });
        }
    }
    if (added.length < count) {
        alert(`${count - added.length} of ${count} circuits were not added: no qubit count in ${minQ}–${maxQ} fits the chosen algorithm and the ${cap}-qubit limit.`);
    }
    dispatch('SET_BATCH_QUEUE', [...st.batchQueue, ...added]);
    renderBatchQueue();
    closeGeneratorModal();
    if (added.length) document.dispatchEvent(new Event('circuit-list-added'));
}
