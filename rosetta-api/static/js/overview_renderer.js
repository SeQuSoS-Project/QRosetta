// Top of the Summary tab: a headline naming the backends that differ from others and the
// ones that failed, next steps the report supports, and one row per backend with its counts.

import { backendVerdicts, headlineModel } from './backend_verdicts.js';
import { labelDefinition, labelText } from './labels.js';
import { STATUS_STYLES, _chip, _displayRunnerName, bitOrderTag, fmtInt, fmtNum, precisionTag } from './render_helpers.js';
import { RUNNER_STATUS_LABEL, RUNNER_STATUS_STYLE, recommendedShots, runnerStatus } from './run_status.js';
import { setTip } from './tooltip.js';

const MAX_NAMED = 4;

function _names(keys) {
    const names = keys.map(_displayRunnerName);
    return names.length <= MAX_NAMED ? names.join(', ')
        : `${names.slice(0, MAX_NAMED).join(', ')} and ${names.length - MAX_NAMED} more`;
}

function _differsPhrase(b, measured) {
    if (!measured) return `${_displayRunnerName(b.key)} differs from ${b.differs} of ${b.compared}`;
    const parts = [];
    if (b.differsFull) parts.push(`${b.differsFull} distinguishable`);
    if (b.differsMarginal) parts.push(`${b.differsMarginal} with a differing single-bit marginal`);
    return `${_displayRunnerName(b.key)} differs from ${b.differs} of ${b.compared} (${parts.join(', ')})`;
}

/** Headline sentences for a single-circuit report. */
export function headlineSentences(data) {
    const v = backendVerdicts(data);
    const h = headlineModel(v);
    const measured = v.mode === 'measured';
    const lines = [];
    const total = v.backends.length;
    lines.push(`${h.ok} of ${total} backend${total === 1 ? '' : 's'} returned a result.`);
    const failedParts = Object.entries(h.failed).filter(([, keys]) => keys.length)
        .map(([st, keys]) => `${RUNNER_STATUS_LABEL[st]}: ${_names(keys)}`);
    if (failedParts.length) lines.push(`${failedParts.join('. ')}.`);
    if (h.ok < 2) return { lines, verdicts: v, model: h, tone: 'offline' };

    if (v.disagreeing === 0) {
        if (measured) {
            lines.push(v.inconclusive
                ? `No pair is distinguishable beyond shot noise, and no single-bit marginal differs; on the full-distribution test ${v.inconclusive} of ${v.pairs} pairs are inconclusive at this shot count.`
                : `Every comparable pair is consistent within shot noise, and no single-bit marginal differs.`);
        } else {
            lines.push(`Every comparable pair of backends agrees.`);
        }
        return { lines, verdicts: v, model: h, tone: v.inconclusive ? 'inconclusive' : 'success' };
    }

    if (h.outliers.length) {
        lines.push(`${h.outliers.map(b => _differsPhrase(b, measured)).join('; ')}.`);
        const others = h.rest.length;
        if (!h.residualPairs.length) {
            if (others > 1) {
                lines.push(measured
                    ? `Among the other ${others} backends, no pair is distinguishable and no single-bit marginal differs.`
                    : `The other ${others} backends agree with each other.`);
            }
        } else {
            const pairs = h.residualPairs.map(([a, b]) => `${_displayRunnerName(a)} × ${_displayRunnerName(b)}`);
            lines.push(`Among the other ${others} backends, ${pairs.length} pair${pairs.length === 1 ? '' : 's'} differ${pairs.length === 1 ? 's' : ''}: `
                + `${pairs.length <= MAX_NAMED ? pairs.join(', ') : `${pairs.slice(0, MAX_NAMED).join(', ')} and ${pairs.length - MAX_NAMED} more`}.`);
        }
    } else {
        const named = h.differing.slice(0, MAX_NAMED).map(b => _differsPhrase(b, measured));
        lines.push(`${named.join('; ')}${h.differing.length > MAX_NAMED ? `; ${h.differing.length - MAX_NAMED} more backends differ from at least one other` : ''}.`);
    }
    if (measured && v.inconclusive) lines.push(`On the full-distribution test, ${v.inconclusive} of ${v.pairs} pairs are inconclusive at this shot count.`);
    lines.push('A pair that differs shows that at least one of the two is wrong; the report does not decide which. Check against an independent reference.');
    return { lines, verdicts: v, model: h, tone: 'anomaly' };
}

const TONE = {
    success: 'bg-green-50 text-green-900 border-green-300',
    anomaly: 'bg-red-50 text-red-900 border-red-300',
    inconclusive: 'bg-sky-50 text-sky-900 border-sky-300',
    offline: 'bg-gray-50 text-gray-800 border-gray-300',
};

/** Next steps the report supports: more shots for inconclusive pairs, failed runs to inspect. */
function _nextSteps(data, v, h) {
    const steps = [];
    const pairs = data.divergence_report?.pairwise_agreement || [];
    const shots = recommendedShots(pairs);
    if (v.mode === 'measured' && v.inconclusive && shots) {
        steps.push(`For the inconclusive pairs, the power model asks for about ${fmtInt(shots)} shots per backend (this run used ${fmtInt(data.n_shots)}).`);
    }
    if (h.failed.timeout.length) steps.push('Timed-out backends: raise the timeout in Config, or run a smaller circuit.');
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
    const steps = _nextSteps(data, verdicts, model);
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

/** One row per backend: status, how many backends it differs from / is inconclusive with,
 * bit order, precision, total time and peak memory. */
export function renderBackendTable(panel, data, verdicts) {
    const raws = new Map((data.raw_results || []).map(r => [r.simulator, r]));
    const measured = verdicts.mode === 'measured';
    const rows = [...verdicts.backends].sort((a, b) => (b.differs - a.differs) || a.key.localeCompare(b.key));
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
        _th('Differs from', measured
            ? 'Other backends this one is distinguishable from beyond shot noise, or differs from in a single-bit marginal.'
            : 'Other backends whose statevector this one disagrees with.'),
        ...(measured ? [_th('Inconclusive with', `Full-distribution test. ${labelDefinition('inconclusive_low_shots')} A pair can also differ in a single-bit marginal.`)] : []),
        _th('Bit order', 'The qubit ordering the backend declares: lsb = qubit 0 is the rightmost bit.'),
        _th('Precision'),
        _th('Total time (s)', 'Compilation + simulation of the timed run (median with Timing repeats above 1). Details in Performance.'),
        _th('Peak memory (MiB)', 'Peak RSS of the simulating process over its whole life. Details in Performance.'),
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
            _countCell(b.differs, b.compared, 'anomaly', b.differsWith.length ? `Differs from: ${b.differsWith.map(_displayRunnerName).join(', ')}` : ''),
            ...(measured ? [_countCell(b.inconclusive, b.compared, 'inconclusive', labelText('inconclusive_low_shots'))] : []),
            order, prec, time, mem);
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
    panel.appendChild(wrap);
}
