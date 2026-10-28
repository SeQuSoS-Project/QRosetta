"""Fixed-seed corpus for the requalification harness: random qelib1 circuits from
scripts/adapter_paths/compare_paths.py (1-10 qubits, every optimisation level the service offers,
preprocessing on and off; measured with shots 1/17/1000 and seeds 0/7/123456789, terminal
measurements only and, for a third as many circuits, mid-circuit measurements too), a deep set
(500-3000 gates, up to 16 qubits), the self-test circuits of rosetta-api/circuits/selftest, and
the three timing circuits of scripts/adapter_paths/time_paths.py."""

import os
import random
import sys

from registry import REPO

sys.path.insert(0, str(REPO / "scripts" / "adapter_paths"))
import compare_paths  # noqa: E402
import time_paths  # noqa: E402

CIRCUIT_SEED = 20261002
PAYLOAD_SEED = 20261028
SHOTS = (1, 17, 1000)
SEEDS = (0, 7, 123456789)
SELFTEST_DIR = REPO / "rosetta-api" / "circuits" / "selftest"


def _circuits(n, measured, env, stream):
    saved = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        rng = random.Random(CIRCUIT_SEED + stream)
        return [compare_paths.random_circuit(rng, measured) for _ in range(n)]
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _strip_measurements(qasm):
    return "".join(line for line in qasm.splitlines(keepends=True)
                   if not line.startswith(("measure ", "creg ")))


def build(kind, levels, n_sv, n_measured, n_deep, single_register=False, max_gates=None):
    """[(case dict)] with ``id``, ``kind`` (corpus part), ``endpoint`` and ``payload``."""
    base_env = {"SINGLE_REGISTER": "1"} if single_register else {}
    if max_gates:
        base_env["MAX_GATES"] = str(max_gates)
    deep_env = {**base_env, "MIN_GATES": "500", "MAX_GATES": "3000", "MAX_QUBITS": "16"}
    rng = random.Random(PAYLOAD_SEED)
    cases = []

    def add(part, endpoint, qasm, levels_, pres, measured):
        for level in levels_:
            for pre in pres:
                payload = {"circuit_data": qasm, "optimization_level": level}
                if kind == "runner":
                    payload["apply_preprocessing"] = pre
                    if measured:
                        payload.update(n_shots=rng.choice(SHOTS), seed=rng.choice(SEEDS))
                cases.append({"id": f"{part}-{len(cases):05d}", "kind": part, "endpoint": endpoint,
                              "level": level, "pre": pre if kind == "runner" else None, "payload": payload})

    pres = (True, False) if kind == "runner" else (None,)
    selftest = sorted(SELFTEST_DIR.glob("*.qasm"))
    if kind == "runner":
        for qasm in _circuits(n_sv, False, base_env, 0):
            add("random_sv", "run", qasm, levels, pres, False)
        for qasm in _circuits(n_measured, True, {**base_env, "TERMINAL_ONLY": "1"}, 1):
            add("random_measured", "run_measured", qasm, levels, pres, True)
        for qasm in _circuits(n_measured // 3, True, base_env, 4):
            add("midcircuit_measured", "run_measured", qasm, levels, pres, True)
        for qasm in _circuits(n_deep, False, deep_env, 2):
            add("deep_sv", "run", qasm, levels, pres, False)
        for qasm in _circuits(n_deep, True, {**deep_env, "TERMINAL_ONLY": "1"}, 3):
            add("deep_measured", "run_measured", qasm, levels, pres, True)
        for path in selftest:
            measured = path.name.startswith("m_")
            add("selftest_" + ("measured" if measured else "sv"), "run_measured" if measured else "run",
                path.read_text(), levels, pres, measured)
    else:
        for qasm in _circuits(n_sv, False, base_env, 0):
            add("random", "compile", qasm, levels, pres, False)
        for qasm in _circuits(n_deep, False, deep_env, 2):
            add("deep", "compile", qasm, levels, pres, False)
        for path in selftest:
            add("selftest", "compile", _strip_measurements(path.read_text()), levels, pres, False)
    return cases


def cli_case_ids(cases, per_part=2):
    """A few cases of each corpus part that also go through ``main.py --endpoint``."""
    chosen, seen = [], {}
    for case in cases:
        if seen.get(case["kind"], 0) < per_part:
            seen[case["kind"]] = seen.get(case["kind"], 0) + 1
            chosen.append(case["id"])
    return chosen


def timing_payloads(repeats):
    """{file name: {endpoint, payload}} for the three timing circuits in both modes."""
    out = {}
    for measured in (False, True):
        for name, qasm in time_paths.timing_cases(measured).items():
            payload = {"circuit_data": qasm, "timing_repeats": repeats}
            if measured:
                payload.update(n_shots=8200, seed=1)
            mode = "measured" if measured else "sv"
            out[f"{mode}-{name}.json"] = {"endpoint": "run_measured" if measured else "run", "payload": payload}
    return out

