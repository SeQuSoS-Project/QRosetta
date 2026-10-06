// The Compile-only services popover: lists GET /compilers (one row per compiler, a checkbox per
// level), Toggle All, and reads which levels are ticked for the next run's `compilers` field.

import { BASE_URL } from './api.js';

const GRID_ID = 'compiler-grid';

function _el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

const LEVEL_CELL = 'w-9 flex-shrink-0 flex justify-center';

/** Every level any compiler offers, in order. */
function _levelColumns(compilers) {
    const levels = new Set(compilers.flatMap(c => Object.keys(c.optimization_levels || {}).map(Number)));
    return [...levels].sort((a, b) => a - b);
}

function _header(columns) {
    const row = _el('div', 'sticky top-0 z-10 flex items-center gap-1 bg-white border-b border-gray-200 py-1 text-[11px] font-medium text-gray-500');
    row.setAttribute('role', 'row');
    const name = _el('span', 'flex-1', 'Compiler');
    name.setAttribute('role', 'columnheader');
    row.appendChild(name);
    for (const level of columns) {
        const cell = _el('span', LEVEL_CELL, `L${level}`);
        cell.setAttribute('role', 'columnheader');
        cell.title = `Optimization level ${level}`;
        row.appendChild(cell);
    }
    return row;
}

function _row(compiler, columns) {
    const row = _el('div', 'py-1.5');
    row.setAttribute('role', 'row');
    const line = _el('div', 'flex items-center gap-1');
    const name = _el('span', `flex-1 text-sm font-medium ${compiler.available ? 'text-gray-800' : 'text-gray-400 line-through'}`, compiler.name);
    name.setAttribute('role', 'cell');
    line.appendChild(name);
    const offered = compiler.optimization_levels || {};
    for (const level of columns) {
        const cell = _el('span', LEVEL_CELL);
        cell.setAttribute('role', 'cell');
        const description = offered[String(level)];
        if (description !== undefined) {
            const box = /** @type {HTMLInputElement} */ (_el('input'));
            box.type = 'checkbox';
            box.title = description;
            box.setAttribute('aria-label', `${compiler.name} level ${level}: ${description}`);
            box.dataset.compiler = compiler.id;
            box.dataset.level = String(level);
            box.disabled = !compiler.available;
            cell.appendChild(box);
        }
        line.appendChild(cell);
    }
    row.appendChild(line);
    if (!compiler.available) row.appendChild(_el('p', 'qr-help', `Unavailable: ${compiler.unavailable_reason || 'unknown'}`));
    const versions = _versionText(compiler.versions);
    if (versions) row.appendChild(_el('p', 'qr-help break-words', versions));
    return row;
}

/** One line: the versions the running compiler image reports, native components first. */
function _versionText(versions) {
    if (!versions || typeof versions !== 'object') return '';
    const parts = [];
    for (const c of Array.isArray(versions.native_components) ? versions.native_components : []) {
        if (c && typeof c.name === 'string' && typeof c.version === 'string') {
            const patches = Array.isArray(c.patches) && c.patches.length ? `, patched with ${c.patches.join(', ')}` : '';
            parts.push(`${c.name} ${c.version} (built from source${patches})`);
        }
    }
    const sdk = versions.sdk_versions && typeof versions.sdk_versions === 'object' ? versions.sdk_versions : {};
    for (const [name, version] of Object.entries(sdk)) {
        if (typeof version === 'string') parts.push(`${name} ${version}`);
    }
    if (typeof versions.image_git_sha === 'string') parts.push(`image commit ${versions.image_git_sha}`);
    return parts.join(', ');
}

/** Fetch GET /compilers and render a table: one row per compiler, one column per level. */
export async function loadCompilers() {
    const grid = document.getElementById(GRID_ID);
    if (!grid) return;
    try {
        const resp = await fetch(`${BASE_URL}/compilers`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const compilers = (await resp.json()).filter(c => c.enabled);
        const columns = _levelColumns(compilers);
        grid.replaceChildren(_header(columns), ...compilers.map(c => _row(c, columns)));
        if (!compilers.length) grid.replaceChildren(_el('p', 'text-xs text-gray-500', 'This server offers no compile-only services.'));
    } catch (e) {
        grid.replaceChildren(_el('p', 'text-xs text-red-700', `The compiler list could not be loaded (${e instanceof Error ? e.message : String(e)}).`));
    }
}

/** The ticked compiler levels as {compiler id: [levels]}; {} when none is ticked. */
export function getCompilerSelection() {
    const selection = {};
    document.querySelectorAll(`#${GRID_ID} input[type="checkbox"][data-compiler]`).forEach(node => {
        const box = /** @type {HTMLInputElement} */ (node);
        if (!box.checked || box.disabled) return;
        (selection[box.dataset.compiler] ||= []).push(Number(box.dataset.level));
    });
    return selection;
}

/** Tick every available level, or untick them all when all are ticked. */
export function toggleAllCompilers() {
    const boxes = /** @type {HTMLInputElement[]} */ (Array.from(document.querySelectorAll(`#${GRID_ID} input[type="checkbox"][data-compiler]:not(:disabled)`)));
    const allChecked = boxes.length > 0 && boxes.every(box => box.checked);
    boxes.forEach(box => { box.checked = !allChecked; });
    document.getElementById(GRID_ID)?.dispatchEvent(new Event('change', { bubbles: true }));
}

document.getElementById(GRID_ID)?.addEventListener('change', () => document.dispatchEvent(new Event('workspace-change')));
document.getElementById('compilers-toggle-all')?.addEventListener('click', toggleAllCompilers);
