// Config panel section for compile-only services: lists GET /compilers and reads which
// compiler levels are ticked for the next run's `compilers` field.

import { BASE_URL } from './api.js';

const GRID_ID = 'compiler-grid';

function _el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

function _row(compiler) {
    const row = _el('div', 'border border-teal-100 rounded p-2');
    const head = _el('div', 'flex items-center justify-between gap-2');
    head.appendChild(_el('span', 'text-sm font-medium text-teal-900', compiler.name));
    if (!compiler.available) {
        head.appendChild(_el('span', 'text-[11px] text-gray-500', `unavailable: ${compiler.unavailable_reason || 'unknown'}`));
    }
    row.appendChild(head);
    const levels = _el('div', 'flex flex-wrap gap-x-3 gap-y-1 mt-1');
    for (const [level, description] of Object.entries(compiler.optimization_levels || {})) {
        const label = _el('label', 'inline-flex items-center gap-1 text-xs text-gray-700 cursor-pointer');
        label.title = description;
        const box = /** @type {HTMLInputElement} */ (_el('input', 'h-3.5 w-3.5'));
        box.type = 'checkbox';
        box.dataset.compiler = compiler.id;
        box.dataset.level = level;
        box.disabled = !compiler.available;
        label.appendChild(box);
        label.appendChild(document.createTextNode(`level ${level}`));
        levels.appendChild(label);
    }
    row.appendChild(levels);
    const versions = _versionText(compiler.versions);
    if (versions) row.appendChild(_el('p', 'text-[11px] text-gray-500 mt-1 break-words', versions));
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

/** Fetch GET /compilers and render one row per compiler, with a checkbox per level. */
export async function loadCompilers() {
    const grid = document.getElementById(GRID_ID);
    if (!grid) return;
    try {
        const resp = await fetch(`${BASE_URL}/compilers`);
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const compilers = (await resp.json()).filter(c => c.enabled);
        grid.replaceChildren(...compilers.map(_row));
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

document.getElementById(GRID_ID)?.addEventListener('change', () => document.dispatchEvent(new Event('workspace-change')));
