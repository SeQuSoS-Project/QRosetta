// Summary tab of a single-circuit report: failed runs by status, what the pairwise
// agreement records show, and per-backend run details (precision, seeds, preprocessing).

import { panelElements } from './dom.js';
import {
    STATUS_STYLES, _applyLegendDots, _chip, _cloneTemplate, _displayRunnerName, fmtInt, fmtNum,
    precisionTag, renderPreprocessingList,
} from './render_helpers.js';
import {
    DIRECT_AGREEMENT, RUNNER_STATUS_LABEL, RUNNER_STATUS_STYLE, TRANSFORM_AGREEMENT, UNEXPLAINED, runnerStatus,
} from './run_status.js';
import { AGREEMENT_THRESHOLD_DEFAULTS } from './utils.js';

const FAILURE_HEADINGS = {
    offline: { heading: 'Offline', text: 'runner unreachable' },
    timeout: { heading: 'Timed out', text: null },
    error: { heading: 'Errors', text: null },
};

function _block(heading, styleKey, items) {
    const wrap = document.createElement('div');
    const colors = {
        success: 'bg-green-50 text-green-800 border-green-200',
        divergence: 'bg-yellow-50 text-yellow-800 border-yellow-200',
        anomaly: 'bg-red-50 text-red-700 border-red-200',
        error: 'bg-orange-50 text-orange-900 border-orange-200',
        timeout: 'bg-purple-50 text-purple-900 border-purple-200',
        offline: 'bg-gray-50 text-gray-700 border-gray-200',
    }[styleKey];
    wrap.className = `p-4 border rounded mb-4 ${colors}`;
    const h3 = document.createElement('h3');
    h3.className = 'font-bold';
    h3.textContent = heading;
    wrap.appendChild(h3);
    if (items.length) {
        const ul = document.createElement('ul');
        ul.className = 'list-disc ml-5 mt-2 text-sm space-y-0.5';
        items.forEach(item => {
            const li = document.createElement('li');
            if (typeof item === 'string') li.textContent = item;
            else li.appendChild(item);
            ul.appendChild(li);
        });
        wrap.appendChild(ul);
    }
    return wrap;
}

function _pairItem(p, detail) {
    const frag = document.createDocumentFragment();
    const b = document.createElement('b');
    const [a, c] = p.simulators || ['?', '?'];
    b.textContent = `${_displayRunnerName(a)} × ${_displayRunnerName(c)}`;
    frag.appendChild(b);
    if (detail) frag.appendChild(document.createTextNode(`: ${detail}`));
    return frag;
}

function _orderingNote(p) {
    const ord = p.provenance?.qubit_ordering || {};
    const vals = Object.entries(ord);
    if (vals.length !== 2) return '';
    const text = vals.map(([k, v]) => `${k}=${v ?? 'not declared'}`).join(', ');
    return vals[0][1] && vals[0][1] === vals[1][1]
        ? ` (declared orderings are the same: ${text})`
        : ` (declared: ${text})`;
}

function _tolerances(pairs, data) {
    const recorded = pairs.find(p => p.metrics && p.agreement !== 'not_comparable')?.metrics || {};
    const requested = data.agreement_thresholds || {};
    const pick = key => (typeof recorded[key] === 'number' ? recorded[key]
        : (typeof requested[key] === 'number' ? requested[key] : AGREEMENT_THRESHOLD_DEFAULTS[key]));
    const text = v => (typeof v === 'number' && v !== 0 && Math.abs(v) < 1e-3 ? v.toExponential() : String(v));
    return {
        fidelity: text(pick('fidelity_tolerance')),
        phase: text(pick('phase_tolerance')),
        js: text(pick('js_threshold')),
        hellinger: text(pick('hellinger_threshold')),
    };
}

function _metricText(p) {
    const m = p.metrics || {};
    const t = p.transform_effect || {};
    if (p.mode === 'statevector') {
        const after = t.fidelity_after_transform !== undefined ? `, fidelity after transform ${fmtNum(t.fidelity_after_transform)}` : '';
        return `direct fidelity ${fmtNum(m.direct_fidelity)}${after}`;
    }
    const after = t.js_divergence_after_transform !== undefined ? `; after transform JS ${fmtNum(t.js_divergence_after_transform)} nats` : '';
    return `JS ${fmtNum(m.js_divergence)} nats, Hellinger ${fmtNum(m.hellinger_distance)}${after}`;
}

/** Agreement blocks built from pairwise_agreement[].agreement and the statistical verdicts. */
function _renderAgreementBlocks(panel, data, nOk) {
    const report = data.divergence_report || {};
    const pairs = Array.isArray(report.pairwise_agreement) ? report.pairwise_agreement : [];
    const measured = !!data.n_shots || pairs.some(p => p.mode === 'measured');

    if (nOk < 2) {
        panel.appendChild(_block(`No comparison: ${nOk} backend(s) returned a result`, 'offline',
            ['At least two successful backends are needed for a pairwise comparison.']));
        return;
    }

    if (pairs.length === 0) {
        const divs = Array.isArray(report.divergences_found) ? report.divergences_found : [];
        const items = divs.map(d => `${(d.simulators || []).join(' & ')}: ${d.type}`
            + (d.fidelity !== undefined ? ` (fidelity ${fmtNum(d.fidelity)})` : '')
            + (d.js_divergence !== undefined ? ` (JS ${fmtNum(d.js_divergence)})` : ''));
        panel.appendChild(_block(
            `This report has no pairwise agreement records; ${divs.length} divergence(s) recorded`,
            divs.length ? 'divergence' : 'offline', items));
        return;
    }

    const tol = _tolerances(pairs, data);
    const comparable = pairs.filter(p => p.agreement !== 'not_comparable');
    const direct = pairs.filter(p => DIRECT_AGREEMENT.has(p.agreement));
    const verdictOf = p => p.metrics?.statistical_test?.verdict;
    const alpha = report.statistical_test_summary?.alpha;

    const allDirect = direct.length === pairs.length;
    const allConsistent = !measured || pairs.every(p => verdictOf(p) === 'consistent');
    if (allDirect && allConsistent) {
        let msg;
        if (measured) {
            msg = `All ${pairs.length} pairs are within JS ≤ ${tol.js} nats and Hellinger ≤ ${tol.hellinger}, `
                + `and no pair is statistically distinguishable at α=${alpha ?? '—'} `
                + `(chi-square and G-test, BH-corrected; ${fmtInt(data.n_shots)} shots per backend).`;
        } else {
            const phaseOnly = direct.filter(p => p.agreement === 'agree_up_to_global_phase').length;
            msg = `All ${pairs.length} pairs agree within fidelity tolerance ${tol.fidelity} `
                + `(fidelity ≥ 1 − ${tol.fidelity})`
                + (phaseOnly ? `; ${phaseOnly} of them differ by a global phase larger than ${tol.phase} rad.` : '.');
        }
        const frag = _cloneTemplate('tpl-summary-success-banner');
        frag.querySelector('.tpl-msg').textContent = msg;
        panel.appendChild(frag);
        return;
    }

    const overview = `${direct.length} of ${pairs.length} pairs agree without a transform`
        + (measured ? ` (JS ≤ ${tol.js} nats, Hellinger ≤ ${tol.hellinger})` : ` (fidelity ≥ 1 − ${tol.fidelity})`)
        + `; ${comparable.length} of ${pairs.length} pairs were comparable.`;
    const ov = document.createElement('p');
    ov.className = 'text-sm text-gray-700 mb-3';
    ov.textContent = overview;
    panel.appendChild(ov);

    const unexplained = pairs.filter(p => UNEXPLAINED.has(p.agreement));
    if (unexplained.length) {
        panel.appendChild(_block(`Not explained by any registered transform (${unexplained.length})`, 'anomaly',
            unexplained.map(p => _pairItem(p, `${p.agreement}; ${_metricText(p)}`))));
    }

    const bitrev = pairs.filter(p => p.agreement === 'agree_after_bit_reversal');
    if (bitrev.length) {
        panel.appendChild(_block(`Agree only after reversing bit order (${bitrev.length})`, 'divergence',
            bitrev.map(p => _pairItem(p, `${_metricText(p)}${_orderingNote(p)}`))));
    }

    const perm = pairs.filter(p => p.agreement === 'agree_after_qubit_permutation');
    if (perm.length) {
        panel.appendChild(_block(`Agree only after a qubit permutation (${perm.length})`, 'divergence',
            perm.map(p => _pairItem(p, `permutation ${JSON.stringify(p.transform_effect?.permutation ?? null)}; ${_metricText(p)}`))));
    }

    const norm = pairs.filter(p => p.agreement === 'agree_after_normalization');
    if (norm.length) {
        panel.appendChild(_block(`Agree after normalising an input statevector (${norm.length})`, 'divergence',
            norm.map(p => {
                const norms = p.metrics?.norms || {};
                const text = Object.entries(norms).map(([k, v]) => `${k} norm ${fmtNum(v, 6)}`).join(', ');
                return _pairItem(p, `${text}; label after normalisation: ${p.metrics?.normalized_agreement ?? '—'}`);
            })));
    }

    const other = pairs.filter(p => !DIRECT_AGREEMENT.has(p.agreement) && !TRANSFORM_AGREEMENT.has(p.agreement)
        && !UNEXPLAINED.has(p.agreement) && p.agreement !== 'not_comparable');
    if (other.length) {
        panel.appendChild(_block(`Other labels (${other.length})`, 'divergence',
            other.map(p => _pairItem(p, p.agreement))));
    }

    const notComparable = pairs.filter(p => p.agreement === 'not_comparable');
    if (notComparable.length) {
        panel.appendChild(_block(`Not comparable (${notComparable.length})`, 'offline',
            notComparable.map(p => {
                const details = p.metrics?.details && Object.keys(p.metrics.details).length
                    ? ` (${Object.entries(p.metrics.details).map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : v}`).join('; ')})`
                    : '';
                return _pairItem(p, `${p.metrics?.reason || 'reason not recorded'}${details}`);
            })));
    }

    if (measured) {
        const notConsistent = pairs.filter(p => verdictOf(p) && verdictOf(p) !== 'consistent');
        if (notConsistent.length) {
            const anyDistinguishable = notConsistent.some(p => verdictOf(p) === 'distinguishable');
            panel.appendChild(_block(
                `Shot-noise test at α=${alpha ?? '—'}: ${notConsistent.length} pair(s) not consistent`,
                anyDistinguishable ? 'anomaly' : 'divergence',
                notConsistent.map(p => {
                    const st = p.metrics.statistical_test;
                    return _pairItem(p, `${st.verdict}; χ² p (BH) ${fmtNum(st.chi2?.p_value_bh)}, G-test p (BH) ${fmtNum(st.g_test?.p_value_bh)}`);
                })));
        }
    }
}

function _renderFailures(panel, raws) {
    const byStatus = { offline: [], timeout: [], error: [] };
    raws.forEach(r => {
        const st = runnerStatus(r);
        if (st !== 'ok') byStatus[st].push(r);
    });
    Object.entries(byStatus).forEach(([st, list]) => {
        if (!list.length) return;
        const cfg = FAILURE_HEADINGS[st];
        panel.appendChild(_block(`${cfg.heading} (${list.length})`, RUNNER_STATUS_STYLE[st], list.map(r => {
            const frag = document.createDocumentFragment();
            const b = document.createElement('b');
            b.textContent = _displayRunnerName(r.simulator);
            frag.appendChild(b);
            frag.appendChild(document.createTextNode(`: ${cfg.text || r.error || RUNNER_STATUS_LABEL[st]}`));
            return frag;
        })));
    });
}

function _kv(parent, key, value) {
    if (value === undefined || value === null || value === '') return;
    const row = document.createElement('div');
    const k = document.createElement('span');
    k.className = 'text-gray-400';
    k.textContent = `${key}: `;
    const v = document.createElement('span');
    v.className = 'font-mono text-gray-800 break-words';
    v.textContent = typeof value === 'object' ? JSON.stringify(value) : String(value);
    row.appendChild(k);
    row.appendChild(v);
    parent.appendChild(row);
}

/** Run configuration and per-backend details: status, precision, seeds, memory method, threads, preprocessing. */
function _renderRunDetails(panel, data, raws) {
    const details = document.createElement('details');
    details.className = 'mt-4 border rounded bg-white';
    const summary = document.createElement('summary');
    summary.className = 'px-3 py-2 cursor-pointer text-sm font-semibold text-gray-700 select-none';
    summary.textContent = 'Run details per backend (precision, seeds, preprocessing)';
    details.appendChild(summary);

    const body = document.createElement('div');
    body.className = 'px-3 pb-3 text-xs text-gray-700 space-y-3';

    const top = document.createElement('div');
    top.className = 'space-y-0.5';
    _kv(top, 'master seed', data.seed);
    _kv(top, 'per-runner seed derivation', data.seed_derivation);
    _kv(top, 'n_shots', data.n_shots);
    _kv(top, 'apply_preprocessing', data.apply_preprocessing);
    _kv(top, 'started', data.started_at);
    _kv(top, 'finished', data.finished_at);
    if (Array.isArray(data.api_preprocessing_applied)) {
        const label = document.createElement('div');
        label.className = 'text-gray-400';
        label.textContent = 'applied by the API before dispatch:';
        top.appendChild(label);
        top.appendChild(renderPreprocessingList(data.api_preprocessing_applied.map(e => (String(e).startsWith('API:') ? e : `API: ${e}`))));
    }
    if (Array.isArray(data.dispatched_circuits) && data.dispatched_circuits.length > 1) {
        _kv(top, 'dispatched circuits', data.dispatched_circuits.map(c => `${c.group}: ${(c.runners || []).join(', ')}`).join('; '));
    }
    body.appendChild(top);

    raws.forEach(r => {
        const card = document.createElement('div');
        card.className = 'border-t border-gray-100 pt-2';
        const head = document.createElement('div');
        head.className = 'flex flex-wrap items-center gap-1 font-medium text-gray-900';
        head.appendChild(document.createTextNode(_displayRunnerName(r.simulator)));
        const st = runnerStatus(r);
        head.appendChild(_chip(STATUS_STYLES[RUNNER_STATUS_STYLE[st]].badge, RUNNER_STATUS_LABEL[st], 'Dispatch status'));
        const prec = precisionTag(r.precision);
        if (prec) head.appendChild(prec);
        card.appendChild(head);

        const grid = document.createElement('div');
        grid.className = 'grid grid-cols-1 sm:grid-cols-2 gap-x-4 mt-1';
        _kv(grid, 'qubit ordering', r.qubit_ordering);
        _kv(grid, 'sampling method', r.sampling_method);
        _kv(grid, 'runner seed', r.runner_seed);
        if (r.runner_seed !== undefined && r.seed_honoured === false) {
            _kv(grid, 'seed honoured', 'no: this backend ignores the seed, so its counts are not reproducible');
        }
        _kv(grid, 'dispatch group', r.dispatch_group);
        _kv(grid, 'timed runs', r.timing_samples);
        _kv(grid, 'window memory method', r.memory_method);
        _kv(grid, 'process peak method', r.process_peak_rss_method);
        if (r.thread_env) {
            _kv(grid, 'thread env', Object.entries(r.thread_env).map(([k, v]) => `${k}=${v ?? 'unset'}`).join(', '));
        }
        if (r.statevector_omitted_for_display) {
            _kv(grid, 'statevector', 'not in this browser copy (over 14 qubits); in the server copy of the job');
        }
        card.appendChild(grid);

        if (st === 'ok' || Array.isArray(r.preprocessing_applied)) {
            const label = document.createElement('div');
            label.className = 'text-gray-400 mt-1';
            label.textContent = 'preprocessing:';
            card.appendChild(label);
            card.appendChild(renderPreprocessingList(r.preprocessing_applied));
        }
        body.appendChild(card);
    });

    details.appendChild(body);
    panel.appendChild(details);
}

export function renderSummaryPanel(data, title) {
    const panel = panelElements.summary;
    if (!panel) return;
    panel.innerHTML = '';

    const h2 = document.createElement('h2');
    h2.className = 'text-xl font-semibold text-gray-900 mb-4';
    h2.textContent = title;
    panel.appendChild(h2);

    const legendFrag = _cloneTemplate('tpl-legend-suite');
    _applyLegendDots(legendFrag);
    panel.appendChild(legendFrag);

    if (data.error) {
        const errFrag = _cloneTemplate('tpl-summary-api-error');
        errFrag.querySelector('.tpl-error-text').textContent = data.error;
        panel.appendChild(errFrag);
        return;
    }

    const raws = Array.isArray(data.raw_results) ? data.raw_results : [];
    _renderFailures(panel, raws);
    _renderAgreementBlocks(panel, data, raws.filter(r => runnerStatus(r) === 'ok').length);
    _renderRunDetails(panel, data, raws);
}
