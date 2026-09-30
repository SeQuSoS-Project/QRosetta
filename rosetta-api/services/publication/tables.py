"""Table builders, returning (headers, rows, title, caption), and text-blob builders."""

from .theme import (
    _AGREEMENT_GLOSSARY, _ASSESSMENT_GLOSSARY, _MEASUREMENT_NOTES, _NOT_COMPARABLE_GLOSSARY,
    _THRESHOLD_DEFAULTS, _UNRANKED_GLOSSARY, _VERDICT_GLOSSARY,
)
from .formats import _fmt_int, _fmt_num, _fmt_p, _fmt_text
from .selectors import (
    JS_UNIT, _distinct, _field, _key_metric, _pair_key, _pairwise_records, _report_rows,
    _timing_samples,
)


def _tbl_agreement(divergence_report: dict, mode: str):
    """One row per backend pair: label, transform, key metric(s), verdict and assessment
    (measured), reason."""
    records = _pairwise_records(divergence_report)
    measured = mode == "measured"
    headers = ["Pair", "Agreement", "Registered transform"]
    if measured:
        headers += [f"JS, direct ({JS_UNIT})", f"JS, label-aligned basis ({JS_UNIT})",
                    "Stat verdict", "Measured assessment"]
    else:
        headers.append("Direct fidelity")
    headers.append("Not-comparable reason")
    rows = []
    for r in records:
        m = r.get("metrics") or {}
        row = [_pair_key(r), _fmt_text(r.get("agreement")),
               _fmt_text(r.get("registered_transform")), _fmt_num(_key_metric(r))]
        if measured:
            row += [_fmt_num(m.get("label_aligned_js_divergence")),
                    _fmt_text((m.get("statistical_test") or {}).get("verdict")),
                    _fmt_text(r.get("measured_assessment"))]
        row.append(_fmt_text(m.get("reason")) if r.get("agreement") == "not_comparable" else "—")
        rows.append(row)
    metric = (f"JS, direct is the Jensen–Shannon divergence in {JS_UNIT} of the keys as "
              "reported; JS, label-aligned basis bit-reverses the second backend's keys when the "
              "two declared bit orders differ (lsb vs msb) and equals the direct value otherwise"
              if measured else
              "Direct fidelity is |<a|b>|^2 of the normalised vectors before any transform")
    caption = ("Classification over the registered-transform lattice; each label reports the "
               f"transform whose numerical effect explains the pair. {metric}.")
    if measured:
        caption += (" Measured assessment combines the descriptive label with the shot-noise "
                    "verdict: a pair over the distance thresholds whose verdict is consistent "
                    "is consistent_within_shot_noise.")
    return headers, rows, "Pairwise explained-cause agreement", caption


def _tbl_performance(results: dict):
    """Per-backend timings: ranked runs by total time, then unranked runs with the reason."""
    headers = ["Rank", "Simulator", "Compilation (s)", "Simulation (s)", "Total (s)",
               "Simulation CPU (s)", "Process CPU (s)", "Gate count", "Depth", "Status"]
    rows = [[row["rank"],
             _fmt_text(row["entry"].get("simulator")),
             _fmt_num(_field(row, "compilation_time_sec"), 6),
             _fmt_num(_field(row, "simulation_time_sec"), 6),
             _fmt_num(_field(row, "execution_time_sec"), 6),
             _fmt_num(_field(row, "simulation_cpu_time_sec"), 6),
             _fmt_num(_field(row, "cpu_time_sec"), 6),
             _fmt_int(_field(row, "gate_count")), _fmt_int(_field(row, "circuit_depth")),
             row["status"]]
            for row in _report_rows(results, "performance_report")]
    caption = (f"Wall-clock times of the timed run, n={_timing_samples(results)} timing sample(s) "
               "per backend; a warm-up run precedes it and is not included. Total = compilation "
               "+ simulation. Simulation CPU is process CPU time over the simulation window. "
               "Process CPU is getrusage CPU time of the whole isolated runner process, "
               "including interpreter start, imports and the warm-up. Ranked by total time, "
               "fastest first; runs without a rank follow with the reason in Status. Gate "
               "count and depth are taken from each backend's transpiled QASM.")
    return headers, rows, "Execution timing", caption


def _tbl_resources(results: dict):
    """Per-backend memory: ranked runs by process peak RSS, then unranked runs with the reason."""
    headers = ["Rank", "Simulator", "Process peak RSS (MiB)", "Sim-window peak RSS (MiB)",
               "Sim-window RSS delta (MiB)", "Theoretical SV (MiB)", "Precision", "Status"]
    rows = [[row["rank"],
             _fmt_text(row["entry"].get("simulator")),
             _fmt_num(_field(row, "process_peak_rss_mb"), 1),
             _fmt_num(_field(row, "process_peak_mb"), 1),
             _fmt_num(_field(row, "memory_usage_mb")),
             _fmt_num(_field(row, "theoretical_statevector_mb")),
             _fmt_text(_field(row, "precision")), row["status"]]
            for row in _report_rows(results, "resource_report")]
    caption = ("Process peak RSS is the peak resident memory of the simulating process over its "
               "whole life (interpreter start, imports, warm-up and timed run); method: "
               f"{_distinct(results, 'process_peak_rss_method')}. Rows are ranked by it, lowest "
               "first; runs without a rank follow with the reason in Status. Sim-window peak RSS "
               "and RSS delta (peak minus RSS at monitor entry) cover the pre-execute step and "
               f"simulation window of the timed run; method: {_distinct(results, 'memory_method')}. "
               "Theoretical SV is 2^n × 16 bytes for the declared qubit count. 1 MiB = 1024^2 bytes. "
               "For small circuits process peak RSS is dominated by the SDK import footprint; "
               "the sim-window RSS delta is the simulation's own allocation.")
    return headers, rows, "Resource usage", caption


def _verdict_text(st: dict) -> str:
    """The verdict, followed by the inconclusive reason in parentheses when one is set."""
    verdict = _fmt_text(st.get("verdict"))
    reason = st.get("inconclusive_reason")
    return f"{verdict} ({reason})" if reason else verdict


def _tbl_statistical(divergence_report: dict):
    """Per-pair chi-square and G-test p-values, effect sizes, power and verdict."""
    records = [r for r in _pairwise_records(divergence_report)
               if (r.get("metrics", {}) or {}).get("statistical_test")]
    headers = ["Pair", "Basis", "chi2 p", "chi2 p (BH)", "G-test p", "G-test p (BH)",
               "Total variation", "Cramér's V", "Power@obs", "Shots/backend for power",
               "Pooled outcomes", "Verdict"]
    rows = []
    for r in records:
        st = r["metrics"]["statistical_test"]
        ef, pw, chi2, gt = (st.get("effect_size") or {}, st.get("power") or {},
                            st.get("chi2") or {}, st.get("g_test") or {})
        rows.append([_pair_key(r), _fmt_text(st.get("basis")),
                     _fmt_p(chi2.get("p_value")), _fmt_p(chi2.get("p_value_bh")),
                     _fmt_p(gt.get("p_value")), _fmt_p(gt.get("p_value_bh")),
                     _fmt_num(ef.get("total_variation")), _fmt_num(ef.get("cramers_v")),
                     _fmt_num(pw.get("power_to_detect_delta_at_observed_shots"), 3),
                     _fmt_int(pw.get("shots_per_backend_for_target_power")),
                     _fmt_int(st.get("pooled_outcomes")), _verdict_text(st)])
    caption = ("Shot-noise-aware homogeneity tests (chi-square + G-test) in the label-aligned "
               "basis (bit-reversed when the declared bit orders differ), with BH-corrected "
               "p-values, effect size and prospective power for a total-variation gap of 0.05. "
               "Outcomes with an expected count below 5 are pooled into one bin. At FDR q = 0.05 "
               "the expected share of false discoveries among flagged pairs is at most q, so a "
               "few flagged pairs are expected by chance. A non-significant pair with power "
               "below 0.8 is inconclusive_low_shots.")
    return headers, rows, "Shot-noise statistical test", caption


def _tbl_matrix(divergence_report: dict, key: str, title: str):
    """The N×N matrix ``key`` with the diagonal and not-compared (None) cells shown as "—"."""
    labels = divergence_report.get("simulators", [])
    mat = divergence_report[key]
    headers = [""] + list(labels)
    rows = []
    for i, s1 in enumerate(labels):
        row = [s1]
        for j in range(len(labels)):
            v = mat[i][j]
            row.append("—" if (i == j or v is None or v == -1.0) else _fmt_num(v))
        rows.append(row)
    caption = f"{title} (raw metric; not-compared pairs and the diagonal shown as —). Symmetric matrix."
    return headers, rows, title, caption


def _tbl_metadata(results: dict, mode: str):
    """Per-backend SDK versions, ordering and sampling labels, opt level and status."""
    headers = ["Simulator", "SDK versions", "Qubit ordering", "Sampling method", "Opt level", "Status"]
    rows = []
    for r in results.get("raw_results", []):
        sdk = ", ".join(f"{k}={_fmt_text(v)}" for k, v in (r.get("sdk_versions") or {}).items()) or "—"
        status = (r.get("dispatch_status") or r.get("status")
                  or ("error" if r.get("error") is not None else "ok"))
        rows.append([_fmt_text(r.get("simulator")), sdk, _fmt_text(r.get("qubit_ordering")),
                     _fmt_text(r.get("sampling_method")), _fmt_int(r.get("optimization_level")),
                     _fmt_text(status)])
    n_shots = results.get("n_shots")
    seed = results.get("seed")
    run_line = f"mode={mode}"
    if n_shots is not None:
        run_line += f", n_shots={_fmt_int(n_shots)}"
    if seed is not None:
        run_line += f", seed={_fmt_int(seed)}"
    caption = f"Run + provenance metadata ({run_line}). Ground-truth executed versions and endpoint labels."
    return headers, rows, "Run and provenance metadata", caption


def _txt_glossary(mode: str) -> str:
    """Markdown glossary of agreement labels, not-comparable reasons and (measured) verdicts."""
    lines = ["# QRosetta agreement taxonomy — glossary", "",
             "Agreement classes (registered-transform lattice):", ""]
    for label, desc in _AGREEMENT_GLOSSARY:
        lines.append(f"- **{label}** — {desc}")
    lines += ["", "Not-comparable reasons (metrics.reason):", ""]
    for label, desc in _NOT_COMPARABLE_GLOSSARY:
        lines.append(f"- **{label}** — {desc}")
    if mode == "measured":
        lines += ["", "Shot-noise statistical verdicts (reported alongside the descriptive label):", ""]
        for label, desc in _VERDICT_GLOSSARY:
            lines.append(f"- **{label}** — {desc}")
        lines += ["", "Measured assessment (measured_assessment, from the verdict):", ""]
        for label, desc in _ASSESSMENT_GLOSSARY:
            lines.append(f"- **{label}** — {desc}")
    lines += ["", "Measurement notes:", ""]
    for note in _MEASUREMENT_NOTES:
        lines.append(f"- {note}")
    lines += ["", "Unranked runs in the timing and resource tables (reason):", ""]
    for label, desc in _UNRANKED_GLOSSARY:
        lines.append(f"- **{label}** — {desc}")
    lines += ["", f"Default thresholds: {_THRESHOLD_DEFAULTS}. A run may override them; the "
              "values applied are recorded in each pairwise record. JS divergence is in "
              f"{JS_UNIT} (maximum ln 2).",
              "", "Each label names the registered transform that explains the pair and reports its "
              "numerical effect; the per-pair records carry full provenance."]
    return "\n".join(lines)


def _txt_executed_qasm(results: dict, runner: str) -> str:
    """The transpiled QASM ``runner`` executed, with a two-line comment header."""
    for r in results.get("raw_results", []):
        if r.get("simulator") == runner:
            tq = r.get("transpiled_qasm")
            header = (f"// Executed (transpiled) OpenQASM for backend: {runner}\n"
                      f"// This is the exact circuit the {runner} adapter ran (after preprocessing).\n")
            return header + (tq or "// (no transpiled QASM recorded for this runner)")
    return f"// no result for runner {runner}"
