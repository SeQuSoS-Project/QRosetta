"""The self-test plan GET /selftest serves: two playlist requests with every request field
pinned here (never read from request_defaults), the circuits, their expected answers per
declared order, and the checks with their PASS/WARN/FAIL rules."""

import math

from config import settings
from services.selftest.circuits import (
    CIRCUITS, MEASURED, STATEVECTOR, circuit_text, expected_file_sha256, expected_statevector,
    load_expected,
)

SELFTEST_VERSION = "selftest-2026.10.27.2"
PLAN_SCHEMA = "qrosetta.selftest_plan@1"
EXPECTED_SHA256 = "f6f6dfef4c3d573905f120fc123b8c2b33441aba430f570aec57e541c43d3717"

N_SHOTS = 8200
SEED = 20261027
FIDELITY_TOLERANCE = 1e-5
NORM_TOLERANCE = 1e-4
GHZ_BALANCE_SIGMAS = 6.0
RUNNER_CPU_QUOTA_CORES = 1.0
RUNNER_MEMORY_LIMIT_MIB = 1024
THREAD_ENV_VALUE = "1"

THRESHOLDS = {"fidelity_tolerance": 1e-5, "phase_tolerance": 1e-6, "norm_tolerance": 1e-4,
              "js_threshold": 0.01, "hellinger_threshold": 0.1}

PINNED = {
    "optimization_level": 0,
    "runner_config": {},
    "runner_phases": {},
    "timeout_seconds": 120,
    "timing_repeats": 1,
    "exclusive": False,
    "bypass_limits": False,
    "apply_preprocessing": True,
    "thresholds": THRESHOLDS,
    "compilers": {},
    "simulate": True,
    "n_shots": N_SHOTS,
    "seed": SEED,
}

CLIENT_SETS = {"target_simulators": "The backends under test. Every result in the job is "
                                    "evaluated, and every backend named here must return one."}

KNOWN_ANSWER_CHECKS = [
    {"check": "plan", "pass": "the job is a playlist of this plan's part: its circuits, mode and "
                              "recorded settings equal the plan's",
     "fail": "a circuit not in the plan, a plan circuit not run, or a recorded setting that differs"},
    {"check": "statevector", "pass": (
        f"dispatch_status ok; qubit_ordering lsb or msb (and equal to the registry's when it records "
        f"one); 2**n amplitudes, all finite; |norm - 1| <= {NORM_TOLERANCE}; fidelity with the "
        f"expected state in that order, both vectors normalised, >= 1 - {FIDELITY_TOLERANCE}"),
     "fail": "any of these fails, or a backend named in target_simulators has no result"},
    {"check": "counts_key", "pass": "counts equal {the expected key for the declared order: n_shots}",
     "fail": "any other key, or a total other than n_shots"},
    {"check": "ghz_sampling", "pass": (
        f"only the all-0 and all-1 keys, total n_shots, and |p(all-0) - 0.5| <= "
        f"{GHZ_BALANCE_SIGMAS:g} sigma"),
     "fail": "any other key, another total, or a larger deviation"},
]

ENVIRONMENT_CHECKS = [
    {"check": "cpu_quota_cores", "field": "cpu_environment.cpu_quota_cores",
     "pass": f"{RUNNER_CPU_QUOTA_CORES}", "warn": None, "fail": "null or another value"},
    {"check": "thread_env", "field": "thread_env",
     "pass": f"every variable {THREAD_ENV_VALUE}", "warn": None, "fail": "otherwise"},
    {"check": "memory_method", "field": "memory_method",
     "pass": "vmhwm", "warn": "a sampling fallback", "fail": None},
    {"check": "memory_limit_mib", "field": "cpu_environment.memory_limit_mib",
     "pass": f"{RUNNER_MEMORY_LIMIT_MIB}", "warn": "null or another value", "fail": None},
    {"check": "precision", "field": "precision",
     "pass": "as the runner registry records it for the job's mode", "warn": None, "fail": "otherwise",
     "skip": "the registry records no precision (null) for the backend in that mode"},
    {"check": "qubit_ordering", "field": "qubit_ordering",
     "pass": "as the runner registry records it for the job's mode", "warn": None, "fail": "otherwise",
     "skip": "the registry records no qubit_ordering for the backend in that mode"},
    {"check": "host_virtualisation",
     "field": "cpu_environment.hypervisor or image_identity.host_hypervisor_cpu_flag",
     "pass": "false (bare metal)",
     "warn": "true: a virtual machine; timings are not comparable with bare-metal runs, "
             "known-answer checks are unaffected", "fail": None,
     "skip": "not recorded"},
    {"check": "host_emulation",
     "field": "cpu_environment.emulation or image_identity.emulation.emulated, cpu_environment.cpu_model",
     "pass": "emulation recorded as false (the image's architecture equals the host's)", "warn": None,
     "fail": "emulation recorded (the image's architecture differs from the host's), or a CPU model "
             "naming Rosetta (VirtualApple)",
     "skip": "not recorded"},
    {"check": "provenance", "field": "image_source, else image_identity.source and git_sha",
     "pass": "release, pulled or loaded", "warn": "built_locally or pulled-other",
     "fail": "unknown or not recorded, or a -dirty commit", "skip": "not recorded by this server's runners"},
]


def ghz_balance_bound(n_shots: int = N_SHOTS, p: float = 0.5) -> float:
    """``GHZ_BALANCE_SIGMAS`` binomial standard deviations of a proportion at ``n_shots``."""
    return GHZ_BALANCE_SIGMAS * math.sqrt(p * (1 - p) / n_shots)


def _pairs(state) -> list:
    return [[float(v.real), float(v.imag)] for v in state]


def _expected_view(entry: dict) -> dict:
    kind = entry["check"]
    if kind == "statevector":
        return {"statevector": {order: _pairs(expected_statevector(entry, order))
                                for order in ("lsb", "msb")},
                "amplitude_format": "[real, imaginary] per basis index"}
    if kind == "counts_key":
        return {"counts": {order: {key: N_SHOTS} for order, key in entry["counts_key"].items()}}
    return {"support": entry["support"], "p_all_zero": entry["p_all_zero"],
            "max_deviation": ghz_balance_bound()}


def part_request(part: str) -> dict:
    """The /run_batch_suite body of one part, without target_simulators."""
    tasks = [{"name": name, "source": "qasm", "qasm_string": circuit_text(name)}
             for name, circuit_part, _kind, _what in CIRCUITS if circuit_part == part]
    return {"mode": part, "tasks": tasks, **PINNED, "execution_target": settings.EXECUTION_MODE}


def selftest_plan() -> dict:
    """The body of GET /selftest."""
    expected = load_expected()["circuits"]
    circuits = []
    for name, part, kind, what in CIRCUITS:
        entry = expected[name]
        circuits.append({"name": name, "part": part, "check": kind, "tests": what,
                         "qasm": circuit_text(name), "qasm_sha256": entry["qasm_sha256"],
                         "n_qubits": entry["n_qubits"], "expected": _expected_view(entry)})
    return {
        "schema": PLAN_SCHEMA,
        "selftest_version": SELFTEST_VERSION,
        "expected_sha256": expected_file_sha256(),
        "expected_source": ("numpy reference built from the qelib1 matrices "
                            "(services/selftest/reference.py); no backend, SDK or pytket call"),
        "jobs": [{"part": part, "endpoint": "/run_batch_suite", "request": part_request(part),
                  "client_sets": CLIENT_SETS,
                  "evaluate": "GET /jobs/{job_id}/selftest-result"}
                 for part in (STATEVECTOR, MEASURED)],
        "circuits": circuits,
        "tolerances": {"fidelity_tolerance": FIDELITY_TOLERANCE, "norm_tolerance": NORM_TOLERANCE,
                       "ghz_balance_sigmas": GHZ_BALANCE_SIGMAS,
                       "ghz_max_deviation": ghz_balance_bound()},
        "known_answer_checks": KNOWN_ANSWER_CHECKS,
        "environment_checks": ENVIRONMENT_CHECKS,
        "pass_rule": ("PASS when no check FAILs and none WARNs; WARN when a check WARNs and none "
                      "FAILs; FAIL otherwise. SKIP rows do not change the outcome."),
        "tested": ("bit order, idle qubits, qubit permutation, cx direction, rz sign, measured key "
                   "order through the API path, sampling support and balance"),
        "not_tested": ("gates other than x, h, ry, rz and cx, user-defined gates, mid-circuit "
                       "measurement, circuits above 3 qubits, optimization levels above 0, "
                       "preprocessing off"),
    }
