// Validation of the run inputs (shots, timeout, timing repeats, seed, agreement thresholds) against the
// server limits, with inline error messages. A run is not submitted while any input is invalid.

import { getState } from './state.js';
import { THRESHOLD_INPUT_IDS } from './utils.js';

const THRESHOLD_LABELS = {
    fidelity_tolerance: 'Statevector fidelity tolerance',
    phase_tolerance: 'Statevector phase tolerance',
    js_threshold: 'Measured JS threshold',
    hellinger_threshold: 'Measured Hellinger threshold',
    norm_tolerance: 'Statevector norm tolerance',
};

const TIMING_REPEATS_MIN = 1;
const TIMING_REPEATS_MAX = 10;

const INVALID_CLASSES = ['border-red-500', 'ring-1', 'ring-red-500'];

function _input(id) {
    return /** @type {HTMLInputElement|null} */ (document.getElementById(id));
}

function _setFieldError(el, message) {
    if (!el) return;
    const holder = el.parentElement;
    let note = holder ? holder.querySelector(`.field-error[data-for="${el.id}"]`) : null;
    if (!message) {
        el.removeAttribute('aria-invalid');
        INVALID_CLASSES.forEach(c => el.classList.remove(c));
        if (note) note.remove();
        return;
    }
    el.setAttribute('aria-invalid', 'true');
    INVALID_CLASSES.forEach(c => el.classList.add(c));
    if (!note && holder) {
        note = document.createElement('p');
        note.className = 'field-error text-xs text-red-600 mt-1';
        note.dataset.for = el.id;
        el.insertAdjacentElement('afterend', note);
    }
    if (note) note.textContent = message;
}

function _integerIn(raw, min, max) {
    const text = String(raw).trim();
    if (text === '' || !/^-?\d+$/.test(text)) return null;
    const n = Number(text);
    if (!Number.isSafeInteger(n)) return null;
    if (min !== null && min !== undefined && n < min) return null;
    if (max !== null && max !== undefined && n > max) return null;
    return n;
}

function _rangeText(min, max) {
    if (max === null || max === undefined) return `an integer ≥ ${min}`;
    return `an integer from ${min} to ${max}`;
}

/** Timeout range the server accepts: GET /config limits, else 10–300 s. */
export function timeoutRange() {
    const st = getState();
    return { min: st.timeoutMin, max: st.timeoutMax };
}

/** Shots range the server accepts: GET /config limits, else ≥ 1. */
export function shotsRange() {
    const st = getState();
    return { min: st.shotsMin, max: st.shotsMax };
}

/**
 * Check the inputs a run sends. Marks invalid fields inline and returns the errors.
 * @param {{ shotsId?: string, measured?: boolean }} opts
 * @returns {{ ok: boolean, errors: string[], shots: number|null, timeout: number|null, timingRepeats: number|null }}
 */
export function validateRunInputs({ shotsId, measured = false } = {}) {
    const errors = [];

    let shots = null;
    if (shotsId) {
        const el = _input(shotsId);
        if (measured && el) {
            const { min, max } = shotsRange();
            shots = _integerIn(el.value, min, max);
            const msg = shots === null ? `Shots must be ${_rangeText(min, max)}.` : null;
            _setFieldError(el, msg);
            if (msg) errors.push(msg);
        } else {
            _setFieldError(el, null);
        }
    }

    let timeout = null;
    const tEl = _input('timeout-input');
    if (tEl) {
        const { min, max } = timeoutRange();
        timeout = _integerIn(tEl.value, min, max);
        const msg = timeout === null ? `Timeout must be ${_rangeText(min, max)} seconds.` : null;
        _setFieldError(tEl, msg);
        if (msg) errors.push(`Config → ${msg}`);
    }

    let timingRepeats = 1;
    const rEl = _input('timing-repeats-input');
    if (rEl) {
        timingRepeats = _integerIn(rEl.value, TIMING_REPEATS_MIN, TIMING_REPEATS_MAX);
        const msg = timingRepeats === null
            ? `Timing repeats must be ${_rangeText(TIMING_REPEATS_MIN, TIMING_REPEATS_MAX)}.` : null;
        _setFieldError(rEl, msg);
        if (msg) errors.push(`Config → ${msg}`);
    }

    const seedEl = _input('seed-input');
    if (seedEl) {
        const raw = String(seedEl.value).trim();
        const msg = raw !== '' && _integerIn(raw, 0, null) === null
            ? 'Seed must be empty or a non-negative integer.' : null;
        _setFieldError(seedEl, measured ? msg : null);
        if (measured && msg) errors.push(`Config → ${msg}`);
    }

    for (const [key, id] of Object.entries(THRESHOLD_INPUT_IDS)) {
        const el = _input(id);
        if (!el) continue;
        const raw = String(el.value).trim();
        const v = Number(raw);
        const msg = (raw === '' || !Number.isFinite(v) || v < 0)
            ? `${THRESHOLD_LABELS[key]} must be a number ≥ 0.` : null;
        _setFieldError(el, msg);
        if (msg) errors.push(`Config → Agreement thresholds → ${msg}`);
    }

    return { ok: errors.length === 0, errors, shots, timeout, timingRepeats };
}

/** Show (or clear, with an empty list) the validation errors next to a run button. */
export function showRunErrors(targetId, errors) {
    const box = document.getElementById(targetId);
    if (!box) return;
    box.innerHTML = '';
    if (!errors || errors.length === 0) {
        box.classList.add('hidden');
        return;
    }
    const head = document.createElement('p');
    head.className = 'font-semibold';
    head.textContent = 'Not submitted. Fix these inputs first:';
    box.appendChild(head);
    const ul = document.createElement('ul');
    ul.className = 'list-disc ml-5';
    errors.forEach(e => {
        const li = document.createElement('li');
        li.textContent = e;
        ul.appendChild(li);
    });
    box.appendChild(ul);
    box.classList.remove('hidden');
}
