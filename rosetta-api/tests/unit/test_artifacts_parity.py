"""The browser builders in static/js/artifact_formats.js render text artifacts, number
formats and the artifact catalog identically to services/publication. Runs the JS in
Node; skipped when Node is unavailable."""
import json
import math
import os
import shutil
import subprocess

import pytest

from services.publication import (
    _fmt_int, _fmt_num, _fmt_p, item_paths, list_artifacts, normalize_params, render_artifact,
    view_slug,
)
from services.publication.subset import subset_results
from tests.unit.test_publication import MEASURED, STATEVECTOR

_NODE = shutil.which("node")
_HARNESS = os.path.join(os.path.dirname(__file__), "artifacts_parity_harness.mjs")

pytestmark = pytest.mark.skipif(_NODE is None, reason="node not available")

_SERVER_ONLY_FORMATS = {"xlsx"}

_LABELS = ["agree_directly", "agree_up_to_global_phase", "agree_after_bit_reversal",
           "agree_after_qubit_permutation", "agree_after_normalization", "residual_disagreement"]
_SV_REASONS = ["missing_statevector", "statevector_parse_error", "empty_statevector",
               "nonfinite_statevector", "zero_norm_statevector", "shape_mismatch",
               "comparison_error"]
_COUNT_REASONS = ["missing_counts", "empty_counts", "invalid_bitstring_key",
                  "non_numeric_counts", "nonfinite_counts", "negative_counts",
                  "zero_total_counts", "nonfinite_metric", "comparison_error"]
_FIDELITIES = [1.0, 1, 0.99996, 0.996, 0.0, 0, 0.5, 1 - 1e-12]


def _sv_edge():
    """Statevector report with every label and reason, near-1 fidelities and unranked runs."""
    sims = [f"s{i}" for i in range(4)]
    pairs = []
    for i, label in enumerate(_LABELS):
        pairs.append({"simulators": [sims[i % 4], sims[(i + 1) % 4]], "mode": "statevector",
                      "agreement": label, "registered_transform": "identity" if i == 0 else None,
                      "metrics": {"direct_fidelity": _FIDELITIES[i],
                                  "label_aligned_fidelity": _FIDELITIES[-1 - i],
                                  "unaligned_basis_match": [None, "direct", "bit_reversal"][i % 3]}})
    for reason in _SV_REASONS:
        pairs.append({"simulators": ["s0", "s3"], "mode": "statevector",
                      "agreement": "not_comparable", "registered_transform": None,
                      "metrics": {"reason": reason, "details": {}}})
    return {
        "timing_samples": 1,
        "divergence_report": {
            "simulators": sims,
            "fidelity_matrix": [[-1.0, 0.99996, 1, 0], [0.99996, -1.0, 5e-5, 0.996],
                                [1, 5e-5, 1.0, None], [0, 0.996, None, -1.0]],
            "pairwise_agreement": pairs,
        },
        "performance_report": {
            "ranking_metric": "execution_time_sec",
            "ranking": [
                {"simulator": "s0", "status": "success", "rank": 1, "compilation_time_sec": 0,
                 "simulation_time_sec": 2.0, "execution_time_sec": 2.0, "cpu_time_sec": 3,
                 "gate_count": 2.0, "circuit_depth": 1},
                {"simulator": "s1", "status": "success", "compilation_time_sec": 1e-7,
                 "simulation_time_sec": 0.5, "execution_time_sec": 0.5000001,
                 "cpu_time_sec": None, "gate_count": None, "circuit_depth": 0},
            ],
            "unranked": [
                {"simulator": "s2", "status": "error", "reason": "runner_error", "error": "boom",
                 "execution_time_sec": None, "rank": None},
                {"simulator": "s3", "status": "error", "reason": "missing_timing",
                 "execution_time_sec": None, "rank": None},
            ],
        },
        "resource_report": {
            "ranking_metric": "process_peak_rss_mb",
            "ranking": [
                {"simulator": "s1", "status": "success", "rank": 1, "process_peak_rss_mb": 80,
                 "memory_usage_mb": 0.0, "process_peak_mb": 70.0,
                 "theoretical_statevector_mb": 6.103515625e-05},
            ],
            "unranked": [
                {"simulator": "s0", "status": "success", "reason": "missing_process_peak_rss",
                 "process_peak_rss_mb": None, "memory_usage_mb": 0.03125, "process_peak_mb": 1.0,
                 "theoretical_statevector_mb": 1.52587890625e-05, "rank": None},
                {"simulator": "s2", "status": "error", "reason": "runner_error", "error": "boom",
                 "process_peak_rss_mb": None, "memory_usage_mb": None, "process_peak_mb": None,
                 "rank": None},
            ],
        },
        "raw_results": [
            {"simulator": "s0", "optimization_level": None, "sdk_versions": {"a": "1.0"},
             "qubit_ordering": "little_endian", "sampling_method": None, "status": "ok",
             "memory_method": "vmhwm", "process_peak_rss_method": "vmhwm",
             "precision": "complex128", "simulation_cpu_time_sec": 1.9,
             "transpiled_qasm": "OPENQASM 2.0;"},
            {"simulator": "s1", "optimization_level": 2.0, "sdk_versions": {},
             "memory_method": "sampled_10ms", "precision": None, "device": "GPU",
             "gpu_name": "NVIDIA RTX"},
            {"simulator": "s2", "error": "boom", "status": "timeout", "optimization_level": 0},
            {"simulator": "s3", "error": "", "qubit_ordering": ""},
        ],
    }


def _measured_edge():
    """Measured report with not-comparable pairs, every count reason and >12 histogram pairs."""
    sims = [f"m{i}" for i in range(7)]
    pairs = []
    for i in range(len(sims)):
        for j in range(i + 1, len(sims)):
            pairs.append({"simulators": [sims[i], sims[j]], "mode": "measured",
                          "agreement": "distance_within_threshold" if (i + j) % 2 else
                          "distance_exceeds_threshold",
                          "registered_transform": "identity_threshold_check",
                          "measured_assessment": [
                              "consistent_within_shot_noise", "distinguishable",
                              "inconclusive_low_shots", "ambiguous"][(i * j) % 4],
                          "metrics": {"js_divergence": [0, 5e-5, 0.69, 1e-9][(i + j) % 4],
                                      "label_aligned_js_divergence": [None, 2e-6, 0.0, 0.5][(i + j) % 4],
                                      "statistical_test": {
                                          "basis": ["direct", "bit_reversal"][(i + j) % 2],
                                          "pooled_outcomes": [0, 3][(i * j) % 2],
                                          "inconclusive_reason": [None, None, "low_power",
                                                                  None][(i * j) % 4],
                                          "resolvable_by_more_shots": [None, None, False,
                                                                       None][(i * j) % 4],
                                          "verdict": [
                                              "consistent", "distinguishable",
                                              "inconclusive_low_shots", "ambiguous"][(i * j) % 4],
                                          "effect_size": {"total_variation": 0, "cramers_v": 2e-6},
                                          "power": {"power_to_detect_delta_at_observed_shots": 0.99996,
                                                    "shots_per_backend_for_target_power": 1570.0,
                                                    "alpha_used": 0.05 / (21 * 3.645359), "m_pairs": 21,
                                                    "c_m": 3.6453587047627294},
                                          "chi2": {"p_value": [1, 0.0, 1.65e-188][(i + j) % 3],
                                                   "p_value_by": [0.99996, 0, 2e-300][(i + j) % 3]},
                                          "g_test": {"p_value": 3e-12, "p_value_by": None}}}})
    for reason in _COUNT_REASONS:
        pairs.append({"simulators": ["m0", "x"], "mode": "measured", "agreement": "not_comparable",
                      "registered_transform": None, "measured_assessment": "not_comparable",
                      "metrics": {"reason": reason, "details": {}}})
    n = len(sims)
    mat = [[0.0 if a == b else [0, 5e-5, 0.69, None][(a + b) % 4] for b in range(n)] for a in range(n)]
    raw = [{"simulator": s, "counts": {"00": 64, "11": 64}, "memory_method": "vmhwm"} for s in sims]
    raw.append({"simulator": "x", "error": "boom", "status": "offline"})
    return {"n_shots": 128.0, "seed": 7, "divergence_report": {
        "simulators": sims, "statistical_distance_matrix (js_divergence)": mat,
        "hellinger_distance_matrix": mat, "js_divergence_unit": "nats",
        "pairwise_agreement": pairs,
        "statistical_test_summary": {"verdict_counts": {"consistent": 1}}},
        "performance_report": {"ranking": [], "unranked": [
            {"simulator": "x", "status": "error", "reason": "runner_error", "rank": None}]},
        "resource_report": {"ranking": [], "unranked": [
            {"simulator": "x", "status": "error", "reason": "runner_error", "rank": None}]},
        "raw_results": raw}


def _repeated_timing():
    """_sv_edge with per-run timing samples: odd and even counts, ties, one single-run backend."""
    rep = _sv_edge()
    rep["timing_samples"] = 4
    s0, s1 = rep["raw_results"][0], rep["raw_results"][1]
    s0.update({"timing_samples": 4, "compilation_time_samples": [0.0, 1e-7, 0.0, 3e-7],
               "simulation_time_samples": [2.0, 0.1, 0.30000000000000004, 7.5]})
    s1.update({"timing_samples": 3, "compilation_time_samples": [1e-7, 1e-7, 2e-7],
               "simulation_time_samples": [0.5, 0.49, 0.5100001]})
    rep["performance_report"]["ranking"][0]["overlaps_next"] = True
    rep["performance_report"]["ranking"][1]["overlaps_next"] = True
    return rep


def _overlapping():
    """_repeated_timing with recorded overlap counts on the successful runs."""
    rep = _repeated_timing()
    rep["raw_results"][0].update({"overlapping_runs": 3, "server_overlapping_runs": 0})
    rep["raw_results"][1].update({"overlapping_runs": 1.0, "server_overlapping_runs": 2})
    return rep


def _exclusive():
    """_sv_edge where every successful run was exclusive."""
    rep = _sv_edge()
    for r in rep["raw_results"]:
        r["exclusive"] = True
    return rep


def _many_pairs():
    """Ten backends, 45 pairs: the pairwise tables take the longtable form."""
    rep = _sv_edge()
    sims = [f"s{i}" for i in range(10)]
    pairs = [{"simulators": [a, b], "mode": "statevector", "agreement": "agree_directly",
              "registered_transform": "identity",
              "metrics": {"direct_fidelity": 1 - 1e-13 * (i + j), "label_aligned_fidelity": 1.0}}
             for i, a in enumerate(sims) for j, b in enumerate(sims) if i < j]
    rep["divergence_report"] = {"simulators": sims, "pairwise_agreement": pairs,
                                "fidelity_matrix": [[1.0] * 10 for _ in sims]}
    return rep


def _counts_rich():
    """Five backends on 5 classical bits: spread-out counts, one lsb backend, one without
    counts, a missing pair verdict and ties in probability."""
    sims = ["p", "q", "r", "s", "t"]
    raw = []
    for n, sim in enumerate(sims[:4]):
        counts = {}
        for i in range(32):
            c = (i * (7 + n) + 3 * n) % 23
            if c:
                counts[format(i, "05b")] = c
        counts["00000"] = 40 + n
        raw.append({"simulator": sim, "qubit_ordering": "lsb" if sim == "q" else "msb",
                    "counts": counts})
    raw.append({"simulator": "t", "error": "boom", "status": "error"})
    pairs = [{"simulators": [a, b], "mode": "measured",
              "measured_assessment": ["distinguishable", "consistent_within_shot_noise"][(i + j) % 2],
              "marginal_assessment": "marginal_distinguishable" if a == "r" else None}
             for i, a in enumerate(sims[:4]) for j, b in enumerate(sims[:4]) if i < j]
    return {"n_shots": 300, "task_name": "rich (5q)",
            "divergence_report": {"simulators": sims, "pairwise_agreement": pairs},
            "performance_report": {"ranking": [
                {"simulator": s, "status": "success", "compilation_time_sec": 0.001 * (k + 1),
                 "simulation_time_sec": 0.01 / (k + 1), "execution_time_sec": 0.001 * (k + 1) + 0.01 / (k + 1)}
                for k, s in enumerate(sims[:4])], "unranked": []},
            "resource_report": {"ranking": [{"simulator": s, "process_peak_rss_mb": 100 + k,
                                             "memory_usage_mb": 0.5 * k} for k, s in enumerate(sims[:4])],
                                "unranked": []},
            "raw_results": raw}


_CASES = [("measured", MEASURED), ("measured", _counts_rich()), ("statevector", STATEVECTOR), ("statevector", _many_pairs()),
          ("statevector", _sv_edge()), ("measured", _measured_edge()),
          ("statevector", _repeated_timing()), ("statevector", _overlapping()),
          ("statevector", _exclusive())]


def _js(payload):
    proc = subprocess.run([_NODE, _HARNESS], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=60)
    assert proc.returncode == 0, f"harness failed: {proc.stderr}"
    return json.loads(proc.stdout)


def _text_requests(results, mode):
    """Every text artifact × every browser-renderable format it supports."""
    return [{"id": a["id"], "fmt": fmt} for a in list_artifacts(results, mode)
            if a["view"] == "text" for fmt in a["formats"] if fmt not in _SERVER_ONLY_FORMATS]


def _key(r):
    return f"{r['id']}|{r['fmt']}|{json.dumps(r.get('params') or {}, separators=(',', ':'))}"


def _json_roundtrip(results):
    """The report as the browser sees it (Python floats like 2.0 arrive as JS numbers)."""
    return json.loads(json.dumps(results))


@pytest.mark.parametrize("mode,results", _CASES)
def test_text_artifacts_match(mode, results):
    results = _json_roundtrip(results)
    reqs = _text_requests(results, mode)
    assert reqs
    js = _js({"results": results, "requests": reqs})["texts"]
    mismatches = [_key(r) for r, text in zip(reqs, js)
                  if text != render_artifact(results, mode, r["id"], r["fmt"])[0].decode("utf-8")]
    assert not mismatches, "JS/Python drift on: " + ", ".join(mismatches)


@pytest.mark.parametrize("mode,results", _CASES)
def test_catalog_matches(mode, results):
    results = _json_roundtrip(results)
    py = [{**a, "formats": [f for f in a["formats"] if f not in _SERVER_ONLY_FORMATS]}
          for a in list_artifacts(results, mode)]
    assert _js({"results": results})["catalog"] == py


_NUMS = [0, 0.0, 1, 1.0, 2.0, -0.0, 0.5, 0.03125, -0.03125, 0.125, 0.99996, 0.996, 1 - 1e-12,
         1 - 1e-16, 5e-5, 4.9999e-5, 6.103515625e-05, 9.9951e-4, 1e-3, 0.0994999, 123456.5,
         1e15, 1e-300, -2.5e-7, 0.69314718, 1234.56789, "abc", None, True]
_SPECIAL = {"__nan__": math.nan, "__inf__": math.inf, "__-inf__": -math.inf}


def _py(v):
    return _SPECIAL.get(v, v) if isinstance(v, str) else v


def test_number_formatting_matches():
    values = _NUMS + list(_SPECIAL)
    nums = [{"v": v, "d": d} for v in values for d in (1, 2, 3, 4, 6)]
    ints = values + [3, 3.0, 1570.0, 2.5]
    out = _js({"nums": nums, "ints": ints})
    assert out["nums"] == [_fmt_num(_py(n["v"]), n["d"]) for n in nums]
    assert out["ints"] == [_fmt_int(_py(v)) for v in ints]


def test_full_precision_csv_text_matches():
    from services.publication.formats import _full
    values = [0.1, 1e-5, 1.5e-7, 123.456, 1e15, 1e16, 1.2345e20, -0.00125, 0.001, 2.0, -3.0,
              1 / 3, 1e-300, 5e-324, 0.99996, 6.103515625e-05, 0.0009995, 999.0000001,
              123456789.123, -7.5e-4, 1.7976931348623157e308]
    assert _js({"fulls": values})["fulls"] == [_full(v) for v in values]


def test_p_value_formatting_matches_and_never_prints_zero_for_tiny_values():
    ps = [0, 0.0, 1.65e-188, 1e-300, 5e-324, 0.5, 1, None, "__nan__"]
    out = _js({"ps": ps})["ps"]
    assert out == [_fmt_p(_py(v)) for v in ps]
    assert out[:5] == ["<1e-300", "<1e-300", "1.65e-188", "1.00e-300", "4.94e-324"]


def test_harness_covers_expected_artifacts():
    ids = {a["id"] for a in list_artifacts(MEASURED, "measured") if a["view"] == "text"}
    assert {"agreement", "performance", "resources", "metadata", "glossary"} <= ids


def test_edge_fixture_exercises_every_label_and_reason():
    sv = render_artifact(_sv_edge(), "statevector", "agreement", "csv")[0].decode()
    ms = render_artifact(_measured_edge(), "measured", "agreement", "csv")[0].decode()
    for token in _LABELS + _SV_REASONS:
        assert token in sv
    for token in _COUNT_REASONS:
        assert token in ms
    gloss = render_artifact(_sv_edge(), "statevector", "glossary", "markdown")[0].decode()
    for token in _LABELS + _SV_REASONS + _COUNT_REASONS + ["runner_error", "missing_timing",
                                                          "missing_process_peak_rss"]:
        assert f"**{token}**" in gloss


_COUNT_PARAMS = [
    {}, {"top": 3}, {"top": 3, "other": False}, {"outcomes": "threshold", "threshold": 0.05},
    {"outcomes": "threshold", "threshold": 1e-05}, {"outcomes": "threshold", "threshold": 1},
    {"outcomes": "bits", "bits": [4, 0]}, {"outcomes": "bits", "bits": [1], "keyorder": "lsb"},
    {"outcomes": "bits", "bits": [0, 1, 2], "sort": "probability"},
    {"sort": "bitstring", "keyorder": "lsb"}, {"sort": "hamming"},
    {"layout": "diff", "ref": "r", "band": False}, {"layout": "diff"}, {"layout": "panels", "yscale": "log"},
    {"layout": "heatmap", "colour": "highlight", "ref": "q"}, {"yscale": "log", "colour": "highlight"},
    {"backends": ["q", "s"]}, {"backends": ["t", "p"]}, {"size": "single", "title": False},
]
_VIEW_PARAMS = {
    "counts": _COUNT_PARAMS,
    "marginals": [{}, {"layout": "diff", "ref": "s"}, {"errorbars": False}, {"layout": "diff", "errorbars": False},
                  {"colour": "highlight"}, {"backends": ["r"]}],
    "hamming": [{}, {"layout": "lines"}, {"layout": "diff", "ref": "q"}, {"colour": "highlight", "ref": "r"}],
    "rank": [{}, {"xscale": "linear"}, {"colour": "highlight"}, {"backends": ["p", "q"]}],
    "execution_time": [{}, {"stage": "simulation"}, {"stage": "compilation", "xscale": "log"},
                       {"stage": "stacked", "xscale": "log"}, {"backends": ["s", "p"]}],
    "resource_usage": [{}, {"metric": "memory_delta"}],
    "agreement": [{}, {"backends": ["p", "r"]}],
    "metadata": [{"backends": ["t"]}],
}


def _view_cases():
    from services.publication.views import VIEW_BY_ID
    for vid, plist in _VIEW_PARAMS.items():
        for params in plist:
            yield vid, VIEW_BY_ID[vid], params


def test_parameterised_views_match():
    """Every table of a parameterised view, and the catalog legends, agree for each case."""
    results = _json_roundtrip(_counts_rich())
    reqs, catalogs = [], []
    for vid, view, params in _view_cases():
        if "table" in view:
            reqs += [{"id": view["table"], "fmt": fmt, "params": params}
                     for fmt in ("latex", "csv", "html", "markdown")]
        catalogs.append((vid, params))
    js = _js({"results": results, "requests": reqs})["texts"]
    mismatches = [_key(r) for r, text in zip(reqs, js) if text != render_artifact(
        results, "measured", r["id"], r["fmt"], params=r["params"])[0].decode("utf-8")]
    assert not mismatches, "JS/Python drift on: " + ", ".join(mismatches)
    for vid, params in catalogs:
        scoped = subset_results(results, params["backends"]) if params.get("backends") else results
        p = {k: v for k, v in params.items() if k != "backends"}
        py = [{**a, "formats": [f for f in a["formats"] if f not in _SERVER_ONLY_FORMATS]}
              for a in list_artifacts(scoped, "measured", {vid: p})]
        assert _js({"results": scoped, "catalogParams": {vid: p}})["catalog"] == py, (vid, params)


_NORMALIZE = [
    ("counts", {}), ("counts", {"backends": ["s", "p", "t", "q", "r"]}), ("counts", {"backends": ["s", "p"]}),
    ("counts", {"nope": 1, "zz": 2}), ("counts", {"layout": "pie"}), ("counts", {"top": 0}),
    ("counts", {"top": True}), ("counts", {"top": 65}), ("counts", {"threshold": -0.5}),
    ("counts", {"threshold": 0.25}), ("counts", {"backends": ["zz", "yy"]}), ("counts", {"backends": []}),
    ("counts", {"backends": "p"}), ("counts", {"backends": ["p"], "ref": "q"}), ("counts", {"ref": 3}),
    ("counts", {"bits": [0, 0]}), ("counts", {"bits": [5]}), ("counts", {"bits": [-1]}),
    ("counts", {"bits": list(range(7))}), ("counts", {"bits": [True]}), ("counts", {"bits": [3, 1]}),
    ("counts", {"other": "yes"}), ("counts", {"size": "poster"}), ("counts", {"layout": None}),
    ("agreement", {"size": "single"}), ("glossary", {}), ("nope", {}),
    ("execution_time", {"stage": "simulation", "title": False}),
    ("counts", {"ref": "t"}), ("counts", {"backends": ["t"]}), ("marginals", {"backends": ["t", "q"]}),
    ("hamming", {"backends": ["t", "r"], "ref": "t"}), ("rank", {"ref": "zz"}),
]
_SLUGS = [
    ("counts", {}), ("counts", {"layout": "diff", "ref": "q"}), ("counts", {"threshold": 1e-05}),
    ("counts", {"threshold": 0.125, "outcomes": "threshold"}), ("counts", {"top": 20, "other": False}),
    ("counts", {"bits": [3, 1]}), ("counts", {"backends": ["q", "r"]}), ("counts", {"backends": ["q", "r"], "ref": "r"}),
    ("counts", {"size": "double", "title": False}), ("marginals", {"errorbars": False}),
    ("execution_time", {"stage": "simulation"}), ("glossary", {}), ("metadata", {"backends": ["t"]}),
    ("counts", {"backends": ["t", "q"]}), ("hamming", {"backends": ["t"]}),
]


def _py_try(fn):
    try:
        return fn()
    except (ValueError, KeyError) as exc:
        return {"__error__": str(exc).strip("'") if isinstance(exc, KeyError) else str(exc)}


def test_view_parameters_slugs_and_paths_match():
    results = _json_roundtrip(_counts_rich())
    paths = [("counts", "counts_x", ["svg", "png", "latex", "csv", "markdown", "xlsx", "text"]),
             ("agreement", "agreement", ["latex", "svg", "csv"]), ("glossary", "glossary", ["markdown", "text", "csv"]),
             ("agreement_distribution", "a", ["pdf", "csv"]), ("counts", "c", ["csv"])]
    out = _js({"results": results, "normalize": [{"view": v, "params": p} for v, p in _NORMALIZE],
               "slugs": [{"view": v, "params": p} for v, p in _SLUGS],
               "itemPaths": [{"view": v, "slug": s, "formats": f} for v, s, f in paths]})
    py_norm = [_py_try(lambda v=v, p=p: normalize_params(v, p, results)) for v, p in _NORMALIZE]
    assert out["normalized"] == py_norm
    py_slugs = [view_slug(v, normalize_params(v, p, results), results) for v, p in _SLUGS]
    assert out["slugs"] == py_slugs
    assert out["itemPaths"] == [item_paths(v, s, f) for v, s, f in paths]


@pytest.mark.parametrize("mode,results", [("measured", _measured_edge()), ("statevector", _sv_edge()),
                                          ("measured", _counts_rich())])
def test_backend_subset_matches(mode, results):
    results = _json_roundtrip(results)
    sims = list(results["divergence_report"]["simulators"])
    picks = [sims[:1], sims[1:3], sims[::2], [], sims + ["x"]]
    assert _js({"results": results, "subsets": picks})["subsets"] == [subset_results(results, p) for p in picks]
