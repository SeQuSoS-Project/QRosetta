"""timing_repeats: one warm-up, then N timed runs; reported times are medians, output and
memory come from the first timed run, and the field travels API payload -> runner payload."""
import pytest

from qrosetta_commons.helpers import run_with_uniform_measurement, timing_repeats_of
from qrosetta_commons.models import CircuitPayload, MeasuredCircuitPayload

_SIM = {1: 9.0, 2: 5.0, 3: 1.0, 4: 2.0}


def _processor():
    calls = []

    def process(payload):
        calls.append(payload.get("seed"))
        n = len(calls)
        return {"simulator": "t", "counts": {"0": n}, "memory_usage_mb": float(n),
                "compilation_time_sec": 0.1 * n, "simulation_time_sec": _SIM[n],
                "simulation_cpu_time_sec": _SIM[n] / 2,
                "execution_time_sec": 0.1 * n + _SIM[n]}
    return process, calls


def test_three_repeats_after_one_warm_up():
    process, calls = _processor()
    r = run_with_uniform_measurement(process, {"timing_repeats": 3, "seed": 11})
    assert calls == [11, 11, 11, 11]
    assert r["counts"] == {"0": 2} and r["memory_usage_mb"] == 2.0
    assert r["compilation_time_samples"] == pytest.approx([0.2, 0.3, 0.4])
    assert r["simulation_time_samples"] == [5.0, 1.0, 2.0]
    assert r["simulation_time_sec"] == 2.0 and r["simulation_time_sec_median"] == 2.0
    assert r["simulation_time_sec_mean"] == pytest.approx(8.0 / 3)
    assert r["simulation_time_sec_stdev"] > 0
    assert r["compilation_time_sec"] == pytest.approx(0.3)
    assert r["execution_time_sec"] == pytest.approx(0.3 + 2.0)
    assert r["simulation_cpu_time_sec"] == 1.0
    assert r["timing_repeats"] == 3 and r["timing_statistic"] == "median"


def test_single_repeat_has_no_stdev():
    process, calls = _processor()
    r = run_with_uniform_measurement(process, {})
    assert len(calls) == 2
    assert r["simulation_time_samples"] == [5.0]
    assert r["simulation_time_sec_stdev"] is None
    assert r["timing_repeats"] == 1


def test_failing_repeat_makes_the_result_an_error():
    calls = []

    def process(payload):
        calls.append(1)
        if len(calls) == 3:
            return {"simulator": "t", "error": "flaky"}
        return {"simulator": "t", "counts": {"0": 1}, "compilation_time_sec": 0.1,
                "simulation_time_sec": 0.1, "execution_time_sec": 0.2}

    r = run_with_uniform_measurement(process, {"timing_repeats": 4})
    assert r["error"] == "flaky"
    assert r["failed_timing_repeat"] == 2
    assert r["simulation_time_sec"] is None
    assert len(calls) == 3


@pytest.mark.parametrize("value,expected", [(None, 1), (0, 1), (3, 3), (99, 10), ("x", 1)])
def test_timing_repeats_of_bounds(value, expected):
    assert timing_repeats_of({"timing_repeats": value}) == expected


def test_runner_models_accept_timing_repeats():
    assert CircuitPayload(circuit_data="x", timing_repeats=4).model_dump()["timing_repeats"] == 4
    assert MeasuredCircuitPayload(circuit_data="x", n_shots=1).timing_repeats == 1
    with pytest.raises(ValueError):
        CircuitPayload(circuit_data="x", timing_repeats=11)


def test_api_payload_forwards_timing_repeats():
    from services.dispatcher import build_runner_payload
    sent = build_runner_payload({"circuit_data": "x", "timing_repeats": 5, "runner_config": {}},
                                {"key": "qiskit", "opt_level": 0})
    assert sent["timing_repeats"] == 5
