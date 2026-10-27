// Bidirectional isolation of displayed text. A text node that holds an explicit bidi formatting
// character (embeddings, overrides, isolates, marks) or a right-to-left letter is moved into a
// <bdi> element, so its direction cannot reorder the text around it; its characters and its
// own order are unchanged. watchBidi runs over a root once and then on every change below it,
// which covers runner errors, preprocessing notes, SDK versions, compiler refusals, run and
// circuit names and uploaded reports whichever renderer shows them. Leaf module: no imports.

const BIDI = /[؜‎‏‪-‮⁦-⁩֐-ࣿיִ-﷿ﹰ-ﻼ\u{10800}-\u{10FFF}\u{1E800}-\u{1EFFF}]/u;
const XHTML = 'http://www.w3.org/1999/xhtml';
const SKIP = new Set(['BDI', 'SCRIPT', 'STYLE', 'TEXTAREA', 'OPTION', 'TITLE', 'TEMPLATE']);

/** True when `text` holds a character whose direction can reorder neighbouring text. */
export function needsIsolation(text) {
    return typeof text === 'string' && BIDI.test(text);
}

/** @param {Text} node */
function _wrap(node) {
    const parent = node.parentElement;
    if (!parent || parent.namespaceURI !== XHTML || SKIP.has(parent.tagName) || parent.closest('bdi')) return;
    const bdi = document.createElement('bdi');
    parent.insertBefore(bdi, node);
    bdi.appendChild(node);
}

/** Isolate every text node at or below `root` that needs it. @param {Node} root */
export function isolateBidi(root) {
    if (root.nodeType === Node.TEXT_NODE) {
        if (needsIsolation(/** @type {Text} */ (root).data)) _wrap(/** @type {Text} */ (root));
        return;
    }
    if (root.nodeType !== Node.ELEMENT_NODE && root.nodeType !== Node.DOCUMENT_FRAGMENT_NODE) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
        acceptNode: n => (needsIsolation(/** @type {Text} */ (n).data) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT),
    });
    const found = [];
    while (walker.nextNode()) found.push(/** @type {Text} */ (walker.currentNode));
    found.forEach(_wrap);
}

/** Isolate the text below `root` now and whenever it changes. @param {Node} root */
export function watchBidi(root) {
    isolateBidi(root);
    new MutationObserver(records => {
        for (const r of records) {
            if (r.type === 'characterData') isolateBidi(r.target);
            else r.addedNodes.forEach(isolateBidi);
        }
    }).observe(root, { subtree: true, childList: true, characterData: true });
}
