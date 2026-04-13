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

let _loaderElapsedTimer = null;

function setLoading(isLoading, message = "Processing...") {
    const loader = document.getElementById('loader');
    const loaderText = document.getElementById('loader-text');

    if (isLoading) {
        if (loaderText) loaderText.textContent = message;
        loader.classList.remove('hidden');
        loader.classList.add('flex');
        allButtons.forEach(btn => { if (btn) btn.disabled = true });
        if (!_loaderElapsedTimer) {
            const startTime = Date.now();
            const elapsedEl = document.getElementById('loader-elapsed');
            if (elapsedEl) elapsedEl.textContent = '0s elapsed';
            _loaderElapsedTimer = setInterval(() => {
                const el = document.getElementById('loader-elapsed');
                if (el) el.textContent = `${Math.floor((Date.now() - startTime) / 1000)}s elapsed`;
            }, 1000);
        }
    } else {
        loader.classList.add('hidden');
        loader.classList.remove('flex');
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

const _STATUS_CFG = {
    queued:   { color: 'bg-gray-300',    text: 'text-gray-400',   label: 'QUEUED',    pulse: false, terminal: false },
    spawning: { color: 'bg-amber-400',   text: 'text-amber-600',  label: 'SPAWNING',  pulse: true,  terminal: false },
    running:  { color: 'bg-blue-500',    text: 'text-blue-600',   label: 'RUNNING',   pulse: true,  terminal: false },
    done:     { color: 'bg-green-500',   text: 'text-green-700',  label: 'DONE',      pulse: false, terminal: true  },
    error:    { color: 'bg-red-500',     text: 'text-red-600',    label: 'ERROR',     pulse: false, terminal: true  },
    timeout:  { color: 'bg-orange-400',  text: 'text-orange-500', label: 'TIMEOUT',   pulse: false, terminal: true  },
};

const _RUNNER_NAMES = {
    "qiskit": "Qiskit", "cirq": "Cirq", "qulacs": "Qulacs", "braket": "Braket",
    "projectq": "ProjectQ", "quest": "QuEST", "pennylane-lightning": "PL Lightning",
    "pennylane-default": "PL Default", "qsim-cirq": "qsim-Cirq", "qibo": "Qibo",
    "qrisp": "Qrisp", "myqlm": "myQLM", "pyquil": "PyQuil",
    "torchquantum": "TorchQuantum", "quimb": "Quimb", "cuquantum": "cuQuantum",
};

// Per-runner phase tracking: { simId: { status, since, frozenElapsed } }
let _runnerPhases = {};
let _runnerCardTimer = null;

function _startRunnerCardTimer() {
    if (_runnerCardTimer) return;
    _runnerCardTimer = setInterval(() => {
        const now = Date.now();
        for (const [simId, phase] of Object.entries(_runnerPhases)) {
            if (phase.terminal) continue;
            const elapsed = Math.floor((now - phase.since) / 1000);
            const el = document.getElementById(`rsc-elapsed-${simId}`);
            if (el) el.textContent = `${elapsed}s`;
        }
    }, 1000);
}

function _stopRunnerCardTimer() {
    if (_runnerCardTimer) { clearInterval(_runnerCardTimer); _runnerCardTimer = null; }
    _runnerPhases = {};
}

function updateRunnerStatuses(statuses) {
    if (!statuses || typeof statuses !== 'object') return;
    const grid = document.getElementById('runner-status-grid');
    if (!grid) return;

    const now = Date.now();

    for (const [simId, status] of Object.entries(statuses)) {
        const cfg = _STATUS_CFG[status] || _STATUS_CFG['queued'];
        const name = _RUNNER_NAMES[simId] || simId;

        // Track phase transitions to reset per-runner timer
        const prev = _runnerPhases[simId];
        if (!prev || prev.status !== status) {
            const frozenElapsed = prev && prev.terminal ? prev.frozenElapsed
                : prev ? Math.floor((now - prev.since) / 1000) : 0;
            _runnerPhases[simId] = {
                status,
                since: now,
                terminal: cfg.terminal,
                frozenElapsed: cfg.terminal ? frozenElapsed : 0,
            };
        }

        let card = document.getElementById(`rsc-${simId}`);
        if (!card) {
            card = document.createElement('div');
            card.id = `rsc-${simId}`;
            card.className = 'flex items-center gap-2 p-2 rounded border border-gray-100 bg-gray-50 font-mono text-xs';
            grid.appendChild(card);
        }

        const phase = _runnerPhases[simId];
        const elapsedDisplay = cfg.terminal
            ? `${phase.frozenElapsed}s`
            : `<span id="rsc-elapsed-${simId}">0s</span>`;

        card.innerHTML = `
            <span class="w-2 h-2 rounded-full flex-shrink-0 ${cfg.color}${cfg.pulse ? ' animate-pulse' : ''}"></span>
            <span class="flex-1 text-gray-700 truncate">${name}</span>
            <span class="font-semibold tracking-widest text-[10px] ${cfg.text} mr-1">${cfg.label}</span>
            <span class="text-gray-400 text-[10px] w-7 text-right">${elapsedDisplay}</span>
        `;
    }

    _startRunnerCardTimer();
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
            headers: typeof getAuthHeaders === 'function' ? getAuthHeaders({ 'Content-Type': 'application/json' }) : { 'Content-Type': 'application/json' },
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
