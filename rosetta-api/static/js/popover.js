// Non-modal popovers anchored to a button. The button toggles the panel and reports it in
// aria-expanded; Escape or a click outside closes it and returns focus to the button; one
// popover is open at a time. A panel follows the .qr-popover anatomy (header, scrolling body;
// see css/tailwind.src.css). It opens on the side of the button with more room, its height is
// capped at that room, and it is placed again whenever its content, the window or a scroll
// position changes, so content that grows while it is open stays reachable. Leaf module.

const GAP = 6;
const MARGIN = 8;
const MIN_ROOM = 160;

let _open = null;

const _watcher = new MutationObserver(() => { if (_open) _place(_open.button, _open.panel); });

function _close(restoreFocus) {
    if (!_open) return;
    const { button, panel } = _open;
    _watcher.disconnect();
    panel.classList.add('hidden');
    button.setAttribute('aria-expanded', 'false');
    _open = null;
    if (restoreFocus) button.focus();
}

/** Place `panel` beside `button`: below when its content fits there, else on the roomier side,
 * with its height capped at that side's room. */
function _place(button, panel) {
    const b = button.getBoundingClientRect();
    const roomBelow = window.innerHeight - b.bottom - GAP - MARGIN;
    const roomAbove = b.top - GAP - MARGIN;
    panel.style.position = 'fixed';
    panel.style.zIndex = '60';
    panel.style.maxHeight = 'none';
    const natural = panel.getBoundingClientRect().height;
    const below = natural <= roomBelow || roomBelow >= roomAbove;
    const room = Math.max(MIN_ROOM, below ? roomBelow : roomAbove);
    const height = Math.min(natural, room);
    panel.style.maxHeight = `${room}px`;
    panel.style.top = `${below ? b.bottom + GAP : Math.max(MARGIN, b.top - GAP - height)}px`;
    const width = panel.getBoundingClientRect().width;
    panel.style.left = `${Math.min(Math.max(MARGIN, b.right - width), window.innerWidth - width - MARGIN)}px`;
}

/** Close whichever popover is open. */
export function closePopover(restoreFocus = false) {
    _close(restoreFocus);
}

/**
 * Wire `button` to toggle `panel`. `onOpen` runs each time it opens (it may return a promise);
 * `focusSelector` names the element inside the panel that takes focus on opening.
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
        _watcher.observe(panel, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['class', 'hidden'] });
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
