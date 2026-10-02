// Circuits tab: the submitted, dispatched and executed circuit texts of one run, and any
// compile-only input and outputs, side by side, with a line diff between any two of them.
// Shows recorded text only.

import { circuitPanes, sourcePaneId } from './circuit_panes.js';
import { comparableLines, differOnlyInLineBreaks, endsWithNewline, splitLines, visibleFormatCharacters } from './qasm_text.js';
import { _displayRunnerName, fmtInt, renderTooltip } from './render_helpers.js';
import { userFacingError } from './run_status.js';
import { diffHunks, diffLines } from './text_diff.js';
import { downloadBlob, makeCopyIconButton } from './utils.js';

const DEFAULT_EXECUTED_SHOWN = 2;
const DEFAULT_COMPILED_SHOWN = 2;

const KIND_LABEL = {
    input: 'Submitted', dispatched: 'Dispatched', executed: 'Executed',
    'compile-input': 'Compiler input', compiled: 'Compiled',
};
const KIND_CHIP = {
    input: 'bg-gray-100 text-gray-700 border-gray-300',
    dispatched: 'bg-blue-50 text-blue-800 border-blue-200',
    executed: 'bg-indigo-50 text-indigo-800 border-indigo-200',
    'compile-input': 'bg-teal-50 text-teal-800 border-teal-200',
    compiled: 'bg-teal-50 text-teal-800 border-teal-200',
};

const NORMALISATION_OPTIONS = [
    ['whitespace', 'Ignore whitespace and line breaks', 'Compare one statement per line, with single spaces between tokens.'],
    ['comments', 'Ignore comments', "Drop // and /* */ comments, blank lines and trailing spaces before comparing. QMAP's '// i' and '// o' layout lines are kept, because they say which qubit is which."],
    ['header', 'Ignore OPENQASM and include lines', 'Drop the version statement and include statements (qelib1.inc, hqslib1.inc, ...) before comparing.'],
    ['angles', 'Compare angles by value', 'Evaluate each gate parameter that has no variables (pi/4, 0.25*pi, 0.7853981633974483) and compare it in radians rounded to 12 significant digits. Parameters with variables, as in gate bodies, are compared as written.'],
];

function _el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

export function paneTitle(pane) {
    if (pane.kind === 'input') return 'Submitted circuit';
    if (pane.kind === 'dispatched') return `Dispatched · ${pane.group}`;
    if (pane.kind === 'compile-input') return 'Compiler input';
    if (pane.kind === 'compiled') {
        const level = pane.level === null ? '' : ` · level ${pane.level}`;
        return `Compiled · ${pane.compilerName || pane.compilerId}${level}`;
    }
    return `Executed · ${_displayRunnerName(pane.key)}`;
}

function _fileName(pane, prefix) {
    const base = (prefix ? `${prefix}_` : '') + (pane.kind === 'input' ? 'circuit'
        : pane.kind === 'dispatched' ? `dispatched_${pane.group}`
        : pane.kind === 'compile-input' ? 'compile_input'
        : pane.kind === 'compiled' ? `compiled_${pane.key}` : `executed_${pane.key}`);
    return `${base.replace(/[^A-Za-z0-9_.-]+/g, '_')}.qasm`;
}

function _noteList(summary, notes) {
    const details = _el('details', 'text-xs text-gray-600');
    details.appendChild(_el('summary', 'cursor-pointer select-none', `${summary} (${notes.length})`));
    const list = _el('ul', 'list-disc pl-5 mt-1 space-y-0.5');
    notes.forEach(note => list.appendChild(_el('li', 'break-words', note)));
    details.appendChild(list);
    return details;
}

function _metricLine(pane, keys = ['executed_gate_count', 'executed_depth']) {
    const row = _el('div', 'flex flex-wrap gap-x-4 text-xs text-gray-700');
    const add = (key, label, value) => {
        const item = _el('span');
        item.appendChild(renderTooltip(key, label));
        item.appendChild(document.createTextNode(`: ${fmtInt(value)}`));
        row.appendChild(item);
    };
    add(keys[0], 'Gates', pane.gateCount);
    add(keys[1], 'Depth', pane.depth);
    return row;
}

function _sourceNote(pane, uploaded) {
    const note = _recordedNote(pane);
    return uploaded ? `According to the uploaded report: ${note.charAt(0).toLowerCase()}${note.slice(1)}` : note;
}

function _recordedNote(pane) {
    if (pane.kind === 'input') return 'The circuit as submitted, before any change by the API.';
    if (pane.kind === 'compile-input') {
        return 'The circuit every compile-only service received: the submitted circuit as the API prepares it for statevector runners.';
    }
    if (pane.kind === 'compiled' && pane.text === null) {
        return 'A compile-only service was asked for this level and returned no circuit. It is not part of the pairwise comparison.';
    }
    if (pane.kind === 'compiled') {
        const layout = pane.compilerId === 'qmap'
            ? " The lines '// i' and '// o' list, for logical qubits 0, 1, 2, ..., the physical qubit of the chain that holds each one at the start and at the end."
            : '';
        return `The output of a compile-only service. It was not simulated and is not part of the pairwise comparison. Gate count and depth are counted from this text.${layout}`;
    }
    if (pane.kind === 'dispatched') {
        const names = pane.runners.map(_displayRunnerName).join(', ');
        return `The circuit the API sent to the ${pane.group} group${names ? `: ${names}` : ''}.`;
    }
    const group = pane.group ? ` Received the ${pane.group} circuit.` : '';
    if (pane.text === null) return `This backend returned no circuit text.${group}`;
    if (pane.metrics.fromText === true) {
        return `The circuit this backend executed, as its runner recorded it. Gate count and depth are counted from this text.${group}`;
    }
    if (pane.metrics.fromText === false) {
        return `The circuit this backend executed, as its runner recorded it. Gate count and depth are counted from ${pane.metrics.basis}, not from this text, so the text and the counts can differ.${group}`;
    }
    return `The circuit this backend executed, as its runner recorded it.${group}`;
}

function _paneCard(pane, context) {
    const card = _el('section', 'flex-shrink-0 w-[26rem] max-w-full flex flex-col border border-gray-200 rounded-md bg-white');
    const head = _el('header', 'p-2 border-b border-gray-200 space-y-1');
    const titleRow = _el('div', 'flex items-center gap-2');
    titleRow.appendChild(_el('span', `text-[10px] uppercase tracking-wider border rounded px-1.5 py-0.5 ${KIND_CHIP[pane.kind]}`, KIND_LABEL[pane.kind]));
    titleRow.appendChild(_el('h4', 'text-sm font-semibold text-gray-900 truncate', paneTitle(pane)));
    head.appendChild(titleRow);
    head.appendChild(_el('p', 'text-xs text-gray-500 leading-snug', _sourceNote(pane, context.uploaded)));
    if (pane.kind === 'executed') {
        head.appendChild(_metricLine(pane));
        if (pane.apiNotes.length) head.appendChild(_noteList('API changes', pane.apiNotes));
        if (pane.runnerNotes.length) head.appendChild(_noteList('Backend transforms', pane.runnerNotes));
        if (pane.sdkVersions) {
            const versions = Object.entries(pane.sdkVersions).map(([name, v]) => `${name} ${v}`);
            if (versions.length) head.appendChild(_noteList('SDK versions', versions));
        }
    } else if (pane.kind === 'compiled') {
        if (pane.text !== null) {
            const line = _metricLine(pane, ['compiled_gate_count', 'compiled_depth']);
            if (pane.multiQubitGateCount !== null) {
                const item = _el('span');
                item.appendChild(renderTooltip('compiled_multi_qubit_gate_count', 'On 2+ qubits'));
                item.appendChild(document.createTextNode(`: ${fmtInt(pane.multiQubitGateCount)}`));
                line.appendChild(item);
            }
            head.appendChild(line);
            if (pane.gateCounts.length) {
                head.appendChild(_noteList('Gates by name', pane.gateCounts.map(([name, n]) => `${name}: ${n}`)));
            }
        }
        if (pane.passes.length) head.appendChild(_noteList('Passes', pane.passes));
        if (pane.sdkVersions) {
            const versions = Object.entries(pane.sdkVersions).map(([name, v]) => `${name} ${v}`);
            if (versions.length) head.appendChild(_noteList('SDK versions', versions));
        }
        if (pane.nativeComponents.length) {
            head.appendChild(_noteList('Built from source', pane.nativeComponents.map(c =>
                `${c.name} ${c.version}${c.sourceSha256 ? ` (source sha256 ${c.sourceSha256.slice(0, 12)}…)` : ''}`
                + (c.patches.length ? `, patched with ${c.patches.join(', ')}` : ''))));
        }
    } else if ((pane.kind === 'dispatched' || pane.kind === 'compile-input') && pane.apiNotes.length) {
        head.appendChild(_noteList('API changes', pane.apiNotes));
    }
    card.appendChild(head);

    if (pane.text === null) {
        const status = pane.refusalKind === 'input' ? ' (refused)'
            : pane.refusalKind === 'output_check' ? ' (output rejected)'
            : pane.status ? ` (status: ${pane.status})` : '';
        const what = pane.kind === 'compiled' ? 'No output circuit was recorded for this compiler'
            : 'No executed circuit was recorded for this backend';
        card.appendChild(_el('p', 'p-3 text-xs text-gray-500 italic', `${what}${status}.`));
        if (pane.kind === 'executed' && pane.reason) {
            card.appendChild(_el('p', 'px-3 pb-3 text-xs text-gray-700 break-words', userFacingError(pane.reason)));
        }
        if (pane.kind === 'compiled' && pane.reason) {
            const label = pane.refusalKind === 'input' ? 'Refused: '
                : pane.refusalKind === 'output_check' ? 'Output rejected by the check: ' : '';
            card.appendChild(_el('p', 'px-3 pb-3 text-xs text-gray-700 break-words', `${label}${pane.reason}`));
        }
        return card;
    }
    const lines = splitLines(pane.text).length;
    const shown = visibleFormatCharacters(pane.text);
    const bar = _el('div', 'flex items-center gap-2 px-2 py-1 border-b border-gray-100 text-xs text-gray-500');
    bar.appendChild(_el('span', 'flex-1', `${lines} line${lines === 1 ? '' : 's'}${endsWithNewline(pane.text) ? '' : ', no final line break'}`));
    if (shown.count) {
        card.appendChild(_el('p', 'px-2 py-1 text-xs text-amber-900 bg-amber-50 border-b border-amber-200',
            `This text holds ${shown.count} invisible formatting character${shown.count === 1 ? '' : 's'} (such as a direction override), shown below as ⟨U+…⟩. Copy and download keep the original text.`));
    }
    bar.appendChild(makeCopyIconButton(() => pane.text, 'Copy this circuit'));
    const download = _el('button', 'text-xs text-gray-600 hover:text-gray-900 bg-gray-100 hover:bg-gray-200 border border-gray-300 rounded-md px-2 py-1', '⬇ .qasm');
    download.type = 'button';
    download.onclick = () => downloadBlob(new Blob([pane.text], { type: 'text/plain' }), _fileName(pane, context.filePrefix));
    bar.appendChild(download);
    card.appendChild(bar);
    card.appendChild(_el('pre', 'max-h-[60vh] overflow-auto p-2 text-xs font-mono whitespace-pre text-gray-800', shown.text));
    return card;
}

function _defaultShown(panes) {
    const shown = new Set(panes.filter(p => p.kind === 'input' || p.kind === 'dispatched').map(p => p.id));
    panes.filter(p => p.kind === 'executed' && p.text !== null)
        .slice(0, DEFAULT_EXECUTED_SHOWN).forEach(p => shown.add(p.id));
    const compiled = panes.filter(p => p.kind === 'compiled' && p.text !== null).slice(0, DEFAULT_COMPILED_SHOWN);
    compiled.forEach(p => shown.add(p.id));
    panes.filter(p => p.kind === 'compiled' && p.text === null && p.refusalKind).forEach(p => shown.add(p.id));
    if (compiled.length) panes.filter(p => p.kind === 'compile-input').forEach(p => shown.add(p.id));
    return shown;
}

function _panePicker(panes, shown, onChange) {
    const box = _el('fieldset', 'flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-700');
    box.appendChild(_el('legend', 'text-xs font-semibold text-gray-500 uppercase tracking-wider mb-1', 'Panes'));
    const inputs = [];
    const setAll = (checked) => {
        panes.forEach(pane => { if (checked) shown.add(pane.id); else shown.delete(pane.id); });
        inputs.forEach(input => { input.checked = checked; });
        onChange();
    };
    for (const [text, checked] of [['All', true], ['None', false]]) {
        const button = _el('button', 'text-xs text-blue-700 hover:underline', text);
        button.type = 'button';
        button.onclick = () => setAll(checked);
        box.appendChild(button);
    }
    panes.forEach(pane => {
        const label = _el('label', 'inline-flex items-center gap-1 cursor-pointer');
        const input = /** @type {HTMLInputElement} */ (_el('input', 'h-3.5 w-3.5'));
        input.type = 'checkbox';
        input.checked = shown.has(pane.id);
        inputs.push(input);
        input.onchange = () => {
            if (input.checked) shown.add(pane.id); else shown.delete(pane.id);
            onChange();
        };
        label.appendChild(input);
        label.appendChild(document.createTextNode(paneTitle(pane)));
        box.appendChild(label);
    });
    return box;
}

function _paneSelect(panes, selectedId, label, accessibleName) {
    const wrap = _el('label', 'inline-flex items-center gap-1 text-xs text-gray-700');
    wrap.title = accessibleName;
    wrap.appendChild(document.createTextNode(label));
    const select = /** @type {HTMLSelectElement} */ (_el('select', 'border border-gray-300 rounded px-1 py-0.5 text-xs max-w-[16rem]'));
    panes.forEach(pane => {
        const option = /** @type {HTMLOptionElement} */ (_el('option', '', paneTitle(pane)));
        option.value = pane.id;
        option.selected = pane.id === selectedId;
        select.appendChild(option);
    });
    select.setAttribute('aria-label', accessibleName);
    wrap.appendChild(select);
    return [wrap, select];
}

function _diffRow(op, aLines, bLines) {
    const style = op.type === 'delete' ? 'bg-red-50 text-red-900'
        : op.type === 'insert' ? 'bg-green-50 text-green-900' : 'text-gray-700';
    const sign = op.type === 'delete' ? '−' : op.type === 'insert' ? '+' : ' ';
    const row = _el('div', `grid grid-cols-[3rem_3rem_1rem_1fr] font-mono text-xs ${style}`);
    row.appendChild(_el('span', 'text-right pr-2 text-gray-400 select-none', op.a === null ? '' : String(op.a + 1)));
    row.appendChild(_el('span', 'text-right pr-2 text-gray-400 select-none', op.b === null ? '' : String(op.b + 1)));
    row.appendChild(_el('span', 'select-none', sign));
    row.appendChild(_el('span', 'whitespace-pre', visibleFormatCharacters(op.type === 'insert' ? bLines[op.b] : aLines[op.a]).text));
    return row;
}

function _skipRow(skip, aLines, bLines) {
    const button = _el('button', 'w-full text-left px-2 py-0.5 text-xs text-blue-700 bg-gray-50 hover:bg-gray-100 border-y border-gray-100',
        `Show ${skip.count} unchanged line${skip.count === 1 ? '' : 's'}`);
    button.type = 'button';
    button.onclick = () => button.replaceWith(...skip.ops.map(op => _diffRow(op, aLines, bLines)));
    return button;
}

function _renderDiff(out, a, b, options) {
    out.replaceChildren();
    const aLines = comparableLines(a.text, options);
    const bLines = comparableLines(b.text, options);
    const result = diffLines(aLines, bLines);
    if (!result.complete) {
        out.appendChild(_el('p', 'text-xs text-gray-600', 'The two texts differ in too many lines for a line diff here. Compare the panes side by side, or download both and diff them locally.'));
        return;
    }
    const normalised = options.whitespace || options.comments || options.header || options.angles;
    const summary = _el('p', 'text-xs text-gray-600 mb-1');
    summary.appendChild(_el('span', '', `${result.deleted} line${result.deleted === 1 ? '' : 's'} only in A, ${result.inserted} only in B`));
    summary.appendChild(document.createTextNode(normalised ? ' (normalised text).' : ' (raw text).'));
    if (!normalised && differOnlyInLineBreaks(a.text, b.text)) {
        summary.appendChild(document.createTextNode(' The texts differ only in their line-break characters (CRLF or LF).'));
    }
    if (!normalised && endsWithNewline(a.text) !== endsWithNewline(b.text)) {
        summary.appendChild(document.createTextNode(` Only ${endsWithNewline(a.text) ? 'A' : 'B'} ends with a line break.`));
    }
    out.appendChild(summary);
    if (result.deleted === 0 && result.inserted === 0) return;
    const body = _el('div', 'border border-gray-200 rounded max-h-[60vh] overflow-auto bg-white');
    diffHunks(result.ops).forEach(item => {
        body.appendChild(item.type === 'skip' ? _skipRow(item, aLines, bLines) : _diffRow(item, aLines, bLines));
    });
    out.appendChild(body);
}

function _diffSection(panes) {
    const withText = panes.filter(p => p.text !== null);
    const section = _el('section', 'space-y-2');
    section.appendChild(_el('h3', 'text-sm font-semibold text-gray-900', 'Diff'));
    section.appendChild(_el('p', 'text-xs text-gray-500',
        "A line diff compares text only. Two texts can differ in every line and still describe the same circuit (gates rewritten, angles written differently, qubits relabelled), so the counts below say nothing about whether the circuits are equivalent."));
    if (withText.length < 2) {
        section.appendChild(_el('p', 'text-xs text-gray-500', 'This run recorded fewer than two circuit texts.'));
        return section;
    }
    const firstExecuted = withText.find(p => p.kind === 'executed');
    const bId = (firstExecuted || withText[withText.length - 1]).id;
    const aId = sourcePaneId(withText.find(p => p.id === bId), withText) || withText[0].id;
    const controls = _el('div', 'flex flex-wrap items-center gap-3');
    const [aWrap, aSelect] = _paneSelect(withText, aId, 'A', 'Diff side A (lines shown with −)');
    const [bWrap, bSelect] = _paneSelect(withText, bId, 'B', 'Diff side B (lines shown with +)');
    controls.appendChild(aWrap);
    controls.appendChild(bWrap);
    const toggles = {};
    NORMALISATION_OPTIONS.forEach(([key, label, title]) => {
        const wrap = _el('label', 'inline-flex items-center gap-1 text-xs text-gray-700 cursor-pointer');
        wrap.title = title;
        const box = /** @type {HTMLInputElement} */ (_el('input', 'h-3.5 w-3.5'));
        box.type = 'checkbox';
        wrap.appendChild(box);
        wrap.appendChild(document.createTextNode(label));
        controls.appendChild(wrap);
        toggles[key] = box;
    });
    section.appendChild(controls);
    const out = _el('div');
    out.setAttribute('aria-live', 'polite');
    section.appendChild(out);
    const paint = () => {
        const options = Object.fromEntries(Object.entries(toggles).map(([key, box]) => [key, box.checked]));
        _renderDiff(out, withText.find(p => p.id === aSelect.value), withText.find(p => p.id === bSelect.value), options);
    };
    [aSelect, bSelect, ...Object.values(toggles)].forEach(control => { control.onchange = paint; });
    paint();
    return section;
}

function _crateNote(report, sharePage) {
    if (sharePage) return '';
    const batch = typeof report.task_name === 'string';
    return batch
        ? ' The RO-Crate holds the same texts for this task as circuits/<task>.qasm, dispatched_circuits/<task>/, transpiled_circuits/<task>/, compile_inputs/<task>.qasm and compiled_circuits/<task>/.'
        : ' The RO-Crate holds the same texts as circuit.qasm, dispatched_circuits/, transpiled_circuits/, compile_input.qasm and compiled_circuits/.';
}

/**
 * Render the Circuits view of `report` into `panel`. Options: `extraControls(container, report)`
 * adds controls under the introduction (the share link); `uploaded` words every note as
 * the uploaded report's claim; `sharePage` leaves out exporting hints; `filePrefix` starts
 * download names (a batch task's slug).
 */
export function renderCircuitExplorer(report, panel, { extraControls = null, uploaded = false, sharePage = false, filePrefix = '' } = {}) {
    panel.replaceChildren();
    const panes = circuitPanes(report);
    const root = _el('div', 'space-y-4');
    root.appendChild(_el('p', 'text-xs text-gray-600 leading-snug',
        'The circuit texts this run recorded: the circuit as submitted, the circuit the API sent to each dispatch group, the circuit each backend executed and, when compile-only services were selected, their input and output.' + _crateNote(report, sharePage)));
    if (extraControls) {
        const host = _el('div');
        extraControls(host, report);
        root.appendChild(host);
    }
    if (!panes.length) {
        root.appendChild(_el('p', 'text-sm text-gray-500', 'This report holds no circuit text.'));
        panel.appendChild(root);
        return;
    }
    const shown = _defaultShown(panes);
    const context = { uploaded, filePrefix: String(filePrefix).replace(/[^A-Za-z0-9_.-]+/g, '-').replace(/^-+|-+$/g, '') };
    const grid = _el('div', 'flex gap-3 overflow-x-auto pb-2 items-start');
    const paintGrid = () => grid.replaceChildren(...panes.filter(p => shown.has(p.id)).map(p => _paneCard(p, context)));
    root.appendChild(_panePicker(panes, shown, paintGrid));
    root.appendChild(grid);
    root.appendChild(_diffSection(panes));
    paintGrid();
    panel.appendChild(root);
}
