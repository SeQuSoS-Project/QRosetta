// Entry point of share.html: reads the token from the URL fragment, fetches the shared
// run's circuit texts and renders them with the Circuits view.

import { BASE_URL, formatApiError } from './api.js';
import { renderCircuitExplorer } from './circuit_explorer_renderer.js';
import { visibleFormatCharacters } from './qasm_text.js';

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

function _options(data, task) {
    return { uploaded: data.report_source !== 'server_job', sharePage: true,
             filePrefix: task && typeof task.task_name === 'string' ? task.task_name : '' };
}

function _showTask(panel, data, index) {
    const task = data.benchmark_summary[index];
    renderCircuitExplorer(task, panel, _options(data, task));
}

function _ownerText(value, fallback) {
    return typeof value === 'string' && value ? visibleFormatCharacters(value).text : fallback;
}

function _render(root, data) {
    const header = _el('header', 'space-y-1');
    header.appendChild(_el('p', 'text-xs text-gray-500', "Run name, as given by the link's owner:"));
    header.appendChild(_el('h1', 'text-lg font-semibold text-gray-900 break-words', _ownerText(data.run_name, 'Shared run')));
    const saved = _when(data.saved_at);
    const expires = _when(data.link_expires_at);
    header.appendChild(_el('p', 'text-xs text-gray-500',
        `${saved ? `Saved ${saved}. ` : ''}${expires ? `This read-only link works until ${expires}.` : ''}`));
    if (data.report_source !== 'server_job') {
        header.appendChild(_el('p', 'text-xs text-amber-900 bg-amber-50 border border-amber-200 rounded p-2',
            data.report_source === 'upload'
                ? "This report was uploaded by the link's owner, not produced by this server's run of the circuit. The texts below are as the owner supplied them."
                : 'This report was saved before the server recorded where saved reports come from, so it cannot say whether this server produced it.'));
    }
    root.appendChild(header);
    const panel = _el('div', 'mt-4');
    if (Array.isArray(data.benchmark_summary)) {
        const tasks = data.benchmark_summary;
        const label = _el('label', 'inline-flex items-center gap-2 text-sm text-gray-700 mt-3', "Circuit (names as given by the link's owner)");
        const select = /** @type {HTMLSelectElement} */ (_el('select', 'border border-gray-300 rounded px-2 py-1 text-sm'));
        tasks.forEach((task, i) => {
            const option = /** @type {HTMLOptionElement} */ (_el('option', '', `${i + 1}. ${_ownerText(task.task_name, `Task ${i + 1}`)}`));
            option.value = String(i);
            select.appendChild(option);
        });
        select.onchange = () => _showTask(panel, data, Number(select.value));
        label.appendChild(select);
        root.appendChild(label);
        root.appendChild(panel);
        if (tasks.length) _showTask(panel, data, 0);
        else panel.appendChild(_el('p', 'text-sm text-gray-500', 'This run has no circuits.'));
        return;
    }
    root.appendChild(panel);
    renderCircuitExplorer(data, panel, _options(data, null));
}

let _request = 0;

async function main() {
    const request = ++_request;
    const root = document.getElementById('share-root');
    root.replaceChildren(_el('p', 'text-sm text-gray-500', 'Loading…'));
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
        if (request !== _request) return;
        if (res.status === 404) {
            root.replaceChildren(_el('p', 'text-sm text-gray-600', 'This link does not exist, has expired or was revoked.'));
            return;
        }
        if (!res.ok) throw new Error(await formatApiError(res));
        const data = await res.json();
        if (request !== _request) return;
        root.replaceChildren();
        _render(root, data);
    } catch (err) {
        root.replaceChildren(_el('p', 'text-sm text-red-700', err.message));
    }
}

window.addEventListener('hashchange', main);
main();
