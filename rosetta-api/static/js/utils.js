// Frontend logic for utils functionality.

import { allButtons } from './dom.js';
import { BASE_URL, getAuthHeaders } from './api.js';

import { renderBatchProgress, _stopRunnerCardTimer } from './status_cards.js';
import { dispatch, getState } from './state.js';

export function isConnectionError(errorMsg) {
    if (!errorMsg) return false;
    const msg = errorMsg.toLowerCase();
    return msg.includes("connection refused") ||
        msg.includes("name or service not known") ||
        msg.includes("failed to connect") ||
        msg.includes("failed to fetch") ||
        msg.includes("load resource") ||
        msg.includes("failed to get response") ||
        msg.includes("502 bad gateway") ||
        msg.includes("service unavailable") ||
        msg.includes("failed to decode json");
}

export let _loaderElapsedTimer = null;

// options.overlay (default true): when true, show the full results-panel processing
// overlay (used by actual benchmark runs). When false, show only a small busy toast so
// circuit-prep actions (generate / preset / auto-gen / benchmark fetch) don't blank out
// any result already displayed on the right.
export function setLoading(isLoading, message = "Processing...", options = {}) {
    const overlay = options.overlay !== false;
    const loader = document.getElementById('loader');
    const loaderText = document.getElementById('loader-text');
    const busyToast = document.getElementById('busy-toast');
    const busyToastText = document.getElementById('busy-toast-text');

    if (isLoading) {
        if (overlay) {
            if (loaderText) loaderText.textContent = message;
            renderBatchProgress(null);  // clear stale batch list
            loader.classList.remove('hidden');
            loader.classList.add('flex');
            if (!_loaderElapsedTimer) {
                const startTime = Date.now();
                const elapsedEl = document.getElementById('loader-elapsed');
                if (elapsedEl) elapsedEl.textContent = '0s elapsed';
                _loaderElapsedTimer = setInterval(() => {
                    const el = document.getElementById('loader-elapsed');
                    if (el) el.textContent = `${Math.floor((Date.now() - startTime) / 1000)}s elapsed`;
                }, 1000);
            }
        } else if (busyToast) {
            if (busyToastText) busyToastText.textContent = message;
            busyToast.classList.remove('hidden');
            busyToast.classList.add('flex');
        }
        allButtons.forEach(btn => { if (btn) btn.disabled = true });
    } else {
        loader.classList.add('hidden');
        loader.classList.remove('flex');
        if (busyToast) {
            busyToast.classList.add('hidden');
            busyToast.classList.remove('flex');
        }
        allButtons.forEach(btn => { if (btn) btn.disabled = false });
        if (_loaderElapsedTimer) {
            clearInterval(_loaderElapsedTimer);
            _loaderElapsedTimer = null;
        }
        _stopRunnerCardTimer();
        const grid = document.getElementById('runner-status-grid');
        if (grid) grid.innerHTML = '';
        const elapsedEl = document.getElementById('loader-elapsed');
        if (elapsedEl) elapsedEl.textContent = '0s elapsed';
    }
}

// --- Reusable copy affordances -------------------------------------------------------
export const COPY_ICON_SVG = '<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>';

export function _flashCopied(btn) {
    if (!btn) return;
    const old = btn.innerHTML;
    btn.innerHTML = '<span class="text-xs font-medium">✓ Copied</span>';
    btn.disabled = true;
    setTimeout(() => { btn.innerHTML = old; btn.disabled = false; }, 1500);
}

export function copyText(text, btn) {
    navigator.clipboard.writeText(text)
        .then(() => _flashCopied(btn))
        .catch(err => { console.error(err); alert('Copy failed.'); });
}

export async function copyImageToClipboard(blob, btn) {
    try {
        await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })]);
        _flashCopied(btn);
    } catch (err) {
        console.error(err);
        alert('Copy image failed (your browser may block image clipboard). Use Download instead.');
    }
}

// Build a small copy-icon button. `getText` may be a string or a () => string.
export function makeCopyIconButton(getText, title = 'Copy to clipboard') {
    const btn = document.createElement('button');
    btn.className = 'inline-flex items-center gap-1 text-gray-600 hover:text-gray-900 bg-gray-100 hover:bg-gray-200 border border-gray-300 rounded-md px-2 py-1 transition-all';
    btn.title = title;
    btn.innerHTML = COPY_ICON_SVG;
    btn.onclick = () => copyText(typeof getText === 'function' ? getText() : getText, btn);
    return btn;
}

// Copy the current input-circuit QASM from the editor.
export function copyCircuitQasm(btn) {
    const el = document.getElementById('qasm-input');
    if (el) copyText(el.value || '', btn);
}

export function downloadFullReport() {

    window.location.href = `${BASE_URL}/download_latest_report`;
}

export function _stripStatevectors(data) {
    if (Array.isArray(data)) {
        return data.map(_stripStatevectors);
    }
    if (data && typeof data === 'object') {
        const out = {};
        for (const [k, v] of Object.entries(data)) {
            if (k === 'statevector') continue;
            out[k] = _stripStatevectors(v);
        }
        return out;
    }
    return data;
}

export function togglePublicationOptions() {
    const enabled = document.getElementById('pub-enable')?.checked;
    const opts = document.getElementById('pub-options');
    if (opts) opts.classList.toggle('hidden', !enabled);
}

export function _readPublicationSelection() {
    // Returns null (omitted) unless the master checkbox is on and >=1 category selected.
    if (!document.getElementById('pub-enable')?.checked) return null;
    const vals = (sel) => Array.from(document.querySelectorAll(sel))
        .filter(el => el.checked).map(el => el.value);
    const categories = vals('.pub-category');
    if (categories.length === 0) return null;
    const figure_formats = vals('.pub-figfmt');
    const table_formats = vals('.pub-tblfmt');
    return {
        categories,
        figure_formats: figure_formats.length ? figure_formats : ['svg'],
        table_formats: table_formats.length ? table_formats : ['csv'],
    };
}

export async function exportRoCrate() {
    const results = getState().currentSuiteData;
    if (!results) {
        alert("No results to export. Run a comparison first.");
        return;
    }

    const includeStatevectors = document.getElementById('export-include-sv')?.checked || false;
    const authorName = document.getElementById('export-author-name')?.value.trim() || null;
    const authorAffiliation = document.getElementById('export-author-affiliation')?.value.trim() || null;
    const publicationArtifacts = _readPublicationSelection();

    // Strip statevectors client-side unless explicitly requested, so the request body
    // stays well under the 1MB upload limit (statevector runs can be many MB otherwise).
    let payloadResults = includeStatevectors ? results : _stripStatevectors(results);
    let finalIncludeSv = includeStatevectors;

    const tempBody = JSON.stringify({
        format: 'ro-crate',
        include_statevectors: includeStatevectors,
        author_name: authorName,
        author_affiliation: authorAffiliation,
        publication_artifacts: publicationArtifacts,
        results: payloadResults,
    });

    if (includeStatevectors && tempBody.length > 1000000) {
        alert("Statevector exceeds the 1MB upload limit. The RO-Crate will be downloaded without it, but your complete statevector will be downloaded simultaneously as a separate JSON file directly from your browser.");
        payloadResults = _stripStatevectors(results);
        finalIncludeSv = false;
        
        // Trigger local download of full json asynchronously so it doesn't block
        setTimeout(() => downloadFullReport(), 500);
    }

    const btn = document.getElementById('btn-export-rocrate');
    let originalText = '';
    if (btn) {
        originalText = btn.innerHTML;
        btn.innerHTML = `<span class="inline-block animate-spin mr-1 border-2 border-emerald-600 border-t-transparent rounded-full w-3 h-3"></span> Exporting`;
        btn.disabled = true;
    }

    try {
        const response = await fetch(`${BASE_URL}/export`, {
            method: 'POST',
            headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({
                format: 'ro-crate',
                include_statevectors: finalIncludeSv,
                author_name: authorName,
                author_affiliation: authorAffiliation,
                publication_artifacts: publicationArtifacts,
                results: payloadResults,
            })
        });

        if (!response.ok) {
            if (response.status === 413) {
                throw new Error("Results too large to export with statevectors. Uncheck 'include statevectors' and try again.");
            }
            const errData = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(errData.detail || errData.error || `HTTP ${response.status}`);
        }

        const blob = await response.blob();
        const disposition = response.headers.get('Content-Disposition') || '';
        const filenameMatch = disposition.match(/filename="?(.+?)"?$/);
        const filename = filenameMatch ? filenameMatch[1] : `rosetta-export.zip`;

        downloadBlob(blob, filename);
    } catch (err) {
        console.error("RO-Crate export failed:", err);
        alert("Export failed: " + err.message);
    } finally {
        if (btn) {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    }
}

// Global sampling seed (measured mode). Empty field => null, and the backend generates a
// seed and records it in the report, so no run is ever un-reproducible. Never sends null-as-0.
export function getSeed() {
    const el = document.getElementById('seed-input');
    if (!el) return null;
    const raw = String(el.value).trim();
    if (raw === '') return null;
    const n = parseInt(raw, 10);
    return Number.isFinite(n) && n >= 0 ? n : null;
}

// Hand the browser a file. Every download in the app goes through here; six call sites
// previously rebuilt this anchor dance, each revoking the object URL slightly differently
// or not at all.
export function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function _escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c =>
        ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

// Agreement thresholds from the config panel. Defaults match the backend; sent on every
// run so the effective values are explicit in provenance. Returns undefined if the inputs
// are absent (older cached HTML) so the backend falls back to its defaults.
export const _AGREEMENT_THRESHOLD_DEFAULTS = {
    fidelity_tolerance: 1e-12, phase_tolerance: 1e-12,
    js_threshold: 0.01, hellinger_threshold: 0.1,
};
export function getAgreementThresholds() {
    const ids = { fidelity_tolerance: 'th-fidelity', phase_tolerance: 'th-phase',
                  js_threshold: 'th-js', hellinger_threshold: 'th-hellinger' };
    const out = {};
    let anyPresent = false;
    for (const [key, id] of Object.entries(ids)) {
        const el = document.getElementById(id);
        if (!el) continue;
        anyPresent = true;
        const v = parseFloat(el.value);
        out[key] = (Number.isFinite(v) && v >= 0) ? v : _AGREEMENT_THRESHOLD_DEFAULTS[key];
    }
    return anyPresent ? out : undefined;
}
export function resetAgreementThresholds() {
    const ids = { 'th-fidelity': '1e-12', 'th-phase': '1e-12', 'th-js': '0.01', 'th-hellinger': '0.1' };
    for (const [id, val] of Object.entries(ids)) {
        const el = document.getElementById(id);
        if (el) el.value = val;
    }
}

export function exportPlaylist() {
    const queue = getState().batchQueue;
    if (queue.length === 0) {
        alert("Playlist is empty.");
        return;
    }
    downloadBlob(new Blob([JSON.stringify(queue, null, 2)], { type: 'application/json' }), "quantum_playlist.json");
}

export function importQasm(inputElement) {
    const file = inputElement.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function (e) {
        document.getElementById('qasm-input').value = e.target.result;
        let fileName = file.name;
        if (fileName.endsWith('.qasm')) {
            fileName = fileName.substring(0, fileName.length - 5);
        }
        document.getElementById('ctx-algo-name').value = fileName;
        dispatch('SET_CURRENT_ALGO_NAME', fileName);
        inputElement.value = '';
    };
    reader.readAsText(file);
}

export function exportQasm() {
    const qasmText = document.getElementById('qasm-input').value;
    if (!qasmText || qasmText.trim() === '') {
        alert("No QASM content to export.");
        return;
    }
    let fileName = document.getElementById('ctx-algo-name').value.trim() || 'circuit';
    if (!fileName.endsWith('.qasm')) {
        fileName += '.qasm';
    }
    downloadBlob(new Blob([qasmText], { type: 'text/plain' }), fileName);
}

