"""HTTP dispatcher for runners running as long-lived Docker Compose services."""

from services import host_load
from services.run_registry import DISPATCH_TOKEN, REGISTRY
import time
import httpx
import asyncio
from qrosetta_commons.helpers import get_logger, unmeasured_metrics
from config import settings

logger = get_logger("rosetta-api")

LOCAL_RUNNER_IMAGE = "not recorded (HTTP dispatch to a Compose service exposes no image id)"


def _runner_error(sim_name: str, message: str, dispatch_status: str = "error") -> dict:
    return {
        "simulator": sim_name,
        "error": message,
        "dispatch_status": dispatch_status,
        **unmeasured_metrics(),
        "queue_wait_sec": None,
    }


def _stopped_by_user(sim_name: str, message: str, dispatch_status: str = "error") -> dict:
    result = _runner_error(sim_name, message, dispatch_status)
    result["stopped_by_user"] = True
    return result


async def safe_request(client, url, payload, sim_name, timeout_s, http_timeout=None):
    """Dispatch to one runner and classify transport failures.

    Failures carry ``dispatch_status``: ``timeout`` when httpx's read budget expires,
    ``offline`` when the runner cannot be reached, ``error`` otherwise. A dropped
    connection is reported with status ``error``; its message names the possible causes
    unless a stop notice (``services.host_load``) covers the service, which records
    ``stopped_by_user``.
    """
    kind = "compiler" if str(url).rstrip("/").endswith("/compile") else "runner"
    t0 = time.perf_counter()
    try:
        if http_timeout is None:
            response = await client.post(url, json=payload)
        else:
            response = await client.post(url, json=payload, timeout=http_timeout)
        response.raise_for_status()
        return response.json()
    except (httpx.ConnectError, httpx.ConnectTimeout):
        if host_load.stopped_by_user(sim_name):
            return _stopped_by_user(sim_name, (
                f"STOPPED BY USER: the {sim_name} {kind} was being stopped on this host (qrosetta stop "
                f"or remove) and could not be reached; the run did not start."), "offline")
        return _runner_error(
            sim_name,
            f"UNAVAILABLE: the {sim_name} {kind} could not be reached. Server operators can "
            f"check whether its service is running.", "offline")
    except httpx.TimeoutException:
        return _runner_error(
            sim_name,
            f"TIMEOUT ({timeout_s}s): the {sim_name} {kind} did not respond within its queue "
            f"and run budget. The circuit may be too large or deep for the allocated "
            f"resources; reduce the qubit count or raise the timeout.", "timeout")
    except (httpx.RemoteProtocolError, httpx.ReadError) as e:
        elapsed = time.perf_counter() - t0
        if host_load.stopped_by_user(sim_name):
            return _stopped_by_user(sim_name, (
                f"STOPPED BY USER after ~{elapsed:.0f}s: the {sim_name} {kind} was stopped on this "
                f"host (qrosetta stop --force or remove) while this run was in flight; its result "
                f"was lost."))
        near_deadline = elapsed >= 0.8 * float(timeout_s)
        causes = (f"The {kind} process or its container ended, or the network connection failed; "
                  f"this server did not record which. Possible causes: the container was stopped, "
                  f"the process crashed or ran out of memory, "
                  f"{'a time limit ended it, ' if near_deadline else ''}or the network failed. "
                  f"Server operators can see details in the {kind} logs.")
        if near_deadline:
            return _runner_error(
                sim_name,
                f"{kind.upper()} TERMINATED after ~{elapsed:.0f}s: the {sim_name} {kind} closed the "
                f"connection near the {timeout_s}s deadline without returning a result. {causes}")
        return _runner_error(
            sim_name,
            f"CONNECTION LOST after ~{elapsed:.0f}s to the {sim_name} {kind} "
            f"({type(e).__name__}) before it returned a result. {causes}")
    except httpx.HTTPStatusError as e:
        return _runner_error(
            sim_name, f"HTTP {e.response.status_code} from the {sim_name} {kind}.")
    except Exception as e:
        logger.error(f"Unexpected error dispatching to {sim_name}: {e}", exc_info=True)
        return _runner_error(
            sim_name,
            f"Unexpected error communicating with the {sim_name} {kind}: {type(e).__name__}.")


async def dispatch_http_local(runner_urls: dict, runner_payload: dict, timeout_seconds: int, runner_statuses: dict = None) -> list:
    """Run every job over HTTP, phase by phase, and return the annotated results.

    Each runner executes one run at a time and queues the rest. A job may wait in that
    queue for ``queue_wait_budget()`` seconds (RUNNER_QUEUE_MAX_WAIT_SEC, sent as
    ``max_queue_wait_seconds``); its hard-kill budget ``timeout_seconds`` starts once it
    leaves the queue. The API's read timeout is queue cap + timeout +
    RUNNER_DEADLINE_BUFFER_SEC, so the runner reports a queue or run timeout before the API
    gives up. The job runs in a background task that the browser polls, so no gateway
    timeout applies to this wait. The connect timeout is short so an unreachable runner
    fails fast.
    """
    from services.dispatcher import (
        expand_runner_jobs, group_specs_by_phase, build_runner_payload, annotate_result,
        utc_now_iso, queue_wait_budget,
    )

    specs = expand_runner_jobs(runner_urls, runner_payload)
    phase_groups = group_specs_by_phase(specs)
    token = DISPATCH_TOKEN.get() or object()

    def _http_timeout(queue_budget):
        return httpx.Timeout(
            float(queue_budget) + float(timeout_seconds) + float(settings.RUNNER_DEADLINE_BUFFER_SEC),
            connect=float(settings.RUNNER_CONNECT_TIMEOUT_SEC),
        )

    async def _run_and_track(client, spec, local_payload):
        key = spec["key"]
        if runner_statuses is not None:
            runner_statuses[key] = "running"
        dispatched_at = utc_now_iso()
        run_id = REGISTRY.start(token)
        try:
            result = await safe_request(client, spec["url"], local_payload, key, timeout_seconds,
                                        _http_timeout(local_payload["max_queue_wait_seconds"]))
        finally:
            overlaps = REGISTRY.finish_counts(run_id)
        result["server_overlapping_runs"] = overlaps["runs"]
        result["server_overlapping_host_load"] = overlaps["host_load"]
        annotate_result(result, spec, local_payload, dispatched_at,
                        dispatch_status=result.pop("dispatch_status", None),
                        runner_image=LOCAL_RUNNER_IMAGE)
        if runner_statuses is not None:
            runner_statuses[key] = {"ok": "done", "timeout": "timeout", "offline": "offline"}.get(
                result.get("dispatch_status"), "error")
        return result

    if runner_statuses is not None:
        for spec in specs:
            runner_statuses[spec["key"]] = "queued"

    results = []
    async with httpx.AsyncClient(timeout=_http_timeout(0)) as client:
        for group in phase_groups:
            tasks = []
            for spec in group:
                local_payload = build_runner_payload(runner_payload, spec)
                local_payload["hard_timeout_seconds"] = int(timeout_seconds)
                local_payload["max_queue_wait_seconds"] = queue_wait_budget()
                logger.info(f"Dispatching job to {spec['key']} (Level: {spec['opt_level']}, Phase: {spec['phase']})...")
                tasks.append(_run_and_track(client, spec, local_payload))
            results.extend(await asyncio.gather(*tasks))

    return results
