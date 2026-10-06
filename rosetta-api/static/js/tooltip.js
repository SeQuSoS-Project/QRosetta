// One shared tooltip for elements with a data-tip attribute: shown on hover, keyboard focus
// or tap, hidden on leave, blur, a tap elsewhere or Escape. Leaf module: no imports.

let _tip = null;
let _owner = null;

function _ensureTip() {
    if (_tip) return _tip;
    _tip = document.createElement('div');
    _tip.id = 'shared-tooltip';
    _tip.setAttribute('role', 'tooltip');
    _tip.className = 'hidden fixed z-[60] max-w-sm px-3 py-2 text-xs leading-snug text-white bg-gray-900 rounded shadow-lg pointer-events-none';
    document.body.appendChild(_tip);
    return _tip;
}

function _show(el) {
    const text = el.getAttribute('data-tip');
    if (!text) return;
    const tip = _ensureTip();
    tip.textContent = text;
    tip.classList.remove('hidden');
    _owner = el;
    el.setAttribute('aria-describedby', 'shared-tooltip');
    const r = el.getBoundingClientRect();
    const t = tip.getBoundingClientRect();
    const left = Math.max(8, Math.min(r.left, window.innerWidth - t.width - 8));
    const below = r.bottom + 6 + t.height < window.innerHeight;
    tip.style.left = `${left}px`;
    tip.style.top = `${below ? r.bottom + 6 : Math.max(8, r.top - t.height - 6)}px`;
}

function _hide() {
    if (_tip) _tip.classList.add('hidden');
    if (_owner) _owner.removeAttribute('aria-describedby');
    _owner = null;
}

const _target = e => (e.target instanceof Element ? e.target.closest('[data-tip]') : null);

/** Make `el` show `text` in the shared tooltip, and reachable by keyboard. */
export function setTip(el, text) {
    if (!text) return el;
    el.setAttribute('data-tip', text);
    if (!el.matches('a, button, input, select, textarea, summary') && !el.hasAttribute('tabindex')) el.tabIndex = 0;
    return el;
}

export function initTooltips() {
    document.addEventListener('mouseover', e => { const el = _target(e); if (el && el !== _owner) _show(el); });
    document.addEventListener('mouseout', e => { const el = _target(e); if (el && el === _owner && !el.contains(/** @type {Node} */ (e.relatedTarget))) _hide(); });
    document.addEventListener('focusin', e => { const el = _target(e); if (el) _show(el); });
    document.addEventListener('focusout', e => { if (_target(e) === _owner) _hide(); });
    document.addEventListener('click', e => {
        const el = _target(e);
        if (!el) { _hide(); return; }
        if (el === _owner && /** @type {PointerEvent} */ (e).pointerType !== 'mouse') _hide(); else _show(el);
    });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') _hide(); });
    window.addEventListener('scroll', _hide, true);
}
