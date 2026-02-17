// --- HELPER FUNCTIONS ---
function isConnectionError(errorMsg) {
    if (!errorMsg) return false;
    const msg = errorMsg.toLowerCase();
    return msg.includes("connection refused") ||
        msg.includes("name or service not known") ||
        msg.includes("failed to connect") ||
        msg.includes("failed to get response") ||
        msg.includes("502 bad gateway") ||
        msg.includes("503 service unavailable") ||
        msg.includes("failed to decode json");
}

function setLoading(isLoading, message = "Processing...") {
    const loader = document.getElementById('loader');
    const loaderText = document.getElementById('loader-text');

    if (isLoading) {
        if (loaderText) loaderText.textContent = message;
        loader.classList.remove('hidden');
        loader.classList.add('flex');
        allButtons.forEach(btn => { if (btn) btn.disabled = true });
    } else {
        loader.classList.add('hidden');
        loader.classList.remove('flex');
        allButtons.forEach(btn => { if (btn) btn.disabled = false });
    }
}

function copyRawJson(btn) {
    const txt = jsonOutput.textContent;
    navigator.clipboard.writeText(txt).then(() => {
        const old = btn.textContent;
        btn.textContent = "Copied!";
        setTimeout(() => btn.textContent = old, 2000);
    }).catch(err => console.error(err));
}

function downloadFullReport() {
    // --- FIX: Use BASE_URL for fetch ---
    window.location.href = `${BASE_URL}/download_latest_report`;
}

function downloadRawJson() {
    const jsonString = jsonOutput.textContent;
    if (!jsonString || jsonString.trim() === '') {
        alert("No JSON content to download.");
        return;
    }
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(jsonString);
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute("href", dataStr);
    downloadAnchorNode.setAttribute("download", "rosetta_raw_report.json");
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
}

function exportPlaylist() {
    if (batchQueue.length === 0) {
        alert("Playlist is empty.");
        return;
    }
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(batchQueue, null, 2));
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute("href", dataStr);
    downloadAnchorNode.setAttribute("download", "quantum_playlist.json");
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
}

function importPlaylist(inputElement) {
    const file = inputElement.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function (e) {
        try {
            const loaded = JSON.parse(e.target.result);
            if (Array.isArray(loaded)) {
                batchQueue = loaded;
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
