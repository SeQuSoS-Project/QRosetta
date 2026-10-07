// The artifact catalog of a report and the backend subset. Mirrors services/publication
// registry.py (_iter_artifacts, list_artifacts, _scoped) and subset.py;
// tests/unit/test_artifacts_parity.py compares the two. No DOM, no network.

import {
    JS_UNIT, _artDistinct, _artPairwise, _artSlug, _artTimingRepeated, _artTimingSamples,
    _dataAgreement, _dataMatrix, _dataMetadata, _dataPerformance, _dataResources, _dataStatistical,
    _renderTable, _txtExecutedQasm, _txtGlossary,
} from './artifact_formats.js';
import {
    countProbabilities, countsLegend, dataCounts, dataHamming, dataMarginals, dataRank,
    hammingLegend, marginalsLegend, rankLegend,
} from './artifact_distributions.js';
import { VIEW_OF_ARTIFACT, normalizeParams } from './artifact_views.js';

/** "measured" when the report has n_shots, else "statevector". */
export function _artifactMode(results) { return ('n_shots' in results) ? 'measured' : 'statevector'; }

/**
 * Artifacts available for `results`: {id, label, group, view, view_id, formats, legend[,
 * getText, getData]}; a distribution view's legend is computed when first read. `params`
 * maps a view id to raw parameters (normalised here); views not in it use their defaults.
 */
export function buildArtifactCatalog(results, params = {}) {
    const div = results.divergence_report || {};
    const mode = _artifactMode(results);
    const norm = {};
    Object.entries(params || {}).forEach(([vid, p]) => { norm[vid] = normalizeParams(vid, p, results); });
    const vp = id => {
        const vid = VIEW_OF_ARTIFACT[id];
        if (vid === undefined) return [null, {}];
        if (!norm[vid]) norm[vid] = normalizeParams(vid, {}, results);
        return [vid, norm[vid]];
    };
    const items = [];
    const table = (id, label, group, dataFn, legend) => items.push({
        id, label, group, view: 'text', view_id: vp(id)[0], formats: ['latex', 'csv', 'html', 'markdown'], legend,
        getText: fmt => _renderTable(fmt, dataFn()), getData: dataFn,
    });
    const blob = (id, label, group, formats, textFn, legend) => items.push({
        id, label, group, view: 'text', view_id: vp(id)[0], formats, legend, getText: () => textFn(),
    });
    const image = (id, label, group, legend) => {
        const item = { id, label, group, view: 'image', view_id: vp(id)[0], formats: ['svg', 'png', 'pdf'] };
        if (typeof legend === 'function') {
            let text = null;
            Object.defineProperty(item, 'legend', { enumerable: true, get: () => (text ??= legend()) });
        } else item.legend = legend;
        items.push(item);
    };

    const pairwise = _artPairwise(div);
    if (pairwise.length) {
        image('agreement_distribution', 'Agreement class distribution', 'Agreement',
            'Bar chart of how many backend pairs fall into each agreement label (transform-explained, residual or not comparable)' + (mode === 'measured' ? ' and shot-noise verdict' : '') + '.');
        table('agreement', 'Pairwise agreement table', 'Agreement', () => _dataAgreement(div, mode),
            `One row per backend pair: explained-cause label, registered transform, key metric (direct fidelity, or JS divergence in ${JS_UNIT} direct and in the label-aligned basis), statistical verdict and measured assessment (measured) and not-comparable reason.`);
    }
    const heat = mode === 'statevector'
        ? [['fidelity_matrix', 'Raw statevector fidelity (no transform)', 'fidelity']]
        : [['statistical_distance_matrix (js_divergence)', `Raw Jensen–Shannon divergence (${JS_UNIT})`, 'js_divergence'],
           ['hellinger_distance_matrix', 'Raw Hellinger distance', 'hellinger']];
    const multi = (div.simulators || []).length >= 2;
    heat.forEach(([key, title, base]) => {
        if (multi && Array.isArray(div[key]) && div[key].length) {
            const short = title.split('(')[0].trim();
            image(`${base}_heatmap`, `${short} heatmap`, 'Divergence',
                `${title}: N×N heatmap; darker = larger value. Not-compared pairs and the diagonal shown neutral.`);
            const mid = { fidelity: 'matrix_fidelity', js_divergence: 'matrix_js', hellinger: 'matrix_hellinger' }[base];
            table(mid, `${short} matrix (table)`, 'Divergence', () => _dataMatrix(div, key, title),
                `${title} as a copyable N×N matrix table (raw metric).`);
        }
    });
    const unrankedNote = 'runs without a rank are listed with their status and reason and have no bar.';
    const perf = results.performance_report || {};
    const repeated = _artTimingRepeated(results);
    if ((perf.ranking || []).length || (perf.unranked || []).length) {
        const pt = vp('performance_time')[1];
        const stageText = { stacked: 'Stacked compilation + simulation', simulation: 'Simulation', compilation: 'Compilation' }[pt.stage];
        const log = pt.xscale === 'log' && pt.stage !== 'stacked';
        image('performance_time', 'Execution-time chart', 'Performance',
            `${stageText} wall-clock time per backend `
            + (repeated ? '(median of each stage over the timed runs), ' : '(raw), ')
            + `n=${_artTimingSamples(results)} timing sample(s) per backend; GPU runs are labelled (GPU); ` + unrankedNote
            + (log ? ' Logarithmic time axis.' : ''));
        table('performance', 'Execution-time table', 'Performance', () => _dataPerformance(results),
            'Per-backend device, compilation, simulation and total wall-clock time'
            + (repeated ? ' (medians, with the IQR, stdev and n of total time)' : '')
            + ', simulation and process CPU time, and status (raw).');
    }
    const res = results.resource_report || {};
    if ((res.ranking || []).length || (res.unranked || []).length) {
        const pr = vp('resource_memory')[1];
        if (pr.metric === 'memory_delta') {
            image('resource_memory', 'Process peak RSS chart', 'Resources',
                'Sim-window RSS delta of each backend (peak minus RSS at monitor entry over the pre-execute step and simulation window of the first timed run), in '
                + `MiB; method: ${_artDistinct(results, 'memory_method')}. It reads near 0 when the simulation reuses memory the warm-up freed. Bars follow the resource `
                + 'ranking (process peak RSS); GPU runs are labelled (GPU); ' + unrankedNote);
        } else {
            image('resource_memory', 'Process peak RSS chart', 'Resources',
                "Peak RSS of each backend's simulating process over its whole life (interpreter start, imports, warm-up and every timed run), in MiB; method: "
                + `${_artDistinct(results, 'process_peak_rss_method')}. Ranked lowest first; GPU runs are labelled (GPU) and not ranked because GPU device memory is not measured; ` + unrankedNote);
        }
        table('resources', 'Resource-usage table', 'Resources', () => _dataResources(results),
            'Per-backend device, process peak RSS, sim-window peak RSS and RSS delta, theoretical statevector size, precision and status (raw).');
    }
    if (mode === 'measured') {
        if (pairwise.some(r => (r.metrics || {}).statistical_test)) {
            table('statistical_test', 'Statistical-test table', 'Statistical', () => _dataStatistical(div),
                'Chi-square + G-test p-values (raw + BY) in the label-aligned basis, effect size, power and pooled outcomes per pair.');
        }
        if (countProbabilities(results).sims.length) {
            const pc = vp('counts_overview')[1];
            image('counts_overview', 'Count comparison', 'Statistical', () => countsLegend(results, pc));
            table('counts_table', 'Count comparison (table)', 'Statistical', () => dataCounts(results, pc),
                'Measured probability of each shown outcome (rows) per backend (columns).');
            const pm = vp('qubit_marginals')[1];
            image('qubit_marginals', 'Single-bit marginals', 'Statistical', () => marginalsLegend(results, pm));
            table('qubit_marginals_table', 'Single-bit marginals (table)', 'Statistical', () => dataMarginals(results),
                'P(c[j] = 1) for each classical bit j (rows) per backend (columns).');
            const ph = vp('hamming_weight')[1];
            image('hamming_weight', 'Hamming-weight distribution', 'Statistical', () => hammingLegend(results, ph));
            table('hamming_weight_table', 'Hamming-weight distribution (table)', 'Statistical', () => dataHamming(results),
                'Probability of each Hamming weight (rows) per backend (columns).');
            const pk = vp('rank_probability')[1];
            image('rank_probability', 'Outcome probabilities by rank', 'Statistical', () => rankLegend(results, pk));
            table('rank_probability_table', 'Outcome spread (table)', 'Statistical', () => dataRank(results),
                'Per backend: shots, observed outcomes, largest probability and the outcomes covering 50% and 90% of the shots.');
        }
    }
    if ((results.raw_results || []).length) {
        table('metadata', 'Run + provenance metadata', 'Metadata', () => _dataMetadata(results, mode),
            'Backends, device, SDK versions, qubit-ordering & sampling labels, opt level, run params.');
        (results.raw_results || []).forEach(r => {
            if (r.simulator && r.transpiled_qasm) {
                blob(`circuit_${_artSlug(r.simulator)}`, `Executed QASM: ${r.simulator}`, 'Circuits',
                    ['qasm', 'text'], () => _txtExecutedQasm(results, r.simulator),
                    `The exact transpiled OpenQASM executed by the ${r.simulator} adapter.`);
            }
        });
    }
    const terms = ['agreement class', 'not-comparable reason'];
    if (mode === 'measured') terms.push('statistical verdict');
    terms.push('unranked reason');
    blob('glossary', 'Taxonomy glossary', 'Reference', ['markdown', 'text'], () => _txtGlossary(mode),
        'Definitions of every ' + terms.join(', ') + ', plus the default thresholds.');
    return items;
}

/**
 * Copy of `results` restricted to the `selected` backends: square N×N matrices sliced,
 * pairwise records, raw results, ranking and unranked lists filtered, verdict counts
 * recomputed. Does not mutate `results`.
 */
export function _subsetResults(results, selected) {
    const div = results.divergence_report || {};
    const allSims = div.simulators || [];
    const keepIdx = [];
    allSims.forEach((s, i) => { if (selected.has(s)) keepIdx.push(i); });
    const newDiv = Object.assign({}, div);
    newDiv.simulators = keepIdx.map(i => allSims[i]);
    Object.keys(div).forEach(k => {
        const v = div[k];
        if (Array.isArray(v) && v.length === allSims.length
            && v.every(row => Array.isArray(row) && row.length === allSims.length)) {
            newDiv[k] = keepIdx.map(i => keepIdx.map(j => v[i][j]));
        }
    });
    if (Array.isArray(div.pairwise_agreement)) {
        newDiv.pairwise_agreement = div.pairwise_agreement.filter(r => {
            const s = r.simulators || [];
            return s.length === 2 && selected.has(s[0]) && selected.has(s[1]);
        });
    }
    const summary = div.statistical_test_summary;
    if (summary && summary.verdict_counts) {
        const vc = {};
        (newDiv.pairwise_agreement || []).forEach(r => {
            const v = ((r.metrics || {}).statistical_test || {}).verdict;
            if (v) vc[v] = (vc[v] || 0) + 1;
        });
        newDiv.statistical_test_summary = Object.assign({}, summary, { verdict_counts: vc });
    }
    const out = Object.assign({}, results, { divergence_report: newDiv });
    if (Array.isArray(results.raw_results)) {
        out.raw_results = results.raw_results.filter(r => selected.has(r.simulator));
    }
    ['performance_report', 'resource_report'].forEach(rep => {
        const report = results[rep];
        if (!report) return;
        const patch = {};
        ['ranking', 'unranked'].forEach(k => {
            if (Array.isArray(report[k])) patch[k] = report[k].filter(r => selected.has(r.simulator));
        });
        out[rep] = Object.assign({}, report, patch);
    });
    return out;
}

/**
 * The view's artifacts as the server renders them (registry.py _scoped): the report
 * restricted to the view's backends and its catalog with the view's normalised parameters.
 * Throws for a bad parameter.
 */
export function scopedCatalog(results, viewId, params) {
    const p = normalizeParams(viewId, params, results);
    const scoped = p.backends ? _subsetResults(results, new Set(p.backends)) : results;
    return { params: p, results: scoped, catalog: buildArtifactCatalog(scoped, { [viewId]: p }) };
}
