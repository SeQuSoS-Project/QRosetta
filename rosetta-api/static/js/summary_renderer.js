// Summary tab of a single-circuit report: which backends ran, failed runs by status, what
// the pairwise agreement records show, and per-backend run details.

import { panelElements } from './dom.js';
import {
    STATUS_STYLES, _applyLegendDots, _chip, _cloneTemplate, _displayRunnerName, fmtInt, fmtNum, fmtPValue, fmtProb,
    executionTags, precisionTag, queueWaitText, renderPreprocessingList, throttleText, outsideProcessText,
} from './render_helpers.js';
import { getEnabledRunnerIds } from './config.js';
import { parseRunnerKey } from './runner_key.js';
import {
    RUNNER_STATUS_LABEL, RUNNER_STATUS_STYLE, adjustedPValue, correctionLongName, correctionName, effectiveAgreement,
    measuredAssessment, pairPower, pairPowerLevel, recommendedShots, resolvableByMoreShots, runnerStatus,
    statevectorGroup, unalignedBasis, unalignedBasisMatch, userFacingError,
} from './run_status.js';
import { thresholdDefaults } from './utils.js';

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
        if (items.length > 12) {
            const det = document.createElement('details');
            det.className = 'mt-2 text-sm';
            const sum = document.createElement('summary');
            sum.className = 'cursor-pointer select-none';
            sum.textContent = `Show all ${items.length}`;
            det.appendChild(sum);
            det.appendChild(ul);
            wrap.appendChild(det);
        } else {
            wrap.appendChild(ul);
        }
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
    const defaults = thresholdDefaults();
    const pick = key => (typeof recorded[key] === 'number' ? recorded[key]
        : (typeof requested[key] === 'number' ? requested[key] : defaults[key]));
    const text = v => (typeof v === 'number' && v !== 0 && Math.abs(v) < 1e-3 ? v.toExponential() : String(v));
    return {
        fidelity: text(pick('fidelity_tolerance')),
        phase: text(pick('phase_tolerance')),
        norm: text(pick('norm_tolerance')),
        js: text(pick('js_threshold')),
        hellinger: text(pick('hellinger_threshold')),
    };
}

const TRANSFORM_NAMES = {
    agree_directly: 'direct',
    agree_up_to_global_phase: 'direct',
    agree_after_bit_reversal: 'bit-reversed',
    agree_after_qubit_permutation: 'permuted',
};

/** Fidelity under the transform the pair's label names, with the direct value when it differs. */
function _statevectorMetricText(p) {
    const m = p.metrics || {};
    const t = p.transform_effect || {};
    const label = effectiveAgreement(p);
    let named = null;
    if (label === 'agree_after_bit_reversal') named = m.bit_reversed_fidelity ?? t.fidelity_after_transform;
    else if (label === 'agree_after_qubit_permutation') named = m.qubit_permutation?.fidelity ?? t.fidelity_after_transform;
    const direct = `direct fidelity ${fmtNum(m.direct_fidelity)}`;
    if (named !== null && named !== undefined) {
        const phase = label === 'agree_after_bit_reversal' && t.global_phase_aligned
            ? `, global phase offset ${fmtNum(t.relative_phase_after_transform_rad ?? m.label_aligned_relative_phase_rad)} rad` : '';
        return `${TRANSFORM_NAMES[label]} fidelity ${fmtNum(named)}${phase} (${direct})`;
    }
    if (label === 'residual_disagreement') {
        const parts = [direct, `bit-reversed ${fmtNum(m.bit_reversed_fidelity)}`];
        if (m.qubit_permutation?.attempted) parts.push(`best permutation ${fmtNum(m.qubit_permutation.fidelity)}`);
        return parts.join(', ');
    }
    const phase = m.direct_relative_phase_rad;
    return `${direct}${typeof phase === 'number' && phase !== 0 ? `, global phase offset arg⟨a|b⟩ ${fmtNum(phase)} rad` : ''}`;
}

function _measuredMetricText(p) {
    const m = p.metrics || {};
    const t = p.transform_effect || {};
    const direct = `JS ${fmtNum(m.js_divergence)} nats, Hellinger ${fmtNum(m.hellinger_distance)}`;
    if (p.agreement === 'agree_after_qubit_permutation' && t.js_divergence_after_transform !== undefined) {
        return `permuted JS ${fmtNum(t.js_divergence_after_transform)} nats, Hellinger `
            + `${fmtNum(t.hellinger_distance_after_transform)} (direct ${direct})`;
    }
    if (m.label_aligned_basis === 'bit_reversal' && typeof m.label_aligned_js_divergence === 'number') {
        return `label-aligned (bit-reversed) JS ${fmtNum(m.label_aligned_js_divergence)} nats, Hellinger `
            + `${fmtNum(m.label_aligned_hellinger_distance)} (direct ${direct})`;
    }
    if (p.agreement === 'agree_after_bit_reversal' && t.js_divergence_after_transform !== undefined) {
        return `bit-reversed JS ${fmtNum(t.js_divergence_after_transform)} nats, Hellinger `
            + `${fmtNum(t.hellinger_distance_after_transform)} (direct ${direct})`;
    }
    return direct;
}

/** True when a measured pair's distance label agrees in the basis its declared bit orders select. */
function _agreesInLabelAlignedBasis(p) {
    const basis = p.metrics?.label_aligned_basis;
    if (p.agreement === 'distance_within_threshold') return basis !== 'bit_reversal';
    if (p.agreement === 'agree_after_bit_reversal') return basis === 'bit_reversal';
    return false;
}

/** The descriptive JS/Hellinger label of a measured pair, as secondary detail beside its assessment. */
function _distanceLabelText(p) {
    const basis = p.metrics?.label_aligned_basis;
    const perm = p.transform_effect?.permutation ?? p.metrics?.qubit_permutation?.permutation;
    switch (p.agreement) {
        case 'distance_within_threshold':
            return basis === 'bit_reversal'
                ? `within the JS/Hellinger thresholds only without reversing bit order, although the declared orderings differ${_orderingNote(p)}`
                : 'within the JS/Hellinger thresholds';
        case 'agree_after_bit_reversal':
            return basis === 'bit_reversal'
                ? 'agree in the label-aligned (bit-reversed) basis'
                : `within the thresholds only after reversing bit order${_orderingNote(p)}`;
        case 'agree_after_qubit_permutation':
            return `within the thresholds only after qubit permutation ${JSON.stringify(perm ?? null)}`;
        case 'distance_exceeds_threshold':
            return 'above the JS/Hellinger thresholds under every registered transform';
        default:
            return String(p.agreement);
    }
}

function _metricText(p) {
    return p.mode === 'statevector' ? _statevectorMetricText(p) : _measuredMetricText(p);
}

function _testText(p) {
    const st = p.metrics?.statistical_test;
    if (!st) return '';
    const c = correctionName(st);
    const weak = st.verdict === 'distinguishable' && st.significant_fwer === false
        ? '; significant under BY only, not under Holm\'s family-wise correction: other pairs\' discoveries lowered the bar for this one'
        : '';
    return `; χ² p (${c}) ${fmtPValue(adjustedPValue(st.chi2))}, G-test p (${c}) ${fmtPValue(adjustedPValue(st.g_test))}${weak}`;
}

function _powerText(p) {
    const power = pairPower(p);
    if (power === null) return '';
    const delta = p.metrics?.statistical_test?.power?.delta_tv;
    return `; power ${fmtProb(power)} to detect a TV gap of ${typeof delta === 'number' ? fmtNum(delta) : '—'}`;
}

/** Significance level the power figures of these pairs were computed at. */
function _powerLevelText(pairs) {
    const lvl = pairs.map(pairPowerLevel).find(l => l.alphaUsed !== null);
    if (lvl) {
        const m = lvl.m !== null ? `, m = ${fmtInt(lvl.m)} tested pairs` : '';
        const cm = lvl.cm !== null ? `, c_m = ${fmtNum(lvl.cm)}` : '';
        const level = lvl.cm !== null ? 'α/(m·c_m)' : 'α/m';
        return `Power is computed for a single test at ${level} = ${fmtNum(lvl.alphaUsed)} (α = ${lvl.alpha ?? '—'}${m}${cm}).`;
    }
    const alpha = pairs.map(pairPowerLevel).find(l => l.alpha !== null)?.alpha;
    return `This report records no adjusted significance level, so power is shown at the unadjusted α = ${alpha ?? '—'}.`;
}

function _measuredItem(p, { power = true } = {}) {
    return _pairItem(p, `${_metricText(p)}; distance label: ${_distanceLabelText(p)}${_testText(p)}${power ? _powerText(p) : ''}`);
}

function _note(block, text) {
    const note = document.createElement('p');
    note.className = 'text-sm mt-2';
    note.textContent = text;
    block.insertBefore(note, block.querySelector('details, ul'));
}

function _notComparableBlock(panel, pairs) {
    const notComparable = pairs.filter(p => p.agreement === 'not_comparable');
    if (!notComparable.length) return;
    panel.appendChild(_block(`Not comparable (${notComparable.length})`, 'offline',
        notComparable.map(p => {
            const details = p.metrics?.details && Object.keys(p.metrics.details).length
                ? ` (${Object.entries(p.metrics.details).map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : v}`).join('; ')})`
                : '';
            return _pairItem(p, `${p.metrics?.reason || 'reason not recorded'}${details}`);
        })));
}

/** Why a statevector pair in the disagreement group disagrees, followed by its metrics. */
function _disagreementText(p) {
    if (unalignedBasisMatch(p)) {
        const basis = { direct: 'the direct basis', bit_reversal: 'the bit-reversed basis' }[unalignedBasis(p)] || 'a basis';
        return `matches only in ${basis}, which the declared orderings do not imply${_orderingNote(p)}; ${_metricText(p)}`;
    }
    if (effectiveAgreement(p) === 'agree_after_qubit_permutation') {
        const perm = p.transform_effect?.permutation ?? p.metrics?.qubit_permutation?.permutation ?? null;
        return `agrees only after an undeclared qubit permutation ${JSON.stringify(perm)}; ${_metricText(p)}`;
    }
    return `no registered transform explains the difference; ${_metricText(p)}`;
}

/** Statevector pairs: agreement, bit order as declared, disagreements, normalisation notes. */
function _renderStatevectorBlocks(panel, pairs, tol) {
    const byGroup = { agree: [], bit_order: [], disagree: [], not_comparable: [], other: [] };
    pairs.forEach(p => byGroup[statevectorGroup(p)].push(p));
    const direct = byGroup.agree.filter(p => effectiveAgreement(p) === 'agree_directly');
    const phase = byGroup.agree.filter(p => effectiveAgreement(p) === 'agree_up_to_global_phase');
    const bitOrder = byGroup.bit_order;
    const disagree = byGroup.disagree;
    const comparable = pairs.filter(p => p.agreement !== 'not_comparable');
    const normalised = pairs.filter(p => p.agreement === 'agree_after_normalization' && statevectorGroup(p) !== 'disagree');

    const allAgree = byGroup.agree.length + bitOrder.length === pairs.length;
    const criterion = `fidelity ≥ 1 − ${tol.fidelity}, phase tolerance ${tol.phase} rad`;
    if (allAgree) {
        let msg = `All ${pairs.length} pairs agree (${criterion})`;
        const parts = [];
        if (bitOrder.length) parts.push(`${bitOrder.length} after the bit reversal their declared orderings imply`);
        if (phase.length) parts.push(`${phase.length} up to a global phase larger than ${tol.phase} rad`);
        msg += parts.length ? `; ${parts.join(', ')}.` : '.';
        if (normalised.length) msg += ` ${normalised.length} pair(s) involve a statevector whose norm differs from 1 by more than ${tol.norm}; see below.`;
        const frag = _cloneTemplate('tpl-summary-success-banner');
        frag.querySelector('.tpl-msg').textContent = msg;
        panel.appendChild(frag);
    } else {
        const ov = document.createElement('p');
        ov.className = 'text-sm text-gray-700 mb-3';
        ov.textContent = `Of ${pairs.length} pairs: ${direct.length} agree directly, ${phase.length} up to a global phase, `
            + `${bitOrder.length} after the bit reversal their declared orderings imply, ${disagree.length} disagree `
            + `(${criterion}); ${comparable.length} of ${pairs.length} pairs were comparable.`;
        panel.appendChild(ov);
    }

    if (disagree.length) {
        const block = _block(`Disagree (${disagree.length})`, 'anomaly', disagree.map(p => _pairItem(p, _disagreementText(p))));
        _note(block, 'A pair disagrees when no registered transform explains the difference, when it agrees only after an '
            + 'undeclared qubit permutation, or when it matches only in the basis the declared qubit orderings do not imply. '
            + 'The report does not decide which backend is wrong; check against an independent reference.');
        panel.appendChild(block);
    }
    if (bitOrder.length) {
        panel.appendChild(_block(`Agree after the bit reversal the declared orderings imply (${bitOrder.length})`, 'divergence',
            bitOrder.map(p => _pairItem(p, `${_metricText(p)}${_orderingNote(p)}`))));
    }
    if (phase.length) {
        panel.appendChild(_block(`Agree up to a global phase offset larger than ${tol.phase} rad (${phase.length})`, 'success',
            phase.map(p => _pairItem(p, _metricText(p)))));
    }

    if (normalised.length) {
        panel.appendChild(_block(`Agree after normalising a statevector whose norm is off by more than ${tol.norm} (${normalised.length})`, 'success',
            normalised.map(p => {
                const norms = p.metrics?.norms || {};
                const text = Object.entries(norms).map(([k, v]) => `${_displayRunnerName(k)} norm ${fmtNum(v, 8)}`).join(', ');
                return _pairItem(p, `${text}; after normalisation: ${p.metrics?.normalized_agreement ?? '—'}, ${_metricText(p)}`);
            })));
    }

    if (byGroup.other.length) {
        panel.appendChild(_block(`Other labels (${byGroup.other.length})`, 'divergence', byGroup.other.map(p => _pairItem(p, p.agreement))));
    }
    _notComparableBlock(panel, pairs);
}

/** Inconclusive pairs by cause: low power, expected counts more shots can raise, outcomes too rare at any shot count. */
function _inconclusiveBlocks(panel, pairs) {
    const target = pairs[0]?.metrics?.statistical_test?.power?.target_power ?? 0.8;
    const reason = p => p.metrics?.statistical_test?.inconclusive_reason;
    const uncharacterised = pairs.filter(p => p.metrics?.statistical_test?.support_characterised === false);
    const characterised = pairs.filter(p => p.metrics?.statistical_test?.support_characterised !== false);
    const lowPower = characterised.filter(p => reason(p) === 'low_power');
    const rest = characterised.filter(p => reason(p) !== 'low_power');
    const tooRare = rest.filter(p => resolvableByMoreShots(p) === false);
    const lowCounts = rest.filter(p => resolvableByMoreShots(p) !== false);
    const pooling = rest.some(p => p.metrics?.statistical_test?.pooled_outcomes !== undefined) ? ' even after pooling rare outcomes' : '';

    if (uncharacterised.length) {
        const unseen = Math.max(...uncharacterised.map(p => p.metrics.statistical_test.unseen_mass_good_turing ?? 0));
        const block = _block(`Inconclusive, the sample does not yet show the outcome distribution (${uncharacterised.length})`, 'offline',
            uncharacterised.map(p => _measuredItem(p)));
        _note(block, `Outcomes seen only once carry up to ${fmtProb(unseen)} of the shots (Good–Turing estimate of the probability of `
            + 'outcomes not yet seen), so the outcome distribution is spread over more outcomes than the sample covers. No shot '
            + 'count can be recommended from it, and the number needed may exceed the platform maximum. Measuring fewer qubits '
            + '(only the ones of interest) gives the test a distribution it can resolve.');
        panel.appendChild(block);
    }
    if (lowPower.length) {
        const rec = recommendedShots(lowPower);
        const pooledPairs = lowPower.some(p => (p.metrics?.statistical_test?.power?.pooled_probability ?? 0) > 0
            || p.metrics?.statistical_test?.recommendation_is_lower_bound === true);
        const advice = rec ? `: more shots would help: ${pooledPairs ? 'at least ' : ''}~${fmtInt(rec)} per backend` : '';
        const block = _block(`Inconclusive, test power below ${target} (${lowPower.length})${advice}`, 'offline',
            lowPower.map(p => _measuredItem(p)));
        _note(block, 'Neither test finds a significant difference, but the power to detect the target gap is below '
            + `${target}, so these pairs are neither consistent nor in disagreement. ${_powerLevelText(lowPower)}`
            + (rec ? ` The power model reaches ${target} at about ${fmtInt(rec)} shots per backend.` : '')
            + (pooledPairs ? ' Rare outcomes were pooled for some of these pairs; the recommendation assumes the outcomes seen so far '
                + 'are all there are, so with more shots new outcomes can appear and raise it.' : ''));
        panel.appendChild(block);
    }
    if (lowCounts.length) {
        const block = _block(`Inconclusive, expected counts below 5${pooling} (${lowCounts.length}): more shots would help`, 'offline',
            lowCounts.map(p => _measuredItem(p)));
        _note(block, 'Some outcomes are too rare in this sample for the chi-square and G-test to be reliable, so the tests '
            + 'cannot decide either way.');
        panel.appendChild(block);
    }
    if (tooRare.length) {
        const block = _block(`Inconclusive, outcomes too rare for the test at any practical shot count (${tooRare.length})`, 'offline',
            tooRare.map(p => _measuredItem(p)));
        _note(block, `Expected counts stay below 5${pooling}, and the report records that more shots would not change `
            + 'this at a practical shot count. The distance label and the metrics are the available evidence for these pairs.');
        panel.appendChild(block);
    }
}

/**
 * Measured pairs grouped only by their shot-noise assessment, so each pair appears in one
 * group; the descriptive distance label is shown as detail. Only "distinguishable" is a
 * disagreement.
 */
function _renderMeasuredBlocks(panel, pairs, tol, data, alpha) {
    const groups = { consistent_within_shot_noise: [], inconclusive_low_shots: [], distinguishable: [], ambiguous: [], untested: [] };
    pairs.forEach(p => {
        if (p.agreement === 'not_comparable') return;
        const a = measuredAssessment(p);
        (groups[a] || groups.untested).push(p);
    });
    const comparable = pairs.filter(p => p.agreement !== 'not_comparable');
    const shots = data.n_shots ? `${fmtInt(data.n_shots)} shots per backend` : 'shots per backend not recorded';
    const corr = correctionName(data.divergence_report?.statistical_test_summary,
        pairs.find(p => p.metrics?.statistical_test)?.metrics?.statistical_test);
    const test = `chi-square and G-test, ${corr}-corrected at α=${alpha ?? '—'}; ${shots}`;

    const allConsistent = comparable.length === pairs.length
        && groups.consistent_within_shot_noise.length === pairs.length
        && pairs.every(_agreesInLabelAlignedBasis);
    if (allConsistent) {
        const frag = _cloneTemplate('tpl-summary-success-banner');
        frag.querySelector('.tpl-msg').textContent = `All ${pairs.length} pairs are consistent within shot noise (${test}) `
            + `and within JS ≤ ${tol.js} nats and Hellinger ≤ ${tol.hellinger} in the label-aligned basis. `
            + 'Consistent means the tests found no difference at the stated power; it does not show the distributions are equal. '
            + _powerLevelText(pairs);
        panel.appendChild(frag);
        return;
    }

    const ov = document.createElement('p');
    ov.className = 'text-sm text-gray-700 mb-3';
    const parts = [
        `${groups.consistent_within_shot_noise.length} consistent within shot noise`,
        `${groups.inconclusive_low_shots.length} inconclusive (low power or rare outcomes)`,
        `${groups.distinguishable.length} distinguishable`,
    ];
    if (groups.ambiguous.length) parts.push(`${groups.ambiguous.length} inconclusive (the two tests disagree)`);
    if (groups.untested.length) parts.push(`${groups.untested.length} without a shot-noise test`);
    ov.textContent = `Of ${pairs.length} pairs: ${parts.join(', ')}; ${pairs.length - comparable.length} not comparable (${test}). `
        + 'Each pair is listed once, under its shot-noise assessment; the JS/Hellinger distance label is shown beside it.';
    panel.appendChild(ov);

    if (groups.distinguishable.length) {
        const block = _block(`Distinguishable beyond shot noise (${groups.distinguishable.length})`, 'anomaly',
            groups.distinguishable.map(p => _measuredItem(p, { power: false })));
        _note(block, corr === 'BY'
            ? `The Benjamini–Yekutieli correction controls the false discovery rate at q = ${alpha ?? '—'} under any dependence `
                + 'between the tests, including pairs that share a backend and so share its sample. On average up to that '
                + 'fraction of the flagged pairs are flagged by chance, so a few flagged pairs among many can be false '
                + 'discoveries; flags that all involve one backend can come from one unusual sample of that backend.'
            : `The ${correctionLongName(corr)} correction controls the false discovery rate at q = ${alpha ?? '—'} for `
                + 'independent or positively dependent (PRDS) tests; pairs that share a backend share its sample and are '
                + 'dependent. A few flagged pairs among many can be false discoveries.');
        panel.appendChild(block);
    }
    if (groups.ambiguous.length) {
        panel.appendChild(_block(`Inconclusive: the chi-square and G-test disagree (${groups.ambiguous.length})`, 'offline',
            groups.ambiguous.map(p => _measuredItem(p, { power: false }))));
    }
    if (groups.untested.length) {
        const exceeds = groups.untested.filter(p => p.agreement === 'distance_exceeds_threshold');
        const rest = groups.untested.filter(p => p.agreement !== 'distance_exceeds_threshold');
        if (exceeds.length) {
            panel.appendChild(_block(`Above the JS/Hellinger thresholds, no shot-noise test recorded (${exceeds.length})`, 'anomaly',
                exceeds.map(p => _pairItem(p, _metricText(p)))));
        }
        if (rest.length) {
            panel.appendChild(_block(`No shot-noise test recorded (${rest.length})`, 'offline',
                rest.map(p => _pairItem(p, `${_distanceLabelText(p)}; ${_metricText(p)}`))));
        }
    }
    if (groups.inconclusive_low_shots.length) _inconclusiveBlocks(panel, groups.inconclusive_low_shots);

    const consistent = groups.consistent_within_shot_noise;
    if (consistent.length) {
        const aboveThreshold = consistent.filter(p => !_agreesInLabelAlignedBasis(p)).length;
        const powers = consistent.map(pairPower).filter(v => v !== null);
        const block = _block(`Consistent within shot noise (${consistent.length})`, 'success',
            consistent.map(p => _measuredItem(p)));
        const notes = [];
        if (powers.length) {
            const lo = Math.min(...powers), hi = Math.max(...powers);
            const range = fmtProb(lo) === fmtProb(hi) ? fmtProb(lo) : `${fmtProb(lo)}–${fmtProb(hi)}`;
            notes.push(`Test power ${range} to detect a total-variation gap of `
                + `${consistent[0].metrics?.statistical_test?.power?.delta_tv ?? '—'}; power is the chance the test would flag a gap of that size. `
                + _powerLevelText(consistent));
        }
        if (aboveThreshold) {
            notes.push(`${aboveThreshold} of these do not meet the descriptive JS ≤ ${tol.js} / Hellinger ≤ ${tol.hellinger} thresholds in the label-aligned basis; those thresholds depend on the shot count, and the test finds no difference beyond shot noise.`);
        }
        notes.forEach(t => _note(block, t));
        panel.appendChild(block);
    }
    _notComparableBlock(panel, pairs);
}

/** Agreement blocks built from pairwise_agreement[] and the shot-noise assessments. */
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
    if (measured) _renderMeasuredBlocks(panel, pairs, tol, data, report.statistical_test_summary?.alpha);
    else _renderStatevectorBlocks(panel, pairs, tol);
}

/** "N of M enabled backends ran", with the enabled backends that were not part of the run. */
function _renderCoverage(panel, raws) {
    const ranIds = [...new Set(raws.map(r => parseRunnerKey(r.simulator).simId))];
    const okIds = new Set(raws.filter(r => runnerStatus(r) === 'ok').map(r => parseRunnerKey(r.simulator).simId));
    const enabled = getEnabledRunnerIds();
    const p = document.createElement('p');
    p.className = 'text-sm text-gray-700 mb-3';
    if (enabled.length === 0) {
        p.textContent = `${ranIds.length} backend(s) ran; ${okIds.size} returned a result.`;
        panel.appendChild(p);
        return;
    }
    const ranEnabled = ranIds.filter(id => enabled.includes(id));
    const skipped = enabled.filter(id => !ranIds.includes(id));
    let text = `${ranEnabled.length} of ${enabled.length} enabled backends ran; ${okIds.size} returned a result.`;
    if (skipped.length) text += ` Not in this run: ${skipped.map(_displayRunnerName).join(', ')}.`;
    p.textContent = text;
    panel.appendChild(p);
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
            const why = r.never_started
                ? 'queued and never started: the runner was busy with other runs for the whole wait budget'
                : (cfg.text || userFacingError(r.error) || RUNNER_STATUS_LABEL[st]);
            frag.appendChild(document.createTextNode(`: ${why}`));
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
    summary.textContent = 'Run details per backend (device, precision, seeds, queue wait, preprocessing)';
    details.appendChild(summary);

    const body = document.createElement('div');
    body.className = 'px-3 pb-3 text-xs text-gray-700 space-y-3';

    const top = document.createElement('div');
    top.className = 'space-y-0.5';
    _kv(top, 'master seed', data.seed);
    _kv(top, 'per-runner seed derivation', data.seed_derivation);
    _kv(top, 'n_shots', data.n_shots);
    _kv(top, 'apply_preprocessing', data.apply_preprocessing);
    _kv(top, 'analysis version', data.analysis_version ?? data.divergence_report?.analysis_version);
    _kv(top, 'git commit', data.git_sha);
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
        executionTags(r).forEach(tag => head.appendChild(tag));
        card.appendChild(head);

        const grid = document.createElement('div');
        grid.className = 'grid grid-cols-1 sm:grid-cols-2 gap-x-4 mt-1';
        _kv(grid, 'device', r.device);
        _kv(grid, 'GPU', r.gpu_name);
        if (typeof r.custatevec_enabled === 'boolean') _kv(grid, 'cuStateVec', r.custatevec_enabled ? 'enabled' : 'not enabled');
        _kv(grid, 'simulator backend', r.simulator_backend);
        _kv(grid, 'simulation method', r.simulation_method);
        const wait = queueWaitText(r);
        if (wait) _kv(grid, 'queue wait', wait);
        if (r.never_started) _kv(grid, 'started', 'no: the run stayed queued until its wait budget ran out');
        if (r.timed_out) _kv(grid, 'timed out', 'yes');
        _kv(grid, 'qubit ordering', r.qubit_ordering);
        _kv(grid, 'sampling method', r.sampling_method);
        _kv(grid, 'runner seed', r.runner_seed);
        if (r.runner_seed !== undefined && r.seed_honoured === false) {
            _kv(grid, 'seed honoured', 'no: this backend ignores the seed, so its counts are not reproducible');
        }
        _kv(grid, 'dispatch group', r.dispatch_group);
        if (typeof r.concurrent_runs === 'number') _kv(grid, 'dispatched with', `${r.concurrent_runs - 1} other run(s) in the same phase (phase ${r.dispatch_phase ?? 1})`);
        if (typeof r.overlapping_runs === 'number') _kv(grid, 'overlapped with', `${r.overlapping_runs} other run(s) of this job while it ran`);
        if (typeof r.server_overlapping_runs === 'number') _kv(grid, 'other jobs', `${r.server_overlapping_runs} run(s) of other jobs in flight (dispatched or queued) while it ran`);
        if (r.exclusive === true) _kv(grid, 'exclusive', `yes; waited ${fmtNum(r.exclusive_wait_sec ?? 0, 1)} s for the server to be idle`);
        _kv(grid, 'timed runs', r.timing_samples);
        const env = r.cpu_environment;
        if (env) {
            _kv(grid, 'host CPU', env.cpu_model);
            _kv(grid, 'CPU quota', typeof env.cpu_quota_cores === 'number' ? `${fmtNum(env.cpu_quota_cores, 2)} CPU` : 'none');
            const mhz = env.cpu_max_mhz || {};
            if (Array.isArray(r.simulation_cpus) && r.simulation_cpus.length) {
                _kv(grid, 'simulation CPUs', r.simulation_cpus.map(c => (mhz[c] ? `${c} (max ${fmtInt(mhz[c])} MHz)` : String(c))).join(', '));
            }
        }
        if (typeof r.simulation_cgroup_cpu_time_sec === 'number') {
            _kv(grid, 'container CPU in simulation window', outsideProcessText(r) || `${fmtNum(r.simulation_cgroup_cpu_time_sec, 4)} s (matches the process)`);
        }
        if (typeof r.simulation_throttled_sec === 'number') {
            _kv(grid, 'throttled in simulation window', throttleText(r) || `${fmtNum(r.simulation_throttled_sec, 4)} s`);
        }
        _kv(grid, 'window memory method', r.memory_method);
        _kv(grid, 'runner code sha256', r.runner_code_sha256);
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
        errFrag.querySelector('.tpl-error-text').textContent = userFacingError(data.error);
        panel.appendChild(errFrag);
        return;
    }

    if (data.job_error) {
        panel.appendChild(_block('The job failed', 'anomaly', [userFacingError(data.job_error)]));
    }
    const raws = Array.isArray(data.raw_results) ? data.raw_results : [];
    _renderCoverage(panel, raws);
    _renderFailures(panel, raws);
    _renderAgreementBlocks(panel, data, raws.filter(r => runnerStatus(r) === 'ok').length);
    _renderRunDetails(panel, data, raws);
}
