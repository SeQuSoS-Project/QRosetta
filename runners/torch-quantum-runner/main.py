"""TorchQuantum runner: parses QASM with Qiskit, converts it with qiskit2tq and simulates it on a tq.QuantumDevice."""

from fastapi import FastAPI
from qrosetta_commons.helpers import (
    CompileResult, get_logger, register_runner_endpoints, run_cli_main,
    run_measured_job, run_statevector_job, runner_error, with_sdk_versions,
)

logger = get_logger("torchquantum-runner")

app = FastAPI(title="TorchQuantum Runner")

try:
    import importlib
    import torch
    import torchquantum as tq
    import torchquantum.functional as tqf
    from torchquantum.plugin import qiskit2tq
    from qiskit import QuantumCircuit as QiskitCircuit, transpile as qiskit_transpile
    from qiskit import qasm2

    # torchquantum 0.1.8 gate modules reference an unimported `mat_dict`
    # (mit-han-lab/torchquantum#226); alias the package-level dict into each. import_module
    # is needed because `torchquantum.functional.u2` resolves to the function, not the module.
    for _modname in ("u1", "u2", "paulix", "hadamard", "single_excitation"):
        importlib.import_module(f"torchquantum.functional.{_modname}").mat_dict = tqf.mat_dict

    TORCHQUANTUM_AVAILABLE = True
    logger.info("TorchQuantum and Qiskit loaded successfully.")
except ImportError as e:
    TORCHQUANTUM_AVAILABLE = False
    logger.warning(f"TorchQuantum import failed: {e}. Runner will return errors for all requests.")

_TQ_BASIS_GATES = [
    'h', 'x', 'y', 'z', 's', 't', 'sdg',
    'cx', 'cz', 'swap', 'ccx',
    'rx', 'ry', 'rz', 'u2', 'u3',
]

_PRECISION = "complex64"

_REMOVE_MEASUREMENTS_NOTE = (
    "qiskit.QuantumCircuit.remove_final_measurements(): Terminal measurements are removed "
    "before qiskit2tq conversion; counts are sampled from the resulting statevector. Required by the adapter, applied regardless of "
    "apply_preprocessing.")
_PRECISION_NOTE = (
    "TorchQuantum 0.1.8 simulates in complex64 (its fixed C_DTYPE); counts are sampled from "
    "float64 probabilities computed from that statevector.")


def _compile(payload: dict) -> CompileResult:
    """Parse with Qiskit, transpile to the TorchQuantum basis and convert with qiskit2tq.

    The circuit is (tq_module, transpiled_qiskit_circuit); the latter keeps its measurements
    for provenance serialisation.
    """
    level = min(max(payload.get("optimization_level", 0), 0), 2)
    qc = qiskit_transpile(
        QiskitCircuit.from_qasm_str(payload["circuit_data"]),
        optimization_level=level,
        basis_gates=_TQ_BASIS_GATES,
    )
    executed_qc = qc.remove_final_measurements(inplace=False)
    return CompileResult(
        circuit=(qiskit2tq(executed_qc), qc),
        n_qubits=executed_qc.num_qubits,
        preprocessing_applied=[
            f"qiskit.compiler.transpile(optimization_level={level}, "
            f"basis_gates={_TQ_BASIS_GATES}): Decomposes every gate into a basis TorchQuantum "
            "can execute (levels above 2 run at 2). Required by the adapter, applied "
            "regardless of apply_preprocessing.",
            _REMOVE_MEASUREMENTS_NOTE,
            _PRECISION_NOTE,
        ],
        precision=_PRECISION)


def _serialize(compiled) -> str:
    return qasm2.dumps(compiled.circuit[1])


def _run_sv(tq_module, n_qubits: int):
    """Execute the TorchQuantum module and return the batch-of-one state tensor."""
    qdev = tq.QuantumDevice(n_wires=n_qubits, bsz=1, device="cpu")
    with torch.no_grad():
        tq_module(qdev)
    return qdev.get_states_1d()


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for TorchQuantum statevector simulation.")
    if not TORCHQUANTUM_AVAILABLE:
        return runner_error("torchquantum", "TorchQuantum is not installed in this environment.")

    def execute(compiled, _payload):
        return _run_sv(compiled.circuit[0], compiled.n_qubits)

    def shape_statevector(states, _compiled, _payload):
        return states.detach().cpu().numpy()[0]

    return run_statevector_job(
        simulator="torchquantum", payload=payload, logger=logger, compile_fn=_compile,
        serialize_fn=_serialize, execute_fn=execute, postprocess_fn=shape_statevector,
        qubit_ordering="msb", precision=_PRECISION)


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received circuit data for TorchQuantum measurement simulation.")
    if not TORCHQUANTUM_AVAILABLE:
        return runner_error("torchquantum", "TorchQuantum is not installed in this environment.")

    def execute(compiled, payload):
        state = _run_sv(compiled.circuit[0], compiled.n_qubits)[0].to(torch.complex128)
        probs = torch.clamp(state.abs() ** 2, min=0.0)
        probs = probs / probs.sum()

        generator = None
        if payload.get("seed") is not None:
            generator = torch.Generator()
            generator.manual_seed(int(payload["seed"]))

        return torch.multinomial(
            probs, num_samples=payload.get("n_shots", 1024),
            replacement=True, generator=generator,
        ).numpy()

    def shape_counts(sample_indices, compiled, _payload):
        fmt = f"{{:0{compiled.n_qubits}b}}"
        counts: dict[str, int] = {}
        for idx in sample_indices:
            bitstring = fmt.format(int(idx))
            counts[bitstring] = counts.get(bitstring, 0) + 1
        return counts, "sv_sample"

    return run_measured_job(
        simulator="torchquantum", payload=payload, logger=logger, compile_fn=_compile,
        serialize_fn=_serialize, execute_fn=execute, postprocess_fn=shape_counts,
        qubit_ordering="msb", precision=_PRECISION)


register_runner_endpoints(app, process_run, process_run_measured)

logger.info("TorchQuantum runner API instantiated and ready to receive traffic.")

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "TorchQuantum")
