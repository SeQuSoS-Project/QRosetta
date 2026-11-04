"""The self-test's pinned answers and plan: the expected file regenerates from the circuits,
its sha256 is committed, the probes are the runners' contract probes, every statevector
circuit keeps a wide margin against the errors it is meant to catch, and the plan pins
every request field."""
import itertools
import json
import re
from pathlib import Path

import numpy as np
import pytest

from qrosetta_commons import contract_probes as cp
from schemas import BatchPayload
from services.selftest import circuits, plan, reference

ROOT = Path(__file__).resolve().parents[3]
MARGIN = 0.9


def test_regenerating_the_expected_answers_reproduces_the_pinned_file():
    pinned = circuits.load_expected()
    fresh = json.loads(circuits.expected_file_text(circuits.compute_expected()))
    assert pinned.keys() == fresh.keys() and pinned["circuits"].keys() == fresh["circuits"].keys()
    for name, entry in fresh["circuits"].items():
        old = pinned["circuits"][name]
        for field, value in entry.items():
            if field == "statevector_lsb":
                np.testing.assert_allclose(np.array(old[field]), np.array(value), rtol=0, atol=1e-15)
            elif field == "p_all_zero":
                assert old[field] == pytest.approx(value, abs=1e-15)
            else:
                assert old[field] == value, (name, field)


def test_the_pinned_file_has_the_committed_sha256():
    assert circuits.expected_file_sha256() == plan.EXPECTED_SHA256


def test_every_circuit_file_is_listed_and_hashed():
    files = {p.stem for p in Path(circuits.CIRCUITS_DIR).glob("*.qasm")}
    assert files == {name for name, *_ in circuits.CIRCUITS}
    import hashlib
    for name, entry in circuits.load_expected()["circuits"].items():
        text = circuits.circuit_text(name)
        assert hashlib.sha256(text.encode()).hexdigest() == entry["qasm_sha256"]


_PROBES = {
    "m_probe_one_hot": (cp.ONE_HOT_MEASURED_QASM, cp.EXPECTED_COUNT_KEY),
    **{f"m_probe_{n}": (cp.QASM_HEADER + cp.CLASSICAL_BIT_PROBES[n][0], cp.CLASSICAL_BIT_PROBES[n][1])
       for n in ("clbit_order", "creg_declaration_order", "unmeasured_clbit_mid_creg",
                 "unmeasured_clbit_first_creg")},
}


def _statements(text):
    return [s.strip() for s in text.split(";") if s.strip()]


@pytest.mark.parametrize("name", sorted(_PROBES))
def test_measured_probes_are_the_contract_probes_with_the_same_keys(name):
    probe_text, probe_keys = _PROBES[name]
    assert _statements(circuits.circuit_text(name)) == _statements(probe_text)
    pinned = circuits.load_expected()["circuits"][name]["counts_key"]
    assert pinned == reference.deterministic_counts_key(circuits.circuit_text(name)) == probe_keys


@pytest.mark.parametrize("name,part", [(n, p) for n, p, *_ in circuits.CIRCUITS])
def test_every_circuit_passes_the_api_checks_of_its_mode(name, part):
    pytest.importorskip("pytket")
    from services.validator import validate_request
    validate_request(circuits.circuit_text(name), mode=part, bypass_limits=False,
                     apply_preprocessing=True, check_reserved_names=True)


def test_circuits_avoid_gates_with_documented_upstream_behaviour():
    documented = {"cu3", "cu1", "csx", "cu", "c3sqrtx", "rc3x", "cp", "crz", "u3", "u"}
    for name, *_ in circuits.CIRCUITS:
        gates = {m.group(1) for m in re.finditer(r"^([a-z][a-z0-9]*)\b", circuits.circuit_text(name), re.M)}
        assert not gates & documented, (name, gates & documented)


def _permuted(state, permutation):
    n = int(np.log2(len(state)))
    return state.reshape([2] * n).transpose(permutation).reshape(-1)


def margins(name: str) -> dict:
    """Fidelity of the expected state with each wrong state the circuit is meant to catch."""
    text = circuits.circuit_text(name)
    circuit = reference.parse_circuit(text)
    n, gates = circuit["n_qubits"], circuit["gates"]
    expected = reference.simulate_gates(n, gates)
    out = {}
    for permutation in itertools.permutations(range(n)):
        if permutation == tuple(range(n)):
            continue
        permuted = _permuted(expected, permutation)
        if np.allclose(permuted, expected, atol=1e-15):
            continue
        out[f"permutation {permutation}"] = reference.fidelity(expected, permuted)
    out["bit reversal"] = reference.fidelity(expected, reference.to_msb(expected))
    for i, (gate, params, qubits) in enumerate(gates):
        if gate == "cx":
            flipped = list(gates)
            flipped[i] = (gate, params, qubits[::-1])
            out[f"cx {i} flipped"] = reference.fidelity(expected, reference.simulate_gates(n, flipped))
        if gate == "rz":
            flipped = list(gates)
            flipped[i] = (gate, (-params[0],), qubits)
            out[f"rz {i} sign"] = reference.fidelity(expected, reference.simulate_gates(n, flipped))
    return out


def test_distinct_amplitude_circuit_margin():
    fidelities = margins("sv_distinct_amplitudes")
    assert len([k for k in fidelities if k.startswith("permutation")]) == 5
    assert {"cx 3 flipped", "cx 4 flipped", "rz 5 sign", "bit reversal"} <= fidelities.keys()
    assert max(fidelities.values()) <= MARGIN, fidelities
    assert max(fidelities.values()) == pytest.approx(0.8740, abs=1e-4)
    assert fidelities["bit reversal"] == pytest.approx(0.5594, abs=1e-4)
    assert fidelities["rz 5 sign"] == pytest.approx(0.7954, abs=1e-4)
    assert max(v for k, v in fidelities.items() if k.startswith("permutation")) == pytest.approx(0.8343, abs=1e-4)
    state = reference.statevector(circuits.circuit_text("sv_distinct_amplitudes"))
    magnitudes = np.round(np.abs(state), 6)
    assert len(set(magnitudes)) == len(state)


def test_one_hot_margin_covers_every_permutation_that_moves_the_set_qubit():
    fidelities = margins("sv_one_hot_idle")
    assert len([k for k in fidelities if k.startswith("permutation")]) == 4
    assert max(fidelities.values()) == 0.0


@pytest.mark.parametrize("name", ["sv_one_hot_idle", "sv_distinct_amplitudes", "sv_ghz_3q"])
def test_complex64_rounding_stays_inside_the_tolerance(name):
    expected = reference.statevector(circuits.circuit_text(name))
    cast = expected.astype(np.complex64).astype(complex)
    assert reference.fidelity(expected, cast) >= 1 - 1e-7
    unnormalised = abs(np.vdot(expected, cast)) ** 2
    assert 1 - unnormalised < 1e-7


def test_dropped_gates_are_caught_too():
    """§3.4 cases where every backend agreed on a wrong state removed a gate (rx(1e308) read
    as rx(0); a reserved gate name read as a barrier)."""
    circuit = reference.parse_circuit(circuits.circuit_text("sv_distinct_amplitudes"))
    n, gates = circuit["n_qubits"], circuit["gates"]
    expected = reference.simulate_gates(n, gates)
    for i in range(len(gates)):
        dropped = reference.simulate_gates(n, gates[:i] + gates[i + 1:])
        assert reference.fidelity(expected, dropped) < 1 - 1e-2


def test_plan_requests_pin_every_field_but_the_backends():
    pytest.importorskip("pytket")
    body = plan.selftest_plan()
    for job in body["jobs"]:
        request = job["request"]
        assert set(request) | {"target_simulators"} == set(BatchPayload.model_fields)
        assert set(job["client_sets"]) == {"target_simulators"}
        BatchPayload(**request, target_simulators=["qiskit"])
        assert request["optimization_level"] == 0 and request["apply_preprocessing"] is True
        assert request["n_shots"] == 8200 and request["seed"] == 20261027
        assert request["thresholds"] == {"fidelity_tolerance": 1e-5, "phase_tolerance": 1e-6,
                                         "norm_tolerance": 1e-4, "js_threshold": 0.01,
                                         "hellinger_threshold": 0.1}
        assert [t["qasm_string"] for t in request["tasks"]] == [
            c["qasm"] for c in body["circuits"] if c["part"] == job["part"]]


def test_plan_does_not_follow_server_defaults(monkeypatch):
    from config import settings
    before = plan.part_request("measured")
    monkeypatch.setattr(settings, "DEFAULT_SHOTS", 100)
    monkeypatch.setattr(settings, "DEFAULT_TIMEOUT_SEC", 11)
    assert plan.part_request("measured") == before


def test_plan_expected_forms_follow_the_declared_orders():
    body = plan.selftest_plan()
    one_hot = next(c for c in body["circuits"] if c["name"] == "sv_one_hot_idle")["expected"]["statevector"]
    assert np.argmax([abs(complex(*a)) for a in one_hot["lsb"]]) == cp.EXPECTED_STATEVECTOR_INDEX["lsb"]
    assert np.argmax([abs(complex(*a)) for a in one_hot["msb"]]) == cp.EXPECTED_STATEVECTOR_INDEX["msb"]
    probe = next(c for c in body["circuits"] if c["name"] == "m_probe_one_hot")["expected"]["counts"]
    assert probe == {"lsb": {"001": 8200}, "msb": {"100": 8200}}
    assert body["tolerances"]["ghz_max_deviation"] == pytest.approx(0.0331, abs=1e-4)
    assert body["expected_sha256"] == plan.EXPECTED_SHA256


def test_plan_names_the_gates_it_leaves_untested():
    body = plan.selftest_plan()
    used = set()
    for c in body["circuits"]:
        for line in c["qasm"].splitlines():
            word = re.match(r"\s*([a-z][a-z0-9_]*)", line)
            if word and word.group(1) not in {"openqasm", "include", "qreg", "creg", "barrier"}:
                used.add(word.group(1))
    assert used <= {"x", "h", "ry", "rz", "cx", "measure"}, used
    assert body["not_tested"].startswith("gates other than x, h, ry, rz and cx")
    assert "upstream" not in body["not_tested"]


def test_runner_limits_match_the_compose_file():
    yaml = pytest.importorskip("yaml")
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    from config import settings
    hosts = {svc["base_url"].split("//")[1].split(":")[0]
             for svc in settings.get_runner_services().values() if svc.get("enabled", True)}
    for name, service in compose["services"].items():
        if name not in hosts:
            continue
        limits = service["deploy"]["resources"]["limits"]
        assert float(limits["cpus"]) == plan.RUNNER_CPU_QUOTA_CORES, name
        assert limits["memory"] == f"{plan.RUNNER_MEMORY_LIMIT_MIB // 1024}G", name


def test_handshake_lists_the_selftest_and_summary_features():
    from services.server_info import FEATURES
    assert FEATURES["selftest"] == 1 and FEATURES["summary"] == 1
