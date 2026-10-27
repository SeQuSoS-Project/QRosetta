"""Object-level authorization (OWASP API1, BOLA/IDOR): every route of main.app with an id in its
path, and every route that takes an account's object id in its query or body, is called as the
object's owner, another signed-in account, an anonymous client, and the owner after deactivation.
Account objects (saved circuits, saved runs, share links): another account gets the same 404 as
an id that does not exist and changes nothing; anonymous 401; a deactivated owner 403. Job ids are
capabilities: every caller gets the same answer, and only the account that started a job may save
it. A new id route without a row here fails test_every_id_route_has_a_row."""
import uuid
from dataclasses import dataclass, field

import pytest
from fastapi.routing import APIRoute

import services.history as history_service
import services.job_manager as job_manager
import services.share_links as share_links
from tests.unit.authz_world import world

QASM = "OPENQASM 2.0;\ninclude \"qelib1.inc\";\nqreg q[1];\nh q[0];\n"
REPORT = {
    "input_qasm": QASM,
    "raw_results": [{"simulator": "qiskit", "dispatch_status": "ok", "transpiled_qasm": "h q[0];",
                     "preprocessing_applied": [], "simulation_time_sec": 0.1, "compilation_time_sec": 0.1}],
    "runner_config": {"qiskit": 1},
}
MISSING = "00000000-0000-4000-8000-000000000000"
IDENTITIES = ("owner", "other", "anonymous", "deactivated_owner")


@dataclass
class Owned:
    """A route on one account object: ``kind`` names the object whose id fills the path."""
    kind: str
    ok: int
    body: dict | None = None


@dataclass
class JobSave:
    """POST /history/runs/from_job/{job_id}: a capability read, a save only by the job's owner."""
    ok: int = 201


@dataclass
class Capability:
    """A route whose id is a capability: the answer does not depend on who asks."""
    kind: str = "job"
    body: dict | None = None
    query: dict = field(default_factory=dict)


@dataclass
class Public:
    """A route on bundled, non-account data."""
    value: str


ROWS = {
    ("PATCH", "/history/circuits/{circuit_id}"): Owned("circuit", 200, {"name": "renamed"}),
    ("DELETE", "/history/circuits/{circuit_id}"): Owned("circuit", 204),
    ("GET", "/history/runs/{run_id}"): Owned("run", 200),
    ("PATCH", "/history/runs/{run_id}"): Owned("run", 200, {"run_name": "renamed"}),
    ("POST", "/history/runs/{run_id}/export"): Owned("run", 200),
    ("POST", "/history/runs/{run_id}/share-links"): Owned("run", 201, {"expires_in_days": 7}),
    ("GET", "/history/runs/{run_id}/share-links"): Owned("run", 200),
    ("GET", "/history/runs/{run_id}/summary"): Owned("run", 200),
    ("DELETE", "/history/share-links/{link_id}"): Owned("link", 200),
    ("POST", "/history/runs/from_job/{job_id}"): JobSave(),
    ("GET", "/jobs/{job_id}"): Capability(),
    ("GET", "/jobs/{job_id}/report"): Capability(),
    ("GET", "/jobs/{job_id}/summary"): Capability(),
    ("GET", "/jobs/{job_id}/circuit-texts"): Capability(),
    ("GET", "/jobs/{job_id}/selftest-result"): Capability(),
    ("GET", "/jobs/{job_id}/publication/artifacts"): Capability(),
    ("POST", "/jobs/{job_id}/export"): Capability(body={}),
    ("POST", "/jobs/{job_id}/publication/render"): Capability(body={"artifact_id": "nosuch", "format": "csv"}),
    ("GET", "/experiments/{job_id}/bundle"): Capability(kind="experiment"),
    ("GET", "/examples/{name}"): Public("rotation_1q.qasm"),
}

BODY_OR_QUERY_ID_ROWS = {
    ("DELETE", "/history/runs"): "run_ids in the body",
    ("POST", "/history/runs"): "circuit_id in the query or the body",
}

NOT_ACCOUNT_IDS = {
    ("POST", "/shared/circuits"): "the share token is the credential (tests/unit/test_share_links.py)",
}


class Scene:
    """Owner A and deactivated owner D, each with a circuit, a run linked to it and a share link;
    another account B; a finished job started by A and one by D."""

    def __init__(self, w):
        self.w = w
        self.ids = {}
        for who in ("owner", "deactivated_owner"):
            uid = w.user()
            with w.session() as db:
                circuit = history_service.create_circuit(db, uid, f"{who} circuit", QASM)
                run = history_service.save_run(db, uid, dict(REPORT), circuit.id)
                link, _token = share_links.create_link(db, uid, run.id, 7)
                self.ids[who] = {"user": uid, "circuit": circuit.id, "run": run.id, "link": link.id}
            job_id = str(uuid.uuid4())
            job = job_manager._completed_job("local", dict(REPORT), {})
            job["owner_user_id"] = uid
            job_manager.ACTIVE_JOBS[job_id] = job
            self.ids[who]["job"] = job_id
            self.ids[who]["experiment"] = job_id
        self.ids["other"] = {"user": w.user()}
        self.headers = {who: w.headers(self.ids[who]["user"]) for who in ("owner", "other", "deactivated_owner")}
        self.headers["anonymous"] = {}
        w.set_active(self.ids["deactivated_owner"]["user"], False)

    def close(self):
        for who in ("owner", "deactivated_owner"):
            job_manager.ACTIVE_JOBS.pop(self.ids[who]["job"], None)

    def target(self, identity, kind):
        """The object id the identity's request names: its own for the deactivated owner, A's
        for everyone else."""
        return self.ids["deactivated_owner" if identity == "deactivated_owner" else "owner"][kind]

    def call(self, identity, method, path, value, body=None, query=None):
        url = path.replace(path[path.index("{"):path.index("}") + 1], value)
        kwargs = {"headers": self.headers[identity], "params": query or {}}
        if body is not None:
            kwargs["json"] = body
        return self.w.client.request(method, url, **kwargs)

    def owner_state(self):
        """What A holds, read as A: circuit names, run names, active share links."""
        h = self.headers["owner"]
        circuits = sorted((c["id"], c["name"]) for c in self.w.client.get("/history/circuits", headers=h).json())
        runs = sorted((r["id"], r["run_name"]) for r in self.w.client.get("/history/runs", headers=h).json())
        links = self.w.client.get(f"/history/runs/{self.ids['owner']['run']}/share-links", headers=h).json()
        return circuits, runs, sorted((link["id"], link["active"]) for link in links)


@pytest.fixture
def scene(tmp_path, monkeypatch):
    with world(tmp_path, monkeypatch) as w:
        built = Scene(w)
        try:
            yield built
        finally:
            built.close()


def _id_routes():
    import main
    return {(m, r.path) for r in main.app.routes if isinstance(r, APIRoute) and "{" in r.path
            for m in r.methods if m != "HEAD"}


def test_every_id_route_has_a_row():
    assert _id_routes() == set(ROWS)


def test_every_account_id_in_a_query_or_body_has_a_row():
    import main
    doc = main.app.openapi()
    schemas = doc["components"]["schemas"]
    found = set()
    for path, ops in doc["paths"].items():
        for method, op in ops.items():
            names = {p["name"] for p in op.get("parameters", []) if p.get("in") == "query"}
            ref = (((op.get("requestBody") or {}).get("content") or {}).get("application/json") or {}).get("schema", {})
            ref = ref.get("$ref", "") or "".join(x.get("$ref", "") for x in ref.get("anyOf", []))
            if ref:
                names |= set(schemas[ref.rsplit("/", 1)[-1]].get("properties", {}))
            if any(n.endswith(("_id", "_ids")) or n == "token" for n in names):
                found.add((method.upper(), path))
    found.add(("POST", "/history/runs"))
    exempt = {("POST", "/compare"), ("POST", "/compare_measured"), ("POST", "/run_batch_suite"),
              ("POST", "/experiments"), ("POST", "/plan"), ("POST", "/publication/render"),
              ("POST", "/publication/artifacts"), ("POST", "/export"), ("POST", "/summary"),
              ("POST", "/timing-caveats"), ("POST", "/jobs/{job_id}/publication/render")}
    unexplained = found - set(BODY_OR_QUERY_ID_ROWS) - set(NOT_ACCOUNT_IDS) - set(ROWS) - exempt
    assert unexplained == set(), unexplained


def _cells():
    for key, row in ROWS.items():
        for identity in IDENTITIES:
            yield pytest.param(key, row, identity, id=f"{key[0]} {key[1]} as {identity}")


@pytest.mark.parametrize("key, row, identity", list(_cells()))
def test_matrix_cell(scene, key, row, identity):
    method, path = key
    if isinstance(row, Public):
        reference = scene.call("owner", method, path, row.value)
        answer = scene.call(identity, method, path, row.value)
        assert (answer.status_code, answer.content) == (reference.status_code, reference.content) and answer.status_code == 200
        return
    if isinstance(row, Capability):
        value = scene.target("owner", row.kind)
        reference = scene.call("owner", method, path, value, row.body, row.query)
        answer = scene.call(identity, method, path, value, row.body, row.query)
        assert answer.status_code == reference.status_code, (identity, answer.text, reference.text)
        assert answer.status_code not in (401, 403)
        if answer.headers.get("content-type", "").startswith("application/json"):
            assert answer.json() == reference.json()
        missing = scene.call(identity, method, path, MISSING, row.body, row.query)
        assert missing.status_code == 404, missing.text
        return
    before = scene.owner_state()
    kind = "job" if isinstance(row, JobSave) else row.kind
    body = None if isinstance(row, JobSave) else row.body
    value = scene.target(identity, kind)
    answer = scene.call(identity, method, path, value, body)
    if identity == "owner":
        assert answer.status_code == row.ok, answer.text
        return
    if identity == "anonymous":
        assert answer.status_code == 401 and answer.headers["www-authenticate"] == "Bearer"
    elif identity == "deactivated_owner":
        assert answer.status_code == 403
        assert answer.json() == {"detail": "This account has been deactivated"}
    elif isinstance(row, JobSave):
        assert answer.status_code == 403
        assert "another signed-in account" in answer.json()["detail"]
    else:
        unknown = scene.call(identity, method, path, MISSING, body)
        assert answer.status_code == 404, answer.text
        assert (answer.status_code, answer.json()) == (unknown.status_code, unknown.json())
    assert scene.owner_state() == before
    with scene.w.session() as db:
        assert history_service.list_runs(db, scene.ids["deactivated_owner"]["user"])


@pytest.mark.parametrize("identity", ["other", "anonymous", "deactivated_owner"])
def test_batch_delete_of_runs_that_are_not_the_callers(scene, identity):
    before = scene.owner_state()
    ids = [scene.ids["owner"]["run"], scene.ids["deactivated_owner"]["run"]]
    answer = scene.w.client.request("DELETE", "/history/runs", json={"run_ids": ids}, headers=scene.headers[identity])
    assert answer.status_code == {"other": 404, "anonymous": 401, "deactivated_owner": 403}[identity], answer.text
    assert scene.owner_state() == before
    with scene.w.session() as db:
        assert len(history_service.list_runs(db, scene.ids["deactivated_owner"]["user"])) == 1


def test_batch_delete_skips_another_accounts_run_beside_the_callers_own(scene):
    ids = [scene.ids["owner"]["run"], scene.ids["deactivated_owner"]["run"]]
    answer = scene.w.client.request("DELETE", "/history/runs", json={"run_ids": ids}, headers=scene.headers["owner"])
    assert answer.status_code == 200
    assert answer.json()["deleted"] == [ids[0]] and answer.json()["not_found"] == [ids[1]]
    with scene.w.session() as db:
        assert len(history_service.list_runs(db, scene.ids["deactivated_owner"]["user"])) == 1


@pytest.mark.parametrize("where", ["query", "body"])
def test_a_run_cannot_be_linked_to_another_accounts_circuit(scene, where):
    foreign = scene.ids["owner"]["circuit"]
    other = scene.headers["other"]
    if where == "query":
        answer = scene.w.client.post("/history/runs", params={"circuit_id": foreign}, json=dict(REPORT), headers=other)
    else:
        answer = scene.w.client.post("/history/runs", json={**REPORT, "circuit_id": foreign}, headers=other)
    unknown = scene.w.client.post("/history/runs", params={"circuit_id": MISSING}, json=dict(REPORT), headers=other)
    assert answer.status_code == unknown.status_code == 404
    assert answer.json() == unknown.json()
    assert scene.w.client.get("/history/runs", headers=other).json() == []


def test_an_anonymous_job_is_saved_by_any_account_that_holds_its_id(scene):
    job_id = str(uuid.uuid4())
    job_manager.ACTIVE_JOBS[job_id] = job_manager._completed_job("local", dict(REPORT), {})
    try:
        answer = scene.w.client.post(f"/history/runs/from_job/{job_id}", headers=scene.headers["other"])
        assert answer.status_code == 201, answer.text
    finally:
        job_manager.ACTIVE_JOBS.pop(job_id, None)
