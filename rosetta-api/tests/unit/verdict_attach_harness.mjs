// For test_report_summary.py: what the page shows for a report, read from its recorded verdicts or
// from a server summary attached to it (attachSummary) in the same Node process.
import { attachSummary, isDisagreement, lacksVerdicts, measuredAssessment, statevectorGroup } from '../../static/js/run_status.js';
import { backendVerdicts, headlineModel } from '../../static/js/backend_verdicts.js';
import { headlineSentences } from '../../static/js/overview_renderer.js';

/** The page's reading of every circuit of `report`, with `summary` attached first when given. */
export function shownVerdicts(report, summary = null) {
    const before = lacksVerdicts(report);
    if (summary) attachSummary(report, summary);
    const tasks = Array.isArray(report.benchmark_summary) ? report.benchmark_summary : [report];
    return {
        lacked: before,
        lacks: lacksVerdicts(report),
        tasks: tasks.map(task => {
            const pairs = task.divergence_report?.pairwise_agreement || [];
            const v = backendVerdicts(task);
            return {
                pairs: pairs.map(p => [isDisagreement(p), measuredAssessment(p) ?? null, statevectorGroup(p)]),
                verdicts: v,
                model: headlineModel(v),
                headline: headlineSentences(task).lines,
            };
        }),
    };
}

/** The error a page read gives for a report without verdicts. */
export function readWithoutVerdicts(report) {
    try {
        backendVerdicts(report);
        return null;
    } catch (e) {
        return String(e.message);
    }
}
