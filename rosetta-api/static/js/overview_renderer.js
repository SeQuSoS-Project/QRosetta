// Top of the Summary tab: a headline naming the backends that differ from others and the
// ones that failed, next steps the report supports, and one row per backend with its counts.

import { MAX_NAMED, backendVerdicts, headlineModel } from './backend_verdicts.js';
import { labelDefinition, labelText } from './labels.js';
import { STATUS_STYLES, _chip, _displayRunnerName, bitOrderTag, fmtInt, fmtNum, precisionTag } from './render_helpers.js';
import { RUNNER_STATUS_LABEL, RUNNER_STATUS_STYLE, pairRecommendation, recommendedShots, runnerStatus } from './run_status.js';
import { parseRunnerKey } from './runner_key.js';
import { getState } from './state.js';
import { setTip } from './tooltip.js';

function _list(items) {
    if (items.length <= 1) return items.join('');
    if (items.length === 2) return `${items[0]} and ${items[1]}`;
    return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`;
}

function _names(keys) {
    const names = keys.map(_displayRunnerName);
    return names.length <= MAX_NAMED ? _list(names)
        : `${names.slice(0, MAX_NAMED).join(', ')} and ${names.length - MAX_NAMED} more`;
}

const _plural = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`;
const _cap = s => (s.startsWith('all ') ? `A${s.slice(1)}` : s);

/** "backend" or "run": a multi-run report compares runs, several of them on one backend. */
export function unitNoun(verdicts) {
    return verdicts.multiRun ? 'run' : 'backend';
}

/** Fidelity or total variation for the headline: three decimals, or scientific notation near 1 or 0. */
function _fidelityText(f) {
    return f < 0.999 ? `lowest fidelity ${f.toFixed(3)}` : `lowest fidelity 1 − ${(1 - f).toExponential(1)}`;
}

function _tvText(tv) {
    return `largest total variation ${tv >= 0.01 ? tv.toFixed(3) : tv.toExponential(1)}`;
}

/** Worst difference over backends' differing pairs: "lowest fidelity …" or "largest total variation …", or ''. */
function _magnitude(backends, measured) {
    if (measured) {
        const tvs = backends.map(b => b.largestTv).filter(x => x !== null);
        return tvs.length ? _tvText(Math.max(...tvs)) : '';
    }
    const fs = backends.map(b => b.worstFidelity).filter(x => x !== null);
    return fs.length ? _fidelityText(Math.min(...fs)) : '';
}

function _detail(backends, measured) {
    const parts = [];
    if (measured && backends.length === 1) {
        const b = backends[0];
        if (b.differsFull) parts.push(`${b.differsFull} distinguishable`);
        if (b.differsMarginal) parts.push(`${b.differsMarginal} with a differing single-bit marginal`);
    }
    const size = _magnitude(backends, measured);
    if (size) parts.push(size);
    return parts.length ? ` (${parts.join('; ')})` : '';
}

function _differsPhrase(b, measured, noun) {
    const n = b.differsWith.length;
    const what = n === b.compared ? `all ${_plural(b.compared, `other ${noun}`)}` : `${n} of ${b.compared} other ${noun}s`;
    return `${_displayRunnerName(b.key)} differs from ${what}${_detail([b], measured)}`;
}

/** Names of a group's members; in a multi-run report, a backend all of whose runs are in the group is named once. */
function _memberNames(members, byKey) {
    const runsOf = new Map();
    [...byKey.keys()].forEach(k => {
        const id = parseRunnerKey(k).simId;
        runsOf.set(id, (runsOf.get(id) || 0) + 1);
    });
    const inGroup = new Map();
    members.forEach(k => {
        const id = parseRunnerKey(k).simId;
        inGroup.set(id, [...(inGroup.get(id) || []), k]);
    });
    const parts = [];
    inGroup.forEach((keys, id) => {
        if (parseRunnerKey(keys[0]).isMulti && keys.length === runsOf.get(id) && keys.length > 1) {
            parts.push(`all ${keys.length} ${_displayRunnerName(id)} runs`);
        } else {
            parts.push(...keys.map(_displayRunnerName));
        }
    });
    return parts.length <= MAX_NAMED ? _list(parts) : `${parts.slice(0, MAX_NAMED).join(', ')} and ${parts.length - MAX_NAMED} more`;
}

/** One sentence for a group of backends that agree with each other and differ from backends outside it. */
function _groupPhrase(g, byKey, measured, noun) {
    if (g.members.length === 1) return _differsPhrase(byKey.get(g.members[0]), measured, noun);
    const names = _memberNames(g.members, byKey);
    const how = measured ? 'are consistent with each other' : 'agree with each other';
    const detail = _detail(g.members.map(k => byKey.get(k)), measured);
    if (g.differsFromAll) return `${names} ${how} and differ from every other ${noun} (${g.comparedOutside}${detail ? `; ${detail.slice(2, -1)}` : ''})`;
    return `${names} ${how}; together they differ from ${g.differsFrom.length} of the ${_plural(g.comparedOutside, `other ${noun}`)}${detail}`;
}

/** "Among the other N backends, no pair is distinguishable …" or "The other N backends agree with each other." */
function _restLine(v, rest, byKey, measured, noun) {
    const n = rest.length;
    if (n < 2) return null;
    if (measured) {
        const set = new Set(rest);
        const byOnly = (v.byOnlyPairs || []).some(([x, y]) => set.has(x) && set.has(y));
        return `Among the other ${_plural(n, noun)}, no pair is distinguishable${byOnly ? ' apart from the BY-only pairs below' : ''}${v.marginalTested ? ' and no single-bit marginal differs' : ''}.`;
    }
    const set = new Set(rest);
    const allAgree = rest.every(k => byKey.get(k).comparedWith.filter(o => set.has(o)).every(o => byKey.get(k).agreesWith.includes(o)));
    return allAgree ? `The other ${_plural(n, noun)} agree with each other.` : `No pair among the other ${_plural(n, noun)} differs.`;
}

function _pairText(a, b, records, measured) {
    const p = records.find(r => r.simulators?.includes(a) && r.simulators?.includes(b));
    let size = '';
    if (p) {
        if (measured) {
            const tv = p.metrics?.statistical_test?.effect_size?.total_variation;
            if (typeof tv === 'number') size = ` (${_tvText(tv).replace('largest ', '')})`;
        } else {
            const f = p.metrics?.label_aligned_fidelity ?? p.metrics?.direct_fidelity;
            if (typeof f === 'number') size = ` (${_fidelityText(f).replace('lowest ', '')})`;
        }
    }
    return `${_displayRunnerName(a)} × ${_displayRunnerName(b)}${size}`;
}

/** Sentences for the backends that differ, following the model's kind. */
function _differenceLines(v, h, measured, noun, records) {
    const byKey = new Map(v.backends.map(b => [b.key, b]));
    const lines = [];
    if (h.kind === 'named') {
        lines.push(`${h.named.map(g => _cap(_groupPhrase(g, byKey, measured, noun))).join('. ')}.`);
        const rest = _restLine(v, h.rest, byKey, measured, noun);
        if (rest) lines.push(rest);
        return lines;
    }
    if (h.kind === 'camps') {
        const camps = h.camps.map(g => `${_memberNames(g.members, byKey)} (${g.members.length})`);
        const size = _magnitude(h.camps.flatMap(g => g.members.map(k => byKey.get(k))), measured);
        lines.push(`The ${noun}s split into ${h.camps.length} groups that differ from each other${size ? ` (${size})` : ''}: ${camps.join('; ')}.`);
        lines.push(measured ? 'Within each group no pair is distinguishable.' : 'Within each group no pair differs.');
        if (h.neutral.length) {
            lines.push(`${_names(h.neutral)} ${h.neutral.length === 1 ? 'differs' : 'differ'} from no ${noun}.`);
        }
        return lines;
    }
    if (h.kind === 'pairs') {
        const k = h.pairs.length;
        lines.push(`${k === 1 ? 'One pair differs' : `${k} pairs differ`}: ${h.pairs.map(([a, b]) => _pairText(a, b, records, measured)).join(', ')}.`);
        lines.push(measured
            ? `No other pair is distinguishable${v.marginalTested ? ' or differs in a single-bit marginal' : ''}.`
            : 'No other pair differs.');
        const isolated = h.pairs.every(([a, b]) => byKey.get(a).differsWith.length === 1 && byKey.get(b).differsWith.length === 1);
        if (measured && isolated) {
            lines.push(`${k === 1 ? 'Its two backends are' : 'Each of these backends is'} consistent with or inconclusive against every other ${noun}; a flagged pair can be a chance result, so rerun with more shots to confirm.`);
        }
        return lines;
    }
    lines.push(`${h.named.map(g => _differsPhrase(byKey.get(g.members[0]), measured, noun)).join('. ')}.`);
    const n = h.rest.length, k = h.pairs.length;
    if (k && k <= MAX_NAMED) {
        lines.push(`Among the other ${_plural(n, noun)}, ${_plural(k, 'pair')} differ${k === 1 ? 's' : ''}: ${h.pairs.map(([x, y]) => _pairText(x, y, records, measured)).join(', ')}.`);
    } else if (k) {
        lines.push(`Among the other ${_plural(n, noun)}, ${k} pairs differ; the Agreement tab lists them.`);
    } else {
        const rest = _restLine(v, h.rest, byKey, measured, noun);
        if (rest) lines.push(rest);
    }
    return lines;
}

/** Headline sentences for a single-circuit report. */
export function headlineSentences(data) {
    const v = backendVerdicts(data);
    const h = headlineModel(v);
    const measured = v.mode === 'measured';
    const noun = unitNoun(v);
    const lines = [];
    const total = v.backends.length;
    const backendCount = new Set(v.backends.map(b => parseRunnerKey(b.key).simId)).size;
    lines.push(v.multiRun
        ? `${h.ok} of ${_plural(total, 'run')} on ${_plural(backendCount, 'backend')} returned a result.`
        : `${h.ok} of ${_plural(total, 'backend')} returned a result.`);
    const failedParts = Object.entries(h.failed).filter(([, keys]) => keys.length)
        .map(([st, keys]) => `${RUNNER_STATUS_LABEL[st]}: ${_names(keys)}`);
    if (failedParts.length) lines.push(`${failedParts.join('. ')}.`);
    if (h.ok < 2) return { lines, verdicts: v, model: h, tone: 'offline' };

    const byOnlyLine = v.byOnly
        ? `${_plural(v.byOnly, 'further pair')} ${v.byOnly === 1 ? 'is' : 'are'} significant under Benjamini–Yekutieli only, not under Holm's family-wise correction, with no single-bit marginal difference: ${_pairNames(v.byOnlyPairs)}.`
        : null;
    const marginalClause = v.marginalTested ? ', and no single-bit marginal differs' : '';
    if (h.kind === 'none') {
        if (measured) {
            const inconclusive = v.inconclusive ? `; on the full-distribution test ${v.inconclusive} of ${v.pairs} pairs are inconclusive at this shot count` : '';
            if (h.byOnlyHub) {
                const b = v.backends.find(x => x.key === h.byOnlyHub);
                const n = b.byOnlyWith.length;
                const what = n === b.compared ? `all ${_plural(b.compared, `other ${noun}`)}` : `${n} of ${b.compared} other ${noun}s`;
                lines.push(`${_displayRunnerName(b.key)} is distinguishable from ${what} under Benjamini–Yekutieli, but none of these pairs passes Holm's family-wise correction${marginalClause.replace(', and', ' and')}.`);
                if (v.inconclusive) lines.push(`On the full-distribution test, ${v.inconclusive} of ${v.pairs} pairs are inconclusive at this shot count.`);
            } else if (byOnlyLine) {
                lines.push(`No pair is distinguishable under both Benjamini–Yekutieli and Holm${marginalClause}${inconclusive}.`, byOnlyLine);
            } else {
                lines.push(v.inconclusive
                    ? `No pair is distinguishable beyond shot noise${marginalClause}${inconclusive}.`
                    : `Every comparable pair is consistent within shot noise${marginalClause}.`);
            }
        } else {
            lines.push(`Every comparable pair of ${noun}s agrees.`);
        }
        return { lines, verdicts: v, model: h, tone: v.inconclusive || byOnlyLine ? 'inconclusive' : 'success' };
    }

    lines.push(..._differenceLines(v, h, measured, noun, data?.divergence_report?.pairwise_agreement || []));
    if (byOnlyLine) lines.push(byOnlyLine);
    if (measured && v.inconclusive) lines.push(`On the full-distribution test, ${v.inconclusive} of ${v.pairs} pairs are inconclusive at this shot count.`);
    lines.push('A pair that differs shows that at least one of the two is wrong; the report does not decide which. Check against an independent reference.');
    return { lines, verdicts: v, model: h, tone: 'anomaly' };
}

function _pairNames(pairs) {
    const named = pairs.map(([a, b]) => `${_displayRunnerName(a)} × ${_displayRunnerName(b)}`);
    return named.length <= MAX_NAMED ? named.join(', ') : `${named.slice(0, MAX_NAMED).join(', ')} and ${named.length - MAX_NAMED} more`;
}

const TONE = {
    success: 'bg-green-50 text-green-900 border-green-300',
    anomaly: 'bg-red-50 text-red-900 border-red-300',
    inconclusive: 'bg-sky-50 text-sky-900 border-sky-300',
    offline: 'bg-gray-50 text-gray-800 border-gray-300',
};

/** True when the recommendation for one of these pairs is a lower bound or comes from pooling rare outcomes. */
function _recommendationIsLowerBound(pairs, shots) {
    return pairs.some(p => {
        const st = p.metrics?.statistical_test || {};
        if (pairRecommendation(p).shots !== shots) return false;
        return st.recommendation_is_lower_bound === true || (st.power?.pooled_probability ?? 0) > 0;
    });
}

/** Next steps the report supports: more shots for inconclusive pairs, failed runs to inspect. */
export function nextSteps(data, v = backendVerdicts(data), h = headlineModel(v)) {
    const steps = [];
    const pairs = data.divergence_report?.pairwise_agreement || [];
    const shots = recommendedShots(pairs);
    if (v.mode === 'measured' && v.inconclusive && shots) {
        steps.push(_recommendationIsLowerBound(pairs, shots)
            ? `For the inconclusive pairs, the power model asks for at least ${fmtInt(shots)} shots per backend (this run used ${fmtInt(data.n_shots)}); outcomes not yet seen can raise it.`
            : `For the inconclusive pairs, the power model asks for about ${fmtInt(shots)} shots per backend (this run used ${fmtInt(data.n_shots)}).`);
    }
    if (h.failed.timeout.length) {
        const max = getState().timeoutMax;
        const atMax = typeof data.timeout_seconds === 'number' && typeof max === 'number' && data.timeout_seconds >= max;
        steps.push(atMax
            ? `Timed-out backends: the timeout was already at the server maximum (${fmtInt(max)} s); run a smaller circuit.`
            : 'Timed-out backends: raise the timeout in the Execution chip, or run a smaller circuit.');
    }
    if (h.failed.error.length) steps.push('Backends with errors: their messages are under "Errors" below.');
    if (v.disagreeing) steps.push('To see the evidence for a pair, open the Agreement tab or the lists below.');
    return steps;
}

export function renderHeadline(panel, data) {
    const { lines, verdicts, model, tone } = headlineSentences(data);
    const card = document.createElement('section');
    card.className = `p-4 mb-4 border-l-4 rounded ${TONE[tone]}`;
    card.setAttribute('aria-label', 'Result');
    lines.forEach((text, i) => {
        const p = document.createElement('p');
        p.className = i === lines.length - 1 && tone === 'anomaly' ? 'text-xs mt-2 opacity-80' : 'text-sm';
        if (i === 0) p.classList.add('font-semibold');
        p.textContent = text;
        card.appendChild(p);
    });
    const steps = nextSteps(data, verdicts, model);
    if (steps.length) {
        const ul = document.createElement('ul');
        ul.className = 'list-disc ml-5 mt-2 text-xs space-y-0.5';
        steps.forEach(t => { const li = document.createElement('li'); li.textContent = t; ul.appendChild(li); });
        card.appendChild(ul);
    }
    panel.appendChild(card);
    return { verdicts, model };
}

function _th(text, tip) {
    const th = document.createElement('th');
    th.scope = 'col';
    th.className = 'px-2 py-1 text-left font-medium text-gray-600 whitespace-nowrap';
    th.textContent = text;
    if (tip) setTip(th, tip);
    return th;
}

function _countCell(n, of, style, tip) {
    const td = document.createElement('td');
    td.className = 'px-2 py-1 whitespace-nowrap';
    if (!of) { td.textContent = '—'; return td; }
    if (n === 0) { td.textContent = `0 of ${of}`; td.classList.add('text-gray-500'); return td; }
    td.appendChild(_chip(STATUS_STYLES[style].badge, `${n} of ${of}`, tip));
    return td;
}

/** Differs-from cell: red for the backends the headline names, gray for the others; pairs flagged under BY only follow in gray text. */
function _differsCell(b, flagged, measured) {
    const robust = b.differsWith.length;
    const size = _magnitude([b], measured);
    const tip = robust
        ? `Differs from: ${b.differsWith.map(_displayRunnerName).join(', ')}.${size ? ` ${size.charAt(0).toUpperCase()}${size.slice(1)}.` : ''}${flagged ? '' : ' The headline does not name this one.'}`
        : '';
    const td = _countCell(robust, b.compared, flagged ? 'anomaly' : 'offline', tip);
    if (b.differsByOnly && b.compared) {
        const extra = document.createElement('span');
        extra.className = 'ml-1 text-gray-500';
        extra.textContent = `+${b.differsByOnly} BY only`;
        setTip(extra, `Significant under Benjamini–Yekutieli but not under Holm's family-wise correction, with no single-bit marginal difference: ${b.byOnlyWith.map(_displayRunnerName).join(', ')}.`);
        td.appendChild(extra);
    }
    return td;
}

/** One row per backend: status, how many backends it differs from / is inconclusive with,
 * bit order, precision, total time and peak memory. */
export function renderBackendTable(panel, data, verdicts, model = headlineModel(verdicts)) {
    const raws = new Map((data.raw_results || []).map(r => [r.simulator, r]));
    const measured = verdicts.mode === 'measured';
    const noun = unitNoun(verdicts);
    const flagged = new Set(model.flagged);
    const rows = [...verdicts.backends].sort((a, b) => (b.differsWith.length - a.differsWith.length)
        || (b.differsByOnly - a.differsByOnly) || a.key.localeCompare(b.key));
    if (!rows.length) return;

    const wrap = document.createElement('div');
    wrap.className = 'overflow-x-auto mb-4 border rounded';
    const table = document.createElement('table');
    table.className = 'min-w-full text-xs';
    const caption = document.createElement('caption');
    caption.className = 'text-left text-xs font-semibold text-gray-700 px-2 py-1 bg-gray-50';
    caption.textContent = 'Backends';
    table.appendChild(caption);
    const head = document.createElement('tr');
    head.append(
        _th('Backend'),
        _th('Status'),
        _th('Differs from', (measured
            ? `Other ${noun}s this one is distinguishable from beyond shot noise, or differs from in a single-bit marginal. `
            : `Other ${noun}s whose statevector this one disagrees with. `)
            + `Red for the ${noun}s the headline names as differing; gray for the others. `
            + (measured ? 'Hover a count for the largest total variation over its differing pairs.' : 'Hover a count for the lowest fidelity over its differing pairs.')
            + (measured ? ' "BY only" counts pairs significant under Benjamini–Yekutieli but not under Holm, which are not in the red or gray count.' : '')),
        ...(measured ? [_th('Inconclusive with', `Full-distribution test. ${labelDefinition('inconclusive_low_shots')} A pair can also differ in a single-bit marginal.`)] : []),
        _th('Bit order', 'The qubit ordering the backend declares: lsb = qubit 0 is the rightmost bit.'),
        _th('Precision'),
        _th('Total time (s)', 'Compilation + simulation of the timed run (median with Timing repeats above 1). Details in Performance.'),
        _th('Peak memory (MiB)', 'Peak RSS of the simulating process over its whole life, including interpreter start, SDK imports and the warm-up run; for small circuits it is mostly the SDK footprint. Details in Performance.'),
    );
    const thead = document.createElement('thead');
    thead.appendChild(head);
    table.appendChild(thead);
    const tbody = document.createElement('tbody');
    rows.forEach(b => {
        const raw = raws.get(b.key);
        const status = raw ? runnerStatus(raw) : b.status;
        const tr = document.createElement('tr');
        tr.className = 'border-t';
        const name = document.createElement('th');
        name.scope = 'row';
        name.className = 'px-2 py-1 text-left font-medium text-gray-900 whitespace-nowrap';
        name.textContent = _displayRunnerName(b.key);
        const st = document.createElement('td');
        st.className = 'px-2 py-1';
        st.appendChild(_chip(STATUS_STYLES[RUNNER_STATUS_STYLE[status] || 'offline'].badge, RUNNER_STATUS_LABEL[status] || status, labelDefinition(status)));
        const order = document.createElement('td');
        order.className = 'px-2 py-1';
        const orderTag = bitOrderTag(b.bitOrder);
        if (orderTag) { orderTag.classList.remove('ml-1'); order.appendChild(orderTag); } else order.textContent = '—';
        const prec = document.createElement('td');
        prec.className = 'px-2 py-1';
        const tag = raw ? precisionTag(raw.precision) : null;
        if (tag) { tag.classList.remove('ml-1'); prec.appendChild(tag); } else prec.textContent = '—';
        const time = document.createElement('td');
        time.className = 'px-2 py-1 font-mono';
        time.textContent = typeof raw?.execution_time_sec === 'number' ? fmtNum(raw.execution_time_sec) : '—';
        const mem = document.createElement('td');
        mem.className = 'px-2 py-1 font-mono';
        mem.textContent = typeof raw?.process_peak_rss_mb === 'number' ? fmtNum(raw.process_peak_rss_mb, 1) : '—';
        tr.append(name, st,
            _differsCell(b, flagged.has(b.key), measured),
            ...(measured ? [_countCell(b.inconclusive, b.compared, 'inconclusive', labelText('inconclusive_low_shots'))] : []),
            order, prec, time, mem);
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
    panel.appendChild(wrap);
}
