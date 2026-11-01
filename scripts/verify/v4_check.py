"""V4 checks of one job's results against the reference: statevector known answers, the
relabelling and register-split relations between a backend's own results, and sampled counts
against the reference distribution (Pearson goodness of fit, Holm across the job).

A row's status: PASS; FAIL (a wrong answer); REFUSED (the backend returned an error for the
circuit: no answer, which the platform reports as such); NO_RESULT (timeout, offline, or no
result in the report)."""

import base64
import math

import numpy as np
from scipy.stats import chi2

import qelib1_reference as ref

# Upstream behaviours CLAUDE.md §3.4 documents, as matrix models of the gates involved. A FAIL
# whose output equals the model's answer on the circuit the backend received is labelled with it.
PENNYLANE_UNITARY_GATES = ("cu3", "csx", "c3x", "c4x", "c3sqrtx", "rccx", "rc3x", "cu1", "cu", "u", "u0")


def _qibo_cu3(matrix, params):
    theta, phi, lam = params
    out = np.eye(4, dtype=complex)
    out[np.ix_([1, 3], [1, 3])] = np.exp(-0.5j * (phi + lam)) * ref.u_matrix(theta, phi, lam)
    return out


DEFECT_MODELS = (
    {"id": "pennylane-qubitunitary-wire-order", "backends": ("pennylane-default", "pennylane-lightning"),
     "documented": "PennyLane from_qasm swaps control and target on QubitUnitary (cu3, custom gates): "
                   "pennylane-qiskit 0.39 imports every Qiskit gate outside QISKIT_OPERATION_MAP as a "
                   "QubitUnitary of Qiskit's little-endian matrix, so its operands are reversed",
     "overrides": {g: (lambda m, p: ref.reverse_operands(m)) for g in PENNYLANE_UNITARY_GATES}},
    {"id": "qibo-cu3-phase", "backends": ("qibo",),
     "documented": "qibo cu3 is controlled(e^{-i(phi+lambda)/2} U3)",
     "overrides": {"cu3": _qibo_cu3}},
    {"id": "qrisp-cu1-as-crz", "backends": ("qrisp",),
     "documented": "qrisp runs cu1 as crz (and csx, defined through cu1, acts as crx(pi/2))",
     "overrides": {"cu1": lambda m, p: ref.GateLibrary().matrix("crz", p),
                   "csx": lambda m, p: ref.GateLibrary().matrix("crx", (math.pi / 2,))}},
)

FIDELITY_TOLERANCE = 1e-5
NORM_TOLERANCE = 1e-4
ALPHA = 0.01
SUPPORT_FLOOR = 1e-9


def decode(raw):
    """A result's statevector: base64 of complex128 bytes (``encode_statevector``), or a list."""
    if isinstance(raw, str):
        return np.frombuffer(base64.b64decode(raw), dtype=np.complex128).copy()
    if isinstance(raw, list):
        return np.array([complex(*v) if isinstance(v, (list, tuple)) else complex(v) for v in raw])
    raise ValueError("no statevector")


def to_lsb(state, ordering):
    return ref.to_order(state, ordering)


def permute(state_lsb, perm):
    """The lsb statevector after original qubit i is renamed perm[i]."""
    n = len(perm)
    inverse = [0] * n
    for i, p in enumerate(perm):
        inverse[p] = i
    tensor = np.asarray(state_lsb).reshape([2] * n)
    axes = [n - 1 - inverse[n - 1 - k] for k in range(n)]
    return np.transpose(tensor, axes).reshape(-1)


def result_problem(result):
    """``(status, reason)`` for a result without an answer, else None."""
    if result is None:
        return "NO_RESULT", "no result in the report"
    status = result.get("dispatch_status")
    if status in ("timeout", "offline"):
        return "NO_RESULT", f"{status}: {str(result.get('error') or '')[:200]}"
    if result.get("error") or (status not in (None, "ok")):
        return "REFUSED", str(result.get("error") or status)[:300]
    return None


def row(case, backend, status, reason, **values):
    return {"case": case["name"], "family": case["family"], "gate": case.get("gate"), "backend": backend,
            "status": status, "reason": reason, **values}


def statevector_row(case, backend, result):
    problem = result_problem(result)
    if problem:
        return row(case, backend, *problem)
    ordering = result.get("qubit_ordering")
    if ordering not in ("lsb", "msb"):
        return row(case, backend, "FAIL", f"qubit_ordering {ordering!r}")
    try:
        state = decode(result.get("statevector"))
    except (ValueError, TypeError):
        return row(case, backend, "FAIL", "no decodable statevector")
    n = case["n_qubits"]
    if state.size != 2 ** n:
        return row(case, backend, "FAIL", f"{state.size} amplitudes, expected {2 ** n}")
    if not np.all(np.isfinite(state)) or np.linalg.norm(state) == 0:
        return row(case, backend, "FAIL", "non-finite or zero statevector")
    norm = float(np.linalg.norm(state))
    fid = ref.fidelity(ref.to_order(case["expected"], ordering), state)
    best = max(ref.fidelity(ref.to_order(case["expected"], o), state) for o in ("lsb", "msb"))
    values = {"fidelity": fid, "norm": norm, "ordering": ordering, "fidelity_other_order": best}
    problems = []
    if abs(norm - 1) > NORM_TOLERANCE:
        problems.append(f"norm {norm:.9g}")
    if fid < 1 - FIDELITY_TOLERANCE:
        problems.append(f"fidelity {fid:.9g} with the reference in {ordering} order")
    if problems:
        return row(case, backend, "FAIL", "; ".join(problems), **values)
    return row(case, backend, "PASS", f"1-F {1 - fid:.1e}", **values)


def relation_row(case, partner, backend, result, partner_result):
    """A pair's relation on one backend's own results: b equals a with qubits renamed."""
    for r in (result, partner_result):
        problem = result_problem(r)
        if problem:
            return row(case, backend, problem[0], "pair: " + problem[1], check="relation")
    try:
        b = to_lsb(decode(result["statevector"]), result["qubit_ordering"])
        a = to_lsb(decode(partner_result["statevector"]), partner_result["qubit_ordering"])
    except (ValueError, TypeError, KeyError):
        return row(case, backend, "FAIL", "pair: no decodable statevector", check="relation")
    if a.size != b.size or a.size != 2 ** case["n_qubits"]:
        return row(case, backend, "FAIL", "pair: sizes differ", check="relation")
    fid = ref.fidelity(permute(a, case["perm"]), b)
    if fid < 1 - FIDELITY_TOLERANCE:
        return row(case, backend, "FAIL", f"relation fidelity {fid:.9g} with {partner['name']} renamed",
                   check="relation", fidelity=fid)
    return row(case, backend, "PASS", f"relation 1-F {1 - fid:.1e}", check="relation", fidelity=fid)


def goodness_of_fit(counts_lsb: dict, distribution: dict):
    """``(p_value, df, outside)``: Pearson chi-square of the counts against the reference
    distribution (bins with expected < 5 pooled, a pool under 5 merged into the smallest bin),
    and the shots on outcomes the reference gives probability < SUPPORT_FLOOR."""
    shots = sum(counts_lsb.values())
    outside = sum(c for k, c in counts_lsb.items() if distribution.get(k, 0.0) < SUPPORT_FLOOR)
    support = {k: p for k, p in distribution.items() if p >= SUPPORT_FLOOR}
    big = {k: p for k, p in support.items() if p * shots >= 5}
    small = [k for k in support if k not in big]
    bins = [([k], p) for k, p in big.items()]
    if small:
        pooled = sum(support[k] for k in small)
        if pooled * shots >= 5 or not bins:
            bins.append((small, pooled))
        else:
            smallest = min(range(len(bins)), key=lambda i: bins[i][1])
            bins[smallest] = (bins[smallest][0] + small, bins[smallest][1] + pooled)
    if len(bins) < 2:
        return 1.0, 0, outside
    total_p = sum(p for _k, p in bins)
    observed = np.array([sum(counts_lsb.get(k, 0) for k in keys) for keys, _p in bins], dtype=float)
    expected = np.array([p / total_p for _k, p in bins]) * (shots - outside)
    stat = float(np.sum((observed - expected) ** 2 / expected))
    df = len(bins) - 1
    return float(chi2.sf(stat, df)), df, outside


def counts_row(case, backend, result, shots):
    problem = result_problem(result)
    if problem:
        return row(case, backend, *problem)
    ordering = result.get("qubit_ordering")
    counts = result.get("counts")
    if ordering not in ("lsb", "msb") or not isinstance(counts, dict):
        return row(case, backend, "FAIL", f"qubit_ordering {ordering!r} or no counts")
    n = case["n_qubits"]
    lsb = {}
    for key, value in counts.items():
        if not isinstance(key, str) or len(key) != n or set(key) - {"0", "1"}:
            return row(case, backend, "FAIL", f"key {key!r} is not {n} classical bits")
        k = key if ordering == "lsb" else key[::-1]
        lsb[k] = lsb.get(k, 0) + int(value)
    total = sum(lsb.values())
    if total != shots:
        return row(case, backend, "FAIL", f"{total} shots, expected {shots}")
    p, df, outside = goodness_of_fit(lsb, case["distribution"])
    values = {"p_value": p, "df": df, "outside_support": outside, "ordering": ordering}
    if outside:
        return row(case, backend, "FAIL", f"{outside} shots on outcomes the reference excludes", **values)
    return row(case, backend, "PENDING", f"chi-square p {p:.3g} (df {df})", **values)


def holm(rows, alpha=ALPHA):
    """Rows PENDING a p-value become PASS or FAIL under Holm at ``alpha`` across ``rows``."""
    pending = sorted((r for r in rows if r["status"] == "PENDING"), key=lambda r: r["p_value"])
    m = len(pending)
    rejecting = True
    for i, r in enumerate(pending):
        threshold = alpha / (m - i)
        rejecting = rejecting and r["p_value"] <= threshold
        r["status"] = "FAIL" if rejecting else "PASS"
        r["holm_threshold"] = threshold
    return rows


def evaluate(cases, raw_by_task, mode, shots=None, dispatched=None):
    """Rows for every case x backend in ``raw_by_task`` ({task name: {backend: result}});
    ``dispatched`` ({task name: {backend: qasm}}) lets FAIL rows be matched to DEFECT_MODELS."""
    by_name = {c["name"]: c for c in cases}
    backends = sorted({b for results in raw_by_task.values() for b in results})
    rows = []
    for case in cases:
        results = raw_by_task.get(case["name"], {})
        for backend in backends:
            result = results.get(backend)
            if mode == "statevector":
                rows.append(statevector_row(case, backend, result))
                if "pair" in case:
                    partner = by_name[case["pair"]]
                    rows.append(relation_row(case, partner, backend, result,
                                             raw_by_task.get(partner["name"], {}).get(backend)))
            else:
                rows.append(counts_row(case, backend, result, shots))
    if mode == "measured":
        holm(rows)
    for r in rows:
        if r["status"] == "FAIL" and r.get("check") != "relation" and dispatched:
            qasm = dispatched.get(r["case"], {}).get(r["backend"])
            if qasm:
                explain(r, by_name[r["case"]], raw_by_task[r["case"]][r["backend"]], qasm, mode)
    return rows


def explain(row_, case, result, dispatched, mode):
    """Label a FAIL row with the documented model that reproduces the backend's answer on
    ``dispatched`` (the circuit it received), if one does."""
    for model in DEFECT_MODELS:
        if row_["backend"] not in model["backends"]:
            continue
        library = ref.GateLibrary(overrides=model["overrides"])
        try:
            if mode == "statevector":
                expected = ref.statevector(dispatched, library)
                state = decode(result["statevector"])
                fit = ref.fidelity(ref.to_order(expected, result["qubit_ordering"]), state) >= 1 - FIDELITY_TOLERANCE
            else:
                distribution = ref.clbit_distribution(dispatched, library)
                counts = {(k if result["qubit_ordering"] == "lsb" else k[::-1]): v for k, v in result["counts"].items()}
                p_value, _df, outside = goodness_of_fit(counts, distribution)
                fit = outside == 0 and p_value >= row_.get("holm_threshold", ALPHA)
        except (ref.ReferenceError, KeyError, ValueError, TypeError):
            continue
        if fit:
            row_["explained_by"] = model["id"]
            return row_
    return row_


def summary(rows):
    """{backend: {status: count}} and the FAIL rows."""
    table = {}
    for r in rows:
        table.setdefault(r["backend"], {}).setdefault(r["status"], 0)
        table[r["backend"]][r["status"]] += 1
    return table, [r for r in rows if r["status"] == "FAIL"]
