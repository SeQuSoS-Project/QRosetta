// The settings chips in the Run footer: one chip per settings group (Backends, Execution,
// Circuit Preprocessing, Compile-only services, Agreement Thresholds, Sampling seed). Each chip
// shows the group's current value, is highlighted when it differs from the default, and opens
// the group's controls in a popover.

import { getCompilerSelection } from './compilers_config.js';
import { _multiRunEnabled, _orderingEnabled, getEnabledRunnerIds, getTargetSimulators } from './config.js';
import { bindPopover } from './popover.js';
import { THRESHOLD_INPUT_IDS, thresholdDefaults } from './utils.js';

const PLAIN = ['bg-white', 'text-gray-700', 'border-gray-300', 'hover:bg-gray-50'];
const CHANGED = ['bg-indigo-600', 'text-white', 'border-indigo-600', 'hover:bg-indigo-700'];

const _el = id => /** @type {HTMLInputElement|null} */ (document.getElementById(id));

/** [text, changed] per chip, from the current settings.
 * @returns {Record<string, [string, boolean]>} */
function _summaries() {
    const enabled = getEnabledRunnerIds().length;
    const selected = getTargetSimulators().length;
    const level = /** @type {HTMLSelectElement|null} */ (document.getElementById('opt-global'))?.value || '0';
    const backendParts = [`Backends: ${enabled ? `${selected}${selected === enabled ? '' : ` of ${enabled}`}` : 'loading'}`, `Global Opt ${level}`];
    if (_multiRunEnabled) backendParts.push('multi-run');
    if (_orderingEnabled) backendParts.push('custom order');

    const timeout = _el('timeout-input');
    const repeats = parseInt(_el('timing-repeats-input')?.value || '1', 10);
    const exclusive = !!_el('exclusive-checkbox')?.checked;
    const executionParts = [`Execution: ${timeout?.value || '—'} s`, `${repeats} repeat${repeats === 1 ? '' : 's'}`];
    if (exclusive) executionParts.push('exclusive');
    const autosave = !!_el('autosave-toggle')?.checked;
    if (autosave) executionParts.push('auto-save');

    const pre = /** @type {HTMLInputElement|null} */ (document.querySelector('input[name="preprocessing"]:checked'))?.value || 'on';
    const bypass = !!_el('bypass-limits-checkbox')?.checked;
    const preText = `SDK Preprocessing: ${{ on: 'On', off: 'Off', both: 'Both' }[pre] || pre}${bypass ? ' · limits bypassed' : ''}`;

    const levels = Object.values(getCompilerSelection()).reduce((n, l) => n + l.length, 0);

    const defaults = thresholdDefaults();
    const thresholdsChanged = Object.entries(THRESHOLD_INPUT_IDS).some(([key, id]) => {
        const raw = String(_el(id)?.value ?? '').trim();
        return raw !== '' && Number(raw) !== defaults[key];
    });

    const seed = String(_el('seed-input')?.value ?? '').trim();

    return {
        'chip-backends': [backendParts.join(' · '), selected !== enabled || level !== '0' || _multiRunEnabled || _orderingEnabled],
        'chip-execution': [executionParts.join(' · '),
            !!(timeout && timeout.value !== timeout.defaultValue) || repeats !== 1 || exclusive || autosave],
        'chip-preprocessing': [preText, pre !== 'on' || bypass],
        'chip-compilers': [`Compile-only services: ${levels ? `${levels} level${levels === 1 ? '' : 's'}` : 'none'}`, levels > 0],
        'chip-thresholds': [`Agreement Thresholds: ${thresholdsChanged ? 'changed' : 'default'}`, thresholdsChanged],
        'chip-seed': [`Seed: ${seed || 'random'}`, seed !== ''],
    };
}

/** Rewrite every chip's text and highlight. */
export function updateSettingsChips() {
    Object.entries(_summaries()).forEach(([id, [text, changed]]) => {
        const chip = document.getElementById(id);
        if (!chip) return;
        chip.textContent = `${text} ▾`;
        chip.title = changed ? `${text} (changed from the default)` : text;
        (changed ? PLAIN : CHANGED).forEach(c => chip.classList.remove(c));
        (changed ? CHANGED : PLAIN).forEach(c => chip.classList.add(c));
    });
}

/** Wire each chip to its popover and keep the chips current. */
export function initSettingsBar() {
    document.querySelectorAll('.settings-chip').forEach(node => {
        const chip = /** @type {HTMLElement} */ (node);
        const panel = document.getElementById(chip.dataset.popover || '');
        if (!panel) return;
        chip.setAttribute('aria-haspopup', 'dialog');
        bindPopover(chip, panel, { focusSelector: 'input, select, button' });
        panel.addEventListener('input', updateSettingsChips);
        panel.addEventListener('change', () => {
            updateSettingsChips();
            document.dispatchEvent(new Event('workspace-change'));
        });
    });
    document.addEventListener('workspace-change', updateSettingsChips);
    updateSettingsChips();
}

/** Open the popover of the chip with id `chipId`. */
export function openSettings(chipId) {
    const chip = document.getElementById(chipId);
    if (chip && chip.getAttribute('aria-expanded') !== 'true') chip.click();
}

