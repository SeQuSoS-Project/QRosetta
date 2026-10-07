"""Kubernetes dispatcher: one Job per runner run, results exchanged through S3.

At most ``K8S_MAX_CONCURRENT_JOBS`` Jobs exist at a time across all jobs of this API process,
so every Job created fits the project's CPU quota; the rest wait for a slot.
"""

import os
import re
import json
import time
import uuid
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError, BotoCoreError
from kubernetes import client as k8s_client, config as k8s_config
from kubernetes.client.rest import ApiException
from config import settings, server_image_digests
from qrosetta_commons.helpers import get_logger, unmeasured_metrics

logger = get_logger("rosetta-api")

IMAGE_TAG = os.environ.get("IMAGE_TAG", "latest")
S3_FETCH_ATTEMPTS = 6
S3_FETCH_BASE_DELAY_SEC = 2
RBAC_FALLBACK_POLL_SEC = 5
POD_GONE_WAIT_SEC = 30
PAYLOAD_ENV_MAX_BYTES = 96 * 1024
IMAGE_PULL_FAILURES = frozenset({"ErrImagePull", "ImagePullBackOff", "InvalidImageName",
                                 "ErrImageNeverPull", "RegistryUnavailable"})
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")

RUNNER_RESOURCES = {"requests": {"cpu": "200m", "memory": "256Mi"},
                    "limits": {"cpu": "1000m", "memory": "1Gi"}}
COMPILER_RESOURCES = {"requests": {"cpu": "200m", "memory": "512Mi"},
                      "limits": {"cpu": "1000m", "memory": "2Gi"}}

JOB_SLOTS = threading.BoundedSemaphore(settings.K8S_MAX_CONCURRENT_JOBS)


def _make_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=BotoConfig(signature_version='s3v4'),
    )


def _delete_s3_object(s3, bucket: str, key: str) -> None:
    """Delete one exchange object; a failure is logged, never raised."""
    try:
        s3.delete_object(Bucket=bucket, Key=key)
    except Exception as e:
        logger.warning(f"[K8s] Could not delete s3://{bucket}/{key}: {type(e).__name__}: {e}")


def _take_s3_result(s3, bucket: str, completed_key: str) -> dict:
    """Read and parse the completed result, then delete it. Raises when the result cannot be
    read; a failed delete does not discard a result already read."""
    obj = s3.get_object(Bucket=bucket, Key=completed_key)
    result = json.loads(obj["Body"].read())
    _delete_s3_object(s3, bucket, completed_key)
    return result


def _fetch_s3_result(s3, bucket, completed_key, sim_name, status_callback):
    """Phase 2: fetch and delete the completed result, retrying with exponential backoff."""
    for attempt in range(S3_FETCH_ATTEMPTS):
        if attempt > 0:
            time.sleep(min(S3_FETCH_BASE_DELAY_SEC * (2 ** (attempt - 1)), 16))
        try:
            result = _take_s3_result(s3, bucket, completed_key)
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


def _image_digest(hostname: str) -> str | None:
    """The deployed digest of ``hostname``'s image from QROSETTA_IMAGE_DIGESTS (a
    ``sha256:...`` string or an object with a ``digest`` field), or None."""
    entry = server_image_digests().get(hostname)
    digest = entry.get("digest") if isinstance(entry, dict) else entry
    return digest if isinstance(digest, str) and _DIGEST.match(digest) else None


def runner_image_ref(hostname: str) -> str:
    """Image reference a Job is created with and its result records: registry/name@digest
    when QROSETTA_IMAGE_DIGESTS has the image, else registry/name:IMAGE_TAG."""
    registry = os.environ.get("K8S_IMAGE_REGISTRY", "docker.io/qrosetta")
    digest = _image_digest(hostname)
    if digest:
        return f"{registry}/{hostname}@{digest}"
    return f"{registry}/{hostname}:{IMAGE_TAG}"


def job_resources(endpoint_type: str) -> dict:
    """Requests and limits of a Job: compile Jobs get the 2 GiB of the local compiler
    containers, runner Jobs 1 GiB; both 1000m CPU, the size one job slot accounts for."""
    return COMPILER_RESOURCES if endpoint_type == "compile" else RUNNER_RESOURCES


def _build_job_spec(sim_name: str, hostname: str, job_id: str, endpoint_type: str,
                    payload_json: str | None, active_deadline_seconds: int = None) -> k8s_client.V1Job:
    """Construct the Kubernetes Job manifest for a single runner pod. Without
    ``payload_json`` the pod reads its payload from ``jobs/pending/<job_id>.json``."""
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
        k8s_client.V1EnvVar(name="S3_ENDPOINT_URL",        value=settings.S3_ENDPOINT_URL),
        k8s_client.V1EnvVar(name="S3_REGION",              value=settings.S3_REGION),
        k8s_client.V1EnvVar(name="MAX_QUBITS_STATEVECTOR", value=str(settings.MAX_QUBITS_STATEVECTOR)),
        k8s_client.V1EnvVar(name="MAX_QUBITS_MEASURED",    value=str(settings.MAX_QUBITS_MEASURED)),
        k8s_client.V1EnvVar(name="MAX_QUBITS_COMPILE",     value=str(settings.MAX_QUBITS_COMPILE)),
        k8s_client.V1EnvVar(name="OMP_NUM_THREADS",        value="1"),
        k8s_client.V1EnvVar(name="MKL_NUM_THREADS",        value="1"),
        k8s_client.V1EnvVar(name="OPENBLAS_NUM_THREADS",   value="1"),
        k8s_client.V1EnvVar(name="NUMEXPR_NUM_THREADS",    value="1"),
        k8s_client.V1EnvVar(name="NUMBA_NUM_THREADS",      value="1"),
        # OpenShift's random UID can reset HOME to /, where pytket cannot write its config.
        k8s_client.V1EnvVar(name="HOME",                   value="/home/appuser"),
        _secret_ref("S3_ACCESS_KEY"),
        _secret_ref("S3_SECRET_KEY"),
        _secret_ref("S3_BUCKET_NAME"),
    ]
    if payload_json is not None:
        env_vars.append(k8s_client.V1EnvVar(name="QROSETTA_PAYLOAD", value=payload_json))

    resources = k8s_client.V1ResourceRequirements(**job_resources(endpoint_type))

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
                    s3, bucket: str, completed_key: str, deadline: float, status_callback) -> str | dict:
    """Phase 1: poll pod status until Succeeded/Failed or the deadline.

    A 403 on the first pod listing (no RBAC permission) switches to polling S3 directly;
    any other listing failure is retried on the next poll. Returns the result dict (RBAC
    fallback), 'succeeded', 'failed', 'timeout_running' (the pod reached Running),
    'timeout_pending' (the pod never reached Running), 'timeout_no_pod' (no pod was ever
    created) or 'timeout_unknown' (pod phase could not be read).
    """
    pod_is_running = False
    pod_seen = False
    pod_check_ok = None
    listing_failures = 0

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
                    pod_seen = True
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
            except ApiException as e:
                if e.status == 403 and pod_check_ok is None:
                    pod_check_ok = False
                    logger.warning(f"[K8s] Pod listing forbidden for {sim_name} (RBAC); polling S3: {e.reason}")
                else:
                    listing_failures += 1
                    if listing_failures == 1:
                        logger.warning(f"[K8s] Pod listing failed for {sim_name} (HTTP {e.status}); retrying")
            except Exception as e:
                listing_failures += 1
                if listing_failures == 1:
                    logger.warning(f"[K8s] Pod listing failed for {sim_name} ({type(e).__name__}); retrying")
        else:
            time.sleep(RBAC_FALLBACK_POLL_SEC)
            try:
                result = _take_s3_result(s3, bucket, completed_key)
            except Exception:
                continue
            logger.info(f"[K8s] Job for {sim_name} completed via RBAC fallback (job_id={job_id})")
            if status_callback:
                status_callback("error" if "error" in result else "done")
            return result

    if pod_check_ok is not True:
        return "timeout_unknown"
    if not pod_seen:
        return "timeout_no_pod"
    return "timeout_running" if pod_is_running else "timeout_pending"


def _pending_pod_state(core_api, namespace: str, job_name: str) -> tuple[str | None, str]:
    """Why the Job's pod is still Pending: ('unschedulable', message) when the scheduler has
    not placed it, ('image_pull_failed', reason) when its image cannot be pulled,
    ('starting', reason) while the image is pulled or the container created, and
    (None, '') when the pod cannot be read."""
    try:
        pods = core_api.list_namespaced_pod(
            namespace=namespace, label_selector=f"job-name={job_name}",
            _request_timeout=10).items
    except Exception as e:
        logger.warning(f"[K8s] Could not read the pod of '{job_name}': {e}")
        return None, ""
    if not pods:
        return None, ""
    status = pods[0].status
    for cond in status.conditions or []:
        if cond.type == "PodScheduled" and cond.status == "False":
            return "unschedulable", (cond.message or cond.reason or "no reason given")
    for cs in status.container_statuses or []:
        waiting = cs.state.waiting if cs.state else None
        if waiting and waiting.reason in IMAGE_PULL_FAILURES:
            return "image_pull_failed", waiting.reason
    reasons = [cs.state.waiting.reason for cs in status.container_statuses or []
               if cs.state and cs.state.waiting and cs.state.waiting.reason]
    return "starting", (reasons[0] if reasons else "ContainerCreating")


def _pod_refusal_resource(core_api, namespace: str, job_name: str) -> str | None:
    """The resource named in the Job's latest 'exceeded quota' FailedCreate event
    (e.g. 'limits.cpu'), 'unknown' for a quota refusal naming none, None otherwise."""
    try:
        events = core_api.list_namespaced_event(
            namespace=namespace, field_selector=f"involvedObject.name={job_name}",
            _request_timeout=10).items
    except Exception as e:
        logger.warning(f"[K8s] Could not read events of '{job_name}': {e}")
        return None
    refusals = [ev for ev in events
                if ev.reason == "FailedCreate" and "exceeded quota" in (ev.message or "")]
    if not refusals:
        return None
    message = refusals[-1].message
    logger.warning(f"[K8s] Pod of '{job_name}' refused: {message}")
    requested = message.split("requested: ", 1)[1].split(",")[0] if "requested: " in message else ""
    return requested.split("=")[0].strip() or "unknown"


def _wait_pod_gone(core_api, namespace: str, job_name: str) -> None:
    """Wait up to POD_GONE_WAIT_SEC for a deleted Job's pod to disappear, so the slot it
    frees is also free in the quota."""
    end = time.time() + POD_GONE_WAIT_SEC
    while time.time() < end:
        try:
            if not core_api.list_namespaced_pod(
                    namespace=namespace, label_selector=f"job-name={job_name}",
                    _request_timeout=10).items:
                return
        except Exception:
            return
        time.sleep(2)


def _delete_job(batch_api, core_api, namespace: str, job_name: str) -> None:
    """Delete a Job and wait for its pod to go; a failure is logged, never raised."""
    try:
        batch_api.delete_namespaced_job(
            name=job_name, namespace=namespace, propagation_policy="Background",
            _request_timeout=10)
        logger.info(f"[K8s] Deleted job '{job_name}'")
        _wait_pod_gone(core_api, namespace, job_name)
    except ApiException as e:
        if e.status != 404:
            logger.warning(f"[K8s] Could not delete job '{job_name}': HTTP {e.status}")
    except Exception as e:
        logger.warning(f"[K8s] Could not delete job '{job_name}': {type(e).__name__}: {e}")


def _create_job(batch_api, core_api, namespace: str, job) -> None:
    """Create the Job. When the create call fails without a definite answer from the API
    server (a client timeout, a dropped connection, a 5xx), the Job may still exist: it is
    looked up, and a Job that exists counts as created. One that cannot be confirmed
    either way is deleted before the error propagates, so no Job runs outside its slot."""
    job_name = job.metadata.name
    try:
        batch_api.create_namespaced_job(namespace=namespace, body=job, _request_timeout=30)
        return
    except ApiException as e:
        if e.status is not None and 400 <= e.status < 500:
            raise
        failure = e
    except Exception as e:
        failure = e
    logger.warning(f"[K8s] Creating '{job_name}' failed ({type(failure).__name__}); checking whether it exists")
    try:
        batch_api.read_namespaced_job(name=job_name, namespace=namespace, _request_timeout=10)
        logger.info(f"[K8s] Job '{job_name}' exists despite the failed create call")
        return
    except ApiException as e:
        if e.status == 404:
            raise failure
    except Exception:
        pass
    _delete_job(batch_api, core_api, namespace, job_name)
    raise failure


def _k8s_error(sim_name: str, message: str, dispatch_status: str) -> dict:
    """Result for a run that returned nothing: the message and every metric unmeasured."""
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
    budget = float(settings.RUNNER_QUEUE_MAX_WAIT_SEC)
    t0 = time.monotonic()
    if not JOB_SLOTS.acquire(timeout=budget):
        waited = time.monotonic() - t0
        if status_callback:
            status_callback("timeout")
        result = _k8s_error(spec["sim_name"], (
            f"TIMEOUT while waiting for one of the server's {settings.K8S_MAX_CONCURRENT_JOBS} "
            f"Kubernetes job slots: waited {waited:.0f} s (queue budget {budget:.0f} s); "
            f"the run never started."), "timeout")
        result.update(never_started=True, timed_out=True, queue_wait_sec=waited)
        return annotate_result(result, spec, local_payload, dispatched_at,
                               dispatch_status=result.pop("dispatch_status", None),
                               runner_image=runner_image_ref(hostname))
    waited = time.monotonic() - t0
    try:
        result = _run_k8s_job_inner(spec["sim_name"], spec["url"], local_payload, timeout_seconds, namespace, status_callback)
    except Exception as e:
        logger.error(f"[K8s] Could not create job for {spec['key']}: {e}", exc_info=True)
        if status_callback:
            status_callback("error")
        result = _k8s_error(spec["sim_name"], f"UNAVAILABLE: the {spec['key']} Job could not be created ({type(e).__name__}).", "offline")
    finally:
        JOB_SLOTS.release()
    result["queue_wait_sec"] = waited
    return annotate_result(result, spec, local_payload, dispatched_at,
                           dispatch_status=result.pop("dispatch_status", None),
                           runner_image=runner_image_ref(hostname))


def _pending_result(sim_name: str, state: str | None, detail: str, timeout_seconds: int) -> dict:
    """Result for a Job whose pod was still Pending at the deadline."""
    if state == "unschedulable":
        result = _k8s_error(sim_name, (
            f"TIMEOUT: Kubernetes did not schedule the {sim_name} pod within {timeout_seconds} s "
            f"({detail}); the run never started."), "timeout")
        result.update(never_started=True, timed_out=True)
        return result
    if state == "image_pull_failed":
        return _k8s_error(sim_name, f"UNAVAILABLE: the {sim_name} image could not be pulled ({detail}).", "offline")
    if state == "starting":
        result = _k8s_error(sim_name, (
            f"TIMEOUT ({timeout_seconds}s): the {sim_name} pod was still starting ({detail}: "
            f"pulling its image or creating its container) when the budget ran out; the "
            f"simulation did not start. A first run on a node pulls the image; a rerun is "
            f"usually faster."), "timeout")
        result.update(timed_out=True, pod_waiting_reason=detail)
        return result
    return _k8s_error(sim_name, f"UNAVAILABLE: the {sim_name} pod was not running after {timeout_seconds}s and its state could not be read.", "offline")


def _run_k8s_job_inner(sim_name: str, url: str, local_payload: dict, timeout_seconds: int, namespace: str, status_callback=None) -> dict:
    """Create the Job, poll its pod and fetch the S3 result for one runner run.

    A payload larger than PAYLOAD_ENV_MAX_BYTES is written to ``jobs/pending/<id>.json``
    (Linux caps one environment string at 128 KiB) and deleted when the run ends. Each call
    creates its own K8s ApiClient and S3 client: the default shared pool (maxsize=4)
    deadlocks under 14+ concurrent threads.
    """
    api_client = k8s_client.ApiClient()
    batch_api = k8s_client.BatchV1Api(api_client=api_client)
    core_api = k8s_client.CoreV1Api(api_client=api_client)
    s3 = _make_s3_client()
    bucket = settings.S3_BUCKET_NAME
    pending_key = None

    try:
        endpoint_type = url.rstrip("/").split("/")[-1]
        hostname = url.split("//")[1].split(":")[0]

        job_id = uuid.uuid4().hex
        completed_key = f"jobs/completed/{job_id}.json"

        payload_bytes = json.dumps(local_payload).encode()
        payload_env = payload_bytes.decode()
        if len(payload_bytes) > PAYLOAD_ENV_MAX_BYTES:
            pending_key = f"jobs/pending/{job_id}.json"
            s3.put_object(Bucket=bucket, Key=pending_key, Body=payload_bytes,
                          ContentLength=len(payload_bytes))
            payload_env = None
        logger.info(f"[K8s] Preparing job for {sim_name} (payload: {len(payload_bytes)} bytes "
                    f"{'in S3' if pending_key else 'in env'}, job_id={job_id})")

        active_deadline = timeout_seconds + settings.RUNNER_DEADLINE_BUFFER_SEC
        job = _build_job_spec(sim_name, hostname, job_id, endpoint_type, payload_env,
                              active_deadline_seconds=active_deadline)
        job_name = job.metadata.name

        _create_job(batch_api, core_api, namespace, job)
        logger.info(f"[K8s] Spawned job '{job_name}' for {sim_name} (job_id={job_id})")
        if status_callback:
            status_callback("spawning")

        try:
            return _await_job(batch_api, core_api, namespace, job_name, sim_name, job_id,
                              s3, bucket, completed_key, timeout_seconds, status_callback)
        except Exception:
            _delete_job(batch_api, core_api, namespace, job_name)
            raise
    finally:
        if pending_key:
            _delete_s3_object(s3, bucket, pending_key)
        api_client.close()


def _await_job(batch_api, core_api, namespace: str, job_name: str, sim_name: str, job_id: str,
               s3, bucket: str, completed_key: str, timeout_seconds: int, status_callback) -> dict:
    """Poll a created Job to its end and return its result or the failure that ended it."""
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
    pending = _pending_pod_state(core_api, namespace, job_name) if terminal_state == "timeout_pending" else None
    if timed_out:
        _delete_job(batch_api, core_api, namespace, job_name)

    if status_callback:
        status_callback("timeout" if timed_out else "error")
    if terminal_state == "timeout_no_pod":
        refused = _pod_refusal_resource(core_api, namespace, job_name)
        if refused:
            result = _k8s_error(sim_name, (
                f"TIMEOUT: the cluster's resource quota did not admit a pod for the {sim_name} "
                f"Job ({refused}) within {timeout_seconds} s; the run never started."), "timeout")
            result.update(never_started=True, timed_out=True)
            return result
        return _k8s_error(sim_name, f"UNAVAILABLE: Kubernetes created no pod for the {sim_name} Job within {timeout_seconds} s.", "offline")
    if terminal_state == "timeout_pending":
        result = _pending_result(sim_name, *pending, timeout_seconds)
        if status_callback and result["dispatch_status"] == "offline":
            status_callback("offline")
        return result
    if timed_out:
        return _k8s_error(sim_name, f"TIMEOUT ({timeout_seconds}s): the Kubernetes Job (scheduling, image pull, SDK import, warm-up and timed run) did not complete within {timeout_seconds} s.", "timeout")
    return _k8s_error(sim_name, "Runner pod completed but S3 result was not found.", "error")


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
