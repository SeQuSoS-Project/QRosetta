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


def _run_k8s_job_for_simulator(sim_name: str, url: str, local_payload: dict, timeout_seconds: int, s3, batch_api, core_api, namespace: str, status_callback=None) -> dict:
    """Sync: upload payload to S3, spawn a K8s Job, poll for the result. Runs in a thread.

    Receives shared s3 client and pre-configured K8s API objects from the
    caller — these are created ONCE before threads start, avoiding race
    conditions on k8s_config globals and connection-pool proliferation.
    """
    # --- Parse URL ---
    # e.g. "http://qsim-cirq-runner:8000/run_measured" -> hostname="qsim-cirq-runner", endpoint_type="run_measured"
    endpoint_type = url.rstrip("/").split("/")[-1]
    hostname = url.split("//")[1].split(":")[0]

    job_id = uuid.uuid4().hex
    pending_key = f"jobs/pending/{job_id}.json"
    completed_key = f"jobs/completed/{job_id}.json"
    bucket = settings.S3_BUCKET_NAME

    # --- S3 Payload Drop ---
    payload_bytes = json.dumps(local_payload).encode()
    s3.put_object(
        Bucket=bucket,
        Key=pending_key,
        Body=payload_bytes,
        ContentLength=len(payload_bytes),
    )
    logger.info(f"[K8s] Uploaded payload for {sim_name} → s3://{bucket}/{pending_key}")

    # --- K8s Job Spawn ---
    image = f"image-registry.apps.2.rahti.csc.fi/qrosetta/{hostname}:latest"

    env_vars = [
        k8s_client.V1EnvVar(name="S3_ENDPOINT_URL",  value=os.environ.get("S3_ENDPOINT_URL", "")),
        k8s_client.V1EnvVar(name="S3_ACCESS_KEY",    value=os.environ.get("S3_ACCESS_KEY", "")),
        k8s_client.V1EnvVar(name="S3_SECRET_KEY",    value=os.environ.get("S3_SECRET_KEY", "")),
        k8s_client.V1EnvVar(name="S3_BUCKET_NAME",   value=os.environ.get("S3_BUCKET_NAME", "")),
        k8s_client.V1EnvVar(name="S3_REGION",        value=os.environ.get("S3_REGION", "us-east-1")),
        # Pin all math-library thread counts to 1 so pods don't steal CPU from
        # each other when multiple jobs run concurrently — matches the local
        # docker-compose benchmarking environment.
        k8s_client.V1EnvVar(name="OMP_NUM_THREADS",      value="1"),
        k8s_client.V1EnvVar(name="MKL_NUM_THREADS",      value="1"),
        k8s_client.V1EnvVar(name="OPENBLAS_NUM_THREADS", value="1"),
        k8s_client.V1EnvVar(name="NUMEXPR_NUM_THREADS",  value="1"),
    ]

    # Mirror the docker-compose resource caps so every runner job gets a
    # predictable slice of the cluster, regardless of how many are queued.
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

    # --- S3 + Pod Status Polling Loop ---
    deadline = time.time() + timeout_seconds
    loop_start = time.time()
    pod_is_running = False
    pod_succeeded = False        # True once K8s phase == Succeeded
    pod_check_ok = None          # None=unknown, True=RBAC ok, False=RBAC denied
    s3_grace_ticks = 0           # S3 polls after pod Succeeded with no result yet
    S3_GRACE_TICKS_MAX = 10      # ~20 s of Allas propagation grace window
    # Caps for situations where pod status is unavailable (RBAC denied):
    # After NO_POD_SECS with no pod visible and no S3 result, give up.
    NO_POD_SECS = 120
    poll_tick = 0

    while time.time() < deadline:
        time.sleep(2)
        poll_tick += 1
        elapsed = time.time() - loop_start

        # Check pod phase every 4s until terminal (keep checking even after Running
        # so we can catch Succeeded/Failed without waiting for the full timeout).
        if poll_tick % 2 == 0 and not pod_succeeded:
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
                        pod_succeeded = True
                        if not pod_is_running:
                            pod_is_running = True
                            if status_callback:
                                status_callback("running")
                        logger.info(f"[K8s] Pod for {sim_name} Succeeded — waiting for S3 result (job_id={job_id})")
                    elif phase == "Failed":
                        logger.error(f"[K8s] Pod for {sim_name} Failed (job_id={job_id})")
                        if status_callback:
                            status_callback("error")
                        try:
                            s3.delete_object(Bucket=bucket, Key=pending_key)
                        except Exception:
                            pass
                        return {
                            "simulator": sim_name,
                            "error": "Runner pod failed (non-zero exit). Check container logs in Rahti for details.",
                            "execution_time_sec": 0.0,
                            "memory_usage_mb": 0.0,
                        }
                elif pod_check_ok and elapsed > NO_POD_SECS and not pod_is_running:
                    # Pod listing works (RBAC ok) but no pod has appeared — the
                    # job may have been evicted or never scheduled.
                    logger.error(f"[K8s] No pod found for {sim_name} after {elapsed:.0f}s (job_id={job_id})")
                    if status_callback:
                        status_callback("error")
                    return {
                        "simulator": sim_name,
                        "error": f"No runner pod appeared after {NO_POD_SECS}s. The job may have been evicted or failed to schedule.",
                        "execution_time_sec": 0.0,
                        "memory_usage_mb": 0.0,
                    }
            except Exception as e:
                if pod_check_ok is None:
                    pod_check_ok = False
                    logger.warning(f"[K8s] Pod listing unavailable for {sim_name} (RBAC?): {e}")

        # Check S3 for completed result
        try:
            obj = s3.get_object(Bucket=bucket, Key=completed_key)
            result = json.loads(obj["Body"].read())
            s3.delete_object(Bucket=bucket, Key=pending_key)
            s3.delete_object(Bucket=bucket, Key=completed_key)
            logger.info(f"[K8s] Job for {sim_name} completed (job_id={job_id})")
            if status_callback:
                status_callback("error" if "error" in result else "done")
            return result
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                if pod_succeeded:
                    # Pod Succeeded but Allas hasn't propagated the result yet —
                    # count down a short grace window before giving up.
                    s3_grace_ticks += 1
                    if s3_grace_ticks >= S3_GRACE_TICKS_MAX:
                        logger.error(f"[K8s] Pod for {sim_name} Succeeded but S3 result never appeared after {s3_grace_ticks} retries (job_id={job_id})")
                        if status_callback:
                            status_callback("error")
                        return {
                            "simulator": sim_name,
                            "error": "Runner pod completed but S3 result was not found. The pod may have crashed during the S3 upload.",
                            "execution_time_sec": 0.0,
                            "memory_usage_mb": 0.0,
                            "_s3_recovery_key": completed_key,
                        }
                elif pod_check_ok is False and elapsed > NO_POD_SECS:
                    # RBAC denied pod listing AND no S3 result after the cap —
                    # bail out rather than block until the full 300 s timeout.
                    logger.error(f"[K8s] {sim_name}: no S3 result after {elapsed:.0f}s and pod listing unavailable (job_id={job_id})")
                    if status_callback:
                        status_callback("error")
                    return {
                        "simulator": sim_name,
                        "error": f"No result after {NO_POD_SECS}s. Pod listing was unavailable (check RBAC); the runner may not have started.",
                        "execution_time_sec": 0.0,
                        "memory_usage_mb": 0.0,
                        "_s3_recovery_key": completed_key,
                    }
                continue
            logger.warning(f"[K8s] S3 poll error for {sim_name} (job_id={job_id}): {e}")
            continue
        except (BotoCoreError, Exception) as e:
            # Catch transient network errors (EndpointConnectionError,
            # ConnectionClosedError, ReadTimeoutError) that do NOT inherit
            # from ClientError.  Log and retry on next poll tick.
            logger.warning(f"[K8s] S3 transient error for {sim_name} (job_id={job_id}): {type(e).__name__}: {e}")
            continue

    # --- Timeout ---
    logger.error(f"[K8s] Job for {sim_name} timed out after {timeout_seconds}s (job_id={job_id})")
    try:
        s3.delete_object(Bucket=bucket, Key=pending_key)
    except Exception:
        pass
    if status_callback:
        status_callback("timeout")
    return {
        "simulator": sim_name,
        "error": f"TIMEOUT ({timeout_seconds}s): K8s job did not complete in time.",
        "execution_time_sec": 0.0,
        "memory_usage_mb": 0.0,
        "_s3_recovery_key": completed_key,
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

    # --- S3 Recovery Sweep ---
    # Pods complete and upload to S3, but the polling loop sometimes misses
    # 1-2 results due to transient Allas hiccups.  Before returning, do one
    # last check for any runner that failed/timed-out but left a recovery key.
    # This is cheap (1 S3 GET per failed runner) and rescues real data.
    bucket = settings.S3_BUCKET_NAME
    recovered = 0
    final_results = list(results)
    for i, result in enumerate(final_results):
        recovery_key = result.get("_s3_recovery_key")
        if not recovery_key or "error" not in result:
            continue
        sim_name = result.get("simulator", "unknown")
        logger.info(f"[K8s] Recovery sweep: checking S3 for {sim_name} (key={recovery_key})")
        try:
            obj = s3.get_object(Bucket=bucket, Key=recovery_key)
            recovered_result = json.loads(obj["Body"].read())
            s3.delete_object(Bucket=bucket, Key=recovery_key)
            logger.info(f"[K8s] Recovery sweep: RESCUED result for {sim_name}")
            if runner_statuses is not None:
                runner_statuses[sim_name] = "error" if "error" in recovered_result else "done"
            final_results[i] = recovered_result
            recovered += 1
        except Exception:
            # Still not there — genuine failure, keep original error result.
            pass

    if recovered:
        logger.info(f"[K8s] Recovery sweep rescued {recovered} runner(s)")

    # Strip internal recovery keys from final output
    for result in final_results:
        result.pop("_s3_recovery_key", None)

    return final_results


async def dispatch_to_runners(runner_urls: dict, runner_payload: dict, timeout_seconds: int = settings.RUNNER_TIMEOUT_SEC, runner_statuses: dict = None) -> list:
    """Routes dispatch to the appropriate backend based on EXECUTION_MODE."""
    if EXECUTION_MODE == "kubernetes":
        return await _dispatch_kubernetes_jobs(runner_urls, runner_payload, timeout_seconds, runner_statuses)
    return await _dispatch_http_local(runner_urls, runner_payload, timeout_seconds, runner_statuses)
