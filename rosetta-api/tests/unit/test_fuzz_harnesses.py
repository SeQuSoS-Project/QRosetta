"""The fuzz harnesses in scripts/fuzz run for a few seconds each on their seed inputs, so they
keep working without the long runs, and every saved fuzz finding replays within the
validator's oracle under every request option."""
import random
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("pytket")

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts" / "fuzz"
sys.path.insert(0, str(SCRIPTS))

import fuzz_targets  # noqa: E402
from hypothesis import HealthCheck, given, settings, strategies as st  # noqa: E402

QUICK = settings(max_examples=60, deadline=None, database=None, derandomize=True,
                 suppress_health_check=list(HealthCheck))
TOKENS = [b"OPENQASM 2.0;", b"qreg q[2];", b"creg c[2];", b"gate g(t) a { rz(t) a; }", b"\n",
          b";", b"{", b"}", b"(", b")", b"[", b"]", b",", b"->", b"//", b"/*", b"if(c==1)",
          b"measure q -> c;", b"barrier q;", b"reset q[0];", b"pi^pi", b"1e309", b"\xe2\x80\xae",
          b"\x00", b"q[99999999999999999999999999999999]", b"sin(", b"cx q[0], q[0];"]
SEEDS = fuzz_targets.seed_corpus(max_bytes=4096)
ALL_OPTIONS = [
    {"mode": mode, "apply_preprocessing": pre, "statevector": sv and mode == "statevector",
     "bypass_limits": bypass, "check_reserved_names": reserved}
    for mode in fuzz_targets.MODES for pre in (True, False) for sv in (True, False)
    for bypass in (False, True) for reserved in (True, False)
    if not (sv and mode != "statevector")
]


@st.composite
def mutated_seeds(draw):
    data = bytearray(draw(st.sampled_from(SEEDS)))
    for _ in range(draw(st.integers(1, 6))):
        pos = draw(st.integers(0, len(data)))
        kind = draw(st.integers(0, 3))
        if kind == 0:
            data[pos:pos] = draw(st.sampled_from(TOKENS))
        elif kind == 1:
            data[pos:pos + draw(st.integers(1, 40))] = b""
        elif kind == 2:
            data[pos:pos] = data[pos:pos + draw(st.integers(1, 200))] * draw(st.integers(1, 50))
        else:
            data[pos:pos + 1] = bytes([draw(st.integers(0, 255))])
    return bytes(data)


def test_seed_corpus_is_the_bundled_circuits():
    assert len(fuzz_targets.seed_files()) >= 328
    assert len(SEEDS) > 200


@QUICK
@given(mutated_seeds())
def test_validator_harness_quick(data):
    fuzz_targets.validator_oracle(data)


def test_validator_harness_measures_memory_on_a_seed():
    assert fuzz_targets.validator_oracle(SEEDS[0], measure_memory=True) in (
        "accepted", "refused 400", "refused 413")


def test_atheris_entry_point_runs_the_same_oracle():
    source = (SCRIPTS / "validator_atheris.py").read_text()
    assert "fuzz_targets.validator_oracle(data)" in source
    assert "instrument_imports" in source


def _corpus_files():
    return sorted((fuzz_targets.CORPUS_DIR / "validator").glob("*.qasm"))


def test_fuzz_corpus_is_not_empty():
    assert _corpus_files()


@pytest.mark.parametrize("path", _corpus_files(), ids=lambda p: p.name)
def test_saved_finding_replays_under_every_option(path):
    data = path.read_bytes()
    for options in ALL_OPTIONS:
        fuzz_targets.validator_oracle(data, flags=options)


@QUICK
@given(st.data())
def test_grammar_harness_quick(data):
    from qasm_grammar import programs
    program = data.draw(programs(max_qregs=2, max_size=2, max_gates=2, max_statements=5))
    qiskit = True
    try:
        import qiskit.qasm2  # noqa: F401
    except ImportError:
        qiskit = False
    fuzz_targets.grammar_oracle(program, qiskit=qiskit)


def test_report_harness_quick(tmp_path, monkeypatch):
    import report_fuzz
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    stats = report_fuzz.run(4, tmp_path / "findings", seed=1)
    assert stats["requests"] >= 5
    assert not list((tmp_path / "findings").glob("*.txt"))


def test_redos_inventory_covers_the_validator_patterns():
    import redos
    entries = redos.inventory()
    files = {e["file"] for e in entries}
    assert "rosetta-api/services/validator.py" in files
    assert "rosetta-api/services/qasm_structure.py" in files
    assert len(entries) >= 120


def test_redos_quick_on_the_validator_patterns():
    import redos
    entries = [e for e in redos.inventory()
               if e["file"] in ("rosetta-api/services/validator.py",
                                "rosetta-api/services/qasm_structure.py")]
    rng = random.Random(0)
    start = time.perf_counter()
    for entry in rng.sample(entries, k=min(8, len(entries))):
        worst = redos._check_pattern(entry, size=64_000, kill_sec=5.0)
        assert worst["sec"] < 0.5, (entry["pattern"], worst)
    assert time.perf_counter() - start < 120
