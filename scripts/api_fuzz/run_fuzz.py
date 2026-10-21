"""Property-based fuzzing of the rosetta-api OpenAPI contract with Schemathesis, in process.

The app runs over ASGI with an in-memory SQLite database, the rate limiter off, storage and
job spill files under --workdir, every runner reported available and background tasks
recorded instead of run, so nothing is dispatched. A seeding step runs one statevector,
measured, playlist and experiment job through the real workers against a fake fleet (Bell
state / Bell counts) and saves runs, a circuit and a share link. The fuzzer puts those ids
into path parameters, and accepted circuits, reports (some with odd values) and artifact ids
into bodies, for part of the examples. Every operation is fuzzed in positive and negative
generation mode with the checks not_a_server_error, status_code_conformance,
content_type_conformance and response_schema_conformance, and a probe sends reports holding
NaN or Infinity. Failures, uncaught exceptions and slow calls are grouped and written to
<workdir>/fuzz_report.json.

Usage (from the repository root): see scripts/api_fuzz/README.md.
"""

import argparse
import asyncio
import json
import logging
import os
import random
import re
import sys
import time
import traceback
import uuid
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
API_DIR = REPO / "rosetta-api"

BELL = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\nh q[0];\ncx q[0],q[1];\n'
BELL_MEASURED = (BELL.replace("qreg q[2];\n", "qreg q[2];\ncreg c[2];\n")
                 + "measure q[0] -> c[0];\nmeasure q[1] -> c[1];\n")
SEED_RUNNERS = ["qiskit", "cirq", "qulacs"]
OWNER_EMAIL, OWNER_PASSWORD = "fuzz-owner@example.org", "fuzzpass123"


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--examples", type=int, default=150, help="examples per operation and mode")
    p.add_argument("--seed", type=int, default=0, help="Hypothesis seed")
    p.add_argument("--ops", default="", help="regex on 'METHOD /path'; only matching operations")
    p.add_argument("--skip-ops", default="", help="regex on 'METHOD /path'; operations to leave out")
    p.add_argument("--modes", default="positive,negative", help="comma-separated generation modes")
    p.add_argument("--slow-sec", type=float, default=10.0, help="report calls slower than this")
    p.add_argument("--call-timeout", type=float, default=120.0, help="per-call ASGI read timeout")
    p.add_argument("--replay", default="", help="resend the first request of each finding in this "
                   "fuzz_report.json and show the server's log lines, instead of fuzzing")
    p.add_argument("--logs", action="store_true", help="print the API's ERROR log lines")
    p.add_argument("--workdir", default=str(Path.home() / ".tmp" / "api-fuzz"),
                   help="database, storage, spill files and the report go here")
    return p.parse_args()


def prepare_environment(workdir: Path):
    for sub in ("s3", "spill"):
        (workdir / sub).mkdir(parents=True, exist_ok=True)
    os.environ["DATABASE_URL"] = f"sqlite:///{workdir / 'import_time.db'}"
    os.environ["S3_LOCAL_DIR"] = str(workdir / "s3")
    os.environ["QROSETTA_JOB_SPILL_DIR"] = str(workdir / "spill")
    os.environ["EXECUTION_MODE"] = "local"
    os.environ.setdefault("SECRET_KEY", "api-fuzz-only-not-a-deployment-key")
    os.environ["TMPDIR"] = str(workdir)
    os.environ["HYPOTHESIS_STORAGE_DIRECTORY"] = str(workdir / ".hypothesis")
    os.chdir(API_DIR)
    sys.path[:0] = [str(API_DIR), str(REPO / "shared")]


def build_app():
    """The production app with its database, limiter, availability probe and background
    tasks replaced for in-process fuzzing; returns ``(app, recorded_tasks)``."""
    from fastapi import BackgroundTasks
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import services.availability as availability
    from db.database import Base, get_db
    from main import app
    from services.security import limiter

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def _get_db():
        db = session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    limiter.enabled = False

    async def _probe(client, svc):
        return availability._registry_entry(svc)
    availability._probe = _probe

    recorded = []
    BackgroundTasks.add_task = lambda self, func, *a, **k: recorded.append((func, a, k))
    return app, recorded


def install_fake_fleet():
    """Runners answer with the Bell state or Bell counts, whatever circuit they receive."""
    import numpy as np

    import services.dispatcher as dispatcher
    import services.dispatcher_http as dispatcher_http
    from qrosetta_commons.helpers import counts_result, get_num_qubits_from_qasm, statevector_result

    class _Monitor:
        method = "fake"

        def get_peak_usage_mb(self):
            return 1.0

        def get_process_peak_mb(self):
            return 2.0

    async def fake_safe_request(client, url, payload, sim_name, timeout_s, http_timeout=None):
        qasm = payload.get("circuit_data") or ""
        n = max(1, get_num_qubits_from_qasm(qasm))
        common = dict(simulator=sim_name, compilation_time=0.001, simulation_time=0.002,
                      monitor=_Monitor(), qubit_ordering="lsb", preprocessing_applied=[],
                      transpiled_qasm=qasm, n_qubits=n, precision="complex128")
        if str(url).rstrip("/").endswith("/run_measured"):
            widths = [int(w) for w in re.findall(r"creg\s+\w+\s*\[\s*(\d+)\s*\]", qasm)] or [n]
            width = sum(widths)
            shots = int(payload.get("n_shots") or 2)
            counts = {"0" * width: shots - shots // 2, "1" * width: shots // 2}
            result = counts_result(counts=counts, sampling_method="fake", **common)
        else:
            sv = np.zeros(2 ** n, dtype=np.complex128)
            sv[0] = sv[-1] = 2 ** -0.5
            result = statevector_result(statevector=sv, **common)
        result["process_peak_rss_mb"] = 3.0
        return result

    dispatcher_http.safe_request = fake_safe_request
    dispatcher.EXECUTION_MODE = "local"


def _register(client, email):
    client.post("/auth/register", json={"email": email, "password": OWNER_PASSWORD})
    r = client.post("/auth/token", data={"username": email, "password": OWNER_PASSWORD})
    r.raise_for_status()
    return r.json()["access_token"]


class Seeds:
    """Objects the fuzzer can name in path parameters, recreated when a call deletes them."""

    def __init__(self, client, recorded):
        self.client = client
        self.recorded = recorded
        self.token = _register(client, OWNER_EMAIL)
        self.auth = {"Authorization": f"Bearer {self.token}"}
        self.values = defaultdict(list)
        self.share_tokens = []
        self._throwaway = 0

    def throwaway_auth(self):
        self._throwaway += 1
        return {"Authorization": "Bearer " + _register(self.client, f"fuzz-gone-{self._throwaway}@example.org")}

    def _post(self, path, body):
        r = self.client.post(path, json=body, headers=self.auth)
        if r.status_code >= 300:
            raise RuntimeError(f"seeding {path} failed: {r.status_code} {r.text[:400]}")
        return r.json()

    def _run_recorded(self):
        tasks, self.recorded[:] = list(self.recorded), []

        async def _all():
            for func, a, k in tasks:
                await func(*a, **k)
        asyncio.run(_all())

    def jobs(self):
        from services.job_manager import ACTIVE_JOBS, new_job
        made = {
            "statevector": self._post("/compare", {"qasm_string": BELL, "target_simulators": SEED_RUNNERS}),
            "measured": self._post("/compare_measured", {"qasm_string": BELL_MEASURED, "n_shots": 200,
                                                         "seed": 1, "target_simulators": SEED_RUNNERS}),
            "batch": self._post("/run_batch_suite", {"mode": "measured", "n_shots": 200, "seed": 2,
                                                     "target_simulators": SEED_RUNNERS,
                                                     "tasks": [{"algorithm": "ghz", "qubits": 2},
                                                               {"name": "bell", "qasm_string": BELL_MEASURED}]}),
            "experiment": self._post("/experiments", {"mode": "statevector", "target_simulators": SEED_RUNNERS,
                                                      "circuits": [{"source": "qasm", "name": "bell",
                                                                    "qasm_string": BELL}]}),
        }
        self._run_recorded()
        for kind, envelope in made.items():
            status = ACTIVE_JOBS[envelope["job_id"]]["status"]
            if status != "completed":
                raise RuntimeError(f"seed job {kind} ended {status}: {ACTIVE_JOBS[envelope['job_id']].get('error')}")
            self.values["job_id"].append(envelope["job_id"])
        ACTIVE_JOBS["fuzz-processing-job"] = new_job("local")
        self.values["job_id"].append("fuzz-processing-job")
        self.job_kinds = {e["job_id"]: k for k, e in made.items()}

    def history(self):
        self.values["run_id"].clear()
        self.values["circuit_id"].clear()
        self.values["link_id"].clear()
        for kind in ("statevector", "measured", "batch"):
            job_id = next(j for j, k in self.job_kinds.items() if k == kind)
            self.values["run_id"].append(self._post(f"/history/runs/from_job/{job_id}", {})["id"])
        self.values["circuit_id"].append(self._post("/history/circuits", {"name": "bell", "qasm_string": BELL})["id"])
        run_id = self.values["run_id"][0]
        for old in self.client.get(f"/history/runs/{run_id}/share-links", headers=self.auth).json():
            if old.get("active"):
                self.client.delete(f"/history/share-links/{old['id']}", headers=self.auth)
        link = self._post(f"/history/runs/{run_id}/share-links", {"expires_in_days": 30})
        self.values["link_id"].append(link["id"])
        self.share_tokens = [link["token"]]

    def examples(self):
        names = [e["name"] for e in self.client.get("/examples").json() if isinstance(e, dict) and "name" in e]
        self.values["name"] = names[:5]
        self.values["algorithm"] = sorted(self.client.get("/benchmarks/mqt/list").json())[:8]
        self.values["circuit"] = self.client.get("/benchmarks/qasmbench/list").json()[:8]
        algorithms = self.client.get("/algorithms").json()
        self.values["presets"] = [a["id"] if isinstance(a, dict) else a for a in algorithms]

    def reports_and_catalogs(self):
        """Display reports of the seed jobs (single-circuit and batch) and the artifacts each
        offers, for ``realistic`` bodies."""
        self.reports, self.report_catalogs, self.job_catalogs = [], [], {}
        for job_id, kind in self.job_kinds.items():
            if kind == "experiment":
                continue
            report = self.client.get(f"/jobs/{job_id}").json()["results"]
            self.reports.append(report)
            r = self.client.post("/publication/artifacts", json={"results": report})
            self.report_catalogs.append(r.json() if r.status_code == 200 else [])
            if kind != "batch":
                self.job_catalogs[job_id] = self.client.get(f"/jobs/{job_id}/publication/artifacts").json()

    def check_reports(self):
        """Every completed seed job serves its report (the ASGI lifespan, which empties the
        spill directory, has already started)."""
        for job_id, kind in self.job_kinds.items():
            path = f"/experiments/{job_id}/bundle" if kind == "experiment" else f"/jobs/{job_id}/report"
            r = self.client.get(path)
            if r.status_code != 200:
                raise RuntimeError(f"seed job {kind}: GET {path} -> {r.status_code} {r.text[:300]}")

    def add_upload(self, run_id, n):
        """Name an uploaded (possibly mutated) run in later run_id parameters, and every
        fifth one also through a share link, keeping at most three such runs."""
        runs = self.values["run_id"]
        runs[3:] = (runs[3:] + [run_id])[-3:]
        if n % 5 == 0:
            r = self.client.post(f"/history/runs/{run_id}/share-links", json={}, headers=self.auth)
            if r.status_code == 201:
                self.share_tokens = (self.share_tokens + [r.json()["token"]])[-4:]

    def ensure(self):
        """Recreate the saved runs, circuit and share link if a fuzzed call removed one."""
        runs = {r["id"] for r in self.client.get("/history/runs", headers=self.auth).json()}
        circuits = {c["id"] for c in self.client.get("/history/circuits", headers=self.auth).json()}
        links = {link["id"] for link in self.client.get(
            f"/history/runs/{self.values['run_id'][0]}/share-links", headers=self.auth).json()
            if link.get("active")} if self.values["run_id"][0] in runs else set()
        if (not set(self.values["run_id"]) <= runs or not set(self.values["circuit_id"]) <= circuits
                or not set(self.values["link_id"]) <= links):
            self.history()


def substitute(case, seeds, counter):
    """Put a seeded id or name into each known path or query parameter for two examples in
    three, and for one in three also realistic values into the body (see ``realistic``)."""
    if counter % 3 == 2:
        return
    for location in ("path_parameters", "query"):
        params = getattr(case, location, None)
        if not isinstance(params, dict):
            continue
        for key, value in list(params.items()):
            choices = seeds.values.get(key)
            if choices and isinstance(value, str):
                params[key] = choices[counter % len(choices)]
    if (case.operation.path == "/shared/circuits" and isinstance(case.body, dict)
            and isinstance(case.body.get("token"), str) and seeds.share_tokens):
        case.body["token"] = seeds.share_tokens[counter % len(seeds.share_tokens)]
    if counter % 3 == 1 and isinstance(case.body, dict):
        realistic(case, seeds, counter)


def _circuit_for(path, body):
    return BELL_MEASURED if "measured" in path or body.get("mode") == "measured" else BELL


ODD_VALUES = [None, True, 0, -1, 2 ** 63, 1e308, -1e308, 1e-320, "", "x" * 300,
              "\u0000", "<script>", "../../etc/passwd", [], {}, [None], {"": None}, "NaN", "-0"]


def mutate(report, rng):
    """Replace one to three values anywhere inside ``report`` by an odd JSON value, or drop a
    key; deterministic for a given ``rng``."""
    for _ in range(rng.randint(1, 3)):
        parents = []

        def walk(node, depth=0):
            if isinstance(node, dict):
                for key in node:
                    parents.append((node, key))
                    walk(node[key], depth + 1)
            elif isinstance(node, list):
                for index in range(len(node)):
                    parents.append((node, index))
                    walk(node[index], depth + 1)
        walk(report)
        if not parents:
            return
        parent, key = rng.choice(parents)
        if isinstance(parent, dict) and rng.random() < 0.2:
            del parent[key]
        else:
            parent[key] = rng.choice(ODD_VALUES)


def realistic(case, seeds, n):
    """Replace generated circuits, runner ids, emails, reports and artifact ids in a JSON
    body by ones the API accepts, keeping every other generated field."""
    import copy
    body, path = case.body, case.operation.path
    if isinstance(body.get("qasm_string"), str):
        body["qasm_string"] = _circuit_for(path, body)
    for key in ("tasks", "circuits"):
        if isinstance(body.get(key), list):
            for item in body[key]:
                if isinstance(item, dict) and isinstance(item.get("qasm_string"), str):
                    item["qasm_string"] = _circuit_for(path, body)
    presets = seeds.values.get("presets") or []
    for item in [body] + [i for k in ("tasks", "circuits") if isinstance(body.get(k), list)
                          for i in body[k] if isinstance(i, dict)]:
        if presets and isinstance(item.get("algorithm"), str) and item.get("source") in (None, "preset"):
            item["algorithm"] = presets[n % len(presets)]
            if not isinstance(item.get("qubits"), int) or not 0 <= item["qubits"] <= 30:
                item["qubits"] = 2 + n % 10
    if isinstance(body.get("target_simulators"), list):
        body["target_simulators"] = SEED_RUNNERS[: 1 + n % len(SEED_RUNNERS)]
    if path == "/auth/register" and "email" in body:
        body["email"] = f"fuzz-new-{n}-{len(seeds.values['job_id'])}@example.org"
    if path == "/auth/token" and "username" in body:
        body["username"], body["password"] = OWNER_EMAIL, OWNER_PASSWORD
    if path == "/history/runs" and isinstance(body.get("run_ids"), list):
        body["run_ids"] = seeds.values["run_id"][: 1 + n % 2] + body["run_ids"][:1]
    report_index = n % len(seeds.reports)
    report = copy.deepcopy(seeds.reports[report_index])
    if (n // 3) % 2 == 1:
        mutate(report, random.Random(n))
    if path == "/history/runs" and case.operation.method.upper() == "POST":
        body.update(report)
    elif "results" in body:
        body["results"] = report
    if isinstance(body.get("artifact_id"), str):
        job_id = (case.path_parameters or {}).get("job_id")
        catalog = seeds.job_catalogs.get(job_id) or seeds.report_catalogs[report_index]
        if catalog:
            artifact = catalog[n % len(catalog)]
            body["artifact_id"] = artifact["id"]
            if isinstance(body.get("format"), str):
                body["format"] = artifact["formats"][n % len(artifact["formats"])]


def _short(text, limit=600):
    text = str(text)
    return text if len(text) <= limit else text[:limit] + " ..."


def fuzz(schema, seeds, args):
    import hypothesis
    from hypothesis import HealthCheck, Phase, given, settings
    from schemathesis import GenerationMode
    from schemathesis.checks import not_a_server_error
    from schemathesis.core.failures import FailureGroup
    from schemathesis.specs.openapi.checks import (
        content_type_conformance, response_schema_conformance, status_code_conformance)

    checks = [not_a_server_error, status_code_conformance, content_type_conformance,
              response_schema_conformance]
    modes = [GenerationMode(m.strip()) for m in args.modes.split(",") if m.strip()]
    only = re.compile(args.ops) if args.ops else None
    skip = re.compile(args.skip_ops) if args.skip_ops else None

    findings = {}
    stats = defaultdict(lambda: defaultdict(int))
    slow = []
    errors = defaultdict(int)
    tracebacks = {}
    slowest = {}

    def record(label, mode, kind, status, message, case, response_text=""):
        first = message.strip().splitlines()[0] if message.strip() else ""
        key = (label, kind, status, re.sub(r"\d+(\.\d+)?", "N", first)[:160])
        entry = findings.setdefault(key, {"operation": label, "mode": mode, "kind": kind,
                                          "status": status, "message": _short(message, 3000),
                                          "response": _short(response_text, 1500),
                                          "curl": None, "count": 0})
        entry["count"] += 1
        if "request" not in entry:
            entry["request"] = {"method": case.method, "path": case.formatted_path,
                                "query": dict(case.query or {}), "headers": dict(case.headers or {}),
                                "body": case.body}
        if entry["curl"] is None:
            try:
                entry["curl"] = case.as_curl_command()
            except Exception:
                entry["curl"] = repr(case)[:1500]

    for result in schema.get_all_operations():
        operation = result.ok()
        label = f"{operation.method.upper()} {operation.path}"
        if (only and not only.search(label)) or (skip and skip.search(label)):
            continue
        for mode in modes:
            counter = [0]
            started = time.perf_counter()

            @hypothesis.seed(args.seed)
            @settings(max_examples=args.examples, deadline=None, database=None,
                      suppress_health_check=list(HealthCheck), phases=[Phase.explicit, Phase.generate],
                      print_blob=False, report_multiple_bugs=False)
            @given(case=operation.as_strategy(generation_mode=mode))
            def run(case):
                counter[0] += 1
                try:
                    one(case, counter[0])
                except Exception as exc:
                    key = f"{label} [{mode.value}]: {type(exc).__name__}: {_short(exc, 200)}"
                    errors[key] += 1
                    tracebacks.setdefault(key, "".join(traceback.format_exception(exc))[-3000:])

            def one(case, n):
                substitute(case, seeds, n)
                if label == "DELETE /auth/me":
                    headers = seeds.throwaway_auth()
                else:
                    headers = {} if n % 4 == 3 else dict(seeds.auth)
                t0 = time.perf_counter()
                try:
                    response = case.call(headers=headers, timeout=args.call_timeout)
                except Exception as exc:
                    elapsed = time.perf_counter() - t0
                    text = "".join(traceback.format_exception(exc))
                    kind = "timeout" if "Timeout" in type(exc).__name__ else "exception"
                    record(label, mode.value, kind, None, text, case)
                    stats[label][f"{mode.value}:{kind}"] += 1
                    if elapsed > args.slow_sec:
                        slow.append({"operation": label, "seconds": round(elapsed, 2)})
                    return
                elapsed = time.perf_counter() - t0
                stats[label][f"{mode.value}:{response.status_code}"] += 1
                slowest[label] = max(slowest.get(label, 0.0), round(elapsed, 3))
                if elapsed > args.slow_sec:
                    slow.append({"operation": label, "seconds": round(elapsed, 2),
                                 "status": response.status_code, "curl": case.as_curl_command()})
                try:
                    case.validate_response(response, checks=checks, headers=headers)
                except FailureGroup as group:
                    for failure in group.exceptions:
                        record(label, mode.value, getattr(failure, "title", type(failure).__name__),
                               response.status_code,
                               f"{getattr(failure, 'title', '')}: {getattr(failure, 'message', failure)}",
                               case, response.content[:2000].decode("utf-8", "replace"))
                if label == "POST /history/runs" and response.status_code == 201:
                    seeds.add_upload(response.json()["id"], n)
                if operation.method.upper() in ("DELETE", "PATCH"):
                    seeds.ensure()

            try:
                run()
            except hypothesis.errors.Unsatisfiable:
                pass
            except Exception as exc:
                errors[f"{label} [{mode.value}]: {type(exc).__name__}: {_short(exc, 300)}"] += 1
            print(f"{label:55s} {mode.value:8s} {counter[0]:4d} calls "
                  f"{time.perf_counter() - started:7.1f}s", flush=True)
    return findings, stats, slow, errors, tracebacks, slowest


def probe_non_finite(client, seeds):
    """Send seeded reports holding NaN or Infinity (which the HTTP client of the fuzzer
    cannot encode) to the routes that take a report, and read back any run that was saved;
    returns the calls that answered 5xx."""
    import copy
    problems = []

    def send(method, path, body):
        raw = json.dumps(body, allow_nan=True).encode()
        r = client.request(method, path, content=raw,
                           headers={**seeds.auth, "Content-Type": "application/json"})
        if r.status_code >= 500:
            problems.append({"operation": f"{method} {path}", "status": r.status_code})
        return r

    for index, report in enumerate(seeds.reports):
        for value in (float("nan"), float("inf"), float("-inf")):
            bad = copy.deepcopy(report)
            leaves = []

            def walk(node):
                items = node.items() if isinstance(node, dict) else enumerate(node) if isinstance(node, list) else ()
                for key, child in items:
                    if isinstance(child, float):
                        leaves.append((node, key))
                    walk(child)
            walk(bad)
            parent, key = random.Random(index).choice(leaves) if leaves else (bad, "n_shots")
            parent[key] = value
            send("POST", "/export", {"results": bad})
            send("POST", "/publication/artifacts", {"results": bad})
            for artifact in seeds.report_catalogs[index][:3]:
                send("POST", "/publication/render", {"results": bad, "artifact_id": artifact["id"],
                                                     "format": artifact["formats"][0]})
            saved = send("POST", "/history/runs", bad)
            if saved.status_code == 201:
                run_id = saved.json()["id"]
                for method, path in (("GET", f"/history/runs/{run_id}"), ("GET", "/history/runs"),
                                     ("POST", f"/history/runs/{run_id}/export")):
                    r = client.request(method, path, headers=seeds.auth)
                    if r.status_code >= 500:
                        problems.append({"operation": f"{method} {path}", "status": r.status_code,
                                         "after": "a report with a non-finite number was saved"})
    return problems


def replay(client, seeds, report_path):
    """Send each finding's first request again, with the API's log lines shown."""
    logging.disable(logging.NOTSET)
    for finding in json.loads(report_path.read_text())["findings"]:
        request = finding.get("request")
        if not request:
            continue
        sent = request.get("headers")
        headers = {**(sent if isinstance(sent, dict) else {}), **seeds.auth}
        print(f"--- {finding['operation']} ({finding['kind']}, status {finding['status']})", flush=True)
        try:
            r = client.request(request["method"], request["path"], params=request.get("query"),
                               json=request.get("body"), headers=headers)
            print(r.status_code, r.content[:300].decode("utf-8", "replace"), flush=True)
        except Exception:
            traceback.print_exc()
    return 0


def main():
    args = parse_args()
    workdir = Path(args.workdir).expanduser().resolve()
    prepare_environment(workdir)
    from fastapi.testclient import TestClient

    import schemathesis

    app, recorded = build_app()
    logging.disable(logging.WARNING if args.logs else logging.CRITICAL)
    install_fake_fleet()
    schema = schemathesis.openapi.from_asgi("/openapi.json", app)
    client = TestClient(app, raise_server_exceptions=False)
    seeds = Seeds(client, recorded)
    real_uuid4, counter = uuid.uuid4, iter(range(1, 10 ** 6))
    uuid.uuid4 = lambda: uuid.UUID(int=next(counter))
    try:
        seeds.jobs()
        seeds.history()
    finally:
        uuid.uuid4 = real_uuid4
    seeds.examples()
    seeds.check_reports()
    seeds.reports_and_catalogs()
    print("seeded:", {k: len(v) for k, v in seeds.values.items()}, flush=True)

    if args.replay:
        return replay(client, seeds, Path(args.replay))
    started = time.perf_counter()
    non_finite = probe_non_finite(client, seeds)
    findings, stats, slow, errors, tracebacks, slowest = fuzz(schema, seeds, args)
    total = time.perf_counter() - started
    report = {"examples": args.examples, "seed": args.seed, "modes": args.modes,
              "seconds": round(total, 1), "findings": sorted(findings.values(), key=lambda f: f["operation"]),
              "slow_calls": slow, "non_finite_probe": non_finite, "harness_errors": dict(errors),
              "harness_tracebacks": tracebacks,
              "status_counts": {op: dict(c) for op, c in stats.items()},
              "slowest_call_seconds": dict(sorted(slowest.items(), key=lambda kv: -kv[1]))}
    out = workdir / "fuzz_report.json"
    out.write_text(json.dumps(report, indent=2, default=str))
    print(f"\n{len(findings)} distinct findings, {len(slow)} slow calls, {len(non_finite)} 5xx in the "
          f"non-finite probe, {len(errors)} harness errors in {total:.0f}s; report: {out}")
    for p in non_finite:
        print(f"  non-finite probe: {p}")
    for f in report["findings"]:
        print(f"  [{f['count']:4d}] {f['operation']} {f['mode']} {f['kind']} status={f['status']}: "
              f"{f['message'].splitlines()[0][:150]}")
    for name, count in errors.items():
        print(f"  harness error x{count}: {name}")
    return 1 if findings or slow or non_finite else 0


if __name__ == "__main__":
    sys.exit(main())
