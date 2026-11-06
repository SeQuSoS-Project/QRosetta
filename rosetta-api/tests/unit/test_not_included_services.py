"""Services an installed release publishes no image of: the API reports them unavailable with the
reason "not included in this release" (QROSETTA_NOT_INCLUDED, set by `qrosetta start`), and the
CLI's selftest, doctor and backends say so instead of "not started in this stack"."""

import asyncio

import httpx
import pytest
import yaml
from fastapi import HTTPException

import services.availability as availability
import services.compilation as compilation
import services.fresh_probes as fresh_probes
import services.service_listing as service_listing
from config import settings
from tests.unit._qrosetta_fake import REPO, FakeEngine, FakeServer

from qrosetta_cli import config as cfgmod  # noqa: E402
from qrosetta_cli import manifest as mf  # noqa: E402
from qrosetta_cli.client import reads, selftest  # noqa: E402
from qrosetta_cli.context import Context  # noqa: E402
from qrosetta_cli.stack import doctor  # noqa: E402
from qrosetta_cli.stack.engine import Engine  # noqa: E402


@pytest.fixture(autouse=True)
def _fresh_cache(monkeypatch):
    availability.clear_cache()
    monkeypatch.setattr(settings, "EXECUTION_MODE", "local")
    monkeypatch.setattr(settings, "NOT_DEPLOYED", frozenset())
    monkeypatch.setattr(settings, "NOT_INCLUDED", frozenset({"myqlm", "bqskit"}))
    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(lambda request: httpx.Response(404))
        return real(*args, **kwargs)
    monkeypatch.setattr(availability.httpx, "AsyncClient", factory)
    yield
    availability.clear_cache()


@pytest.fixture
def env(tmp_path):
    return {"QROSETTA_PROJECT": "qr", "HOME": str(tmp_path / "home"), "XDG_RUNTIME_DIR": str(tmp_path / "run"),
            "XDG_STATE_HOME": str(tmp_path / "state"), "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "XDG_CACHE_HOME": str(tmp_path / "cache")}


def test_the_cli_and_the_api_use_one_text():
    assert mf.NOT_INCLUDED == availability.NOT_INCLUDED == "not included in this release"
    assert mf.not_included_text(["myqlm"]).startswith(mf.NOT_INCLUDED)


@pytest.mark.parametrize("mode", ["local", "kubernetes"])
def test_not_included_services_are_unavailable_with_their_reason(monkeypatch, mode):
    monkeypatch.setattr(settings, "EXECUTION_MODE", mode)
    status = asyncio.run(availability.runner_availability(["myqlm", "qiskit"]))
    assert status["myqlm"] == {"available": False, "reason": availability.NOT_INCLUDED, "device": None}
    assert status["qiskit"]["available"] is True
    monkeypatch.setattr(settings, "NOT_DEPLOYED", frozenset({"myqlm"}))
    assert asyncio.run(availability.runner_availability(["myqlm"]))["myqlm"]["reason"] == availability.NOT_DEPLOYED
    with pytest.raises(HTTPException) as err:
        asyncio.run(availability.require_available(["myqlm"]))
    assert "myqlm: not deployed on this server" in err.value.detail


def test_runs_naming_them_are_refused_with_the_reason():
    with pytest.raises(HTTPException) as err:
        asyncio.run(availability.require_available(["myqlm", "qiskit"]))
    assert err.value.status_code == 400 and err.value.detail == (
        "Unavailable runner(s) requested: myqlm: not included in this release.")
    with pytest.raises(HTTPException) as err:
        compilation.validate_compilers({"bqskit": [1]})
    assert err.value.detail == "Compiler 'bqskit' is not included in this release."


def test_listings_and_fresh_rows_carry_the_reason(monkeypatch):
    rows = {r["id"]: r for r in asyncio.run(service_listing.runner_rows())}
    assert rows["myqlm"]["available"] is False and rows["myqlm"]["unavailable_reason"] == "not included in this release"
    compilers = {r["id"]: r for r in asyncio.run(service_listing.compiler_rows())}
    assert compilers["bqskit"]["unavailable_reason"] == "not included in this release"
    assert "myqlm" not in fresh_probes._wanted(settings.get_runner_services())

    async def authorize(request):
        return "lifecycle"
    monkeypatch.setattr(fresh_probes, "authorize", authorize)
    monkeypatch.setattr(fresh_probes, "check_rate", lambda client: None)
    fresh = {r["id"]: r for r in asyncio.run(service_listing.fresh_rows("runners", None, "c"))}
    assert fresh["myqlm"]["unavailable_reason"] == "not included in this release"
    assert fresh["myqlm"]["reason"] == "not_included" and fresh["myqlm"]["fresh"] is False
    monkeypatch.setattr(settings, "NOT_INCLUDED", frozenset())
    monkeypatch.setattr(settings, "NOT_DEPLOYED", frozenset({"myqlm"}))
    fresh_probes._rounds.clear()
    fresh = {r["id"]: r for r in asyncio.run(service_listing.fresh_rows("runners", None, "c"))}
    assert fresh["myqlm"]["reason"] == "not_deployed"
    assert fresh["myqlm"]["unavailable_reason"] == "not deployed on this server"
    compilers = {r["id"]: r for r in asyncio.run(service_listing.fresh_rows("compilers", None, "c"))}
    assert compilers["bqskit"].get("reason") != "not_included"


def test_compose_passes_the_list_to_the_api():
    compose = yaml.safe_load((REPO / "docker-compose.yml").read_text())
    assert "QROSETTA_NOT_INCLUDED=${QROSETTA_NOT_INCLUDED:-}" in compose["services"]["api"]["environment"]


def test_a_checkout_gives_compose_an_empty_list(tmp_path, env):
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    fake = FakeEngine().standard()
    ctx = Context(args=type("A", (), {})(), env=dict(env, QROSETTA_NOT_INCLUDED="qiskit"),
                  cfg=cfgmod.Config("/none", False), checkout=str(tmp_path),
                  engine_factory=lambda d: Engine(fake.engine, d, run=fake, popen=fake.popen, env=ctx.env))
    assert doctor.local_services(ctx)["not_included"] == set()
    assert {e.get(mf.NOT_INCLUDED_VAR) for cmd, e in fake.calls if cmd[1] == "compose"} == {""}


class _Conn:
    local = True


def _ctx(env, stack):
    return Context(args=type("A", (), {"backends": None})(), env=env, cfg=cfgmod.Config("/none", False),
                   local_stack=lambda c: stack)


def test_selftest_names_them_as_not_included(env):
    rows = [{"id": "qiskit", "enabled": True, "available": True},
            {"id": "myqlm", "enabled": True, "available": False, "unavailable_reason": "not included in this release"},
            {"id": "cuquantum", "enabled": True, "available": False, "unavailable_reason": "unreachable"},
            {"id": "quimb", "enabled": True, "available": False, "unavailable_reason": "unreachable"}]
    stack = {"running": {"qiskit"}, "created": {"qiskit"}, "profile": "minimal", "not_included": {"cuquantum", "myqlm"}}
    keys, left = selftest.backends_under_test(_ctx(env, stack), _Conn(), rows)
    assert keys == ["qiskit"]
    assert dict(left) == {"myqlm": "not included in this release", "cuquantum": "not included in this release",
                          "quimb": "not started in this stack (profile minimal)"}
    keys, left = selftest.backends_under_test(_ctx(env, None), _Conn(), rows)
    assert dict(left)["myqlm"] == "not included in this release" and dict(left)["cuquantum"] == "unreachable"


def test_doctor_lists_them_apart_from_services_not_started(env):
    runners = [{"id": "qiskit", "enabled": True, "available": True},
               {"id": "quest", "enabled": True, "available": False, "error_kind": "dns"},
               {"id": "myqlm", "enabled": True, "available": False, "unavailable_reason": "not included in this release"},
               {"id": "cuquantum", "enabled": True, "available": False, "error_kind": "dns"}]
    compilers = [{"id": "bqskit", "enabled": True, "available": False,
                  "unavailable_reason": "not included in this release"}]
    server = FakeServer(runners=runners, compilers=compilers)
    rep = doctor.Report()
    doctor.check_live(rep, {"server": None}, server, env, running={"qiskit"}, not_included={"cuquantum"})
    rows = [(c.id, c.status, c.message) for c in rep.checks if c.id in ("runners", "compilers")]
    assert ("runners", "INFO", "not included in this release: myqlm, cuquantum") in rows
    assert ("runners", "INFO", "not started in this stack: quest (`qrosetta status` lists them)") in rows
    assert ("compilers", "INFO", "not included in this release: bqskit") in rows
    assert not any(r[1] == "WARN" for r in rows)
    rep = doctor.Report()
    doctor.check_live(rep, {"server": None}, server, env)
    rows = [(c.id, c.status, c.message) for c in rep.checks if c.id == "runners"]
    assert ("runners", "INFO", "not included in this release: myqlm") in rows
    assert any(r[1] == "WARN" and "1 of 3 runners available" in r[2] and "myqlm" not in r[2] for r in rows)


def test_doctor_reads_the_installed_release(env, monkeypatch, tmp_path):
    from qrosetta_cli import mode as modes
    from tests.unit._qrosetta_fake import release_manifest

    monkeypatch.setattr(modes, "PACKAGE_PARENT", str(tmp_path / "site-packages"))
    monkeypatch.setattr(mf, "load", lambda path=None: release_manifest())
    monkeypatch.chdir(tmp_path)
    ctx = Context(args=type("A", (), {"project_dir": None})(), env=env, cfg=cfgmod.Config("/none", False))
    assert doctor.not_included_ids(ctx) == {"myqlm"}
    ctx = Context(args=type("A", (), {"project_dir": None})(), env=env, cfg=cfgmod.Config("/none", False),
                  checkout=str(REPO))
    assert doctor.not_included_ids(ctx) == set()


def test_backends_note_names_the_reason():
    entry = {"id": "myqlm", "enabled": True, "available": False, "unavailable_reason": "not included in this release"}
    assert reads._note(entry) == "not included in this release"
    assert reads._note(dict(entry, unavailable_reason="unreachable")) == "unreachable"
