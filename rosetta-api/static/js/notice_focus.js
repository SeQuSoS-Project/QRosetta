// Keeps the focused control clear of the page's fixed notices (busy toast, history-save notice):
// when focus lands on an element a shown notice overlaps, the element is scrolled to the middle
// of its scroll containers. Leaf module: no imports.

/** @param {DOMRect} a @param {DOMRect} b */
function _overlap(a, b) {
    return a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
}

/** Watch focus for the notices with these element ids. @param {string[]} ids */
export function keepFocusClearOf(ids) {
    document.addEventListener('focusin', e => {
        const target = e.target;
        if (!(target instanceof HTMLElement)) return;
        const box = target.getBoundingClientRect();
        const covered = ids.some(id => {
            const notice = document.getElementById(id);
            return notice && !notice.classList.contains('hidden') && !notice.contains(target) && _overlap(box, notice.getBoundingClientRect());
        });
        if (covered) target.scrollIntoView({ block: 'center', inline: 'nearest' });
    });
}
