// Shared benchmark-selection logic used by both the Benchmarks panel (precise multi-select)
// and the Experiment panel (quick "add all of a suite"). One module so neither surface
// duplicates list-fetching, normalization, or queueing.
//
// Benchmark queue items are lightweight references resolved server-side at run time:
//   { source: 'mqt'|'qasmbench', algorithm, qubits, name, qasm_string: null }
// The batch worker and the experiment runner both resolve them via benchmark_library.

const _bmEntriesCache = {};   // suite -> normalized entries (fetched once)

function bmCurrentSuite() {
    return document.querySelector('input[name="bench-suite"]:checked')?.value || 'mqt';
}

// Max-qubit cap from the Benchmarks panel input (empty = no cap). Entries whose size is
// unknown (0, e.g. a name without an _n suffix) are kept so nothing is silently hidden.
function bmMaxQubits() {
    const v = parseInt(document.getElementById('bench-max-qubits')?.value);
    return Number.isFinite(v) && v > 0 ? v : Infinity;
}

function _bmWithinCap(entry, maxQ) {
    return !entry.qubits || entry.qubits <= maxQ;
}

function _bmParseQubits(name) {
    const m = String(name).match(/_n(\d+)$/);
    return m ? parseInt(m[1]) : 0;
}

// Fetch and normalize every circuit in a suite to a selectable entry.
async function bmSuiteEntries(suite) {
    if (_bmEntriesCache[suite]) return _bmEntriesCache[suite];
    const entries = [];
    if (suite === 'mqt') {
        const map = await fetchMQTList();   // { algorithm: [qubit sizes] }
        for (const algo of Object.keys(map).sort()) {
            for (const q of map[algo]) {
                entries.push({ suite, algorithm: algo, qubits: q, label: `${algo} (${q}q)` });
            }
        }
    } else {
        const names = await fetchQASMBenchList();   // [circuit names]
        for (const name of names) {
            entries.push({ suite, algorithm: name, qubits: _bmParseQubits(name), label: name });
        }
    }
    _bmEntriesCache[suite] = entries;
    return entries;
}

function bmEntryToQueueItem(e) {
    return {
        source: e.suite, algorithm: e.algorithm, qubits: e.qubits || 0,
        name: e.label || e.algorithm, qasm_string: null,
    };
}

function _bmItemKey(item) {
    if (item.source) return `${item.source}:${item.algorithm}:${item.qubits}`;
    return item.qasm_string ? `q:${item.name}:${item.qasm_string.length}` : `p:${item.algorithm}:${item.qubits}`;
}

// Add items to the batch queue, skipping ones already present. Returns the number added.
function bmAddToQueue(items) {
    const queue = [...getState().batchQueue];
    const seen = new Set(queue.map(_bmItemKey));
    let added = 0;
    for (const it of items) {
        const k = _bmItemKey(it);
        if (seen.has(k)) continue;
        seen.add(k);
        queue.push(it);
        added++;
    }
    if (added) {
        dispatch('SET_BATCH_QUEUE', queue);
        renderBatchQueue();
    }
    return added;
}

// --- Benchmarks panel: precise multi-select ------------------------------------------

async function bmLoadChecklist() {
    const list = document.getElementById('bench-checklist');
    if (!list) return;
    list.innerHTML = '<div class="text-emerald-500 italic">loading…</div>';
    try {
        await bmSuiteEntries(bmCurrentSuite());
        bmRenderChecklist();
    } catch (e) {
        list.innerHTML = `<div class="text-red-600">${e.message}</div>`;
    }
}

function bmRenderChecklist() {
    const list = document.getElementById('bench-checklist');
    if (!list) return;
    const suite = bmCurrentSuite();
    const filter = (document.getElementById('bench-filter')?.value || '').toLowerCase();
    const maxQ = bmMaxQubits();
    const entries = (_bmEntriesCache[suite] || [])
        .filter(e => e.label.toLowerCase().includes(filter) && _bmWithinCap(e, maxQ));

    list.innerHTML = '';
    if (entries.length === 0) {
        list.innerHTML = '<div class="text-emerald-500 italic">no matches</div>';
        bmUpdateSelectedCount();
        return;
    }
    for (const e of entries) {
        const id = `bm-${suite}-${e.algorithm}-${e.qubits}`;
        const row = document.createElement('label');
        row.className = 'flex items-center gap-2 cursor-pointer hover:bg-emerald-50 rounded px-1';
        row.innerHTML =
            `<input type="checkbox" class="bm-check" data-suite="${_escapeHtml(e.suite)}" data-algo="${_escapeHtml(e.algorithm)}" `
            + `data-qubits="${_escapeHtml(e.qubits)}" data-label="${_escapeHtml(e.label)}" id="${_escapeHtml(id)}" onchange="bmUpdateSelectedCount()">`
            + `<span class="font-mono truncate">${_escapeHtml(e.label)}</span>`;
        list.appendChild(row);
    }
    bmUpdateSelectedCount();
}

function bmSelectedItems() {
    return Array.from(document.querySelectorAll('.bm-check:checked')).map(cb => ({
        source: cb.dataset.suite, algorithm: cb.dataset.algo,
        qubits: parseInt(cb.dataset.qubits) || 0, name: cb.dataset.label, qasm_string: null,
    }));
}

function bmUpdateSelectedCount() {
    const el = document.getElementById('bench-selected-count');
    if (el) el.textContent = String(document.querySelectorAll('.bm-check:checked').length);
}

function bmToggleSelectAll() {
    const on = document.getElementById('bench-select-all')?.checked;
    document.querySelectorAll('.bm-check').forEach(cb => { cb.checked = on; });
    bmUpdateSelectedCount();
}

function bmAddSelectedToBatch() {
    const items = bmSelectedItems();
    if (items.length === 0) { alert('Select at least one benchmark circuit.'); return; }
    const added = bmAddToQueue(items);
    openDrawer('playlist-section');
    if (added < items.length) {
        // some were already queued
    }
}

// --- Experiment panel: quick "add all of a suite" ------------------------------------

async function bmAddAllOfSuite(suite, maxQubits) {
    try {
        const maxQ = Number.isFinite(maxQubits) && maxQubits > 0 ? maxQubits : Infinity;
        const entries = (await bmSuiteEntries(suite)).filter(e => _bmWithinCap(e, maxQ));
        const added = bmAddToQueue(entries.map(bmEntryToQueueItem));
        renderBatchQueue();
        const cap = Number.isFinite(maxQ) ? ` (≤ ${maxQ}q)` : '';
        alert(`Added ${added} ${suite === 'mqt' ? 'MQT Bench' : 'QASMBench'}${cap} circuit(s) to the batch`
            + (added === 0 ? ' (all already present or above the cap).' : '.'));
    } catch (e) {
        alert(e.message);
    }
}


// --- Benchmarks panel: selectors, single fetch, load-to-editor ----------------------
// (moved from app.js; the benchmark concern lives here)

let _mqtSizes = {};

async function populateBenchmarkSelectors() {
    try {
        const [mqt, qasm] = await Promise.all([fetchMQTList(), fetchQASMBenchList()]);
        _mqtSizes = mqt || {};

        const mqtSel = document.getElementById('bench-mqt-algo');
        if (mqtSel) {
            mqtSel.innerHTML = '';
            Object.keys(_mqtSizes).forEach(algo => {
                const o = document.createElement('option');
                o.value = algo;
                o.textContent = algo;
                mqtSel.appendChild(o);
            });
            mqtSel.onchange = updateMqtQubitRange;  // idempotent: won't stack on re-populate
            updateMqtQubitRange();
        }

        const qSel = document.getElementById('bench-qasmbench-circuit');
        if (qSel) {
            qSel.innerHTML = '';
            (qasm || []).forEach(name => {
                const o = document.createElement('option');
                o.value = name;
                o.textContent = name;
                qSel.appendChild(o);
            });
        }
    } catch (error) {
        console.error('Failed to load benchmark lists:', error);
    }
}

function updateMqtQubitRange() {
    const algo = document.getElementById('bench-mqt-algo')?.value;
    const sizes = _mqtSizes[algo] || [];
    const input = document.getElementById('bench-mqt-qubits');
    if (!input || sizes.length === 0) return;
    input.min = sizes[0];
    input.max = sizes[sizes.length - 1];
    const v = parseInt(input.value);
    if (!(v >= sizes[0] && v <= sizes[sizes.length - 1])) input.value = sizes[0];
}

function toggleBenchSuite() {
    const suite = document.querySelector('input[name="bench-suite"]:checked').value;
    const mqtOptions = document.getElementById('bench-mqt-options');
    const qasmbenchOptions = document.getElementById('bench-qasmbench-options');
    
    if (suite === 'mqt') {
        mqtOptions.classList.remove('hidden');
        qasmbenchOptions.classList.add('hidden');
    } else {
        mqtOptions.classList.add('hidden');
        qasmbenchOptions.classList.remove('hidden');
    }
    if (typeof bmLoadChecklist === 'function') bmLoadChecklist();
}

async function fetchBenchmarkQasm() {
    const suite = document.querySelector('input[name="bench-suite"]:checked').value;
    const errorDiv = document.getElementById('bench-error');
    errorDiv.classList.add('hidden');
    
    try {
        let data;
        let title = "";
        
        if (suite === 'mqt') {
            const algo = document.getElementById('bench-mqt-algo').value;
            const qubits = document.getElementById('bench-mqt-qubits').value;
            setLoading(true, "Fetching MQT Bench...", { overlay: false });
            data = await fetchMQTBench(algo, qubits);
            title = `MQT Bench: ${document.getElementById('bench-mqt-algo').options[document.getElementById('bench-mqt-algo').selectedIndex].text} (${qubits}q)`;
        } else {
            const circuit = document.getElementById('bench-qasmbench-circuit').value;
            setLoading(true, "Fetching QASMBench...", { overlay: false });
            data = await fetchQASMBench(circuit);
            title = `QASMBench: ${document.getElementById('bench-qasmbench-circuit').options[document.getElementById('bench-qasmbench-circuit').selectedIndex].text}`;
        }
        
        return { qasm: data.qasm, title: title };
    } catch (error) {
        errorDiv.textContent = error.message;
        errorDiv.classList.remove('hidden');
        return null;
    } finally {
        setLoading(false);
    }
}

async function loadBenchmark() {
    if (getState().isProcessing) return;
    const result = await fetchBenchmarkQasm();
    if (result && result.qasm) {
        qasmInput.value = result.qasm;
        dispatch('SET_CURRENT_ALGO_NAME', result.title);
        updateContextBar();
        closeDrawers();
    }
}

function addBenchmarkToBatch() {
    if (getState().isProcessing) return;
    const suite = bmCurrentSuite();
    let item;
    if (suite === 'mqt') {
        const algo = document.getElementById('bench-mqt-algo').value;
        const qubits = parseInt(document.getElementById('bench-mqt-qubits').value) || 0;
        if (!algo) return;
        item = { source: 'mqt', algorithm: algo, qubits, name: `${algo} (${qubits}q)`, qasm_string: null };
    } else {
        const circuit = document.getElementById('bench-qasmbench-circuit').value;
        if (!circuit) return;
        item = { source: 'qasmbench', algorithm: circuit, qubits: _bmParseQubits(circuit), name: circuit, qasm_string: null };
    }
    bmAddToQueue([item]);
    openDrawer('playlist-section');
}
