"""helpers.run_self_test and the provenance fields every runner result carries."""
import hashlib
import io
import re
from pathlib import Path

import pytest

pytest.importorskip("pytket")

import qrosetta_commons
from qrosetta_commons import helpers
from tests.unit import _selftest_fixture as fx


def _self_test(process_run, process_run_measured, **kw):
    out = io.StringIO()
    failed = helpers.run_self_test(process_run, process_run_measured, out=out, **kw)
    return failed, out.getvalue()


def test_a_correct_runner_passes_every_probe():
    failed, text = _self_test(fx.process_run, fx.process_run_measured,
                              qubit_ordering_statevector="msb", qubit_ordering_counts="msb")
    assert failed == 0, text
    assert "PASS seed_reproducibility" in text and "PASS counts_mid_circuit" in text


def test_a_runner_ignoring_its_seed_fails_the_seed_probe():
    failed, text = _self_test(fx.process_run, fx.process_run_measured_ignoring_seed)
    assert failed == 1 and "FAIL seed_reproducibility" in text, text


def test_a_mislabelled_counts_key_fails_the_bit_order_probes():
    failed, text = _self_test(fx.process_run, fx.process_run_measured_wrong_label)
    assert "FAIL counts_one_hot" in text and "FAIL counts_clbit_order" in text, text
    assert failed >= 2


def test_a_declared_ordering_that_differs_from_the_result_fails():
    failed, text = _self_test(fx.process_run, fx.process_run_measured,
                              qubit_ordering_statevector="lsb")
    assert "FAIL statevector_one_hot" in text and "runner declares 'lsb'" in text, text


def test_a_runner_dropping_the_rest_of_a_barrier_line_fails():
    failed, text = _self_test(fx.process_run_dropping_barrier_lines, fx.process_run_measured)
    assert "FAIL statevector_barrier_then_gate_on_one_line" in text, text
    assert "PASS statevector_barrier_only" in text, text


def test_no_runner_or_shared_helper_filters_qasm_lines_by_barrier():
    root = Path(__file__).resolve().parents[3]
    pattern = re.compile(r"startswith\(\s*['\"]barrier")
    sources = list((root / "runners").glob("*/main.py")) + list(
        (root / "shared" / "qrosetta_commons").glob("*.py"))
    assert sources
    offenders = [str(p) for p in sources if pattern.search(p.read_text())]
    assert not offenders, offenders


def test_cli_self_test_exits_non_zero_on_failure(monkeypatch):
    monkeypatch.setattr("sys.argv", ["main.py", "--self-test"])
    with pytest.raises(SystemExit) as exit_info:
        helpers.run_cli_main(None, fx.process_run, fx.process_run_measured_ignoring_seed, "fx")
    assert exit_info.value.code == 1


def _expected_code_sha() -> str:
    digest = hashlib.sha256(Path(fx.__file__).read_bytes())
    root = Path(qrosetta_commons.__file__).resolve().parent
    for path in sorted(root.rglob("*.py"), key=lambda p: p.relative_to(root).as_posix()):
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_results_carry_code_hash_device_and_declared_sdk_versions():
    result = fx.process_run({"circuit_data": fx_qasm(), "optimization_level": 0})
    assert result.get("error") is None, result.get("error")
    assert result["runner_code_sha256"] == _expected_code_sha()
    assert result["device"] == "CPU"
    assert set(result["sdk_versions"]) >= {"pytket", "numpy"}
    assert all(v != helpers.NOT_INSTALLED for v in result["sdk_versions"].values())


def test_error_results_carry_the_code_hash_and_no_device():
    result = fx.process_run({"circuit_data": "OPENQASM 2.0;\nqreg q[1];\nfoo q[0];\n"})
    assert result["error"] and result["device"] is None
    assert result["runner_code_sha256"] == _expected_code_sha()


def test_an_undeclared_distribution_is_reported_as_not_installed(monkeypatch):
    monkeypatch.setattr(helpers, "_DECLARED_SDK_PACKAGES", ["numpy"])
    helpers.declare_sdk_packages("no-such-distribution-xyz", "numpy")
    versions = helpers.get_sdk_versions()
    assert list(versions) == ["numpy", "no-such-distribution-xyz"]
    assert versions["no-such-distribution-xyz"] == helpers.NOT_INSTALLED


def fx_qasm():
    return 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'
