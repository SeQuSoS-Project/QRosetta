"""Kubernetes dispatcher: one Job per runner run, results exchanged through S3."""

import os
import json
import time
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError, BotoCoreError
from kubernetes import client as k8s_client, config as k8s_config
from config import settings
from qrosetta_commons.helpers import get_logger, unmeasured_metrics

logger = get_logger("rosetta-api")

IMAGE_TAG = os.environ.get("IMAGE_TAG", "latest")
S3_FETCH_ATTEMPTS = 6
S3_FETCH_BASE_DELAY_SEC = 2
RBAC_FALLBACK_POLL_SEC = 5

def _make_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=BotoConfig(signature_version='s3v4'),
    )

def _fetch_s3_result(s3, bucket, completed_key, sim_name, status_callback):
    """Phase 2: fetch and delete the completed result, retrying with exponential backoff."""
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

def runner_image_ref(hostname: str) -> str:
    """Image reference a runner Job is created with (registry/name:IMAGE_TAG)."""
    registry = os.environ.get("K8S_IMAGE_REGISTRY", "docker.io/qrosetta")
    return f"{registry}/{hostname}:{IMAGE_TAG}"


def _build_job_spec(sim_name: str, hostname: str, job_id: str, endpoint_type: str, payload_json: str, active_deadline_seconds: int = None) -> k8s_client.V1Job:
    """Construct the Kubernetes Job manifest for a single runner pod."""
    image = runner_image_ref(hostname)

    def _secret_ref(key: str) -> k8s_client.V1EnvVar:
        """Reference a value from the rosetta-secrets K8s Secret by key name."""
        return k8s_client.V1EnvVar(
            name=key,
            value_from=k8s_client.V1EnvVarSource(
                secret_key_ref=k8s_client.V1SecretKeySelector(
                    name="rosetta-secrets", key=key
                )
            ),
        )

    env_vars = [
        k8s_client.V1EnvVar(name="S3_ENDPOINT_URL",     value=os.environ.get("S3_ENDPOINT_URL", "")),
        k8s_client.V1EnvVar(name="S3_REGION",            value=os.environ.get("S3_REGION", "us-east-1")),
        k8s_client.V1EnvVar(name="QROSETTA_PAYLOAD",     value=payload_json),
        k8s_client.V1EnvVar(name="OMP_NUM_THREADS",      value="1"),
        k8s_client.V1EnvVar(name="MKL_NUM_THREADS",      value="1"),
        k8s_client.V1EnvVar(name="OPENBLAS_NUM_THREADS", value="1"),
        k8s_client.V1EnvVar(name="NUMEXPR_NUM_THREADS",  value="1"),
        k8s_client.V1EnvVar(name="NUMBA_NUM_THREADS",    value="1"),
        # OpenShift's random UID can reset HOME to /, where pytket cannot write its config.
        k8s_client.V1EnvVar(name="HOME",                 value="/home/appuser"),
        _secret_ref("S3_ACCESS_KEY"),
        _secret_ref("S3_SECRET_KEY"),
        _secret_ref("S3_BUCKET_NAME"),
    ]

    resources = k8s_client.V1ResourceRequirements(
        requests={"cpu": "200m", "memory": "256Mi"},
        limits={"cpu": "1000m", "memory": "1Gi"},
    )

    job_name = f"qrosetta-{sim_name}-{job_id[:8]}"
    return k8s_client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=k8s_client.V1ObjectMeta(name=job_name),
        spec=k8s_client.V1JobSpec(
            backoff_limit=0,
            ttl_seconds_after_finished=300,
            active_deadline_seconds=active_deadline_seconds,
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

def _poll_pod_phase(core_api, namespace: str, job_name: str, sim_name: str, job_id: str,
                    s3, bucket: str, completed_key: str, deadline: float, status_callback) -> str | None:
    """Phase 1: poll pod status until Succeeded/Failed or the deadline.

    Falls back to polling S3 directly if pod listing is unavailable (RBAC). Returns the
    result dict (RBAC fallback), 'succeeded', 'failed', 'timeout_running' (the pod reached
    Running), 'timeout_pending' (the pod never reached Running) or 'timeout_unknown'
    (pod phase could not be read).
    """
    pod_is_running = False
    pod_check_ok = None

    while time.time() < deadline:
        if pod_check_ok is not False:
            time.sleep(2)
            try:
                pods = core_api.list_namespaced_pod(
                    namespace=namespace,
                    label_selector=f"job-name={job_name}",
                    _request_timeout=10,
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
                        return "succeeded"
                    elif phase == "Failed":
                        logger.error(f"[K8s] Pod for {sim_name} Failed (job_id={job_id})")
                        return "failed"
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
            except Exception:
                continue

    if pod_check_ok is not True:
        return "timeout_unknown"
    return "timeout_running" if pod_is_running else "timeout_pending"

def _k8s_error(sim_name: str, message: str, dispatch_status: str) -> dict:
    return {
        "simulator": sim_name,
        "error": message,
        "dispatch_status": dispatch_status,
        **unmeasured_metrics(),
        "queue_wait_sec": None,
    }


def _run_k8s_job_for_simulator(spec: dict, local_payload: dict, timeout_seconds: int, namespace: str, status_callback=None) -> dict:
    """Run one job and annotate its result with the spec's key, seed and dispatch status."""
    from services.dispatcher import annotate_result, utc_now_iso

    dispatched_at = utc_now_iso()
    hostname = spec["url"].split("//")[1].split(":")[0]
    try:
        result = _run_k8s_job_inner(spec["sim_name"], spec["url"], local_payload, timeout_seconds, namespace, status_callback)
    except Exception as e:
        logger.error(f"[K8s] Could not create job for {spec['key']}: {e}", exc_info=True)
        if status_callback:
            status_callback("error")
        result = _k8s_error(spec["sim_name"], f"UNAVAILABLE: the {spec['key']} Job could not be created ({type(e).__name__}).", "offline")
    return annotate_result(result, spec, local_payload, dispatched_at,
                           dispatch_status=result.pop("dispatch_status", None),
                           runner_image=runner_image_ref(hostname))

def _run_k8s_job_inner(sim_name: str, url: str, local_payload: dict, timeout_seconds: int, namespace: str, status_callback=None) -> dict:
    """Create the Job, poll its pod and fetch the S3 result for one runner run.

    Each call creates its own K8s ApiClient and S3 client: the default shared pool
    (maxsize=4) deadlocks under 14+ concurrent threads.
    """
    api_client = k8s_client.ApiClient()
    batch_api = k8s_client.BatchV1Api(api_client=api_client)
    core_api = k8s_client.CoreV1Api(api_client=api_client)
    s3 = _make_s3_client()

    try:
        endpoint_type = url.rstrip("/").split("/")[-1]
        hostname = url.split("//")[1].split(":")[0]

        job_id = uuid.uuid4().hex
        completed_key = f"jobs/completed/{job_id}.json"
        bucket = settings.S3_BUCKET_NAME

        payload_json = json.dumps(local_payload)
        logger.info(f"[K8s] Preparing job for {sim_name} (payload: {len(payload_json)} bytes, job_id={job_id})")

        active_deadline = timeout_seconds + settings.RUNNER_DEADLINE_BUFFER_SEC
        job = _build_job_spec(sim_name, hostname, job_id, endpoint_type, payload_json,
                              active_deadline_seconds=active_deadline)
        job_name = job.metadata.name

        batch_api.create_namespaced_job(namespace=namespace, body=job, _request_timeout=30)
        logger.info(f"[K8s] Spawned job '{job_name}' for {sim_name} (job_id={job_id})")
        if status_callback:
            status_callback("spawning")

        deadline = time.time() + timeout_seconds
        terminal_state = _poll_pod_phase(
            core_api, namespace, job_name, sim_name, job_id,
            s3, bucket, completed_key, deadline, status_callback
        )

        if isinstance(terminal_state, dict):
            return terminal_state

        if terminal_state == "failed":
            if status_callback:
                status_callback("error")
            return _k8s_error(sim_name, "The runner pod exited with an error before returning a result (likely out of memory or time). Server operators can see details in the runner pod logs.", "error")

        if terminal_state == "succeeded":
            logger.info(f"[K8s] Fetching S3 result for {sim_name} (job_id={job_id})")
        else:
            logger.warning(f"[K8s] Phase 1 timed out for {sim_name} — attempting S3 fetch (job_id={job_id})")

        result = _fetch_s3_result(s3, bucket, completed_key, sim_name, status_callback)
        if result:
            return result

        timed_out = terminal_state != "succeeded"
        if timed_out:
            try:
                batch_api.delete_namespaced_job(
                    name=job_name, namespace=namespace, propagation_policy="Background",
                    _request_timeout=10)
                logger.info(f"[K8s] Deleted timed-out job '{job_name}' for {sim_name}")
            except Exception as e:
                logger.warning(f"[K8s] Could not delete timed-out job '{job_name}': {e}")

        if status_callback:
            status_callback("timeout" if timed_out else "error")
        if terminal_state == "timeout_pending":
            return _k8s_error(sim_name, f"UNAVAILABLE: the {sim_name} pod was not running after {timeout_seconds}s (unschedulable, or the image could not be pulled).", "offline")
        if timed_out:
            return _k8s_error(sim_name, f"TIMEOUT ({timeout_seconds}s): the Kubernetes Job (scheduling, image pull, SDK import, warm-up and timed run) did not complete within {timeout_seconds} s.", "timeout")
        return _k8s_error(sim_name, "Runner pod completed but S3 result was not found.", "error")
    finally:
        api_client.close()

async def dispatch_kubernetes_jobs(runner_urls: dict, runner_payload: dict, timeout_seconds: int, runner_statuses: dict = None) -> list:
    """Run every job as a Kubernetes Job, one thread per job, phase by phase."""
    from services.dispatcher import expand_runner_jobs, group_specs_by_phase, build_runner_payload

    specs = expand_runner_jobs(runner_urls, runner_payload)
    phase_groups = group_specs_by_phase(specs)
    loop = asyncio.get_event_loop()

    try:
        k8s_config.load_incluster_config()
    except Exception:
        k8s_config.load_kube_config()

    namespace = os.environ.get("NAMESPACE", "qrosetta")

    def make_callback(key):
        def cb(status):
            if runner_statuses is not None:
                runner_statuses[key] = status
        return cb

    if runner_statuses is not None:
        for spec in specs:
            runner_statuses[spec["key"]] = "queued"

    results = []
    for group in phase_groups:
        executor = ThreadPoolExecutor(max_workers=max(1, len(group)))
        tasks = []
        for spec in group:
            local_payload = build_runner_payload(runner_payload, spec)
            logger.info(f"[K8s] Scheduling job for {spec['key']} (Level: {spec['opt_level']}, Phase: {spec['phase']})...")
            tasks.append(
                loop.run_in_executor(
                    executor, _run_k8s_job_for_simulator,
                    spec, local_payload, timeout_seconds, namespace, make_callback(spec["key"]),
                )
            )
        try:
            results.extend(await asyncio.gather(*tasks))
        finally:
            executor.shutdown(wait=False)

    return results
