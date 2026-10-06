// The results area before the first result: the tabs a result will have (not yet usable), a
// title naming what Run will do, and the table the result will fill, with "—" in every value
// cell. Below it, example circuits and a link to the docs. The running view (status_cards.js)
// builds its tabs and tables with the same greyTabs() and placeholderTable(). Leaf module:
// emptyStateModel() is pure; the rest only builds DOM.

const MODE_RUN = { statevector: 'a statevector run', measured: 'a measured run' };
const DETAIL_TABS = ['Summary', 'Agreement', 'Performance', 'Circuits', 'Exports'];
export const BACKEND_COLUMNS = ['Backend', 'Status', 'Differs from', 'Bit order', 'Precision', 'Total time (s)', 'Peak memory (MiB)'];
const MEASURED_BACKEND_COLUMNS = ['Backend', 'Status', 'Differs from', 'Inconclusive with', 'Bit order', 'Precision', 'Total time (s)', 'Peak memory (MiB)'];
const PLAYLIST_COLUMNS = ['Task', 'Status', 'Fastest (total time)', 'Lowest process peak RSS'];

const _plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;

function _table(caption, columns, items) {
    return {
        caption, columns,
        keys: items.map(item => item.key),
        rows: items.map(item => [item.name, ...columns.slice(1).map(() => '—')]),
    };
}

/**
 * What the results area shows before a run.
 * @param {{source: 'editor'|'list', circuitName: string, playlist: string[], modes: {statevector: boolean, measured: boolean},
 *          preprocessing: string, compilerCount: number, backends: {key: string, name: string}[], backendsLoaded: boolean,
 *          examples: {value: string, label: string}[]}} input
 *   `backends` are {key, name} in report order; `playlist` the playlist's item labels.
 */
export function emptyStateModel(input) {
    const modes = ['statevector', 'measured'].filter(m => input.modes[m]);
    const modeText = `as ${modes.map(m => MODE_RUN[m]).join(' and then as ')}`;
    const pause = modes.length > 1 ? ',' : '';
    const list = input.source === 'list';
    const what = list ? `the Playlist (${_plural(input.playlist.length, 'circuit')})` : (input.circuitName || 'the circuit in the editor');
    const n = input.backends.length;
    const base = { kicker: 'No results yet', examples: input.examples, docs: { href: 'docs.html#reading', label: 'How to read the results' } };

    if (!modes.length && !input.compilerCount) {
        return { ...base, tabs: [], title: 'Nothing to run yet', text: 'Tick Statevector or Measured under Mode, or a level under Compile-only services.', table: null };
    }
    if (!modes.length) {
        return {
            ...base, tabs: ['Summary', 'Circuits', 'Exports'], title: `Ready to compile ${what}`,
            text: `Run compiles it with ${_plural(input.compilerCount, 'ticked compile-only level')}; the compiled circuits appear in the Circuits tab. Nothing is simulated.`,
            table: null,
        };
    }
    if (!input.backendsLoaded) {
        return { ...base, tabs: list ? ['Suite Summary', 'Exports'] : DETAIL_TABS, title: `Ready to run ${what}`, text: 'Loading the backend list.', table: null };
    }
    if (!n) {
        return { ...base, tabs: [], title: 'No backend is ticked', text: 'Tick at least one backend under Backends.', table: null };
    }
    if (input.preprocessing === 'both') {
        return {
            ...base, tabs: [], title: `Ready to run an experiment on ${what}`,
            text: `Run Experiment runs it on ${_plural(n, 'backend')} ${modeText}, with SDK preprocessing on and then off; the results per setting and a downloadable bundle appear here.`,
            table: _table('Backends', BACKEND_COLUMNS, input.backends),
        };
    }
    if (list) {
        return {
            ...base, tabs: ['Suite Summary', 'Exports'], title: `Ready to run ${what}`,
            text: `Run sends each circuit to ${_plural(n, 'backend')} ${modeText}; each row of this table becomes one circuit's outcome, with its full report under Details.`,
            table: _table('Playlist', PLAYLIST_COLUMNS, input.playlist.map((name, i) => ({ key: String(i), name }))),
        };
    }
    const measuredOnly = modes.length === 1 && modes[0] === 'measured';
    return {
        ...base, tabs: DETAIL_TABS, title: `Ready to run ${what}`,
        text: `Run sends it to the ${_plural(n, 'backend')} below ${modeText}${pause} and compares every pair of outputs; the results fill this table.`,
        table: _table('Backends', measuredOnly ? MEASURED_BACKEND_COLUMNS : BACKEND_COLUMNS, input.backends),
    };
}

function _el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

/** A greyed copy of the result's tab strip; it does nothing until a result replaces it. */
export function greyTabs(labels) {
    const nav = _el('div', 'flex flex-wrap border-b border-gray-200');
    nav.setAttribute('aria-hidden', 'true');
    labels.forEach(label => nav.appendChild(_el('span', 'ml-4 px-3 py-3 font-medium text-sm border-b-2 border-transparent text-gray-300 select-none', label)));
    return nav;
}

/** The table of a model, styled like the Summary's Backends table. Each body row carries its
 * key as data-key; its second cell (Status) has the class qr-status-cell. */
export function placeholderTable(table) {
    const wrap = _el('div', 'overflow-x-auto mb-4 border rounded');
    const el = _el('table', 'min-w-full text-xs');
    el.appendChild(_el('caption', 'text-left text-xs font-semibold text-gray-700 px-2 py-1 bg-gray-50', table.caption));
    const head = _el('tr');
    table.columns.forEach(c => {
        const th = _el('th', 'px-2 py-1 text-left font-medium text-gray-600 whitespace-nowrap', c);
        th.scope = 'col';
        head.appendChild(th);
    });
    const thead = _el('thead');
    thead.appendChild(head);
    el.appendChild(thead);
    const tbody = _el('tbody');
    table.rows.forEach(([name, ...cells], i) => {
        const tr = _el('tr', 'border-t');
        if (table.keys) tr.dataset.key = table.keys[i];
        const th = _el('th', 'px-2 py-1 text-left font-medium text-gray-700 whitespace-nowrap', name);
        th.scope = 'row';
        tr.appendChild(th);
        cells.forEach((c, j) => tr.appendChild(_el('td', `px-2 py-1 text-gray-300 whitespace-nowrap${j === 0 ? ' qr-status-cell' : ''}`, c)));
        tbody.appendChild(tr);
    });
    el.appendChild(tbody);
    wrap.appendChild(el);
    return wrap;
}

/** Replace `container`'s content with the model; `onExample(value)` opens an example circuit. */
export function renderEmptyState(container, model, { onExample }) {
    if (!container) return;
    const parts = [];
    if (model.tabs.length) parts.push(greyTabs(model.tabs));

    const body = _el('div', 'p-4');
    body.appendChild(_el('p', 'text-xs font-medium uppercase tracking-wide text-gray-400', model.kicker));
    body.appendChild(_el('h2', 'text-xl font-semibold text-gray-900 mt-1', model.title));
    body.appendChild(_el('p', 'text-sm text-gray-600 mt-1 mb-4', model.text));
    if (model.table) body.appendChild(placeholderTable(model.table));

    const more = _el('p', 'text-xs text-gray-600 flex flex-wrap items-center gap-x-3 gap-y-1');
    if (model.examples.length) {
        more.appendChild(_el('span', 'text-gray-500', 'Examples:'));
        model.examples.forEach(ex => {
            const button = _el('button', 'text-indigo-700 underline hover:text-indigo-900', ex.label);
            button.type = 'button';
            button.title = 'Load into the editor';
            button.addEventListener('click', () => onExample(ex.value));
            more.appendChild(button);
        });
    }
    const docs = /** @type {HTMLAnchorElement} */ (_el('a', 'text-indigo-700 underline hover:text-indigo-900', model.docs.label));
    docs.href = model.docs.href;
    docs.target = '_blank';
    docs.rel = 'noopener';
    more.appendChild(docs);
    body.appendChild(more);

    parts.push(body);
    container.replaceChildren(...parts);
}
