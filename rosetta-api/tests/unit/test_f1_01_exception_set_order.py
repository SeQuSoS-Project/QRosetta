"""F1-01: an exception raised in the preparation worker reaches the caller with its own type when
its message lists a set, whatever order the set lists its items in after unpickling. F1-02: one
whose message cannot be built without an attribute that does not pickle is a PreparationFailed
naming it, and the worker keeps running."""
import asyncio
import pickle

import pytest

from services import job_store, prep_worker
from tests.unit import prep_probes


@pytest.fixture(autouse=True)
def fresh_worker(tmp_path, monkeypatch):
    monkeypatch.setattr(job_store, "SPILL_DIR", str(tmp_path / "spill"))
    yield
    prep_worker.stop()


def _raised(func):
    try:
        func()
    except Exception as exc:
        return exc
    raise AssertionError(f"{func.__name__} returned")


def _outcome(func):
    try:
        asyncio.run(prep_worker.call(func))
    except Exception as exc:
        return type(exc), str(exc)
    return "returned", None


def test_the_probe_set_lists_its_items_in_another_order_once_pickled():
    items = prep_probes.reordered_set()
    assert list(items) == [3, 17]
    assert list(pickle.loads(pickle.dumps(items))) == [17, 3]


@pytest.mark.parametrize("probe,cls", [
    (prep_probes.raise_listing_a_set, prep_probes.ListsASet),
    (prep_probes.raise_listing_a_set_beside_a_parser, prep_probes.ListsASet),
    (prep_probes.raise_a_set_argument, ValueError),
])
def test_f1_01_an_exception_listing_a_set_keeps_its_type(probe, cls):
    exc = _raised(probe)
    assert type(pickle.loads(pickle.dumps(prep_worker._portable(exc)))) is cls
    kind, message = _outcome(probe)
    assert kind is cls
    assert message in (str(exc), str(exc).replace("3, 17", "17, 3"))


def test_f1_02_an_exception_whose_message_needs_a_dropped_attribute_is_a_preparation_failure():
    pid = asyncio.run(prep_worker.call(prep_probes.pid))
    assert _outcome(prep_probes.raise_needing_its_parser) == (
        prep_worker.PreparationFailed, "NeedsItsParser: parsed X")
    assert prep_worker.worker_pid() == pid
