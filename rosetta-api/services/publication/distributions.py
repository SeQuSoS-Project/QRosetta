"""Measured-distribution views (count comparison, single-bit marginals, Hamming weight,
outcome spread): data, tables and captions. Mirrored by static/js/artifact_distributions.js."""

import json
import threading
from collections import OrderedDict
from typing import Callable, Dict

from .formats import _fixed, _fmt_int, _format_columns, _full, _num
from .selectors import _msb_counts, _run_label
from .views import report_backends


_MEMO: "OrderedDict[tuple, tuple]" = OrderedDict()
_MEMO_LOCK = threading.Lock()
_MEMO_SIZE = 6


def _memo(name: str, results: dict, params, compute: Callable):
    """``compute()`` cached per report object and parameters, for the few reports in use.
    A figure, its caption and its table read the same data within one request."""
    key = (name, id(results), json.dumps(params, sort_keys=True))
    with _MEMO_LOCK:
        hit = _MEMO.get(key)
        if hit is not None and hit[0] is results:
            _MEMO.move_to_end(key)
            return hit[1]
    value = compute()
    with _MEMO_LOCK:
        _MEMO[key] = (results, value)
        while len(_MEMO) > _MEMO_SIZE:
            _MEMO.popitem(last=False)
    return value


def count_probabilities(results: dict) -> dict:
    """{sims, counts, totals, prob, missing}: backends with counts in report order, their
    msb-order counts and totals, prob(sim, key) and the backends without counts."""
    return _memo("counts", results, None, lambda: _count_probabilities(results))


def _count_probabilities(results: dict) -> dict:
    counts = _msb_counts(results)
    sims = [s for s in report_backends(results) if s in counts]
    totals = {s: sum(counts[s].values()) for s in sims}
    missing = [s for s in report_backends(results) if s not in counts]

    def prob(s, o):
        return counts[s].get(o, 0) / totals[s] if totals[s] else 0.0

    return {"sims": sims, "counts": counts, "totals": totals, "prob": prob, "missing": missing}


def missing_note(cp: dict) -> str:
    return (f" Backends without counts are not drawn: {', '.join(cp['missing'])}."
            if cp["missing"] else "")


def highlight_note(p: dict) -> str:
    return (f" Coloured: backends whose pair with {p['ref']} is a disagreement (shot-noise "
            "verdict or a single-bit marginal); grey: the rest."
            if p.get("colour") == "highlight" else "")


def _weight(key: str) -> int:
    return key.count("1")


def count_selection(results: dict, p: dict) -> dict:
    """The outcomes the count comparison shows: {cp, rows: [{key, label, vals}], other,
    observed, rest, note, key_note}. ``vals`` follow cp["sims"]."""
    return _memo("selection", results, p, lambda: _count_selection(results, p))


def _count_selection(results: dict, p: dict) -> dict:
    cp = count_probabilities(results)
    sims, prob = cp["sims"], cp["prob"]
    lsb = p["keyorder"] == "lsb"
    if p["outcomes"] == "bits":
        bits = p["bits"]
        k = len(bits)
        marg = {s: {} for s in sims}
        for s in sims:
            for o in sorted(cp["counts"][s]):
                lab = "".join(o[b] if b < len(o) else "0" for b in bits)
                marg[s][lab] = marg[s].get(lab, 0.0) + prob(s, o)
        keys = [format(i, f"0{k}b") for i in range(2 ** k)]
        rows = [{"key": key, "vals": [marg[s].get(key, 0.0) for s in sims]} for key in keys]
        order = list(reversed(bits)) if lsb else list(bits)
        note = (f"the marginal distribution over classical bits {', '.join(str(b) for b in bits)}: "
                f"all {2 ** k} outcomes, the other bits summed out")
        key_note = "keys read " + " ".join(f"c[{b}]" for b in order) + " from left to right"
        other, observed, rest = None, None, []
    else:
        score = {}
        for s in sims:
            for o in cp["counts"][s]:
                v = prob(s, o)
                if v > score.get(o, -1.0):
                    score[o] = v
        observed = sorted(score)
        ranked = sorted(observed, key=lambda o: -score[o])
        if p["outcomes"] == "top":
            kept = ranked[:p["top"]]
        else:
            kept = [o for o in ranked if score[o] >= p["threshold"]]
        kept_set = set(kept)
        rest = [o for o in observed if o not in kept_set]
        rows = [{"key": o, "vals": [prob(s, o) for s in sims]} for o in kept]
        other = None
        if rest:
            ov = []
            for s in sims:
                total = 0.0
                for o in sorted(cp["counts"][s]):
                    if o not in kept_set:
                        total += prob(s, o)
                ov.append(total)
            mean = 0.0
            for v in ov:
                mean += v
            mean = mean / len(ov) if ov else 0.0
            other = {"vals": ov, "share": _fixed(mean * 100, 1)}
        if not rest:
            note = f"all {len(observed)} observed outcomes"
        elif p["outcomes"] == "top":
            note = (f"the {len(kept)} outcomes with the largest probability on any backend, of "
                    f"{len(observed)} observed")
        else:
            note = (f"the {len(kept)} of {len(observed)} observed outcomes with probability ≥ "
                    f"{_full(p['threshold'])} on any backend")
        if rest:
            note += (f"; the other {len(rest)} ({other['share']}% of shots on average) are "
                     + ("summed into 'other'" if p["other"] else "not shown"))
        key_note = ("keys in lsb order (classical bit 0 rightmost)" if lsb
                    else "keys in msb order (classical bit 0 leftmost)")
    for r in rows:
        r["label"] = r["key"][::-1] if lsb else r["key"]
    if p["sort"] == "bitstring":
        rows.sort(key=lambda r: r["label"])
    elif p["sort"] == "hamming":
        rows.sort(key=lambda r: (_weight(r["key"]), r["label"]))
    elif p["outcomes"] == "bits":
        rows.sort(key=lambda r: -max(r["vals"], default=0.0))
    if other and p["other"]:
        rows.append({"key": None, "label": f"other (+{len(rest)})", "vals": other["vals"]})
    return {"cp": cp, "rows": rows, "other": other, "observed": observed, "rest": rest,
            "note": note, "key_note": key_note}


_COUNT_LEADS = {
    "overlay": "Clustered bars of measured probabilities, one colour per backend",
    "heatmap": "Outcome × backend heatmap of measured probabilities; a uniform row is "
               "agreement, a varying row is disagreement",
}


def counts_legend(results: dict, p: dict) -> str:
    """Caption of the count comparison figure."""
    sel = count_selection(results, p)
    if p["layout"] == "panels":
        lead = f"One panel per backend; black ticks mark {p['ref']}"
    elif p["layout"] == "diff":
        lead = f"Measured probability of each backend minus {p['ref']}"
        if p["band"]:
            lead += ("; the shaded band is ±2σ shot noise of the difference of two independent "
                     "samples at the reference probability and shot count")
    else:
        lead = _COUNT_LEADS[p["layout"]]
    text = (f"{lead}, for {len(sel['cp']['sims'])} backend(s), {_run_label(results)}. Shows "
            f"{sel['note']}; {sel['key_note']}; lsb-declared backends are bit-reversed to one "
            "order first.")
    if p["yscale"] == "log" and p["layout"] in ("overlay", "panels"):
        text += " Logarithmic probability axis."
    return text + highlight_note(p) + missing_note(sel["cp"])


def tbl_counts(results: dict, p: dict):
    sel = count_selection(results, p)
    sims = sel["cp"]["sims"]
    rows = _format_columns([[r["label"]] + [_num(v) for v in r["vals"]] for r in sel["rows"]])
    caption = (f"Measured probability of each outcome (rows) for each backend (columns), "
               f"{_run_label(results)}. Shows {sel['note']}; {sel['key_note']}; lsb-declared "
               "backends are bit-reversed to one order first." + missing_note(sel["cp"]))
    return ["Outcome"] + sims, rows, "Measured outcome probabilities", caption


def marginals(results: dict) -> dict:
    """{cp, n, m: {sim: [P(c[j] = 1) for j]}}."""
    return _memo("marginals", results, None, lambda: _marginals(results))


def _marginals(results: dict) -> dict:
    cp = count_probabilities(results)
    n = max([len(o) for s in cp["sims"] for o in cp["counts"][s]] or [0])
    m = {}
    for s in cp["sims"]:
        vals = [0.0] * n
        for o in sorted(cp["counts"][s]):
            pr = cp["prob"](s, o)
            for j, ch in enumerate(o):
                if ch == "1":
                    vals[j] += pr
        m[s] = vals
    return {"cp": cp, "n": n, "m": m}


def marginals_legend(results: dict, p: dict) -> str:
    d = marginals(results)
    k = len(d["cp"]["sims"])
    if p["layout"] == "diff":
        text = f"P(c[j] = 1) of each backend minus {p['ref']}, for {k} backend(s), {_run_label(results)}"
        if p["errorbars"]:
            text += "; the shaded band is ±2σ shot noise of the difference at the reference value"
    else:
        text = (f"Probability that each classical bit reads 1, P(c[j] = 1), for {k} backend(s), "
                f"{_run_label(results)}")
        if p["errorbars"]:
            text += "; error bars are ±2σ binomial shot noise"
    return (text + ". The single-bit marginal tests compare these probabilities pair by pair "
            "(Holm across all tested bits)." + highlight_note(p) + missing_note(d["cp"]))


def tbl_marginals(results: dict, p: dict):
    d = marginals(results)
    sims = d["cp"]["sims"]
    rows = _format_columns([[f"c[{j}]"] + [_num(d["m"][s][j]) for s in sims]
                            for j in range(d["n"])])
    caption = (f"Probability that classical bit j reads 1 for each backend, {_run_label(results)}; "
               "lsb-declared backends are bit-reversed to one order first, so c[j] is the same "
               "bit for every backend." + missing_note(d["cp"]))
    return ["Classical bit"] + sims, rows, "Single-bit marginals P(c[j] = 1)", caption


def hamming(results: dict) -> dict:
    """{cp, n, h: {sim: [P(weight = w) for w in 0..n]}}."""
    return _memo("hamming", results, None, lambda: _hamming(results))


def _hamming(results: dict) -> dict:
    cp = count_probabilities(results)
    n = max([len(o) for s in cp["sims"] for o in cp["counts"][s]] or [0])
    h = {}
    for s in cp["sims"]:
        vals = [0.0] * (n + 1)
        for o in sorted(cp["counts"][s]):
            vals[_weight(o)] += cp["prob"](s, o)
        h[s] = vals
    return {"cp": cp, "n": n, "h": h}


def hamming_legend(results: dict, p: dict) -> str:
    d = hamming(results)
    k = len(d["cp"]["sims"])
    if p["layout"] == "diff":
        text = (f"Probability of Hamming weight w for each backend minus {p['ref']}, for {k} "
                f"backend(s), {_run_label(results)}; the shaded band is ±2σ shot noise of the "
                "difference at the reference probability")
    else:
        each = "one line per backend" if p["layout"] == "lines" else "one colour per backend"
        text = (f"Probability of measuring w ones (Hamming weight w = 0 to {d['n']}), {each}, "
                f"for {k} backend(s), {_run_label(results)}")
    return text + ". Independent of bit order." + highlight_note(p) + missing_note(d["cp"])


def tbl_hamming(results: dict, p: dict):
    d = hamming(results)
    sims = d["cp"]["sims"]
    rows = _format_columns([[str(w)] + [_num(d["h"][s][w]) for s in sims]
                            for w in range(d["n"] + 1)])
    caption = (f"Probability of measuring w ones in the {d['n']}-bit outcome for each backend, "
               f"{_run_label(results)}." + missing_note(d["cp"]))
    return ["Hamming weight"] + sims, rows, "Hamming-weight distribution", caption


def spread(results: dict) -> Dict[str, dict]:
    """Per backend: shots, observed outcomes, sorted probabilities, largest probability and
    the fewest outcomes covering 50% and 90% of the shots."""
    return _memo("spread", results, None, lambda: _spread(results))


def _spread(results: dict) -> dict:
    cp = count_probabilities(results)
    out = {}
    for s in cp["sims"]:
        c = sorted(cp["counts"][s].values(), reverse=True)
        total = cp["totals"][s]
        cover = {}
        for name, num, den in (("half", 1, 2), ("ninety", 9, 10)):
            cum, k = 0, 0
            while k < len(c) and cum * den < num * total:
                cum += c[k]
                k += 1
            cover[name] = k
        out[s] = {"shots": total, "observed": len(c),
                  "sorted": [v / total for v in c] if total else [],
                  "largest": c[0] / total if total and c else None, **cover}
    return {"cp": cp, "rows": out}


def rank_legend(results: dict, p: dict) -> str:
    d = spread(results)
    axes = "logarithmic probability axis" + (", logarithmic rank axis" if p["xscale"] == "log" else "")
    return (f"Observed outcome probabilities of each backend sorted from largest to smallest "
            f"({axes}), for {len(d['cp']['sims'])} backend(s), {_run_label(results)}. The smallest "
            "observable probability is 1/shots; outcomes never observed are absent."
            + highlight_note(p) + missing_note(d["cp"]))


def tbl_rank(results: dict, p: dict):
    d = spread(results)
    rows = _format_columns([[s, _fmt_int(r["shots"]), _fmt_int(r["observed"]), _num(r["largest"]),
                             _fmt_int(r["half"]), _fmt_int(r["ninety"])]
                            for s, r in d["rows"].items()])
    caption = ("Per backend: shots, distinct outcomes observed, the largest outcome probability "
               "and the fewest outcomes whose counts add up to 50% and 90% of the shots, "
               f"{_run_label(results)}." + missing_note(d["cp"]))
    return (["Backend", "Shots", "Observed outcomes", "Largest probability",
             "Outcomes for 50% of shots", "Outcomes for 90% of shots"], rows, "Outcome spread",
            caption)


def disagrees(results: dict, a: str, b: str) -> bool:
    """Whether the measured pair a × b is a disagreement (run_status.js isDisagreement)."""
    for r in (results.get("divergence_report") or {}).get("pairwise_agreement") or []:
        if set(r.get("simulators") or []) == {a, b} and a != b:
            if r.get("marginal_assessment") == "marginal_distinguishable":
                return True
            if r.get("measured_assessment"):
                return r["measured_assessment"] == "distinguishable"
            return r.get("agreement") == "distance_exceeds_threshold"
    return False

