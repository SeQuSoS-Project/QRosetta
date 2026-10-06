// Searchable picker for the Quantum Algorithms menu (WAI-ARIA combobox with a grouped listbox).
// The options live in a hidden <select>; the picker filters them as the user types and sets the
// select's value, firing its change event, so code that reads the select keeps working. Enter
// picks the highlighted option, or the first match when none is highlighted.
// Leaf module: no imports.

/**
 * @param {{ input: HTMLInputElement, listbox: HTMLElement, select: HTMLSelectElement }} parts
 */
export function initCircuitPicker({ input, listbox, select }) {
    let active = -1;
    let shown = [];

    const labelOf = value => {
        const option = Array.from(select.options).find(o => o.value === value);
        return option ? option.textContent : '';
    };
    const syncInput = () => { input.value = labelOf(select.value); };

    const close = () => {
        listbox.classList.add('hidden');
        input.setAttribute('aria-expanded', 'false');
        input.removeAttribute('aria-activedescendant');
        active = -1;
    };

    const highlight = index => {
        shown.forEach((el, i) => {
            const on = i === index;
            el.setAttribute('aria-selected', String(on));
            el.classList.toggle('bg-indigo-100', on);
        });
        active = index;
        if (index >= 0 && shown[index]) {
            input.setAttribute('aria-activedescendant', shown[index].id);
            shown[index].scrollIntoView({ block: 'nearest' });
        } else {
            input.removeAttribute('aria-activedescendant');
        }
    };

    const choose = value => {
        if (value !== select.value) {
            select.value = value;
            select.dispatchEvent(new Event('change'));
        }
        syncInput();
        close();
    };

    const render = filter => {
        const q = filter.trim().toLowerCase();
        listbox.replaceChildren();
        shown = [];
        Array.from(select.children).forEach((group, gi) => {
            if (!(group instanceof HTMLOptGroupElement)) return;
            const matches = Array.from(group.children).filter(o => !q || o.textContent.toLowerCase().includes(q)
                || group.label.toLowerCase().includes(q));
            if (!matches.length) return;
            const box = document.createElement('div');
            box.setAttribute('role', 'group');
            box.setAttribute('aria-labelledby', `picker-group-${gi}`);
            const head = document.createElement('div');
            head.id = `picker-group-${gi}`;
            head.className = 'px-3 pt-2 pb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-500';
            head.textContent = group.label;
            box.appendChild(head);
            matches.forEach(o => {
                const item = document.createElement('div');
                item.id = `picker-opt-${shown.length}`;
                item.setAttribute('role', 'option');
                item.setAttribute('aria-selected', 'false');
                item.dataset.value = /** @type {HTMLOptionElement} */ (o).value;
                item.className = 'px-3 py-1.5 text-sm cursor-pointer hover:bg-indigo-50'
                    + (/** @type {HTMLOptionElement} */ (o).value === select.value ? ' font-semibold' : '');
                item.textContent = o.textContent;
                item.addEventListener('mousedown', e => { e.preventDefault(); choose(item.dataset.value); });
                box.appendChild(item);
                shown.push(item);
            });
            listbox.appendChild(box);
        });
        if (!shown.length) {
            const none = document.createElement('div');
            none.className = 'px-3 py-2 text-sm text-gray-500';
            none.textContent = 'No circuit matches.';
            listbox.appendChild(none);
        }
    };

    const open = filter => {
        render(filter);
        listbox.classList.remove('hidden');
        input.setAttribute('aria-expanded', 'true');
        highlight(filter ? -1 : shown.findIndex(el => el.dataset.value === select.value));
    };

    input.addEventListener('focus', () => input.select());
    input.addEventListener('click', () => { input.select(); open(''); });
    input.addEventListener('input', () => open(input.value));
    input.addEventListener('blur', () => { close(); syncInput(); });
    input.addEventListener('keydown', e => {
        const isOpen = input.getAttribute('aria-expanded') === 'true';
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (!isOpen) open(''); else highlight(Math.min(active + 1, shown.length - 1));
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (isOpen) highlight(Math.max(active - 1, 0));
        } else if (e.key === 'Enter') {
            const pick = active >= 0 ? shown[active] : (input.value.trim() ? shown[0] : null);
            if (isOpen && pick) { e.preventDefault(); choose(pick.dataset.value); }
        } else if (e.key === 'Escape') {
            if (isOpen) { e.preventDefault(); close(); syncInput(); }
        }
    });
    select.addEventListener('change', syncInput);
    syncInput();
    return { refresh: syncInput };
}
