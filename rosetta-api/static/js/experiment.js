// Results of an experiment run (the circuit list run with preprocessing on and off through
// POST /experiments): counts across both settings, errors to triage, and the bundle download
// from GET /experiments/{id}/bundle.

import { BASE_URL, formatApiError, getAuthHeaders } from './api.js';
import { labelText } from './labels.js';
import { statevectorGroup } from './run_status.js';
import { downloadBlob } from './utils.js';

const ASSESSMENTS = ['consistent_within_shot_noise', 'inconclusive_low_shots', 'ambiguous', 'distinguishable'];

/** Class a prevalence row counts: its shot-noise assessment when recorded, else its agreement class. */
function _prevalenceClass(row) {
    return row.measured_assessment ?? row.assessment ?? row.agreement_class;
}

/**
 * Pair counts across axes: measured experiments by shot-noise assessment, statevector
 * experiments by label group.
 * @returns {{ heading: string, text: string }}
 */
function _prevalenceText(summary) {
    const rows = summary.prevalence || [];
    const counts = {};
    rows.forEach(r => {
        const k = _prevalenceClass(r);
        counts[k] = (counts[k] || 0) + (r.pair_count || 0);
    });
    const nc = counts.not_comparable || 0;
    delete counts.not_comparable;
    const tail = nc ? ` · not comparable: ${nc}` : '';
    if (!Object.keys(counts).length) return { heading: 'Pairs', text: nc ? `not comparable: ${nc}` : 'none' };

    if (summary.mode === 'measured') {
        const keys = Object.keys(counts);
        if (keys.every(k => ASSESSMENTS.includes(k))) {
            return {
                heading: 'Pairs by shot-noise assessment',
                text: ASSESSMENTS.filter(k => counts[k]).map(k => `${labelText(k)}: ${counts[k]}`).join(' · ') + tail,
            };
        }
        return {
            heading: 'Pairs by distance label (this summary records no shot-noise assessment; the bundle results/ hold it per pair)',
            text: keys.map(k => `${k}: ${counts[k]}`).join(' · ') + tail,
        };
    }
    const groups = { agree: 0, bit_order: 0, disagree: 0, other: 0 };
    Object.entries(counts).forEach(([k, n]) => {
        const g = statevectorGroup({ agreement: k, mode: 'statevector' });
        groups[g === 'not_comparable' ? 'other' : g] += n;
    });
    const parts = [`agree: ${groups.agree}`, `agree after the declared bit reversal: ${groups.bit_order}`,
        `disagree: ${groups.disagree}`];
    if (groups.other) parts.push(`other labels: ${groups.other}`);
    return {
        heading: 'Statevector pairs',
        text: `${parts.join(' · ')}${tail} (${Object.entries(counts).map(([k, n]) => `${k} ${n}`).join(', ')})`,
    };
}

function _line(parent, heading, text, className = '') {
    const div = document.createElement('p');
    div.className = `text-sm ${className}`;
    if (heading) {
        const b = document.createElement('span');
        b.className = 'font-medium';
        b.textContent = `${heading}: `;
        div.appendChild(b);
    }
    div.appendChild(document.createTextNode(text));
    parent.appendChild(div);
}

/** Render an experiment's summary and bundle download into `panel`. */
export function renderExperimentResult(results, panel, { jobId, name, title }) {
    panel.replaceChildren();
    const summary = results && results.experiment_summary;
    const h2 = document.createElement('h2');
    h2.className = 'text-xl font-semibold text-gray-900 mb-3';
    h2.textContent = title || 'Experiment';
    panel.appendChild(h2);
    if (!summary) {
        _line(panel, null, 'The experiment returned no summary.', 'text-red-700');
        return;
    }
    const nCircuits = (summary.circuits || []).length;
    const nAxes = (summary.axes || []).length;
    const nErr = summary.error_count || 0;
    const nResolve = (summary.resolution_errors || []).length;
    const prev = _prevalenceText(summary);
    const card = document.createElement('section');
    card.className = 'p-4 mb-4 border-l-4 rounded bg-gray-50 border-gray-300 space-y-1';
    _line(card, null, `${summary.cells} runs: ${nCircuits} circuit${nCircuits === 1 ? '' : 's'} × ${nAxes} preprocessing setting${nAxes === 1 ? '' : 's'}.`, 'font-semibold');
    _line(card, prev.heading, prev.text);
    _line(card, 'Errors to classify', `${nErr}${nResolve ? `; circuits that could not be resolved: ${nResolve}` : ''}`);
    panel.appendChild(card);
    _line(panel, null, 'The bundle holds the inputs, every per-circuit result, a conformance matrix, an agreement-prevalence '
        + 'table and a provenance manifest. Each error signature is marked untriaged, for you to classify as adapter, SDK, '
        + 'by design or resource. The server keeps the bundle for 30 minutes.', 'text-gray-600 mb-3');
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'py-2 px-4 rounded-md text-sm font-medium text-white bg-emerald-600 hover:bg-emerald-700';
    button.textContent = '⬇ Download bundle (ZIP)';
    button.onclick = () => downloadExperimentBundle(jobId, name);
    panel.appendChild(button);
}

export async function downloadExperimentBundle(jobId, name) {
    try {
        const res = await fetch(`${BASE_URL}/experiments/${encodeURIComponent(jobId)}/bundle`, { headers: getAuthHeaders() });
        if (!res.ok) throw new Error(await formatApiError(res));
        downloadBlob(await res.blob(), `${String(name || 'experiment').replace(/[^A-Za-z0-9_-]+/g, '_')}.zip`);
    } catch (e) {
        console.error(e);
        alert(`The bundle was not downloaded. ${e.message}`);
    }
}
