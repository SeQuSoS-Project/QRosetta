"""Tests for the server-wide run registry and the exclusive dispatch gate."""
import asyncio

from services.run_registry import ExclusiveGate, RunRegistry


def test_overlap_counts_only_other_tokens():
    reg = RunRegistry()
    a, b = object(), object()
    r1 = reg.start(a)
    r2 = reg.start(a)
    r3 = reg.start(b)
    assert reg.finish(r1) == 1
    assert reg.finish(r3) == 2
    assert reg.finish(r2) == 1
    r4 = reg.start(b)
    assert reg.finish(r4) == 0


def test_exclusive_waits_for_shared_and_blocks_new_shared():
    async def scenario():
        gate, order = ExclusiveGate(), []
        await gate.acquire(False)

        async def exclusive():
            await gate.acquire(True)
            order.append("exclusive")
            await asyncio.sleep(0.05)
            await gate.release(True)

        async def late_shared():
            await asyncio.sleep(0.01)
            await gate.acquire(False)
            order.append("late shared")
            await gate.release(False)

        task_x = asyncio.create_task(exclusive())
        task_s = asyncio.create_task(late_shared())
        await asyncio.sleep(0.03)
        assert order == []
        await gate.release(False)
        await asyncio.gather(task_x, task_s)
        return order

    assert asyncio.run(scenario()) == ["exclusive", "late shared"]


def test_exclusive_wait_cap_raises_and_leaves_gate_usable():
    from services.run_registry import ExclusiveWaitTimeout

    async def scenario():
        gate = ExclusiveGate()
        await gate.acquire(False)
        try:
            await gate.acquire(True, max_wait=0.05)
        except ExclusiveWaitTimeout:
            pass
        else:
            raise AssertionError("expected a timeout")
        assert gate.status()["exclusive_waiting"] == 0
        await gate.acquire(False)
        await gate.release(False)
        await gate.release(False)
        await gate.acquire(True, max_wait=0.05)
        await gate.release(True)

    asyncio.run(scenario())


def test_one_exclusive_job_per_client():
    from services.run_registry import claim_exclusive, release_exclusive
    assert claim_exclusive("1.2.3.4", "job-a") is None
    assert claim_exclusive("1.2.3.4", "job-b") == "job-a"
    assert claim_exclusive("5.6.7.8", "job-c") is None
    release_exclusive("job-a")
    release_exclusive("job-c")
    assert claim_exclusive("1.2.3.4", "job-b") is None
    release_exclusive("job-b")
