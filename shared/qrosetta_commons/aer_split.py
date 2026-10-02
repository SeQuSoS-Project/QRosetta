"""AerBackend.run split at its native call, as qiskit-aer 0.15.1's _execute_circuits_job runs
it: ``prepare`` (Aer's circuit compile, assembly into AerCircuit, run config), ``execute``
(the C++ simulation), ``format_result`` (output checks and the qiskit Result)."""

import datetime

from qrosetta_commons.helpers import require_distribution_version

AER_VERSION = "0.15.1"

PREPARE_NOTE = (
    "qiskit-aer AerBackend.run split at its native call: Aer's circuit compile, "
    "assemble_circuits (Qiskit circuit to AerCircuit) and generate_aer_config run after "
    "transpilation, inside compilation_time; the timed run is Aer's _execute_circuits on "
    "the assembled circuit; checking the output and building the qiskit Result follow it.")


def require_aer(distribution: str) -> None:
    require_distribution_version(distribution, AER_VERSION, "AerBackend._execute_circuits_job")


def prepare(backend, circuit, **run_options) -> dict:
    """Everything AerBackend._execute_circuits_job does before the native call."""
    from qiskit_aer.backends.aerbackend import assemble_circuits, generate_aer_config
    from qiskit_aer import AerError
    circuits, noise_model = backend._compile([circuit], **run_options)
    if backend._target is not None:
        aer_circuits, _ = assemble_circuits(circuits, backend.configuration().basis_gates)
    else:
        aer_circuits, _ = assemble_circuits(circuits)
    if not all(len(c.parameters) == 0 for c in circuits):
        raise AerError("circuits have parameters but parameter_binds is not specified.")
    for circ_id, aer_circuit in enumerate(aer_circuits):
        aer_circuit.circ_id = circ_id
    return {
        "aer_circuits": aer_circuits,
        "noise_model": noise_model,
        "config": generate_aer_config(circuits, backend.options, **run_options),
        "metadata_map": {a.circ_id: c.metadata for a, c in zip(aer_circuits, circuits)},
    }


def execute(backend, prepared: dict):
    return backend._execute_circuits(prepared["aer_circuits"], prepared["noise_model"],
                                     prepared["config"])


def format_result(backend, prepared: dict, output):
    """The qiskit Result AerBackend.run would return for ``output``."""
    from qiskit_aer import AerError
    if not isinstance(output, dict):
        raise AerError("simulation terminated without returning valid output.")
    output["job_id"] = ""
    output["date"] = datetime.datetime.now().isoformat()
    output["backend_name"] = backend.name
    output["backend_version"] = backend.configuration().backend_version
    for result in output["results"]:
        if "header" not in result:
            continue
        result["header"]["metadata"] = prepared["metadata_map"][result.pop("circ_id")]
    return backend._format_results(output)
