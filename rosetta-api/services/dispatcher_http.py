# HTTP-based dispatcher for quantum runners.

import httpx
import asyncio
from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-api")

async def safe_request(client, url, payload, sim_name, timeout_s):
    try:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        return {
            "simulator": sim_name,
            "error": f"TIMEOUT ({timeout_s}s): The runner took too long. This likely means the circuit is too complex for the allocated resources.",
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0
        }
    except (httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError):
        return {
            "simulator": sim_name,
            "error": f"CRITICAL CRASH: The runner container terminated unexpectedly and severed the connection. This is almost certainly a C++ SIGABRT or an OS-level Out-Of-Memory (OOM) kill. To view the exact verbose error, check the Cloud Run or local Docker console logs for the {sim_name} container.",
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0
        }
    except Exception as e:
        logger.error(f"Unexpected error dispatching to {sim_name}: {e}", exc_info=True)
        return {
            "simulator": sim_name,
            "error": "Unexpected error communicating with runner",
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0
        }

async def dispatch_http_local(runner_urls: dict, runner_payload: dict, timeout_seconds: int, runner_statuses: dict = None) -> list:
    from services.dispatcher import expand_runner_jobs, group_specs_by_phase, build_runner_payload

    specs = expand_runner_jobs(runner_urls, runner_payload)
    phase_groups = group_specs_by_phase(specs)
    timeout_float = float(timeout_seconds)

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
    async with httpx.AsyncClient(timeout=timeout_float) as client:
        for group in phase_groups:
            tasks = []
            for spec in group:
                local_payload = build_runner_payload(runner_payload, spec["opt_level"])
                logger.info(f"Dispatching job to {spec['key']} (Level: {spec['opt_level']}, Phase: {spec['phase']})...")
                tasks.append(_run_and_track(client, spec, local_payload))
            results.extend(await asyncio.gather(*tasks))

    return results
