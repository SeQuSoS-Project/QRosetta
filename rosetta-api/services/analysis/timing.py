"""Summary statistics of repeated timed runs, mirrored by static/js/artifact_formats.js."""

import math
import numbers

TIMING_BASES = ("compilation_time", "simulation_time", "execution_time")


def _is_number(v):
    return isinstance(v, numbers.Real) and not isinstance(v, bool) and math.isfinite(float(v))


def _listed(res, base):
    for key in (f"{base}_samples", f"{base}_sec_samples"):
        v = res.get(key)
        if isinstance(v, list) and v and all(_is_number(x) for x in v):
            return [float(x) for x in v]
    return None


def timing_samples(res, base):
    """The per-run samples of ``base`` (e.g. "simulation_time") recorded on a result, or None.

    Reads ``<base>_samples`` or ``<base>_sec_samples``. Total time without its own samples
    is the per-run sum of the compilation and simulation samples.
    """
    samples = _listed(res, base)
    if samples is None and base == "execution_time":
        comp = _listed(res, "compilation_time")
        sim = _listed(res, "simulation_time")
        if comp and sim and len(comp) == len(sim):
            samples = [c + s for c, s in zip(comp, sim)]
    return samples


def _quantile(ordered, q):
    """Linear-interpolation quantile of an ascending list."""
    pos = (len(ordered) - 1) * q
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(ordered) - 1)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def _median(ordered):
    """Middle value, or the mean of the two middle values (statistics.median)."""
    n = len(ordered)
    mid = n // 2
    return ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def summarize(samples):
    """{n, median, q1, q3, iqr, stdev} of a sample list; stdev is the n-1 sample stdev."""
    ordered = sorted(samples)
    n = len(ordered)
    total = 0.0
    for x in ordered:
        total += x
    mean = total / n
    ss = 0.0
    for x in ordered:
        d = x - mean
        ss += d * d
    q1, q3 = _quantile(ordered, 0.25), _quantile(ordered, 0.75)
    return {"n": n, "median": _median(ordered), "q1": q1, "q3": q3, "iqr": q3 - q1,
            "stdev": math.sqrt(ss / (n - 1)) if n > 1 else 0.0}


def timing_summary(res, base):
    """summarize() of the result's ``base`` samples when it has at least two, else None."""
    samples = timing_samples(res, base)
    if samples is None or len(samples) < 2:
        return None
    return summarize(samples)


def stage_median(res, base):
    """Median of ``base`` over two or more timing samples, else None. Total time is the
    median compilation time plus the median simulation time, as execution_time_sec is
    reported; without both it is the median of the per-run totals."""
    if base == "execution_time":
        comp = timing_summary(res, "compilation_time")
        sim = timing_summary(res, "simulation_time")
        if comp and sim:
            return comp["median"] + sim["median"]
    stats = timing_summary(res, base)
    return stats["median"] if stats else None
