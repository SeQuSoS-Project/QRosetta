"""Export views: a figure and/or table (or text) shown together, its parameters, their
validation and the file-name slug. Mirrored by static/js/artifact_views.js."""

import math
from typing import Any, Dict, List, Optional

from .formats import _full, basename_slug

COMMON_PARAMS = {"backends": ("backends", None)}
FIGURE_PARAMS = {"size": ("choice", ("auto", "single", "double", "slide"), "auto"),
                 "title": ("bool", True)}
_COLOUR = ("choice", ("backend", "highlight"), "backend")
_REF = ("backend", None)

VIEWS = [
    {"id": "agreement_distribution", "figure": "agreement_distribution", "params": {}},
    {"id": "agreement", "table": "agreement", "params": {}},
    {"id": "statistical_test", "table": "statistical_test", "params": {}},
    {"id": "counts", "figure": "counts_overview", "table": "counts_table", "params": {
        "layout": ("choice", ("overlay", "panels", "diff", "heatmap"), "overlay"),
        "ref": _REF,
        "outcomes": ("choice", ("top", "threshold", "bits"), "top"),
        "top": ("int", (1, 64), 16),
        "threshold": ("float", (0.0, 1.0), 0.01),
        "bits": ("bits", None),
        "other": ("bool", True),
        "sort": ("choice", ("probability", "bitstring", "hamming"), "probability"),
        "yscale": ("choice", ("linear", "log"), "linear"),
        "band": ("bool", True),
        "keyorder": ("choice", ("msb", "lsb"), "msb"),
        "colour": _COLOUR,
    }},
    {"id": "marginals", "figure": "qubit_marginals", "table": "qubit_marginals_table", "params": {
        "layout": ("choice", ("lines", "diff"), "lines"),
        "ref": _REF,
        "errorbars": ("bool", True),
        "colour": _COLOUR,
    }},
    {"id": "hamming", "figure": "hamming_weight", "table": "hamming_weight_table", "params": {
        "layout": ("choice", ("bars", "lines", "diff"), "bars"),
        "ref": _REF,
        "colour": _COLOUR,
    }},
    {"id": "rank", "figure": "rank_probability", "table": "rank_probability_table", "params": {
        "xscale": ("choice", ("log", "linear"), "log"),
        "ref": _REF,
        "colour": _COLOUR,
    }},
    {"id": "fidelity_heatmap", "figure": "fidelity_heatmap", "table": "matrix_fidelity", "params": {}},
    {"id": "js_divergence_heatmap", "figure": "js_divergence_heatmap", "table": "matrix_js",
     "params": {}},
    {"id": "hellinger_heatmap", "figure": "hellinger_heatmap", "table": "matrix_hellinger",
     "params": {}},
    {"id": "execution_time", "figure": "performance_time", "table": "performance", "params": {
        "stage": ("choice", ("stacked", "simulation", "compilation"), "stacked"),
        "xscale": ("choice", ("linear", "log"), "linear"),
    }},
    {"id": "resource_usage", "figure": "resource_memory", "table": "resources", "params": {
        "metric": ("choice", ("process_peak", "memory_delta"), "process_peak"),
    }},
    {"id": "metadata", "table": "metadata", "params": {}},
    {"id": "glossary", "text": "glossary", "params": {}},
]
VIEW_BY_ID = {v["id"]: v for v in VIEWS}
VIEW_OF_ARTIFACT = {v[k]: v["id"] for v in VIEWS for k in ("figure", "table", "text") if k in v}
MAX_MARGINAL_BITS = 6


def view_param_specs(view_id: str) -> Dict[str, tuple]:
    """Ordered {name: spec} of every parameter the view takes."""
    v = VIEW_BY_ID[view_id]
    specs = dict(COMMON_PARAMS)
    specs.update(v["params"])
    if "figure" in v:
        specs.update(FIGURE_PARAMS)
    return specs


def view_defaults(view_id: str) -> Dict[str, Any]:
    """The view's parameters at their defaults."""
    return {k: (list(s[-1]) if isinstance(s[-1], tuple) else s[-1])
            for k, s in view_param_specs(view_id).items()}


def report_backends(results: dict) -> List[str]:
    """Backends in divergence-report order, then any others present in raw_results."""
    order = list((results.get("divergence_report") or {}).get("simulators") or [])
    seen = set(order)
    for r in results.get("raw_results") or []:
        s = r.get("simulator")
        if s and s not in seen:
            order.append(s)
            seen.add(s)
    return order


def count_bits(results: dict) -> int:
    """Length of the longest counts key in the report (0 without counts)."""
    n = 0
    for r in results.get("raw_results") or []:
        c = r.get("counts")
        if isinstance(c, dict):
            for k in c:
                n = max(n, len(str(k)))
    return n


class ParameterError(ValueError):
    """A view, parameter or format the report cannot take; the message is shown to the user."""


def counted_backends(results: dict) -> List[str]:
    """Backends with a result carrying non-empty counts (the ones _msb_counts keeps), in
    report order."""
    counted = {r.get("simulator") for r in results.get("raw_results") or []
               if isinstance(r.get("counts"), dict) and r["counts"]}
    return [s for s in report_backends(results) if s in counted]


def _check(cond: bool, msg: str):
    if not cond:
        raise ParameterError(msg)


def normalize_params(view_id: str, params: Optional[dict], results: dict) -> Dict[str, Any]:
    """Validate ``params`` for ``view_id`` against ``results`` and fill in defaults.

    ``backends`` becomes None when it lists every backend; ``ref`` the first selected
    backend with counts when None. Raises ParameterError for an unknown view or parameter
    or a bad value.
    """
    _check(view_id in VIEW_BY_ID, f"unknown view '{view_id}'")
    specs = view_param_specs(view_id)
    params = dict(params or {})
    unknown = [k for k in params if k not in specs]
    _check(not unknown, f"unknown parameter(s) for '{view_id}': {', '.join(sorted(unknown))}")
    out = view_defaults(view_id)
    everyone = report_backends(results)
    for key, spec in specs.items():
        if key not in params or params[key] is None:
            continue
        v, kind = params[key], spec[0]
        if kind == "choice":
            _check(v in spec[1], f"{key} must be one of {', '.join(spec[1])}")
        elif kind == "bool":
            _check(isinstance(v, bool), f"{key} must be true or false")
        elif kind == "int":
            _check(isinstance(v, int) and not isinstance(v, bool) and spec[1][0] <= v <= spec[1][1],
                   f"{key} must be an integer from {spec[1][0]} to {spec[1][1]}")
        elif kind == "float":
            _check(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                   and spec[1][0] <= v <= spec[1][1],
                   f"{key} must be a number from {_full(spec[1][0])} to {_full(spec[1][1])}")
            v = float(v)
        elif kind == "backends":
            _check(isinstance(v, list) and all(isinstance(s, str) for s in v),
                   "backends must be a list of backend ids")
            missing = [s for s in v if s not in everyone]
            _check(not missing, f"backends not in this report: {', '.join(missing)}")
            v = [s for s in everyone if s in v]
            _check(len(v) >= 1, "select at least one backend")
            if len(v) == len(everyone):
                v = None
        elif kind == "backend":
            _check(isinstance(v, str), f"{key} must be a backend id")
        elif kind == "bits":
            n = count_bits(results)
            _check(isinstance(v, list) and all(isinstance(b, int) and not isinstance(b, bool)
                                               for b in v),
                   "bits must be a list of classical bit indices")
            _check(1 <= len(v) <= MAX_MARGINAL_BITS and len(set(v)) == len(v),
                   f"bits must list 1 to {MAX_MARGINAL_BITS} distinct classical bits")
            _check(all(0 <= b < n for b in v), f"bits must lie between 0 and {n - 1}")
        out[key] = v
    if "ref" in specs:
        selected = out["backends"] or everyone
        counted = [s for s in counted_backends(results) if s in selected]
        if out["ref"] is None:
            out["ref"] = counted[0] if counted else None
        else:
            _check(out["ref"] in selected, "ref must be one of the selected backends")
            _check(out["ref"] in counted, f"ref must be a backend with counts; {out['ref']} has none")
    if "bits" in specs and out["bits"] is None:
        out["bits"] = list(range(min(3, count_bits(results))))
    return out


def _slug_value(v: Any) -> str:
    if isinstance(v, float):
        return basename_slug(_full(v))
    return basename_slug(str(v))


def view_slug(view_id: str, params: Dict[str, Any], results: dict) -> str:
    """File-name stem for a view: its id plus each non-default parameter."""
    defaults = view_defaults(view_id)
    if "ref" in defaults:
        selected = params.get("backends") or report_backends(results)
        defaults["ref"] = next((s for s in counted_backends(results) if s in selected), None)
    if "bits" in defaults:
        defaults["bits"] = list(range(min(3, count_bits(results))))
    parts = [view_id]
    for key in view_param_specs(view_id):
        v = params.get(key)
        if v == defaults[key]:
            continue
        if key == "backends":
            parts.append(f"{len(v)}-backends")
        elif isinstance(v, bool):
            parts.append(key if v else f"no-{key}")
        elif isinstance(v, list):
            parts.append(f"{key}-" + "-".join(str(x) for x in v))
        else:
            parts.append(f"{key}-{_slug_value(v)}")
    return "_".join(parts)


def dedupe_slugs(slugs: List[str]) -> List[str]:
    """Append -2, -3, ... to repeated slugs, in order."""
    seen: Dict[str, int] = {}
    out = []
    for s in slugs:
        seen[s] = seen.get(s, 0) + 1
        out.append(s if seen[s] == 1 else f"{s}-{seen[s]}")
    return out
