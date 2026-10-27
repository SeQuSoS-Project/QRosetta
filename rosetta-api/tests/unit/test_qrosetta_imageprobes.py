"""qrosetta selftest's image probes: one fresh probe round of GET /runners and GET /compilers with
the lifecycle token, each image's answer, registry fields and commit checked, reported per image
in the output and in selftest.json; and the CPU quota rule read from the stack setting."""

import json
import os

import pytest

from tests.unit._qrosetta_scripted import _json
from tests.unit.test_qrosetta_runs import _evaluation, _selftest_server, envelope, run

from qrosetta_cli import localstack  # noqa: E402
from qrosetta_cli.client import imageprobes, waiting  # noqa: E402
from qrosetta_cli.errors import Exit  # noqa: E402


@pytest.fixture(autouse=True)
def no_pause(monkeypatch):
    monkeypatch.setattr(waiting, "pause", lambda seconds: None)


@pytest.fixture
def env(tmp_path):
    return {"HOME": str(tmp_path), "XDG_STATE_HOME": str(tmp_path / "state"), "XDG_CONFIG_HOME": str(tmp_path / "cfg"),
            "XDG_RUNTIME_DIR": str(tmp_path / "run"), "QROSETTA_RESULTS_DIR": str(tmp_path / "res")}


REGISTRY = {"precision": {"statevector": "complex128", "measured": "complex128"},
            "qubit_ordering": {"statevector": "lsb", "measured": "lsb"}}


def runner(key, sha="abc1234", source="built_locally", **extra):
    versions = {"image_git_sha": sha, "image_identity": {"source": source, "release": None, "git_sha": sha}}
    row = {"id": key, "enabled": True, "available": True, "default_selected": True, "fresh": True,
           "reason": None, "error_kind": None, "probed_at": "2026-10-27T15:05:00Z", "versions": versions,
           "optimization_levels": {"0": ""}, **REGISTRY}
    row.update(extra)
    return row


def compiler(key, sha="abc1234"):
    return {"id": key, "enabled": True, "available": True, "fresh": True, "reason": None, "error_kind": None,
            "probed_at": "2026-10-27T15:05:00Z", "versions": {"image_git_sha": sha, "sdk_versions": {}}}


def server_with(runners, compilers=(), fresh_status=200):
    server = _selftest_server({"statevector": _evaluation("statevector"), "measured": _evaluation("measured")})
    server.seen = []
    inner = server.request

    def request(method, path, query=None, body=None, headers=None, timeout=None):
        if path in ("/runners", "/compilers"):
            server.seen.append((path, query, dict(headers or {})))
            if query and query.get("fresh"):
                if fresh_status != 200:
                    return _json(fresh_status, {"detail": "no"})
                return _json(200, list(runners if path == "/runners" else compilers))
            return _json(200, [{k: v for k, v in r.items() if k not in ("fresh", "reason", "error_kind",
                                                                         "probed_at")} for r in runners])
        return inner(method, path, query, body, headers, timeout)

    server.request = request
    return server


def token(env):
    os.makedirs(os.path.dirname(localstack.token_path(env)), exist_ok=True)
    with open(localstack.token_path(env), "w") as fh:
        fh.write("tok-123\n")


def test_probes_pass_and_send_the_lifecycle_token(env, capsys):
    token(env)
    server = server_with([runner("qiskit"), runner("cirq"), runner("qulacs")], [compiler("pyzx")])
    assert run(["selftest", "--json"], env, server) == 0
    doc = envelope(capsys)
    fresh = [(p, h) for p, q, h in server.seen if q == {"fresh": "true"}]
    assert [p for p, _ in fresh] == ["/runners", "/compilers"]
    assert all(h.get("Authorization") == "Bearer tok-123" for _, h in fresh)
    block = doc["data"]["image_probes"]
    assert block["status"] == "probed" and block["server_git_sha"] == "abc1234"
    assert [(i["id"], i["kind"], i["status"]) for i in block["images"]] == [
        ("qiskit", "runner", "PASS"), ("cirq", "runner", "PASS"), ("qulacs", "runner", "PASS"),
        ("pyzx", "compiler", "PASS")]
    qiskit = block["images"][0]
    assert [c["check"] for c in qiskit["checks"]] == ["answers", "registry", "commit"]
    assert qiskit["checks"][2]["reason"] == "built locally from abc1234, as the API"
    assert doc["data"]["lines"][0] == "Images      3 runners and 1 compiler probed now: 4 passed, 0 warned, 0 failed"
    selftest = json.load(open(os.path.join(doc["data"]["results_dir"], "selftest.json")))
    assert selftest["image_probes"] == block


def test_a_dirty_or_other_commit_and_a_bad_registry_value_are_reported_per_image(env, capsys):
    token(env)
    bad = dict(REGISTRY["precision"], measured="float16")
    server = server_with([runner("qiskit", sha="0ld9999"), runner("cirq", sha="abc1234-dirty"),
                          runner("qulacs", precision=bad)])
    assert run(["selftest", "--json"], env, server) == Exit.SELFTEST_FAILED
    data = envelope(capsys)["data"]
    assert [i["status"] for i in data["image_probes"]["images"]] == ["WARN", "FAIL", "FAIL"]
    assert "image commit (qiskit): built locally from 0ld9999; the API image is from abc1234 (a mixed stack)" \
        in data["warnings"]
    assert any(f.startswith("image commit (cirq): built from uncommitted changes") for f in data["failures"])
    assert "image registry (qulacs): the registry declares measured precision float16" in data["failures"]


def test_images_that_do_not_report_their_commit_are_skipped_and_named(env, capsys):
    token(env)
    old = runner("qulacs")
    old.pop("versions")
    server = server_with([runner("qiskit"), runner("cirq"), old])
    assert run(["selftest"], env, server) == 0
    out = capsys.readouterr().out
    assert "Images      3 runners probed now: 3 passed, 0 warned, 0 failed" in out
    assert "commit not checked for qulacs: its probe row does not carry the image's commit" in out


def test_a_busy_image_is_skipped_and_an_unreachable_one_fails(env, capsys):
    token(env)
    rows = [runner("qiskit", reason="busy", fresh=False, probed_at=None), runner("cirq"), runner("qulacs")]
    assert run(["selftest", "--json"], env, server_with(rows)) == 0
    images = envelope(capsys)["data"]["image_probes"]["images"]
    assert images[0]["status"] == "PASS" and images[0]["checks"][0]["status"] == "SKIP"
    check = imageprobes.check_image(runner("cirq", available=False, error_kind="dns"), "runner", "abc1234")
    assert check["status"] == "FAIL" and "cannot resolve" in check["checks"][0]["reason"]
    assert imageprobes.check_image(None, "runner", "abc1234", "quimb")["checks"][0]["status"] == "FAIL"


def test_without_fresh_probes_the_images_are_not_probed(env, capsys):
    server = server_with([runner("qiskit"), runner("cirq"), runner("qulacs")], fresh_status=401)
    assert run(["selftest", "--json"], env, server) == 0
    data = envelope(capsys)["data"]
    assert data["image_probes"]["status"] == "not_probed" and data["image_probes"]["images"] == []
    assert data["lines"][0].startswith("Images      not probed: fresh probes need the lifecycle token")
    assert not data["warnings"]
    assert run(["selftest", "--no-images", "--json"], env, server_with([runner("qiskit")])) == 0
    assert envelope(capsys)["data"]["lines"][0] == "Images      skipped (--no-images)"


def test_the_cpu_quota_rule_reads_the_stack_setting(env, capsys):
    quota = {"check": "cpu_quota_cores", "status": "FAIL", "reason": "null", "backend": "qiskit"}
    localstack.write_stack_settings(env, "qsimulators", {"cpu_quota": False, "since": "2026-10-27T10:00:00Z"})
    server = _selftest_server({"statevector": _evaluation("statevector", env_rows=[dict(quota)]),
                               "measured": _evaluation("measured")})
    assert run(["selftest", "--json"], env, server) == 0
    data = envelope(capsys)["data"]
    assert data["cli_rules_applied"] == [{"rule": "cpu_quota_off", "backend": "qiskit"}]
    assert any("stack started without the CPU quota" in w for w in data["warnings"])
