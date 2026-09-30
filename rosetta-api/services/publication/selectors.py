"""Accessors that pull the pieces a figure or table needs out of a report."""

from typing import Any, List

from .formats import _fmt_int, _fmt_text

JS_UNIT = "nats"


def _pairwise_records(divergence_report: dict) -> List[dict]:
    """Return the pairwise_agreement list, or [] when absent."""
    recs = divergence_report.get("pairwise_agreement")
    return recs if isinstance(recs, list) else []


def _pair_key(rec: dict) -> str:
    """Return "a × b" for a pairwise record."""
    s = rec.get("simulators", ["?", "?"])
    return f"{s[0]} × {s[1]}"


def _key_metric(rec: dict) -> Any:
    """Direct fidelity (statevector) or JS divergence (measured) of a pairwise record."""
    m = rec.get("metrics", {}) or {}
    return m.get("direct_fidelity") if rec.get("mode") == "statevector" else m.get("js_divergence")


def _heatmap_specs(mode: str):
    """Return (matrix key, title, artifact id) for each heatmap of ``mode``."""
    if mode == "statevector":
        return [("fidelity_matrix", "Raw statevector fidelity (no transform)", "fidelity_heatmap")]
    return [
        ("statistical_distance_matrix (js_divergence)",
         f"Raw Jensen–Shannon divergence ({JS_UNIT})", "js_divergence_heatmap"),
        ("hellinger_distance_matrix", "Raw Hellinger distance", "hellinger_heatmap"),
    ]


def _raw_by_sim(results: dict) -> dict:
    """Map simulator -> its first raw result."""
    out = {}
    for r in results.get("raw_results") or []:
        sim = r.get("simulator")
        if sim is not None and sim not in out:
            out[sim] = r
    return out


_FAILED_STATUSES = ("error", "timeout", "offline")


def _report_rows(results: dict, report_key: str) -> List[dict]:
    """Ranked entries in rank order, then unranked entries, as
    {entry, raw, ranked, failed, rank, status}.

    ``rank`` is the entry's rank (its 1-based position when absent) or "—" if unranked.
    ``status`` is the raw result's ``dispatch_status``, else its ``status``, else the
    entry's, with "success" shown as "ok". ``failed`` marks error/timeout/offline runs;
    unranked rows that did not fail append the reason, e.g. "ok (missing_timing)".
    """
    report = results.get(report_key) or {}
    raw = _raw_by_sim(results)
    rows = []
    for ranked, entries in ((True, report.get("ranking") or []), (False, report.get("unranked") or [])):
        for i, e in enumerate(entries):
            r = raw.get(e.get("simulator")) or {}
            status = r.get("dispatch_status") or r.get("status") or e.get("status") or "—"
            if status == "success":
                status = "ok"
            failed = not ranked and status in _FAILED_STATUSES
            rank = "—"
            if ranked:
                rank = _fmt_int(e.get("rank") if e.get("rank") is not None else i + 1)
            elif e.get("reason") and e.get("reason") != "runner_error":
                status = f"{status} ({e.get('reason')})"
            elif not failed:
                status = f"{status} ({e.get('reason') or 'unranked'})"
            rows.append({"entry": e, "raw": r, "ranked": ranked, "failed": failed,
                         "rank": rank, "status": status})
    return rows


def _field(row: dict, key: str) -> Any:
    """``key`` from the report entry, falling back to the raw result; None for failed runs."""
    if row.get("failed"):
        return None
    v = row["entry"].get(key)
    return row["raw"].get(key) if v is None else v


def _distinct(results: dict, key: str) -> str:
    """Distinct non-empty values of ``key`` across raw results, comma-joined, or "not recorded"."""
    seen = []
    for r in results.get("raw_results") or []:
        v = r.get(key)
        if v not in (None, "") and _fmt_text(v) not in seen:
            seen.append(_fmt_text(v))
    return ", ".join(seen) if seen else "not recorded"


def _timing_samples(results: dict) -> str:
    """Timing samples per backend: results.timing_samples, else the raw results' values, else 1."""
    top = results.get("timing_samples")
    if top is not None:
        return _fmt_int(top)
    vals = []
    for r in results.get("raw_results") or []:
        v = r.get("timing_samples")
        if v is not None and _fmt_int(v) not in vals:
            vals.append(_fmt_int(v))
    return "/".join(vals) if vals else "1"


COMMON_KEY_ORDER_NOTE = ("keys in msb order (classical bit 0 leftmost); "
                         "lsb-declared backends bit-reversed")


def _msb_counts(results: dict) -> dict:
    """Map simulator -> counts with keys in msb order (lsb-declared backends' keys reversed).

    Backends without usable counts are omitted; keys of a backend without a declared
    lsb/msb order are kept as reported.
    """
    out = {}
    for r in results.get("raw_results") or []:
        sim, counts = r.get("simulator"), r.get("counts")
        if not (isinstance(counts, dict) and counts) or sim in out:
            continue
        if r.get("qubit_ordering") == "lsb":
            flipped = {}
            for k, v in counts.items():
                flipped[k[::-1]] = flipped.get(k[::-1], 0) + v
            counts = flipped
        out[sim] = counts
    return out


def _run_label(results: dict) -> str:
    """"<circuit name>, <n> shots" from task_name/run_name/circuit_name and n_shots."""
    name = results.get("task_name") or results.get("run_name") or results.get("circuit_name")
    parts = [str(name)] if name else ["unnamed circuit"]
    if results.get("n_shots") is not None:
        parts.append(f"{_fmt_int(results.get('n_shots'))} shots per backend")
    return ", ".join(parts)
