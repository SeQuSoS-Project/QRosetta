"""Timing caveats: conditions recorded with a run that limit how far its timings can be
compared across backends, per result and per report. The page's timing tags (throttled,
outside process, unstable, mixed cores) and its "Before comparing times" list are read from
these records. Derived only from fields the results already carry; nothing here changes a
timing, a metric or an agreement label."""

TIMING_CAVEATS_VERSION = "timing-caveats-2026.10.27.2"

THROTTLE_SHOWN_SHARE = 0.01
OUTSIDE_PROCESS_SHOWN_SEC = 0.005
OUTSIDE_PROCESS_SHOWN_SHARE = 0.1
UNSTABLE_SPREAD = 1.3
CORE_CLASS_STEP = 1.1
_EMULATED_CPU_MODELS = ("VirtualApple", "QEMU")

TEXT = {
    "shared_dispatch": "Dispatched beside other runs of the same job (not an exclusive run); runs in one phase share the host's cores and memory bandwidth.",
    "overlapping_runs": "Other runs of this job were executing while this run executed.",
    "server_overlapping_runs": "Runs of other jobs on this server were executing while this run executed.",
    "host_load": "The qrosetta command reported load it put on this host (starting, stopping, building, pulling or probing containers) while this run executed.",
    "throttled": "The CPU quota held the runner for at least 1% of the simulation window; that wait is part of simulation_time_sec.",
    "compilation_throttled": "The CPU quota held the runner for at least 1% of the compilation window; that wait is part of compilation_time_sec.",
    "unstable_repeats": "The timed runs spread by more than 1.3x between the fastest and the slowest simulation time.",
    "mixed_cores": "The timed runs of this backend ran on CPUs of different speed classes (maximum frequencies more than 10% apart).",
    "outside_process": "The runner's container used at least 5 ms and 10% more CPU than the simulating process during the simulation window; that work is not in the process's CPU and memory fields.",
    "single_timed_run": "One timed run (timing_repeats = 1): run-to-run variation is not measured.",
    "no_cpu_quota": "No CPU quota was in force for the runner, so its CPU share depended on other load on the host.",
    "virtualised_host": "The host CPU reports the hypervisor flag: the runner ran in a virtual machine.",
    "emulated_cpu": "The CPU model the runner saw is an emulated one, so timings do not describe native execution.",
    "non_x86_64": "The runner reported a machine architecture other than x86_64.",
    "cross_backend_core_speeds": "The simulation windows of these backends ran on CPUs of different speed classes (maximum frequencies more than 10% apart).",
    "cross_backend_cpu_quota": "Backends ran under different CPU quotas.",
    "cross_backend_image_commits": "Backends ran from images built from different commits, so the measurement code may differ between them.",
}

REPORT_ONLY_WHEN_EVERY_RUN = frozenset({"single_timed_run"})
METRIC_CAVEATS = frozenset({"throttled", "compilation_throttled", "unstable_repeats", "mixed_cores",
                            "outside_process"})


def _num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _caveat(code: str, fields, **detail) -> dict:
    out = {"code": code, "text": TEXT[code], "fields": list(fields)}
    if detail:
        out["detail"] = detail
    return out


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value) -> list:
    return value if isinstance(value, list) else []


def timed(result) -> bool:
    """True for a result without an error (the runs whose timings the page shows)."""
    return isinstance(result, dict) and not result.get("error")


def timed_runs(result: dict) -> int:
    """Number of timed runs behind a result's timing fields: ``timing_samples`` when set,
    else ``timing_repeats``, if a positive integer; else the number of simulation samples, at
    least 1."""
    n = result.get("timing_samples")
    if n is None:
        n = result.get("timing_repeats")
    if _num(n) is not None and float(n).is_integer() and n > 0:
        return int(n)
    return len(_list(result.get("simulation_time_samples"))) or 1


def _throttled(result: dict, held: str, length: str) -> bool:
    t, w = _num(result.get(held)), _num(result.get(length))
    if t is None or not t > 0:
        return False
    return not (w is not None and w > 0 and t < THROTTLE_SHOWN_SHARE * w)


def _outside_process(result: dict) -> bool:
    cg = _num(result.get("simulation_cgroup_cpu_time_sec"))
    own = _num(result.get("simulation_cpu_time_sec"))
    if cg is None or own is None:
        return False
    gap = cg - own
    return gap >= OUTSIDE_PROCESS_SHOWN_SEC and gap >= OUTSIDE_PROCESS_SHOWN_SHARE * cg


def core_speeds(result: dict) -> list:
    """Distinct maximum frequencies (MHz) of the CPUs the simulation windows ran on."""
    mhz = _dict(_dict(result.get("cpu_environment")).get("cpu_max_mhz"))
    speeds = {mhz.get(str(c)) for c in _list(result.get("simulation_cpus"))
              if isinstance(c, (int, str)) and not isinstance(c, bool)}
    return sorted(s for s in speeds if _num(s) is not None)


def core_classes(speeds) -> list:
    """Frequencies grouped into classes: a class starts where one exceeds the previous by more
    than 10%."""
    classes = []
    for s in sorted(speeds):
        if classes and s <= classes[-1][-1] * CORE_CLASS_STEP:
            classes[-1].append(s)
        else:
            classes.append([s])
    return classes


def _unstable(result: dict):
    """``(min, max)`` of the simulation samples when they spread beyond UNSTABLE_SPREAD."""
    samples = [s for s in _list(result.get("simulation_time_samples")) if _num(s) is not None]
    if len(samples) < 3:
        return None
    lo, hi = min(samples), max(samples)
    return (lo, hi) if lo > 0 and hi / lo > UNSTABLE_SPREAD else None


def _quota(result: dict):
    """``(recorded, cores)`` of the result's CPU quota."""
    env = _dict(result.get("cpu_environment"))
    if "cpu_quota_cores" not in env:
        return False, None
    return True, _num(env.get("cpu_quota_cores"))


def result_caveats(result: dict) -> list:
    """The caveats of one result, in a fixed order; a result with an error keeps only the
    METRIC_CAVEATS (its metrics are null, so normally none)."""
    if not isinstance(result, dict):
        return []
    out = []
    concurrent = _num(result.get("concurrent_runs"))
    if result.get("exclusive") is not True and concurrent is not None and concurrent > 1:
        out.append(_caveat("shared_dispatch", ["exclusive", "concurrent_runs"]))
    if (_num(result.get("overlapping_runs")) or 0) > 0:
        out.append(_caveat("overlapping_runs", ["overlapping_runs"]))
    if (_num(result.get("server_overlapping_runs")) or 0) > 0:
        out.append(_caveat("server_overlapping_runs", ["server_overlapping_runs", "exclusive"]))
    if (_num(result.get("server_overlapping_host_load")) or 0) > 0:
        out.append(_caveat("host_load", ["server_overlapping_host_load"]))
    if _throttled(result, "simulation_throttled_sec", "simulation_time_sec"):
        out.append(_caveat("throttled", ["simulation_throttled_sec", "simulation_time_sec"]))
    if _throttled(result, "compilation_throttled_sec", "compilation_time_sec"):
        out.append(_caveat("compilation_throttled", ["compilation_throttled_sec",
                                                     "compilation_time_sec"]))
    spread = _unstable(result)
    if spread:
        out.append(_caveat("unstable_repeats", ["simulation_time_samples"],
                           min_sec=spread[0], max_sec=spread[1]))
    classes = core_classes(core_speeds(result))
    if len(classes) > 1:
        out.append(_caveat("mixed_cores", ["simulation_cpus", "cpu_environment.cpu_max_mhz"],
                           classes_mhz=classes))
    if _outside_process(result):
        out.append(_caveat("outside_process", ["simulation_cgroup_cpu_time_sec",
                                               "simulation_cpu_time_sec"]))
    if timed_runs(result) == 1:
        out.append(_caveat("single_timed_run", ["timing_samples", "timing_repeats"]))
    recorded, cores = _quota(result)
    if recorded and cores is None:
        out.append(_caveat("no_cpu_quota", ["cpu_environment.cpu_quota_cores"]))
    if _dict(result.get("image_identity")).get("host_hypervisor_cpu_flag") is True:
        out.append(_caveat("virtualised_host", ["image_identity.host_hypervisor_cpu_flag"]))
    model = str(_dict(result.get("cpu_environment")).get("cpu_model") or "")
    if any(name in model for name in _EMULATED_CPU_MODELS):
        out.append(_caveat("emulated_cpu", ["cpu_environment.cpu_model"]))
    machine = _dict(result.get("runtime_environment")).get("machine")
    if isinstance(machine, str) and machine and machine != "x86_64":
        out.append(_caveat("non_x86_64", ["runtime_environment.machine"]))
    if result.get("error"):
        out = [c for c in out if c["code"] in METRIC_CAVEATS]
    return out


def _cross_backend(results: list) -> list:
    out = []
    classes = core_classes({s for r in results for s in core_speeds(r)})
    if len(classes) > 1:
        out.append(_caveat("cross_backend_core_speeds",
                           ["simulation_cpus", "cpu_environment.cpu_max_mhz"], classes_mhz=classes))
    quotas = {_quota(r)[1] for r in results if _quota(r)[0]}
    if len(quotas) > 1:
        out.append(_caveat("cross_backend_cpu_quota", ["cpu_environment.cpu_quota_cores"]))
    commits = {str(r.get("image_git_sha")) for r in results if r.get("image_git_sha")}
    if len(commits) > 1:
        out.append(_caveat("cross_backend_image_commits", ["image_git_sha"]))
    return out


def summarize(entries) -> list:
    """Report-level caveats of ``entries`` (``(key, result)`` pairs) over the results without
    an error: each per-result code with the keys it applies to (single_timed_run only when it
    applies to every one; server_overlapping_runs not when every run was exclusive), then the
    cross-backend caveats."""
    by_code, timed_results = {}, []
    for key, result in entries:
        if not timed(result):
            continue
        timed_results.append(result)
        for caveat in result_caveats(result):
            entry = by_code.setdefault(caveat["code"], {**_caveat(caveat["code"], caveat["fields"]),
                                                        "backends": []})
            if key not in entry["backends"]:
                entry["backends"].append(key)
    for code in REPORT_ONLY_WHEN_EVERY_RUN:
        if code in by_code and len(by_code[code]["backends"]) < len(timed_results):
            del by_code[code]
    if timed_results and all(r.get("exclusive") is True for r in timed_results):
        by_code.pop("server_overlapping_runs", None)
    order = list(TEXT)
    out = sorted(by_code.values(), key=lambda c: order.index(c["code"]))
    return out + _cross_backend(timed_results)


def derive(results: list) -> dict:
    """``{results: [per-result caveats], report: [...], version}`` for a list of results."""
    results = [r if isinstance(r, dict) else {} for r in results]
    return {"results": [result_caveats(r) for r in results],
            "report": summarize((str(r.get("simulator")), r) for r in results),
            "version": TIMING_CAVEATS_VERSION}


def annotate(report: dict) -> None:
    """Set ``timing_caveats`` on every runner result and on the report, with
    ``timing_caveats_version``."""
    results = [r for r in report.get("raw_results") or [] if isinstance(r, dict)]
    for r in results:
        r["timing_caveats"] = result_caveats(r)
    report["timing_caveats"] = summarize((str(r.get("simulator")), r) for r in results)
    report["timing_caveats_version"] = TIMING_CAVEATS_VERSION


def combine(lists) -> list:
    """One report-level list from several (the tasks of a playlist): each code once, with
    the union of its fields and backends."""
    by_code = {}
    for caveats in lists:
        for caveat in caveats if isinstance(caveats, list) else []:
            if not isinstance(caveat, dict) or caveat.get("code") not in TEXT:
                continue
            entry = by_code.setdefault(caveat["code"], _caveat(caveat["code"], []))
            for f in caveat.get("fields") or []:
                if f not in entry["fields"]:
                    entry["fields"].append(f)
            if "backends" in caveat:
                backends = entry.setdefault("backends", [])
                backends += [b for b in caveat["backends"] if b not in backends]
    order = list(TEXT)
    return sorted(by_code.values(), key=lambda c: order.index(c["code"]))
