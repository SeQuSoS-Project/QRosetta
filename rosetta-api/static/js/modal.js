// Modal dialogs: focus moves into the dialog on open, Tab and Shift+Tab stay inside it, Escape
// closes it, the rest of the page is inert while it is open, and focus returns to the control
// that opened it. Leaf module: no imports.

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), '
    + 'textarea:not([disabled]), iframe, summary, [tabindex]:not([tabindex="-1"])';

/** @type {{ dialog: HTMLElement, opener: Element|null, onEscape: () => void, inerted: Element[], sentinels: HTMLElement[] }[]} */
const _stack = [];

function _visible(el) {
    return el instanceof HTMLElement && el.isConnected && el.getClientRects().length > 0 && !el.closest('[inert], .hidden');
}

/** The focusable elements of `dialog` in document order, without the trap's own sentinels. */
export function focusableIn(dialog) {
    return /** @type {HTMLElement[]} */ (Array.from(dialog.querySelectorAll(FOCUSABLE)))
        .filter(el => !el.hasAttribute('data-modal-sentinel') && _visible(el));
}

function _sentinel(onFocus) {
    const s = document.createElement('span');
    s.tabIndex = 0;
    s.setAttribute('data-modal-sentinel', '');
    s.setAttribute('aria-hidden', 'true');
    s.className = 'sr-only';
    s.addEventListener('focus', onFocus);
    return s;
}

/** The dialog that is open on top, or null. */
export function topModal() {
    return _stack.length ? _stack[_stack.length - 1].dialog : null;
}

/**
 * Open `dialog` as a modal. `initialFocus` is the element (or selector inside the dialog) to
 * focus first, else the first focusable element; `onEscape` runs on Escape (normally the
 * dialog's own close function, which calls closeModal).
 * @param {HTMLElement} dialog
 * @param {{ initialFocus?: string|HTMLElement|null, onEscape?: () => void }} [options]
 */
export function openModal(dialog, { initialFocus = null, onEscape = () => closeModal(dialog) } = {}) {
    if (!dialog) return;
    const existing = _stack.find(m => m.dialog === dialog);
    if (existing) {
        existing.onEscape = onEscape;
        focusInto(dialog, initialFocus);
        return;
    }
    const opener = document.activeElement && document.activeElement !== document.body ? document.activeElement : null;
    const inerted = [];
    Array.from(document.body.children).forEach(el => {
        if (el === dialog || el.contains(dialog) || el.tagName === 'SCRIPT' || el.tagName === 'TEMPLATE' || el.hasAttribute('inert')) return;
        if (el.hasAttribute('data-modal-keep') || el.id === 'shared-tooltip') return;
        el.setAttribute('inert', '');
        inerted.push(el);
    });
    const entry = { dialog, opener, onEscape, inerted, sentinels: [] };
    entry.sentinels = [
        _sentinel(() => { const f = focusableIn(dialog); (f[f.length - 1] || dialog).focus(); }),
        _sentinel(() => { const f = focusableIn(dialog); (f[0] || dialog).focus(); }),
    ];
    dialog.prepend(entry.sentinels[0]);
    dialog.append(entry.sentinels[1]);
    if (!dialog.hasAttribute('tabindex')) dialog.tabIndex = -1;
    _stack.push(entry);
    dialog.classList.remove('hidden');
    focusInto(dialog, initialFocus);
}

/** Move focus into the open `dialog`: to `target` (element or selector) when it can take focus, else the first focusable element. */
export function focusInto(dialog, target = null) {
    const el = typeof target === 'string' ? dialog.querySelector(target) : target;
    const first = el instanceof HTMLElement && _visible(el) ? el : focusableIn(dialog)[0];
    (first || dialog).focus();
}

/**
 * Close the modal `dialog` and return focus to the control that opened it, or to `returnFocus`
 * (element or selector) when given or when the opener is gone or hidden.
 * @param {HTMLElement} dialog
 * @param {{ returnFocus?: string|HTMLElement|null }} [options]
 */
export function closeModal(dialog, { returnFocus = null } = {}) {
    if (!dialog) return;
    dialog.classList.add('hidden');
    const i = _stack.findIndex(m => m.dialog === dialog);
    if (i < 0) return;
    const [entry] = _stack.splice(i, 1);
    entry.inerted.forEach(el => el.removeAttribute('inert'));
    entry.sentinels.forEach(s => s.remove());
    const wanted = typeof returnFocus === 'string' ? document.querySelector(returnFocus) : returnFocus;
    const target = [wanted, entry.opener].find(_visible);
    if (target instanceof HTMLElement) target.focus();
}

/** True when `dialog` is open as a modal. */
export function isModalOpen(dialog) {
    return _stack.some(m => m.dialog === dialog);
}

document.addEventListener('keydown', e => {
    const top = _stack[_stack.length - 1];
    if (!top) return;
    if (e.key === 'Escape') {
        e.preventDefault();
        e.stopImmediatePropagation();
        top.onEscape();
        return;
    }
    if (e.key !== 'Tab') return;
    const f = focusableIn(top.dialog);
    if (!f.length) { e.preventDefault(); top.dialog.focus(); return; }
    const active = document.activeElement;
    if (!top.dialog.contains(active)) { e.preventDefault(); f[0].focus(); return; }
    if (e.shiftKey && (active === f[0] || active === top.dialog)) { e.preventDefault(); f[f.length - 1].focus(); }
    else if (!e.shiftKey && active === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
}, true);
