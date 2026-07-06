# HTTP-based dispatcher for quantum runners.

import time
import httpx
import asyncio
from qrosetta_commons.helpers import get_logger
from config import settings

logger = get_logger("rosetta-api")


def _runner_error(sim_name: str, message: str) -> dict:
    return {
        "simulator": sim_name,
        "error": message,
        "execution_time_sec": 0.0,
        "memory_usage_mb": 0.0,
    }


async def safe_request(client, url, payload, sim_name, timeout_s):
    """Dispatch to one runner and classify failures HONESTLY.

    A dropped connection is reported as what it most likely is given how long it took —
    a runner that dies near the deadline is a timeout/OOM, not asserted to be a specific
    C++ crash. Accurate wording matters: a mislabelled timeout is a mis-triage waiting to
    happen.
    """
    t0 = time.perf_counter()
    try:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        return _runner_error(
            sim_name,
            f"TIMEOUT ({timeout_s}s): the {sim_name} runner did not respond within the time "
            f"budget. The circuit may be too large or deep for the allocated resources — "
            f"reduce the qubit count or raise the timeout.")
    except httpx.ConnectError:
        return _runner_error(
            sim_name,
            f"UNAVAILABLE: could not connect to the {sim_name} runner. Check that its "
            f"container is running.")
    except (httpx.RemoteProtocolError, httpx.ReadError) as e:
        elapsed = time.perf_counter() - t0
        if elapsed >= 0.8 * float(timeout_s):
            return _runner_error(
                sim_name,
                f"RUNNER TERMINATED after ~{elapsed:.0f}s: the {sim_name} worker closed the "
                f"connection near the {timeout_s}s deadline — most likely it exceeded the "
                f"time or memory budget (timeout / OOM kill). Check the {sim_name} container "
                f"logs to confirm.")
        return _runner_error(
            sim_name,
            f"CONNECTION LOST after ~{elapsed:.0f}s to the {sim_name} runner "
            f"({type(e).__name__}). Check the {sim_name} container logs.")
    except httpx.HTTPStatusError as e:
        return _runner_error(
            sim_name, f"HTTP {e.response.status_code} from the {sim_name} runner.")
    except Exception as e:
        logger.error(f"Unexpected error dispatching to {sim_name}: {e}", exc_info=True)
        return _runner_error(
            sim_name,
            f"Unexpected error communicating with the {sim_name} runner: {type(e).__name__}.")

async def dispatch_http_local(runner_urls: dict, runner_payload: dict, timeout_seconds: int, runner_statuses: dict = None) -> list:
    from services.dispatcher import expand_runner_jobs, group_specs_by_phase, build_runner_payload

    specs = expand_runner_jobs(runner_urls, runner_payload)
    phase_groups = group_specs_by_phase(specs)
    # Granular timeouts: a short connect timeout so an unreachable/backed-up runner fails
    # fast. The read budget = the runner's hard-kill budget + headroom, so the runner returns
    # a clean timeout result (it self-terminates at hard_timeout_seconds) before httpx gives up.
    timeout_float = float(timeout_seconds)
    http_timeout = httpx.Timeout(
        timeout_float + float(settings.RUNNER_DEADLINE_BUFFER_SEC),
        connect=float(settings.RUNNER_CONNECT_TIMEOUT_SEC),
    )

    async def _run_and_track(client, spec, local_payload):
        key = spec["key"]
        if runner_statuses is not None:
            runner_statuses[key] = "running"
        result = await safe_request(client, spec["url"], local_payload, key, timeout_seconds)
        result["simulator"] = key
        # Record the effective (clamped, global-or-override-resolved) opt level this
        # runner actually ran at, so the UI/report show ground truth rather than only
        # the per-runner override map.
        result["optimization_level"] = spec["opt_level"]
        if runner_statuses is not None:
            runner_statuses[key] = "error" if "error" in result else "done"
        return result

    if runner_statuses is not None:
        for spec in specs:
            runner_statuses[spec["key"]] = "queued"

    results = []
    async with httpx.AsyncClient(timeout=http_timeout) as client:
        for group in phase_groups:
            tasks = []
            for spec in group:
                local_payload = build_runner_payload(runner_payload, spec["opt_level"])
                # The runner self-terminates at this budget; httpx waits slightly longer.
                local_payload["hard_timeout_seconds"] = int(timeout_seconds)
                logger.info(f"Dispatching job to {spec['key']} (Level: {spec['opt_level']}, Phase: {spec['phase']})...")
                tasks.append(_run_and_track(client, spec, local_payload))
            results.extend(await asyncio.gather(*tasks))

    return results
