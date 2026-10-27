"""A corpus of page workspaces for comparing the server planner (services/plan.py) with the
page's planner (static/js/run_plan.js planRuns and runLimitProblems)."""
import random

from config import settings
from services.preparation_limits import bundled_over_prep_limit

QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'
HUGE_QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[1];\n' + "// \"quoted\" comment\n" * 52000
BIG_QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[1];\n' + "x q[0];\n" * 70000

NAMES = ["", "Bell (2q)", "Custom", "GHZ (3q) (3q) ", "  spaced　", "zero​width",
         "rtl‮override", "́́", "emoji \U0001F600 (4q)", "x" * 300, "   ",
         "tab\tname", "(5q)", "name (12q)\n", " nbsp (2q) ", "\U0001F468‍\U0001F469"]

COMMON = {"optimization_level": 0, "timeout_seconds": 60, "timing_repeats": 1, "exclusive": False,
          "runner_config": {}, "runner_phases": {}, "target_simulators": ["qiskit", "cirq"],
          "execution_target": "local", "bypass_limits": False, "thresholds": None}

THRESHOLDS = {"fidelity_tolerance": 1e-5, "phase_tolerance": 1e-6, "norm_tolerance": 1e-4,
              "js_threshold": 0.01, "hellinger_threshold": 0.1}


def _items(rng: random.Random) -> list:
    bundled = bundled_over_prep_limit()
    pool = [
        {"algorithm": "ghz", "qubits": 3, "name": "GHZ State (Entanglement)"},
        {"source": "mqt", "algorithm": "qft", "qubits": "4", "name": "qft (4q)"},
        {"algorithm": "custom", "qubits": 2, "name": "mine", "qasm_string": QASM},
        {"qasm": QASM, "name": "old format (2q)", "algorithm": "custom"},
        {"algorithm": "", "qubits": None},
        {"qubits": "0x10", "algorithm": "bv", "name": ""},
        {"algorithm": "vqe", "qubits": 5.7, "name": "VQE (5q)", "source": None},
        {"algorithm": "random", "qubits": "  7abc", "source": "preset", "name": NAMES[rng.randrange(len(NAMES))]},
        {"source": "qasmbench", "algorithm": "adder_n4", "qubits": 0, "name": "adder_n4"},
        {"source": "mqt", "name": "no algorithm", "qubits": 3},
        {"qasm_string": QASM, "name": NAMES[rng.randrange(len(NAMES))], "qubits": "2"},
        {"algorithm": 7, "qubits": True, "name": 5},
    ]
    pool += [{**b, "name": f"{b['algorithm']} ({b['qubits']}q)"} for b in bundled]
    return [dict(rng.choice(pool)) for _ in range(rng.randrange(1, 8))]


def _common(rng: random.Random) -> dict:
    common = dict(COMMON)
    if rng.random() < 0.3:
        common["bypass_limits"] = True
    if rng.random() < 0.2:
        del common["timeout_seconds"]
    if rng.random() < 0.2:
        del common["execution_target"]
    if rng.random() < 0.3:
        common["thresholds"] = dict(THRESHOLDS)
    if rng.random() < 0.3:
        common["runner_config"] = {"qiskit": [0, 1], "cirq": 2}
    if rng.random() < 0.2:
        common["runner_phases"] = {"qiskit": 1, "cirq": 2}
    if rng.random() < 0.2:
        common["optimization_level"] = 2
    return common


def _workspace(rng: random.Random, **over) -> dict:
    modes = rng.choice([(True, False), (False, True), (True, True), (False, False)])
    ws = {
        "source": rng.choice(["editor", "list"]),
        "editor": {"qasm": rng.choice([QASM, QASM, "", "  \n\t", QASM + "é"]),
                   "name": rng.choice(NAMES)},
        "list": _items(rng),
        "modes": {"statevector": modes[0], "measured": modes[1]},
        "compilers": rng.choice([{}, {}, {"staq": [1]}, {"pyzx": [1, 2], "qmap": [0]}]),
        "preprocessing": rng.choice(["on", "off", "both"]),
        "rawRunName": rng.choice(NAMES),
        "shots": rng.choice([8200, 1, 1000000, 8200.0, 333]),
        "seed": rng.choice([None, 7, 2**31 - 1]),
        "common": _common(rng),
    }
    ws.update(over)
    return ws


def corpus() -> list:
    """Page workspaces: random combinations and the cases that reach each server limit."""
    rng = random.Random(20261027)
    cases = [_workspace(rng) for _ in range(700)]
    long_list = [{"algorithm": "ghz", "qubits": 3, "name": f"g{i}"} for i in range(settings.MAX_BATCH_TASKS + 1)]
    cells = [{"algorithm": "ghz", "qubits": 3, "name": f"c{i}"} for i in range(settings.MAX_EXPERIMENT_CELLS // 2 + 1)]
    bundled = [dict(b) for b in bundled_over_prep_limit()]
    for modes in ({"statevector": True, "measured": False}, {"statevector": True, "measured": True},
                  {"statevector": False, "measured": False}):
        for bypass in (False, True):
            common = {**COMMON, "bypass_limits": bypass}
            compilers = {} if (modes["statevector"] or modes["measured"]) else {"staq": [1]}
            cases += [
                _workspace(rng, source="list", list=long_list, modes=modes, preprocessing="on", common=common, compilers=compilers),
                _workspace(rng, source="list", list=cells, modes=modes, preprocessing="both", common=common, compilers=compilers),
                _workspace(rng, source="list", list=bundled, modes=modes, preprocessing="on", common=common, compilers=compilers),
                _workspace(rng, source="list", list=bundled[:1], modes=modes, preprocessing="off", common=common, compilers=compilers),
                _workspace(rng, source="editor", editor={"qasm": HUGE_QASM, "name": "huge"}, modes=modes,
                           preprocessing="on", common=common, compilers=compilers),
                _workspace(rng, source="editor", editor={"qasm": BIG_QASM, "name": "big (1q)"}, modes=modes,
                           preprocessing="both", common=common, compilers=compilers),
                _workspace(rng, source="list", modes=modes, preprocessing="on", common=common, compilers=compilers,
                           list=[{"qasm_string": BIG_QASM, "name": "a"}, {"qasm_string": QASM, "name": "b"}]),
                _workspace(rng, source="list", list=[], modes=modes, common=common, compilers=compilers),
            ]
    return cases


def js_limits() -> dict:
    """The limits the page passes to runLimitProblems, as GET /config gives them."""
    return {"maxRequestBytes": settings.MAX_UPLOAD_BYTES, "maxQasmSize": settings.MAX_QASM_SIZE,
            "maxExperimentCells": settings.MAX_EXPERIMENT_CELLS, "maxBatchTasks": settings.MAX_BATCH_TASKS,
            "prepMaxMib": settings.PREP_MAX_MIB, "bundledOverPrepLimit": bundled_over_prep_limit(),
            "executionMode": settings.EXECUTION_MODE}


def plan_request(ws: dict) -> dict:
    """The POST /plan body the page sends for workspace ``ws``."""
    request_settings = {k: {"value": v, "source": "flag"} for k, v in ws["common"].items()}
    request_settings["n_shots"] = {"value": ws["shots"], "source": "flag"}
    request_settings["seed"] = {"value": ws["seed"], "source": "flag"}
    from_list = ws["source"] == "list"
    return {
        "source": "playlist" if from_list else "single",
        "circuits": ws["list"] if from_list else [{"qasm_string": ws["editor"]["qasm"], "name": ws["editor"]["name"]}],
        "modes": [m for m in ("statevector", "measured") if ws["modes"][m]],
        "preprocessing": ws["preprocessing"],
        "compilers": ws["compilers"],
        "name": ws["rawRunName"],
        "settings": request_settings,
    }
