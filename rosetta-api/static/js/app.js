// Page bootstrap: server limits and defaults, the preset list, circuit generation, and the
// offer to resume a job after a reload.

import { BASE_URL, apiDetailText, getAuthHeaders } from './api.js';
import { updateAuthUI, verifySession } from './auth.js';
import { initAutosave } from './autosave.js';
import { loadCompilers } from './compilers_config.js';
import { renderBatchQueue } from './batch.js';
import { initBenchPopover } from './benchmarks_select.js';
import { getDynamicMaxQubits, loadRunners, updateContextBar } from './config.js';
import { saveRunToHistory, showHistoryNotice } from './history.js';
import { setRunSaver } from './share_links.js';
import { initDomRefs, qasmInput, setAllButtons, welcomeMessage } from './dom.js';
import { shotsRange, timeoutRange } from './run_inputs.js';
import { clearPendingJob, loadBatchQueue, loadEditorCircuit, loadPendingJob, saveEditorCircuit } from './session_store.js';
import { dispatch, getState } from './state.js';
import { resetAgreementThresholds, setLoading } from './utils.js';
import { fetchSelection, loadCircuitSources, menuGroups, nearestSize, selectionFor } from './circuit_sources.js';
import { initCircuitPicker } from './circuit_picker.js';
import { resumeJob, updateWorkspace } from './workspace.js';
import { initSettingsBar } from './settings_bar.js';

const EXECUTION_MODE_LABELS = {
    local: 'This server: local runner services',
    kubernetes: 'This server: Kubernetes Jobs',
};

/** Execution-target menu, timeout and shots bounds, and threshold defaults from GET /config. */
function _applyServerConfig(config) {
    const mode = getState().executionMode;
    const select = /** @type {HTMLSelectElement|null} */ (document.getElementById('execution-target-select'));
    if (select && mode) {
        select.innerHTML = '';
        const opt = document.createElement('option');
        opt.value = mode;
        opt.textContent = EXECUTION_MODE_LABELS[mode] || mode;
        select.appendChild(opt);
        select.value = mode;
        select.disabled = true;
    }

    const { min: tMin, max: tMax } = timeoutRange();
    const tInput = /** @type {HTMLInputElement|null} */ (document.getElementById('timeout-input'));
    if (tInput) {
        tInput.min = String(tMin);
        tInput.max = String(tMax);
        const dflt = getState().timeoutDefault;
        if (tInput.value === tInput.defaultValue && Number.isFinite(dflt)) {
            tInput.value = String(dflt);
            tInput.defaultValue = String(dflt);
        }
        const current = Number(tInput.value);
        if (!Number.isFinite(current) || current > tMax) tInput.value = String(tMax);
    }
    const rInput = /** @type {HTMLInputElement|null} */ (document.getElementById('timing-repeats-input'));
    if (rInput) rInput.max = String(getState().timingRepeatsMax);
    if (!getState().exclusiveEnabled) {
        const exclusiveBox = /** @type {HTMLInputElement|null} */ (document.getElementById('exclusive-checkbox'));
        if (exclusiveBox) exclusiveBox.checked = false;
        document.getElementById('exclusive-container')?.classList.add('hidden');
    }
    const tHelp = document.getElementById('timeout-help');
    if (tHelp) {
        tHelp.textContent = `Covers process start, the warm-up run and every timed run. Allowed: ${tMin}–${tMax} s.`
            + (typeof config?.queue_max_wait_sec === 'number' && mode === 'local'
                ? ` Waiting for a busy backend is not counted (at most ${config.queue_max_wait_sec} s).` : '');
    }

    const { min: sMin, max: sMax } = shotsRange();
    ['shots-single'].forEach(id => {
        const el = /** @type {HTMLInputElement|null} */ (document.getElementById(id));
        if (!el) return;
        el.min = String(sMin);
        if (sMax !== null && sMax !== undefined) el.max = String(sMax);
        const dflt = config?.default_n_shots ?? config?.limits?.default_n_shots;
        if (typeof dflt === 'number' && Number.isInteger(dflt) && el.value === el.defaultValue) {
            el.value = String(dflt);
            el.defaultValue = String(dflt);
        }
    });

    if (config.agreement_threshold_defaults) resetAgreementThresholds();
}

let _editorSaveTimer = null;
function _saveEditorSoon() {
    if (_editorSaveTimer) clearTimeout(_editorSaveTimer);
    _editorSaveTimer = setTimeout(() => {
        saveEditorCircuit(qasmInput.value, getState().currentAlgoName);
    }, 400);
}

function _restoreEditorCircuit() {
    const saved = loadEditorCircuit();
    if (!saved) return false;
    qasmInput.value = saved.qasm;
    dispatch('SET_CURRENT_ALGO_NAME', saved.name);
    updateContextBar();
    return true;
}

function _hideResumeBanner() {
    document.getElementById('resume-job-banner')?.classList.add('hidden');
}

function _offerPendingJob() {
    const job = loadPendingJob();
    const banner = document.getElementById('resume-job-banner');
    if (!job || !banner) return;
    const when = new Date(job.submitted_at).toLocaleTimeString();
    const text = document.getElementById('resume-job-text');
    const notStarted = Array.isArray(job.remaining) && job.remaining.length
        ? ` Not started: ${job.remaining.join('; ')}.` : '';
    if (text) text.textContent = `A run submitted at ${when} (${job.run_name || job.title}) had not finished loading when the page was closed.${notStarted}`;
    banner.classList.remove('hidden');
    document.getElementById('resume-job-btn')?.addEventListener('click', () => {
        _hideResumeBanner();
        if (getState().isProcessing) return;
        resumeJob(job);
    }, { once: true });
    document.getElementById('resume-job-discard')?.addEventListener('click', () => {
        clearPendingJob(job.job_id);
        _hideResumeBanner();
    }, { once: true });
}

window.onload = async () => {

    initDomRefs();
    document.getElementById('history-save-notice-close')?.addEventListener('click', () => showHistoryNotice(''));
    const launchers = ['generateCircuit()', 'addToBatch()', 'applyPreset()',
        'bmAddSelectedToBatch()', 'runAutoGeneration()', 'clearBatch()', 'addEditorToPlaylist()']
        .flatMap(call => Array.from(document.querySelectorAll(`button[onclick="${call}"]`)));
    setAllButtons([document.getElementById('btn-run'), ...launchers]);

    updateAuthUI();
    verifySession();

    let restored = false;
    try {
        const [algorithmsResponse, configResponse] = await Promise.all([
            fetch(`${BASE_URL}/algorithms`, { headers: getAuthHeaders() }),
            fetch(`${BASE_URL}/config`),
        ]);
        if (!algorithmsResponse.ok) throw new Error('Failed to fetch algorithms');
        dispatch('SET_ALGORITHMS', await algorithmsResponse.json());
        if (configResponse.ok) {
            const config = await configResponse.json();
            dispatch('SET_CONFIG_LIMITS', config);
            _applyServerConfig(config);
            // The API honours bypass_limits only in local mode.
            if (config.execution_mode !== 'local') {
                const bypassContainer = document.getElementById('bypass-limits-container');
                if (bypassContainer) bypassContainer.classList.add('hidden');
                const bypassCheckbox = document.getElementById('bypass-limits-checkbox');
                if (bypassCheckbox) bypassCheckbox.checked = false;
            }
        }
        loadRunners();
        loadCompilers();
        setRunSaver(jobId => {
            const data = getState().currentSuiteData;
            const name = data && getState().currentJobId === jobId && typeof data.run_name === 'string' ? data.run_name : null;
            return saveRunToHistory(jobId, name);
        });

        const select = /** @type {HTMLSelectElement} */ (document.getElementById('algo-select'));
        await loadCircuitSources();
        const group = (label, items) => {
            const g = document.createElement('optgroup');
            g.label = label;
            items.forEach(([value, text]) => {
                const option = document.createElement('option');
                option.value = value;
                option.textContent = text;
                g.appendChild(option);
            });
            return g;
        };
        select.replaceChildren(...menuGroups(getState().allAlgorithms).map(([label, items]) => group(label, items)));
        initCircuitPicker({
            input: /** @type {HTMLInputElement} */ (document.getElementById('algo-search')),
            listbox: /** @type {HTMLElement} */ (document.getElementById('algo-listbox')),
            select,
        });

        select.addEventListener('change', updateQubitConstraints);
        document.getElementById('algo-qubits')?.addEventListener('change', _snapBenchSize);
        updateQubitConstraints();

        qasmInput.addEventListener('input', () => {
            dispatch('SET_CURRENT_ALGO_NAME', "Custom / Modified");
            updateContextBar();
            _saveEditorSoon();
            document.dispatchEvent(new Event('workspace-change'));
        });
        restored = _restoreEditorCircuit();
        updateContextBar();

    } catch (error) {
        console.error("Failed to load algorithms:", error);
        welcomeMessage.innerHTML = `<div class="p-4 bg-red-100 text-red-700 rounded"><strong>Connection Error:</strong> Could not load algorithms from ${BASE_URL}. Is the server running?</div>`;
        welcomeMessage.classList.remove('text-gray-500');
    }

    initBenchPopover();
    initSettingsBar();

    if (!restored && getState().allAlgorithms.length > 0) {
        generateCircuit();
    }
    dispatch('SET_BATCH_QUEUE', loadBatchQueue());
    renderBatchQueue();
    if (typeof initAutosave === 'function') initAutosave();
    updateWorkspace();
    _offerPendingJob();
};

/** For an MQT Bench algorithm, move the Qubits field to the nearest size the suite has. */
function _snapBenchSize() {
    const sel = selectionFor(/** @type {HTMLSelectElement} */ (document.getElementById('algo-select')).value);
    if (sel.kind !== 'mqt') return;
    const input = /** @type {HTMLInputElement} */ (document.getElementById('algo-qubits'));
    input.value = String(nearestSize(sel.sizes, parseInt(input.value, 10) || sel.sizes[0]));
}

export function updateQubitConstraints(e) {
    const algoId = /** @type {HTMLSelectElement} */ (document.getElementById('algo-select')).value;
    const selectedAlgo = getState().allAlgorithms.find(a => a.id === algoId);
    const input = /** @type {HTMLInputElement} */ (document.getElementById('algo-qubits'));
    const desc = document.getElementById('algo-description');
    const sel = selectionFor(algoId);
    if (sel.kind === 'example' || sel.kind === 'qasmbench') {
        input.value = String(sel.qubits || '');
        input.disabled = true;
        input.title = `A fixed ${sel.qubits}-qubit circuit.`;
        if (desc) {
            desc.textContent = sel.kind === 'example'
                ? `${sel.example?.description || ''} For ${sel.example?.mode} mode: Load ticks ${sel.example?.mode === 'measured' ? 'Measured' : 'Statevector'}.`.trim()
                : `QASMBench circuit, ${sel.qubits} qubits.`;
        }
        return;
    }
    if (sel.kind === 'mqt') {
        input.disabled = false;
        input.title = '';
        input.min = String(sel.sizes[0] ?? 1);
        input.max = String(sel.sizes[sel.sizes.length - 1] ?? 1);
        const current = parseInt(input.value, 10);
        input.value = String(nearestSize(sel.sizes, Number.isFinite(current) ? current : sel.sizes[0]));
        if (desc) desc.textContent = `MQT Bench algorithm. Sizes in the suite: ${sel.sizes[0]}–${sel.sizes[sel.sizes.length - 1]} qubits; the Qubits field picks one.`;
        return;
    }

    if (selectedAlgo) {
        const min = selectedAlgo.min_qubits ?? 1;
        const max = Math.min(selectedAlgo.max_qubits || 24, getDynamicMaxQubits());
        input.min = String(min);
        input.max = String(max);
        const isAlgoChange = e && e.type === 'change';
        if (isAlgoChange || !input.value) {
            if (selectedAlgo.default_qubits !== undefined) input.value = String(selectedAlgo.default_qubits);
        } else {
            const val = parseInt(input.value, 10);
            if (!isNaN(val)) input.value = String(Math.min(max, Math.max(min, val)));
        }

        input.disabled = selectedAlgo.min_qubits === selectedAlgo.max_qubits;
        input.title = input.disabled ? `${selectedAlgo.name} is defined for ${selectedAlgo.min_qubits} qubits only.` : '';
        if (desc) desc.textContent = selectedAlgo.description || '';
    }
}

/** True when the editor holds text the user typed or changed, which Load would replace. */
function _editorHasEdits() {
    return qasmInput.value.trim() !== '' && /^Custom\b/.test(getState().currentAlgoName || '');
}

/** Put an example or benchmark circuit in the editor; an example also ticks the mode it is meant for. */
async function _loadSelection(sel, qubits) {
    const { qasm, title } = await fetchSelection(sel, qubits);
    qasmInput.value = qasm;
    dispatch('SET_CURRENT_ALGO_NAME', title);
    if (sel.kind === 'example') {
        const sv = /** @type {HTMLInputElement|null} */ (document.getElementById('mode-statevector'));
        const ms = /** @type {HTMLInputElement|null} */ (document.getElementById('mode-measured'));
        if (sv && ms) { sv.checked = sel.example?.mode === 'statevector'; ms.checked = sel.example?.mode === 'measured'; }
    }
    updateContextBar();
    saveEditorCircuit(qasmInput.value, getState().currentAlgoName);
    document.dispatchEvent(new Event('editor-loaded'));
}

/** Load: the selected circuit into the editor, asking first when that replaces edits. */
/** Select `value` in the Quantum Algorithms menu and load it into the editor. */
async function _openCircuit(value) {
    const select = /** @type {HTMLSelectElement|null} */ (document.getElementById('algo-select'));
    if (!select || ![...select.options].some(o => o.value === value)) return;
    select.value = value;
    select.dispatchEvent(new Event('change'));
    await generateCircuit();
}

document.addEventListener('open-circuit', e => { _openCircuit(/** @type {CustomEvent} */ (e).detail); });

export async function generateCircuit() {
    if (getState().isProcessing) return;
    if (_editorHasEdits() && !confirm('Load replaces the circuit in the editor, which you have edited. Continue?')) return;
    const algoId = /** @type {HTMLSelectElement} */ (document.getElementById('algo-select')).value;
    const sel = selectionFor(algoId);
    if (sel.kind !== 'algorithm') {
        dispatch('SET_PROCESSING', true);
        setLoading(true, 'Loading circuit...', { overlay: false });
        try {
            await _loadSelection(sel, parseInt(/** @type {HTMLInputElement} */ (document.getElementById('algo-qubits')).value, 10));
        } catch (e) {
            alert(`The circuit was not loaded. ${e.message}`);
        } finally {
            setLoading(false);
            dispatch('SET_PROCESSING', false);
        }
        return;
    }
    const qubits = parseInt(document.getElementById('algo-qubits').value);

    if (!algoId || isNaN(qubits)) {
        alert("Please select an algorithm and specify a valid number of qubits.");
        return;
    }

    dispatch('SET_PROCESSING', true);
    setLoading(true, "Generating Circuit...", { overlay: false });
    try {
        const response = await fetch(`${BASE_URL}/generate_circuit`, {
            method: 'POST',
            headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ algorithm: algoId, qubits: qubits })
        });
        const data = await response.json();
        if (response.ok) {
            qasmInput.value = data.qasm;

            const selectElement = document.getElementById('algo-select');
            dispatch('SET_CURRENT_ALGO_NAME', selectElement.options[selectElement.selectedIndex].text + ` (${qubits}q)`);
            updateContextBar();
            saveEditorCircuit(qasmInput.value, getState().currentAlgoName);
            document.dispatchEvent(new Event('editor-loaded'));
        } else {
            throw new Error(apiDetailText(data.detail) || data.error || "Failed to generate circuit.");
        }
    } catch (error) {
        console.error("Circuit generation failed:", error);
        alert("Circuit generation failed: " + error.message);
    } finally {
        setLoading(false);
        dispatch('SET_PROCESSING', false);
    }
}
