"""The Qrisp adapter's multi_measure wrapper orders outcomes exactly as the Python-sort version it
replaced (runners/qrisp-runner/main.py), for every outcome type Qrisp returns: an int64 array
below 63 measured qubits, a list of Python ints from 63 on. Runs without Qrisp installed."""

import importlib.util
import random
import sys
import types
from pathlib import Path

import numpy as np
import pytest

_MAIN = Path(__file__).resolve().parents[3] / "runners" / "qrisp-runner" / "main.py"

pytestmark = pytest.mark.skipif(not _MAIN.exists(), reason="runner sources not present in this checkout")


@pytest.fixture(scope="module")
def adapter():
    from qrosetta_commons import helpers
    declared = list(helpers._DECLARED_SDK_PACKAGES)
    spec = importlib.util.spec_from_file_location("qrisp_runner_main_under_test", _MAIN)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        helpers._DECLARED_SDK_PACKAGES[:] = declared
    return module


def _previous_wrapper_output(outcomes, probabilities):
    order = sorted(range(len(outcomes)), key=lambda i: int(outcomes[i]))
    if isinstance(outcomes, np.ndarray):
        outcomes = outcomes[order]
    else:
        outcomes = [outcomes[i] for i in order]
    return outcomes, np.asarray(probabilities)[order]


def _cases():
    rng = random.Random(20261105)
    cases = [np.zeros(0, dtype=np.int64), [], np.array([5], dtype=np.int64)]
    for _ in range(100):
        n = rng.randint(1, 2000)
        span = rng.choice([n, n + 1, 2 * n, 4 * n + 1023, 4 * n + 1024, 10 * n])
        distinct = rng.sample(range(span), n)
        cases.append(np.array(distinct, dtype=np.int64))
        cases.append(np.array(distinct, dtype=np.uint64))
        cases.append(np.array([v - rng.randint(0, 2) for v in distinct], dtype=np.int64))
        with_repeat = distinct + [distinct[rng.randrange(n)]]
        rng.shuffle(with_repeat)
        cases.append(np.array(with_repeat, dtype=np.int64))
    for _ in range(200):
        n = rng.randint(1, 300)
        high = rng.choice([2, 7, 1 << 10, 1 << 24, (1 << 62)])
        values = [rng.randrange(high) for _ in range(n)]
        cases.append(np.array(values, dtype=np.int64))
        cases.append(np.array(values, dtype=np.uint64))
        cases.append(np.array(values, dtype=np.int32) if high <= (1 << 24) else np.array(values, dtype=np.int64))
        cases.append(list(values))
        cases.append([v + (1 << 63) + rng.randrange(1 << 70) for v in values])
        cases.append(np.array(values, dtype=object))
    return cases


def test_outcome_order_equals_the_python_sort(adapter):
    for outcomes in _cases():
        expected = sorted(range(len(outcomes)), key=lambda i: int(outcomes[i]))
        assert [int(i) for i in adapter._outcome_order(outcomes)] == expected


def test_distinct_outcomes_are_scattered_without_a_sort(adapter, monkeypatch):
    def no_sort(*args, **kwargs):
        raise AssertionError("argsort called")

    monkeypatch.setattr(np, "argsort", no_sort)
    outcomes = np.random.default_rng(1).permutation(1 << 12).astype(np.int64)
    order = adapter._outcome_order(outcomes)
    assert isinstance(order, np.ndarray)
    assert order.tolist() == sorted(range(len(outcomes)), key=lambda i: int(outcomes[i]))


def test_repeated_sparse_or_negative_outcomes_fall_back_to_a_stable_argsort(adapter, monkeypatch):
    calls = []
    argsort = np.argsort

    def counted(*args, **kwargs):
        calls.append(kwargs.get("kind"))
        return argsort(*args, **kwargs)

    monkeypatch.setattr(np, "argsort", counted)
    for values in ([3, 1, 2, 1], [0, 1 << 20], [2, -1, 0]):
        outcomes = np.array(values, dtype=np.int64)
        order = adapter._outcome_order(outcomes)
        assert order.tolist() == sorted(range(len(values)), key=lambda i: values[i])
    assert calls == ["stable", "stable", "stable"]


def test_wrapped_multi_measure_returns_what_the_previous_wrapper_returned(adapter, monkeypatch):
    replies = []

    class QuantumState:
        def multi_measure(self, mes_qubits, return_res_states=True):
            return replies.pop(0)

    fake = types.ModuleType("qrisp.simulator.quantum_state")
    fake.QuantumState = QuantumState
    for name in ("qrisp", "qrisp.simulator"):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.setitem(sys.modules, "qrisp.simulator.quantum_state", fake)
    adapter._canonical_multi_measure()
    adapter._canonical_multi_measure()
    assert QuantumState.multi_measure._qrosetta_sorted

    rng = np.random.default_rng(20261105)
    for outcomes in _cases():
        probabilities = rng.random(len(outcomes))
        replies.append((outcomes, list(probabilities)))
        got_outcomes, got_probabilities = QuantumState().multi_measure([0], return_res_states=False)
        want_outcomes, want_probabilities = _previous_wrapper_output(outcomes, list(probabilities))
        assert type(got_outcomes) is type(want_outcomes)
        if isinstance(want_outcomes, np.ndarray):
            assert got_outcomes.dtype == want_outcomes.dtype
            assert np.array_equal(got_outcomes, want_outcomes)
        else:
            assert got_outcomes == want_outcomes
        assert got_probabilities.dtype == want_probabilities.dtype
        assert got_probabilities.tobytes() == want_probabilities.tobytes()

    replies.append(("states",))
    assert QuantumState().multi_measure([0]) == ("states",)
