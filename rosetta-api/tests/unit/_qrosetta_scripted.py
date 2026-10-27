"""A scripted Quantum Rosetta server for the qrosetta run tests that need no server
dependencies: /config with the handshake, /openapi.json, POST /plan, the run routes, job
polling, report, summary, export and self-test routes, answered from dicts the test sets. Every
request is logged in order."""

import json
import uuid

from tests.unit._qrosetta_fake import REPO  # noqa: F401

from qrosetta_cli.client.transport import Response, Transport  # noqa: E402

ROLES = {"differs": "difference", "differs_by_only": "difference", "inconclusive": "not_established",
         "not_comparable": "not_established", "unassessed": "not_established", "no_comparison": "not_established",
         "runs_without_output": "runs_without_output", "agrees": "agreement", "bit_order": "agreement"}
FIELDS = ["qasm_string", "optimization_level", "runner_config", "runner_phases", "timeout_seconds",
          "timing_repeats", "exclusive", "target_simulators", "execution_target", "bypass_limits",
          "apply_preprocessing", "thresholds", "compilers", "simulate", "n_shots", "seed", "tasks", "mode",
          "circuits", "preprocessing_modes", "keep_statevectors", "label"]
ENDPOINTS = {"statevector": "/compare", "measured": "/compare_measured"}


def outcomes(**counts):
    out = dict.fromkeys(ROLES, 0)
    out.update(counts)
    return out


def summary(**counts):
    return {"analysis_version": "divergence-test.1", "report_source": "server_job", "outcome_roles": dict(ROLES),
            "outcomes": outcomes(**counts), "runs": {"total": 3, "returned": 3 - counts.get("runs_without_output", 0),
                                                     "without_output": counts.get("runs_without_output", 0)},
            "pair_verdicts": [], "backend_verdicts": {"backends": [{"key": k, "status": "ok", "compared": 2}
                                                                   for k in ("qiskit", "cirq", "qulacs")],
                                                      "headline_model": {"kind": "none"}},
            "benchmark_summary": None}


def _json(status, body, headers=None):
    return Response(status, {"content-type": "application/json", **(headers or {})}, json.dumps(body).encode())


class Scripted(Transport):
    """`summaries` maps a mode (statevector, measured, compile) to the summary its jobs get;
    `final` the job status; `polls` how many polls a job stays processing; `routes` overrides
    any (method, path) with (status, body) or a callable."""

    def __init__(self, features=None, summaries=None, final="completed", polls=0, local=True):
        feats = {"plan": 1, "summary": 1, "job_phase": 1, "status_labels": 1}
        feats.update(features or {})
        self.url = "http://localhost:8080" if local else "https://q.example.org"
        self.config = {
            "server": {"platform_version": "2.0.0", "api_levels": [1, 1], "analysis_version": "divergence-test.1",
                       "git_sha": "abc1234", "features": feats},
            "status_labels": {"runs": {"running": {"label": "SENT", "hint": None}, "done": {"label": "DONE"}},
                              "phases": {"dispatching": {"label": "RUNNING"}, "done": {"label": "DONE"}}},
            "summary_outcomes": {"analysis_version": "divergence-test.1", "roles": dict(ROLES)},
            "agreement_threshold_defaults": {"fidelity_tolerance": 1e-5, "js_threshold": 0.01},
            "request_defaults": {"requests": {
                k: {"endpoint": e, "fields": {"n_shots": {"server_fills": True, "default": 8200},
                                              "optimization_level": {"server_fills": True, "default": 0},
                                              "timing_repeats": {"server_fills": True, "default": 1},
                                              "seed": {"server_fills": True, "default": None}}}
                for k, e in (("compare", "/compare"), ("compare_measured", "/compare_measured"),
                             ("run_batch_suite", "/run_batch_suite"), ("experiments", "/experiments"))}},
            "limits": {"max_request_bytes": 1048576, "job_ttl_sec": 86400},
            "exclusive": {"enabled": True, "exclusive_running": False, "exclusive_waiting": 0, "shared_running": 0},
        }
        self.summaries = summaries or {}
        self.final = final
        self.polls = polls
        self.routes = {}
        self.jobs = {}
        self.log = []
        self.plans = []
        self.fields = list(FIELDS)
        self.tokens = []

    def __call__(self, server, token=None, timeout=None):
        self.tokens.append(token)
        return self

    def openapi(self):
        schema = {"properties": {f: {} for f in self.fields}}
        return {"paths": {e: {"post": {"requestBody": {"content": {"application/json": {
            "schema": {"$ref": "#/components/schemas/Req"}}}}}} for e in
            ("/compare", "/compare_measured", "/run_batch_suite", "/experiments")},
            "components": {"schemas": {"Req": schema}}}

    def plan(self, req):
        self.plans.append(req)
        given = {k: s["value"] for k, s in (req.get("settings") or {}).items()}
        source = {k: s["source"] for k, s in (req.get("settings") or {}).items()}
        modes = req.get("modes") or []
        runs = []
        circuit = {"tasks": req["circuits"]} if req["source"] == "playlist" else \
            {"qasm_string": req["circuits"][0]["qasm_string"]}
        if not modes:
            payload = {**circuit, "simulate": False, "compilers": req.get("compilers"),
                       "apply_preprocessing": req.get("preprocessing", "on") != "off"}
            runs.append({"endpoint": "/run_batch_suite" if req["source"] == "playlist" else "/compare",
                         "kind": "batch" if req["source"] == "playlist" else "single", "mode": None,
                         "title": "c (compile only)", "payload": payload})
        for i, mode in enumerate(modes):
            payload = {k: v for k, v in given.items() if k not in ("n_shots", "seed") or mode == "measured"}
            if mode == "measured":
                payload["seed"] = given.get("seed")
            payload.update(circuit, apply_preprocessing=req.get("preprocessing", "on") != "off",
                           compilers=req.get("compilers") if i == 0 else {})
            if req.get("preprocessing") == "both":
                payload.pop("apply_preprocessing")
                payload.pop("tasks", None)
                payload.pop("qasm_string", None)
                payload.update(mode=mode, circuits=req["circuits"], preprocessing_modes=[True, False])
                runs.append({"endpoint": "/experiments", "kind": "experiment", "mode": mode,
                             "title": f"{req.get('name') or 'c'} ({mode}, both)", "payload": payload})
                continue
            if req["source"] == "playlist":
                payload["mode"] = mode
            runs.append({"endpoint": "/run_batch_suite" if req["source"] == "playlist" else ENDPOINTS[mode],
                         "kind": "batch" if req["source"] == "playlist" else "single", "mode": mode,
                         "title": f"{req.get('name') or 'c'} ({mode})", "payload": payload})
        for run in runs:
            run["sources"] = {k: source.get(k, "plan") for k in run["payload"]}
        return {"schema": "qrosetta.plan@1", "runs": runs, "problems": list(self.routes.get("problems", []))}

    def _job_mode(self, job):
        p = job["payload"]
        if p.get("simulate") is False:
            return "compile"
        return p.get("mode") or ("measured" if job["endpoint"] == "/compare_measured" else "statevector")

    def request(self, method, path, query=None, body=None, headers=None, timeout=None):
        self.log.append((method, path, query))
        payload = json.loads(body) if body else None
        key = (method, path.split("?")[0])
        if key in self.routes:
            route = self.routes[key]
            if callable(route):
                return route(payload, query)
            return _json(*route)
        if path == "/config":
            return _json(200, self.config)
        if path == "/openapi.json":
            return _json(200, self.openapi())
        if path == "/plan":
            return _json(200, self.plan(payload))
        if path in ("/runners", "/compilers"):
            rows = [{"id": k, "enabled": True, "available": True, "default_selected": True,
                     "optimization_levels": {"0": "", "1": "", "2": ""}} for k in ("qiskit", "cirq", "qulacs")]
            return _json(200, rows)
        if method == "POST" and path in ("/compare", "/compare_measured", "/run_batch_suite", "/experiments"):
            job_id = str(uuid.uuid4())
            self.jobs[job_id] = {"endpoint": path, "payload": payload, "polls": 0}
            return _json(200, {"job_id": job_id, "status": "pending", "phase": "queued", "target": "local"})
        if path.startswith("/jobs/"):
            parts = path.split("/")
            job = self.jobs.get(parts[2])
            if job is None:
                return _json(404, {"detail": "Job not found or expired."})
            if len(parts) == 3:
                job["polls"] += 1
                done = job["polls"] > self.polls
                status = self.final if done else "processing"
                return _json(200, {"job_id": parts[2], "status": status, "phase": "done" if done else "dispatching",
                                   "target": "local", "error": "all runners failed" if status == "failed" else None,
                                   "runner_statuses": {"qiskit": "done" if done else "running"},
                                   "results": {"x": 1} if done else None})
            if parts[3] == "report":
                return _json(200, {"report": True, "endpoint": job["endpoint"], "seed": 99, "n_shots": 4000,
                                   "optimization_level": 1, "timing_repeats": 3,
                                   "agreement_thresholds": {"fidelity_tolerance": 1e-5},
                                   "runner_phases": {}, "runner_config": {}, "timeout_seconds": 60,
                                   "exclusive": False, "apply_preprocessing": True,
                                   "resolved_runners": {"dispatched": ["cirq", "qiskit"]}})
            if parts[3] == "summary":
                return _json(200, self.summaries.get(self._job_mode(job), summary(agrees=3)))
            if parts[3] == "export":
                return Response(200, {"content-type": "application/zip"}, b"PK\x05\x06" + b"\0" * 18)
        if path.startswith("/experiments/") and path.endswith("/bundle"):
            if path.split("/")[2] not in self.jobs:
                return _json(404, {"detail": "Job not found or expired."})
            return Response(200, {"content-type": "application/zip"}, b"PK\x05\x06" + b"\0" * 18)
        if path == "/summary":
            return _json(200, summary(agrees=3) | {"report_source": "client_supplied"})
        if path == "/export":
            return Response(200, {"content-type": "application/zip"}, b"PK\x05\x06" + b"\0" * 18)
        return _json(404, {"detail": "Not Found"})

    def paths(self, method=None):
        return [p for m, p, _ in self.log if method is None or m == method]
