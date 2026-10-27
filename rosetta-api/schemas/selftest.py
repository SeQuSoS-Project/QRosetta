"""Documented shapes of GET /selftest and GET /jobs/{job_id}/selftest-result, for
/openapi.json only; the routes return dicts and these models never filter them."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Status = Literal["PASS", "WARN", "FAIL", "SKIP"]


class _Open(BaseModel):
    model_config = ConfigDict(extra="allow")


class SelftestJob(_Open):
    part: Literal["statevector", "measured"] = Field(..., description="Which half of the self-test this request runs.")
    endpoint: str = Field(..., description="The route to POST the request to.")
    request: Dict[str, Any] = Field(..., description="The request body, every field pinned; add target_simulators.")
    client_sets: Dict[str, str] = Field(..., description="The fields the client adds, with their meaning.")
    evaluate: str = Field(..., description="The route that evaluates the finished job.")


class SelftestCircuit(_Open):
    name: str
    part: Literal["statevector", "measured"]
    check: Literal["statevector", "counts_key", "ghz_sampling"] = Field(..., description="The known-answer check applied to each backend's result.")
    tests: str = Field(..., description="What a wrong backend or API path this circuit catches.")
    qasm: str
    qasm_sha256: str
    n_qubits: int
    expected: Dict[str, Any] = Field(..., description="statevector: {statevector: {lsb, msb}} as [real, imaginary] pairs; counts_key: {counts: {lsb, msb}}; ghz_sampling: {support: {lsb, msb}, p_all_zero, max_deviation}.")


class SelftestPlan(_Open):
    """GET /selftest."""
    schema_: str = Field(..., alias="schema", description="qrosetta.selftest_plan@1.")
    selftest_version: str
    expected_sha256: str = Field(..., description="sha256 of circuits/selftest/expected.json, the pinned expected answers.")
    expected_source: str
    jobs: List[SelftestJob]
    circuits: List[SelftestCircuit]
    tolerances: Dict[str, float]
    known_answer_checks: List[Dict[str, Any]]
    environment_checks: List[Dict[str, Any]]
    pass_rule: str
    tested: str
    not_tested: str


class SelftestRow(_Open):
    check: str = Field(..., description="plan, statevector, counts_key, ghz_sampling, or an environment check name.")
    status: Status
    reason: str
    backend: Optional[str] = Field(None, description="Result key; null for a plan row or a circuit no backend ran.")
    circuit: Optional[str] = None


class SelftestResult(_Open):
    """GET /jobs/{job_id}/selftest-result."""
    schema_: str = Field(..., alias="schema", description="qrosetta.selftest_result@1.")
    selftest_version: str
    expected_sha256: str
    job_id: Optional[str] = None
    part: Literal["statevector", "measured"]
    report_source: Literal["server_job"]
    status: Literal["PASS", "WARN", "FAIL"] = Field(..., description="FAIL if any row FAILs, else WARN if any row WARNs, else PASS.")
    counts: Dict[str, int]
    backends: Dict[str, Status] = Field(..., description="Each backend's worst known-answer or environment status.")
    plan: List[SelftestRow]
    known_answer: List[SelftestRow]
    environment_checks: List[SelftestRow]
    caveats: List[str]
