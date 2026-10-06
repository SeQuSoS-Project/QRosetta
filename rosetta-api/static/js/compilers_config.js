// The Compile-only services popover: lists GET /compilers (one row per compiler, a checkbox per
// level) and reads which levels are ticked for the next run's `compilers` field.

import { BASE_URL } from './api.js';

const GRID_ID = 'compiler-grid';

function _el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

function _row(compiler) {
    const row = _el('div', 'py-1.5 space-y-0.5');
    const line = _el('div', 'flex flex-wrap items-center justify-between gap-x-3 gap-y-1');
    line.appendChild(_el('span', `text-sm font-medium ${compiler.available ? 'text-gray-800' : 'text-gray-400'}`, compiler.name));
    const levels = _el('div', 'flex flex-wrap gap-x-3 gap-y-1');
    for (const [level, description] of Object.entries(compiler.optimization_levels || {})) {
        const label = _el('label', 'qr-option text-xs items-center');
        label.title = description;
        const box = /** @type {HTMLInputElement} */ (_el('input', 'mt-0'));
        box.type = 'checkbox';
        box.dataset.compiler = compiler.id;
        box.dataset.level = level;
        box.disabled = !compiler.available;
        label.appendChild(box);
        label.appendChild(document.createTextNode(`level ${level}`));
        levels.appendChild(label);
    }
    line.appendChild(levels);
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
