"""Table builders, returning (headers, rows, title, caption), and text-blob builders."""

from .theme import (
    _AGREEMENT_GLOSSARY, _ANALYSIS_VERSION_NOTE, _ASSESSMENT_GLOSSARY, _MEASUREMENT_NOTES,
    _NOT_COMPARABLE_GLOSSARY,
    _THRESHOLD_DEFAULTS, _UNRANKED_GLOSSARY, _VERDICT_GLOSSARY,
)
from .formats import _fmt_int, _fmt_num, _fmt_text, _format_columns, _num, _pnum
from .selectors import (
    DEVICE_NOTE, GPU_MEMORY_NOTE, JS_UNIT, _device, _distinct, _field, _key_metric, _pair_key,
    _pairwise_records, _report_rows, _timing_repeated, _timing_samples, _timing_stats,
    _timing_value,
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
        headers += ["Direct fidelity", "Fidelity, label-aligned basis", "Unaligned-basis match"]
    headers.append("Not-comparable reason")
    rows = []
    for r in records:
        m = r.get("metrics") or {}
        row = [_pair_key(r), _fmt_text(r.get("agreement")),
               _fmt_text(r.get("registered_transform")), _num(_key_metric(r))]
        if measured:
            row += [_num(m.get("label_aligned_js_divergence")),
                    _fmt_text((m.get("statistical_test") or {}).get("verdict")),
                    _fmt_text(r.get("measured_assessment"))]
        else:
            row += [_num(m.get("label_aligned_fidelity")), _fmt_text(m.get("unaligned_basis_match"))]
        row.append(_fmt_text(m.get("reason")) if r.get("agreement") == "not_comparable" else "—")
        rows.append(row)
    rows = _format_columns(rows)
    metric = (f"JS, direct is the Jensen–Shannon divergence in {JS_UNIT} of the keys as "
              "reported; JS, label-aligned basis bit-reverses the second backend's keys when the "
              "two declared bit orders differ (lsb vs msb) and equals the direct value otherwise"
              if measured else
              "Direct fidelity is |<a|b>|^2 of the normalised vectors before any transform; "
              "the label-aligned basis bit-reverses the second vector when the two declared "
              "qubit orderings differ (lsb vs msb) and the label is assigned in it. "
              "Unaligned-basis match names the other basis when the pair matches only there, "
              "which is a disagreement")
    caption = ("Classification over the registered-transform lattice; each label reports the "
               f"transform whose numerical effect explains the pair. {metric}.")
    if measured:
        caption += (" Measured assessment combines the descriptive label with the shot-noise "
                    "verdict: a pair over the distance thresholds whose verdict is consistent "
                    "is consistent_within_shot_noise.")
    return headers, rows, "Pairwise explained-cause agreement", caption


def _tbl_performance(results: dict):
    """Per-backend timings: ranked runs by total time, then unranked runs with the reason.

    With two or more timing samples on any result the stage columns are medians, followed
    by the IQR, stdev and sample count of total time."""
    if _timing_repeated(results):
        return _tbl_performance_repeated(results)
    headers = ["Rank", "Simulator", "Device", "Compilation (s)", "Simulation (s)", "Total (s)",
               "Simulation CPU (s)", "Process CPU (s)", "Gate count", "Depth", "Status"]
    rows = _format_columns([[row["rank"],
             _fmt_text(row["entry"].get("simulator")), _device(row),
             _num(_field(row, "compilation_time_sec"), 6),
             _num(_field(row, "simulation_time_sec"), 6),
             _num(_field(row, "execution_time_sec"), 6),
             _num(_field(row, "simulation_cpu_time_sec"), 6),
             _num(_field(row, "cpu_time_sec"), 6),
             _fmt_int(_field(row, "gate_count")), _fmt_int(_field(row, "circuit_depth")),
             row["status"]]
            for row in _report_rows(results, "performance_report")])
    caption = (f"Wall-clock times of the timed run, n={_timing_samples(results)} timing sample(s) "
               "per backend; a warm-up run precedes it and is not included. Total = compilation "
               "+ simulation. Simulation CPU is process CPU time over the simulation window. "
               "Process CPU is getrusage CPU time of the whole isolated runner process, "
               "including interpreter start, imports and the warm-up. Ranked by total time, "
               "fastest first; runs without a rank follow with the reason in Status. Gate "
               "count and depth describe the circuit each backend executed (gate_metrics_basis)."
               f"{_run_conditions(results)} {DEVICE_NOTE}")
    return headers, rows, "Execution timing", caption


def _run_conditions(results: dict) -> str:
    """Caption sentence on whether the successful runs ran exclusively or overlapped others."""
    raws = [r for r in results.get("raw_results") or [] if isinstance(r, dict) and not r.get("error")]
    if not raws:
        return ""
    if all(r.get("exclusive") is True for r in raws):
        return (" Exclusive run: the backends ran one at a time with no other run in flight on "
                "the server.")

    def most(key):
        return max([int(r[key]) for r in raws if isinstance(r.get(key), (int, float))
                    and not isinstance(r.get(key), bool)] or [0])
    own, other = most("overlapping_runs"), most("server_overlapping_runs")
    if not own and not other:
        return ""
    return (f" Runs overlapped in time with up to {own} other run(s) of this job and {other} "
            f"run(s) of other jobs (overlapping_runs, server_overlapping_runs); overlapping runs "
            f"share cores and memory bandwidth.")


def _tbl_performance_repeated(results: dict):
    """_tbl_performance with median stage times and the spread of total time."""
    headers = ["Rank", "Simulator", "Device", "Compilation median (s)", "Simulation median (s)",
               "Total median (s)", "Total IQR (s)", "Total stdev (s)", "n",
               "Simulation CPU (s)", "Process CPU (s)", "Gate count", "Depth", "Status"]
    rows = []
    for row in _report_rows(results, "performance_report"):
        total = _timing_stats(row, "execution_time_sec")
        n = total["n"] if total else (None if row["failed"] else 1)
        rows.append([row["rank"], _fmt_text(row["entry"].get("simulator")), _device(row),
                     _num(_timing_value(row, "compilation_time_sec"), 6),
                     _num(_timing_value(row, "simulation_time_sec"), 6),
                     _num(_timing_value(row, "execution_time_sec"), 6),
                     _num(total["iqr"] if total else None, 6),
                     _num(total["stdev"] if total else None, 6),
                     _fmt_int(n),
                     _num(_field(row, "simulation_cpu_time_sec"), 6),
                     _num(_field(row, "cpu_time_sec"), 6),
                     _fmt_int(_field(row, "gate_count")), _fmt_int(_field(row, "circuit_depth")),
                     row["status"]])
    rows = _format_columns(rows)
    caption = ("Median wall-clock times over the n timed runs of each backend (column n); a "
               "warm-up run precedes them and is not included. Total median = compilation "
               "median + simulation median, the reported execution_time_sec. Total IQR is the "
               "interquartile range (Q3 - Q1, linear interpolation) and Total stdev the sample "
               "standard deviation (n - 1) of the per-run totals (compilation + simulation); "
               "both are — for a backend with one run. Simulation CPU is the median over the "
               "timed runs of process CPU time from t2 to t3; process CPU is getrusage CPU "
               "time of the whole isolated runner process, including interpreter start, "
               "imports, the warm-up and every timed run. Ranked by median total time, fastest first; runs without a rank "
               "follow with the reason in Status. Gate count and depth describe the circuit each "
               f"backend executed (gate_metrics_basis).{_run_conditions(results)} {DEVICE_NOTE}")
    return headers, rows, "Execution timing", caption


def _tbl_resources(results: dict):
    """Per-backend memory: ranked runs by process peak RSS, then unranked runs with the reason."""
    headers = ["Rank", "Simulator", "Device", "Process peak RSS (MiB)",
               "Sim-window peak RSS (MiB)", "Sim-window RSS delta (MiB)", "Theoretical SV (MiB)",
               "Precision", "Status"]
    rows = _format_columns([[row["rank"],
             _fmt_text(row["entry"].get("simulator")), _device(row),
             _num(_field(row, "process_peak_rss_mb"), 1),
             _num(_field(row, "process_peak_mb"), 1),
             _num(_field(row, "memory_usage_mb")),
             _num(_field(row, "theoretical_statevector_mb")),
             _fmt_text(_field(row, "precision")), row["status"]]
            for row in _report_rows(results, "resource_report")])
    caption = ("Process peak RSS is the peak resident memory of the simulating process over its "
               "whole life (interpreter start, imports, warm-up and every timed run); method: "
               f"{_distinct(results, 'process_peak_rss_method')}. Rows are ranked by it, lowest "
               "first; runs without a rank follow with the reason in Status. Sim-window peak RSS "
               "and RSS delta (peak minus RSS at monitor entry) cover the pre-execute step and "
               f"simulation window of the first timed run; method: {_distinct(results, 'memory_method')}. "
               "Theoretical SV is 2^n × 16 bytes (8 for complex64) for the declared qubit count. 1 MiB = 1024^2 bytes. "
               "For small circuits process peak RSS is dominated by the SDK import footprint; "
               "the sim-window RSS delta is the memory the simulation window added, near 0 when it reuses memory the warm-up freed. "
               f"{GPU_MEMORY_NOTE} {DEVICE_NOTE}")
    return headers, rows, "Resource usage", caption


def _verdict_text(st: dict) -> str:
    """The verdict, followed by the inconclusive reason in parentheses when one is set."""
    verdict = _fmt_text(st.get("verdict"))
    reason = st.get("inconclusive_reason")
    if not reason:
        return verdict
    if st.get("resolvable_by_more_shots") is False:
        reason += "; not resolvable by more shots"
    return f"{verdict} ({reason})"


def _power_alpha_text(records) -> str:
    """" = <alpha_used> (m = <m_pairs>, c_m = <c_m>)" from the first record that records
    them, else ""."""
    for r in records:
        pw = r["metrics"]["statistical_test"].get("power") or {}
        if pw.get("alpha_used") is not None and pw.get("m_pairs") is not None:
            c_m = f", c_m = {_fmt_num(pw['c_m'])}" if pw.get("c_m") is not None else ""
            return f" = {_fmt_num(pw['alpha_used'])} (m = {_fmt_int(pw['m_pairs'])}{c_m})"
    return ""


def _tbl_statistical(divergence_report: dict):
    """Per-pair chi-square and G-test p-values, effect sizes, power and verdict."""
    records = [r for r in _pairwise_records(divergence_report)
               if (r.get("metrics", {}) or {}).get("statistical_test")]
    headers = ["Pair", "Basis", "chi2 p", "chi2 p (BY)", "G-test p", "G-test p (BY)",
               "Total variation", "Cramér's V", "Power@obs", "Shots/backend for power",
               "Pooled outcomes", "Verdict"]
    rows = []
    for r in records:
        st = r["metrics"]["statistical_test"]
        ef, pw, chi2, gt = (st.get("effect_size") or {}, st.get("power") or {},
                            st.get("chi2") or {}, st.get("g_test") or {})
        rows.append([_pair_key(r), _fmt_text(st.get("basis")),
                     _pnum(chi2.get("p_value")), _pnum(chi2.get("p_value_by")),
                     _pnum(gt.get("p_value")), _pnum(gt.get("p_value_by")),
                     _num(ef.get("total_variation")), _num(ef.get("cramers_v")),
                     _num(pw.get("power_to_detect_delta_at_observed_shots"), 3),
                     _fmt_int(pw.get("shots_per_backend_for_target_power")),
                     _fmt_int(st.get("pooled_outcomes")), _verdict_text(st)])
    rows = _format_columns(rows)
    caption = ("Shot-noise-aware homogeneity tests (chi-square + G-test) in the label-aligned "
               "basis (bit-reversed when the declared bit orders differ), with "
               "Benjamini-Yekutieli (BY) adjusted p-values and effect size. A pair is "
               "distinguishable only when both tests are significant after BY over the m "
               "comparable pairs. BY controls the false discovery rate at q = 0.05 under any "
               "dependence between the tests, including pairs that share one backend's "
               "sample; a flagged pair can still be a false discovery. Power@obs is the power "
               "of the chi-square test to detect a total-variation gap of 0.05 at "
               f"alpha/(m·c_m){_power_alpha_text(records)}, the threshold BY applies to a "
               "single discovery: a lower bound for detecting one wrong backend. Outcomes with "
               "an expected count below 5 are pooled into one bin. A non-significant pair with "
               "power below 0.8 is inconclusive_low_shots.")
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
            row.append("—" if (i == j or v is None or v == -1.0) else _num(v))
        rows.append(row)
    rows = _format_columns(rows)
    caption = f"{title} (raw metric; not-compared pairs and the diagonal shown as —). Symmetric matrix."
    return headers, rows, title, caption


def _tbl_metadata(results: dict, mode: str):
    """Per-backend SDK versions, ordering and sampling labels, opt level and status."""
    headers = ["Simulator", "Device", "SDK versions", "Qubit ordering", "Sampling method",
               "Opt level", "Status"]
    rows = []
    for r in results.get("raw_results", []):
        sdk = ", ".join(f"{k}={_fmt_text(v)}" for k, v in (r.get("sdk_versions") or {}).items()) or "—"
        status = (r.get("dispatch_status") or r.get("status")
                  or ("error" if r.get("error") is not None else "ok"))
        device = _device({"entry": {}, "raw": r})
        if r.get("gpu_name"):
            device += f" ({_fmt_text(r.get('gpu_name'))})"
        rows.append([_fmt_text(r.get("simulator")), device, sdk, _fmt_text(r.get("qubit_ordering")),
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
              "values applied are recorded in each pairwise record and in the divergence "
              f"report's agreement_thresholds. JS divergence is in {JS_UNIT} (maximum ln 2).",
              "", _ANALYSIS_VERSION_NOTE,
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
