// Entry point of share.html: reads the token from the URL fragment, fetches the shared
// run's circuit texts and renders them with the Circuits view.

import { BASE_URL, formatApiError } from './api.js';
import { renderCircuitExplorer } from './circuit_explorer_renderer.js';

function _el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

function _when(iso) {
    const date = new Date(iso);
    return Number.isNaN(date.getTime()) ? '' : date.toLocaleString();
}

function _showTask(panel, tasks, index) {
    renderCircuitExplorer(tasks[index], panel);
}

function _render(root, data) {
    const header = _el('header', 'space-y-1');
    header.appendChild(_el('h1', 'text-lg font-semibold text-gray-900', data.run_name || 'Shared run'));
    const saved = _when(data.saved_at);
    const expires = _when(data.link_expires_at);
    header.appendChild(_el('p', 'text-xs text-gray-500',
        `${saved ? `Saved ${saved}. ` : ''}${expires ? `This read-only link works until ${expires}.` : ''}`));
    root.appendChild(header);
    const panel = _el('div', 'mt-4');
    if (Array.isArray(data.benchmark_summary)) {
        const tasks = data.benchmark_summary;
        const label = _el('label', 'inline-flex items-center gap-2 text-sm text-gray-700 mt-3', 'Circuit');
        const select = /** @type {HTMLSelectElement} */ (_el('select', 'border border-gray-300 rounded px-2 py-1 text-sm'));
        tasks.forEach((task, i) => {
            const option = /** @type {HTMLOptionElement} */ (_el('option', '', task.task_name || `Task ${i + 1}`));
            option.value = String(i);
            select.appendChild(option);
        });
        select.onchange = () => _showTask(panel, tasks, Number(select.value));
        label.appendChild(select);
        root.appendChild(label);
        root.appendChild(panel);
        if (tasks.length) _showTask(panel, tasks, 0);
        else panel.appendChild(_el('p', 'text-sm text-gray-500', 'This run has no circuits.'));
        return;
    }
    root.appendChild(panel);
    renderCircuitExplorer(data, panel);
}

async function main() {
    const root = document.getElementById('share-root');
    const token = window.location.hash.slice(1);
    if (!token) {
        root.replaceChildren(_el('p', 'text-sm text-gray-600', 'This page needs the link you were given, including the part after #.'));
        return;
    }
    try {
        const res = await fetch(`${BASE_URL}/shared/circuits`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token }),
            referrerPolicy: 'no-referrer',
        });
        if (res.status === 404) {
            root.replaceChildren(_el('p', 'text-sm text-gray-600', 'This link does not exist, has expired or was revoked.'));
            return;
        }
        if (!res.ok) throw new Error(await formatApiError(res));
        root.replaceChildren();
        _render(root, await res.json());
    } catch (err) {
        root.replaceChildren(_el('p', 'text-sm text-red-700', err.message));
    }
}

main();
