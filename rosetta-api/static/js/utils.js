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
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute("href", url);
    downloadAnchorNode.setAttribute("download", "rosetta_raw_report.json");
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
    URL.revokeObjectURL(url);
}

function exportPlaylist() {
    if (batchQueue.length === 0) {
        alert("Playlist is empty.");
        return;
    }
    const blob = new Blob([JSON.stringify(batchQueue, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute("href", url);
    downloadAnchorNode.setAttribute("download", "quantum_playlist.json");
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
    URL.revokeObjectURL(url);
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

function importQasm(inputElement) {
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
        currentAlgoName = fileName;
        inputElement.value = '';
    };
    reader.readAsText(file);
}

function exportQasm() {
    const qasmText = document.getElementById('qasm-input').value;
    if (!qasmText || qasmText.trim() === '') {
        alert("No QASM content to export.");
        return;
    }
    let fileName = document.getElementById('ctx-algo-name').value.trim() || 'circuit';
    if (!fileName.endsWith('.qasm')) {
        fileName += '.qasm';
    }
    const blob = new Blob([qasmText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const downloadAnchorNode = document.createElement('a');
    downloadAnchorNode.setAttribute("href", url);
    downloadAnchorNode.setAttribute("download", fileName);
    document.body.appendChild(downloadAnchorNode);
    downloadAnchorNode.click();
    downloadAnchorNode.remove();
    URL.revokeObjectURL(url);
}

function showVisualizerTab() {
    const welcome = document.getElementById('welcome-message');
    if (welcome) welcome.classList.add('hidden');
    Object.values(panelElements).forEach(panel => {
        if (panel) panel.classList.add('hidden');
    });
    if (panelElements['visualizer']) panelElements['visualizer'].classList.remove('hidden');

    const tabNav = document.getElementById('tab-nav');
    if (tabNav) {
        tabNav.querySelectorAll('button').forEach(btn => {
            btn.classList.remove('border-blue-600', 'text-blue-600');
            btn.classList.add('border-transparent', 'text-gray-500', 'hover:text-gray-700');
        });
    }
}

async function generateAndVisualize() {
    const qasmText = document.getElementById('qasm-input').value;
    if (!qasmText || qasmText.trim() === '') {
        alert("No QASM code to visualize.");
        return;
    }

    const btn = document.getElementById('btn-visualize');
    let originalText = "📊 Visualize";
    if (btn) {
        originalText = btn.innerHTML;
        btn.innerHTML = `<span class="inline-block animate-spin mr-1 border-2 border-purple-600 border-t-transparent rounded-full w-3 h-3"></span> Loading`;
        btn.disabled = true;
    }

    try {
        const response = await fetch(`${BASE_URL}/visualize/quirk`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ qasm_string: qasmText })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to generate visualizer URL');
        }

        document.getElementById('quirk-iframe').src = data.url;
        showVisualizerTab();
    } catch (err) {
        console.error("Visualizer API Error:", err);
        alert("Could not auto-generate Quirk visualizer for this specific circuit.\nDetails: " + err.message);
    } finally {
        if (btn) {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    }
}

function closeVisualizer() {
    if (panelElements['visualizer']) panelElements['visualizer'].classList.add('hidden');
    if (currentSuiteData) {
        showTab(currentSuiteData.benchmark_summary ? 'suite-summary' : 'summary');
    } else {
        const welcome = document.getElementById('welcome-message');
        if (welcome) welcome.classList.remove('hidden');
        const tabNav = document.getElementById('tab-nav');
        if (tabNav) {
            tabNav.querySelectorAll('button').forEach(btn => {
                btn.classList.remove('border-blue-600', 'text-blue-600');
                btn.classList.add('border-transparent', 'text-gray-500', 'hover:text-gray-700');
            });
        }
    }
}
