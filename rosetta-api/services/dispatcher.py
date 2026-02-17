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
async def dispatch_to_runners(runner_urls: dict, runner_payload: dict, timeout_seconds: int = settings.RUNNER_TIMEOUT_SEC) -> list:
    """ runner_payload can contain 'optimization_level' (global) and 'runner_config' (overrides) """
    global_opt = runner_payload.get("optimization_level", 0)
    runner_overrides = runner_payload.get("runner_config", {})

    # Clamp timeout to be safe? Or assume caller did it? Pydantic/Validator should handle clamping usually.
    # But let's be sure we cast to float for httpx
    
    async with httpx.AsyncClient(timeout=float(timeout_seconds)) as client:
        dispatch_tasks = []
        for sim_name, url in runner_urls.items():
            # Determine specific opt level for this runner
            # We map sim_name (e.g. 'qiskit') to payload keys
            # The runner_urls keys match the sim_names we use in logs/logic
            
            # Map sim_name to a cleaner key if needed, but for now we assume they match
            # e.g. 'qiskit_runner' vs 'qiskit'
            # Let's standardize on the prefix before _runner if present
            config_key = sim_name.replace("_runner", "")
            
            p_level = runner_overrides.get(config_key, global_opt)
            
            # Create a localized payload
            local_payload = runner_payload.copy()
            local_payload["optimization_level"] = p_level
            
            logger.info(f"Dispatching job to {sim_name} (Level: {p_level})...") 
            dispatch_tasks.append(client.post(url, json=local_payload))

        responses = await asyncio.gather(*dispatch_tasks, return_exceptions=True)

    aggregated_results = []
    for i, res in enumerate(responses):
        sim_name = list(runner_urls.keys())[i]
        if isinstance(res, httpx.Response):
            try:
                aggregated_results.append(res.json())
            except Exception as e:
                aggregated_results.append({
                    "simulator": sim_name,
                    "error": f"Failed to decode JSON response: {str(e)}. Response text: {res.text}"
                })
        elif isinstance(res, httpx.TimeoutException):
             aggregated_results.append({
                "simulator": sim_name,
                "error": f"TIMEOUT ({timeout_seconds}s): The runner took too long. This likely means the circuit is too complex for the allocated 512MB RAM or CPU limit."
            })
        elif isinstance(res, httpx.ConnectError):
            aggregated_results.append({
                "simulator": sim_name,
                "error": "CONNECTION FAILED: The runner is unreachable. It may have crashed due to running out of memory (OOM) or is still booting."
            })
        elif isinstance(res, httpx.RemoteProtocolError):
            aggregated_results.append({
                "simulator": sim_name,
                "error": "CRITICAL FAILURE: The runner crashed unexpectedly (SIGABRT/SEGV). This usually happens when the C++ simulator runs out of memory (OOM) or encounters an internal error."
            })
        else:
            aggregated_results.append({
                "simulator": sim_name,
                "error": f"Network/System Error: {type(res).__name__}: {str(res)}"
            })
    return aggregated_results
