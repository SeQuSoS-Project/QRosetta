// Shared UI utilities: loading overlay, clipboard, downloads, report and RO-Crate export,
// agreement-threshold inputs, seed input, and QASM/playlist import/export.

import { allButtons } from './dom.js';
import { BASE_URL, getAuthHeaders } from './api.js';

import { renderBatchProgress, _stopRunnerCardTimer } from './status_cards.js';
import { dispatch, getState } from './state.js';

export let _loaderElapsedTimer = null;

/** Show or hide the busy state. options.overlay=false shows a small toast instead of the
 * full results-panel overlay, so a displayed report stays visible. */
export function setLoading(isLoading, message = "Processing...", options = {}) {
    const overlay = options.overlay !== false;
    const loader = document.getElementById('loader');
    const loaderText = document.getElementById('loader-text');
    const busyToast = document.getElementById('busy-toast');
    const busyToastText = document.getElementById('busy-toast-text');

    if (isLoading) {
        if (overlay) {
            if (loaderText) loaderText.textContent = message;
            renderBatchProgress(null);
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

/** A small copy-icon button; `getText` is a string or a () => string. */
export function makeCopyIconButton(getText, title = 'Copy to clipboard') {
    const btn = document.createElement('button');
    btn.className = 'inline-flex items-center gap-1 text-gray-600 hover:text-gray-900 bg-gray-100 hover:bg-gray-200 border border-gray-300 rounded-md px-2 py-1 transition-all';
    btn.title = title;
    btn.innerHTML = COPY_ICON_SVG;
    btn.onclick = () => copyText(typeof getText === 'function' ? getText() : getText, btn);
    return btn;
}

export function copyCircuitQasm(btn) {
    const el = document.getElementById('qasm-input');
    if (el) copyText(el.value || '', btn);
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

/** The publication-artifact selection, or null unless the checkbox is on and a category is selected. */
export function _readPublicationSelection() {
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

const JOB_REPORT_TTL_MIN = 30;
const DISPLAY_SV_MAX_QUBITS = 14;
const EXPORT_UPLOAD_LIMIT_BYTES = 1000000;

const EXPIRED_TEXT = `The server keeps a job's full report for ${JOB_REPORT_TTL_MIN} minutes after it completes, and this job's copy is no longer there (expired, or the server restarted).`;
/** What the browser-held copy of a report lacks. */
function _browserCopyText(results) {
    if (results && results.statevector_storage === 'removed_before_storage') {
        return 'This report was stored without statevectors.';
    }
    return `The copy held in this browser does not include statevectors of circuits over ${DISPLAY_SV_MAX_QUBITS} qubits.`;
}

/** Job id of the report on screen when it came from a job run in this session, else null. */
function _liveJobId() {
    return getState().currentJobId || null;
}

async function _errorDetail(response) {
    const body = await response.json().catch(() => null);
    return (body && (body.detail || body.error)) || response.statusText || `HTTP ${response.status}`;
}

function _filenameFrom(response, fallback) {
    const disposition = response.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="?(.+?)"?$/);
    return match ? match[1] : fallback;
}

/** Download the server's untruncated report for the current job (GET /jobs/{id}/report). */
export async function downloadFullReport() {
    const jobId = _liveJobId();
    if (!jobId) {
        alert(`This report was not produced by a job in this session, so the server holds no full copy of it. Use "Download displayed JSON". ${_browserCopyText(getState().currentSuiteData)}`);
        return;
    }
    try {
        const res = await fetch(`${BASE_URL}/jobs/${encodeURIComponent(jobId)}/report`, { headers: getAuthHeaders() });
        if (res.status === 404) {
            alert(`${EXPIRED_TEXT} Use "Download displayed JSON" instead. ${_browserCopyText(getState().currentSuiteData)}`);
            return;
        }
        if (res.status === 409) {
            alert(`The server has no full report for this job: ${await _errorDetail(res)}`);
            return;
        }
        if (!res.ok) throw new Error(await _errorDetail(res));
        downloadBlob(await res.blob(), _filenameFrom(res, `qrosetta_report_${jobId.slice(0, 8)}.json`));
    } catch (err) {
        console.error("Full report download failed:", err);
        alert("Download failed: " + err.message);
    }
}

/** POST /export with the report held in the browser; null if the user cancels. */
async function _exportBrowserCopy(results, options) {
    let body = JSON.stringify({
        ...options,
        results: options.include_statevectors ? results : _stripStatevectors(results),
    });
    if (options.include_statevectors && new Blob([body]).size > EXPORT_UPLOAD_LIMIT_BYTES) {
        const ok = confirm("With statevectors, this report is larger than the 1 MB upload limit for exporting data held in the browser.\n\nExport it without statevectors?");
        if (!ok) return null;
        body = JSON.stringify({ ...options, include_statevectors: false, results: _stripStatevectors(results) });
    }
    return fetch(`${BASE_URL}/export`, {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body,
    });
}

/** Export the report as an RO-Crate ZIP: from the server copy for a live job
 * (POST /jobs/{id}/export), else from the browser copy (POST /export). */
export async function exportRoCrate() {
    const results = getState().currentSuiteData;
    if (!results) {
        alert("No results to export. Run a comparison first.");
        return;
    }

    const options = {
        format: 'ro-crate',
        include_statevectors: document.getElementById('export-include-sv')?.checked || false,
        author_name: document.getElementById('export-author-name')?.value.trim() || null,
        author_affiliation: document.getElementById('export-author-affiliation')?.value.trim() || null,
        publication_artifacts: _readPublicationSelection(),
    };

    const btn = document.getElementById('btn-export-rocrate');
    let originalText = '';
    if (btn) {
        originalText = btn.innerHTML;
        btn.innerHTML = `<span class="inline-block animate-spin mr-1 border-2 border-emerald-600 border-t-transparent rounded-full w-3 h-3"></span> Exporting`;
        btn.disabled = true;
    }

    try {
        let response = null;
        const jobId = _liveJobId();
        if (jobId) {
            response = await fetch(`${BASE_URL}/jobs/${encodeURIComponent(jobId)}/export`, {
                method: 'POST',
                headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
                body: JSON.stringify(options),
            });
            if (response.status === 404 || response.status === 409) {
                const why = response.status === 404
                    ? EXPIRED_TEXT
                    : `The server has no exportable copy of this job: ${await _errorDetail(response)}`;
                if (!confirm(`${why}\n\nExport the copy held in this browser instead? ${_browserCopyText(results)}`)) return;
                response = null;
            }
        }
        if (!response) response = await _exportBrowserCopy(results, options);
        if (!response) return;

        if (!response.ok) {
            if (response.status === 413) {
                throw new Error("The report is larger than the 1 MB upload limit. Uncheck 'Include raw statevectors' and try again.");
            }
            throw new Error(await _errorDetail(response));
        }
        downloadBlob(await response.blob(), _filenameFrom(response, 'rosetta-export.zip'));
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

/** The sampling seed field; empty gives null, and the API then generates and records a seed.
 * A value that is not a non-negative integer is rejected by validateRunInputs() before a run. */
export function getSeed() {
    const el = document.getElementById('seed-input');
    if (!el) return null;
    const raw = String(el.value).trim();
    if (raw === '') return null;
    const n = Number(raw);
    return Number.isInteger(n) && n >= 0 ? n : null;
}

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

/** Defaults of AgreementThresholds in schemas/benchmark.py (checked by
 * tests/unit/test_threshold_defaults_sync.py). */
export const AGREEMENT_THRESHOLD_DEFAULTS = {
    fidelity_tolerance: 1e-5, phase_tolerance: 1e-12,
    js_threshold: 0.01, hellinger_threshold: 0.1, norm_tolerance: 1e-4,
};

export const THRESHOLD_INPUT_IDS = {
    fidelity_tolerance: 'th-fidelity', phase_tolerance: 'th-phase',
    js_threshold: 'th-js', hellinger_threshold: 'th-hellinger', norm_tolerance: 'th-norm',
};

/** Threshold defaults: the server's (GET /config agreement_threshold_defaults) over the built-in ones. */
export function thresholdDefaults() {
    const server = getState().thresholdDefaults || {};
    const out = { ...AGREEMENT_THRESHOLD_DEFAULTS };
    Object.keys(out).forEach(k => { if (typeof server[k] === 'number') out[k] = server[k]; });
    return out;
}

/** Threshold values from the config panel, sent with every run; undefined if the inputs are absent.
 * Fields that do not parse are left out; validateRunInputs() blocks the run before that. */
export function getAgreementThresholds() {
    const out = {};
    let anyPresent = false;
    for (const [key, id] of Object.entries(THRESHOLD_INPUT_IDS)) {
        const el = /** @type {HTMLInputElement|null} */ (document.getElementById(id));
        if (!el) continue;
        anyPresent = true;
        const raw = String(el.value).trim();
        const v = Number(raw);
        if (raw !== '' && Number.isFinite(v) && v >= 0) out[key] = v;
    }
    return anyPresent ? out : undefined;
}

export function resetAgreementThresholds() {
    const defaults = thresholdDefaults();
    for (const [key, id] of Object.entries(THRESHOLD_INPUT_IDS)) {
        const el = /** @type {HTMLInputElement|null} */ (document.getElementById(id));
        if (el) el.value = String(defaults[key]);
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

