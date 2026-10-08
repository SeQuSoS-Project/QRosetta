// Exports tab wording: each view's label, group, description and controls, the formats an
// export item offers, and the presets. Data only; artifact_views.js holds the parameters.

import { VIEW_BY_ID } from './artifact_views.js';

const BACKENDS = { key: 'backends', label: 'Backends', control: 'backends' };
const SIZE = { key: 'size', label: 'Figure size', control: 'select', more: true,
    options: [['auto', 'Automatic'], ['single', 'Single column (3.5 in)'], ['double', 'Double column (7 in)'], ['slide', 'Slide (16:9)']] };
const TITLE = { key: 'title', label: 'Title in figure', control: 'toggle', more: true };
const COLOUR = { key: 'colour', label: 'Colour', control: 'seg', more: true,
    options: [['backend', 'By backend'], ['highlight', 'Highlight disagreeing']],
    help: 'Highlight colours the backends whose pair with the reference is a disagreement and greys the rest.' };
const refWhen = layouts => ({ key: 'ref', label: 'Reference', control: 'ref',
    show: p => layouts.includes(p.layout) || p.colour === 'highlight' });
const FIGURE_MORE = [SIZE, TITLE];

export const SIZE_TAGS = {
    auto: 'Automatic size', single: 'Single column · 3.5 × 2.6 in', double: 'Double column · 7 × 3.6 in', slide: 'Slide · 13.3 × 7.5 in',
};

/** UI of each view, in list order; `kind` json and qasm are local to the browser. */
export const VIEW_UI = [
    { id: 'agreement_distribution', group: 'Agreement', label: 'Agreement class distribution',
        desc: 'How many backend pairs fall into each agreement label and shot-noise verdict.',
        controls: [BACKENDS, ...FIGURE_MORE] },
    { id: 'agreement', group: 'Agreement', label: 'Pairwise agreement table',
        desc: 'One row per backend pair: label, transform, key metric, verdict and reason.', controls: [BACKENDS] },
    { id: 'statistical_test', group: 'Statistical', label: 'Statistical-test table',
        desc: 'Chi-square and G-test p-values, effect size and power per pair.', controls: [BACKENDS] },
    { id: 'counts', group: 'Statistical', label: 'Count comparison',
        desc: 'Measured outcome probabilities per backend. Pick two backends for a one-against-one histogram.',
        controls: [BACKENDS,
            { key: 'layout', label: 'Layout', control: 'seg',
                options: [['overlay', 'Overlay'], ['panels', 'Small multiples'], ['diff', 'Difference from reference'], ['heatmap', 'Heatmap']] },
            refWhen(['diff', 'panels']),
            { key: 'outcomes', label: 'Outcomes', control: 'outcomes' },
            { key: 'sort', label: 'Sort', control: 'seg', more: true,
                options: [['probability', 'Probability'], ['bitstring', 'Bitstring'], ['hamming', 'Hamming weight']] },
            { key: 'yscale', label: 'Probability axis', control: 'seg', more: true,
                options: [['linear', 'Linear'], ['log', 'Log']], show: p => p.layout === 'overlay' || p.layout === 'panels' },
            { key: 'band', label: 'Shot-noise band', control: 'toggle', more: true, show: p => p.layout === 'diff',
                help: '±2σ of the difference of two independent samples at the reference probability and shot count.' },
            { key: 'keyorder', label: 'Key order', control: 'seg', more: true,
                options: [['msb', 'msb (c[0] left)'], ['lsb', 'lsb (c[0] right)']],
                help: 'How keys are written on the axis. Example with three classical bits where only c[0] reads 1: msb writes 100, lsb writes 001 (the order Qiskit prints). lsb-declared backends are aligned to one order before plotting either way.' },
            COLOUR, ...FIGURE_MORE] },
    { id: 'marginals', group: 'Statistical', label: 'Single-bit marginals',
        desc: 'P(c[j] = 1) for each classical bit: one point per bit, however many qubits the circuit has.',
        controls: [BACKENDS,
            { key: 'layout', label: 'Layout', control: 'seg', options: [['lines', 'All backends'], ['diff', 'Difference from reference']] },
            refWhen(['diff']),
            { key: 'errorbars', label: 'Shot noise', control: 'toggle', help: '±2σ binomial error bars, or a band around the reference in the difference layout.' },
            COLOUR, ...FIGURE_MORE] },
    { id: 'hamming', group: 'Statistical', label: 'Hamming weight',
        desc: 'Probability of measuring w ones: n + 1 bins instead of 2^n outcomes.',
        controls: [BACKENDS,
            { key: 'layout', label: 'Layout', control: 'seg', options: [['bars', 'Bars'], ['lines', 'Lines'], ['diff', 'Difference from reference']] },
            refWhen(['diff']), COLOUR, ...FIGURE_MORE] },
    { id: 'rank', group: 'Statistical', label: 'Rank–probability',
        desc: 'Each backend’s outcome probabilities sorted from largest to smallest; shows how spread out a distribution is.',
        controls: [BACKENDS,
            { key: 'xscale', label: 'Rank axis', control: 'seg', options: [['log', 'Log'], ['linear', 'Linear']] },
            refWhen([]), COLOUR, ...FIGURE_MORE] },
    { id: 'fidelity_heatmap', group: 'Divergence', label: 'Raw statevector fidelity heatmap',
        desc: 'N × N fidelity between backends before any transform.', controls: [BACKENDS, ...FIGURE_MORE] },
    { id: 'js_divergence_heatmap', group: 'Divergence', label: 'Raw Jensen–Shannon divergence heatmap',
        desc: 'N × N Jensen–Shannon divergence between backends, in nats.', controls: [BACKENDS, ...FIGURE_MORE] },
    { id: 'hellinger_heatmap', group: 'Divergence', label: 'Raw Hellinger distance heatmap',
        desc: 'N × N Hellinger distance between backends.', controls: [BACKENDS, ...FIGURE_MORE] },
    { id: 'execution_time', group: 'Performance', label: 'Execution time',
        desc: 'Compilation and simulation wall-clock time per backend.',
        controls: [BACKENDS,
            { key: 'stage', label: 'Stage', control: 'seg', options: [['stacked', 'Compilation + simulation'], ['simulation', 'Simulation'], ['compilation', 'Compilation']] },
            { key: 'xscale', label: 'Time axis', control: 'seg', options: [['linear', 'Linear'], ['log', 'Log']], show: p => p.stage !== 'stacked' },
            ...FIGURE_MORE] },
    { id: 'resource_usage', group: 'Resources', label: 'Resource usage',
        desc: 'Memory per backend; the table adds sim-window peak, theoretical statevector size and precision.',
        controls: [BACKENDS,
            { key: 'metric', label: 'Metric', control: 'seg', options: [['process_peak', 'Process peak RSS'], ['memory_delta', 'Mem Delta']] },
            ...FIGURE_MORE] },
    { id: 'metadata', group: 'Metadata', label: 'Run + provenance metadata',
        desc: 'Device, SDK versions, bit order, sampling method and optimisation level per backend.', controls: [BACKENDS] },
    { id: 'json', group: 'Metadata', label: 'Report JSON', kind: 'json',
        desc: 'The report as held in this browser. The crate always includes it as results.json.', controls: [] },
    { id: 'qasm', group: 'Circuits', label: 'Executed QASM', kind: 'qasm',
        desc: 'The exact circuit each backend executed. Every backend’s file is always in the crate.', controls: [] },
    { id: 'glossary', group: 'Reference', label: 'Taxonomy glossary',
        desc: 'Definitions of every agreement label, verdict and reason, and the default thresholds.', controls: [] },
];
export const VIEW_UI_BY_ID = Object.fromEntries(VIEW_UI.map(v => [v.id, v]));

/** Formats an export item of the view offers, as [value, label]. */
export function itemFormats(viewId) {
    const v = VIEW_BY_ID[viewId];
    if (!v) return [];
    if (v.text) return [['markdown', 'Markdown'], ['text', 'Text']];
    const fig = v.figure ? [['svg', 'SVG'], ['pdf', 'PDF'], ['png', 'PNG']] : [];
    if (!v.table) return fig;
    return v.figure ? fig.concat([['latex', 'LaTeX'], ['csv', 'CSV']])
        : [['latex', 'LaTeX'], ['csv', 'CSV'], ['markdown', 'Markdown'], ['html', 'HTML'], ['xlsx', 'XLSX']];
}

/** Formats a newly added item starts with. */
export function defaultFormats(viewId) {
    const v = VIEW_BY_ID[viewId];
    if (v.text) return ['markdown'];
    return v.figure ? ['svg'] : ['latex', 'csv'];
}

const item = (view, params = {}, formats = null) => ({ view, params, formats: formats || defaultFormats(view) });

/** Presets: {id, label, make(available, mode)} where `available` is the set of view ids the report offers. */
export const PRESETS = [
    { id: 'paper', label: 'Paper figures', make: (available, mode) => [
        item('agreement_distribution'), item('agreement', {}, ['latex']),
        mode === 'measured' ? item('counts', { layout: 'diff' }) : item('fidelity_heatmap'),
        item('marginals', { layout: 'diff' }), item('execution_time', {}, ['svg', 'latex']), item('glossary'),
    ].filter(i => available.has(i.view)) },
    { id: 'data', label: 'Data for analysis', make: available => [
        item('agreement', {}, ['csv']), item('statistical_test', {}, ['csv']),
        item('counts', { outcomes: 'threshold', threshold: 0, other: false }, ['csv']),
        item('marginals', {}, ['csv']), item('hamming', {}, ['csv']),
        item('fidelity_heatmap', {}, ['csv']), item('js_divergence_heatmap', {}, ['csv']),
        item('execution_time', {}, ['csv']), item('resource_usage', {}, ['csv']), item('metadata', {}, ['csv']),
    ].filter(i => available.has(i.view)) },
    { id: 'everything', label: 'Everything', make: available => VIEW_UI.filter(v => !v.kind && available.has(v.id))
        .map(v => item(v.id, {}, itemFormats(v.id).map(f => f[0]))) },
    { id: 'none', label: 'Nothing extra (data and circuits only)', make: () => [] },
];

const _svg = d => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
/** Line icons for the Exports tab buttons. */
export const ICONS = {
    download: _svg('<path d="M12 3v12m0 0-5-5m5 5 5-5M5 21h14"/>'),
    copy: _svg('<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>'),
    plus: _svg('<path d="M12 5v14M5 12h14"/>'),
    check: _svg('<path d="M20 6 9 17l-5-5"/>'),
    edit: _svg('<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/>'),
    remove: _svg('<path d="M18 6 6 18M6 6l12 12"/>'),
    crate: _svg('<path d="M21 8 12 3 3 8v8l9 5 9-5Z"/><path d="m3 8 9 5 9-5M12 13v8"/>'),
};
