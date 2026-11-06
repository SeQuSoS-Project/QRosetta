"""The terminal layout of qrosetta's checks and errors: marks on a UTF-8 terminal and the words
PASS/FAIL/WARN/INFO elsewhere, colour by NO_COLOR, CLICOLOR_FORCE, TERM and [output] color,
doctor's numbered fixes in the order to apply them and its next step, start's pre-checks
(which stop before compose), the self-test's "not started" wording, and the JSON left as it was."""

import io
import json
import subprocess

import pytest

from tests.unit._qrosetta_fake import FakeEngine, FakeServer, Unreachable, ours
from tests.unit.test_qrosetta_contracts import validate_envelope
from tests.unit.test_qrosetta_doctor import CONTROLLERS, FakeHost, _doctor

from qrosetta_cli import config as cfgmod  # noqa: E402
from qrosetta_cli import layout, output  # noqa: E402
from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.client import selftest  # noqa: E402
from qrosetta_cli.context import Context  # noqa: E402
from qrosetta_cli.errors import CliError, Exit  # noqa: E402
from qrosetta_cli.stack import doctor, preflight  # noqa: E402
from qrosetta_cli.stack.engine import Engine  # noqa: E402


class Stream(io.StringIO):
    def __init__(self, tty, encoding):
        super().__init__()
        self._tty, self._encoding = tty, encoding

    def isatty(self):
        return self._tty

    @property
    def encoding(self):
        return self._encoding


@pytest.fixture
def env(tmp_path):
    return {"QROSETTA_PROJECT": "qr", "HOME": str(tmp_path / "home"), "XDG_RUNTIME_DIR": str(tmp_path / "run"),
            "XDG_STATE_HOME": str(tmp_path / "state"), "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "XDG_CACHE_HOME": str(tmp_path / "cache")}


@pytest.fixture
def project(tmp_path):
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    return tmp_path


# --- marks, words and colour -----------------------------------------------------------------


@pytest.mark.parametrize("tty,encoding,marks", [(True, "utf-8", True), (True, "UTF8", True),
                                                (True, "ascii", False), (True, "latin-1", False),
                                                (False, "utf-8", False), (True, None, False)])
def test_marks_only_on_a_utf8_terminal(tty, encoding, marks):
    assert output.use_marks(Stream(tty, encoding)) is marks


@pytest.mark.parametrize("setting,env,tty,color", [
    ("auto", {}, True, True), ("auto", {}, False, False),
    ("auto", {"NO_COLOR": "1"}, True, False), ("auto", {"NO_COLOR": ""}, True, True),
    ("auto", {"TERM": "dumb"}, True, False),
    ("auto", {"CLICOLOR_FORCE": "1"}, False, True), ("auto", {"CLICOLOR_FORCE": "0"}, False, False),
    ("auto", {"CLICOLOR_FORCE": "1", "NO_COLOR": "1"}, True, False),
    ("never", {}, True, False), ("never", {"CLICOLOR_FORCE": "1"}, True, False),
    ("always", {}, False, True), ("always", {"NO_COLOR": "1"}, True, False),
])
def test_colour_follows_no_color_clicolor_force_term_and_the_config(setting, env, tty, color):
    output.configure(color=setting, env=env)
    assert output.use_color(Stream(tty, "utf-8")) is color


def test_rows_print_marks_or_the_words_as_before():
    items = [("PASS", "os", "Linux x86_64"), ("FAIL", "podman socket", "no socket"), ("INFO", "gpu", "a\nb")]
    assert layout.rows(items, marks=True, color=False) == [
        "  ✓  os             Linux x86_64", "  ✗  podman socket  no socket", "  ·  gpu            a",
        "                    b"]
    assert layout.rows(items, marks=False, color=False) == [
        "PASS  os             Linux x86_64", "FAIL  podman socket  no socket", "INFO  gpu            a",
        "                     b"]
    coloured = layout.rows(items[:2], marks=True, color=True)
    assert coloured[0].startswith("  \033[32m✓\033[0m") and coloured[1].startswith("  \033[31m✗\033[0m")
    assert "\033" not in "".join(layout.rows(items, marks=False, color=False))


def test_doctor_prints_words_when_piped_and_marks_on_a_utf8_terminal(env, monkeypatch, capsys):
    monkeypatch.setattr(doctor, "Host", lambda e: FakeHost(env))
    assert main(["doctor"], env=dict(env, NO_COLOR="1"), transport_factory=Unreachable()) == 0
    out = capsys.readouterr().out
    assert "PASS  os" in out and "✓" not in out and "\033" not in out
    monkeypatch.setattr(output, "use_marks", lambda stream=None: True)
    assert main(["doctor"], env=dict(env, NO_COLOR="1"), transport_factory=Unreachable()) == 0
    out = capsys.readouterr().out
    assert "  ✓  os" in out and "PASS" not in out and "\033" not in out


def test_a_character_the_encoding_lacks_prints_as_a_question_mark_and_output_goes_on(monkeypatch):
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="ascii")
    monkeypatch.setattr("sys.stdout", stream)
    output.result("jobs  change: qrosetta config path → [lifecycle] jobs_kept")
    output.result("Next step:  qrosetta selftest")
    stream.flush()
    assert raw.getvalue().decode().splitlines() == ["jobs  change: qrosetta config path ? [lifecycle] jobs_kept",
                                                    "Next step:  qrosetta selftest"]


# --- doctor: fixes, count sentence, next step --------------------------------------------------


def _broken(env):
    """compose missing, the podman socket missing, the port in use and little disk."""
    host = FakeHost(env, compose="Error: looking up compose provider failed", port_free=False,
                    free=2 * doctor.GIB, files={"/etc/os-release": "ID=fedora\n"})
    host.paths.discard(f"{env['XDG_RUNTIME_DIR']}/podman/podman.sock")
    return host


def test_fixes_are_numbered_in_the_order_to_apply_them_and_not_printed_under_rows(env):
    rep = _doctor(env, _broken(env))
    rep.checks.reverse()
    lines = doctor.report_lines(rep)
    text = "\n".join(lines)
    numbered = [line for line in lines if line[:5].strip().rstrip(".").isdigit()]
    assert [n.split(".")[0].strip() for n in numbered] == ["1", "2", "3", "4", "5", "6"]
    assert "Install Docker Compose v2" in numbered[0] and "podman's API socket" in numbered[1]
    assert "Use port 8090" in numbered[2] and "Free space under" in numbered[3] and "Free space under" in numbered[4]
    assert numbered[5] == "  6. Set [lifecycle] job_storage lower (qrosetta config path), or free space in the image store."
    rows = lines[2:lines.index("")]
    assert not any("systemctl" in r or "dnf install" in r for r in rows)
    assert "       sudo dnf install docker-compose" in lines
    assert "       systemctl --user enable --now podman.socket" in lines
    assert "3 checks failed, 3 warnings. Resolve them, then run `qrosetta doctor` again." in lines
    assert lines[-1].startswith("Next step once all checks pass:  qrosetta ") and "\n\n  1. " in text


@pytest.mark.parametrize("failed,warned,sentence", [
    (1, 0, "1 check failed. Resolve it, then run `qrosetta doctor` again."),
    (2, 1, "2 checks failed, 1 warning. Resolve them, then run `qrosetta doctor` again."),
    (0, 2, "No check failed, 2 warnings."), (0, 0, "No check failed.")])
def test_count_sentence(failed, warned, sentence):
    assert layout.count_sentence(failed, warned, "qrosetta doctor") == sentence


def test_next_step_follows_the_stack_state(env, tmp_path, monkeypatch):
    from qrosetta_cli import mode as modes

    monkeypatch.setattr(modes, "PACKAGE_PARENT", str(tmp_path / "site-packages"))
    ctx = Context(args=type("A", (), {})(), env=env, cfg=cfgmod.Config("/none", False), transport_factory=Unreachable())
    host = FakeHost(env)
    host.images_present = lambda c: None
    assert doctor.next_command(ctx, host, True) == "qrosetta selftest"
    assert doctor.next_command(ctx, host, False) == "qrosetta pull --profile minimal"
    host.images_present = lambda c: True
    assert doctor.next_command(ctx, host, False) == "qrosetta start -d"
    host.images_present = lambda c: False
    ctx.checkout = str(tmp_path)
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    assert doctor.next_command(ctx, host, False) == "qrosetta build --profile minimal"


def test_the_port_fix_writes_or_names_the_config_file(tmp_path):
    path = tmp_path / "qrosetta" / "config.toml"
    new = doctor.port_steps(cfgmod.Config(str(path), False))
    assert new[0][0] == "Use port 8090 for this and every later command:"
    assert new[0][1] == [f"mkdir -p {tmp_path / 'qrosetta'}",
                         f"printf '[lifecycle]\\nbind = \"127.0.0.1:8090\"\\n' > {path}", "qrosetta start -d"]
    appended = doctor.port_steps(cfgmod.Config(str(path), False, {"output": {}}, loaded=True))
    assert appended[0][1][0].endswith(f">> {path}") and "\\n[lifecycle]\\n" in appended[0][1][0]
    edited = doctor.port_steps(cfgmod.Config(str(path), False, {"lifecycle": {"bind": "x"}}, loaded=True))
    assert edited[0] == (f"Use port 8090 for this and every later command. In {path}, under [lifecycle], set:",
                         ['bind = "127.0.0.1:8090"'])


def test_doctor_json_is_unchanged_and_the_terminal_report_is_not_repeated_on_stderr(env, monkeypatch, capsys):
    monkeypatch.setattr(doctor, "Host", lambda e: _broken(env))
    assert main(["doctor"], env=env, transport_factory=Unreachable()) == Exit.CHECKS_FAILED
    captured = capsys.readouterr()
    assert captured.err == "" and captured.out.splitlines()[-1].startswith("Next step once all checks pass:")
    assert main(["doctor", "--json"], env=env, transport_factory=Unreachable()) == Exit.CHECKS_FAILED
    captured = capsys.readouterr()
    doc = json.loads(captured.out)
    validate_envelope(doc)
    assert "qrosetta: 3 check(s) failed: compose, podman_socket, port." in captured.err
    assert doc["error"]["message"] == "3 check(s) failed: compose, podman_socket, port."
    assert doc["error"]["hint"] == "sudo dnf install docker-compose"
    for check in doc["data"]["checks"]:
        assert set(check) == {"id", "status", "message", "fix"}
    fixes = {c["id"]: c["fix"] for c in doc["data"]["checks"]}
    assert fixes["podman_socket"] == "systemctl --user enable --now podman.socket"
    assert fixes["port"].startswith("qrosetta start -d --bind 127.0.0.1:8090\nLater commands use")


# --- start's pre-checks --------------------------------------------------------------------------


def _cli(fake, project, env, argv, host, server=None):
    return main(argv, checkout=str(project), env=env, tty=False,
                engine_factory=lambda d: Engine(fake.engine, d, run=fake, popen=fake.popen, env=env),
                transport_factory=server or Unreachable(), host_factory=lambda e: host)


def _stopped():
    fake = FakeEngine().standard()
    for c in fake.containers.values():
        c["State"]["Running"] = False
    return fake


def test_start_stops_before_compose_when_a_check_fails(project, env, capsys):
    fake = _stopped()
    assert _cli(fake, project, env, ["start", "-d"], FakeHost(env, port_free=False)) == Exit.ENGINE
    assert fake.calls == []
    err = capsys.readouterr().err
    lines = err.splitlines()
    assert lines[0] == "qrosetta: not started, because 1 check failed."
    assert "FAIL  port           127.0.0.1:8080 is in use" in lines and "PASS  engine" in err
    assert "  1. Use port 8090 for this and every later command:" in lines
    assert lines[-1] == "       qrosetta start -d" and "subuid" not in err and "disk" not in err
    assert _cli(fake, project, env, ["start", "-d", "--json"], FakeHost(env, port_free=False)) == Exit.ENGINE
    doc = json.loads(capsys.readouterr().out)
    validate_envelope(doc)
    assert doc["error"]["reason"] == "port_in_use" and doc["error"]["hint"] == "qrosetta start -d --bind 127.0.0.1:8090"
    assert fake.calls == []


def test_start_pre_checks_use_the_bind_it_will_publish_and_accept_its_own_stack(env):
    seen = []

    class Host(FakeHost):
        def port_free(self, host, port):
            seen.append((host, port))
            return False

    ctx = Context(args=type("A", (), {"bind": "127.0.0.1:9000"})(), env=env, cfg=cfgmod.Config("/none", False),
                  transport_factory=Unreachable())
    ours = Host(env, published=["127.0.0.1:8080"])
    rep = preflight.run(ctx, ours, preflight.effective_bind(ctx), True)
    assert seen == [("127.0.0.1", 9000)] and [c.id for c in rep.failed] == ["port"]
    assert rep.failed[0].reason == "port_in_use"
    assert [c.id for c in rep.checks] == ["engine", "compose", "podman_socket", "port"]
    rep = preflight.run(ctx, ours, "127.0.0.1:8080", True)
    assert not rep.failed and "running Quantum Rosetta" in rep.checks[-1].message
    assert not preflight.run(ctx, Host(env, published=["0.0.0.0:8080"]), "127.0.0.1:8080", True).failed
    assert doctor.same_address("[::]:8080", "127.0.0.1:8080")
    assert not doctor.same_address("127.0.0.1:8080", "127.0.0.1:8090")


def test_doctor_counts_the_port_as_this_stacks_while_its_api_does_not_answer(env):
    rows = [c for c in _doctor(env, FakeHost(env, port_free=False, published=["127.0.0.1:8080"])).checks
            if c.id == "port"]
    assert rows[0].status == "PASS" and "running Quantum Rosetta" in rows[0].message
    assert _doctor(env, FakeHost(env, port_free=False, published=["127.0.0.1:9000"])).failed[0].id == "port"


def test_web_addresses_reads_the_labelled_web_server_container():
    calls = []

    def run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "127.0.0.1:8080->8080/tcp, [::1]:8080->8080/tcp\n", "")

    host = doctor.Host({}, run=run)
    assert host.web_addresses("podman", "qr") == ["127.0.0.1:8080", "[::1]:8080"]
    assert calls[0][:4] == ["podman", "ps", "--format", "{{.Ports}}"]
    assert {calls[0][i + 1] for i, a in enumerate(calls[0]) if a == "--filter"} == {
        "label=com.docker.compose.project=qr", "label=org.qrosetta.project=qr", "label=org.qrosetta.id=nginx"}


@pytest.mark.parametrize("controllers,quota_on,blocked,reason", [
    ("cpu io memory pids\n", True, False, None),
    ("cpu io memory\n", True, False, None),
    ("io memory pids\n", True, True, "cpu_controller_missing"),
    ("io memory pids\n", False, False, None),
    ("cpu io pids\n", False, True, "memory_controller_missing"),
])
def test_start_refuses_on_cgroup_delegation_as_before(env, controllers, quota_on, blocked, reason):
    ctx = Context(args=type("A", (), {})(), env=env, cfg=cfgmod.Config("/none", False),
                  transport_factory=Unreachable())
    rep = preflight.run(ctx, FakeHost(env, files={CONTROLLERS: controllers}), "127.0.0.1:8080", quota_on)
    assert bool(rep.failed) is blocked
    if blocked:
        assert rep.failed[0].id == "cgroup" and rep.failed[0].reason == reason
        assert any("qrosetta start -d --no-cpu-quota" in cmds for _, cmds in rep.failed[0].steps) == (
            reason == "cpu_controller_missing")


def test_start_with_passing_checks_reaches_compose(project, env, capsys, monkeypatch):
    from qrosetta_cli.stack import serve

    monkeypatch.setattr(serve, "_sleep", lambda s: None)
    fake = _stopped()
    assert _cli(fake, project, env, ["start", "-d"], FakeHost(env), server=FakeServer(fresh=True)) == 0
    assert any("up" in c for c, _ in fake.calls)
    assert capsys.readouterr().out.splitlines()[-1] == (
        "Next step:  open http://localhost:8080 in a browser, or run `qrosetta selftest`")


# --- errors ---------------------------------------------------------------------------------------


def test_errors_with_evidence_print_what_happened_the_evidence_and_the_command_last(capsys):
    err = CliError("Not ready after 180 s: a; b.", Exit.ENGINE, "not_ready", hint="qrosetta logs qiskit --tail 50",
                   headline="2 of 3 runners and compilers not ready after 180 s.", evidence=["a", "b"],
                   step="Read the log of qiskit:")
    from qrosetta_cli.cli import _print_error

    _print_error(err)
    assert capsys.readouterr().err.splitlines() == [
        "qrosetta: 2 of 3 runners and compilers not ready after 180 s.", "", "  a", "  b", "",
        "Read the log of qiskit:", "  qrosetta logs qiskit --tail 50"]
    assert err.as_dict()["message"] == "Not ready after 180 s: a; b."
    _print_error(CliError("Plain.", hint="qrosetta status"))
    assert capsys.readouterr().err.splitlines() == ["qrosetta: Plain.", "qrosetta status"]


def test_unhealthy_api_json_message_keeps_the_health_report(project, env, capsys):
    from tests.unit.test_qrosetta_cli import _unhealthy_api, cli

    assert cli(_unhealthy_api(FakeEngine().standard()), project, env, ["start", "-d", "--json"]) == Exit.ENGINE
    doc = json.loads(capsys.readouterr().out)
    message = doc["error"]["message"]
    assert message.startswith("`compose up` failed: The API container was running but failed its health check")
    assert "\nLast health check of rosetta-api: exit code 1\n" in message and "Last 3 lines of its log:" in message


# --- selftest -----------------------------------------------------------------------------------------


class _Conn:
    local = True

    def __init__(self, rows):
        self.rows = rows


def test_selftest_names_backends_outside_the_started_profile(env):
    rows = [{"id": "qiskit", "enabled": True, "available": True},
            {"id": "quimb", "enabled": True, "available": False, "unavailable_reason": "unreachable"},
            {"id": "cirq", "enabled": True, "available": False, "unavailable_reason": "unreachable"},
            {"id": "cuquantum", "enabled": True, "available": False, "unavailable_reason": "no usable GPU"}]
    stack = {"running": {"qiskit"}, "created": {"qiskit", "cirq", "cuquantum"}, "profile": "minimal"}
    ctx = Context(args=type("A", (), {"backends": None})(), env=env, cfg=cfgmod.Config("/none", False),
                  local_stack=lambda c: stack)
    keys, left = selftest.backends_under_test(ctx, _Conn(rows), rows)
    assert keys == ["qiskit"]
    assert dict(left) == {"quimb": "not started in this stack (profile minimal)", "cirq": "unreachable",
                          "cuquantum": "no usable GPU"}
    stack["profile"] = None
    assert dict(selftest.backends_under_test(ctx, _Conn(rows), rows)[1])["quimb"] == "not started in this stack"
    ctx.local_stack = lambda c: None
    assert dict(selftest.backends_under_test(ctx, _Conn(rows), rows)[1])["quimb"] == "unreachable"


def test_local_services_names_the_profile_whose_backends_were_created(project, env):
    fake = FakeEngine().standard()
    ctx = Context(args=type("A", (), {})(), env=env, cfg=cfgmod.Config("/none", False), checkout=str(project),
                  engine_factory=lambda d: Engine(fake.engine, d, run=fake, popen=fake.popen, env=env))
    assert doctor.local_services(ctx) == {"running": {"api", "nginx"}, "created": {"api", "nginx"}, "profile": None}
    fake.add("qiskit-runner", ours("qiskit_runner"), image="i-qiskit")
    assert doctor.local_services(ctx)["profile"] == "minimal"


def test_selftest_screen_lines_keep_the_json_lines(tmp_path):
    lines = ["Images      1 runner probed now: 1 passed, 0 warned, 0 failed", "Statevector FAIL (1 failed)",
             "FAIL        statevector (qiskit): wrong state", "WARN        caveat", "Not tested  quimb: unreachable",
             "FAIL (1 failed). Results: /r/"]
    out = selftest.screen_lines(lines, ["statevector (qiskit): wrong state"], ["caveat"], "/r")
    assert out[:3] == lines[:2] + ["Not tested  quimb: unreachable"]
    assert "FAIL  statevector (qiskit): wrong state" in out and "WARN  caveat" in out
    assert out[-4:] == ["Self-test failed: 1 check failed, 1 warning. Results: /r/", "",
                        "Read the jobs' summaries:", "  qrosetta show summary"]
    passed = selftest.screen_lines(lines[:2] + lines[-1:], [], [], "/r")
    assert passed[-2:] == ["Self-test passed. Results: /r/", "Summaries:  qrosetta show summary"]


# --- version ---------------------------------------------------------------------------------------


def test_version_prints_aligned_rows(env, project, capsys):
    assert main(["version"], checkout=str(project), env=env, transport_factory=Unreachable()) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("qrosetta ") and out[1] == ""
    keys = [line[2:].split("  ")[0] for line in out[2:]]
    assert keys == ["Python", "Mode", "CLI API levels", "Release manifest", "Server"]
    assert len({line.index(line[2:].split("  ", 1)[1].lstrip(), 2) for line in out[2:]}) == 1
