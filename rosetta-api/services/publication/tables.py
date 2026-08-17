# Table and text-blob builders. Each returns (headers, rows, title, caption) or a string.


from .theme import _AGREEMENT_GLOSSARY, _VERDICT_GLOSSARY
from .formats import _fmt_num
from .selectors import _key_metric, _pair_key, _pairwise_records


def _tbl_agreement(divergence_report: dict, mode: str):
    records = _pairwise_records(divergence_report)
    measured = mode == "measured"
    headers = ["Pair", "Agreement", "Registered transform",
               "Fidelity" if not measured else "JS divergence"]
    if measured:
        headers.append("Stat verdict")
    rows = []
    for r in records:
        row = [_pair_key(r), r.get("agreement", "—"), r.get("registered_transform") or "—",
               _fmt_num(_key_metric(r))]
        if measured:
            row.append(((r.get("metrics", {}) or {}).get("statistical_test") or {}).get("verdict", "—"))
        rows.append(row)
    caption = ("Classification over the registered-transform lattice; each label reports the "
               "transform whose numerical effect explains the pair.")
    return headers, rows, "Pairwise explained-cause agreement", caption


def _tbl_performance(results: dict):
    ranking = (results.get("performance_report") or {}).get("ranking", [])
    headers = ["Rank", "Simulator", "Compilation (s)", "Simulation (s)", "Total (s)", "CPU (s)",
               "Gate count", "Depth", "Status"]
    rows = [[i + 1, r.get("simulator", "—"), _fmt_num(r.get("compilation_time_sec"), 6),
             _fmt_num(r.get("simulation_time_sec"), 6), _fmt_num(r.get("execution_time_sec"), 6),
             _fmt_num(r.get("cpu_time_sec"), 6), _fmt_num(r.get("gate_count")),
             _fmt_num(r.get("circuit_depth")), r.get("status", "—")]
            for i, r in enumerate(ranking)]
    caption = ("Wall-clock and CPU timings measured by QRosetta (raw), after a uniform disclosed "
               "warm-up run precedes every timed measurement. Gate count/depth are derived from "
               "each backend's own transpiled QASM.")
    return headers, rows, "Execution timing", caption


def _tbl_resources(results: dict):
    ranking = (results.get("resource_report") or {}).get("ranking", [])
    headers = ["Rank", "Simulator", "Process peak RSS (MiB)", "Mem delta (MiB)",
               "Process peak (MiB)", "Theoretical SV (MiB)", "Status"]
    rows = [[i + 1, r.get("simulator", "—"), _fmt_num(r.get("process_peak_rss_mb"), 1),
             _fmt_num(r.get("memory_usage_mb")), _fmt_num(r.get("process_peak_mb"), 1),
             _fmt_num(r.get("theoretical_statevector_mb")), r.get("status", "—")]
            for i, r in enumerate(ranking)]
    caption = ("Process peak RSS (raw, resource.getrusage) is the kernel-reported peak of the "
               "whole isolated run, including compilation and the warm-up; ranking is by this "
               "column. Mem delta / Process peak are each backend's own sim-window measurement.")
    return headers, rows, "Resource usage", caption


def _tbl_statistical(divergence_report: dict):
    records = [r for r in _pairwise_records(divergence_report)
               if (r.get("metrics", {}) or {}).get("statistical_test")]
    headers = ["Pair", "Basis", "chi2 p", "chi2 p (BH)", "G-test p", "G-test p (BH)",
               "Total variation", "Cramér's V", "Power@obs", "Shots/backend for power", "Verdict"]
    rows = []
    for r in records:
        st = r["metrics"]["statistical_test"]
        ef, pw, chi2, gt = (st.get("effect_size", {}), st.get("power", {}),
                            st.get("chi2", {}), st.get("g_test", {}))
        rows.append([_pair_key(r), st.get("basis", "—"),
                     _fmt_num(chi2.get("p_value")), _fmt_num(chi2.get("p_value_bh")),
                     _fmt_num(gt.get("p_value")), _fmt_num(gt.get("p_value_bh")),
                     _fmt_num(ef.get("total_variation")), _fmt_num(ef.get("cramers_v")),
                     _fmt_num(pw.get("power_to_detect_delta_at_observed_shots"), 3),
                     pw.get("shots_per_backend_for_target_power", "—"), st.get("verdict", "—")])
    caption = ("Shot-noise-aware homogeneity tests (chi-square + G-test) with BH-corrected p-values, "
               "effect size, and prospective power, reported alongside the descriptive label.")
    return headers, rows, "Shot-noise statistical test", caption


def _tbl_matrix(divergence_report: dict, key: str, title: str):
    labels = divergence_report.get("simulators", [])
    mat = divergence_report[key]
    headers = [""] + list(labels)
    rows = []
    for i, s1 in enumerate(labels):
        row = [s1]
        for j in range(len(labels)):
            v = mat[i][j]
            row.append("—" if (i == j or v == -1.0) else _fmt_num(v))
        rows.append(row)
    caption = f"{title} (raw metric; −1 / diagonal shown as —). Symmetric matrix."
    return headers, rows, title, caption


def _tbl_metadata(results: dict, mode: str):
    headers = ["Simulator", "SDK versions", "Qubit ordering", "Sampling method", "Opt level", "Status"]
    rows = []
    for r in results.get("raw_results", []):
        sim = r.get("simulator", "—")
        sdk = ", ".join(f"{k}={v}" for k, v in (r.get("sdk_versions") or {}).items()) or "—"
        rows.append([sim, sdk, r.get("qubit_ordering", "—"), r.get("sampling_method", "—"),
                     r.get("optimization_level", "—"), "error" if r.get("error") else "completed"])
    n_shots = results.get("n_shots")
    seed = results.get("seed")
    run_line = f"mode={mode}"
    if n_shots is not None:
        run_line += f", n_shots={n_shots}"
    if seed is not None:
        run_line += f", seed={seed}"
    caption = f"Run + provenance metadata ({run_line}). Ground-truth executed versions and endpoint labels."
    return headers, rows, "Run and provenance metadata", caption


# --- Text-blob builders (return str) --------------------------------------------------

def _txt_glossary(mode: str) -> str:
    lines = ["# QRosetta agreement taxonomy — glossary", "",
             "Agreement classes (registered-transform lattice):", ""]
    for label, desc in _AGREEMENT_GLOSSARY:
        lines.append(f"- **{label}** — {desc}")
    if mode == "measured":
        lines += ["", "Shot-noise statistical verdicts (reported alongside the descriptive label):", ""]
        for label, desc in _VERDICT_GLOSSARY:
            lines.append(f"- **{label}** — {desc}")
    lines += ["", "Each label names the registered transform that explains the pair and reports its "
              "numerical effect; the per-pair records carry full provenance."]
    return "\n".join(lines)


def _txt_executed_qasm(results: dict, runner: str) -> str:
    for r in results.get("raw_results", []):
        if r.get("simulator") == runner:
            tq = r.get("transpiled_qasm")
            header = (f"// Executed (transpiled) OpenQASM for backend: {runner}\n"
                      f"// This is the exact circuit the {runner} adapter ran (after preprocessing).\n")
            return header + (tq or "// (no transpiled QASM recorded for this runner)")
    return f"// no result for runner {runner}"
