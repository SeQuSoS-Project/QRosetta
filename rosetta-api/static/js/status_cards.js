// Live job-polling UI: the batch-progress list and the per-runner status card grid, both
// updated by api.js on every poll tick. A leaf module (no imports from utils.js/renderers.js)
// so api.js can depend on it without reintroducing api.js <-> utils.js.

import { formatRunnerLabel } from './runner_key.js';

// Mirrors utils.js _escapeHtml. Kept as its own tiny copy rather than an import so this
// module stays a leaf; see artifact_formats.js for the same tradeoff made elsewhere.
function _escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c =>
        ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

export const _BATCH_STATUS_ICON = {
    done: ['✓', 'text-emerald-600'],
    running: ['▶', 'text-indigo-600 animate-pulse'],
    error: ['✕', 'text-red-600'],
    queued: ['◦', 'text-gray-400'],
};
export function _batchRowMarkup(t, i) {
    const [icon, cls] = _BATCH_STATUS_ICON[t.status] || _BATCH_STATUS_ICON.queued;
    return `<div id="bp-row-${i}" data-status="${t.status || 'queued'}" class="flex items-center gap-2 text-xs">
            <span class="font-mono ${cls} w-3 text-center">${icon}</span>
            <span class="truncate text-gray-600">${_escapeHtml(t.name || '')}</span>
        </div>`;
}
export function renderBatchProgress(progress) {
    const host = document.getElementById('batch-progress');
    if (!host) return;
    if (!progress || !Array.isArray(progress.tasks) || !progress.tasks.length) {
        host.classList.add('hidden');
        host.innerHTML = '';
        return;
    }
    host.classList.remove('hidden');
    const tasks = progress.tasks;
    const counterText = `${progress.completed || 0}/${progress.total || tasks.length}`;

    // The poller calls this every few seconds; after the first build, update only the rows
    // whose status changed (and the counter) so the list doesn't thrash the DOM or jump scroll.
    let list = document.getElementById('batch-progress-list');
    if (list && list.children.length === tasks.length) {
        const counter = document.getElementById('batch-progress-counter');
        if (counter) counter.textContent = counterText;
        tasks.forEach((t, i) => {
            const row = list.children[i];
            if (row && row.dataset.status !== (t.status || 'queued')) {
                row.outerHTML = _batchRowMarkup(t, i);
            }
        });
        return;
    }

    // First build (or the task set changed): render the whole list once.
    const prevScroll = list?.scrollTop || 0;
    const rows = tasks.map((t, i) => _batchRowMarkup(t, i)).join('');
    host.innerHTML = `
        <div class="flex justify-between items-center text-[11px] font-mono text-indigo-400 mb-1">
            <span class="uppercase tracking-widest">circuits</span>
            <span id="batch-progress-counter">${counterText}</span>
        </div>
        <div id="batch-progress-list" class="max-h-48 overflow-y-auto space-y-0.5 pr-1 border-l-2 border-indigo-100 pl-2">${rows}</div>`;
    list = document.getElementById('batch-progress-list');
    if (list) list.scrollTop = prevScroll;
}

export const _STATUS_CFG = {
    queued:   { color: 'bg-gray-300',    text: 'text-gray-400',   label: 'QUEUED',    pulse: false, terminal: false },
    spawning: { color: 'bg-amber-400',   text: 'text-amber-600',  label: 'SPAWNING',  pulse: true,  terminal: false },
    running:  { color: 'bg-blue-500',    text: 'text-blue-600',   label: 'SENT',      pulse: true,  terminal: false,
                hint: 'Sent to the backend. Each backend runs one request at a time, so this includes any wait behind another job; the wait is recorded as queue_wait_sec.' },
    done:     { color: 'bg-green-500',   text: 'text-green-700',  label: 'DONE',      pulse: false, terminal: true  },
    error:    { color: 'bg-orange-500',  text: 'text-orange-700', label: 'ERROR',     pulse: false, terminal: true  },
    timeout:  { color: 'bg-purple-500',  text: 'text-purple-700', label: 'TIMEOUT',   pulse: false, terminal: true  },
    offline:  { color: 'bg-gray-400',    text: 'text-gray-500',   label: 'OFFLINE',   pulse: false, terminal: true,
                hint: 'The backend could not be reached.' },
};

export const _RUNNER_NAMES = {
    "qiskit": "Qiskit", "cirq": "Cirq", "qulacs": "Qulacs", "braket": "Braket",
    "projectq": "ProjectQ", "quest": "QuEST", "pennylane-lightning": "PL Lightning",
    "pennylane-default": "PL Default", "qsim-cirq": "qsim-Cirq", "qibo": "Qibo",
    "qrisp": "Qrisp", "myqlm": "myQLM", "pyquil": "PyQuil",
    "torchquantum": "TorchQuantum", "quimb": "Quimb", "cuquantum": "cuQuantum",
    "bqskit": "BQSKit (compile)", "pyzx": "PyZX (compile)", "qmap": "QMAP (compile)",
    "cirq-transformers": "Cirq (compile)", "staq": "staq (compile)", "qsynth": "Q-Synth (compile)",
    "quartz": "Quartz (compile)",
    "synthetiq": "Synthetiq (compile)",
};

export let _runnerPhases = {};
export let _runnerCardTimer = null;

export function _startRunnerCardTimer() {
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

export function _stopRunnerCardTimer() {
    if (_runnerCardTimer) { clearInterval(_runnerCardTimer); _runnerCardTimer = null; }
    _runnerPhases = {};
}

export function updateRunnerStatuses(statuses) {
    if (!statuses || typeof statuses !== 'object') return;
    const grid = document.getElementById('runner-status-grid');
    if (!grid) return;

    const now = Date.now();

    for (const [simId, status] of Object.entries(statuses)) {
        const cfg = _STATUS_CFG[status] || _STATUS_CFG['queued'];
        const name = formatRunnerLabel(simId, _RUNNER_NAMES);

        const prev = _runnerPhases[simId];
        const statusChanged = !prev || prev.status !== status;

        if (statusChanged) {
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

        if (!card || statusChanged) {
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
                <span class="font-semibold tracking-widest text-[10px] ${cfg.text} mr-1"${cfg.hint ? ` title="${cfg.hint}"` : ''}>${cfg.label}</span>
                <span class="text-gray-400 text-[10px] w-7 text-right">${elapsedDisplay}</span>
            `;
        }
    }

    _startRunnerCardTimer();
}
