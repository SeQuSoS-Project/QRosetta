// Non-modal popovers anchored to a button: the button toggles the panel and reports it in
// aria-expanded; Escape or a click outside closes it and returns focus to the button. One
// popover is open at a time. The panel is placed in the window, below the button when it fits
// there and above it otherwise. Leaf module: no imports.

let _open = null;

function _close(restoreFocus) {
    if (!_open) return;
    const { button, panel } = _open;
    panel.classList.add('hidden');
    button.setAttribute('aria-expanded', 'false');
    _open = null;
    if (restoreFocus) button.focus();
}

/** Fixed position next to `button`, inside the window. */
function _place(button, panel) {
    const gap = 6, margin = 8;
    const b = button.getBoundingClientRect();
    panel.style.position = 'fixed';
    panel.style.zIndex = '60';
    panel.style.maxHeight = `${window.innerHeight - 2 * margin}px`;
    panel.style.overflowY = 'auto';
    const p = panel.getBoundingClientRect();
    const below = b.bottom + gap + p.height <= window.innerHeight - margin;
    const top = below ? b.bottom + gap : Math.max(margin, b.top - gap - p.height);
    const left = Math.min(Math.max(margin, b.right - p.width), window.innerWidth - p.width - margin);
    panel.style.top = `${top}px`;
    panel.style.left = `${left}px`;
}

/** Close whichever popover is open. */
export function closePopover(restoreFocus = false) {
    _close(restoreFocus);
}

/**
 * Wire `button` to toggle `panel`. `onOpen` runs each time it opens; `focusSelector` names the
 * element inside the panel that takes focus on opening.
 */
export function bindPopover(button, panel, { onOpen = null, focusSelector = null } = {}) {
    button.setAttribute('aria-expanded', 'false');
    button.setAttribute('aria-controls', panel.id);
    button.addEventListener('click', () => {
        if (_open && _open.panel === panel) { _close(false); return; }
        _close(false);
        panel.classList.remove('hidden');
        button.setAttribute('aria-expanded', 'true');
        _open = { button, panel };
        _place(button, panel);
        Promise.resolve(onOpen ? onOpen() : null).then(() => { if (_open && _open.panel === panel) _place(button, panel); });
        const target = focusSelector ? panel.querySelector(focusSelector) : null;
        if (target instanceof HTMLElement) target.focus();
    });
}

document.addEventListener('mousedown', e => {
    if (!_open || !(e.target instanceof Node)) return;
    if (_open.panel.contains(e.target) || _open.button.contains(e.target)) return;
    _close(false);
});
document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && _open) _close(true);
});
window.addEventListener('resize', () => { if (_open) _place(_open.button, _open.panel); });
document.addEventListener('scroll', e => {
    if (_open && !(e.target instanceof Node && _open.panel.contains(e.target))) _place(_open.button, _open.panel);
}, true);
