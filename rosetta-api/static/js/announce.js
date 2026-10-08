// Screen-reader announcements through the page's polite live region (#sr-announcer). Leaf module.

let _timer = null;

/** Announce `text` politely; an identical repeat is still read. */
export function announce(text) {
    const region = document.getElementById('sr-announcer');
    if (!region || !text) return;
    clearTimeout(_timer);
    region.textContent = '';
    _timer = setTimeout(() => { region.textContent = String(text); }, 100);
}

/** The first sentence of `text` (up to the first ". " or the end). */
export function firstSentence(text) {
    const s = String(text || '').trim();
    const m = s.match(/^.*?[.!?](?=\s|$)/s);
    return m ? m[0] : s;
}

/** Focus `el` without scrolling the page when it is already in view; makes it focusable by script if needed. */
export function focusHeading(el) {
    if (!(el instanceof HTMLElement)) return false;
    if (!el.hasAttribute('tabindex')) el.tabIndex = -1;
    el.focus({ preventScroll: true });
    return document.activeElement === el;
}

/** True when focus is nowhere in particular (on <body>), or on `el`. */
export function focusIsLost(el = null) {
    const a = document.activeElement;
    return !a || a === document.body || a === document.documentElement || (el !== null && a === el);
}
