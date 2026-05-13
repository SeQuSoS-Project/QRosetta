import httpx
import asyncio
from config import settings
from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-api")
_RUNNER_SERVICES = settings.get_runner_services()


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
    global_opt = runner_payload.get("optimization_level", 0)
    runner_overrides = runner_payload.get("runner_config", {})
    timeout_float = float(timeout_seconds)

    async def _run_and_track(sim_name, url, local_payload):
        if runner_statuses is not None:
            runner_statuses[sim_name] = "running"
        result = await safe_request(client, url, local_payload, sim_name, timeout_seconds)
        if runner_statuses is not None:
            runner_statuses[sim_name] = "error" if "error" in result else "done"
        return result

    async with httpx.AsyncClient(timeout=timeout_float) as client:
        tasks = []
        for sim_name, url in runner_urls.items():
            if runner_statuses is not None:
                runner_statuses[sim_name] = "queued"
            p_level = runner_overrides.get(sim_name, global_opt)
            runner_info = _RUNNER_SERVICES.get(sim_name, {})
            opt_levels_dict = runner_info.get("optimization_levels", {})
            if opt_levels_dict:
                p_level = min(p_level, max(opt_levels_dict.keys()))
            local_payload = runner_payload.copy()
            local_payload["optimization_level"] = p_level
            logger.info(f"Dispatching job to {sim_name} (Level: {p_level})...")
            tasks.append(_run_and_track(sim_name, url, local_payload))

        results = await asyncio.gather(*tasks)

    return list(results)
