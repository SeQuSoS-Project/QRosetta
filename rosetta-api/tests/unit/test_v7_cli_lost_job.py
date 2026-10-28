"""V7(e) Failure injection, the CLI while the API restarts mid-job (WM#3): polls ride out an
outage of proxy 502 pages or refused connections with backoff, on a virtual clock; a job the
restarted server no longer has ends the wait with exit 14 `job_lost`, STATUS `job-lost`, the
planned jobs not submitted and how to run the plan again, and is not waited for again; an
outage longer than 5 minutes is exit 11; no HTML page is printed and nothing ends as an internal
error."""

import json
import os

import pytest

from tests.unit._qrosetta_scripted import Scripted, _json

from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.client import results, waiting  # noqa: E402
from qrosetta_cli.client.transport import Response, Transient  # noqa: E402
from qrosetta_cli.errors import Exit  # noqa: E402

from tests.unit.test_qrosetta_contracts import validate_envelope  # noqa: E402

QASM = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'
NGINX_502 = (b"<html>\r\n<head><title>502 Bad Gateway</title></head>\r\n<body>\r\n<center><h1>502 Bad Gateway"
             b"</h1></center>\r\n<hr><center>nginx</center>\r\n</body>\r\n</html>\r\n")


class Clock:
    """A virtual clock that waiting.pause advances."""

    def __init__(self):
        self.now = 0.0

    def pause(self, seconds):
        self.now += seconds

    def clock(self):
        return self.now


@pytest.fixture
def vclock(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(waiting, "pause", clock.pause)
    monkeypatch.setattr(waiting, "clock", clock.clock)
    return clock


@pytest.fixture
def env(tmp_path):
    return {"HOME": str(tmp_path), "XDG_STATE_HOME": str(tmp_path / "state"), "XDG_CONFIG_HOME": str(tmp_path / "cfg"),
            "XDG_RUNTIME_DIR": str(tmp_path / "run"), "QROSETTA_RESULTS_DIR": str(tmp_path / "res")}


@pytest.fixture
def circuit(tmp_path):
    path = tmp_path / "bell.qasm"
    path.write_text(QASM)
    return str(path)


class Restarting(Scripted):
    """Jobs run for ``running_polls`` polls; then the API is down for ``down_sec`` virtual seconds
    (``outage``: an nginx 502 page or no connection), and comes back without its jobs unless
    ``keeps_jobs``."""

    def __init__(self, clock, down_sec=60.0, outage="nginx", keeps_jobs=False, running_polls=1, **kwargs):
        super().__init__(polls=10 ** 6 if not keeps_jobs else running_polls + 1, **kwargs)
        self.clock, self.down_sec, self.outage, self.keeps_jobs = clock, down_sec, outage, keeps_jobs
        self.running_polls = running_polls
        self.down_from = None
        self.outage_answers = 0

    def request(self, method, path, query=None, body=None, headers=None, timeout=None):
        parts = path.split("/")
        polling = method == "GET" and len(parts) == 3 and parts[1] == "jobs"
        if polling and parts[2] in self.jobs and self.jobs[parts[2]]["polls"] >= self.running_polls:
            if self.down_from is None:
                self.down_from = self.clock.now
            if self.clock.now - self.down_from < self.down_sec:
                self.log.append((method, path, query))
                self.outage_answers += 1
                if self.outage == "nginx":
                    return Response(502, {"content-type": "text/html"}, NGINX_502)
                raise Transient(f"No answer from {self.url}: [Errno 111] Connection refused.", Exit.UNREACHABLE,
                                "unreachable", hint="qrosetta status")
            if not self.keeps_jobs:
                self.jobs.clear()
        return super().request(method, path, query=query, body=body, headers=headers, timeout=timeout)


def run(argv, env, server):
    return main(argv, env=env, transport_factory=server)


def envelope(capsys):
    captured = capsys.readouterr()
    doc = json.loads(captured.out)
    validate_envelope(doc)
    return doc, captured.err


def _job_dirs(env):
    root = env["QROSETTA_RESULTS_DIR"]
    invs = sorted(os.path.join(root, d) for d in os.listdir(root) if d != "latest")
    return invs, [d for inv in invs for d in results.job_dirs(inv)]


@pytest.mark.parametrize("outage", ["nginx", "refused"])
def test_v7_05_a_job_lost_in_a_restart_is_exit_14_with_its_status_and_the_plan_to_rerun(
        env, circuit, capsys, vclock, outage):
    server = Restarting(vclock, down_sec=60.0, outage=outage)
    code = run(["run", circuit, "--json"], env, server)
    doc, err = envelope(capsys)
    assert code == Exit.NOT_FOUND
    assert doc["error"]["reason"] == "job_lost"
    (inv,), (job_dir,) = _job_dirs(env)
    message = doc["error"]["message"]
    assert message.startswith("The server no longer has job ")
    assert ": it restarted while the job ran (a restart loses every job in progress), or the job finished more " \
           "than 24 h ago. Its results are lost; " in message
    assert message.endswith(f"{job_dir}{os.sep}STATUS says job-lost.")
    assert doc["error"]["hint"] == f"qrosetta run --request {os.path.join(inv, 'plan.json')}"
    assert results.read_status(job_dir) == "job-lost"
    assert [j["status"] for j in doc["data"]["jobs"]] == ["lost"]
    assert server.outage_answers >= 4
    assert "<html" not in err and "<html" not in json.dumps(doc) and "nginx" not in err
    assert "Polling again in 12 s" in err or "Polling again in 24 s" in err
    assert run(["wait", "--all"], env, server) == Exit.NOT_FOUND
    assert "No unfinished job" in capsys.readouterr().err


def test_v7_05_later_planned_jobs_are_named_when_the_first_is_lost(env, circuit, capsys, vclock):
    server = Restarting(vclock, down_sec=20.0)
    code = run(["run", circuit, "--mode", "statevector,measured", "--json"], env, server)
    doc, _err = envelope(capsys)
    assert code == Exit.NOT_FOUND
    assert doc["error"]["message"].endswith("STATUS says job-lost. 1 planned job not submitted.")
    assert [p for m, p, _ in server.log if m == "POST" and p != "/plan"] == ["/compare"]


def test_v7_05_wait_reports_a_job_lost_while_it_waited(env, circuit, capsys, vclock):
    server = Restarting(vclock, down_sec=30.0)
    server.running_polls = 10 ** 6
    assert run(["run", circuit, "--detach"], env, server) == 0
    capsys.readouterr()
    server.running_polls = 1
    for job in server.jobs.values():
        job["polls"] = 0
    code = run(["wait", "--json"], env, server)
    doc, _err = envelope(capsys)
    assert code == Exit.NOT_FOUND and doc["error"]["reason"] == "job_lost"
    assert doc["error"]["code"] == "not_found"
    (_inv,), (job_dir,) = _job_dirs(env)
    assert results.read_status(job_dir) == "job-lost"


def test_a_restart_that_keeps_the_job_is_ridden_out(env, circuit, capsys, vclock):
    server = Restarting(vclock, down_sec=90.0, outage="refused", keeps_jobs=True, running_polls=2)
    assert run(["run", circuit, "--json"], env, server) == 0
    doc, _err = envelope(capsys)
    (job,) = doc["data"]["jobs"]
    assert job["status"] == "completed" and results.read_status(job["dir"]) == "complete"
    assert server.outage_answers >= 4


def test_an_outage_longer_than_five_minutes_is_exit_11_and_the_job_can_be_waited_for(env, circuit, capsys,
                                                                                      vclock):
    server = Restarting(vclock, down_sec=10 ** 9, outage="nginx")
    code = run(["run", circuit, "--json"], env, server)
    doc, err = envelope(capsys)
    assert code == Exit.UNREACHABLE and doc["error"]["reason"] == "unreachable"
    message = doc["error"]["message"]
    assert message.startswith("No answer from http://localhost:8080 for 5 minutes while waiting for job ")
    assert message.endswith("The job may still be running there.")
    assert "an HTML error page from a proxy in front of the API; the API may be stopped or restarting" in message
    assert doc["error"]["hint"].startswith("qrosetta wait job:")
    assert 300 <= vclock.now - server.down_from <= 300 + 30 + 2 * 7
    assert "<html" not in err and "<html" not in json.dumps(doc)
    (_inv,), (job_dir,) = _job_dirs(env)
    assert results.read_status(job_dir) is None


def test_v7_06_an_html_error_page_is_named_not_printed(env, capsys, vclock):
    server = Scripted()
    server.routes[("GET", "/runners")] = lambda payload, query: Response(502, {"content-type": "text/html"}, NGINX_502)
    assert run(["backends", "--json"], env, server) not in (Exit.OK, Exit.INTERNAL)
    doc, err = envelope(capsys)
    assert "<html" not in json.dumps(doc) and "<html" not in err
    assert "an HTML error page from a proxy in front of the API; the API may be stopped or restarting" in \
        doc["error"]["message"]


def test_a_404_on_the_first_poll_is_still_a_lost_job(env, circuit, capsys, vclock):
    server = Scripted()
    original = server.request

    def request(method, path, query=None, body=None, headers=None, timeout=None):
        if method == "GET" and path.startswith("/jobs/") and path.count("/") == 2:
            return _json(404, {"detail": "Job not found."})
        return original(method, path, query, body, headers, timeout)

    server.request = request
    assert run(["run", circuit, "--json"], env, server) == Exit.NOT_FOUND
    doc, _err = envelope(capsys)
    assert doc["error"]["reason"] == "job_lost"
    assert doc["error"]["message"].startswith("The server no longer has job ")
