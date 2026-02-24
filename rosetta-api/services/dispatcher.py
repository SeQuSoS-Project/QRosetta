import httpx
import asyncio
from config import settings
from qrosetta_commons.helpers import get_logger

logger = get_logger("rosetta-api")

# --- CONFIGURATION (8 Runners, 2 Categories) ---
RUNNER_SERVICES = settings.get_runner_services()

# --- DYNAMIC URL BUILDERS (2 Groups) ---
STATEVECTOR_RUNNER_URLS = {
    name: f"{config['base_url']}/run" for name, config in RUNNER_SERVICES.items() 
    if "statevector" in config["capabilities"]
}
# Group 1: Native samplers that get MODIFIED QASM
NATIVE_SAMPLING_URLS = {
    name: f"{config['base_url']}/run_measured" for name, config in RUNNER_SERVICES.items()
    if "measured_native" in config["capabilities"]
}
# Group 2: Statevector samplers that get ORIGINAL QASM
SAMPLED_SV_URLS = {
    name: f"{config['base_url']}/run_measured" for name, config in RUNNER_SERVICES.items()
    if "measured_sampled" in config["capabilities"]
}


# --- MODULAR DISPATCH LOGIC ---

async def safe_request(client, url, payload, sim_name, timeout_s):
    """
    Wraps the HTTP request to handle crashes/timeouts gracefully.
    Returns the JSON response OR a fallback error dict.
    DOES NOT RAISE EXCEPTIONS.
    """
    try:
        response = await client.post(url, json=payload)
        response.raise_for_status() # Raise for 4xx/5xx
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
        return {
            "simulator": sim_name,
            "error": f"Unexpected Error: {str(e)}",
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0
        }


# --- MODULAR DISPATCH LOGIC ---
async def dispatch_to_runners(runner_urls: dict, runner_payload: dict, timeout_seconds: int = settings.RUNNER_TIMEOUT_SEC) -> list:
    """ runner_payload can contain 'optimization_level' (global) and 'runner_config' (overrides) """
    global_opt = runner_payload.get("optimization_level", 0)
    runner_overrides = runner_payload.get("runner_config", {})
    
    # We cast to float for httpx and ensure a minimum 120.0s timeout
    timeout_float = max(120.0, float(timeout_seconds))

    async with httpx.AsyncClient(timeout=timeout_float) as client:
        tasks = []
        for sim_name, url in runner_urls.items():
            # Determine specific opt level
            config_key = sim_name.replace("_runner", "")
            p_level = runner_overrides.get(config_key, global_opt)
            
            # Create a localized payload
            local_payload = runner_payload.copy()
            local_payload["optimization_level"] = p_level
            
            logger.info(f"Dispatching job to {sim_name} (Level: {p_level})...")
            
            # Schedule the safe request
            tasks.append(
                safe_request(client, url, local_payload, sim_name, timeout_seconds)
            )

        # Gather results (exceptions are already caught in safe_request)
        results = await asyncio.gather(*tasks)
        
    return results
