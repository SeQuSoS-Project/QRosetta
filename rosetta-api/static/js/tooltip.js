// One shared tooltip for elements with a data-tip attribute: shown on hover, keyboard focus or
// tap, and kept while the pointer is on the element or on the tooltip itself; hidden when the
// pointer leaves both, on blur, a tap elsewhere or Escape. Non-interactive elements with a tip
// share one Tab stop per row (tr, li or [data-tip-group]); Left/Right, Home and End move between
// them. Leaf module: no imports.

let _tip = null;
let _owner = null;
let _hideTimer = null;

const GROUP = 'tr, li, [data-tip-group]';

function _ensureTip() {
    if (_tip) return _tip;
    _tip = document.createElement('div');
    _tip.id = 'shared-tooltip';
    _tip.setAttribute('role', 'tooltip');
    _tip.className = 'hidden fixed z-[60] max-w-sm px-3 py-2 text-xs leading-snug text-white bg-gray-900 rounded shadow-lg';
    _tip.addEventListener('mouseenter', () => clearTimeout(_hideTimer));
    _tip.addEventListener('mouseleave', e => { if (!_owner?.contains(/** @type {Node} */ (e.relatedTarget))) _hideSoon(); });
    document.body.appendChild(_tip);
    return _tip;
}

/** The tip elements that share `el`'s Tab stop, in document order. */
function _rowOf(el) {
    const group = el.closest(GROUP) || el.parentElement;
    if (!group) return [el];
    return /** @type {HTMLElement[]} */ (Array.from(group.querySelectorAll('[data-tip-roving]')))
        .filter(x => (x.closest(GROUP) || x.parentElement) === group);
}

function _show(el, { keyboard = false } = {}) {
    const text = el.getAttribute('data-tip');
    if (!text) return;
    clearTimeout(_hideTimer);
    const tip = _ensureTip();
    tip.textContent = text;
    if (keyboard && el.hasAttribute('data-tip-roving') && _rowOf(el).length > 1) {
        const hint = document.createElement('span');
        hint.className = 'block mt-1 text-gray-200';
        hint.textContent = 'Left and Right arrows: the other notes in this row.';
        tip.appendChild(hint);
    }
    tip.classList.remove('hidden');
    if (_owner && _owner !== el) _owner.removeAttribute('aria-describedby');
    _owner = el;
    el.setAttribute('aria-describedby', 'shared-tooltip');
    const r = el.getBoundingClientRect();
    const t = tip.getBoundingClientRect();
    const left = Math.max(8, Math.min(r.left, window.innerWidth - t.width - 8));
    const below = r.bottom + 4 + t.height < window.innerHeight;
    tip.style.left = `${left}px`;
    tip.style.top = `${below ? r.bottom + 4 : Math.max(8, r.top - t.height - 4)}px`;
}

function _hide() {
    clearTimeout(_hideTimer);
    if (_tip) _tip.classList.add('hidden');
    if (_owner) _owner.removeAttribute('aria-describedby');
    _owner = null;
}

function _hideSoon() {
    clearTimeout(_hideTimer);
    _hideTimer = setTimeout(_hide, 150);
}

const _target = e => (e.target instanceof Element ? e.target.closest('[data-tip]') : null);

/** Make `el` show `text` in the shared tooltip, and reachable by keyboard. */
export function setTip(el, text) {
    if (!text) return el;
    el.setAttribute('data-tip', text);
    if (!el.matches('a, button, input, select, textarea, summary') && !el.hasAttribute('tabindex')) {
        el.setAttribute('data-tip-roving', '');
        el.tabIndex = 0;
    }
    return el;
}

/** Give each row of tip elements one Tab stop: the first, or the one focused last. */
export function settleTipStops(root = document) {
    const seen = new Set();
    root.querySelectorAll('[data-tip-roving]').forEach(el => {
        const row = _rowOf(/** @type {HTMLElement} */ (el));
        const key = row[0];
        if (seen.has(key)) return;
        seen.add(key);
        const current = row.find(x => x.hasAttribute('data-tip-current')) || row[0];
        row.forEach(x => { x.tabIndex = x === current ? 0 : -1; });
    });
}

function _onRowKey(e) {
    const el = e.target instanceof HTMLElement && e.target.hasAttribute('data-tip-roving') ? e.target : null;
    if (!el) return;
    const row = _rowOf(el);
    const i = row.indexOf(el);
    const next = e.key === 'ArrowRight' ? row[i + 1] : e.key === 'ArrowLeft' ? row[i - 1]
        : e.key === 'Home' ? row[0] : e.key === 'End' ? row[row.length - 1] : null;
    if (!next || next === el) return;
    e.preventDefault();
    next.focus();
}

export function initTooltips() {
    document.addEventListener('mouseover', e => { const el = _target(e); if (el && el !== _owner) _show(el); else if (el) clearTimeout(_hideTimer); });
    document.addEventListener('mouseout', e => {
        const el = _target(e);
        const to = /** @type {Node} */ (e.relatedTarget);
        if (el && el === _owner && !el.contains(to) && !(_tip && _tip.contains(to))) _hideSoon();
    });
    document.addEventListener('focusin', e => {
        const el = _target(e);
        if (!el) return;
        if (el.hasAttribute('data-tip-roving')) {
            _rowOf(el).forEach(x => { x.tabIndex = x === el ? 0 : -1; x.toggleAttribute('data-tip-current', x === el); });
        }
        _show(el, { keyboard: true });
    });
    document.addEventListener('focusout', e => { if (_target(e) === _owner) _hide(); });
    document.addEventListener('click', e => {
        if (_tip && e.target instanceof Node && _tip.contains(e.target)) return;
        const el = _target(e);
        if (!el) { _hide(); return; }
        if (el === _owner && /** @type {PointerEvent} */ (e).pointerType !== 'mouse') _hide(); else _show(el);
    });
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') _hide();
        else _onRowKey(e);
    });
    window.addEventListener('scroll', e => { if (!(_tip && e.target instanceof Node && _tip.contains(e.target))) _hide(); }, true);
    let pending = false;
    new MutationObserver(() => {
        if (pending) return;
        pending = true;
        requestAnimationFrame(() => { pending = false; settleTipStops(); });
    }).observe(document.body, { childList: true, subtree: true });
}
