"""The terminal layout of qrosetta's checks and errors: marks on a UTF-8 terminal and the words
PASS/FAIL/WARN/INFO elsewhere, colour by NO_COLOR, CLICOLOR_FORCE, TERM and [output] color,
doctor's numbered fixes in the order to apply them and its next step, start's pre-checks
(which stop before compose), the self-test's "not started" wording, and the JSON left as it was."""

import io
import json

import pytest

from tests.unit._qrosetta_fake import Unreachable
from tests.unit.test_qrosetta_contracts import validate_envelope
from tests.unit.test_qrosetta_doctor import FakeHost, _doctor

from qrosetta_cli import config as cfgmod  # noqa: E402
from qrosetta_cli import layout, output  # noqa: E402
from qrosetta_cli.cli import main  # noqa: E402
from qrosetta_cli.context import Context  # noqa: E402
from qrosetta_cli.errors import Exit  # noqa: E402
from qrosetta_cli.stack import doctor  # noqa: E402


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
