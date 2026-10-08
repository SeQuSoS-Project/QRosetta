// Exports tab: the list of views, the builder (preview, caption, settings, download, add to
// export) and the Export panel. Built when the tab is first shown for a report. Figures are
// drawn by the server; tables and text are built in the browser.

import { BASE_URL, formatApiError, getAuthHeaders } from './api.js';
import { ART_LATEX_PACKAGES, _artSlug } from './artifact_formats.js';
import { buildArtifactCatalog, scopedCatalog } from './artifact_catalog.js';
import { countSelection } from './artifact_distributions.js';
import { VIEW_BY_ID, normalizeParams, reportBackends, viewDefaults, viewSlug } from './artifact_views.js';
import { ICONS, SIZE_TAGS, VIEW_UI, VIEW_UI_BY_ID, defaultFormats } from './export_view_ui.js';
import { makeItem, presetItems, renderExportPanel, resetExportPanel } from './export_panel.js';
import { _displayRunnerName, makeButton as button, makeEl as el } from './render_helpers.js';
import { dispatch, getState } from './state.js';
import { formatBytes } from './request_limits.js';
import { _stripStatevectors, copyImageToClipboard, copyText, downloadBlob, hasStatevectors, shownCircuitName } from './utils.js';

const PNG_SCALES = [[1, '150 dpi'], [2, '300 dpi'], [4, '600 dpi']];
const TEXT_EXT = { latex: 'tex', csv: 'csv', html: 'html', markdown: 'md', qasm: 'qasm', text: 'txt', json: 'json' };
const DISPLAY_WIDTH = { single: 'max-w-[440px]', double: 'max-w-[820px]', auto: '', slide: '' };
const DENSE_BARS = 180;

const S = {
    pending: null, results: null, crateResults: null, stripped: null, mode: 'statevector',
    scope: 'report', available: new Set(), viewId: null, tab: null, params: {}, bitsText: {},
    editingId: null, qasmBackend: null, jsonWithSv: false, moreOpen: false, owner: null,
    panel: null, generation: 0, resolved: new Map(), dlChoice: {}, figureUrls: new Map(),
    renderTimer: null, renderAbort: null, jobTask: undefined, jobCopyGone: false, lastFigure: null,
};
const _baskets = new WeakMap();

const FIGURE_RAW_FIELDS = [
    'simulator', 'counts', 'qubit_ordering', 'error', 'status', 'dispatch_status', 'device', 'gpu_name',
    'timing_samples', 'compilation_time_sec', 'simulation_time_sec', 'execution_time_sec',
    'compilation_time_samples', 'simulation_time_samples', 'execution_time_samples',
    'compilation_time_sec_samples', 'simulation_time_sec_samples', 'execution_time_sec_samples',
    'process_peak_rss_mb', 'memory_usage_mb', 'process_peak_mb', 'process_peak_rss_method', 'memory_method',
];
const PAIR_FIELDS = ['simulators', 'mode', 'agreement', 'measured_assessment', 'marginal_assessment'];
const _pick = (obj, keys) => Object.fromEntries(keys.filter(k => obj && k in obj).map(k => [k, obj[k]]));

/** The fields of a report that figures read: per-backend counts and timings, pair labels,
 * matrices and the ranking reports. Keeps an upload for a figure small. */
function figureReport(results) {
    const div = results.divergence_report || {};
    const out = _pick(results, ['n_shots', 'seed', 'circuit_name', 'task_name', 'run_name', 'timing_samples',
        'performance_report', 'resource_report']);
    out.divergence_report = Object.assign({}, div, {
        pairwise_agreement: (div.pairwise_agreement || []).map(r => _pick(r, PAIR_FIELDS)),
    });
    out.raw_results = (results.raw_results || []).map(r => _pick(r, FIGURE_RAW_FIELDS));
    return out;
}

/** Render one artifact on the server and return it as a Blob: from the server's copy of a
 * job run in this session while it is kept, else from the report in the request. */
async function _fetchFigureBlob(id, fmt, scale, params = {}, signal = undefined) {
    const jobId = getState().currentJobId;
    if (jobId && S.jobTask !== undefined && !S.jobCopyGone) {
        const name = shownCircuitName(S.stripped);
        const resp = await fetch(`${BASE_URL}/jobs/${encodeURIComponent(jobId)}/publication/render`, {
            method: 'POST',
            headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
            body: JSON.stringify({ artifact_id: id, format: fmt, scale, params, task: S.jobTask,
                ...(name ? { circuit_name: name } : {}) }),
            signal,
        });
        if (resp.ok) return await resp.blob();
        if (resp.status !== 404 && resp.status !== 409) throw new Error(await formatApiError(resp));
        S.jobCopyGone = true;
    }
    const report = ['svg', 'png', 'pdf'].includes(fmt) ? figureReport(S.stripped) : S.stripped;
    const resp = await fetch(`${BASE_URL}/publication/render`, {
        method: 'POST',
        headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ results: report, artifact_id: id, format: fmt, scale, params }),
        signal,
    });
    if (resp.status === 413) {
        throw new Error(`this report is larger than the server's upload limit of ${formatBytes(getState().maxRequestBytes)}, so the server cannot draw it from the copy in this browser. `
            + 'A run from this session is drawn from the server copy for 30 minutes after it completes; an RO-Crate exported from a saved run includes the figures.');
    }
    if (!resp.ok) throw new Error(await formatApiError(resp));
    return await resp.blob();
}

/** A complete LaTeX document around one table snippet. */
function latexStandalone(snippet) {
    return ['\\documentclass{article}', '\\usepackage[T1]{fontenc}', '\\usepackage[utf8]{inputenc}',
        `\\usepackage{${ART_LATEX_PACKAGES}}`, '\\usepackage[margin=2cm]{geometry}', '\\begin{document}', '',
        snippet.trimEnd(), '', '\\end{document}', ''].join('\n');
}

function _sortedJson(v) {
    if (Array.isArray(v)) return v.map(_sortedJson);
    if (v && typeof v === 'object') return Object.fromEntries(Object.keys(v).sort().map(k => [k, _sortedJson(v[k])]));
    return v;
}

/** The task reports of a playlist, else the report itself. */
function _reports(results) {
    return Array.isArray(results?.benchmark_summary) ? results.benchmark_summary : [results];
}

/** Views the report offers: those whose artifacts the catalog lists, plus Report JSON and,
 * with executed circuits, Executed QASM. */
function _availableViews(results) {
    const out = new Set(['json']);
    _reports(results).forEach(r => {
        if (!r || r.error) return;
        try {
            buildArtifactCatalog(r).forEach(a => {
                if (a.view_id) out.add(a.view_id);
                if (a.id.startsWith('circuit_')) out.add('qasm');
            });
        } catch (e) { console.error(e); }
    });
    return out;
}

function _rawParams(viewId) {
    if (!S.params[viewId]) S.params[viewId] = {};
    return S.params[viewId];
}

/** {params, error, catalog, results} of a view from its raw parameters, cached until the
 * parameters change. */
function _resolve(viewId) {
    if (!(viewId in VIEW_BY_ID)) return { params: {}, error: null, catalog: null, results: S.results };
    if (S.bitsText[viewId]?.error) return { params: {}, error: S.bitsText[viewId].error, catalog: null, results: S.results };
    const key = viewId + JSON.stringify(_rawParams(viewId));
    if (!S.resolved.has(key)) {
        try {
            const sc = scopedCatalog(S.results, viewId, _rawParams(viewId));
            S.resolved.set(key, { params: sc.params, error: null, catalog: sc.catalog, results: sc.results });
        } catch (e) {
            S.resolved.set(key, { params: {}, error: e.message, catalog: null, results: S.results });
        }
    }
    return S.resolved.get(key);
}

function _artifact(resolved, kind) {
    const id = VIEW_BY_ID[S.viewId]?.[kind];
    return id && resolved.catalog ? resolved.catalog.find(a => a.id === id) || null : null;
}

/** The slug of a view's parameters on this report, or null when they do not fit it. */
function _slugOf(viewId, params) {
    try { return viewSlug(viewId, normalizeParams(viewId, params, S.results), S.results); } catch { return null; }
}

function _tabsFor(viewId) {
    const ui = VIEW_UI_BY_ID[viewId];
    if (ui.kind === 'json') return [['text', 'JSON']];
    if (ui.kind === 'qasm') return [['text', 'QASM']];
    const v = VIEW_BY_ID[viewId];
    if (v.text) return [['text', 'Text']];
    const tabs = [];
    if (v.figure) tabs.push(['chart', 'Chart']);
    if (v.table) tabs.push(['table', 'Table'], ['data', 'Data']);
    return tabs;
}

/** One-line summary of an item's parameters for the Export panel. Playlist crates draw each
 * circuit with its own backends, reference and bits, so those are left out there. */
function summariseItem(item) {
    const own = S.scope === 'report';
    const p = item.params || {};
    const parts = [];
    const pick = (key, labels) => { if (p[key] !== undefined && labels[p[key]]) parts.push(labels[p[key]]); };
    const ref = own && p.ref ? _displayRunnerName(p.ref) : 'reference';
    pick('layout', { overlay: 'overlay', panels: 'small multiples', diff: `difference from ${ref}`, heatmap: 'heatmap', lines: 'lines', bars: 'bars' });
    if (p.outcomes === 'bits') parts.push(own ? `bits ${(p.bits || []).join(', ')}` : 'marginal over bits');
    else if (p.outcomes === 'threshold') parts.push(p.threshold === 0 ? 'all outcomes' : `p ≥ ${p.threshold}`);
    else if (p.top !== undefined) parts.push(`top ${p.top}`);
    pick('stage', { stacked: 'both stages', simulation: 'simulation', compilation: 'compilation' });
    pick('metric', { process_peak: 'process peak RSS', memory_delta: 'Mem Delta' });
    pick('xscale', { log: 'log axis' });
    pick('size', { single: 'single column', double: 'double column', slide: 'slide' });
    if (p.title === false) parts.push('no title');
    if (p.colour === 'highlight') parts.push('highlight disagreeing');
    if (own && Array.isArray(p.backends)) parts.push(`${p.backends.length} backend${p.backends.length === 1 ? '' : 's'}`);
    return parts.join(', ') || 'default settings';
}

function _onBasketChange() {
    const items = getState().exportItems;
    _baskets.set(S.owner, { items, customised: getState().exportCustomised });
    if (S.editingId !== null && !items.some(x => x.id === S.editingId)) {
        S.editingId = null;
        _renderBuilder();
    } else {
        _renderActions();
    }
    _renderViews();
    _renderAside();
}

function _renderAside() {
    const slugReport = S.scope === 'suite'
        ? _reports(S.crateResults).find(r => r && !r.error) || S.results : S.results;
    renderExportPanel(S.panel.querySelector('[data-export-aside]'), {
        results: S.results, crateResults: S.crateResults, slugReport, mode: S.mode, scope: S.scope,
        available: S.available, canEdit: S.scope === 'report' || S.scope === 'task',
        editingId: S.editingId, summarise: summariseItem, onChange: _onBasketChange,
        onEdit: id => {
            const it = getState().exportItems.find(x => x.id === id);
            if (!it) return;
            S.viewId = it.view;
            S.params[it.view] = JSON.parse(JSON.stringify(it.params));
            delete S.bitsText[it.view];
            S.editingId = id;
            S.tab = _tabsFor(it.view)[0][0];
            _renderAll();
            S.panel.querySelector('[data-export-builder]')?.scrollIntoView({ block: 'nearest' });
        },
    });
}

function _renderViews() {
    const nav = S.panel.querySelector('[data-export-views]');
    const select = S.panel.querySelector('[data-export-view-select]');
    nav.innerHTML = '';
    select.innerHTML = '';
    const inBasket = new Set(getState().exportItems.map(i => i.view));
    let group = null;
    VIEW_UI.filter(v => S.available.has(v.id)).forEach(v => {
        if (v.group !== group) {
            group = v.group;
            nav.append(el('div', 'qr-export-group', group));
        }
        const b = button('qr-export-view' + (v.id === S.viewId ? ' qr-export-view-on' : ''), '');
        b.setAttribute('aria-current', String(v.id === S.viewId));
        b.dataset.focus = `view:${v.id}`;
        const vdef = VIEW_BY_ID[v.id];
        const tag = v.kind ? (v.kind === 'json' ? 'JSON' : 'QASM') : vdef.figure ? 'FIG' : vdef.table ? 'TAB' : 'TXT';
        b.append(el('span', 'qr-export-tag', tag), el('span', 'min-w-0 flex-1', v.label));
        if (inBasket.has(v.id)) {
            const dot = el('span', 'h-1.5 w-1.5 flex-shrink-0 rounded-full bg-indigo-500');
            dot.title = 'In the export';
            b.append(dot);
        }
        b.addEventListener('click', () => _selectView(v.id));
        nav.append(b);
        const o = el('option', '', `${v.group}: ${v.label}`);
        o.value = v.id; o.selected = v.id === S.viewId;
        select.append(o);
    });
}

function _selectView(viewId) {
    S.viewId = viewId;
    S.editingId = null;
    S.tab = _tabsFor(viewId)[0][0];
    _renderAll();
}

function _renderAll() {
    _renderViews();
    _renderBuilder();
    _renderAside();
}

/** Re-render with `render()` and give focus back to the control that had it. */
function _keepFocus(render) {
    const key = /** @type {HTMLElement|null} */ (document.activeElement)?.dataset?.focus;
    render();
    if (!key) return;
    const target = /** @type {HTMLElement|null} */ (S.panel.querySelector(`[data-focus="${CSS.escape(key)}"]`));
    target?.focus();
}

function _renderBuilder() {
    const host = S.panel.querySelector('[data-export-builder]');
    host.innerHTML = '';
    const ui = VIEW_UI_BY_ID[S.viewId];
    const head = el('div', 'space-y-0.5');
    head.append(el('h3', 'text-base font-semibold text-gray-900', ui.label), el('p', 'text-xs text-gray-500', ui.desc));
    host.append(head);
    const review = button('qr-btn qr-export-review self-start', `Review the export (${getState().exportItems.length} added)`);
    review.addEventListener('click', () => S.panel.querySelector('[data-export-aside]')?.scrollIntoView({ block: 'start' }));
    host.append(review);
    if (S.editingId !== null && getState().exportItems.some(x => x.id === S.editingId)) {
        const bar = el('div', 'qr-export-editing');
        bar.append(el('span', 'flex-1', `Editing “${ui.label}” from the export. Press Update in export to keep the changes.`));
        const stop = button('qr-btn', 'Stop editing');
        stop.addEventListener('click', () => { S.editingId = null; _renderBuilder(); _renderAside(); });
        bar.append(stop);
        host.append(bar);
    }
    const tabs = _tabsFor(S.viewId);
    if (!tabs.some(t => t[0] === S.tab)) S.tab = tabs[0][0];
    const preview = el('div', 'qr-export-preview');
    preview.id = 'export-preview';
    if (tabs.length > 1) {
        const bar = el('div', 'flex gap-1 border-b border-gray-200');
        bar.setAttribute('role', 'tablist');
        bar.setAttribute('aria-label', `${ui.label} views`);
        tabs.forEach(([key, label], i) => {
            const t = button('qr-export-subtab', label);
            t.id = `export-subtab-${key}`;
            t.dataset.focus = `tab:${key}`;
            t.setAttribute('role', 'tab');
            t.setAttribute('aria-selected', String(S.tab === key));
            t.setAttribute('aria-controls', 'export-preview');
            t.tabIndex = S.tab === key ? 0 : -1;
            t.addEventListener('click', () => { S.tab = key; _keepFocus(_renderBuilder); });
            t.addEventListener('keydown', e => {
                const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
                if (!step) return;
                e.preventDefault();
                S.tab = tabs[(i + step + tabs.length) % tabs.length][0];
                _renderBuilder();
                /** @type {HTMLElement|null} */ (S.panel.querySelector(`#export-subtab-${S.tab}`))?.focus();
            });
            bar.append(t);
        });
        host.append(bar);
        preview.setAttribute('role', 'tabpanel');
        preview.setAttribute('aria-labelledby', `export-subtab-${S.tab}`);
    }
    host.append(preview);
    const caption = el('p', 'text-xs text-gray-700 leading-relaxed');
    caption.setAttribute('data-export-caption', '');
    host.append(caption);
    const controls = el('div', '');
    controls.setAttribute('data-export-controls', '');
    host.append(controls);
    const actions = el('div', 'flex flex-wrap items-center gap-2');
    actions.setAttribute('data-export-actions', '');
    host.append(actions);
    const r = _resolve(S.viewId);
    _renderPreview(r);
    _renderControls(r);
    _renderActions();
}

function _renderPreview(r) {
    const preview = S.panel.querySelector('#export-preview');
    const caption = S.panel.querySelector('[data-export-caption]');
    preview.innerHTML = '';
    caption.textContent = '';
    const ui = VIEW_UI_BY_ID[S.viewId];
    if (ui.kind === 'json') return _renderJson(preview);
    if (ui.kind === 'qasm') return _renderQasm(preview);
    if (r.error) {
        preview.append(el('div', 'qr-export-hint', r.error));
        return;
    }
    const fig = _artifact(r, 'figure');
    const tbl = _artifact(r, 'table');
    const txt = _artifact(r, 'text');
    const tableData = tbl && (!fig || S.tab === 'table') ? tbl.getData() : null;
    const capText = fig ? fig.legend : tableData ? `${tableData.title}. ${tableData.caption}` : txt ? txt.legend : '';
    if (capText) {
        caption.append(el('span', 'font-semibold', 'Caption. '), document.createTextNode(capText));
    }
    if (S.tab === 'chart' && fig) {
        const paper = el('div', `qr-export-paper ${DISPLAY_WIDTH[r.params.size] || ''}`);
        preview.append(paper);
        preview.append(el('div', 'self-end text-[11px] text-gray-500', SIZE_TAGS[r.params.size] || ''));
        const hint = _hint(r);
        if (hint) preview.append(hint);
        _paintFigure(paper, fig.id, r.params);
    } else if (S.tab === 'table' && tbl) {
        preview.append(_tableEl(tableData));
        const det = el('details', 'self-stretch');
        det.append(el('summary', 'qr-export-heading cursor-pointer', 'LaTeX source'));
        det.append(el('pre', 'qr-export-code', tbl.getText('latex')));
        det.append(el('p', 'text-xs text-gray-500 mt-1', `To paste it into your own document, add \\usepackage{${ART_LATEX_PACKAGES}} to its preamble.`));
        preview.append(det);
    } else if (S.tab === 'data' && tbl) {
        preview.append(el('div', 'qr-export-heading self-start', `CSV: the numbers behind this ${fig ? 'figure' : 'table'}`));
        preview.append(el('pre', 'qr-export-code', tbl.getText('csv')));
        if (fig) {
            preview.append(el('div', 'qr-export-heading self-start', 'Figure spec, saved beside the figure in the crate'));
            preview.append(el('pre', 'qr-export-code', _specText(r, fig)));
        }
    } else if (txt) {
        preview.append(el('pre', 'qr-export-code', txt.getText(txt.formats[0])));
    }
}

function _specText(r, fig) {
    const v = VIEW_BY_ID[S.viewId];
    return JSON.stringify(_sortedJson({
        view: S.viewId, figure: v.figure || null, table: v.table || null, parameters: r.params,
        caption: fig.legend, analysis_version: (S.results.divergence_report || {}).analysis_version ?? null,
    }), null, 2);
}

function _hint(r) {
    if (S.viewId !== 'counts' || r.params.layout !== 'overlay') return null;
    const sel = countSelection(r.results, r.params);
    const bars = sel.rows.length * Math.max(1, sel.cp.sims.length);
    if (bars <= DENSE_BARS) return null;
    const box = el('div', 'qr-export-hint flex flex-wrap items-center gap-2');
    box.append(el('span', '', `${bars} bars in one panel. Differences between backends read more easily as`));
    const fix = button('qr-btn', 'Difference from reference');
    fix.addEventListener('click', () => _set('layout', 'diff'));
    box.append(fix);
    return box;
}

function _tableEl(data) {
    const wrap = el('div', 'qr-export-table');
    const table = el('table', 'min-w-full text-xs');
    const thead = el('thead');
    const hr = el('tr');
    data.headers.forEach(h => hr.append(el('th', '', String(h))));
    thead.append(hr);
    const tbody = el('tbody');
    data.rows.forEach(row => {
        const tr = el('tr');
        row.forEach(c => tr.append(el('td', '', String(c))));
        tbody.append(tr);
    });
    table.append(thead, tbody);
    wrap.append(table);
    return wrap;
}

function _paintFigure(paper, figId, params) {
    const key = JSON.stringify([S.generation, figId, params]);
    const show = url => {
        paper.innerHTML = '';
        const img = el('img', 'block w-full h-auto');
        img.src = url;
        img.alt = `${VIEW_UI_BY_ID[S.viewId].label}${VIEW_BY_ID[S.viewId]?.table ? '. The plotted values are in the Table tab of this view.' : ''}`;
        paper.append(img);
        S.lastFigure = { view: S.viewId, url };
    };
    if (S.figureUrls.has(key)) { show(S.figureUrls.get(key)); return; }
    if (S.lastFigure?.view === S.viewId) {
        const wrap = el('div', 'relative');
        const img = el('img', 'block w-full h-auto opacity-40');
        img.src = S.lastFigure.url;
        img.alt = '';
        wrap.append(img, el('div', 'absolute inset-0 flex items-center justify-center text-xs font-medium text-gray-700', 'Rendering the figure'));
        paper.append(wrap);
    } else {
        paper.append(el('div', 'p-6 text-center text-xs text-gray-500', 'Rendering the figure'));
    }
    _cancelRender();
    const generation = S.generation;
    S.renderTimer = setTimeout(() => {
        const abort = new AbortController();
        S.renderAbort = abort;
        _fetchFigureBlob(figId, 'svg', 1, _rawParams(S.viewId), abort.signal).then(blob => {
            if (generation !== S.generation) return;
            const url = URL.createObjectURL(blob);
            S.figureUrls.set(key, url);
            if (paper.isConnected) show(url);
        }).catch(e => {
            if (e.name === 'AbortError' || generation !== S.generation) return;
            paper.innerHTML = '';
            paper.append(el('div', 'p-6 text-center text-xs text-red-700', `The figure could not be drawn: ${e.message}`));
        });
    }, 200);
}

function _cancelRender() {
    clearTimeout(S.renderTimer);
    S.renderAbort?.abort();
    S.renderAbort = null;
}

function _jsonShown() {
    return S.jsonWithSv ? S.results : _stripStatevectors(S.results);
}

function _renderJson(preview) {
    if (hasStatevectors(S.results)) {
        const lab = el('label', 'flex items-center gap-2 self-start text-xs text-gray-600 cursor-pointer');
        const cb = el('input', '');
        cb.type = 'checkbox'; cb.id = 'json-show-sv'; cb.checked = S.jsonWithSv;
        cb.dataset.focus = 'json-show-sv';
        cb.addEventListener('change', () => { S.jsonWithSv = cb.checked; _keepFocus(_renderBuilder); });
        lab.append(cb, document.createTextNode('Show statevector amplitudes (they can be hundreds of thousands of lines)'));
        preview.append(lab);
    }
    preview.append(el('pre', 'qr-export-code', JSON.stringify(_jsonShown(), null, 2)));
}

function _qasmBackends() {
    return (S.results.raw_results || []).filter(r => r.simulator && r.transpiled_qasm).map(r => r.simulator);
}

function _qasmText() {
    const item = buildArtifactCatalog(S.results).find(a => a.id === `circuit_${_artSlug(S.qasmBackend || '')}`);
    return item ? item.getText('qasm') : null;
}

function _renderQasm(preview) {
    const sims = _qasmBackends();
    if (!sims.includes(S.qasmBackend)) S.qasmBackend = sims[0] || null;
    preview.append(el('pre', 'qr-export-code', _qasmText() ?? 'No executed circuit was recorded.'));
}

function _row(label, control, help) {
    const row = el('div', 'qr-export-row');
    row.append(el('div', 'qr-export-label', label));
    const cell = el('div', 'flex min-w-0 flex-wrap items-center gap-1.5');
    cell.append(...[].concat(control));
    if (help) cell.append(el('div', 'basis-full text-[11px] text-gray-500', help));
    row.append(cell);
    return row;
}

/** Set one parameter and re-render. Changing which outcomes are shown drops any invalid
 * value of the other outcome modes; dropping the reference's backend drops the reference. */
function _set(key, value) {
    const raw = _rawParams(S.viewId);
    if (value === null) delete raw[key];
    else raw[key] = value;
    if (key === 'outcomes') {
        delete S.bitsText[S.viewId];
        ['top', 'threshold', 'bits'].forEach(k => {
            if (!(k in raw)) return;
            try { normalizeParams(S.viewId, { [k]: raw[k] }, S.results); } catch { delete raw[k]; }
        });
    }
    if (key === 'backends' && raw.ref !== undefined && Array.isArray(value) && !value.includes(raw.ref)) delete raw.ref;
    _keepFocus(_renderBuilder);
}

function _seg(key, label, options, current) {
    const g = el('div', 'qr-seg');
    g.setAttribute('role', 'group');
    g.setAttribute('aria-label', label);
    options.forEach(([value, text]) => {
        const b = button('', text);
        b.dataset.focus = `${key}:${value}`;
        b.setAttribute('aria-pressed', String(current === value));
        b.addEventListener('click', () => _set(key, value));
        g.append(b);
    });
    return g;
}

function _backendChips(p) {
    const everyone = reportBackends(S.results);
    const selected = p.backends || everyone;
    const chips = everyone.map(sim => {
        const c = button('qr-chip', _displayRunnerName(sim));
        c.title = sim;
        c.dataset.focus = `backend:${sim}`;
        c.setAttribute('aria-pressed', String(selected.includes(sim)));
        c.addEventListener('click', () => {
            const next = selected.includes(sim) ? selected.filter(s => s !== sim) : everyone.filter(s => selected.includes(s) || s === sim);
            _set('backends', next);
        });
        return c;
    });
    const all = button('qr-link', 'All');
    all.dataset.focus = 'backends:all';
    all.addEventListener('click', () => _set('backends', null));
    const none = button('qr-link', 'None');
    none.dataset.focus = 'backends:none';
    none.addEventListener('click', () => _set('backends', []));
    return chips.concat([all, none]);
}

function _numberInput(id, key, value, attrs, parse) {
    const n = el('input', 'qr-input-small');
    n.type = 'number'; n.id = id; n.value = String(value); n.dataset.focus = key;
    Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, v));
    n.addEventListener('change', () => _set(key, n.value.trim() === '' ? null : parse(n.value)));
    return n;
}

function _outcomesControl(p) {
    const parts = [_seg('outcomes', 'Outcomes', [['top', 'Top'], ['threshold', 'Above threshold'], ['bits', 'Marginal over bits']], p.outcomes)];
    if (p.outcomes === 'top') {
        const n = _numberInput('export-top', 'top', p.top, { min: '1', max: '64', 'aria-label': 'Number of outcomes', class: 'qr-input-small w-14' }, v => Number(v));
        parts.push(n, el('span', 'text-xs text-gray-500', 'outcomes'));
    } else if (p.outcomes === 'threshold') {
        const n = _numberInput('export-threshold', 'threshold', p.threshold, { min: '0', max: '1', step: '0.001', 'aria-label': 'Probability threshold', class: 'qr-input-small w-20' }, v => Number(v));
        parts.push(el('span', 'text-xs text-gray-500', 'probability ≥'), n);
    } else {
        const t = el('input', 'qr-input-small w-28 text-left');
        t.type = 'text'; t.id = 'export-bits'; t.dataset.focus = 'bits';
        t.value = S.bitsText[S.viewId]?.text ?? (p.bits || []).join(', ');
        t.setAttribute('aria-label', 'Classical bits');
        t.addEventListener('change', () => {
            const words = t.value.split(/[\s,]+/).filter(Boolean);
            const nums = words.map(Number);
            if (!words.length || nums.some(v => !Number.isInteger(v))) {
                S.bitsText[S.viewId] = { text: t.value, error: 'Give classical bit numbers separated by commas, e.g. 0, 5, 11.' };
                _keepFocus(_renderBuilder);
                return;
            }
            delete S.bitsText[S.viewId];
            _set('bits', nums);
        });
        parts.push(t, el('span', 'text-xs text-gray-500', 'classical bits, up to 6'));
    }
    if (p.outcomes !== 'bits') {
        const lab = el('label', 'ml-1 flex items-center gap-1.5 text-xs text-gray-700 cursor-pointer');
        const cb = el('input', '');
        cb.type = 'checkbox'; cb.checked = !!p.other; cb.id = 'export-other'; cb.dataset.focus = 'other';
        cb.addEventListener('change', () => _set('other', cb.checked));
        lab.append(cb, document.createTextNode("Sum the rest into 'other'"));
        parts.push(lab);
    }
    return parts;
}

function _outcomesHelp(p) {
    if (p.outcomes === 'bits') return 'Sums out the other bits: k chosen bits give 2^k outcomes, every one shown.';
    const sizes = (S.results.raw_results || []).map(x => x.counts)
        .filter(c => c && typeof c === 'object').map(c => Object.keys(c).length);
    if (!sizes.length) return null;
    const lo = Math.min(...sizes), hi = Math.max(...sizes);
    return `Each backend observed ${lo === hi ? lo : `${lo}–${hi}`} distinct outcomes in this run.`;
}

function _control(c, p) {
    const value = p[c.key];
    if (c.control === 'backends') return _row(c.label, _backendChips(p), `${(p.backends || reportBackends(S.results)).length} of ${reportBackends(S.results).length} selected`);
    if (c.control === 'seg') return _row(c.label, _seg(c.key, c.label, c.options, value), c.help);
    if (c.control === 'select' || c.control === 'ref') {
        const s = el('select', 'qr-input text-xs w-auto');
        s.id = `export-${c.key}`;
        s.dataset.focus = c.key;
        s.setAttribute('aria-label', c.label);
        const options = c.control === 'ref'
            ? (p.backends || reportBackends(S.results)).map(sim => [sim, _displayRunnerName(sim)]) : c.options;
        options.forEach(([v, l]) => { const o = el('option', '', l); o.value = v; o.selected = v === value; s.append(o); });
        s.addEventListener('change', () => _set(c.key, s.value));
        return _row(c.label, s, c.help);
    }
    if (c.control === 'toggle') {
        const lab = el('label', 'flex items-center gap-1.5 text-xs text-gray-700 cursor-pointer');
        const cb = el('input', '');
        cb.type = 'checkbox'; cb.checked = !!value; cb.id = `export-${c.key}`; cb.dataset.focus = c.key;
        cb.setAttribute('aria-label', c.label);
        cb.addEventListener('change', () => _set(c.key, cb.checked));
        lab.append(cb, document.createTextNode(value ? 'Shown' : 'Hidden'));
        return _row(c.label, lab, c.help);
    }
    if (c.control === 'outcomes') return _row(c.label, _outcomesControl(p), _outcomesHelp(p));
    return null;
}

function _renderControls(r) {
    const host = S.panel.querySelector('[data-export-controls]');
    host.innerHTML = '';
    host.className = '';
    const ui = VIEW_UI_BY_ID[S.viewId];
    if (ui.kind === 'qasm') {
        host.className = 'qr-export-controls';
        const s = el('select', 'qr-input text-xs w-auto');
        s.id = 'export-qasm-backend'; s.dataset.focus = 'qasm-backend';
        s.setAttribute('aria-label', 'Backend');
        _qasmBackends().forEach(sim => { const o = el('option', '', _displayRunnerName(sim)); o.value = sim; o.selected = sim === S.qasmBackend; s.append(o); });
        s.addEventListener('change', () => { S.qasmBackend = s.value; _keepFocus(_renderBuilder); });
        host.append(_row('Backend', s));
        return;
    }
    if (!(S.viewId in VIEW_BY_ID)) return;
    const p = r.error ? Object.assign(viewDefaults(S.viewId), _rawParams(S.viewId)) : r.params;
    const visible = ui.controls.filter(c => !c.show || c.show(p));
    if (!visible.length) return;
    host.className = 'qr-export-controls';
    visible.filter(c => !c.more).forEach(c => { const row = _control(c, p); if (row) host.append(row); });
    const more = visible.filter(c => c.more);
    if (more.length) {
        const det = el('details', 'border-t border-gray-100 pt-2');
        det.open = S.moreOpen;
        det.addEventListener('toggle', () => { S.moreOpen = det.open; });
        det.append(el('summary', 'cursor-pointer text-xs font-semibold text-gray-600', 'More: ' + more.map(c => c.label.toLowerCase()).join(', ')));
        const inner = el('div', 'mt-2 space-y-2');
        more.forEach(c => { const row = _control(c, p); if (row) inner.append(row); });
        det.append(inner);
        host.append(det);
    }
}

function _downloadOptions(viewId) {
    const ui = VIEW_UI_BY_ID[viewId];
    if (ui.kind === 'json') return [['json', 'JSON']];
    if (ui.kind === 'qasm') return [['qasm', 'QASM']];
    if (VIEW_BY_ID[viewId].text) return [['markdown', 'Markdown'], ['text', 'Text']];
    if (S.tab === 'chart') return [['svg', 'SVG'], ['pdf', 'PDF'], ...PNG_SCALES.map(([s, l]) => [`png:${s}`, `PNG, ${l}`])];
    if (S.tab === 'table') return [['latex', 'LaTeX'], ['latex-standalone', 'LaTeX document'], ['csv', 'CSV'], ['markdown', 'Markdown'], ['html', 'HTML'], ['xlsx', 'XLSX']];
    return [['csv', 'CSV'], ...(VIEW_BY_ID[viewId].figure ? [['spec', 'Figure spec (JSON)']] : [])];
}

/** The text a download or copy of `choice` gives for the current view, or null when the
 * choice is drawn by the server (a figure or XLSX). */
function _text(r, choice) {
    const ui = VIEW_UI_BY_ID[S.viewId];
    if (ui.kind === 'json') return JSON.stringify(_jsonShown(), null, 2);
    if (ui.kind === 'qasm') return _qasmText();
    const fig = _artifact(r, 'figure'), tbl = _artifact(r, 'table'), txt = _artifact(r, 'text');
    if (choice === 'spec' && fig) return _specText(r, fig);
    if (choice === 'latex-standalone' && tbl) return latexStandalone(tbl.getText('latex'));
    if (tbl && ['latex', 'csv', 'markdown', 'html'].includes(choice)) return tbl.getText(choice);
    if (txt && ['markdown', 'text'].includes(choice)) return txt.getText(choice);
    return null;
}

function _fileName(r, choice) {
    const ui = VIEW_UI_BY_ID[S.viewId];
    if (ui.kind === 'json') return 'rosetta_raw_report.json';
    if (ui.kind === 'qasm') return `executed_${_artSlug(S.qasmBackend || '')}.qasm`;
    const stem = _slugOf(S.viewId, _rawParams(S.viewId)) || S.viewId;
    const fmt = choice.split(':')[0];
    if (choice === 'spec') return `${stem}.spec.json`;
    if (choice === 'latex-standalone') return `${stem}_standalone.tex`;
    return `${stem}.${TEXT_EXT[fmt] || fmt}`;
}

async function _download(choice, btn) {
    const r = _resolve(S.viewId);
    if (r.error) return;
    const text = _text(r, choice);
    if (text !== null) {
        downloadBlob(new Blob([text], { type: 'text/plain' }), _fileName(r, choice));
        return;
    }
    const [fmt, scaleText] = choice.split(':');
    const target = ['svg', 'pdf', 'png'].includes(fmt) ? _artifact(r, 'figure') : _artifact(r, 'table');
    if (!target) return;
    const old = btn.innerHTML;
    btn.disabled = true; btn.textContent = 'Rendering';
    try {
        downloadBlob(await _fetchFigureBlob(target.id, fmt, parseInt(scaleText || '1', 10), _rawParams(S.viewId)), _fileName(r, choice));
    } catch (e) {
        alert(`Download failed: ${e.message}`);
    } finally {
        btn.disabled = false; btn.innerHTML = old;
    }
}

async function _copy(choice, btn) {
    const r = _resolve(S.viewId);
    if (r.error) return;
    const text = _text(r, choice);
    if (text !== null) { copyText(text, btn); return; }
    const fig = _artifact(r, 'figure');
    if (S.tab !== 'chart' || !fig) return;
    try {
        copyImageToClipboard(await _fetchFigureBlob(fig.id, 'png', parseInt(choice.split(':')[1] || '1', 10), _rawParams(S.viewId)), btn);
    } catch (e) {
        alert(`Copy failed: ${e.message}`);
    }
}

function _renderActions() {
    const host = S.panel?.querySelector('[data-export-actions]');
    if (!host) return;
    host.innerHTML = '';
    const opts = _downloadOptions(S.viewId);
    const choiceKey = `${S.viewId}:${S.tab}`;
    if (!opts.some(([v]) => v === S.dlChoice[choiceKey])) S.dlChoice[choiceKey] = opts[0][0];
    const group = el('span', 'qr-split');
    const sel = el('select', '');
    sel.id = 'export-download-format';
    sel.dataset.focus = 'download-format';
    sel.setAttribute('aria-label', 'Download format');
    opts.forEach(([v, l]) => { const o = el('option', '', l); o.value = v; o.selected = v === S.dlChoice[choiceKey]; sel.append(o); });
    const dl = button('qr-btn', 'Download', ICONS.download);
    dl.addEventListener('click', () => _download(sel.value, dl));
    group.append(sel, dl);
    const copy = button('qr-btn', S.tab === 'chart' ? 'Copy PNG' : 'Copy', ICONS.copy);
    const paintCopy = () => {
        copy.disabled = sel.value === 'xlsx';
        copy.title = copy.disabled ? 'An XLSX file cannot be copied as text; download it instead.' : '';
    };
    sel.addEventListener('change', () => { S.dlChoice[choiceKey] = sel.value; paintCopy(); });
    paintCopy();
    copy.addEventListener('click', () => _copy(sel.value, copy));
    host.append(group, copy, el('span', 'flex-1'));
    const ui = VIEW_UI_BY_ID[S.viewId];
    if (ui.kind === 'json' || ui.kind === 'qasm') {
        host.append(el('span', 'text-xs text-gray-500', ui.kind === 'json' ? 'Always in the crate as results.json' : 'Always in the crate under transpiled_circuits/'));
        return;
    }
    if (S.scope === 'suite' || S.scope === 'error') return;
    const r = _resolve(S.viewId);
    const items = getState().exportItems;
    const editing = S.editingId !== null && items.some(x => x.id === S.editingId);
    const raw = JSON.parse(JSON.stringify(_rawParams(S.viewId)));
    const slug = r.error ? null : _slugOf(S.viewId, raw);
    const existing = slug !== null && items.some(x => x.view === S.viewId && x.id !== S.editingId && _slugOf(x.view, x.params) === slug);
    let add;
    if (editing) {
        add = button('qr-btn-primary', 'Update in export', ICONS.check);
        add.addEventListener('click', () => {
            const next = items.map(x => x.id === S.editingId ? Object.assign({}, x, { params: raw }) : x);
            dispatch('SET_EXPORT_ITEMS', { items: next, customised: true });
            S.editingId = null;
            _baskets.set(S.owner, { items: next, customised: true });
            _renderAll();
        });
    } else if (existing) {
        add = button('qr-btn-done', 'In export', ICONS.check);
        add.disabled = true;
    } else {
        add = button('qr-btn-primary', 'Add to export', ICONS.plus);
        add.addEventListener('click', () => {
            const next = items.concat([makeItem(S.viewId, raw, defaultFormats(S.viewId))]);
            dispatch('SET_EXPORT_ITEMS', { items: next, customised: true });
            _onBasketChange();
        });
    }
    if (r.error) add.disabled = true;
    const cap = getState().maxExportItems;
    if (!editing && !existing && items.length >= cap) {
        add.disabled = true;
        add.title = `One export holds at most ${cap} items. Remove an item under Added to add this one.`;
        host.append(add, el('span', 'text-xs text-gray-500', `${cap} of ${cap} items added`));
        return;
    }
    host.append(add);
}

/** 'measured' for a measured report or playlist, else 'statevector'. */
function _reportMode(results) {
    if (!results) return 'statevector';
    if ('n_shots' in results || results.mode === 'measured') return 'measured';
    return _reports(results).some(t => t && 'n_shots' in t) ? 'measured' : 'statevector';
}

let _heightObserver = null;
/** Cap the sticky columns at the height of the box the tab scrolls in, so the Export panel
 * scrolls on its own instead of running past the bottom of the results card. */
function _fitStickyColumns(panel) {
    const scroller = panel.closest('#tab-content') || panel.parentElement;
    if (!scroller || typeof ResizeObserver === 'undefined') return;
    const apply = () => panel.style.setProperty('--qr-export-h', `${scroller.clientHeight}px`);
    _heightObserver?.disconnect();
    _heightObserver = new ResizeObserver(apply);
    _heightObserver.observe(scroller);
    apply();
}

/** Load the basket of the report the crate is built from: the one last used for it, else
 * the preset's. */
function _loadBasket(scope, available) {
    if (S.owner === S.crateResults) return;
    S.owner = S.crateResults;
    resetExportPanel();
    const saved = _baskets.get(S.owner);
    if (saved) {
        dispatch('SET_EXPORT_ITEMS', saved);
        return;
    }
    const presetScope = scope === 'suite' ? _availableViews(S.crateResults) : available;
    const items = presetItems(getState().exportPreset, presetScope, S.mode);
    dispatch('SET_EXPORT_ITEMS', { items, customised: false });
    _baskets.set(S.owner, { items, customised: false });
}

/**
 * Set the report the Exports tab shows. `scope`: 'report' (the crate is this report),
 * 'task' (a circuit of the playlist in `crateResults`), 'suite' (the playlist summary) or
 * 'error' (the run failed before dispatch). The tab is built when it is shown
 * (showExportTab), so a report that is never exported costs nothing here.
 */
export function renderExportTab(results, panel, { scope = 'report', crateResults = results } = {}) {
    if (!panel) return;
    _cancelRender();
    S.generation += 1;
    S.pending = { results, panel, scope, crateResults };
    panel.innerHTML = '';
    if (!panel.classList.contains('hidden')) showExportTab();
}

/** Build the Exports tab for the report renderExportTab set, if it is not built yet. */
export function showExportTab() {
    if (!S.pending) return;
    const { results, panel, scope, crateResults } = S.pending;
    S.pending = null;
    S.figureUrls.forEach(url => URL.revokeObjectURL(url));
    S.figureUrls.clear();
    const tasks = Array.isArray(crateResults?.benchmark_summary) ? crateResults.benchmark_summary : null;
    Object.assign(S, {
        results, crateResults, scope, panel, stripped: _stripStatevectors(results),
        mode: _reportMode(results), params: {}, bitsText: {}, editingId: null, qasmBackend: null,
        jsonWithSv: false, resolved: new Map(), dlChoice: {}, jobCopyGone: false, lastFigure: null,
        jobTask: scope === 'report' ? null
            : scope === 'task' && tasks && tasks.indexOf(results) >= 0 ? tasks.indexOf(results) : undefined,
    });
    S.available = scope === 'suite' || scope === 'error' ? new Set(['json']) : _availableViews(results);
    _loadBasket(scope, S.available);
    const first = VIEW_UI.find(v => S.available.has(v.id) && !v.kind && VIEW_BY_ID[v.id].figure);
    S.viewId = (S.viewId && S.available.has(S.viewId)) ? S.viewId : (first ? first.id : 'json');
    S.tab = _tabsFor(S.viewId)[0][0];
    panel.innerHTML = '';
    panel.classList.add('qr-export-host');
    _fitStickyColumns(panel);
    const layout = el('div', 'qr-export-layout');
    const nav = el('nav', 'qr-export-views');
    nav.setAttribute('aria-label', 'Views');
    nav.setAttribute('data-export-views', '');
    const selWrap = el('div', 'qr-export-view-select');
    const sel = el('select', 'qr-input text-sm');
    sel.setAttribute('aria-label', 'View');
    sel.setAttribute('data-export-view-select', '');
    sel.addEventListener('change', () => _selectView(sel.value));
    selWrap.append(sel);
    const builder = el('section', 'qr-export-builder');
    builder.setAttribute('data-export-builder', '');
    const aside = el('aside', 'qr-export-aside');
    aside.setAttribute('aria-label', 'Export');
    aside.setAttribute('data-export-aside', '');
    layout.append(nav, selWrap, builder, aside);
    panel.append(layout);
    _renderAll();
}
