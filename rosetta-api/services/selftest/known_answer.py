"""Known-answer checks of one backend result: a statevector against the pinned expected state
in the backend's declared bit order, a deterministic probe's counts against its one key, and
the sampled GHZ-3 against its support and balance. Each returns one PASS or FAIL row."""

import json

import numpy as np

from qrosetta_commons.helpers import decode_statevector
from services.selftest import reference
from services.selftest.circuits import expected_statevector
from services.selftest.environment import FAIL, PASS, registry_value
from services.selftest.plan import FIDELITY_TOLERANCE, N_SHOTS, NORM_TOLERANCE, ghz_balance_bound

_ORDERS = ("lsb", "msb")
SHOWN = 300


def row(check, status, reason, backend=None, circuit=None, **values) -> dict:
    return {"check": check, "status": status, "reason": reason, "backend": backend,
            "circuit": circuit, **values}


def _short(value) -> str:
    text = json.dumps(value, sort_keys=True, default=str)
    return text if len(text) <= SHOWN else text[:SHOWN] + "..."


def run_problem(result: dict):
    status = result.get("dispatch_status")
    if result.get("error") or (status is not None and status != "ok"):
        error = str(result.get("error") or "")[:SHOWN]
        return f"{status or 'error'}: {error}" if error else str(status)
    return None


def _order(result: dict, key: str, part: str):
    """``(ordering, problem)``: the declared order the expected answer is taken in."""
    declared = result.get("qubit_ordering")
    if declared not in _ORDERS:
        return None, f"qubit_ordering {declared!r} is not lsb or msb"
    registered = registry_value(key, "qubit_ordering", part)
    if registered is not None and registered != declared:
        return declared, f"result declares {declared}, the runner registry records {registered}"
    return declared, None


def _statevector(raw):
    if isinstance(raw, str):
        return decode_statevector(raw)
    if isinstance(raw, list):
        return np.array([complex(v) if not isinstance(v, (list, tuple)) else complex(*v) for v in raw])
    raise ValueError("no statevector")


def _statevector_row(key, result, name, entry, part) -> dict:
    ordering, problem = _order(result, key, part)
    values = {"qubit_ordering": result.get("qubit_ordering"),
              "order_source": "registry" if registry_value(key, "qubit_ordering", part) else "result"}
    if ordering is None:
        return row("statevector", FAIL, problem, key, name, **values)
    problems = [problem] if problem else []
    try:
        state = _statevector(result.get("statevector"))
    except (ValueError, TypeError):
        return row("statevector", FAIL, "the result holds no decodable statevector", key, name, **values)
    n = entry["n_qubits"]
    if state.size != 2 ** n:
        return row("statevector", FAIL, f"{state.size} amplitudes, expected {2 ** n}", key, name, **values)
    if not np.all(np.isfinite(state)) or np.linalg.norm(state) == 0:
        return row("statevector", FAIL, "non-finite or zero statevector", key, name, **values)
    norm = float(np.linalg.norm(state))
    fid = reference.fidelity(expected_statevector(entry, ordering), state)
    values.update(fidelity=fid, infidelity=1.0 - fid, norm=norm)
    if abs(norm - 1.0) > NORM_TOLERANCE:
        problems.append(f"norm {norm:.9g}, allowed 1 +/- {NORM_TOLERANCE:g}")
    if fid < 1.0 - FIDELITY_TOLERANCE:
        problems.append(f"fidelity with the expected state ({ordering}) {fid:.9g}, "
                        f"required >= 1 - {FIDELITY_TOLERANCE:g}")
    if problems:
        return row("statevector", FAIL, "; ".join(problems), key, name, **values)
    return row("statevector", PASS, f"fidelity 1 - {1.0 - fid:.1e} ({ordering})", key, name, **values)


def _counts(result):
    counts = result.get("counts")
    if not isinstance(counts, dict) or not all(
            isinstance(k, str) and isinstance(v, int) and not isinstance(v, bool) for k, v in counts.items()):
        return None
    return counts


def _counts_key_row(key, result, name, entry, part) -> dict:
    ordering, problem = _order(result, key, part)
    values = {"qubit_ordering": result.get("qubit_ordering")}
    if ordering is None:
        return row("counts_key", FAIL, problem, key, name, **values)
    expected = {entry["counts_key"][ordering]: N_SHOTS}
    counts = _counts(result)
    values["expected_counts"] = expected
    if counts != expected:
        return row("counts_key", FAIL, f"expected {_short(expected)} ({ordering}), got {_short(result.get('counts'))}"
                    + (f"; {problem}" if problem else ""), key, name, **values)
    if problem:
        return row("counts_key", FAIL, problem, key, name, **values)
    return row("counts_key", PASS, f"every shot on {next(iter(expected))} ({ordering})", key, name, **values)


def _ghz_row(key, result, name, entry, part) -> dict:
    ordering, problem = _order(result, key, part)
    values = {"qubit_ordering": result.get("qubit_ordering")}
    if ordering is None:
        return row("ghz_sampling", FAIL, problem, key, name, **values)
    counts = _counts(result)
    if counts is None:
        return row("ghz_sampling", FAIL, f"counts not readable: {_short(result.get('counts'))}", key, name, **values)
    support = entry["support"][ordering]
    problems = [problem] if problem else []
    outside = sorted(k for k in counts if k not in support and counts[k])
    if outside:
        problems.append(f"outcomes outside {support}: {_short(outside)}")
    total = sum(counts.values())
    if total != N_SHOTS:
        problems.append(f"{total} shots, expected {N_SHOTS}")
    p0 = counts.get(support[0], 0) / N_SHOTS
    bound = ghz_balance_bound()
    deviation = abs(p0 - entry["p_all_zero"])
    values.update(p_all_zero=p0, deviation=deviation, max_deviation=bound)
    if deviation > bound:
        problems.append(f"p({support[0]}) = {p0:.4f}, more than {bound:.4f} from 0.5")
    if problems:
        return row("ghz_sampling", FAIL, "; ".join(problems), key, name, **values)
    return row("ghz_sampling", PASS, f"support ok, p({support[0]}) = {p0:.4f} (bound +/- {bound:.4f})",
                key, name, **values)


KNOWN_ANSWER = {"statevector": _statevector_row, "counts_key": _counts_key_row,
                 "ghz_sampling": _ghz_row}
