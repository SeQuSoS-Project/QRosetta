"""concurrent_runs counts every run dispatched in a wave in flight beside a run's own wave,
including the other group of a measured run; sequential waves do not count each other."""

from datetime import datetime, timedelta, timezone

from services.dispatcher import annotate_overlaps, record_dispatch_waves

T0 = datetime(2026, 10, 7, tzinfo=timezone.utc)


def _r(key, phase, start, end):
    def at(s):
        return (T0 + timedelta(seconds=s)).isoformat(timespec="milliseconds")
    return {"simulator": key, "dispatch_phase": phase, "dispatched_at": at(start),
            "completed_at": at(end), "concurrent_runs": 99}


def test_two_groups_dispatched_together_count_each_other():
    sampled = record_dispatch_waves([_r("quest", 1, 0, 5), _r("pyquil", 1, 0, 4)])
    native = record_dispatch_waves([_r("qiskit", 1, 0.01, 3), _r("cirq", 1, 0.01, 6), _r("qsim", 1, 0.01, 2)])
    annotate_overlaps(sampled + native)
    assert [r["concurrent_runs"] for r in sampled + native] == [5] * 5


def test_one_dispatch_keeps_its_phase_count():
    results = record_dispatch_waves([_r("a", 1, 0, 2), _r("b", 1, 0, 3), _r("c", 2, 3, 4)])
    annotate_overlaps(results)
    assert [r["concurrent_runs"] for r in results] == [2, 2, 1]
    assert results[0]["dispatch_wave"] is results[1]["dispatch_wave"]
    assert results[0]["dispatch_wave"]["runs"] == 2


def test_sequential_groups_do_not_count_each_other():
    first = record_dispatch_waves([_r("quest", 1, 0, 2)])
    second = record_dispatch_waves([_r("qiskit", 1, 2, 4)])
    annotate_overlaps(first + second)
    assert [r["concurrent_runs"] for r in first + second] == [1, 1]


def test_staggered_phases_of_two_groups():
    sampled = record_dispatch_waves([_r("quest", 1, 0, 10), _r("pyquil", 2, 10, 12)])
    native = record_dispatch_waves([_r("qiskit", 1, 0, 3), _r("cirq", 2, 3, 5), _r("qsim", 2, 3, 6)])
    annotate_overlaps(sampled + native)
    by_key = {r["simulator"]: r["concurrent_runs"] for r in sampled + native}
    assert by_key == {"quest": 4, "pyquil": 1, "qiskit": 2, "cirq": 3, "qsim": 3}
