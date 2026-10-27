"""qrosetta_cli contracts: exit codes and their priority, the JSON envelope and schemas, help and
grammar conventions, the config file, and that no measurement setting is read from the config
or the environment."""

import ast
import json
import re

import pytest

from tests.unit._qrosetta_fake import REPO, FakeEngine, FakeServer, Unreachable

from qrosetta_cli import cli as climod  # noqa: E402
from qrosetta_cli import config as cfgmod  # noqa: E402
from qrosetta_cli import errors  # noqa: E402
from qrosetta_cli.cli import SPECS, build_parser, main  # noqa: E402
from qrosetta_cli.errors import CliError, Exit  # noqa: E402
from qrosetta_cli.stack.engine import Engine  # noqa: E402

SCHEMAS = REPO / "qrosetta_cli" / "schemas"
_TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "object": dict,
          "array": list, "null": type(None)}


def _is(value, name):
    if name in ("integer", "number") and isinstance(value, bool):
        return False
    return isinstance(value, _TYPES[name])


def validate(value, schema, where="$"):
    """The subset of JSON Schema the shipped schemas use: type, enum, pattern, properties,
    required, additionalProperties false, items."""
    types = schema.get("type")
    if types is not None:
        types = types if isinstance(types, list) else [types]
        assert any(_is(value, t) for t in types), f"{where}: {value!r} is not {types}"
    if "enum" in schema:
        assert value in schema["enum"], f"{where}: {value!r} not in {schema['enum']}"
    if "pattern" in schema and isinstance(value, str):
        assert re.search(schema["pattern"], value), f"{where}: {value!r} !~ {schema['pattern']}"
    if isinstance(value, dict):
        for key in schema.get("required", []):
            assert key in value, f"{where}: missing {key}"
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            assert set(value) <= set(props), f"{where}: unexpected {set(value) - set(props)}"
        for key, sub in props.items():
            if key in value:
                validate(value[key], sub, f"{where}.{key}")
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            validate(item, schema["items"], f"{where}[{i}]")


def load_schema(name):
    return json.loads((SCHEMAS / f"{name}.json").read_text())


def validate_envelope(doc):
    validate(doc, load_schema("envelope"))
    name = doc["schema"].split("/", 1)[1]
    if doc["data"] is not None:
        validate(doc["data"], load_schema(name))
    assert doc["ok"] == (doc["exit_code"] == 0)
    assert (doc["error"] is None) == (doc["exit_code"] == 0 or 3 <= doc["exit_code"] <= 9)


def test_every_command_schema_ships_and_names_a_payload_type():
    for spec in SPECS.values():
        assert (SCHEMAS / f"{spec.schema}.json").is_file(), spec.schema
    stable_at_1 = {"status@1", "version@1", "run-result@1", "jobs@1", "job@1", "selftest@1", "summary@1", "export@1"}
    assert (SCHEMAS / "plan@1.json").is_file()
    assert {s.schema for s in SPECS.values() if s.schema.endswith("@1")} == stable_at_1
    assert all(s.schema.endswith("@0") for s in SPECS.values() if not s.stable)


def test_exit_code_table_matches_the_spec():
    expected = {0: "ok", 1: "internal", 2: "usage", 3: "disagreement", 4: "runs_without_output", 5: "job_failed",
                6: "job_cancelled", 7: "wait_timeout", 8: "not_established", 9: "selftest_failed", 10: "refused",
                11: "unreachable", 12: "incompatible", 13: "auth", 14: "not_found", 15: "busy", 16: "engine",
                17: "checks_failed"}
    assert {int(c): errors.name(c) for c in Exit if int(c) < 100} == expected
    assert errors.name(40) == "error" and errors.name(99) == "unknown"


def test_exit_code_priority_order():
    order = [1, 2, 12, 11, 13, 14, 10, 15, 16, 17, 9, 5, 6, 7, 3, 8, 4, 0]
    assert [int(c) for c in errors.PRIORITY] == order
    for i, high in enumerate(order):
        for low in order[i + 1:]:
            assert errors.worst([low, high]) == high
    assert errors.worst([0, 130, 1]) == 130
    assert errors.worst([3, 40]) == 40 and errors.worst([10, 40]) == 10
    assert errors.worst([]) == 0


@pytest.fixture
def env(tmp_path):
    return {"QROSETTA_PROJECT": "qr", "HOME": str(tmp_path), "XDG_RUNTIME_DIR": str(tmp_path / "run"),
            "XDG_STATE_HOME": str(tmp_path / "state"), "XDG_CONFIG_HOME": str(tmp_path / "config")}


@pytest.fixture
def project(tmp_path):
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    return tmp_path


def _run(argv, env, project=None, server=None, fake=None):
    fake = fake or FakeEngine().standard()
    return main(argv, env=env, checkout=str(project) if project else None,
                engine_factory=lambda d: Engine(fake.engine, d, run=fake, popen=fake.popen, env=env),
                transport_factory=server or Unreachable())


def _envelope(capsys):
    out = capsys.readouterr().out
    doc = json.loads(out)
    validate_envelope(doc)
    return doc


def test_one_error_envelope_per_exit_code(env, project, capsys, monkeypatch):
    cases = {
        Exit.USAGE: (["status", "--no-such-flag", "--json"], None),
        Exit.REFUSED: (["api", "POST", "/compare", "--json"], FakeServer(status={"/compare": (400, {"detail": "bad"})})),
        Exit.UNREACHABLE: (["api", "GET", "/config", "--json"], None),
        Exit.INCOMPATIBLE: (["profiles", "--server", "http://localhost:8080", "--json"], FakeServer()),
        Exit.AUTH: (["api", "GET", "/history/runs", "--json"], FakeServer(status={"/history/runs": (401, {"detail": "no"})})),
        Exit.NOT_FOUND: (["api", "GET", "/nope", "--json"], FakeServer()),
        Exit.BUSY: (["stop", "--json"], FakeServer(gate={"shared_running": 1, "exclusive_running": False})),
    }
    for code, (argv, server) in cases.items():
        assert _run(argv, env, project, server) == code, (code, argv)
        doc = _envelope(capsys)
        assert doc["exit_code"] == code and doc["error"]["code"] == errors.name(code)
        assert doc["error"]["hint"], argv
    monkeypatch.setattr(climod, "_load", lambda func: (lambda ctx: 1 / 0))
    assert _run(["status", "--json"], env, project) == Exit.INTERNAL
    doc = _envelope(capsys)
    assert doc["error"]["reason"] == "internal" and doc["error"]["hint"].endswith("cli.log")
    assert "ZeroDivisionError" in open(env["XDG_STATE_HOME"] + "/qrosetta/cli.log").read()


def test_engine_error_envelope(env, project, capsys):
    fake = FakeEngine().standard()
    fake.up_error = "Error: exec /usr/local/bin/python3: exec format error"
    for c in fake.containers.values():
        c["State"]["Running"] = False
    assert _run(["start", "-d", "--json"], env, project, fake=fake) == Exit.ENGINE
    doc = _envelope(capsys)
    assert doc["error"]["reason"] == "wrong_architecture"


def test_success_envelope_carries_the_server_block(env, project, capsys):
    server = FakeServer(block={"platform_version": "2.0.0", "api_levels": [1, 1], "features": {}})
    assert _run(["version", "--json"], env, project, server) == 0
    doc = _envelope(capsys)
    assert doc["server"] == {"kind": "http", "url": "http://localhost:8080", "platform_version": "2.0.0",
                             "api_levels": [1, 1]}
    assert doc["data"]["manifest"] == {"release": None, "index": None}


def _parsers(parser, path=("qrosetta",)):
    yield path, parser
    for action in parser._actions:
        if action.__class__.__name__ == "_SubParsersAction":
            seen = set()
            for name, sub in action.choices.items():
                if id(sub) not in seen:
                    seen.add(id(sub))
                    yield from _parsers(sub, path + (name,))


def test_every_help_ends_with_examples_that_parse():
    parser = build_parser()
    for path, p in _parsers(parser):
        assert p.epilog and p.epilog.startswith("Examples:"), path
        examples = [line.strip() for line in p.epilog.splitlines()[1:] if line.strip().startswith("qrosetta")]
        assert examples, path
        for example in examples:
            build_parser().parse_args(example.split()[1:])


def test_global_options_are_accepted_before_and_after_the_command():
    parser = build_parser()
    for argv in (["--json", "--server", "x", "status"], ["status", "--json", "--server", "x"]):
        args = parser.parse_args(argv)
        assert args.json is True and args.server == "x"
    assert parser.parse_args(["status"]).json is False
    args = parser.parse_args(["config", "show", "--project-dir", "/p"])
    assert args.project_dir == "/p"


def test_no_abbreviated_options_and_typos_get_suggestions(capsys):
    with pytest.raises(CliError) as err:
        build_parser().parse_args(["start", "--detac"])
    assert err.value.code == Exit.USAGE
    assert main(["stauts"]) == Exit.USAGE
    assert "did you mean status?" in capsys.readouterr().err


def test_aliases_and_bare_commands(env, capsys):
    parser = build_parser()
    assert parser.parse_args(["rm"]).spec_name == "remove"
    assert parser.parse_args(["config"]).spec_name == "config show"
    assert main([], env=env) == 0
    out = capsys.readouterr().out
    assert out.startswith("Get started:") and out.rstrip().endswith("More: qrosetta help all")
    for line in out.splitlines():
        if line.startswith("  qrosetta"):
            build_parser().parse_args(line.split("  ")[1].split()[1:])
    assert main(["help", "all"], env=env) == 0
    listing = capsys.readouterr().out
    assert all(name in listing for name in SPECS) and "(experimental)" in listing
    assert main(["help", "start"], env=env) == 0
    via_help = capsys.readouterr().out
    assert main(["start", "--help"], env=env) == 0
    assert capsys.readouterr().out == via_help


def test_experimental_commands_are_marked_and_notice_once(env, tmp_path, capsys):
    for name, spec in SPECS.items():
        assert ("(experimental)" in climod._help(spec)) == (not spec.stable), name
    cfg_path = tmp_path / "config" / "qrosetta" / "config.toml"
    assert main(["config", "init"], env=env) == 0
    err = capsys.readouterr().err
    assert err.count("is experimental") == 1 and cfg_path.is_file()
    pytest.importorskip("tomllib")
    cfg_path.write_text("[output]\nexperimental_notice = false\n")
    assert main(["config", "init"], env=env) == Exit.USAGE
    assert "is experimental" not in capsys.readouterr().err


def test_config_template_loads_and_holds_no_measurement_setting(tmp_path):
    pytest.importorskip("tomllib")
    path = tmp_path / "c.toml"
    path.write_text(cfgmod.TEMPLATE)
    assert cfgmod.load(str(path), {}).loaded


def _request_fields():
    pytest.importorskip("pydantic")
    from services.request_defaults import request_defaults
    d = request_defaults()
    names = set(d["agreement_thresholds"])
    for req in d["requests"].values():
        names |= set(req["fields"])
        if isinstance(req.get("items"), dict):
            names |= set(req["items"].get("fields") or {})
    return names | {"shots", "backends", "seed", "timeout", "repeats", "thresholds", "opt_level"}


def _leaf_keys(schema):
    for key, rule in schema.items():
        yield key
        if isinstance(rule, dict):
            yield from _leaf_keys(rule)


def test_no_config_key_names_a_request_field():
    fields = _request_fields()
    assert "n_shots" in fields and "timeout_seconds" in fields
    assert not set(_leaf_keys(cfgmod.SCHEMA)) & fields


@pytest.mark.parametrize("table", ["", "lifecycle", "output", "servers.local", "run"])
def test_a_measurement_setting_in_the_config_is_refused(tmp_path, table):
    pytest.importorskip("tomllib")
    for field in ("n_shots", "seed", "timeout_seconds", "optimization_level", "target_simulators", "exclusive"):
        path = tmp_path / "c.toml"
        path.write_text((f"[{table}]\n" if table else "") + f"{field} = 1\n")
        with pytest.raises(CliError) as err:
            cfgmod.load(str(path), {})
        assert err.value.code == Exit.USAGE and err.value.hint == f"edit {path}"
        assert "no measurement setting" in err.value.message


def test_config_validation(tmp_path):
    pytest.importorskip("tomllib")
    path = tmp_path / "c.toml"
    for text, reason in (('[lifecycle]\nengine = "lxc"\n', "config_invalid"),
                         ("[lifecycle]\ncpu_quota = 1\n", "config_invalid"),
                         ('[profiles.minimal]\nservices = ["x"]\n', "config_reserved_profile"),
                         ('[profiles.qrosetta-x]\nservices = ["x"]\n', "config_reserved_profile"),
                         ("[lifecycle\n", "config_invalid")):
        path.write_text(text)
        with pytest.raises(CliError) as err:
            cfgmod.load(str(path), {})
        assert err.value.reason == reason, text
    with pytest.raises(CliError) as err:
        cfgmod.load(None, {"QROSETTA_CONFIG": str(tmp_path / "missing.toml")})
    assert err.value.code == Exit.NOT_FOUND
    assert not cfgmod.load(None, {"XDG_CONFIG_HOME": str(tmp_path / "none")}).loaded


def test_config_show_and_path(env, capsys):
    assert main(["config", "path"], env=env) == 0
    assert capsys.readouterr().out.strip() == env["XDG_CONFIG_HOME"] + "/qrosetta/config.toml"
    assert main(["config", "show", "--json"], env=dict(env, QROSETTA_ENGINE="podman")) == 0
    doc = _envelope(capsys)
    rows = {r["key"]: r for r in doc["data"]["settings"]}
    assert rows["lifecycle.engine"]["source"] == "env QROSETTA_ENGINE" and rows["config file"]["source"] == "absent"
    assert main(["config", "edit"], env=env) == Exit.USAGE


def _cli_sources():
    for path in sorted((REPO / "qrosetta_cli").rglob("*.py")):
        yield path, ast.parse(path.read_text())


_ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]+$")
STANDARD_ENV = {"HOME", "USER", "XDG_RUNTIME_DIR", "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME",
                "VISUAL", "EDITOR"}
PASSTHROUGH_ENV = {"QROSETTA_GIT_SHA"}
IMAGE_METADATA = {"QROSETTA_IMAGE_GIT_SHA"}


def _env_reads():
    names = set()
    for path, tree in _cli_sources():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("get", "getenv"):
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    if _ENV_NAME.match(node.args[0].value):
                        names.add(node.args[0].value)
            if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load):
                key = node.slice
                if isinstance(key, ast.Constant) and isinstance(key.value, str) and _ENV_NAME.match(key.value):
                    names.add(key.value)
    return names


def test_the_cli_reads_only_its_own_and_standard_environment_variables():
    reads = _env_reads()
    allowed = set(cfgmod.CLI_ENV) | STANDARD_ENV | PASSTHROUGH_ENV | IMAGE_METADATA
    assert reads <= allowed, reads - allowed
    assert "QROSETTA_TOKEN" in reads and "QROSETTA_ENGINE" in reads


def test_no_environment_variable_names_a_request_field():
    fields = {f.upper() for f in _request_fields()}
    names = set(cfgmod.CLI_ENV) | _env_reads()
    for name in names:
        stem = name[len("QROSETTA_"):] if name.startswith("QROSETTA_") else name
        assert stem not in fields, name


def _server_env_names():
    names = set(re.findall(r"\$\{([A-Z_][A-Z0-9_]*)", (REPO / "docker-compose.yml").read_text()))
    pattern = re.compile(r"""(?:environ\.get|getenv|environ\[)\(?\s*["']([A-Z_][A-Z0-9_]*)["']""")
    for top in ("rosetta-api", "shared", "runners", "compilers"):
        for path in (REPO / top).rglob("*.py"):
            if "tests" in path.parts or ".venv" in path.parts:
                continue
            names |= set(pattern.findall(path.read_text(errors="replace")))
    for path in (REPO / "scripts").rglob("*.sh"):
        names |= set(re.findall(r"\$\{?([A-Z_][A-Z0-9_]*)", path.read_text(errors="replace")))
    names |= set(re.findall(r"QROSETTA_[A-Z0-9_]+", (REPO / "rosetta-api" / "config.py").read_text()))
    return names


def test_cli_owned_variables_are_disjoint_from_server_compose_and_script_names():
    owned = set(cfgmod.CLI_ENV) - set(cfgmod.SHARED_WITH_COMPOSE) - {"NO_COLOR", "CLICOLOR_FORCE", "TERM"}
    clash = owned & _server_env_names()
    assert not clash, clash
    assert "QROSETTA_PROJECT" in _server_env_names()
