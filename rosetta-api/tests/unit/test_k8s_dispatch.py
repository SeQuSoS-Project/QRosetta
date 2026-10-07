"""Kubernetes dispatch: payload delivery, pod polling, pending pods, result fetch, Job
creation, resources, forwarded limits and image references."""

import io
import json
from types import SimpleNamespace

import pytest
from kubernetes.client.rest import ApiException

from services import dispatcher_k8s as k8s


class FakeS3:
    def __init__(self, objects=None, fail_delete=False):
        self.objects = dict(objects or {})
        self.puts, self.deleted = [], []
        self.fail_delete = fail_delete

    def put_object(self, Bucket, Key, Body, ContentLength):
        assert ContentLength == len(Body)
        self.puts.append(Key)
        self.objects[Key] = Body

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise KeyError(Key)
        return {"Body": io.BytesIO(self.objects[Key])}

    def delete_object(self, Bucket, Key):
        if self.fail_delete:
            raise RuntimeError("delete refused")
        self.deleted.append(Key)
        self.objects.pop(Key, None)


def _pod(phase="Pending", conditions=None, waiting=None):
    statuses = None
    if waiting is not None:
        statuses = [SimpleNamespace(state=SimpleNamespace(waiting=SimpleNamespace(reason=waiting)))]
    return SimpleNamespace(status=SimpleNamespace(phase=phase, conditions=conditions,
                                                  container_statuses=statuses))


class FakeCore:
    def __init__(self, listings):
        self.listings = list(listings)

    def list_namespaced_pod(self, **_k):
        item = self.listings.pop(0) if len(self.listings) > 1 else self.listings[0]
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(items=item)

    def list_namespaced_event(self, **_k):
        return SimpleNamespace(items=[])


class FakeBatch:
    def __init__(self, create_error=None, read_error=None):
        self.created, self.deleted = [], []
        self.create_error, self.read_error = create_error, read_error

    def create_namespaced_job(self, namespace, body, _request_timeout):
        self.created.append(body)
        if self.create_error:
            raise self.create_error

    def read_namespaced_job(self, name, namespace, _request_timeout):
        if self.read_error:
            raise self.read_error
        return SimpleNamespace()

    def delete_namespaced_job(self, name, namespace, propagation_policy, _request_timeout):
        self.deleted.append(name)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(k8s.time, "sleep", lambda *_a: None)


def _env(job):
    return {e.name: e.value for e in job.spec.template.spec.containers[0].env}


def _run_inner(monkeypatch, payload, s3, batch, core):
    monkeypatch.setattr(k8s, "_make_s3_client", lambda: s3)
    monkeypatch.setattr(k8s.k8s_client, "ApiClient", lambda: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(k8s.k8s_client, "BatchV1Api", lambda api_client: batch)
    monkeypatch.setattr(k8s.k8s_client, "CoreV1Api", lambda api_client: core)
    return k8s._run_k8s_job_inner("qiskit", "http://pytket-qiskit-runner:8000/run", payload, 5, "ns")


def _succeeding(s3, batch):
    """A core API whose pod succeeds after writing ``{"ok": 1}`` to the completed key."""
    def listing(**_k):
        job_id = batch.created[-1].spec.template.spec.containers[0].command[-1]
        s3.objects[f"jobs/completed/{job_id}.json"] = b'{"ok": 1}'
        return SimpleNamespace(items=[_pod("Succeeded")])
    return SimpleNamespace(list_namespaced_pod=listing, list_namespaced_event=None)


def test_small_payload_travels_in_the_environment(monkeypatch):
    s3, batch = FakeS3(), FakeBatch()
    result = _run_inner(monkeypatch, {"circuit_data": "x" * 100}, s3, batch, _succeeding(s3, batch))
    assert result == {"ok": 1}
    assert json.loads(_env(batch.created[0])["QROSETTA_PAYLOAD"]) == {"circuit_data": "x" * 100}
    assert s3.puts == []


def test_large_payload_goes_to_the_pending_key_and_is_deleted(monkeypatch):
    s3, batch = FakeS3(), FakeBatch()
    payload = {"circuit_data": "h q[0];\n" * 20000}
    result = _run_inner(monkeypatch, payload, s3, batch, _succeeding(s3, batch))
    assert result == {"ok": 1}
    job = batch.created[0]
    job_id = job.spec.template.spec.containers[0].command[-1]
    assert "QROSETTA_PAYLOAD" not in _env(job)
    assert s3.puts == [f"jobs/pending/{job_id}.json"]
    assert f"jobs/pending/{job_id}.json" in s3.deleted
    assert len(json.dumps(payload)) > k8s.PAYLOAD_ENV_MAX_BYTES


def test_runner_reads_the_pending_key_without_the_environment_variable(monkeypatch):
    import sys
    from qrosetta_commons import helpers
    s3 = FakeS3({"jobs/pending/abc.json": b'{"circuit_data": "c"}'})
    monkeypatch.setitem(sys.modules, "boto3", SimpleNamespace(client=lambda *a, **k: s3))
    monkeypatch.delenv("QROSETTA_PAYLOAD", raising=False)
    seen = []
    helpers.run_cli_job(lambda p: seen.append(p) or {"done": True},
                        SimpleNamespace(s3_job_id="abc", payload=None), None)
    assert seen == [{"circuit_data": "c"}]
    assert json.loads(s3.objects["jobs/completed/abc.json"]) == {"done": True}


def test_largest_bundled_benchmark_exceeds_the_environment_threshold():
    from pathlib import Path
    sizes = [p.stat().st_size for p in Path("benchmarks").rglob("*.qasm")]
    assert sizes and max(sizes) > k8s.PAYLOAD_ENV_MAX_BYTES
    assert k8s.PAYLOAD_ENV_MAX_BYTES < 131072 - len("QROSETTA_PAYLOAD=") - 1


def test_transient_listing_failure_does_not_disable_pod_polling():
    core = FakeCore([ApiException(status=500), TimeoutError(), [_pod("Succeeded")]])
    state = k8s._poll_pod_phase(core, "ns", "job", "qiskit", "id", FakeS3(), "b", "k",
                                k8s.time.time() + 30, None)
    assert state == "succeeded"


def test_forbidden_listing_falls_back_to_s3():
    s3 = FakeS3({"k": b'{"statevector": "x"}'})
    core = FakeCore([ApiException(status=403)])
    state = k8s._poll_pod_phase(core, "ns", "job", "qiskit", "id", s3, "b", "k",
                                k8s.time.time() + 30, None)
    assert state == {"statevector": "x"}
    assert s3.deleted == ["k"]


def test_listing_that_never_succeeds_is_unknown(monkeypatch):
    clock = iter(range(0, 1000, 5))
    monkeypatch.setattr(k8s.time, "time", lambda: next(clock))
    core = FakeCore([ApiException(status=500)])
    assert k8s._poll_pod_phase(core, "ns", "job", "q", "id", FakeS3(), "b", "k", 20, None) == "timeout_unknown"


@pytest.mark.parametrize("pod, state", [
    (_pod(conditions=[SimpleNamespace(type="PodScheduled", status="False", reason="Unschedulable",
                                      message="0/5 nodes are available: insufficient cpu")]), "unschedulable"),
    (_pod(waiting="ImagePullBackOff"), "image_pull_failed"),
    (_pod(waiting="ContainerCreating"), "starting"),
    (_pod(), "starting"),
])
def test_pending_pod_classified(pod, state):
    assert k8s._pending_pod_state(FakeCore([[pod]]), "ns", "job")[0] == state


@pytest.mark.parametrize("state, status, never_started", [
    ("unschedulable", "timeout", True),
    ("image_pull_failed", "offline", None),
    ("starting", "timeout", None),
    (None, "offline", None),
])
def test_pending_result_status(state, status, never_started):
    result = k8s._pending_result("qiskit", state, "detail", 60)
    assert result["dispatch_status"] == status
    assert result.get("never_started") is never_started


def test_pod_still_pulling_at_deadline_is_a_timeout(monkeypatch):
    clock = iter(range(0, 1000, 3))
    monkeypatch.setattr(k8s.time, "time", lambda: next(clock))
    s3, batch = FakeS3(), FakeBatch()
    core = FakeCore([[_pod(waiting="ContainerCreating")]])
    result = _run_inner(monkeypatch, {}, s3, batch, core)
    assert result["dispatch_status"] == "timeout"
    assert "still starting" in result["error"]
    assert batch.deleted == [batch.created[0].metadata.name]


def test_result_kept_when_delete_fails():
    s3 = FakeS3({"k": b'{"counts": {"0": 1}}'}, fail_delete=True)
    assert k8s._fetch_s3_result(s3, "b", "k", "q", None) == {"counts": {"0": 1}}


def _job():
    return k8s._build_job_spec("qiskit", "pytket-qiskit-runner", "0123456789abcdef", "run", "{}")


def test_create_timeout_with_job_present_counts_as_created():
    batch = FakeBatch(create_error=TimeoutError("read timed out"))
    k8s._create_job(batch, FakeCore([[]]), "ns", _job())
    assert batch.deleted == []


def test_create_timeout_with_job_absent_raises():
    batch = FakeBatch(create_error=TimeoutError(), read_error=ApiException(status=404))
    with pytest.raises(TimeoutError):
        k8s._create_job(batch, FakeCore([[]]), "ns", _job())
    assert batch.deleted == []


def test_create_timeout_with_job_unknown_deletes_it():
    batch = FakeBatch(create_error=TimeoutError(), read_error=ConnectionError())
    with pytest.raises(TimeoutError):
        k8s._create_job(batch, FakeCore([[]]), "ns", _job())
    assert batch.deleted == [_job().metadata.name]


def test_create_rejected_is_not_looked_up():
    batch = FakeBatch(create_error=ApiException(status=422), read_error=AssertionError("looked up"))
    with pytest.raises(ApiException):
        k8s._create_job(batch, FakeCore([[]]), "ns", _job())


def _quantity(value: str) -> float:
    units = {"m": 1e-3, "Mi": 2 ** 20, "Gi": 2 ** 30}
    for suffix, factor in units.items():
        if value.endswith(suffix):
            return float(value[:-len(suffix)]) * factor
    return float(value)


@pytest.mark.parametrize("endpoint, memory", [("run", "1Gi"), ("run_measured", "1Gi"), ("compile", "2Gi")])
def test_job_resources(endpoint, memory):
    res = k8s.job_resources(endpoint)
    assert res["limits"]["memory"] == memory
    assert res["limits"]["cpu"] == "1000m"
    assert _quantity(res["limits"]["cpu"]) / _quantity(res["requests"]["cpu"]) <= 5
    job = k8s._build_job_spec("cirq-transformers", "cirq-compiler", "0" * 32, endpoint, "{}")
    assert job.spec.template.spec.containers[0].resources.limits["memory"] == memory


def test_job_env_carries_limits_and_s3_settings(monkeypatch):
    monkeypatch.setattr(k8s.settings, "MAX_QUBITS_STATEVECTOR", 11)
    monkeypatch.setattr(k8s.settings, "MAX_QUBITS_MEASURED", 12)
    monkeypatch.setattr(k8s.settings, "MAX_QUBITS_COMPILE", 13)
    monkeypatch.setattr(k8s.settings, "S3_ENDPOINT_URL", "https://s3.example")
    monkeypatch.setenv("S3_ENDPOINT_URL", "https://wrong.example")
    env = _env(_job())
    assert (env["MAX_QUBITS_STATEVECTOR"], env["MAX_QUBITS_MEASURED"], env["MAX_QUBITS_COMPILE"]) == ("11", "12", "13")
    assert env["S3_ENDPOINT_URL"] == "https://s3.example"


DIGEST = "sha256:" + "ab" * 32


@pytest.mark.parametrize("digests, expected", [
    ({"pytket-qiskit-runner": {"digest": DIGEST, "source": "pushed by this deploy"}}, f"reg/pytket-qiskit-runner@{DIGEST}"),
    ({"pytket-qiskit-runner": DIGEST}, f"reg/pytket-qiskit-runner@{DIGEST}"),
    ({"pytket-qiskit-runner": {"digest": "latest"}}, "reg/pytket-qiskit-runner:abc1234"),
    ({}, "reg/pytket-qiskit-runner:abc1234"),
])
def test_image_reference_uses_the_recorded_digest(monkeypatch, digests, expected):
    monkeypatch.setenv("K8S_IMAGE_REGISTRY", "reg")
    monkeypatch.setenv("QROSETTA_IMAGE_DIGESTS", json.dumps(digests))
    monkeypatch.setattr(k8s, "IMAGE_TAG", "abc1234")
    assert k8s.runner_image_ref("pytket-qiskit-runner") == expected
    job = k8s._build_job_spec("qiskit", "pytket-qiskit-runner", "0" * 32, "run", "{}")
    assert job.spec.template.spec.containers[0].image == expected


def test_deploy_script_records_digests_and_dirty_checkouts():
    from pathlib import Path
    script = (Path(__file__).resolve().parents[3] / "scripts" / "rahti_push.sh").read_text()
    assert 'QROSETTA_IMAGE_DIGESTS="$DIGESTS_JSON"' in script
    assert 'QROSETTA_GIT_SHA="$DEPLOY_GIT_SHA"' in script
    assert 'DEPLOY_GIT_SHA="${HEAD_SHA}-dirty"' in script
    assert "retagged, not rebuilt" in script
