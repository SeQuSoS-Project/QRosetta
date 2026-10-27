"""Pair verdicts and per-backend counts: whether a pair of backends differs, agrees, is
inconclusive or was not compared, how many backends each one differs from, and the headline
model built from those counts (``headline.py``).

The aggregator records them in every new divergence report (``pair_verdict`` on each pair,
``backend_verdicts`` on the report); the summary routes apply the same functions to any
report, so a report without the fields gets the answers a new one records. Fields of an
unexpected type are read with JavaScript's conventions (``_truthy``, ``_member``,
``_property_key``)."""

import math
import re

from .headline import headline_model

_DISPATCH_STATUSES = ("ok", "error", "timeout", "offline")

_VERDICT_TO_ASSESSMENT = {
    "consistent": "consistent_within_shot_noise",
    "inconclusive_low_shots": "inconclusive_low_shots",
    "distinguishable": "distinguishable",
    "ambiguous": "ambiguous",
}

_INCONCLUSIVE = ("inconclusive_low_shots", "ambiguous")

_CONNECTION_PHRASES = (
    "connection refused", "name or service not known", "failed to connect", "failed to fetch",
    "load resource", "failed to get response", "502 bad gateway", "service unavailable",
    "failed to decode json",
)

_JS_SPACE = "\t\n\x0b\x0c\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
_TIMEOUT_RE = re.compile(f"time(d)?[{_JS_SPACE}]?out", re.IGNORECASE | re.ASCII)
_MULTI_RUN_RE = re.compile(r"([^\n\r\u2028\u2029]+)~opt([0-9]+)~run([0-9]+)")
_ARRAY_INDEX_RE = re.compile(r"0|[1-9][0-9]*")


def _get(obj, key):
    """``obj[key]`` for a JSON object, else None (a missing member)."""
    return obj.get(key) if isinstance(obj, dict) else None


def _coalesce(*values):
    """The first value that is not None."""
    return next((v for v in values if v is not None), None)


def _truthy(v) -> bool:
    """Truth of a JSON value as the browser tests it: every object and array is true."""
    if v is None or v is False:
        return False
    if isinstance(v, (dict, list)) or v is True:
        return True
    if isinstance(v, (int, float)):
        return v != 0
    return bool(v)


def _js_string(v) -> str:
    """Text of a JSON value as String() gives it, for the values the rule matches text in."""
    if isinstance(v, str):
        return v
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, list):
        return ",".join("" if e is None else _js_string(e) for e in v)
    if isinstance(v, dict):
        return "[object Object]"
    if isinstance(v, float) and v.is_integer() and abs(v) < 1e21:
        return str(int(v))
    return str(v)


def _property_key(v):
    """The property name a value is looked up under in a table keyed by words, or None
    when it cannot name a word (a number, or text joined from two or more elements)."""
    if isinstance(v, str):
        return v
    if isinstance(v, list) and len(v) == 1:
        return _property_key(v[0]) if v[0] is not None else None
    return None


def _member(obj, key: str):
    """``obj[key]`` for a computed key: an object's own member, an array's or a text's
    element or length; None otherwise."""
    if isinstance(obj, dict):
        return obj.get(key)
    if isinstance(obj, (list, str)):
        if key == "length":
            return len(obj)
        if _ARRAY_INDEX_RE.fullmatch(key) and int(key) < len(obj):
            return obj[int(key)]
    return None


def _number(x):
    """A finite JSON number, else None."""
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    try:
        as_float = float(x)
    except OverflowError:
        return None
    if not math.isfinite(as_float):
        return None
    return x if isinstance(x, float) or abs(x) <= 2 ** 53 else as_float


def is_connection_error(error) -> bool:
    """Whether an error text names an unreachable service."""
    if not _truthy(error):
        return False
    msg = _js_string(error).lower()
    return any(phrase in msg for phrase in _CONNECTION_PHRASES)


def runner_status(result) -> str:
    """'ok', 'error', 'timeout' or 'offline': the result's dispatch_status, or for results
    without one, a reading of its error text."""
    if not _truthy(result):
        return "offline"
    status = _get(result, "dispatch_status")
    if isinstance(status, str) and status in _DISPATCH_STATUSES:
        return status
    error = _get(result, "error")
    if not _truthy(error):
        return "ok"
    if is_connection_error(error):
        return "offline"
    if _TIMEOUT_RE.search(_js_string(error)):
        return "timeout"
    return "error"


def effective_agreement(p):
    """The pair's agreement label, or for agree_after_normalization the label its normalised
    vectors received."""
    if _get(p, "agreement") == "agree_after_normalization":
        label = _get(_get(p, "metrics"), "normalized_agreement")
        return label if _truthy(label) else "agree_directly"
    return _get(p, "agreement")


def measured_assessment(p):
    """Shot-noise assessment of a pair: measured_assessment (top level, else under metrics),
    else not_comparable for a not-comparable pair, else read from the statistical-test verdict;
    None when none of these is recorded."""
    recorded = _coalesce(_get(p, "measured_assessment"), _get(_get(p, "metrics"), "measured_assessment"))
    if _truthy(recorded):
        return recorded
    if _get(p, "agreement") == "not_comparable":
        return "not_comparable"
    verdict = _get(_get(_get(p, "metrics"), "statistical_test"), "verdict")
    key = _property_key(verdict)
    return _VERDICT_TO_ASSESSMENT.get(key) if key is not None else None


def unaligned_basis(p):
    """The basis ('direct' or 'bit_reversal') in which a pair matches although its declared
    qubit orderings imply the other one; 'unrecorded' when the pair says so without naming
    the basis; else None."""
    v = _coalesce(_get(_get(p, "metrics"), "unaligned_basis_match"), _get(p, "unaligned_basis_match"))
    if isinstance(v, str) and v:
        return v
    return "unrecorded" if v is True or _get(p, "agreement") == "unaligned_basis_match" else None


def statevector_group(p) -> str:
    """'agree' (directly, up to a global phase, or after normalisation), 'bit_order' (after
    the bit reversal the declared orderings imply), 'disagree' (residual, only after an
    undeclared qubit permutation, or only in an unaligned basis), 'not_comparable' or 'other'."""
    if _get(p, "agreement") == "not_comparable":
        return "not_comparable"
    if unaligned_basis(p) is not None:
        return "disagree"
    label = effective_agreement(p)
    if label in ("residual_disagreement", "agree_after_qubit_permutation"):
        return "disagree"
    if label in ("agree_directly", "agree_up_to_global_phase"):
        return "agree"
    if label == "agree_after_bit_reversal":
        return "bit_order"
    return "other"


def is_disagreement(p) -> bool:
    """Whether the pair's outputs differ by the evidence it records: a measured pair whose
    single-bit marginals differ or whose shot-noise assessment is distinguishable (without an
    assessment, whose distance exceeds the threshold); a statevector pair in the 'disagree'
    group."""
    if _get(p, "mode") == "measured":
        if _get(p, "marginal_assessment") == "marginal_distinguishable":
            return True
        assessment = measured_assessment(p)
        if _truthy(assessment):
            return assessment == "distinguishable"
        return _get(p, "agreement") == "distance_exceeds_threshold"
    return statevector_group(p) == "disagree"


def is_by_only_disagreement(p) -> bool:
    """A measured pair whose only disagreement evidence is significance under
    Benjamini–Yekutieli but not under Holm."""
    if _get(p, "mode") != "measured" or not is_disagreement(p):
        return False
    if _get(p, "marginal_assessment") == "marginal_distinguishable":
        return False
    return _get(_get(_get(p, "metrics"), "statistical_test"), "significant_fwer") is False


def _agrees(p) -> bool:
    if _get(p, "mode") == "measured":
        return measured_assessment(p) == "consistent_within_shot_noise" and not is_disagreement(p)
    return statevector_group(p) in ("agree", "bit_order")


def pair_verdict(p) -> dict:
    """The verdict record of one pair.

    ``verdict`` is one of not_comparable, differs_by_only, differs, inconclusive, agrees,
    bit_order or unassessed, decided in that order. The flags and fields beside it are what
    the Summary, the badges, the Agreement tab and the per-backend counts read."""
    measured = _get(p, "mode") == "measured"
    differs = is_disagreement(p)
    by_only = is_by_only_disagreement(p)
    assessment = measured_assessment(p)
    group = statevector_group(p)
    agrees = _agrees(p)
    inconclusive = measured and assessment in _INCONCLUSIVE
    marginal = _get(p, "marginal_assessment") == "marginal_distinguishable"
    if _get(p, "agreement") == "not_comparable":
        verdict = "not_comparable"
    elif by_only:
        verdict = "differs_by_only"
    elif differs:
        verdict = "differs"
    elif inconclusive:
        verdict = "inconclusive"
    elif agrees:
        verdict = "bit_order" if not measured and group == "bit_order" else "agrees"
    else:
        verdict = "unassessed"
    return {
        "verdict": verdict,
        "differs": differs,
        "differs_by_only": by_only,
        "differs_full": measured and differs and not by_only and assessment == "distinguishable",
        "differs_marginal": measured and differs and not by_only and marginal,
        "agrees": agrees,
        "inconclusive": inconclusive,
        "assessment": assessment,
        "statevector_group": group,
        "effective_agreement": effective_agreement(p),
        "unaligned_basis": unaligned_basis(p),
    }


def verdict_of(p) -> dict:
    """The pair's recorded ``pair_verdict``, else ``pair_verdict(p)``: what the page shows
    for the pair."""
    recorded = _get(p, "pair_verdict")
    if isinstance(recorded, dict) and isinstance(recorded.get("differs"), bool):
        return recorded
    return pair_verdict(p)


def is_multi_run_key(key) -> bool:
    """Whether a result key is ``<id>~opt<L>~run<N>``."""
    text = _js_string(key) if _truthy(key) else ""
    return _MULTI_RUN_RE.fullmatch(text) is not None


def _magnitude(p):
    """(total variation, fidelity) of a pair: total variation for a measured pair, the
    label-aligned fidelity (else the direct one) for a statevector pair."""
    m = _get(p, "metrics")
    if _get(p, "mode") == "measured":
        return _number(_get(_get(_get(m, "statistical_test"), "effect_size"), "total_variation")), None
    return None, _coalesce(_number(_get(m, "label_aligned_fidelity")), _number(_get(m, "direct_fidelity")))


def _new_backend(key, ordering) -> dict:
    return {"key": key, "status": "ok", "compared": 0, "differs": 0, "differs_full": 0,
            "differs_marginal": 0, "differs_by_only": 0, "inconclusive": 0, "not_comparable": 0,
            "differs_with": [], "by_only_with": [], "agrees_with": [], "compared_with": [],
            "worst_fidelity": None, "largest_tv": None, "bit_order": _member(ordering, key),
            "size_with": {}}


def backend_verdicts(report: dict) -> dict:
    """Per-backend counts over a single-circuit report's pairs: how many backends each one
    was compared with, differs from (full distribution, marginal, Benjamini–Yekutieli only),
    is inconclusive with or could not be compared with, the backends it differs from and
    agrees with, and the size of every compared pair."""
    div = _get(report, "divergence_report")
    div = div if _truthy(div) else {}
    pairs = _get(div, "pairwise_agreement")
    pairs = pairs if isinstance(pairs, list) else []
    raws = _get(report, "raw_results")
    raws = raws if isinstance(raws, list) else []
    measured = _truthy(_get(report, "n_shots")) or any(_get(p, "mode") == "measured" for p in pairs)
    ordering = _get(div, "ordering_map")
    ordering = ordering if _truthy(ordering) else {}

    by_key = {}

    def entry(key):
        if key not in by_key:
            by_key[key] = _new_backend(key, ordering)
        return by_key[key]

    for r in raws:
        if _truthy(r) and isinstance(_get(r, "simulator"), str):
            entry(r["simulator"])["status"] = runner_status(r)
    sims = _get(div, "simulators")
    for key in sims if isinstance(sims, list) else []:
        entry(key)

    disagreeing = inconclusive = not_comparable = 0
    by_only_pairs = []
    for p in pairs:
        pair_sims = _get(p, "simulators")
        if not (isinstance(pair_sims, list) and len(pair_sims) == 2):
            continue
        a, b = entry(pair_sims[0]), entry(pair_sims[1])
        if _get(p, "agreement") == "not_comparable":
            a["not_comparable"] += 1
            b["not_comparable"] += 1
            not_comparable += 1
            continue
        v = pair_verdict(p)
        a["compared"] += 1
        b["compared"] += 1
        a["compared_with"].append(b["key"])
        b["compared_with"].append(a["key"])
        tv, fidelity = _magnitude(p)
        value = tv if _get(p, "mode") == "measured" else fidelity
        if value is not None:
            a["size_with"][b["key"]] = value
            b["size_with"][a["key"]] = value
        if v["inconclusive"]:
            inconclusive += 1
            a["inconclusive"] += 1
            b["inconclusive"] += 1
        if v["agrees"]:
            a["agrees_with"].append(b["key"])
            b["agrees_with"].append(a["key"])
        if v["differs"]:
            disagreeing += 1
            a["differs"] += 1
            b["differs"] += 1
            if v["differs_by_only"]:
                a["differs_by_only"] += 1
                b["differs_by_only"] += 1
                a["by_only_with"].append(b["key"])
                b["by_only_with"].append(a["key"])
                by_only_pairs.append([a["key"], b["key"]])
            else:
                a["differs_with"].append(b["key"])
                b["differs_with"].append(a["key"])
                for x in (a, b):
                    if fidelity is not None and (x["worst_fidelity"] is None or fidelity < x["worst_fidelity"]):
                        x["worst_fidelity"] = fidelity
                    if tv is not None and (x["largest_tv"] is None or tv > x["largest_tv"]):
                        x["largest_tv"] = tv
                for field in ("differs_full", "differs_marginal"):
                    if v[field]:
                        a[field] += 1
                        b[field] += 1

    marginal_tested = any(
        _get(p, "mode") == "measured" and _truthy(_get(_get(p, "metrics"), "marginal_test"))
        and _get(p, "marginal_assessment") not in ("not_applicable", "not_tested")
        for p in pairs)
    backends = list(by_key.values())
    out = {"mode": "measured" if measured else "statevector", "backends": backends,
           "pairs": len(pairs), "disagreeing": disagreeing, "by_only": len(by_only_pairs),
           "by_only_pairs": by_only_pairs, "inconclusive": inconclusive,
           "not_comparable": not_comparable, "marginal_tested": marginal_tested,
           "multi_run": any(is_multi_run_key(b["key"]) for b in backends)}
    out["headline_model"] = headline_model(out)
    return out


def annotate_divergence_report(divergence_report: dict, raw_results: list, n_shots=None) -> None:
    """Record ``pair_verdict`` on every pair and ``backend_verdicts`` on the report."""
    pairs = divergence_report.get("pairwise_agreement")
    for p in pairs if isinstance(pairs, list) else []:
        if isinstance(p, dict):
            p["pair_verdict"] = pair_verdict(p)
    divergence_report["backend_verdicts"] = backend_verdicts(
        {"n_shots": n_shots, "raw_results": raw_results, "divergence_report": divergence_report})
