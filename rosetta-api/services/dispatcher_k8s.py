# Kubernetes-based dispatcher for quantum runners.

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
from qrosetta_commons.helpers import get_logger

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

def _build_job_spec(sim_name: str, hostname: str, job_id: str, endpoint_type: str, payload_json: str) -> k8s_client.V1Job:
    """Constructs the Kubernetes Job manifest for a single runner pod."""
    registry = os.environ.get("K8S_IMAGE_REGISTRY", "docker.io/qrosetta")
    image = f"{registry}/{hostname}:{IMAGE_TAG}"

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
        # OpenShift runs containers with a random UID outside /etc/passwd, which causes
        # some runtimes to reset HOME to /. Pytket writes its config to $HOME/.config on
        # first import — explicitly pinning HOME prevents the PermissionError.
        k8s_client.V1EnvVar(name="HOME",                 value="/home/appuser"),

        _secret_ref("S3_ACCESS_KEY"),
        _secret_ref("S3_SECRET_KEY"),
        _secret_ref("S3_BUCKET_NAME"),
    ]

    resources = k8s_client.V1ResourceRequirements(
        requests={"cpu": "100m", "memory": "256Mi"},
        limits={"cpu": "500m",  "memory": "1Gi"},
    )

    job_name = f"qrosetta-{sim_name}-{job_id[:8]}"
    return k8s_client.V1Job(
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

def _poll_pod_phase(core_api, namespace: str, job_name: str, sim_name: str, job_id: str,
                    s3, bucket: str, completed_key: str, deadline: float, status_callback) -> str | None:
    """Phase 1: poll pod status until Succeeded/Failed/timeout.
    Falls back to polling S3 directly if pod listing is unavailable (RBAC).
    Returns 'succeeded', 'failed', or None (timeout/RBAC-fallback-resolved)."""
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
            except ClientError as e:
                if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                    continue
                continue
            except (BotoCoreError, Exception):
                continue

    return None

def _run_k8s_job_for_simulator(sim_name: str, url: str, result_key: str, opt_level: int, local_payload: dict, timeout_seconds: int, namespace: str, status_callback=None) -> dict:
    """Runs one job and stamps the result with result_key. sim_name is the canonical
    runner id used for K8s/image naming; result_key may be a self-comparison virtual
    key (e.g. 'qiskit~opt1~run2') that must be reflected in the result simulator field.
    opt_level is the effective (clamped, resolved) optimization level this run used."""
    result = _run_k8s_job_inner(sim_name, url, local_payload, timeout_seconds, namespace, status_callback)
    if isinstance(result, dict):
        result["simulator"] = result_key
        result["optimization_level"] = opt_level
    return result

def _run_k8s_job_inner(sim_name: str, url: str, local_payload: dict, timeout_seconds: int, namespace: str, status_callback=None) -> dict:
    """Orchestrates job creation, pod polling, and S3 result fetch for one simulator.
    Creates its own K8s ApiClient and S3 client so each of the 14+ concurrent threads
    has an independent connection pool (default shared pool maxsize=4 causes pool-wait
    deadlocks under full concurrency)."""
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

        job = _build_job_spec(sim_name, hostname, job_id, endpoint_type, payload_json)
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
            return {
                "simulator": sim_name,
                "error": "Runner pod failed (non-zero exit). Check container logs in your Kubernetes cluster.",
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
    finally:
        api_client.close()

async def dispatch_kubernetes_jobs(runner_urls: dict, runner_payload: dict, timeout_seconds: int, runner_statuses: dict = None) -> list:
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
            local_payload = build_runner_payload(runner_payload, spec["opt_level"])
            logger.info(f"[K8s] Scheduling job for {spec['key']} (Level: {spec['opt_level']}, Phase: {spec['phase']})...")
            tasks.append(
                loop.run_in_executor(
                    executor, _run_k8s_job_for_simulator,
                    spec["sim_name"], spec["url"], spec["key"], spec["opt_level"], local_payload,
                    timeout_seconds, namespace, make_callback(spec["key"]),
                )
            )
        try:
            results.extend(await asyncio.gather(*tasks))
        finally:
            executor.shutdown(wait=False)

    return results
