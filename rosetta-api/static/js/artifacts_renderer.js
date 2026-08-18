// Artifacts tab — publication-ready figures + tables.
//
// Text artifacts (tables, matrices, executed QASM, glossary) are generated ENTIRELY in
// the browser (no upload) from the report the page already holds. Only matplotlib
// figures need the server: they are rendered on demand via POST /publication/render with
// the statevector-stripped report (tiny), and nothing is stored. The data/text builders
// that mirror services/publication.py live in artifact_formats.js, not here — this file
// is the DOM/viewer layer on top of that catalog.

import { BASE_URL, getAuthHeaders } from './api.js';
import { _artHtmlEscape, _artBackends, _subsetResults, buildArtifactCatalog } from './artifact_formats.js';
import { COPY_ICON_SVG, _stripStatevectors, copyImageToClipboard, downloadBlob, makeCopyIconButton } from './utils.js';

export const ARTIFACT_SCALES = [1, 2, 3, 5];
export const ARTIFACT_SCALE_LABELS = ['Screen (1×)', 'High (2×)', 'Print (3×)', 'Very High (5×)'];
export const _TEXT_EXT = { latex: 'tex', csv: 'csv', html: 'html', markdown: 'md', qasm: 'qasm', text: 'txt' };
export const _IMG_MIME = { svg: 'image/svg+xml', png: 'image/png', pdf: 'application/pdf' };

// ---- figure rendering (server) -------------------------------------------------------
export async function _fetchFigureBlob(stripped, id, fmt, scale) {
    const resp = await fetch(`${BASE_URL}/publication/render`, {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ results: stripped, artifact_id: id, format: fmt, scale }),
    });
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: `HTTP ${resp.status}` }));
        throw new Error(err.detail || `HTTP ${resp.status}`);
    }
    return await resp.blob();
}

// ---- viewers -------------------------------------------------------------------------
// Render format-toggle buttons into `host`, re-rendering in place on pick.
export function _mountFmtSwitcher(host, formats, getCurrent, setCurrent) {
    host.innerHTML = '';
    host.className = 'flex flex-wrap gap-1';
    formats.forEach(f => {
        const b = document.createElement('button');
        b.textContent = f.toUpperCase();
        b.className = 'px-2 py-0.5 rounded text-xs border transition-all '
            + (f === getCurrent() ? 'bg-indigo-600 text-white border-indigo-600'
                                  : 'bg-white text-gray-600 border-gray-300 hover:bg-gray-100');
        b.onclick = () => { setCurrent(f); _mountFmtSwitcher(host, formats, getCurrent, setCurrent); };
        host.appendChild(b);
    });
}

export function _legendLine(text) {
    const p = document.createElement('p');
    p.className = 'text-xs text-gray-500 mt-2 leading-snug';
    p.innerHTML = `<span class="font-semibold text-gray-600">Legend:</span> ${_artHtmlEscape(text)}`;
    return p;
}

export function _renderTextViewer(container, art) {
    container.innerHTML = '';
    const state = { fmt: art.formats[0] };
    const title = document.createElement('h3');
    title.className = 'text-base font-semibold text-gray-900 mb-2';
    title.textContent = art.label;
    container.appendChild(title);

    const bar = document.createElement('div');
    bar.className = 'flex items-center gap-2 mb-2 flex-wrap';
    const pre = document.createElement('pre');
    pre.className = 'text-xs bg-gray-50 border border-gray-200 rounded p-3 overflow-auto max-h-[52vh] whitespace-pre-wrap break-words';
    pre.setAttribute('readonly', 'true');

    const paint = () => { pre.textContent = art.getText(state.fmt); };
    const swHost = document.createElement('div');
    _mountFmtSwitcher(swHost, art.formats, () => state.fmt, f => { state.fmt = f; paint(); });
    bar.appendChild(swHost);

    const copyBtn = makeCopyIconButton(() => pre.textContent, 'Copy text');
    bar.appendChild(copyBtn);
    const dl = document.createElement('button');
    dl.className = 'inline-flex items-center gap-1 text-xs text-gray-600 hover:text-gray-900 bg-gray-100 hover:bg-gray-200 border border-gray-300 rounded-md px-2 py-1';
    dl.textContent = '⬇ Download';
    dl.onclick = () => downloadBlob(new Blob([pre.textContent], { type: 'text/plain' }),
        `${art.id}.${_TEXT_EXT[state.fmt] || 'txt'}`);
    bar.appendChild(dl);

    container.appendChild(bar);
    container.appendChild(pre);
    container.appendChild(_legendLine(art.legend));
    paint();
}

export function _renderImageViewer(container, art, stripped) {
    container.innerHTML = '';
    const state = { fmt: 'png', scaleIdx: 0 };
    const title = document.createElement('h3');
    title.className = 'text-base font-semibold text-gray-900 mb-2';
    title.textContent = art.label;
    container.appendChild(title);

    // Preview (SVG at screen scale — crisp and cheap).
    const preview = document.createElement('div');
    preview.className = 'bg-white border border-gray-200 rounded p-2 mb-3 overflow-auto max-h-[46vh] flex items-center justify-center';
    preview.textContent = 'Rendering preview…';
    container.appendChild(preview);
    _fetchFigureBlob(stripped, art.id, 'svg', 1).then(blob => {
        const img = document.createElement('img');
        img.src = URL.createObjectURL(blob);
        img.className = 'max-w-full h-auto';
        img.alt = art.label;
        preview.innerHTML = ''; preview.appendChild(img);
    }).catch(e => { preview.textContent = `Preview failed: ${e.message}`; });

    // Controls: format + resolution slider + download + copy image.
    const controls = document.createElement('div');
    controls.className = 'space-y-2';

    const fmtRow = document.createElement('div');
    fmtRow.className = 'flex items-center gap-2 flex-wrap';
    const fmtLabel = document.createElement('span');
    fmtLabel.className = 'text-xs text-gray-500'; fmtLabel.textContent = 'Format:';
    fmtRow.appendChild(fmtLabel);
    const swHost = document.createElement('div');
    _mountFmtSwitcher(swHost, art.formats, () => state.fmt, f => { state.fmt = f; });
    fmtRow.appendChild(swHost);
    controls.appendChild(fmtRow);

    const sliderRow = document.createElement('div');
    sliderRow.className = 'flex items-center gap-3';
    const sLabel = document.createElement('span');
    sLabel.className = 'text-xs text-gray-500 whitespace-nowrap'; sLabel.textContent = 'Resolution:';
    const slider = document.createElement('input');
    slider.type = 'range'; slider.min = '0'; slider.max = String(ARTIFACT_SCALES.length - 1);
    slider.step = '1'; slider.value = '0'; slider.className = 'flex-1 accent-indigo-600';
    const sVal = document.createElement('span');
    sVal.className = 'text-xs font-medium text-gray-700 whitespace-nowrap min-w-[130px] text-right';
    const updateSliderLabel = () => {
        const dpi = 150 * ARTIFACT_SCALES[state.scaleIdx];
        sVal.textContent = `${ARTIFACT_SCALE_LABELS[state.scaleIdx]} · ${dpi} dpi`;
    };
    slider.oninput = () => { state.scaleIdx = parseInt(slider.value, 10); updateSliderLabel(); };
    updateSliderLabel();
    sliderRow.append(sLabel, slider, sVal);
    controls.appendChild(sliderRow);
    const note = document.createElement('p');
    note.className = 'text-[11px] text-gray-400';
    note.textContent = 'Preview is at Screen resolution; the chosen resolution applies to Download / Copy (SVG & PDF are vector — resolution-independent).';
    controls.appendChild(note);

    const btnRow = document.createElement('div');
    btnRow.className = 'flex items-center gap-2 flex-wrap';
    const dl = document.createElement('button');
    dl.className = 'inline-flex items-center gap-1 text-xs text-white bg-indigo-600 hover:bg-indigo-700 rounded-md px-3 py-1.5';
    dl.textContent = '⬇ Download';
    dl.onclick = async () => {
        const scale = ARTIFACT_SCALES[state.scaleIdx];
        dl.disabled = true; const old = dl.textContent; dl.textContent = 'Rendering…';
        try {
            const blob = await _fetchFigureBlob(stripped, art.id, state.fmt, scale);
            downloadBlob(blob, `${art.id}.${state.fmt}`);
        } catch (e) { alert(`Download failed: ${e.message}`); }
        finally { dl.disabled = false; dl.textContent = old; }
    };
    btnRow.appendChild(dl);
    const copyImg = document.createElement('button');
    copyImg.className = 'inline-flex items-center gap-1 text-gray-600 hover:text-gray-900 bg-gray-100 hover:bg-gray-200 border border-gray-300 rounded-md px-2 py-1.5';
    copyImg.innerHTML = COPY_ICON_SVG + '<span class="text-xs">PNG</span>';
    copyImg.title = 'Copy PNG to clipboard';
    copyImg.onclick = async () => {
        try {
            const blob = await _fetchFigureBlob(stripped, art.id, 'png', ARTIFACT_SCALES[state.scaleIdx]);
            await copyImageToClipboard(blob, copyImg);
        } catch (e) { alert(`Copy failed: ${e.message}`); }
    };
    btnRow.appendChild(copyImg);
    controls.appendChild(btnRow);

    container.appendChild(controls);
    container.appendChild(_legendLine(art.legend));
}

// ---- panel ---------------------------------------------------------------------------
export function renderArtifactsPanel(results, panel) {
    if (!panel) return;
    panel.innerHTML = '';

    const h2 = document.createElement('h2');
    h2.className = 'text-lg font-semibold text-gray-900 mb-1';
    h2.textContent = 'Artifacts';
    panel.appendChild(h2);
    const sub = document.createElement('p');
    sub.className = 'text-xs text-gray-500 mb-4';
    sub.textContent = 'Publication-ready figures and tables. Tables generate instantly in your browser; figures render on demand. Nothing is uploaded except a small (statevector-free) copy of this report for figure rendering.';
    panel.appendChild(sub);

    if (!buildArtifactCatalog(results).length) {
        const empty = document.createElement('p');
        empty.className = 'text-sm text-gray-500 italic';
        empty.textContent = 'No artifacts available for this report.';
        panel.appendChild(empty);
        return;
    }

    // Backend selector — scope every figure/table to a chosen subset ("which vs which").
    const allBackends = _artBackends(results);
    const selected = new Set(allBackends);
    if (allBackends.length > 1) {
        panel.appendChild(_backendSelector(allBackends, selected, () => rebuild()));
    }

    const layout = document.createElement('div');
    layout.className = 'flex flex-col md:flex-row gap-4';
    const left = document.createElement('div');
    left.className = 'md:w-64 flex-shrink-0 space-y-3 md:max-h-[70vh] md:overflow-y-auto';
    const right = document.createElement('div');
    right.className = 'flex-1 min-w-0 border border-gray-200 rounded-lg p-4 bg-white';
    layout.append(left, right);
    panel.appendChild(layout);

    // (Re)build the catalog + viewers for the currently-selected backend subset.
    function rebuild() {
        left.innerHTML = '';
        right.innerHTML = '<p class="text-sm text-gray-400">Select an artifact on the left.</p>';
        if (!selected.size) {
            left.innerHTML = '<p class="text-sm text-gray-500 italic px-2">Select at least one backend.</p>';
            return;
        }
        const full = selected.size === allBackends.length;
        const active = full ? results : _subsetResults(results, selected);
        const stripped = (typeof _stripStatevectors === 'function') ? _stripStatevectors(active) : active;
        const catalog = buildArtifactCatalog(active);
        if (!catalog.length) {
            left.innerHTML = '<p class="text-sm text-gray-500 italic px-2">No artifacts for this selection.</p>';
            return;
        }
        const groups = {};
        catalog.forEach(a => { (groups[a.group] = groups[a.group] || []).push(a); });
        let activeBtn = null;
        Object.entries(groups).forEach(([group, arts]) => {
            const gl = document.createElement('div');
            gl.className = 'text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-1';
            gl.textContent = group;
            left.appendChild(gl);
            arts.forEach(art => {
                const b = document.createElement('button');
                b.className = 'w-full text-left text-sm px-2 py-1.5 rounded hover:bg-gray-100 flex items-center gap-2';
                const dot = document.createElement('span');
                dot.className = 'text-[10px] px-1 rounded ' + (art.view === 'image'
                    ? 'bg-indigo-100 text-indigo-700' : 'bg-gray-100 text-gray-600');
                dot.textContent = art.view === 'image' ? 'IMG' : 'TXT';
                const lbl = document.createElement('span');
                lbl.className = 'truncate'; lbl.textContent = art.label;
                b.append(dot, lbl);
                b.onclick = () => {
                    if (activeBtn) activeBtn.classList.remove('bg-indigo-50', 'ring-1', 'ring-indigo-200');
                    activeBtn = b; b.classList.add('bg-indigo-50', 'ring-1', 'ring-indigo-200');
                    if (art.view === 'image') _renderImageViewer(right, art, stripped);
                    else _renderTextViewer(right, art);
                };
                left.appendChild(b);
            });
        });
    }
    rebuild();
}

// Chip toggles for the backend subset + All/None shortcuts; `onChange` re-renders the tab.
export function _backendSelector(allBackends, selected, onChange) {
    const wrap = document.createElement('div');
    wrap.className = 'mb-4 p-3 border border-gray-200 rounded-lg bg-gray-50';
    const head = document.createElement('div');
    head.className = 'flex items-center gap-2 mb-2 flex-wrap';
    const title = document.createElement('span');
    title.className = 'text-xs font-semibold text-gray-600';
    title.textContent = 'Backends';
    const hint = document.createElement('span');
    hint.className = 'text-[11px] text-gray-400';
    hint.textContent = 'pick any subset — figures & tables scope to your selection (2 = one-vs-one)';
    head.append(title, hint);

    const chips = document.createElement('div');
    chips.className = 'flex flex-wrap gap-1.5';
    const paint = () => {
        Array.from(chips.children).forEach(chip => {
            const on = selected.has(chip.dataset.sim);
            chip.className = 'px-2 py-0.5 rounded-full text-xs border transition-all ' + (on
                ? 'bg-indigo-600 text-white border-indigo-600'
                : 'bg-white text-gray-500 border-gray-300 hover:bg-gray-100');
        });
    };
    allBackends.forEach(sim => {
        const chip = document.createElement('button');
        chip.dataset.sim = sim;
        chip.textContent = sim;
        chip.onclick = () => {
            if (selected.has(sim)) selected.delete(sim); else selected.add(sim);
            paint(); onChange();
        };
        chips.appendChild(chip);
    });

    const actions = document.createElement('div');
    actions.className = 'flex gap-2 mt-2';
    const mk = (label, fn) => {
        const b = document.createElement('button');
        b.className = 'text-[11px] text-indigo-600 hover:text-indigo-800 hover:underline';
        b.textContent = label;
        b.onclick = () => { fn(); paint(); onChange(); };
        return b;
    };
    actions.append(
        mk('All', () => allBackends.forEach(s => selected.add(s))),
        mk('None', () => selected.clear()),
    );
    wrap.append(head, chips, actions);
    paint();
    return wrap;
}
