// Divergence matrices and the explained-cause agreement panel (pair heatmap, pairwise
// evidence with metrics, shot-noise test and provenance).

import {
    STATUS_STYLES, _applyLegendDots, _chip, _cloneTemplate, _displayRunnerName, fmtInt, fmtNum, fmtPValue, fmtProb,
    getOptBadge, renderPreprocessingList, renderTooltip,
} from './render_helpers.js';
import {
    RUNNER_STATUS_STYLE, adjustedPValue, adjustedSignificant, correctionName, effectiveAgreement, measuredAssessment,
    statusBySimulator, unalignedBasisMatch,
} from './run_status.js';
import { makeCopyIconButton, thresholdDefaults } from './utils.js';

const STATUS_CELL_TEXT = { offline: 'OFF', error: 'ERR', timeout: 'T/O' };

/** Threshold recorded with a pair record, else the schema default. */
function _pairThreshold(rec, key) {
    const v = rec?.metrics?.[key];
    return typeof v === 'number' ? v : thresholdDefaults()[key];
}

const MATRICES = [
    {
        key: 'fidelity_matrix', title: 'Fidelity Matrix',
        within: (v, rec) => v >= 1 - _pairThreshold(rec, 'fidelity_tolerance'),
    },
    {
        key: 'relative_phase_matrix', title: 'Global phase offset arg⟨a|b⟩ (rad)',
        within: (v, rec) => Math.abs(v) <= _pairThreshold(rec, 'phase_tolerance'),
    },
    {
        key: 'statistical_distance_matrix (js_divergence)', title: 'JS Divergence Matrix (nats)',
        within: (v, rec) => v <= _pairThreshold(rec, 'js_threshold'),
    },
    {
        key: 'hellinger_distance_matrix', title: 'Hellinger Distance Matrix',
        within: (v, rec) => v <= _pairThreshold(rec, 'hellinger_threshold'),
    },
];

/** Render the numeric pairwise matrices, coloured by the thresholds recorded with each pair. */
export function renderDivergenceTables(report, panel, config = {}, rawResults = []) {
    if (!panel) return;
    panel.innerHTML = '';

    const outerDiv = document.createElement('div');
    outerDiv.className = 'space-y-8';

    const legendFrag = _cloneTemplate('tpl-legend-divergence');
    _applyLegendDots(legendFrag);
    outerDiv.appendChild(legendFrag);

    const statuses = statusBySimulator(rawResults);
    const lookup = _pairLookup(Array.isArray(report.pairwise_agreement) ? report.pairwise_agreement : []);
    let found = false;

    MATRICES.forEach(spec => {
        const matrix = report[spec.key];
        if (!matrix) return;
        found = true;

        const secFrag = _cloneTemplate('tpl-div-matrix-section');
        const h3 = secFrag.querySelector('.tpl-title');
        h3.classList.remove('tpl-title');
        h3.appendChild(renderTooltip(spec.key, spec.title));

        const theadRow = secFrag.querySelector('thead tr');
        report.simulators.forEach(s => {
            const th = _cloneTemplate('tpl-div-matrix-header-cell').querySelector('th');
            th.appendChild(document.createTextNode(_displayRunnerName(s)));
            const badge = getOptBadge(s, config);
            if (badge) th.appendChild(badge);
            theadRow.appendChild(th);
        });

        const tbody = secFrag.querySelector('.tpl-tbody');
        tbody.classList.remove('tpl-tbody');

        report.simulators.forEach((s1, i) => {
            const tr = document.createElement('tr');
            const rowTh = _cloneTemplate('tpl-div-matrix-row-header').querySelector('th');
            rowTh.appendChild(document.createTextNode(_displayRunnerName(s1)));
            const rBadge = getOptBadge(s1, config);
            if (rBadge) rowTh.appendChild(rBadge);
            tr.appendChild(rowTh);

            matrix[i].forEach((val, j) => {
                const td = _cloneTemplate('tpl-div-matrix-cell').querySelector('td');
                const s2 = report.simulators[j];
                const rec = lookup[_pairKey(s1, s2)];
                const failed = [statuses.get(s1), statuses.get(s2)].find(st => st && st !== 'ok');
                let text;
                let style;
                let title = `${_displayRunnerName(s1)} × ${_displayRunnerName(s2)}`;
                const legacySentinel = val === -1;
                if (i === j) {
                    text = typeof val === 'number' && !legacySentinel ? fmtNum(val) : '-';
                    style = 'neutral';
                    title += ': the backend compared with itself';
                } else if (failed) {
                    text = STATUS_CELL_TEXT[failed];
                    style = RUNNER_STATUS_STYLE[failed];
                    title += `: a run ended with status ${failed}`;
                } else if (rec?.agreement === 'not_comparable' || typeof val !== 'number' || legacySentinel) {
                    text = 'n/c';
                    style = 'offline';
                    title += `: not comparable (${rec?.metrics?.reason || 'no value'})`;
                } else {
                    text = fmtNum(val);
                    style = spec.within(val, rec) ? 'success' : 'divergence';
                    title += `: ${val}${rec ? ` (${rec.agreement})` : ''}`;
                }
                STATUS_STYLES[style].cell.split(' ').forEach(c => td.classList.add(c));
                td.textContent = text;
                td.title = title;
                tr.appendChild(td);
            });
            tbody.appendChild(tr);
        });
        outerDiv.appendChild(secFrag);
    });

    if (!found) {
        const p = document.createElement('p');
        p.className = 'text-gray-500 mt-4';
        p.textContent = 'No matrices available.';
        outerDiv.appendChild(p);
    }

    panel.appendChild(outerDiv);
}

export const AGREEMENT_STYLE = {
    agree_directly: 'success',
    agree_up_to_global_phase: 'success',
    distance_within_threshold: 'success',
    agree_after_bit_reversal: 'divergence',
    agree_after_qubit_permutation: 'anomaly',
    unaligned_basis_match: 'anomaly',
    agree_after_normalization: 'success',
    residual_disagreement: 'anomaly',
    distance_exceeds_threshold: 'anomaly',
    not_comparable: 'offline',
};

export const ASSESSMENT_STYLE = {
    consistent_within_shot_noise: 'success',
    inconclusive_low_shots: 'offline',
    distinguishable: 'anomaly',
    ambiguous: 'offline',
    not_comparable: 'offline',
};

/** Badge style for a pair: by its measured assessment, else by the label without the normalisation note. */
function _pairStyle(p) {
    if (p.mode === 'measured') {
        const a = measuredAssessment(p);
        if (a === 'consistent_within_shot_noise') {
            return AGREEMENT_STYLE[p.agreement] === 'divergence' ? 'divergence' : 'success';
        }
        if (a && ASSESSMENT_STYLE[a]) return ASSESSMENT_STYLE[a];
    } else if (unalignedBasisMatch(p)) {
        return 'anomaly';
    }
    return AGREEMENT_STYLE[effectiveAgreement(p)] || AGREEMENT_STYLE[p.agreement] || 'offline';
}

/** Summary-row metric: the value under the transform the label names. */
function _pairMetricText(p) {
    const m = p.metrics || {};
    const label = effectiveAgreement(p);
    if (p.mode === 'statevector') {
        if (label === 'agree_after_bit_reversal') return `F(bit-rev)=${_fmtNum(m.bit_reversed_fidelity)}`;
        if (label === 'agree_after_qubit_permutation') return `F(perm)=${_fmtNum(m.qubit_permutation?.fidelity ?? p.transform_effect?.fidelity_after_transform)}`;
        return `F=${_fmtNum(m.direct_fidelity)}`;
    }
    if (label === 'agree_after_bit_reversal') return `JS(bit-rev)=${_fmtNum(m.bit_reversed_js_divergence)} nats`;
    if (label === 'agree_after_qubit_permutation') return `JS(perm)=${_fmtNum(m.qubit_permutation?.js_divergence)} nats`;
    return `JS=${_fmtNum(m.js_divergence)} nats`;
}

export const VERDICT_STYLE = {
    consistent: 'success',
    distinguishable: 'anomaly',
    inconclusive_low_shots: 'offline',
    ambiguous: 'divergence',
};

/** Number formatting for the report tabs; the same rules as the publication tables. */
export function _fmtNum(v, digits = 4) {
    return fmtNum(v, digits);
}

export function _kvGrid(rows) {
    const grid = document.createElement('div');
    grid.className = 'grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-0.5';
    rows.forEach(([k, v]) => {
        if (v === undefined) return;
        const row = document.createElement('div');
        row.className = 'min-w-0';
        const kSpan = document.createElement('span');
        kSpan.className = 'text-gray-400';
        kSpan.textContent = `${k}: `;
        const vSpan = document.createElement('span');
        vSpan.className = 'text-gray-800 font-mono break-words';
        vSpan.textContent = (v === null ? '—' : String(v));
        row.appendChild(kSpan);
        row.appendChild(vSpan);
        grid.appendChild(row);
    });
    return grid;
}

export function _kvMap(obj) {
    if (!obj) return '—';
    return Object.entries(obj)
        .map(([k, v]) => `${k}=${v === null ? 'null' : (typeof v === 'object' ? JSON.stringify(v) : v)}`)
        .join(', ');
}

export function _sectionLabel(text) {
    const d = document.createElement('div');
    d.className = 'font-semibold text-gray-500 mb-1';
    d.textContent = text;
    return d;
}

function _yesNo(v) {
    if (v === null || v === undefined) return undefined;
    return v ? 'yes' : 'no';
}

function _permRow(qp) {
    if (qp.attempted) return 'yes';
    return `no (${qp.reason || '—'}${qp.max_qubits ? `, cap ${qp.max_qubits} qubits` : ''})`;
}

export function _agreementMetricsBlock(p) {
    const m = p.metrics || {};
    const wrap = document.createElement('div');

    if (p.agreement === 'not_comparable') {
        wrap.appendChild(_sectionLabel('Not comparable'));
        wrap.appendChild(_kvGrid([
            ['reason', m.reason || '—'],
            ['details', m.details && Object.keys(m.details).length ? _kvMap(m.details) : '—'],
        ]));
        return wrap;
    }

    wrap.appendChild(_sectionLabel('Metrics (direct, and after each registered transform)'));
    const qp = m.qubit_permutation || {};
    let rows;
    if (p.mode === 'statevector') {
        rows = [
            ['direct fidelity', _fmtNum(m.direct_fidelity)],
            ['global phase offset arg⟨a|b⟩ (rad)', _fmtNum(m.direct_relative_phase_rad)],
            ['bit-reversed fidelity', _fmtNum(m.bit_reversed_fidelity)],
            ['perm attempted', _permRow(qp)],
            ['perm', qp.permutation ? JSON.stringify(qp.permutation) : '—'],
            ['perm fidelity', _fmtNum(qp.fidelity)],
            ['norms', m.norms ? Object.entries(m.norms).map(([k, v]) => `${k}=${_fmtNum(v, 6)}`).join(', ') : undefined],
            ['unnormalized input', _yesNo(m.unnormalized_input)],
            ['label after normalization', m.normalized_agreement ?? undefined],
            ['fidelity tolerance', m.fidelity_tolerance],
            ['phase tolerance (rad)', m.phase_tolerance],
            ['norm tolerance', m.norm_tolerance],
        ];
    } else {
        const mismatch = m.shot_total_mismatch;
        rows = [
            ['JS divergence (nats)', _fmtNum(m.js_divergence)],
            ['Hellinger', _fmtNum(m.hellinger_distance)],
            ['bit-rev JS (nats)', _fmtNum(m.bit_reversed_js_divergence)],
            ['bit-rev Hellinger', _fmtNum(m.bit_reversed_hellinger_distance)],
            ['perm attempted', _permRow(qp)],
            ['perm JS (nats)', qp.attempted ? _fmtNum(qp.js_divergence) : undefined],
            ['n_shots requested', fmtInt(m.n_shots)],
            ['shot totals', mismatch ? `${_kvMap(mismatch.observed)} (requested ${mismatch.requested})` : undefined],
            ['JS threshold (nats)', m.js_threshold],
            ['Hellinger threshold', m.hellinger_threshold],
        ];
    }
    wrap.appendChild(_kvGrid(rows));
    return wrap;
}

export function _statisticalTestBlock(st) {
    const wrap = document.createElement('div');
    wrap.appendChild(_sectionLabel(`Shot-noise statistical test (basis: ${st.basis})`));
    const ef = st.effect_size || {};
    const pw = st.power || {};
    const chi2 = st.chi2 || {};
    const gt = st.g_test || {};
    const c = correctionName(st);
    wrap.appendChild(_kvGrid([
        ['χ² p', fmtPValue(chi2.p_value)],
        [`χ² p (${c})`, fmtPValue(adjustedPValue(chi2))],
        [`χ² significant (${c})`, _yesNo(adjustedSignificant(chi2)) ?? '—'],
        ['G-test p', fmtPValue(gt.p_value)],
        [`G-test p (${c})`, fmtPValue(adjustedPValue(gt))],
        [`G-test significant (${c})`, _yesNo(adjustedSignificant(gt)) ?? '—'],
        ['α', st.alpha],
        ['shots', st.n_shots ? _kvMap(st.n_shots) : undefined],
        ['same runner seed', st.shared_seed === null || st.shared_seed === undefined ? 'not recorded' : _yesNo(st.shared_seed)],
        ['total variation', _fmtNum(ef.total_variation)],
        ["Cramér's V", _fmtNum(ef.cramers_v)],
        [`power at observed shots (δ=${pw.delta_tv})`, fmtProb(pw.power_to_detect_delta_at_observed_shots)],
        [c === 'BY' ? 'power computed at α/(m·c_m)' : 'power computed at α/m', typeof pw.alpha_used === 'number'
            ? `${fmtNum(pw.alpha_used)}${typeof pw.m_pairs === 'number' ? ` (m = ${fmtInt(pw.m_pairs)})` : ''}` : undefined],
        ['shots/backend for target power', fmtInt(pw.recommended_shots_per_backend ?? st.recommended_shots_per_backend ?? pw.shots_per_backend_for_target_power)],
        ['more shots than used', typeof (pw.recommended_exceeds_actual ?? st.recommended_exceeds_actual) === 'boolean'
            ? _yesNo(pw.recommended_exceeds_actual ?? st.recommended_exceeds_actual) : undefined],
        ['power df', pw.df !== undefined ? fmtInt(pw.df) : undefined],
        ['low-count warning', st.low_count_warning ? 'yes' : 'no'],
        ['basis source', st.basis_source ?? undefined],
        ['outcomes observed / tested bins', st.observed_outcomes !== undefined
            ? `${fmtInt(st.observed_outcomes)} / ${fmtInt(st.tested_outcome_bins)}` : undefined],
        ['rare outcomes pooled', st.pooled_outcomes !== undefined ? fmtInt(st.pooled_outcomes) : undefined],
        ['inconclusive reason', st.inconclusive_reason ?? undefined],
        ['resolvable by more shots', typeof st.resolvable_by_more_shots === 'boolean' ? _yesNo(st.resolvable_by_more_shots) : undefined],
    ]));
    const model = document.createElement('div');
    model.className = 'text-[11px] text-gray-400 mt-1';
    model.textContent = `Power model: ${pw.model}. The verdict is reported alongside the descriptive label.`;
    wrap.appendChild(model);
    return wrap;
}

export function _provenanceBlock(prov) {
    const wrap = document.createElement('div');
    if (!prov) return wrap;
    const rows = [
        ['qubit ordering', _kvMap(prov.qubit_ordering)],
        ['runner seed', prov.runner_seed ? _kvMap(prov.runner_seed) : (prov.seed ? _kvMap(prov.seed) : undefined)],
        ['sampling method', prov.sampling_method ? _kvMap(prov.sampling_method) : undefined],
        ['SDK versions', _kvMap(prov.sdk_versions)],
    ];
    const header = document.createElement('div');
    header.className = 'flex items-center gap-2';
    header.appendChild(_sectionLabel('Provenance'));
    const asText = () => {
        const lines = rows.filter(r => r[1] !== undefined).map(([k, v]) => `${k}: ${v}`);
        Object.entries(prov.preprocessing_applied || {}).forEach(([sim, list]) => {
            lines.push(`preprocessing ${sim}: ${(list || []).join(' | ') || 'none'}`);
        });
        return lines.join('\n');
    };
    header.appendChild(makeCopyIconButton(asText, 'Copy provenance'));
    wrap.appendChild(header);
    wrap.appendChild(_kvGrid(rows));

    const pre = prov.preprocessing_applied;
    if (pre && Object.keys(pre).length) {
        const box = document.createElement('div');
        box.className = 'mt-1 space-y-1';
        Object.entries(pre).forEach(([sim, list]) => {
            const label = document.createElement('div');
            label.className = 'text-gray-400';
            label.textContent = `preprocessing, ${_displayRunnerName(sim)}:`;
            box.appendChild(label);
            box.appendChild(renderPreprocessingList(list));
        });
        wrap.appendChild(box);
    }
    return wrap;
}

export const AGREEMENT_HEX = {
    agree_directly: '#008300', distance_within_threshold: '#008300',
    agree_up_to_global_phase: '#1baf7a', agree_after_bit_reversal: '#2a78d6',
    agree_after_qubit_permutation: '#4a3aa7', agree_after_normalization: '#d6a400',
    residual_disagreement: '#e34948', distance_exceeds_threshold: '#e34948',
    not_comparable: '#898781',
};

const ASSESSMENT_HEX = {
    consistent_within_shot_noise: '#008300', inconclusive_low_shots: '#898781',
    distinguishable: '#e34948', ambiguous: '#898781',
};

/** Heatmap colour: a measured pair above the descriptive thresholds takes its shot-noise assessment's colour. */
function _cellHex(rec) {
    const a = rec.mode === 'measured' ? measuredAssessment(rec) : null;
    if (a && rec.agreement === 'distance_exceeds_threshold' && ASSESSMENT_HEX[a]) return ASSESSMENT_HEX[a];
    return AGREEMENT_HEX[rec.agreement] || '#898781';
}

/** Pair-table order: disagreement first, not_comparable last. */
export const _AGREEMENT_SEVERITY = {
    residual_disagreement: 0, distance_exceeds_threshold: 0,
    agree_after_normalization: 1, agree_after_qubit_permutation: 2, agree_after_bit_reversal: 3,
    agree_up_to_global_phase: 4, agree_directly: 5, distance_within_threshold: 5,
    not_comparable: 6,
};

export function _pairKey(a, b) {
    return [a, b].sort().join('\u0000');
}

/** Pair records keyed by the unordered simulator pair. */
export function _pairLookup(pairs) {
    const map = {};
    pairs.forEach(p => {
        const s = p.simulators || [];
        if (s.length === 2) map[_pairKey(s[0], s[1])] = p;
    });
    return map;
}

export function _agreementLegend(present) {
    const wrap = document.createElement('div');
    wrap.className = 'flex flex-wrap gap-x-3 gap-y-1 mt-2 text-[11px]';
    present.forEach(label => {
        const item = document.createElement('span');
        item.className = 'inline-flex items-center gap-1';
        const sw = document.createElement('span');
        sw.className = 'inline-block w-3 h-3 rounded-sm border border-gray-300';
        sw.style.backgroundColor = AGREEMENT_HEX[label] || '#898781';
        item.appendChild(sw);
        item.appendChild(document.createTextNode(label));
        wrap.appendChild(item);
    });
    return wrap;
}

export function _agreementSummaryStrip(report, pairs) {
    const strip = document.createElement('div');
    strip.className = 'flex flex-wrap gap-2 mb-4';

    const assessed = pairs.some(p => p.mode === 'measured' && measuredAssessment(p));
    const counts = {};
    pairs.forEach(p => { counts[p.agreement] = (counts[p.agreement] || 0) + 1; });
    Object.keys(counts)
        .sort((a, b) => (_AGREEMENT_SEVERITY[a] ?? 9) - (_AGREEMENT_SEVERITY[b] ?? 9))
        .forEach(label => {
            const style = assessed && label === 'distance_exceeds_threshold' ? 'offline' : (AGREEMENT_STYLE[label] || 'offline');
            const pill = _chip(STATUS_STYLES[style].badge, `${label} · ${counts[label]}`,
                assessed && label === 'distance_exceeds_threshold'
                    ? 'Above the descriptive JS/Hellinger thresholds; the shot-noise assessment decides whether this is a disagreement'
                    : 'Agreement class count');
            strip.appendChild(pill);
        });

    const st = report.statistical_test_summary;
    if (assessed) {
        const sep = document.createElement('span');
        sep.className = 'w-px bg-gray-200 mx-1';
        strip.appendChild(sep);
        const aCounts = {};
        pairs.forEach(p => {
            const a = measuredAssessment(p);
            if (a && a !== 'not_comparable') aCounts[a] = (aCounts[a] || 0) + 1;
        });
        Object.entries(aCounts).forEach(([a, n]) => {
            strip.appendChild(_chip(STATUS_STYLES[ASSESSMENT_STYLE[a] || 'offline'].badge,
                `${a} · ${n}`, `Shot-noise assessment${st ? ` (α=${st.alpha}, ${[].concat(st.correction || []).join('+')})` : ''}`));
        });
    } else if (st && st.verdict_counts) {
        const sep = document.createElement('span');
        sep.className = 'w-px bg-gray-200 mx-1';
        strip.appendChild(sep);
        Object.entries(st.verdict_counts).forEach(([v, n]) => {
            strip.appendChild(_chip(STATUS_STYLES[VERDICT_STYLE[v] || 'offline'].badge,
                `stat: ${v} · ${n}`, `Shot-noise verdict (α=${st.alpha}, ${[].concat(st.correction || []).join('+')})`));
        });
    }
    return strip;
}

export function _agreementHeatmap(report, pairs, config) {
    const sims = report.simulators || [];
    if (sims.length < 2) return null;
    const lookup = _pairLookup(pairs);
    const wrap = document.createElement('div');
    wrap.className = 'mb-6 overflow-x-auto';

    const h = document.createElement('h4');
    h.className = 'text-sm font-semibold text-gray-700 mb-2';
    h.textContent = 'Agreement class by pair';
    wrap.appendChild(h);

    const table = document.createElement('table');
    table.className = 'matrix-table border-collapse text-xs';
    const thead = document.createElement('thead');
    const hrow = document.createElement('tr');
    hrow.appendChild(document.createElement('th'));
    sims.forEach(s => {
        const th = document.createElement('th');
        th.className = 'sim-header px-1 text-gray-600 font-medium align-bottom';
        th.textContent = _displayRunnerName(s);
        hrow.appendChild(th);
    });
    thead.appendChild(hrow);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    sims.forEach((s1, i) => {
        const tr = document.createElement('tr');
        const rh = document.createElement('th');
        rh.className = 'px-2 text-right text-gray-600 font-medium whitespace-nowrap';
        rh.textContent = _displayRunnerName(s1);
        tr.appendChild(rh);
        sims.forEach((s2, j) => {
            const td = document.createElement('td');
            td.className = 'w-6 h-6 text-center border border-white';
            if (i === j) {
                td.classList.add('bg-gray-100');
            } else {
                const rec = lookup[_pairKey(s1, s2)];
                if (rec) {
                    td.style.backgroundColor = _cellHex(rec);
                    td.style.color = '#ffffff';
                    const a = rec.mode === 'measured' ? measuredAssessment(rec) : null;
                    td.title = `${_displayRunnerName(s1)} × ${_displayRunnerName(s2)}: ${rec.agreement}${a ? `, ${a}` : ''}`;
                    td.style.cursor = 'pointer';
                    td.onclick = () => {
                        const row = document.getElementById(`agr-row-${_agrRowId(rec)}`);
                        if (row) { row.open = true; row.scrollIntoView({ block: 'center' }); }
                    };
                } else {
                    td.classList.add('bg-gray-50');
                }
            }
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);

    const present = [...new Set(pairs.map(p => p.agreement))]
        .sort((a, b) => (_AGREEMENT_SEVERITY[a] ?? 9) - (_AGREEMENT_SEVERITY[b] ?? 9));
    const assessedExceeds = pairs.filter(p => p.agreement === 'distance_exceeds_threshold' && p.mode === 'measured' && measuredAssessment(p));
    const legend = _agreementLegend(present.filter(l => !(l === 'distance_exceeds_threshold' && assessedExceeds.length === pairs.filter(p => p.agreement === l).length)));
    [...new Set(assessedExceeds.map(p => measuredAssessment(p)))].forEach(a => {
        const item = document.createElement('span');
        item.className = 'inline-flex items-center gap-1';
        const sw = document.createElement('span');
        sw.className = 'inline-block w-3 h-3 rounded-sm border border-gray-300';
        sw.style.backgroundColor = ASSESSMENT_HEX[a] || '#898781';
        item.appendChild(sw);
        item.appendChild(document.createTextNode(`distance_exceeds_threshold, ${a}`));
        legend.appendChild(item);
    });
    wrap.appendChild(legend);
    return wrap;
}

export function _agrRowId(p) {
    const s = p.simulators || ['?', '?'];
    return `${s[0]}-${s[1]}`.replace(/[^a-zA-Z0-9-]/g, '_');
}

export function _agreementPairTable(pairs) {
    const wrap = document.createElement('div');
    const h = document.createElement('h4');
    h.className = 'text-sm font-semibold text-gray-700 mb-2';
    h.textContent = 'Pairwise evidence';
    wrap.appendChild(h);

    const present = [...new Set(pairs.map(p => p.agreement))]
        .sort((a, b) => (_AGREEMENT_SEVERITY[a] ?? 9) - (_AGREEMENT_SEVERITY[b] ?? 9));
    const filters = document.createElement('div');
    filters.className = 'flex flex-wrap gap-1.5 mb-2';
    const rows = [];
    const setFilter = (label) => {
        rows.forEach(r => { r.style.display = (!label || r.dataset.agreement === label) ? '' : 'none'; });
        filters.querySelectorAll('button').forEach(b => b.classList.toggle('ring-2', b.dataset.f === (label || '')));
    };
    const mkFilterBtn = (label, text) => {
        const b = document.createElement('button');
        b.dataset.f = label || '';
        b.className = 'px-2 py-0.5 rounded text-xs border border-gray-300 hover:bg-gray-100 ring-blue-400';
        b.textContent = text;
        b.onclick = () => setFilter(label);
        return b;
    };
    filters.appendChild(mkFilterBtn('', `All (${pairs.length})`));
    present.forEach(label => filters.appendChild(mkFilterBtn(label, label)));
    wrap.appendChild(filters);

    const list = document.createElement('div');
    list.className = 'space-y-1';

    const sorted = [...pairs].sort((a, b) =>
        (_AGREEMENT_SEVERITY[a.agreement] ?? 9) - (_AGREEMENT_SEVERITY[b.agreement] ?? 9));

    sorted.forEach(p => {
        const det = document.createElement('details');
        det.id = `agr-row-${_agrRowId(p)}`;
        det.dataset.agreement = p.agreement;
        det.className = 'rounded border border-gray-200 bg-white';
        rows.push(det);

        const sum = document.createElement('summary');
        sum.className = 'grid grid-cols-[minmax(140px,1fr)_auto_auto_auto] items-center gap-2 px-3 py-1.5 cursor-pointer text-sm select-none';

        const name = document.createElement('span');
        name.className = 'font-medium text-gray-800 truncate';
        const sims = p.simulators || ['?', '?'];
        name.textContent = `${_displayRunnerName(sims[0])} × ${_displayRunnerName(sims[1])}`;
        sum.appendChild(name);

        const unaligned = p.mode === 'statevector' && unalignedBasisMatch(p) && p.agreement !== 'unaligned_basis_match';
        sum.appendChild(_chip(STATUS_STYLES[_pairStyle(p)].badge,
            unaligned ? `${p.agreement} · unaligned basis` : p.agreement,
            unaligned
                ? 'Matches only in the basis the declared qubit orderings do not imply; counted as a disagreement'
                : (p.agreement === 'agree_after_normalization'
                    ? `Agrees after normalising an input statevector; label after normalisation: ${p.metrics?.normalized_agreement ?? '—'}`
                    : 'Explained-cause label')));

        const metric = document.createElement('span');
        metric.className = 'text-xs text-gray-500 font-mono text-right';
        metric.title = p.mode === 'statevector' ? 'Fidelity under the transform the label names' : 'JS divergence under the transform the label names';
        metric.textContent = _pairMetricText(p);
        sum.appendChild(metric);

        const st = p.metrics && p.metrics.statistical_test;
        const vslot = document.createElement('span');
        const assessment = p.mode === 'measured' ? measuredAssessment(p) : null;
        if (assessment && assessment !== 'not_comparable') {
            vslot.appendChild(_chip(STATUS_STYLES[ASSESSMENT_STYLE[assessment] || 'offline'].badge,
                assessment, `Shot-noise assessment${st?.verdict ? ` (test verdict: ${st.verdict})` : ''}`));
        } else if (st && st.verdict) {
            vslot.appendChild(_chip(STATUS_STYLES[VERDICT_STYLE[st.verdict] || 'offline'].badge,
                st.verdict, 'Shot-noise statistical verdict'));
        }
        sum.appendChild(vslot);
        det.appendChild(sum);

        const body = document.createElement('div');
        body.className = 'px-3 pb-3 pt-2 text-xs text-gray-600 space-y-2 border-t border-gray-100';
        body.appendChild(_agreementMetricsBlock(p));
        if (st) body.appendChild(_statisticalTestBlock(st));
        body.appendChild(_provenanceBlock(p.provenance));
        det.appendChild(body);
        list.appendChild(det);
    });
    wrap.appendChild(list);
    return wrap;
}

export function renderAgreementPanel(report, panel, config = {}) {
    if (!panel) return;
    panel.innerHTML = '';

    const h3 = document.createElement('h3');
    h3.className = 'text-lg font-semibold text-gray-900 mb-4';
    h3.appendChild(renderTooltip('pairwise_agreement', 'Explained-Cause Agreement'));
    panel.appendChild(h3);

    const pairs = report.pairwise_agreement;
    if (!Array.isArray(pairs) || pairs.length === 0) {
        const empty = document.createElement('p');
        empty.className = 'text-sm text-gray-500 italic';
        empty.textContent = 'No explained-cause agreement evidence in this report (older schema, single backend, or no comparable pairs).';
        panel.appendChild(empty);
        return;
    }

    panel.appendChild(_agreementSummaryStrip(report, pairs));
    const heat = _agreementHeatmap(report, pairs, config);
    if (heat) panel.appendChild(heat);
    panel.appendChild(_agreementPairTable(pairs));
}