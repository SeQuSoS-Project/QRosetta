"""Reports for the verdict equivalence test: recorded reports in the repository, reports the
divergence analysis builds from synthetic runner results, and synthetic pair records that
cover every label combination and the fields older reports lack or hold in other places."""

import json
from itertools import combinations
from pathlib import Path

import numpy as np

from qrosetta_commons.helpers import encode_statevector
from services.analysis.divergence import create_counts_report, create_divergence_report

REPO = Path(__file__).resolve().parents[3]

AGREEMENTS = [
    "agree_directly", "agree_up_to_global_phase", "agree_after_bit_reversal",
    "agree_after_qubit_permutation", "agree_after_normalization", "residual_disagreement",
    "unaligned_basis_match", "not_comparable", "distance_within_threshold",
    "distance_exceeds_threshold", "something_else", "", None, 3, ["residual_disagreement"],
]
ASSESSMENTS = [
    "consistent_within_shot_noise", "inconclusive_low_shots", "distinguishable", "ambiguous",
    "not_comparable", "unassessed", "", None, 0, 1, True, False, ["distinguishable"], {"a": 1}, [], {},
]
VERDICTS = [
    "consistent", "inconclusive_low_shots", "distinguishable", "ambiguous", "other", "", None, 0,
    ["consistent"], [["distinguishable"]], ["consistent", "x"], [None], {"v": 1},
]
MARGINALS = [
    "marginal_distinguishable", "no_marginal_difference_detected", "not_applicable", "not_tested",
    "", None, ["marginal_distinguishable"],
]
UNALIGNED = ["direct", "bit_reversal", "", True, False, None, 1, ["direct"], [], {}]
NORMALIZED = ["agree_directly", "agree_up_to_global_phase", "residual_disagreement",
              "agree_after_bit_reversal", "", None, 0, ["x"], [], {}]
MODES = ["measured", "statevector", None, "MEASURED", ""]
FWER = [True, False, None, 0, 1, "false"]
SIZES = [0.0, 0.5, 1.0, 0.999999, 1e-9, 1, 0, -0.1, None, "0.4", True, [0.3]]
ERRORS = [
    None, "", "Connection refused by runner", "Name or service not known", "TIMEOUT (60s): took too long",
    "The runner timed out", "time out", "time\u00a0out", "time\u2003out", "time\ufeffout", "time\x1cout",
    "TIMEDOUT", "tim\u0131out", "t\u0131me out", "T\u0130MED OUT", "Failed to fetch", "502 Bad Gateway",
    "CRITICAL CRASH", "\u0130 failed to connect", "SERVICE UNAVAILABLE", "ValueError: bad gate",
    ["connection refused"], ["timed", "out"], ["timed out"], {"e": 1}, 0, 1, True,
]
DISPATCH = ["ok", "error", "timeout", "offline", "OK", "", None, "cancelled", 1]
ORDERINGS = ["lsb", "msb", None, "", 1, ["msb"]]
KEYS = ["qiskit", "cirq", "qulacs", "quest", "qrisp", "qsim-cirq", "pennylane-default", "qiskit~opt0~run1",
        "qiskit~opt1~run2", "qiskit~opt0~run10", "a", "b", "0", "length", "z9"]


def recorded_reports() -> list:
    """(name, report) for every recorded report in the repository: the experiment results
    and the example crate's results."""
    files = sorted((REPO / "experiments").glob("*/results/**/*.json"))
    files += [REPO / "examples" / "ro-crate-export" / "results.json"]
    out = []
    for path in files:
        if path.is_file():
            data = json.loads(path.read_text())
            if isinstance(data, dict) and isinstance(data.get("divergence_report"), dict):
                out.append((str(path.relative_to(REPO)), data))
    return out


def _state(rng, n, shape):
    size = 2 ** n
    if shape == "basis":
        sv = np.zeros(size, dtype=complex)
        sv[int(rng.integers(0, size))] = 1
    elif shape == "ghz":
        sv = np.zeros(size, dtype=complex)
        sv[0] = sv[-1] = 2 ** -0.5
    else:
        sv = rng.normal(size=size) + 1j * rng.normal(size=size)
    return sv / np.linalg.norm(sv)


def _status_fields(rng, i):
    """Runner outcome fields: dispatch_status with or without error text, or error text only."""
    kind = i % 7
    if kind == 5:
        return {"error": str(rng.choice(["Connection refused", "TIMEOUT (30s)", "bad gate"]))}
    if kind == 6:
        return {"dispatch_status": str(rng.choice(["error", "timeout", "offline"])), "error": "failed"}
    return {"dispatch_status": "ok"}


def _statevector_results(rng, case):
    shapes = ["random", "basis", "ghz", "permuted", "reversed", "phase", "unnormalised", "mixed", "failed"]
    shape = shapes[case % len(shapes)]
    n = int(rng.integers(1, 5))
    k = int(rng.choice([2, 3, 5, 6]))
    base = _state(rng, n, shape if shape in ("basis", "ghz") else "random")
    results = []
    for b in range(k):
        sv = base.copy()
        if shape == "permuted" and b % 2 and n > 1:
            sv = sv.reshape([2] * n).transpose(rng.permutation(n)).reshape(-1)
        elif shape == "reversed" and b % 2 and n > 1:
            sv = sv.reshape([2] * n).transpose(list(reversed(range(n)))).reshape(-1)
        elif shape == "phase" and b % 2:
            sv = sv * np.exp(1j * rng.uniform(-np.pi, np.pi))
        elif shape == "unnormalised" and b % 2:
            sv = sv * 1.01
        elif shape == "mixed" and b % 3 == 2:
            sv = _state(rng, n, "random")
        result = {"simulator": KEYS[b], "qubit_ordering": "lsb" if b % 2 else "msb", **_status_fields(rng, b + case)}
        if shape != "failed" or b % 2 == 0:
            result["statevector"] = encode_statevector(sv)
        results.append(result)
    return f"statevector {case} {shape} n={n} k={k}", results


def _counts_results(rng, case):
    shapes = ["dense", "ghz", "single", "permuted", "reversed", "one_bit", "low_shots", "skewed", "failed"]
    shape = shapes[case % len(shapes)]
    n = 1 if shape == "one_bit" else int(rng.integers(2, 5))
    k = int(rng.choice([2, 3, 5, 6]))
    shots = 20 if shape == "low_shots" else int(rng.choice([200, 2000, 8200]))
    if shape == "ghz":
        p = np.zeros(2 ** n)
        p[0] = p[-1] = 0.5
    elif shape == "single":
        p = np.zeros(2 ** n)
        p[int(rng.integers(0, 2 ** n))] = 1.0
    else:
        p = rng.dirichlet(np.full(2 ** n, 2.0))
    results, base = [], None
    for b in range(k):
        q = p
        if shape == "skewed" and b == k - 1:
            q = np.roll(p, 1)
        counts = {format(i, f"0{n}b"): int(v) for i, v in enumerate(rng.multinomial(shots, q)) if v}
        if base is None:
            base = counts
        elif shape == "permuted" and b % 2:
            perm = rng.permutation(n)
            counts = {"".join(key[s] for s in perm): v for key, v in base.items()}
        elif shape == "reversed" and b % 2:
            counts = {key[::-1]: v for key, v in base.items()}
        result = {"simulator": KEYS[b], "qubit_ordering": "lsb" if b % 2 else "msb", "runner_seed": b,
                  **_status_fields(rng, b + case)}
        if shape != "failed" or b % 2 == 0:
            result["counts"] = counts
        results.append(result)
    return f"counts {case} {shape} n={n} k={k} shots={shots}", results, shots


def analysis_reports(rng, n_cases: int) -> list:
    """(name, report) built by the divergence analysis from synthetic runner results."""
    out = []
    for case in range(n_cases):
        name, results = _statevector_results(rng, case)
        out.append((name, {"raw_results": results, "divergence_report": create_divergence_report(results)}))
        name, results, shots = _counts_results(rng, case)
        out.append((name, {"n_shots": shots, "raw_results": results,
                           "divergence_report": create_counts_report(results, shots)}))
    return out


def _maybe(rng, target: dict, key: str, values, p_missing=0.3):
    if rng.random() >= p_missing:
        target[key] = values[int(rng.integers(0, len(values)))]


def synthetic_pair(rng, a, b) -> dict:
    """A pair record with each field drawn from its values, missing, or of another type."""
    pair = {"simulators": [a, b]}
    _maybe(rng, pair, "mode", MODES, 0.15)
    _maybe(rng, pair, "agreement", AGREEMENTS, 0.05)
    _maybe(rng, pair, "measured_assessment", ASSESSMENTS, 0.5)
    _maybe(rng, pair, "marginal_assessment", MARGINALS, 0.4)
    _maybe(rng, pair, "unaligned_basis_match", UNALIGNED, 0.85)
    shape = rng.random()
    if shape < 0.08:
        _maybe(rng, pair, "metrics", [None, "metrics", 0, [1, 2], True], 0.0)
        return pair
    metrics = {}
    _maybe(rng, metrics, "measured_assessment", ASSESSMENTS, 0.7)
    _maybe(rng, metrics, "unaligned_basis_match", UNALIGNED, 0.7)
    _maybe(rng, metrics, "normalized_agreement", NORMALIZED, 0.5)
    _maybe(rng, metrics, "label_aligned_fidelity", SIZES, 0.4)
    _maybe(rng, metrics, "direct_fidelity", SIZES, 0.4)
    _maybe(rng, metrics, "marginal_test", [{"assessment": "x"}, {}, None, 1, "t"], 0.5)
    if rng.random() < 0.8:
        st = {}
        _maybe(rng, st, "verdict", VERDICTS, 0.3)
        _maybe(rng, st, "significant_fwer", FWER, 0.3)
        if rng.random() < 0.7:
            st["effect_size"] = {}
            _maybe(rng, st["effect_size"], "total_variation", SIZES, 0.2)
        metrics["statistical_test"] = st
    pair["metrics"] = metrics
    return pair


def synthetic_reports(rng, n_reports: int) -> list:
    """(name, report) of synthetic pairs over a few backends, with raw results of every
    status form, missing or extra backends, and pairs that are not two keys."""
    out = []
    for r in range(n_reports):
        k = int(rng.integers(2, 7))
        keys = [str(key) for key in rng.choice(KEYS, size=k, replace=False)]
        pairs = [synthetic_pair(rng, a, b) for a, b in combinations(keys, 2)]
        if rng.random() < 0.2:
            pairs.append({"simulators": [keys[0]], "agreement": "residual_disagreement"})
        if rng.random() < 0.2:
            pairs.append(synthetic_pair(rng, keys[0], "extra-backend"))
        raws = []
        for key in keys + (["raw-only"] if rng.random() < 0.2 else []):
            raw = {"simulator": key}
            _maybe(rng, raw, "dispatch_status", DISPATCH, 0.4)
            _maybe(rng, raw, "error", ERRORS, 0.4)
            raws.append(raw)
        if rng.random() < 0.1 and raws:
            raws.append({**raws[0], "dispatch_status": "timeout"})
        div = {"pairwise_agreement": pairs}
        if rng.random() < 0.7:
            div["simulators"] = keys[::-1] if rng.random() < 0.5 else keys
        if rng.random() < 0.8:
            ordering = {}
            for key in keys:
                _maybe(rng, ordering, key, ORDERINGS, 0.2)
            div["ordering_map"] = ordering
        elif rng.random() < 0.5:
            div["ordering_map"] = [str(rng.choice(["lsb", "msb"])) for _ in range(3)]
        report = {"raw_results": raws, "divergence_report": div}
        _maybe(rng, report, "n_shots", [8200, 0, None, 100], 0.5)
        out.append((f"synthetic {r}", report))
    return out


BACKENDS = ["qiskit", "cirq", "qulacs", "quest", "pennylane-lightning", "pennylane-default", "qsim-cirq", "qibo",
            "qrisp", "myqlm", "pyquil", "torchquantum", "quimb", "cuquantum"]
RUNS = ["qiskit~opt0~run1", "qiskit~opt0~run2", "qiskit~opt0~run10", "qiskit~opt1~run1", "qsim-cirq~opt0~run1"]
COLLATION_KEYS = ["a", "ab", "a-b", "a~opt0~run1", "a0", "b", "b~opt1~run2", "ba", "b-a", "b0", "z", "z9", "0", "0a",
                  "9-x", "x~opt2~run1", "xa"]


def _headline_pair(a, b, v, measured, size):
    if not measured:
        metrics = {} if size is None else {"label_aligned_fidelity": size}
        label = {"differ": "residual_disagreement", "perm": "agree_after_qubit_permutation",
                 "bit": "agree_after_bit_reversal"}.get(v, "agree_directly")
        return {"simulators": [a, b], "mode": "statevector", "agreement": label, "metrics": metrics}
    assessment = {"agree": "consistent_within_shot_noise", "differ": "distinguishable", "by": "distinguishable",
                  "inc": "inconclusive_low_shots", "amb": "ambiguous", "marg": "consistent_within_shot_noise",
                  "marginc": "inconclusive_low_shots"}.get(v, "consistent_within_shot_noise")
    st = {"significant_fwer": v != "by", "verdict": assessment}
    if size is not None:
        st["effect_size"] = {"total_variation": size}
    return {"simulators": [a, b], "mode": "measured", "agreement": "distance_within_threshold",
            "measured_assessment": assessment,
            "marginal_assessment": ("marginal_distinguishable" if v in ("marg", "marginc")
                                    else "no_marginal_difference_detected"),
            "metrics": {"marginal_test": {}, "statistical_test": st}}


def headline_reports(rng, n_reports: int) -> list:
    """(name, report) shaped to reach every headline kind: one or a few wrong backends, groups
    that differ from each other, scattered pairs, failed backends, BY-only and inconclusive
    pairs, multi-run keys, and sizes with ties."""
    out = []
    for r in range(n_reports):
        x = rng.random()
        pool = BACKENDS + RUNS if x < 0.2 else COLLATION_KEYS if x < 0.45 else BACKENDS
        names = [str(k) for k in rng.choice(pool, size=int(rng.integers(2, min(len(pool), 16) + 1)), replace=False)]
        measured = rng.random() < 0.5
        shape = r % 4
        wrong = set(rng.choice(names, size=int(rng.integers(0, min(4, len(names)) + 1)), replace=False))
        camp = set(rng.choice(names, size=len(names) // 2, replace=False))
        p_differ, p_other = rng.random() * 0.5, rng.random() * 0.5
        sizes = [0.1, 0.25, 0.5, 0.9, 0.999, 1.0] if rng.random() < 0.5 else None
        pairs = []
        for a, b in combinations(names, 2):
            x = rng.random()
            if shape == 1:
                v = "differ" if (a in camp) != (b in camp) and x < 0.95 else "agree"
            elif {a, b} & wrong and x < 0.8:
                v = "differ"
            elif x < p_differ * (0.3 if shape == 0 else 1.0):
                v = "differ"
            elif x < p_differ + p_other:
                options = ["inc", "by", "marg", "marginc", "amb"] if measured else ["bit", "perm", "agree"]
                v = str(rng.choice(options))
            else:
                v = "agree"
            size = None
            if rng.random() < 0.9:
                size = sizes[int(rng.integers(0, len(sizes)))] if sizes else float(rng.random())
            pairs.append(_headline_pair(a, b, v, measured, size))
        raws = []
        for name in names:
            x = rng.random()
            status = "ok" if x < 0.85 else str(rng.choice(["error", "timeout", "offline"]))
            raws.append({"simulator": name, "dispatch_status": status})
        report = {"raw_results": raws, "divergence_report": {"pairwise_agreement": pairs, "simulators": names}}
        if measured:
            report["n_shots"] = 8200
        out.append((f"headline {r} shape={shape}", report))
    return out


def corpus(seed: int = 20261027, n_analysis: int = 36, n_synthetic: int = 600, n_headline: int = 400) -> list:
    """Every report of the equivalence corpus as (name, report)."""
    rng = np.random.default_rng(seed)
    return (recorded_reports() + analysis_reports(rng, n_analysis) + synthetic_reports(rng, n_synthetic)
            + headline_reports(rng, n_headline))
