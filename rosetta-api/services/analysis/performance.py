"""Timing and memory rankings across backends.

``ranking`` lists only backends that succeeded and report the ranking metric, in rank
order, each with a 1-based ``rank``. Everything else is listed in ``unranked`` with a
``reason``, so ``ranking[0]`` is absent when no backend succeeded. A failed run's
``status`` is its ``dispatch_status`` (error, timeout or offline). Every entry carries the
``device`` the run reported ("CPU" when it reported none). A run with two or more timing
samples also carries its median total time (median compilation + median simulation) and
the IQR and stdev of the per-run totals, and is ranked by the median total.
"""

from .timing import stage_median, timing_samples, timing_summary

_FAILED_DISPATCH = ("error", "timeout", "offline")
_FAILURE_REASON = {"error": "runner_error", "timeout": "runner_timeout",
                   "offline": "runner_offline"}


def _failure_status(res):
    """"error"/"timeout"/"offline" for a failed run, else None."""
    dispatch_status = res.get("dispatch_status")
    if dispatch_status in _FAILED_DISPATCH:
        return dispatch_status
    if res.get("error") not in (None, ""):
        return "error"
    return None


def _device(res):
    """The run's device, upper-cased; "CPU" when the result reports none."""
    device = res.get("device")
    return str(device).upper() if device not in (None, "") else "CPU"


def _rank(entries, metric):
    """Sort ranked entries ascending by ``metric`` (stable) and assign 1-based ranks.

    ``metric`` is a key or a function of the entry."""
    key = metric if callable(metric) else (lambda x: x[metric])
    ordered = sorted(entries, key=key)
    for position, entry in enumerate(ordered, start=1):
        entry["rank"] = position
    return ordered


def create_performance_report(results_list: list) -> dict:
    """Rank backends by execution_time_sec, fastest first."""
    ranked = []
    unranked = []

    for res in results_list:
        sim_name = res.get('simulator', 'unknown')

        failure = _failure_status(res)
        if failure:
            unranked.append({
                "simulator": sim_name,
                "device": _device(res),
                "status": failure,
                "reason": _FAILURE_REASON[failure],
                "error": res.get('error'),
                "execution_time_sec": None,
                "rank": None,
            })
        elif res.get('execution_time_sec') is None:
            unranked.append({
                "simulator": sim_name,
                "device": _device(res),
                "status": "error",
                "reason": "missing_timing",
                "error": "Result carried no execution_time_sec.",
                "execution_time_sec": None,
                "rank": None,
            })
        else:
            entry = {
                "simulator": sim_name,
                "device": _device(res),
                "status": "success",
                "execution_time_sec": res['execution_time_sec'],
                "compilation_time_sec": res.get('compilation_time_sec'),
                "simulation_time_sec": res.get('simulation_time_sec'),
                "cpu_time_sec": res.get('cpu_time_sec'),
                "gate_count": res.get('gate_count'),
                "circuit_depth": res.get('circuit_depth'),
            }
            entry.update(_repeat_statistics(res))
            ranked.append(entry)

    repeated = any("execution_time_sec_median" in e for e in ranked)
    ordered = _rank(ranked, lambda e: e.get("execution_time_sec_median", e["execution_time_sec"]))
    _mark_overlaps(ordered, {r.get("simulator"): r for r in results_list})
    return {
        "summary": ("Execution time in seconds: median compilation + median simulation over "
                    "the timed runs (fastest first)."
                    if repeated else "Execution time in seconds (fastest first)."),
        "ranking_metric": "execution_time_sec_median" if repeated else "execution_time_sec",
        "ranking": ordered,
        "overlap_rule": OVERLAP_RULE,
        "unranked": unranked,
    }


OVERLAP_RULE = ("overlaps_next is true when this backend's slowest per-run total time is at "
                "least the next-ranked backend's fastest per-run total, so these runs do not "
                "separate the two; None when either has fewer than two timed runs.")


def _mark_overlaps(ordered, raw_by_simulator):
    """Set ``overlaps_next`` on each ranked entry (see OVERLAP_RULE); None for the last."""
    totals = [timing_samples(raw_by_simulator.get(e["simulator"]) or {}, "execution_time")
              for e in ordered]
    for i, entry in enumerate(ordered):
        nxt = totals[i + 1] if i + 1 < len(ordered) else None
        mine = totals[i]
        if nxt is None or mine is None or len(mine) < 2 or len(nxt) < 2:
            entry["overlaps_next"] = None
        else:
            entry["overlaps_next"] = bool(max(mine) >= min(nxt))


def create_resource_report(results_list: list) -> dict:
    """Rank backends by process_peak_rss_mb, lowest first.

    process_peak_rss_mb is the simulating process's own peak RSS (VmHWM) over its
    whole life: interpreter start, SDK import, warm-up and the timed run. The memory fields
    are host RSS, so a GPU run is unranked with reason ``gpu_memory_not_measured``.
    """
    ranked = []
    unranked = []

    for res in results_list:
        sim_name = res.get('simulator', 'unknown')

        failure = _failure_status(res)
        if failure:
            unranked.append({
                "simulator": sim_name,
                "device": _device(res),
                "status": failure,
                "reason": _FAILURE_REASON[failure],
                "error": res.get('error'),
                "process_peak_rss_mb": res.get('process_peak_rss_mb'),
                "memory_usage_mb": None,
                "process_peak_mb": None,
                "rank": None,
            })
            continue

        entry = {
            "simulator": sim_name,
            "device": _device(res),
            "status": "success",
            "process_peak_rss_mb": res.get('process_peak_rss_mb'),
            "memory_usage_mb": res.get('memory_usage_mb'),
            "process_peak_mb": res.get('process_peak_mb'),
            "theoretical_statevector_mb": res.get('theoretical_statevector_mb'),
        }
        if entry["process_peak_rss_mb"] is None:
            entry.update({"reason": "missing_process_peak_rss", "rank": None})
            unranked.append(entry)
        elif entry["device"] == "GPU":
            entry.update({"reason": "gpu_memory_not_measured", "rank": None})
            unranked.append(entry)
        else:
            ranked.append(entry)

    return {
        "summary": "Process peak RSS in MiB (lowest first).",
        "ranking_metric": "process_peak_rss_mb",
        "ranking": _rank(ranked, "process_peak_rss_mb"),
        "unranked": unranked,
    }


def _repeat_statistics(res):
    """Median total time and the IQR and stdev of the per-run totals for a result with two
    or more timing samples; {} otherwise."""
    total = timing_summary(res, "execution_time")
    if total is None:
        return {}
    return {
        "execution_time_sec_median": stage_median(res, "execution_time"),
        "execution_time_sec_iqr": total["iqr"],
        "execution_time_sec_stdev": total["stdev"],
        "timing_samples": total["n"],
        "timing_statistic": "median",
    }
