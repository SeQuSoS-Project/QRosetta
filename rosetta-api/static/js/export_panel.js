// Exports tab, right column: what the RO-Crate will contain (the report, circuits and
// provenance, plus the added views with their formats), presets, credits, the crate button
// and the report-JSON-only downloads.

import { dedupeSlugs, itemPaths, normalizeParams, viewSlug } from './artifact_views.js';
import { ICONS, PRESETS, VIEW_UI_BY_ID, itemFormats } from './export_view_ui.js';
import { makeButton as button, makeEl as el } from './render_helpers.js';
import { readPref, writePref } from './session_store.js';
import { dispatch, getState } from './state.js';
import { printableLabel } from './request_limits.js';
import { limitCodePoints } from './dom.js';
import {
    copyText, crateSources, downloadBlob, downloadFullReport, exportRoCrate, hasStatevectors,
    reportHasTruncatedSv,
} from './utils.js';

const AUTHOR_KEY = 'rosetta_export_author';
const AFFILIATION_KEY = 'rosetta_export_affiliation';
const JOB_REPORT_TTL_MIN = 30;
const ui = { source: null, includeSv: false, confirmPreset: null, filesOpen: false, creditsOpen: false };

/** Forget per-report choices (source, statevectors, a pending preset change). */
export function resetExportPanel() {
    Object.assign(ui, { source: null, includeSv: false, confirmPreset: null });
}

let _nextItemId = 1;
/** An export item with a fresh id. */
export function makeItem(view, params, formats) {
    return { id: _nextItemId++, view, params: JSON.parse(JSON.stringify(params || {})), formats: formats.slice() };
}

/** The preset's items for the views `available` offers. */
export function presetItems(presetId, available, mode) {
    const preset = PRESETS.find(p => p.id === presetId) || PRESETS[0];
    return preset.make(available, mode).map(i => makeItem(i.view, i.params, i.formats));
}

function _setItems(items, customised = true) {
    dispatch('SET_EXPORT_ITEMS', { items, customised });
}

/** Params as the crate request carries them: playlist crates drop per-report choices. */
function _requestParams(item, scope) {
    if (scope === 'report') return item.params;
    const out = Object.assign({}, item.params);
    delete out.backends; delete out.ref; delete out.bits;
    return out;
}

/** Crate paths each item adds, in item order, with slugs worked out on `results` (for a
 * playlist, one of its circuits). An item whose parameters do not fit is named after its
 * view. */
function plannedPaths(results, items, scope) {
    const slugs = dedupeSlugs(items.map(it => {
        try {
            const p = normalizeParams(it.view, scope === 'report' ? it.params : _requestParams(it, scope), results);
            return viewSlug(it.view, p, results);
        } catch { return it.view; }
    }));
    return items.map((it, i) => itemPaths(it.view, slugs[i], it.formats));
}

function _keptUntil(results) {
    const done = Date.parse(results?.finished_at || '');
    if (!Number.isFinite(done)) return `Kept for ${JOB_REPORT_TTL_MIN} minutes after the job completes.`;
    const until = new Date(done + JOB_REPORT_TTL_MIN * 60000);
    return `Kept until ${until.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} (${JOB_REPORT_TTL_MIN} minutes after the job completed).`;
}

function _radio(name, value, checked, title, help, onPick) {
    const label = el('label', 'flex items-start gap-2 text-xs cursor-pointer');
    const input = el('input', 'mt-0.5');
    input.type = 'radio'; input.name = name; input.value = value; input.checked = checked;
    input.addEventListener('change', () => onPick(value));
    const text = el('span', 'min-w-0');
    text.append(el('span', 'block text-gray-800', title), el('span', 'block text-gray-500', help));
    label.append(input, text);
    return label;
}

function _section(title, extra) {
    const sec = el('div', 'qr-export-section');
    const h = el('h4', 'qr-export-heading');
    h.append(el('span', '', title));
    if (extra !== undefined) h.append(el('span', '', extra));
    sec.append(h);
    return sec;
}

function _sourceBlock(results, scope) {
    const box = el('div', 'qr-export-item qr-export-item-locked');
    const head = el('div', 'text-xs font-semibold text-gray-800', 'Report JSON');
    head.append(el('span', 'font-normal text-gray-500', ' · results.json'));
    box.append(head);
    const sources = crateSources();
    if (!sources.includes(ui.source)) ui.source = sources[0];
    const truncated = reportHasTruncatedSv(results);
    const browserHelp = truncated
        ? 'Statevectors of circuits over 14 qubits are not in this copy.'
        : 'The report as shown here.';
    if (sources.length > 1) {
        const pick = v => { ui.source = v; };
        if (sources[0] === 'server') {
            box.append(_radio('crate-source', 'server', ui.source === 'server', 'Server copy, full', _keptUntil(results), pick));
        } else {
            box.append(_radio('crate-source', 'saved', ui.source === 'saved', 'Saved run on the server', 'Statevectors are stored as a sha256 and length.', pick));
        }
        box.append(_radio('crate-source', 'browser', ui.source === 'browser', 'Browser copy (displayed)', browserHelp, pick));
    } else {
        box.append(el('div', 'text-xs text-gray-800', 'Browser copy (displayed)'), el('div', 'text-xs text-gray-500', browserHelp));
    }
    const svLabel = el('label', 'flex items-start gap-2 text-xs cursor-pointer');
    const sv = el('input', 'mt-0.5');
    sv.type = 'checkbox'; sv.id = 'export-include-sv';
    const hasSv = hasStatevectors(results);
    sv.checked = ui.includeSv && hasSv;
    sv.disabled = !hasSv;
    sv.addEventListener('change', () => { ui.includeSv = sv.checked; });
    const svText = el('span', 'min-w-0');
    svText.append(el('span', 'block text-gray-800', 'Include raw statevectors'),
        el('span', 'block text-gray-500', hasSv ? 'Off: results.json keeps a sha256 and length per statevector.' : 'This report has no statevectors.'));
    svLabel.append(sv, svText);
    if (!hasSv) svLabel.classList.add('opacity-60', 'cursor-default');
    box.append(svLabel);
    if (scope !== 'report') {
        box.append(el('div', 'text-xs text-gray-500', scope === 'task'
            ? 'This circuit is part of a playlist: the crate holds every circuit of it.'
            : 'The crate holds every circuit of the playlist.'));
    }
    return box;
}

function _lockedRow(title, desc) {
    const box = el('div', 'qr-export-item qr-export-item-locked');
    box.append(el('div', 'text-xs font-semibold text-gray-800', title), el('div', 'text-xs text-gray-500', desc));
    return box;
}

function _itemRow(item, ctx) {
    const ui0 = VIEW_UI_BY_ID[item.view];
    const row = el('div', 'qr-export-item' + (ctx.editingId === item.id ? ' qr-export-item-current' : ''));
    const top = el('div', 'flex items-start gap-2');
    const text = el('div', 'min-w-0 flex-1');
    text.append(el('div', 'text-xs font-semibold text-gray-800', ui0 ? ui0.label : item.view));
    text.append(el('div', 'text-xs text-gray-500 break-words', ctx.summarise(item)));
    top.append(text);
    const acts = el('div', 'flex flex-shrink-0 gap-0.5');
    if (ctx.canEdit) {
        const edit = button('qr-icon-btn', '', ICONS.edit);
        edit.title = 'Edit'; edit.setAttribute('aria-label', `Edit ${ui0 ? ui0.label : item.view}`);
        edit.addEventListener('click', () => ctx.onEdit(item.id));
        acts.append(edit);
    }
    const rm = button('qr-icon-btn', '', ICONS.remove);
    rm.title = 'Remove'; rm.setAttribute('aria-label', `Remove ${ui0 ? ui0.label : item.view}`);
    rm.addEventListener('click', () => {
        _setItems(getState().exportItems.filter(x => x.id !== item.id));
        ctx.onChange();
    });
    acts.append(rm);
    top.append(acts);
    row.append(top);
    const fmts = el('div', 'flex flex-wrap gap-1');
    fmts.setAttribute('role', 'group');
    fmts.setAttribute('aria-label', `File formats for ${ui0 ? ui0.label : item.view}`);
    itemFormats(item.view).forEach(([value, label]) => {
        const chip = button('qr-fmt', label);
        chip.setAttribute('aria-pressed', String(item.formats.includes(value)));
        chip.addEventListener('click', () => {
            const items = getState().exportItems.map(x => {
                if (x.id !== item.id) return x;
                const on = x.formats.includes(value);
                const formats = on ? x.formats.filter(f => f !== value) : x.formats.concat([value]);
                return Object.assign({}, x, { formats: formats.length ? formats : [value] });
            });
            _setItems(items);
            ctx.onChange();
        });
        fmts.append(chip);
    });
    row.append(fmts);
    return row;
}

function _jsonText(results) { return JSON.stringify(results, null, 2); }

/**
 * Render the Export panel into `aside`. `ctx`: {results (the report on screen), crateResults
 * (the report the crate is built from), slugReport (the report file names are worked out on),
 * mode, scope ('report' | 'task' | 'suite' | 'error'), available (Set of view ids), canEdit,
 * editingId, onEdit(id), onChange(), summarise(item)}.
 */
export function renderExportPanel(aside, ctx) {
    aside.innerHTML = '';
    const { scope } = ctx;
    const head = el('div', 'qr-export-section');
    head.append(el('h3', 'text-sm font-semibold text-gray-900', 'Export'));
    if (scope !== 'error') {
        const row = el('div', 'flex items-center gap-2');
        const lab = el('label', 'text-xs text-gray-500', 'Preset');
        lab.htmlFor = 'export-preset';
        const sel = el('select', 'qr-input text-xs flex-1');
        sel.id = 'export-preset';
        const { exportPreset, exportCustomised, exportItems } = getState();
        PRESETS.forEach(({ id, label }) => {
            const o = el('option', '', label);
            o.value = id; o.selected = !exportCustomised && id === exportPreset;
            sel.append(o);
        });
        if (exportCustomised) {
            const o = el('option', '', 'Custom');
            o.value = 'custom'; o.selected = true;
            sel.append(o);
        }
        sel.addEventListener('change', () => {
            if (sel.value === 'custom') return;
            if (getState().exportCustomised && getState().exportItems.length) {
                ui.confirmPreset = sel.value;
            } else {
                dispatch('SET_EXPORT_PRESET', sel.value);
                _setItems(presetItems(sel.value, ctx.available, ctx.mode), false);
            }
            ctx.onChange();
        });
        row.append(lab, sel);
        head.append(row);
        if (ui.confirmPreset) {
            const conf = el('div', 'qr-export-confirm');
            const preset = PRESETS.find(p => p.id === ui.confirmPreset);
            conf.append(el('span', '', `Replace the ${exportItems.length} added item${exportItems.length === 1 ? '' : 's'} with “${preset.label}”?`));
            const yes = button('qr-btn', 'Replace');
            yes.addEventListener('click', () => {
                dispatch('SET_EXPORT_PRESET', ui.confirmPreset);
                _setItems(presetItems(ui.confirmPreset, ctx.available, ctx.mode), false);
                ui.confirmPreset = null;
                ctx.onChange();
            });
            const no = button('qr-btn', 'Keep mine');
            no.addEventListener('click', () => { ui.confirmPreset = null; ctx.onChange(); });
            conf.append(yes, no);
            head.append(conf);
        }
    }
    aside.append(head);

    if (scope === 'error') {
        aside.append(_reportOnly(ctx, 'This run failed before any backend ran, so there is no RO-Crate to export.'));
        return;
    }

    const always = _section('Always included');
    always.append(_sourceBlock(ctx.crateResults, scope),
        _lockedRow('Circuits', 'The submitted circuit and the circuit each backend was sent and executed.'),
        _lockedRow('Provenance', 'Run configuration, seeds, SDK versions, image commits and each runner’s lock file.'));
    aside.append(always);

    const items = getState().exportItems;
    const added = _section('Added', String(items.length));
    const paths = plannedPaths(ctx.slugReport || ctx.results, items, scope);
    if (!items.length) {
        added.append(el('div', 'qr-export-empty', 'Nothing added. Pick a view, set it up and press Add to export.'));
    } else {
        items.forEach(it => added.append(_itemRow(it, ctx)));
    }
    if (scope !== 'report' && items.length) {
        added.append(el('div', 'text-xs text-gray-500', 'Each view is drawn for every circuit that offers it, with that circuit’s backends, reference and bits.'));
    }
    aside.append(added);

    const credits = el('details', 'qr-export-section');
    credits.open = ui.creditsOpen;
    credits.addEventListener('toggle', () => { ui.creditsOpen = credits.open; });
    const author = readPref(AUTHOR_KEY);
    credits.append(el('summary', 'qr-export-heading cursor-pointer', 'Credits' + (author ? `: ${author}` : '')));
    const body = el('div', 'mt-2 space-y-1.5');
    [['export-author-name', AUTHOR_KEY, 'Author name (optional)', 'name'],
        ['export-author-affiliation', AFFILIATION_KEY, 'Affiliation (optional)', 'organization']].forEach(([id, key, ph, ac]) => {
        const input = el('input', 'qr-input text-xs');
        input.type = 'text'; input.id = id; input.placeholder = ph; input.autocomplete = ac; input.value = readPref(key);
        input.setAttribute('aria-label', ph);
        if (key === AUTHOR_KEY) limitCodePoints(input, getState().maxLabelLength);
        input.addEventListener('change', () => {
            const value = key === AUTHOR_KEY ? printableLabel(input.value, getState().maxLabelLength) : input.value.trim();
            input.value = value;
            writePref(key, value);
        });
        body.append(input);
    });
    credits.append(body);
    aside.append(credits);

    const files = el('details', 'qr-export-section');
    files.open = ui.filesOpen;
    files.addEventListener('toggle', () => { ui.filesOpen = files.open; });
    const addedPaths = paths.flatMap(p => p || []);
    const prefix = scope === 'report' ? '' : '<circuit>/';
    files.append(el('summary', 'qr-export-heading cursor-pointer', `Files from your selection (${addedPaths.length})`));
    const list = el('ul', 'qr-export-files');
    addedPaths.forEach(p => {
        const [folder, ...rest] = p.split('/');
        list.append(el('li', '', rest.length ? `${folder}/${prefix}${rest.join('/')}` : `${prefix}${p}`));
    });
    [['ro-crate-metadata.json'], ['results.json'], ['provenance.json'],
        [scope === 'report' ? 'circuit.qasm' : 'circuits/<circuit>.qasm'],
        ['dispatched_circuits/, transpiled_circuits/'], ['runners/<runner>/requirements.lock']].forEach(([p]) => {
        list.append(el('li', 'text-gray-500', p));
    });
    files.append(list);
    aside.append(files);

    const foot = el('div', 'qr-export-foot');
    const crate = button('qr-btn-primary w-full h-9 text-sm', 'Export RO-Crate', ICONS.crate);
    crate.id = 'btn-export-rocrate';
    const cap = getState().maxExportItems;
    if (items.length > cap) {
        crate.disabled = true;
        crate.title = `One export holds at most ${cap} items; ${items.length} are added. Remove some under Added.`;
    }
    crate.addEventListener('click', () => {
        exportRoCrate({
            source: ui.source || 'browser',
            includeStatevectors: ui.includeSv && hasStatevectors(ctx.crateResults),
            authorName: printableLabel(readPref(AUTHOR_KEY), getState().maxLabelLength), authorAffiliation: readPref(AFFILIATION_KEY),
            items: getState().exportItems.map(it => ({ view: it.view, params: _requestParams(it, scope), formats: it.formats })),
            button: crate,
        });
    });
    foot.append(crate);
    foot.append(el('div', 'text-xs text-gray-500 text-center',
        `${addedPaths.length} file${addedPaths.length === 1 ? '' : 's'} from your selection, plus the report, circuits and provenance`
        + (scope === 'report' ? '' : ' for every circuit') + '.'));
    aside.append(foot);
    aside.append(_reportOnly(ctx));
}

function _reportOnly(ctx, note) {
    const sec = el('div', 'qr-export-section border-b-0');
    sec.append(el('h4', 'qr-export-heading', 'Report JSON only'));
    if (note) sec.append(el('p', 'text-xs text-gray-500', note));
    const grid = el('div', 'grid grid-cols-1 gap-1.5');
    if (getState().currentJobId) {
        const full = button('qr-btn justify-start', 'Download full report', ICONS.download);
        full.id = 'download-btn';
        full.title = "The server's untruncated report of this job, kept for 30 minutes after it completes";
        full.addEventListener('click', () => downloadFullReport());
        grid.append(full);
    }
    const shown = button('qr-btn justify-start', 'Download displayed JSON', ICONS.download);
    shown.title = 'The report as held in this browser, including any statevectors it holds';
    shown.addEventListener('click', () => downloadBlob(new Blob([_jsonText(ctx.results)], { type: 'application/json' }), 'rosetta_raw_report.json'));
    const copy = button('qr-btn justify-start', 'Copy', ICONS.copy);
    copy.title = 'Copy the report JSON';
    copy.addEventListener('click', () => copyText(_jsonText(ctx.results), copy));
    grid.append(shown, copy);
    sec.append(grid);
    return sec;
}
