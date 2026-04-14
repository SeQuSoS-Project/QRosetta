import os
import json
import time
import uuid
import httpx
import asyncio
from concurrent.futures import ThreadPoolExecutor
import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError, BotoCoreError
from kubernetes import client as k8s_client, config as k8s_config
from config import settings
from qrosetta_commons.helpers import get_logger

EXECUTION_MODE = os.environ.get("EXECUTION_MODE", "local")
IMAGE_TAG = os.environ.get("IMAGE_TAG", "latest")

logger = get_logger("rosetta-api")

# --- CONFIGURATION (8 Runners, 2 Categories) ---
RUNNER_SERVICES = settings.get_runner_services()

# --- DYNAMIC URL BUILDERS (2 Groups) ---
STATEVECTOR_RUNNER_URLS = {
    name: f"{config['base_url']}/run" for name, config in RUNNER_SERVICES.items()
    if "statevector" in config["capabilities"] and config.get("enabled", True)
}
# Group 1: Native samplers that get MODIFIED QASM
NATIVE_SAMPLING_URLS = {
    name: f"{config['base_url']}/run_measured" for name, config in RUNNER_SERVICES.items()
    if "measured_native" in config["capabilities"] and config.get("enabled", True)
}
# Group 2: Statevector samplers that get ORIGINAL QASM
SAMPLED_SV_URLS = {
    name: f"{config['base_url']}/run_measured" for name, config in RUNNER_SERVICES.items()
    if "measured_sampled" in config["capabilities"] and config.get("enabled", True)
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


async def _dispatch_http_local(runner_urls: dict, runner_payload: dict, timeout_seconds: int, runner_statuses: dict = None) -> list:
    """HTTP dispatch via httpx — used in EXECUTION_MODE='local' (and default)."""
    global_opt = runner_payload.get("optimization_level", 0)
    runner_overrides = runner_payload.get("runner_config", {})
    timeout_float = max(120.0, float(timeout_seconds))

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
            runner_info = RUNNER_SERVICES.get(sim_name, {})
            opt_levels_dict = runner_info.get("optimization_levels", {})
            if opt_levels_dict:
                p_level = min(p_level, max(opt_levels_dict.keys()))
            local_payload = runner_payload.copy()
            local_payload["optimization_level"] = p_level
            logger.info(f"Dispatching job to {sim_name} (Level: {p_level})...")
            tasks.append(_run_and_track(sim_name, url, local_payload))

        results = await asyncio.gather(*tasks)

    return list(results)


S3_FETCH_ATTEMPTS = 6
S3_FETCH_BASE_DELAY_SEC = 2
RBAC_FALLBACK_POLL_SEC = 5


def _fetch_s3_result(s3, bucket, completed_key, sim_name, status_callback):
    """Fetch result from S3 with exponential backoff. Called after K8s confirms completion."""
    for attempt in range(S3_FETCH_ATTEMPTS):
        if attempt > 0:
            time.sleep(min(S3_FETCH_BASE_DELAY_SEC * (2 ** (attempt - 1)), 16))
        try:
            obj = s3.get_object(Bucket=bucket, Key=completed_key)
            result = json.loads(obj["Body"].read())
            s3.delete_object(Bucket=bucket, Key=completed_key)
            logger.info(f"[K8s] Fetched S3 result for {sim_name} (attempt {attempt + 1})")
            if status_callback:
                status_callback("error" if "error" in result else "done")
            return result
        except ClientError as e:
            if e.response["Error"]["Code"] not in ("NoSuchKey", "404"):
                logger.warning(f"[K8s] S3 fetch error for {sim_name}: {e}")
        except (BotoCoreError, Exception) as e:
            logger.warning(f"[K8s] S3 transient error for {sim_name}: {type(e).__name__}: {e}")
    return None


def _run_k8s_job_for_simulator(sim_name: str, url: str, local_payload: dict, timeout_seconds: int, s3, batch_api, core_api, namespace: str, status_callback=None) -> dict:
    """Sync: spawn a K8s Job with payload as env var, wait for K8s completion, fetch result from S3."""
    endpoint_type = url.rstrip("/").split("/")[-1]
    hostname = url.split("//")[1].split(":")[0]

    job_id = uuid.uuid4().hex
    completed_key = f"jobs/completed/{job_id}.json"
    bucket = settings.S3_BUCKET_NAME

    payload_json = json.dumps(local_payload)
    logger.info(f"[K8s] Preparing job for {sim_name} (payload: {len(payload_json)} bytes, job_id={job_id})")

    image = f"image-registry.apps.2.rahti.csc.fi/qrosetta/{hostname}:{IMAGE_TAG}"

    env_vars = [
        k8s_client.V1EnvVar(name="S3_ENDPOINT_URL",  value=os.environ.get("S3_ENDPOINT_URL", "")),
        k8s_client.V1EnvVar(name="S3_ACCESS_KEY",    value=os.environ.get("S3_ACCESS_KEY", "")),
        k8s_client.V1EnvVar(name="S3_SECRET_KEY",    value=os.environ.get("S3_SECRET_KEY", "")),
        k8s_client.V1EnvVar(name="S3_BUCKET_NAME",   value=os.environ.get("S3_BUCKET_NAME", "")),
        k8s_client.V1EnvVar(name="S3_REGION",        value=os.environ.get("S3_REGION", "us-east-1")),
        k8s_client.V1EnvVar(name="QROSETTA_PAYLOAD", value=payload_json),
        k8s_client.V1EnvVar(name="OMP_NUM_THREADS",      value="1"),
        k8s_client.V1EnvVar(name="MKL_NUM_THREADS",      value="1"),
        k8s_client.V1EnvVar(name="OPENBLAS_NUM_THREADS", value="1"),
        k8s_client.V1EnvVar(name="NUMEXPR_NUM_THREADS",  value="1"),
    ]

    resources = k8s_client.V1ResourceRequirements(
        requests={"cpu": "500m", "memory": "512Mi"},
        limits={"cpu": "1",     "memory": "1Gi"},
    )

    job_name = f"qrosetta-{sim_name}-{job_id[:8]}"
    job = k8s_client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=k8s_client.V1ObjectMeta(name=job_name),
        spec=k8s_client.V1JobSpec(
            backoff_limit=0,
            ttl_seconds_after_finished=300,
            template=k8s_client.V1PodTemplateSpec(
                spec=k8s_client.V1PodSpec(
                    restart_policy="Never",
                    containers=[
                        k8s_client.V1Container(
                            name=sim_name,
                            image=image,
                            image_pull_policy="IfNotPresent",
                            command=["python3", "main.py",
                                     "--endpoint", endpoint_type,
                                     "--s3-job-id", job_id],
                            env=env_vars,
                            resources=resources,
                        )
                    ],
                )
            ),
        ),
    )

    batch_api.create_namespaced_job(namespace=namespace, body=job)
    logger.info(f"[K8s] Spawned job '{job_name}' for {sim_name} (job_id={job_id})")

    if status_callback:
        status_callback("spawning")

    deadline = time.time() + timeout_seconds
    loop_start = time.time()
    pod_is_running = False
    pod_check_ok = None
    terminal_state = None

    while time.time() < deadline:
        elapsed = time.time() - loop_start

        if pod_check_ok is not False:
            time.sleep(2)
            try:
                pods = core_api.list_namespaced_pod(
                    namespace=namespace,
                    label_selector=f"job-name={job_name}",
                )
                pod_check_ok = True
                if pods.items:
                    phase = pods.items[0].status.phase
                    if phase == "Running" and not pod_is_running:
                        pod_is_running = True
                        if status_callback:
                            status_callback("running")
                        logger.info(f"[K8s] Pod for {sim_name} is Running (job_id={job_id})")
                    elif phase == "Succeeded":
                        if not pod_is_running and status_callback:
                            status_callback("running")
                        logger.info(f"[K8s] Pod for {sim_name} Succeeded (job_id={job_id})")
                        terminal_state = "succeeded"
                        break
                    elif phase == "Failed":
                        logger.error(f"[K8s] Pod for {sim_name} Failed (job_id={job_id})")
                        terminal_state = "failed"
                        break
            except Exception as e:
                if pod_check_ok is None:
                    pod_check_ok = False
                    logger.warning(f"[K8s] Pod listing unavailable for {sim_name} (RBAC?): {e}")
        else:
            time.sleep(RBAC_FALLBACK_POLL_SEC)
            try:
                obj = s3.get_object(Bucket=bucket, Key=completed_key)
                result = json.loads(obj["Body"].read())
                s3.delete_object(Bucket=bucket, Key=completed_key)
                logger.info(f"[K8s] Job for {sim_name} completed via RBAC fallback (job_id={job_id})")
                if status_callback:
                    status_callback("error" if "error" in result else "done")
                return result
            except ClientError as e:
                if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                    continue
                continue
            except (BotoCoreError, Exception):
                continue

    if terminal_state == "failed":
        if status_callback:
            status_callback("error")
        return {
            "simulator": sim_name,
            "error": "Runner pod failed (non-zero exit). Check container logs in Rahti.",
            "execution_time_sec": 0.0,
            "memory_usage_mb": 0.0,
        }

    if terminal_state == "succeeded":
        logger.info(f"[K8s] Fetching S3 result for {sim_name} (job_id={job_id})")
    else:
        logger.warning(f"[K8s] Phase 1 timed out for {sim_name} — attempting S3 fetch (job_id={job_id})")

    result = _fetch_s3_result(s3, bucket, completed_key, sim_name, status_callback)
    if result:
        return result

    if status_callback:
        status_callback("timeout" if terminal_state is None else "error")
    error_msg = (
        f"TIMEOUT ({timeout_seconds}s): K8s job did not complete in time."
        if terminal_state is None
        else "Runner pod completed but S3 result was not found."
    )
    return {
        "simulator": sim_name,
        "error": error_msg,
        "execution_time_sec": 0.0,
        "memory_usage_mb": 0.0,
    }


async def _dispatch_kubernetes_jobs(runner_urls: dict, runner_payload: dict, timeout_seconds: int, runner_statuses: dict = None) -> list:
    """Dispatch each runner as a K8s Job via S3 payload exchange, all in parallel.

    Uses a dedicated thread pool sized to the number of runners so that every
    job is created and polled concurrently.  The default asyncio executor is
    far too small (often 5 workers on a 0.5-CPU pod) — that would serialise
    the runners into batches and cause fake timeouts.

    K8s config and the S3 client are initialised ONCE here and shared across
    all threads.  This avoids:
      - Race conditions from 14 threads calling load_incluster_config() (which
        mutates global state).
      - TCP connection-pool proliferation from 14 independent boto3 clients
        hammering CSC Allas simultaneously.
    Both boto3 clients and the kubernetes-python API objects are thread-safe.
    """
    global_opt = runner_payload.get("optimization_level", 0)
    runner_overrides = runner_payload.get("runner_config", {})
    loop = asyncio.get_event_loop()

    # --- Shared resources (created ONCE, used by all threads) ---
    try:
        k8s_config.load_incluster_config()
    except Exception:
        k8s_config.load_kube_config()

    namespace = os.environ.get("NAMESPACE", "qrosetta")
    batch_api = k8s_client.BatchV1Api()
    core_api = k8s_client.CoreV1Api()

    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=BotoConfig(signature_version='s3v4'),
    )

    # One thread per runner — all K8s jobs are created and polled simultaneously.
    executor = ThreadPoolExecutor(max_workers=len(runner_urls))

    tasks = []
    for sim_name, url in runner_urls.items():
        if runner_statuses is not None:
            runner_statuses[sim_name] = "queued"

        p_level = runner_overrides.get(sim_name, global_opt)
        runner_info = RUNNER_SERVICES.get(sim_name, {})
        opt_levels_dict = runner_info.get("optimization_levels", {})
        if opt_levels_dict:
            p_level = min(p_level, max(opt_levels_dict.keys()))

        local_payload = runner_payload.copy()
        local_payload["optimization_level"] = p_level

        def make_callback(name):
            def cb(status):
                if runner_statuses is not None:
                    runner_statuses[name] = status
            return cb

        logger.info(f"[K8s] Scheduling job for {sim_name} (Level: {p_level})...")
        tasks.append(
            loop.run_in_executor(
                executor, _run_k8s_job_for_simulator,
                sim_name, url, local_payload, timeout_seconds,
                s3, batch_api, core_api, namespace,
                make_callback(sim_name),
            )
        )

    try:
        results = await asyncio.gather(*tasks)
    finally:
        executor.shutdown(wait=False)

    return list(results)


async def dispatch_to_runners(runner_urls: dict, runner_payload: dict, timeout_seconds: int = settings.RUNNER_TIMEOUT_SEC, runner_statuses: dict = None) -> list:
    """Routes dispatch to the appropriate backend based on EXECUTION_MODE."""
    if EXECUTION_MODE == "kubernetes":
        return await _dispatch_kubernetes_jobs(runner_urls, runner_payload, timeout_seconds, runner_statuses)
    return await _dispatch_http_local(runner_urls, runner_payload, timeout_seconds, runner_statuses)
