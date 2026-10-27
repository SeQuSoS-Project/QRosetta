"""Request and response bodies of POST /plan."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SettingSource = Literal["flag", "set", "replay"]


class PlanSetting(BaseModel):
    """One request field given explicitly, with where its value came from."""
    model_config = ConfigDict(extra="forbid")

    value: Any = Field(..., description="The field's value, as the run request carries it.")
    source: SettingSource = Field("flag", description="'flag' (a command-line flag or a page control), 'set' (a generic FIELD=JSON setting) or 'replay' (copied from an earlier run's record).")


class PlanRequest(BaseModel):
    """Request body for POST /plan: what one press of Run (or one qrosetta run) asks for."""
    model_config = ConfigDict(extra="forbid")

    source: Literal["single", "playlist"] = Field(..., description="'single': circuits holds one circuit, run with /compare or /compare_measured. 'playlist': circuits is a playlist, run as one /run_batch_suite job per mode.")
    circuits: List[Dict[str, Any]] = Field(default_factory=list, description="Playlist items as the page's playlist files hold them: algorithm, qubits, name, qasm_string (or qasm) and source. A single circuit is {qasm_string, name}.")
    modes: List[Literal["statevector", "measured"]] = Field(default_factory=list, description="The simulation modes to run, one job each. Empty with compilers set plans a compile-only run.")
    preprocessing: Literal["on", "off", "both"] = Field("on", description="'both' plans an experiment over preprocessing on and off.")
    compilers: Dict[str, Any] = Field(default_factory=dict, description="Compile-only services and levels, sent with the first planned job.")
    name: Optional[str] = Field(None, description="The run name, as typed; the server removes refused characters and cuts it to max_label_length.")
    settings: Dict[str, PlanSetting] = Field(default_factory=dict, description="Request fields given explicitly (n_shots, seed, optimization_level, ...). Fields left out are left out of the planned requests too, so the run routes apply their defaults (request_defaults in GET /config).")
    check_circuits: bool = Field(False, description="Also run the submit-time checks of the run routes on every literal circuit and report each refusal as a circuit_refused problem.")


class PlannedRun(BaseModel):
    endpoint: str = Field(..., description="The run route to POST payload to.")
    kind: Literal["single", "batch", "experiment"]
    mode: Optional[Literal["statevector", "measured"]] = Field(None, description="Null for a compile-only run.")
    title: str
    payload: Dict[str, Any] = Field(..., description="The request body, to be sent unchanged.")
    sources: Dict[str, str] = Field(..., description="Where each payload field came from: a setting's source ('flag', 'set', 'replay') or 'plan' for a field the planner sets.")


class PlanProblem(BaseModel):
    code: str = Field(..., description="Stable code: playlist_empty, editor_empty, no_mode, compile_only_needs_one_setting, playlist_too_long, bundled_over_prep_limit, experiment_too_many_cells, circuit_too_large, request_too_large, bypass_needs_account, invalid_request, circuit_refused. New codes may be added.")
    params: Dict[str, Any] = Field(default_factory=dict, description="The numbers and names the problem is about.")
    message: str = Field(..., description="The server's wording; clients may show their own for known codes.")
    run_index: Optional[int] = Field(None, description="Index into runs, or null for a problem with the whole plan.")
    circuit_index: Optional[int] = Field(None, description="Index into the run's tasks or circuits; null for the single circuit or a run-level problem.")
    line: Optional[int] = Field(None, description="Line of the circuit text a circuit_refused problem names, when the check names one.")


class PlanResponse(BaseModel):
    """Response body of POST /plan."""
    schema_: str = Field("qrosetta.plan@1", alias="schema")
    runs: List[PlannedRun]
    problems: List[PlanProblem]
