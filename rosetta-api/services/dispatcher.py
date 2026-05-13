import os
from config import settings
from qrosetta_commons.helpers import get_logger
from services.dispatcher_http import dispatch_http_local
from services.dispatcher_k8s import dispatch_kubernetes_jobs

EXECUTION_MODE = os.environ.get("EXECUTION_MODE", "local")
logger = get_logger("rosetta-api")

RUNNER_SERVICES = settings.get_runner_services()

STATEVECTOR_RUNNER_URLS = {
    name: f"{config['base_url']}/run" for name, config in RUNNER_SERVICES.items()
    if "statevector" in config["capabilities"] and config.get("enabled", True)
}
NATIVE_SAMPLING_URLS = {
    name: f"{config['base_url']}/run_measured" for name, config in RUNNER_SERVICES.items()
    if "measured_native" in config["capabilities"] and config.get("enabled", True)
}
SAMPLED_SV_URLS = {
    name: f"{config['base_url']}/run_measured" for name, config in RUNNER_SERVICES.items()
    if "measured_sampled" in config["capabilities"] and config.get("enabled", True)
}


async def dispatch_to_runners(runner_urls: dict, runner_payload: dict, timeout_seconds: int = settings.RUNNER_TIMEOUT_SEC, runner_statuses: dict = None) -> list:
    if EXECUTION_MODE == "kubernetes":
        return await dispatch_kubernetes_jobs(runner_urls, runner_payload, timeout_seconds, runner_statuses)
    return await dispatch_http_local(runner_urls, runner_payload, timeout_seconds, runner_statuses)
