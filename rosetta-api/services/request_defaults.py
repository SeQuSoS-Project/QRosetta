"""GET /config request_defaults: every field of the run request bodies, with the value the
server uses when a request omits it, read from the request models."""

from pydantic import BaseModel

from config import settings
from schemas import (
    AgreementThresholds, BatchPayload, BenchmarkTask, ExperimentCircuit, ExperimentPayload,
    MeasuredQasmPayload, QasmPayload,
)
from schemas.benchmark import COMPILE_ONLY_EMPTY_FIELDS

REQUEST_KINDS = {
    "compare": ("/compare", QasmPayload),
    "compare_measured": ("/compare_measured", MeasuredQasmPayload),
    "run_batch_suite": ("/run_batch_suite", BatchPayload),
    "experiments": ("/experiments", ExperimentPayload),
}

ITEM_FIELDS = {"run_batch_suite": ("tasks", BenchmarkTask),
               "experiments": ("circuits", ExperimentCircuit)}

WHEN_OMITTED = {
    "runner_config": "Every dispatched runner runs once at optimization_level.",
    "runner_phases": "Every runner is in one phase: all run at the same time.",
    "target_simulators": "Every enabled runner that is available on this server; the ones "
                         "left out as unavailable are listed in the report.",
    "execution_target": "The server's execution mode (execution_mode in GET /config); runs "
                        "are always dispatched in that mode.",
    "thresholds": "The values in request_defaults.agreement_thresholds.",
    "compilers": "No compile-only service runs.",
    "seed": "The server generates a master seed and records it in the report as seed.",
    "label": "The manifest records no label.",
}

ITEM_WHEN_OMITTED = {
    "BenchmarkTask": {
        "name": "The report names the circuit by algorithm.",
        "algorithm": "Required unless qasm_string is given.",
        "qubits": "Required for preset and MQT Bench circuits; read from the QASM otherwise.",
        "qasm_string": "The circuit is resolved from source, algorithm and qubits.",
        "source": "A preset generated from the built-in circuit library.",
    },
    "ExperimentCircuit": {
        "algorithm": "Required for the preset, qasmbench and mqt sources.",
        "qasm_string": "Required for source qasm.",
        "name": "A name derived from algorithm and qubits.",
    },
}


def _field_entries(model: type[BaseModel], notes: dict) -> dict:
    """``{field: {server_fills, default?, when_omitted?}}`` for every field of ``model``."""
    out = {}
    for name, field in model.model_fields.items():
        if field.is_required():
            entry = {"server_fills": False}
        else:
            entry = {"server_fills": True, "default": field.get_default(call_default_factory=True)}
        if name in notes:
            entry["when_omitted"] = notes[name]
        out[name] = entry
    return out


def request_defaults() -> dict:
    """The request_defaults object of GET /config."""
    requests = {}
    for kind, (endpoint, model) in REQUEST_KINDS.items():
        spec = {"endpoint": endpoint, "fields": _field_entries(model, WHEN_OMITTED)}
        if kind in ITEM_FIELDS:
            field, item_model = ITEM_FIELDS[kind]
            spec["items"] = {"field": field,
                             "fields": _field_entries(item_model, ITEM_WHEN_OMITTED[item_model.__name__])}
        requests[kind] = spec
    return {
        "requests": requests,
        "agreement_thresholds": AgreementThresholds().model_dump(),
        "compile_only": {
            "endpoints": [REQUEST_KINDS["compare"][0], REQUEST_KINDS["run_batch_suite"][0]],
            "set": {"simulate": False},
            "requires": ["compilers"],
            "must_be_empty": list(COMPILE_ONLY_EMPTY_FIELDS),
            "max_qubits": settings.MAX_QUBITS_COMPILE,
        },
    }
