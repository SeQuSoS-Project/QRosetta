// The Playlist's Bench popover: tick MQT Bench or QASMBench circuits (with a name filter and a
// qubit cap) and add them, or add a whole suite. Single circuits come from the Quantum
// Algorithms menu. Queue items are references the server resolves at run time:
//   { source: 'mqt'|'qasmbench', algorithm, qubits, name, qasm_string: null }

import { fetchMQTList, fetchQASMBenchList } from './api.js';
import { renderBatchQueue } from './batch.js';
import { bindPopover, closePopover } from './popover.js';
import { dispatch, getState } from './state.js';
import { _escapeHtml } from './utils.js';

export const _bmEntriesCache = {};   // suite -> normalized entries (fetched once)
const _bmSelected = new Set();         // keys of ticked entries; kept across filter changes
const _bmEntryKey = e => `${e.suite}:${e.algorithm}:${e.qubits}`;

export function bmCurrentSuite() {
    return document.querySelector('input[name="bench-suite"]:checked')?.value || 'mqt';
}

// Max-qubit cap from the Bench popover input (empty = no cap). Entries whose size is
// unknown (0, e.g. a name without an _n suffix) are kept, as the cap cannot be checked.
export function bmMaxQubits() {
    const v = parseInt(document.getElementById('bench-max-qubits')?.value);
    return Number.isFinite(v) && v > 0 ? v : Infinity;
}

export function _bmWithinCap(entry, maxQ) {
    return !entry.qubits || entry.qubits <= maxQ;
}

export function _bmParseQubits(name) {
    const m = String(name).match(/_n(\d+)$/);
    return m ? parseInt(m[1]) : 0;
}

// Fetch and normalize every circuit in a suite to a selectable entry.
export async function bmSuiteEntries(suite) {
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

export function bmEntryToQueueItem(e) {
    return {
        source: e.suite, algorithm: e.algorithm, qubits: e.qubits || 0,
        name: e.label || e.algorithm, qasm_string: null,
    };
}

export function _bmItemKey(item) {
    if (item.source) return `${item.source}:${item.algorithm}:${item.qubits}`;
    return item.qasm_string ? `q:${item.name}:${item.qasm_string.length}` : `p:${item.algorithm}:${item.qubits}`;
}

// Add items to the batch queue, skipping ones already present. Returns the number added.
export function bmAddToQueue(items) {
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

// Bench popover: the checklist, its filter and the qubit cap.

export async function bmLoadChecklist() {
    const list = document.getElementById('bench-checklist');
    if (!list) return;
    list.innerHTML = '<div class="text-emerald-500 italic">loading…</div>';
    try {
        await bmSuiteEntries(bmCurrentSuite());
        bmRenderChecklist();
    } catch (e) {
        list.replaceChildren(Object.assign(document.createElement('div'), { className: 'text-red-600', textContent: e.message }));
    }
}

/** The entries the checklist shows: the chosen suite, filtered by name and the qubit cap. */
function _bmShownEntries() {
    const filter = (/** @type {HTMLInputElement|null} */ (document.getElementById('bench-filter'))?.value || '').toLowerCase();
    const maxQ = bmMaxQubits();
    return (_bmEntriesCache[bmCurrentSuite()] || []).filter(e => e.label.toLowerCase().includes(filter) && _bmWithinCap(e, maxQ));
}

export function bmRenderChecklist() {
    const list = document.getElementById('bench-checklist');
    if (!list) return;
    const suite = bmCurrentSuite();
    const entries = _bmShownEntries();
    const shownCount = document.getElementById('bench-shown-count');
    if (shownCount) shownCount.textContent = String(entries.length);

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
            + `data-qubits="${_escapeHtml(e.qubits)}" data-label="${_escapeHtml(e.label)}" id="${_escapeHtml(id)}">`
            + `<span class="font-mono truncate">${_escapeHtml(e.label)}</span>`;
        const box = row.querySelector('input');
        box.checked = _bmSelected.has(_bmEntryKey(e));
        box.addEventListener('change', () => {
            if (box.checked) _bmSelected.add(_bmEntryKey(e)); else _bmSelected.delete(_bmEntryKey(e));
            bmUpdateSelectedCount();
        });
        list.appendChild(row);
    }
    bmUpdateSelectedCount();
}

export function bmSelectedItems() {
    return Object.values(_bmEntriesCache).flat()
        .filter(e => _bmSelected.has(_bmEntryKey(e)))
        .map(bmEntryToQueueItem);
}

export function bmUpdateSelectedCount() {
    const el = document.getElementById('bench-selected-count');
    if (el) el.textContent = String(_bmSelected.size);
}

export function bmToggleSelectAll() {
    const on = document.getElementById('bench-select-all')?.checked;
    document.querySelectorAll('.bm-check').forEach(cb => {
        const box = /** @type {HTMLInputElement} */ (cb);
        box.checked = on;
        const key = `${box.dataset.suite}:${box.dataset.algo}:${box.dataset.qubits}`;
        if (on) _bmSelected.add(key); else _bmSelected.delete(key);
    });
    bmUpdateSelectedCount();
}

export function bmAddSelectedToBatch() {
    const items = bmSelectedItems();
    if (items.length === 0) { alert('Select at least one benchmark circuit.'); return; }
    const added = bmAddToQueue(items);
    _bmSelected.clear();
    const all = /** @type {HTMLInputElement|null} */ (document.getElementById('bench-select-all'));
    if (all) all.checked = false;
    bmRenderChecklist();
    closePopover(true);
    if (added) document.dispatchEvent(new Event('circuit-list-added'));
    if (added < items.length) {
        alert(`${items.length - added} of ${items.length} selected circuits were already in the playlist and were not added again.`);
    }
}

/** + Add all shown: every circuit the checklist shows (suite, name filter and qubit cap). */
export function bmAddAllShown() {
    const items = _bmShownEntries().map(bmEntryToQueueItem);
    if (!items.length) return;
    const added = bmAddToQueue(items);
    closePopover(true);
    if (added) document.dispatchEvent(new Event('circuit-list-added'));
    if (added < items.length) {
        alert(`${items.length - added} of ${items.length} circuits were already in the playlist and were not added again.`);
    }
}

/** Switching suites reloads the checklist. */
export function toggleBenchSuite() {
    bmLoadChecklist();
}

/** Wire the Playlist's Bench button to its popover. */
export function initBenchPopover() {
    const button = document.getElementById('btn-bench');
    const panel = document.getElementById('bench-popover');
    if (button && panel) bindPopover(button, panel, { onOpen: bmLoadChecklist, focusSelector: '#bench-filter' });
}
