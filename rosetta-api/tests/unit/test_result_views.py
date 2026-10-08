"""Result views (play-test round 1): pair metrics in the label-aligned basis, the Summary headline's
groups and BY-only line, run counting in multi-run mode, column number formats, compile-only
headlines, the browser gate counter and the Performance overlap marks in the publication table."""
import json
from itertools import combinations
from pathlib import Path

from qrosetta_commons.helpers import count_qasm_gates_and_depth, count_qasm_gates_by_name
from services.publication.tables import _tbl_performance
from tests.unit.frontend_harness import call_js, requires_node
from tests.unit.test_artifacts_parity import _repeated_timing

_ROOT = Path(__file__).resolve().parents[2]


def _sv(a, b, label, **metrics):
    return {"simulators": [a, b], "mode": "statevector", "agreement": label, "metrics": metrics}


def _m(a, b, assessment, marginal="no_marginal_difference_detected", fwer=None, marginal_test=True):
    st = {"verdict": assessment}
    if fwer is not None:
        st["significant_fwer"] = fwer
    return {"simulators": [a, b], "mode": "measured", "agreement": "distance_within_threshold",
            "measured_assessment": assessment, "marginal_assessment": marginal,
            "metrics": {"statistical_test": st, "marginal_test": {"bits": []} if marginal_test else None}}


def _report(pairs, sims, n_shots=None):
    return {"n_shots": n_shots, "raw_results": [{"simulator": s, "dispatch_status": "ok"} for s in sims],
            "divergence_report": {"simulators": sims, "pairwise_agreement": pairs}}


@requires_node
def test_disagreeing_lsb_msb_pair_shows_the_label_aligned_fidelity():
    residual = _sv("qiskit", "qrisp", "residual_disagreement", direct_fidelity=0.0553, bit_reversed_fidelity=0.933,
                   label_aligned_basis="bit_reversal", label_aligned_fidelity=0.933)
    unaligned = _sv("qiskit", "pennylane-lightning", "residual_disagreement", direct_fidelity=1.0,
                    bit_reversed_fidelity=0.7787, label_aligned_basis="bit_reversal",
                    label_aligned_fidelity=0.7787, unaligned_basis_match="direct")
    same_order = _sv("cirq", "qrisp", "residual_disagreement", direct_fidelity=0.933, bit_reversed_fidelity=0.2,
                     label_aligned_basis="direct", label_aligned_fidelity=0.933)
    out = call_js(["tables_renderer.js"], [("pairMetricText", [p]) for p in (residual, unaligned, same_order)])
    assert out[0] == "F(bit-rev)=0.9330"
    assert out[1] == "F(bit-rev)=0.7787; direct F=1.0000"
    assert out[2] == "F=0.9330"


@requires_node
def test_bit_reversal_pair_with_a_global_phase_shows_the_phase():
    p = _sv("qiskit", "myqlm", "agree_after_bit_reversal", direct_fidelity=1.0, bit_reversed_fidelity=1.0,
            label_aligned_basis="bit_reversal", label_aligned_fidelity=1.0,
            label_aligned_relative_phase_rad=-1.5707963267948966, phase_tolerance=1e-6)
    p["transform_effect"] = {"global_phase_aligned": True}
    no_field = _sv("qiskit", "myqlm", "agree_after_bit_reversal", bit_reversed_fidelity=1.0,
                   label_aligned_basis="bit_reversal", bit_reversed_relative_phase_rad=1.0, phase_tolerance=1e-6)
    out = call_js(["tables_renderer.js", "run_status.js"],
                  [("pairMetricText", [p]), ("hasPhaseOffset", [p]), ("hasPhaseOffset", [no_field])])
    assert out == ["F(bit-rev)=1.0000 · phase -1.5708 rad", True, True]


@requires_node
def test_measured_lsb_msb_pair_shows_the_label_aligned_js():
    p = _m("qiskit", "cirq", "distinguishable")
    p["agreement"] = "distance_exceeds_threshold"
    p["metrics"].update({"js_divergence": 0.21, "label_aligned_basis": "bit_reversal", "label_aligned_js_divergence": 0.45})
    assert call_js(["tables_renderer.js"], [("pairMetricText", [p])]) == ["JS(bit-rev)=0.4500 nats"]


def _headline(report):
    return call_js(["overview_renderer.js"], [("headlineSentences", [report])])[0]


@requires_node
def test_headline_names_a_common_mode_group_and_not_the_correct_backends():
    sims = ["cirq", "pennylane-default", "pennylane-lightning", "qiskit", "qulacs", "quest"]
    pl = {"pennylane-default", "pennylane-lightning"}
    pairs = [_sv(a, b, "residual_disagreement" if len({a, b} & pl) == 1 else "agree_directly")
             for a, b in combinations(sims, 2)]
    out = _headline(_report(pairs, sims))
    assert out["lines"][1] == "PL Default and PL Lightning agree with each other and differ from every other backend (4)."
    assert out["lines"][2] == "The other 4 backends agree with each other."
    assert sorted(out["model"]["flagged"]) == sorted(pl)
    assert "Qiskit" not in " ".join(out["lines"])


@requires_node
def test_headline_keeps_by_only_pairs_apart():
    sims = ["a", "b", "c", "d"]
    pairs = [_m(x, y, "distinguishable", marginal="marginal_distinguishable", fwer=True) if "d" in (x, y)
             else (_m(x, y, "distinguishable", fwer=False) if {x, y} == {"a", "b"}
                   else _m(x, y, "consistent_within_shot_noise")) for x, y in combinations(sims, 2)]
    report = _report(pairs, sims, n_shots=8200)
    out = _headline(report)
    v = call_js(["backend_verdicts.js"], [("backendVerdicts", [report])])[0]
    by_key = {b["key"]: b for b in v["backends"]}
    assert out["model"]["flagged"] == ["d"]
    assert by_key["a"]["differsByOnly"] == 1 and by_key["a"]["differsWith"] == ["d"]
    assert any(line.startswith("1 further pair is significant under Benjamini–Yekutieli only") and "a × b" in line
               for line in out["lines"])


@requires_node
def test_headline_omits_the_marginal_clause_when_the_test_did_not_run():
    sims = ["a", "b", "c"]
    pairs = [_m(x, y, "inconclusive_low_shots", marginal="not_applicable", marginal_test=False)
             for x, y in combinations(sims, 2)]
    out = _headline(_report(pairs, sims, n_shots=20))
    assert "marginal" not in " ".join(out["lines"])
    tested = [_m(x, y, "inconclusive_low_shots") for x, y in combinations(sims, 2)]
    assert "no single-bit marginal differs" in " ".join(_headline(_report(tested, sims, n_shots=20))["lines"])


@requires_node
def test_multi_run_headline_counts_runs():
    sims = [f"qiskit~opt{lvl}~run1" for lvl in range(3)] + ["cirq~opt0~run1", "cirq~opt1~run1", "qibo~opt0~run1", "qibo~opt1~run1"]
    qibo = {"qibo~opt0~run1", "qibo~opt1~run1"}
    pairs = [_sv(a, b, "residual_disagreement" if len({a, b} & qibo) == 1 else "agree_directly")
             for a, b in combinations(sims, 2)]
    out = _headline(_report(pairs, sims))
    assert out["lines"][0] == "7 of 7 runs on 3 backends returned a result."
    assert out["lines"][1] == "All 2 Qibo runs agree with each other and differ from every other run (5)."
    assert out["lines"][2] == "The other 5 runs agree with each other."


@requires_node
def test_run_label_and_empty_state_count_runs():
    ws = {"source": "editor", "modes": {"statevector": True, "measured": False}, "preprocessing": "on", "list": [],
          "compilers": {}, "common": {"target_simulators": ["qiskit", "cirq"], "runner_config": {"qiskit": [0, 0, 1], "cirq": 0}}}
    keys = ["qiskit~opt0~run1", "qiskit~opt0~run2", "qiskit~opt1~run1", "cirq"]
    out = call_js(["run_plan.js", "runner_key.js"], [
        ("plannedRunKeys", [["qiskit", "cirq"], ws["common"]["runner_config"]]),
        ("runButtonLabel", [ws, 2]),
    ])
    assert out[0] == keys
    assert out[1] == "Run Editor Code · Statevector · 4 runs on 2 backends"
    model = call_js(["empty_state.js"], [("emptyStateModel", [{
        "source": "editor", "circuitName": "", "playlist": [], "modes": {"statevector": True, "measured": False},
        "preprocessing": "on", "compilerCount": 0, "backends": [{"key": k, "name": k} for k in keys],
        "backendsLoaded": True, "examples": []}])])[0]
    assert model["text"].startswith("Run sends it to 2 backends as the 4 runs below,")
    assert len(model["table"]["rows"]) == 4


@requires_node
def test_column_format_is_one_notation_per_column():
    out = call_js(["ranking_renderer.js"], [
        ("columnFormat", [[0.0604, 0.000851, 1.2]]),
        ("columnFormat", [[150.2, 2400.0]]),
        ("columnFormat", [[5e-7, 0.2]]),
        ("fmtColumn", [0.0604, {"sci": False, "decimals": 6}]),
    ])
    assert out[0] == {"sci": False, "decimals": 6}
    assert out[1] == {"sci": False, "decimals": 1}
    assert out[2]["sci"] is True
    assert out[3] == "0.060400"


@requires_node
def test_compile_only_headline_names_the_levels_that_did_not_compile():
    def pane(cid, level, text=None, status="ok", refusal=None):
        return {"kind": "compiled", "compilerId": cid, "compilerName": cid, "level": level, "text": text,
                "status": status, "refusalKind": refusal}
    panes = [pane("staq", 1, "x"), pane("qmap", 1, status="error"), pane("bqskit", 2, status="timeout"),
             pane("synthetiq", 0, status="error", refusal="input")]
    lines = call_js(["summary_renderer.js"], [("compileHeadline", [panes])])[0]
    assert lines[0] == "Compile only: no simulator was run. 1 of 4 compiles returned a circuit."
    assert "Refused (the compiler cannot compile this input correctly): synthetiq level 0." in lines
    assert "Timed out: bqskit level 2." in lines and "Failed: qmap level 1." in lines


@requires_node
def test_compile_reasons_are_given_once_per_reason_and_listed_first():
    reason = ("Not compiled: compile-only services take the unitary part of a circuit, and this "
              "circuit has a mid-circuit measurement, reset or classical control.")

    def pane(cid, level, status="skipped"):
        return {"kind": "compiled", "compilerId": cid, "compilerName": cid, "level": level, "text": None,
                "status": status, "refusalKind": None, "reason": reason if status == "skipped" else "boom"}
    panes = [pane("bqskit", 1), pane("pyzx", 1), pane("qmap", 0), pane("staq", 2, status="timeout")]
    reasons, lines = call_js(["summary_renderer.js"], [("compileReasons", [panes]), ("compileHeadline", [panes])])
    assert reasons[0]["names"] == ["bqskit level 1", "pyzx level 1", "qmap level 0"]
    assert reasons[0]["text"].startswith("not run: compile-only services take the unitary part")
    assert len(reasons) == 2 and reasons[1]["names"] == ["staq level 2"]
    assert lines[-1].endswith("the reasons are listed first under Compile-only services below.")
    ok = [{**pane("staq", 1), "text": "x", "status": "ok", "gateCount": 1}]
    (ok_lines,) = call_js(["summary_renderer.js"], [("compileHeadline", [ok])])
    assert ok_lines[-1] == "The outputs and their passes are in the Circuits tab."


@requires_node
def test_compile_errors_get_compiler_wording():
    msg = "The compiler process was terminated (exit code -9). Server operators can see details in the runner logs."
    out = call_js(["run_status.js"], [("userFacingError", [msg, "compile-only service"]),
                                      ("userFacingError", ["x. Check that its container is running.", "compile-only service"])])
    assert "Server operators" not in out[0] and out[0].endswith("tell the administrator of this server.")
    assert out[1] == "x. The compile-only service may be restarting; try again in a minute."


_GATE_CORPUS = [
    'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[4];\nh q[0];\ncu1(pi/2) q[1],q[0];\nbarrier q;\nswap q[0],q[3];\n',
    'qreg a[2]; qreg b[1]; creg c[2];\ngate g(t) x, y { cx x, y; rz(t) y; }\ng(0.3) a[0], b[0]; // h a[1];\nmeasure a -> c;\nreset a[0];\nif (c==1) x a[1];\n',
    'qreg q[3];\nccx q[0],q[1],q[2]; cx q[0], q[0];\nU(0.1,0.2,0.3) q[ 2 ];\nopaque o q;\nBARRIER q[0];\n',
    '',
]


@requires_node
def test_browser_gate_counter_matches_the_python_counter():
    js = call_js(["qasm_text.js"], [("qasmGateMetrics", [text]) for text in _GATE_CORPUS])
    for text, got in zip(_GATE_CORPUS, js):
        gates, depth = count_qasm_gates_and_depth(text)
        _, multi = count_qasm_gates_by_name(text)
        assert got == {"gateCount": gates, "depth": depth, "multiQubitGateCount": multi}, text


@requires_node
def test_editor_badge_does_not_count_barriers():
    qft = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncu1(pi/2) q[1],q[0];\nbarrier q[0],q[1];\nh q[1];\nbarrier q[0],q[1];\nswap q[0],q[1];\n'
    assert call_js(["config.js"], [("_parseQasmStats", [qft])])[0] == {"qubits": 2, "gates": 4}


@requires_node
def test_planned_text_panes_carry_counted_gate_metrics():
    report = {"input_qasm": "qreg q[2]; h q[0]; barrier q; cx q[0],q[1];",
              "compile_input": {"qasm": "qreg q[2]; h q[0]; cx q[0],q[1];"}}
    panes = call_js(["circuit_panes.js"], [("circuitPanes", [report])])[0]
    assert [(p["kind"], p["gateCount"], p["depth"]) for p in panes] == [("input", 2, 2), ("compile-input", 2, 2)]


def test_publication_timing_table_marks_overlaps_and_unstable_runs():
    headers, rows, _, caption = _tbl_performance(json.loads(json.dumps(_repeated_timing())))
    assert rows[0][0].endswith("≈") and not rows[1][0].endswith("≈")
    status = headers.index("Status")
    assert rows[0][status].endswith("(unstable)") and not rows[1][status].endswith("(unstable)")
    assert "overlaps_next" in caption and "unstable:" in caption


def test_qft_description_states_its_bit_convention():
    desc = json.loads((_ROOT / "algorithm_templates" / "qft.json").read_text())["description"]
    assert "q[0] is the most significant bit" in desc and "controlled phases do not act" in desc


def test_compilation_tooltip_names_the_split_adapters():
    text = (_ROOT / "static" / "js" / "render_helpers.js").read_text()
    line = next(line for line in text.splitlines() if line.strip().startswith('"compilation":'))
    assert "inside the simulation call" not in line
    assert all(name in line for name in ("Qulacs", "QuEST", "qsim", "Qiskit", "cuQuantum"))
