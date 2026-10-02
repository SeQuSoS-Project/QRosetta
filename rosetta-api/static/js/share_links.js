// Read-only share links for a saved run: create, list and revoke them from the Circuits
// tab. The page they open is share.html; its token sits in the URL fragment.

import { BASE_URL, formatApiError, getAuthHeaders } from './api.js';
import { dispatch, getState } from './state.js';
import { makeCopyIconButton } from './utils.js';

let _saveRun = null;

/** Set the function that saves a finished job to history: (jobId) => saved run id or null. */
export function setRunSaver(save) {
    _saveRun = save;
}

const EXPIRY_CHOICES = [[1, '1 day'], [7, '7 days'], [30, '30 days'], [90, '90 days']];
const DEFAULT_EXPIRY_DAYS = 30;

function _el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

export function shareUrl(token) {
    return `${window.location.origin}/share.html#${token}`;
}

function _when(iso) {
    const date = new Date(iso);
    return Number.isNaN(date.getTime()) ? String(iso) : date.toLocaleString();
}

async function _request(path, options = {}) {
    const res = await fetch(`${BASE_URL}${path}`, {
        ...options,
        headers: getAuthHeaders({ 'Content-Type': 'application/json', ...(options.headers || {}) }),
    });
    if (!res.ok) throw new Error(await formatApiError(res));
    return res.json();
}

function _linkRow(link, onRevoked) {
    const row = _el('li', 'flex flex-wrap items-center gap-2 text-xs text-gray-700');
    const state = link.active ? `expires ${_when(link.expires_at)}`
        : link.revoked_at ? `revoked ${_when(link.revoked_at)}` : `expired ${_when(link.expires_at)}`;
    if (link.label) row.appendChild(_el('span', 'font-medium', link.label));
    row.appendChild(_el('span', link.active ? '' : 'text-gray-400', `Created ${_when(link.created_at)}, ${state}`));
    if (link.active) {
        const revoke = _el('button', 'text-xs text-red-700 hover:text-red-900 underline', 'Revoke');
        revoke.type = 'button';
        revoke.onclick = async () => {
            if (!window.confirm('Revoke this link? Anyone who has it will no longer be able to open it.')) return;
            revoke.disabled = true;
            try {
                await _request(`/history/share-links/${encodeURIComponent(link.id)}`, { method: 'DELETE' });
                onRevoked();
            } catch (err) {
                revoke.disabled = false;
                row.appendChild(_el('span', 'text-red-700', err.message));
            }
        };
        row.appendChild(revoke);
    }
    return row;
}

async function _paintLinks(list, runId) {
    list.replaceChildren(_el('li', 'text-xs text-gray-400', 'Loading links…'));
    try {
        const links = await _request(`/history/runs/${encodeURIComponent(runId)}/share-links`);
        list.replaceChildren(...links.map(link => _linkRow(link, () => _paintLinks(list, runId))));
        if (!links.length) list.replaceChildren(_el('li', 'text-xs text-gray-400', 'No links yet.'));
    } catch (err) {
        list.replaceChildren(_el('li', 'text-xs text-red-700', err.message));
    }
}

function _createdNotice(token, expiresAt) {
    const box = _el('div', 'space-y-1 p-2 border border-amber-200 bg-amber-50 rounded');
    const row = _el('div', 'flex items-center gap-2');
    const field = /** @type {HTMLInputElement} */ (_el('input', 'flex-1 min-w-0 font-mono text-xs border border-gray-300 rounded px-2 py-1 bg-white'));
    field.readOnly = true;
    field.value = shareUrl(token);
    field.onfocus = () => field.select();
    row.appendChild(field);
    row.appendChild(makeCopyIconButton(() => field.value, 'Copy link'));
    box.appendChild(row);
    box.appendChild(_el('p', 'text-xs text-amber-900',
        `Anyone with this link can read the circuit texts of this run until ${_when(expiresAt)}. The link is shown only now; revoke it below to stop it working.`));
    return box;
}

/**
 * The saved run id of the report on screen, saving its job first when it is not yet in
 * history; null (with a message in `notice`) when that is not possible.
 */
async function _savedRunId(notice) {
    const { authToken, currentHistoryRunId, currentJobId } = getState();
    if (!authToken) {
        notice.replaceChildren(_el('p', 'text-xs text-gray-700',
            'Sign in first (Login / Register at the top of the page). A run started without signing in can still be saved while the server keeps it, at least 30 minutes after it finished.'));
        return null;
    }
    if (currentHistoryRunId) return currentHistoryRunId;
    if (!currentJobId || !_saveRun) {
        notice.replaceChildren(_el('p', 'text-xs text-gray-700',
            'This report did not come from a job run in this session, so it cannot be saved from here. Open a saved run from History to share it.'));
        return null;
    }
    const runId = await _saveRun(currentJobId);
    if (!runId) {
        notice.replaceChildren(_el('p', 'text-xs text-red-700',
            'The run could not be saved (see the notice above the results). The server keeps a job for at least 30 minutes after it finishes.'));
        return null;
    }
    if (getState().currentJobId === currentJobId) dispatch('SET_HISTORY_RUN_ID', runId);
    return runId;
}

function _taskIndex(report) {
    const summary = getState().currentSuiteData?.benchmark_summary;
    const index = Array.isArray(summary) ? summary.indexOf(report) : -1;
    return index >= 0 ? index : null;
}

/** Add the share-link controls for the run being viewed to `container`. */
export function renderShareControls(container, report = null) {
    const section = _el('section', 'space-y-2 p-3 border border-gray-200 rounded-md bg-gray-50');
    section.appendChild(_el('h3', 'text-sm font-semibold text-gray-900', 'Save and share'));
    section.appendChild(_el('p', 'text-xs text-gray-600',
        'A read-only link opens a page with the circuit texts of this saved run: the submitted, dispatched and executed circuits, the compiler input and compiled circuits when there are any, with their transforms and SDK versions. It shows no results, timings or errors. Anyone who has the link can open it until it expires, so share it like a password and revoke it when it is no longer needed.'));
    const controls = _el('div', 'flex flex-wrap items-center gap-2');
    const save = _el('button', 'text-xs font-medium bg-white hover:bg-gray-100 text-gray-800 border border-gray-300 rounded-md px-3 py-1', 'Save to history');
    save.type = 'button';
    const markSaved = () => {
        save.textContent = 'Saved to history';
        save.disabled = true;
    };
    controls.appendChild(save);
    const label = _el('label', 'inline-flex items-center gap-1 text-xs text-gray-700', 'Expires after');
    const expiry = /** @type {HTMLSelectElement} */ (_el('select', 'border border-gray-300 rounded px-1 py-0.5 text-xs'));
    EXPIRY_CHOICES.forEach(([days, text]) => {
        const option = /** @type {HTMLOptionElement} */ (_el('option', '', text));
        option.value = String(days);
        option.selected = days === DEFAULT_EXPIRY_DAYS;
        expiry.appendChild(option);
    });
    label.appendChild(expiry);
    controls.appendChild(label);
    const linkLabel = /** @type {HTMLInputElement} */ (_el('input', 'border border-gray-300 rounded px-2 py-0.5 text-xs w-44'));
    linkLabel.placeholder = 'Label for your list (optional)';
    linkLabel.maxLength = 100;
    linkLabel.setAttribute('aria-label', 'Label for this link, shown only in your list of links');
    controls.appendChild(linkLabel);
    const create = _el('button', 'text-xs font-medium bg-indigo-600 hover:bg-indigo-700 text-white rounded-md px-3 py-1', 'Create link');
    create.type = 'button';
    controls.appendChild(create);
    section.appendChild(controls);
    const notice = _el('div');
    section.appendChild(notice);
    const list = _el('ul', 'space-y-1');
    section.appendChild(list);
    save.onclick = async () => {
        save.disabled = true;
        notice.replaceChildren();
        try {
            const runId = await _savedRunId(notice);
            if (runId) {
                markSaved();
                _paintLinks(list, runId);
                return;
            }
        } catch (err) {
            notice.replaceChildren(_el('p', 'text-xs text-red-700', err.message));
        }
        save.disabled = false;
    };
    create.onclick = async () => {
        create.disabled = true;
        notice.replaceChildren();
        try {
            const runId = await _savedRunId(notice);
            if (!runId) return;
            markSaved();
            const body = { expires_in_days: Number(expiry.value) };
            if (linkLabel.value.trim()) body.label = linkLabel.value.trim();
            const link = await _request(`/history/runs/${encodeURIComponent(runId)}/share-links`, {
                method: 'POST', body: JSON.stringify(body),
            });
            const task = report ? _taskIndex(report) : null;
            notice.replaceChildren(_createdNotice(link.token + (task === null ? '' : `&task=${task}`), link.expires_at));
            _paintLinks(list, runId);
        } catch (err) {
            notice.replaceChildren(_el('p', 'text-xs text-red-700', err.message));
        } finally {
            create.disabled = false;
        }
    };
    const runId = getState().currentHistoryRunId;
    if (runId && getState().authToken) {
        markSaved();
        _paintLinks(list, runId);
    }
    container.appendChild(section);
}
