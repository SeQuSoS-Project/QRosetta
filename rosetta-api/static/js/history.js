// Run history: save completed runs, list, load, rename, download and delete them.

import { tabNav } from './dom.js';
import { BASE_URL, formatApiError, getAuthHeaders } from './api.js';
import { onNextLogin, openAuthModal, updateAuthUI } from './auth.js';
import { clearReport, renderDetailReport, renderSuiteSummary } from './renderers.js';
import { dispatch, getState } from './state.js';
import { downloadBlob, setLoading } from './utils.js';

/** Parse a server timestamp; one without a zone designator is UTC. */
export function parseServerTime(value) {
    if (!value) return null;
    const text = String(value);
    const zoned = /(Z|[+-]\d{2}:?\d{2})$/i.test(text) ? text : `${text}Z`;
    const d = new Date(zoned);
    return Number.isNaN(d.getTime()) ? null : d;
}

function _formatServerTime(value) {
    const d = parseServerTime(value);
    return d ? d.toLocaleString() : '';
}

/**
 * Show (or with an empty message, hide) the history-save notice, optionally with one
 * action button.
 * @param {string} message
 * @param {'error'|'success'} [kind]
 * @param {{ label: string, onClick: () => void } | null} [action]
 */
export function showHistoryNotice(message, kind = 'error', action = null) {
    const box = document.getElementById('history-save-notice');
    const text = document.getElementById('history-save-notice-text');
    const button = document.getElementById('history-save-notice-action');
    if (!box || !text) return;
    if (button) {
        button.classList.toggle('hidden', !action);
        button.textContent = action ? action.label : '';
        button.onclick = action ? () => { showHistoryNotice(''); action.onClick(); } : null;
    }
    if (!message) {
        box.classList.add('hidden');
        box.classList.remove('flex');
        return;
    }
    text.textContent = message;
    box.classList.toggle('bg-red-50', kind === 'error');
    box.classList.toggle('border-red-300', kind === 'error');
    box.classList.toggle('text-red-800', kind === 'error');
    box.classList.toggle('bg-green-50', kind !== 'error');
    box.classList.toggle('border-green-300', kind !== 'error');
    box.classList.toggle('text-green-800', kind !== 'error');
    box.classList.remove('hidden');
    box.classList.add('flex');
}

/** Sign-in prompt for a save rejected with 401; after sign-in the save is retried. */
function _offerSignInAndRetry(jobId, name) {
    dispatch('SET_AUTH_TOKEN', null);
    updateAuthUI();
    const retry = async () => {
        const id = await saveRunToHistory(jobId, name);
        if (id) {
            if (getState().currentJobId === jobId) dispatch('SET_HISTORY_RUN_ID', id);
            showHistoryNotice('Saved to your history.', 'success');
        }
    };
    showHistoryNotice('Your session has expired, so this run was not saved to your history. '
        + 'Sign in again to save it; the server keeps the result for at least 30 minutes after the run finishes.', 'error', {
        label: 'Sign in and save',
        onClick: () => {
            onNextLogin(retry);
            openAuthModal();
        },
    });
}

/** Save a finished job to the signed-in user's history from the server's copy of the report.
 * Returns the saved run id, or null (with a visible notice) when saving failed. */
export async function saveRunToHistory(jobId, name = null) {
    if (!getState().authToken || !jobId) return null;
    try {
        const res = await fetch(`${BASE_URL}/history/runs/from_job/${encodeURIComponent(jobId)}`, {
            method: 'POST',
            headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(name ? { run_name: name } : {})
        });
        if (res.status === 401) {
            _offerSignInAndRetry(jobId, name);
            return null;
        }
        if (!res.ok) throw new Error(await formatApiError(res));
        const data = await res.json().catch(() => null);
        const id = typeof data === 'string' ? data : (data?.id || data?.run_id || null);
        showHistoryNotice('');
        return id;
    } catch (e) {
        console.error("Failed to save run to history:", e);
        showHistoryNotice(`This run was not saved to your history. ${e.message || ''}`.trim());
        return null;
    }
}

export async function openHistoryModal() {
    document.getElementById('history-modal').classList.remove('hidden');
    const list = document.getElementById('history-list');
    list.innerHTML = '<li class="py-4 text-center text-sm text-gray-500">Loading history...</li>';

    if (!getState().authToken) {
        list.innerHTML = '<li class="py-4 text-center text-sm text-gray-500">Please login to view history.</li>';
        return;
    }

    try {
        const response = await fetch(`${BASE_URL}/history/runs`, {
            headers: getAuthHeaders()
        });
        if (response.status === 401) {
            dispatch('SET_AUTH_TOKEN', null);
            updateAuthUI();
            list.innerHTML = '<li class="py-4 text-center text-sm text-gray-500">Your session has expired. Sign in again to view your history.</li>';
            return;
        }
        if (!response.ok) throw new Error("Failed to fetch history");

        const runs = await response.json();
        if (runs.length === 0) {
            list.innerHTML = '<li class="py-4 text-center text-sm text-gray-500">No previous runs found.</li>';
            return;
        }

        runs.sort((a, b) => (parseServerTime(b.created_at)?.getTime() ?? 0) - (parseServerTime(a.created_at)?.getTime() ?? 0));

        list.innerHTML = '';
        runs.forEach(run => {
            const runName = run.run_name || run.id.substring(0, 8);
            const dateStr = _formatServerTime(run.created_at);

            const li = document.createElement('li');
            li.className = "py-4 flex items-center justify-between";

            const leftDiv = document.createElement('div');
            leftDiv.className = "flex items-center flex-1 min-w-0 pr-4";

            const checkbox = document.createElement('input');
            checkbox.type = "checkbox";
            checkbox.className = "history-checkbox mr-4 h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded";
            checkbox.value = run.id;

            const colDiv = document.createElement('div');
            colDiv.className = "flex flex-col flex-1 min-w-0";

            const rowDiv = document.createElement('div');
            rowDiv.className = "flex items-center";

            const nameSpan = document.createElement('span');
            nameSpan.id = `run-name-text-${run.id}`;
            nameSpan.className = "text-sm font-medium text-indigo-600 truncate mr-2";
            nameSpan.textContent = runName;

            const idSpan = document.createElement('span');
            idSpan.className = "text-xs text-gray-400 font-mono bg-gray-100 px-1 rounded border border-gray-200";
            idSpan.textContent = run.id.substring(0, 8);

            const nameInput = document.createElement('input');
            nameInput.type = "text";
            nameInput.id = `run-name-input-${run.id}`;
            nameInput.className = "hidden text-sm border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500 w-full max-w-xs px-2 py-1";
            nameInput.value = runName;

            const editBtn = document.createElement('button');
            editBtn.id = `run-name-edit-btn-${run.id}`;
            editBtn.className = "ml-2 text-xs text-gray-400 hover:text-gray-600";
            editBtn.textContent = "✏️";
            editBtn.addEventListener('click', () => toggleEditRunName(run.id));

            const saveBtn = document.createElement('button');
            saveBtn.id = `run-name-save-btn-${run.id}`;
            saveBtn.className = "hidden ml-2 text-xs font-medium text-green-600 hover:text-green-800";
            saveBtn.textContent = "Save";
            saveBtn.addEventListener('click', () => saveRunName(run.id));

            const cancelBtn = document.createElement('button');
            cancelBtn.id = `run-name-cancel-btn-${run.id}`;
            cancelBtn.className = "hidden ml-2 text-xs font-medium text-red-600 hover:text-red-800";
            cancelBtn.textContent = "Cancel";
            cancelBtn.addEventListener('click', () => cancelEditRunName(run.id, nameSpan.textContent));

            const dateSpan = document.createElement('span');
            dateSpan.className = "text-xs text-gray-500";
            dateSpan.textContent = dateStr;

            rowDiv.append(nameSpan, idSpan, nameInput, editBtn, saveBtn, cancelBtn);
            colDiv.append(rowDiv, dateSpan);
            leftDiv.append(checkbox, colDiv);

            const viewBtn = document.createElement('button');
            viewBtn.className = "text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-700 px-3 py-1.5 rounded-md shadow-sm transition-colors whitespace-nowrap";
            viewBtn.textContent = "View Results";
            viewBtn.addEventListener('click', () => loadHistoricalRun(run.id, runName, run.created_at));

            li.append(leftDiv, viewBtn);
            list.appendChild(li);
        });
    } catch (e) {
        const li = document.createElement('li');
        li.className = "py-4 text-center text-sm text-red-500";
        li.textContent = `Error: ${e.message}`;
        list.innerHTML = '';
        list.appendChild(li);
    }
}

export function clearHistoryState() {
    const banner = document.getElementById('history-active-banner');
    if (banner) {
        banner.remove();
    }
    dispatch('SET_HISTORY_RUN_ID', null);
}

export function toggleSelectAllHistory() {
    const selectAll = document.getElementById('history-select-all');
    const checkboxes = document.querySelectorAll('.history-checkbox');
    checkboxes.forEach(cb => cb.checked = selectAll.checked);
}

export function toggleEditRunName(runId) {
    document.getElementById(`run-name-text-${runId}`).classList.add('hidden');
    document.getElementById(`run-name-edit-btn-${runId}`).classList.add('hidden');
    document.getElementById(`run-name-input-${runId}`).classList.remove('hidden');
    document.getElementById(`run-name-save-btn-${runId}`).classList.remove('hidden');
    document.getElementById(`run-name-cancel-btn-${runId}`).classList.remove('hidden');
    document.getElementById(`run-name-input-${runId}`).focus();
}

export function cancelEditRunName(runId, originalName) {
    document.getElementById(`run-name-input-${runId}`).value = originalName;
    document.getElementById(`run-name-text-${runId}`).classList.remove('hidden');
    document.getElementById(`run-name-edit-btn-${runId}`).classList.remove('hidden');
    document.getElementById(`run-name-input-${runId}`).classList.add('hidden');
    document.getElementById(`run-name-save-btn-${runId}`).classList.add('hidden');
    document.getElementById(`run-name-cancel-btn-${runId}`).classList.add('hidden');
}

export async function saveRunName(runId) {
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
        cancelEditRunName(runId, newName);
    } catch (e) {
        console.error(e);
        alert("Failed to save run name.");
    }
}

export async function deleteSelectedHistory() {
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
        openHistoryModal();
    } catch (e) {
        console.error(e);
        alert("Failed to delete runs.");
    }
}

export async function downloadSelectedHistory() {
    const checkboxes = document.querySelectorAll('.history-checkbox:checked');
    const runIds = Array.from(checkboxes).map(cb => cb.value);
    if (runIds.length === 0) return;

    setLoading(true, "Downloading histories...");
    try {
        const fetches = runIds.map(id => fetch(`${BASE_URL}/history/runs/${id}`, { headers: getAuthHeaders() }).then(res => res.json()));
        const results = await Promise.all(fetches);

        downloadBlob(new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' }),
            `qrosetta_runs_batch_${Date.now()}.json`);
    } catch (e) {
        console.error(e);
        alert("Failed to download runs.");
    } finally {
        setLoading(false);
    }
}

export function closeHistoryModal() {
    document.getElementById('history-modal').classList.add('hidden');
}

export async function loadHistoricalRun(runId, runName, createdAt) {
    if (!getState().authToken) return;
    closeHistoryModal();
    setLoading(true, "Loading Past Run...");
    clearReport();

    try {
        const response = await fetch(`${BASE_URL}/history/runs/${runId}`, {
            headers: getAuthHeaders()
        });
        if (!response.ok) throw new Error("Failed to load historical run details.");

        const data = await response.json();
        dispatch('SET_JOB_ID', null);
        dispatch('SET_SUITE_DATA', data);
        dispatch('SET_HISTORY_RUN_ID', runId);

        const historyBanner = document.createElement('div');
        historyBanner.id = "history-active-banner";
        historyBanner.className = "p-3 bg-yellow-50 border-b border-yellow-200 text-yellow-800 text-sm flex justify-between items-center";

        const displayDate = _formatServerTime(createdAt || data.created_at) || new Date().toLocaleString();
        const title = document.createElement('div');
        const strong = document.createElement('strong');
        strong.textContent = 'Viewing Past Run:';
        title.append(strong, ' ');
        if (runName) {
            const idTag = document.createElement('span');
            idTag.className = 'text-xs font-mono ml-2 opacity-75';
            idTag.textContent = `(${String(runId).substring(0, 8)})`;
            const when = document.createElement('span');
            when.className = 'ml-2';
            when.textContent = `- ${displayDate}`;
            title.append(runName, idTag, when);
        } else {
            title.append(displayDate);
        }
        const closeBtn = document.createElement('button');
        closeBtn.type = 'button';
        closeBtn.className = 'text-yellow-600 hover:text-yellow-900 font-bold underline';
        closeBtn.textContent = 'Close Results & Return to Editor';
        closeBtn.addEventListener('click', clearHistoryView);
        historyBanner.append(title, closeBtn);

        const tabNav = document.getElementById('tab-nav');
        document.getElementById('history-active-banner')?.remove();
        tabNav.parentNode.insertBefore(historyBanner, tabNav);

        const isBatch = !!data.benchmark_summary;
        if (isBatch) {
            dispatch('SET_SUITE_TITLE', runName || "Historical Batch Run");
            renderSuiteSummary(data, getState().currentSuiteTitle);
        } else {
            renderDetailReport(data, runName || "Historical Single Run", {});
        }
    } catch (e) {
        console.error("Historical load fail:", e);
        renderDetailReport({ error: e.message }, "Error Loading History");
    } finally {
        setLoading(false);
    }
}

export function clearHistoryView() {
    clearReport();
    const banner = document.getElementById('history-active-banner');
    if (banner) banner.remove();
}