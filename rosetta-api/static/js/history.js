// Frontend logic for history functionality.

async function saveRunToHistory(payload) {
    if (!getState().authToken) return null;
    try {
        const res = await fetch(`${BASE_URL}/history/runs`, {
            method: 'POST',
            headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify(payload)
        });
        if (!res.ok) return null;
        const data = await res.json();
        return data.id || null;
    } catch (e) {
        console.error("Failed to save run to history:", e);
        return null;
    }
}

async function openHistoryModal() {
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
        if (!response.ok) throw new Error("Failed to fetch history");

        const runs = await response.json();
        if (runs.length === 0) {
            list.innerHTML = '<li class="py-4 text-center text-sm text-gray-500">No previous runs found.</li>';
            return;
        }

        runs.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

        list.innerHTML = '';
        runs.forEach(run => {
            const runName = run.run_name || run.id.substring(0, 8);
            const dateStr = new Date(run.created_at).toLocaleString();

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
            cancelBtn.addEventListener('click', () => cancelEditRunName(run.id, nameInput.value));

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

function clearHistoryState() {
    const banner = document.getElementById('history-active-banner');
    if (banner) {
        banner.remove();
    }
    dispatch('SET_HISTORY_RUN_ID', null);
}

function toggleSelectAllHistory() {
    const selectAll = document.getElementById('history-select-all');
    const checkboxes = document.querySelectorAll('.history-checkbox');
    checkboxes.forEach(cb => cb.checked = selectAll.checked);
}

function toggleEditRunName(runId) {
    document.getElementById(`run-name-text-${runId}`).classList.add('hidden');
    document.getElementById(`run-name-edit-btn-${runId}`).classList.add('hidden');
    document.getElementById(`run-name-input-${runId}`).classList.remove('hidden');
    document.getElementById(`run-name-save-btn-${runId}`).classList.remove('hidden');
    document.getElementById(`run-name-cancel-btn-${runId}`).classList.remove('hidden');
    document.getElementById(`run-name-input-${runId}`).focus();
}

function cancelEditRunName(runId, originalName) {
    document.getElementById(`run-name-input-${runId}`).value = originalName;
    document.getElementById(`run-name-text-${runId}`).classList.remove('hidden');
    document.getElementById(`run-name-edit-btn-${runId}`).classList.remove('hidden');
    document.getElementById(`run-name-input-${runId}`).classList.add('hidden');
    document.getElementById(`run-name-save-btn-${runId}`).classList.add('hidden');
    document.getElementById(`run-name-cancel-btn-${runId}`).classList.add('hidden');
}

async function saveRunName(runId) {
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
        document.getElementById(`run-name-cancel-btn-${runId}`).setAttribute('onclick', `cancelEditRunName('${runId}', '${newName}')`);
        cancelEditRunName(runId, newName);
    } catch (e) {
        console.error(e);
        alert("Failed to save run name.");
    }
}

async function deleteSelectedHistory() {
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

async function downloadSelectedHistory() {
    const checkboxes = document.querySelectorAll('.history-checkbox:checked');
    const runIds = Array.from(checkboxes).map(cb => cb.value);
    if (runIds.length === 0) return;

    setLoading(true, "Downloading histories...");
    try {
        const fetches = runIds.map(id => fetch(`${BASE_URL}/history/runs/${id}`, { headers: getAuthHeaders() }).then(res => res.json()));
        const results = await Promise.all(fetches);

        const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `qrosetta_runs_batch_${Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (e) {
        console.error(e);
        alert("Failed to download runs.");
    } finally {
        setLoading(false);
    }
}

function closeHistoryModal() {
    document.getElementById('history-modal').classList.add('hidden');
}

async function loadHistoricalRun(runId, runName, createdAt) {
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
        dispatch('SET_SUITE_DATA', data);
        dispatch('SET_HISTORY_RUN_ID', runId);

        const historyBanner = document.createElement('div');
        historyBanner.id = "history-active-banner";
        historyBanner.className = "p-3 bg-yellow-50 border-b border-yellow-200 text-yellow-800 text-sm flex justify-between items-center";

        const displayDate = createdAt ? new Date(createdAt).toLocaleString() : new Date(data.created_at || Date.now()).toLocaleString();
        const displayTitle = runName ? `<strong>Viewing Past Run:</strong> ${runName} <span class="text-xs font-mono ml-2 opacity-75">(${runId.substring(0, 8)})</span> <span class="ml-2">- ${displayDate}</span>` : `<strong>Viewing Past Run:</strong> ${displayDate}`;

        historyBanner.innerHTML = `
            <div>${displayTitle}</div>
            <button onclick="clearHistoryView()" class="text-yellow-600 hover:text-yellow-900 font-bold underline">Close Results & Return to Editor</button>
        `;

        const tabNav = document.getElementById('tab-nav');
        if (!document.getElementById('history-active-banner')) {
            tabNav.parentNode.insertBefore(historyBanner, tabNav);
        }

        const isBatch = !!data.benchmark_summary;
        if (isBatch) {
            dispatch('SET_SUITE_TITLE', "Historical Batch Run");
            renderSuiteSummary(data, getState().currentSuiteTitle);
        } else {
            renderDetailReport(data, "Historical Single Run", {});
        }
    } catch (e) {
        console.error("Historical load fail:", e);
        renderDetailReport({ error: e.message }, "Error Loading History");
    } finally {
        setLoading(false);
    }
}

function clearHistoryView() {
    clearReport();
    const banner = document.getElementById('history-active-banner');
    if (banner) banner.remove();
}