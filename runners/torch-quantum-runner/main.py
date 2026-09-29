"""TorchQuantum runner: parses QASM with Qiskit, converts it with qiskit2tq and simulates it on a tq.QuantumDevice."""

from fastapi import FastAPI
from qrosetta_commons.counts import prepare_final_state_sampling, prepare_statevector_qasm
from qrosetta_commons.helpers import (
    CompileResult, _draw_statevector_samples, get_logger, register_runner_endpoints, run_cli_main,
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

_PRECISION_NOTE = (
    "TorchQuantum 0.1.8 simulates in complex64 (its fixed C_DTYPE); counts are drawn with "
    "numpy.random.Generator.choice from that statevector's float32 probabilities, which "
    "choice normalises.")


def _compile(payload: dict, qasm: str, notes=()) -> CompileResult:
    """Parse the measurement-free QASM with Qiskit, transpile to the TorchQuantum basis and
    convert with qiskit2tq. The circuit is (tq_module, transpiled_qiskit_circuit)."""
    level = min(max(payload.get("optimization_level", 0), 0), 2)
    qc = qiskit_transpile(
        QiskitCircuit.from_qasm_str(qasm),
        optimization_level=level,
        basis_gates=_TQ_BASIS_GATES,
    )
    return CompileResult(
        circuit=(qiskit2tq(qc), qc),
        n_qubits=qc.num_qubits,
        preprocessing_applied=[
            *notes,
            f"qiskit.compiler.transpile(optimization_level={level}, "
            f"basis_gates={_TQ_BASIS_GATES}): Decomposes every gate into a basis TorchQuantum "
            "can execute (levels above 2 run at 2). Required by the adapter, applied "
            "regardless of apply_preprocessing.",
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

    def compile_step(payload):
        qasm, notes = prepare_statevector_qasm(payload["circuit_data"])
        return _compile(payload, qasm, notes)

    def execute(compiled, _payload):
        return _run_sv(compiled.circuit[0], compiled.n_qubits)

    def shape_statevector(states, _compiled, _payload):
        return states.detach().cpu().numpy()[0]

    return run_statevector_job(
        simulator="torchquantum", payload=payload, logger=logger, compile_fn=compile_step,
        serialize_fn=_serialize, execute_fn=execute, postprocess_fn=shape_statevector,
        qubit_ordering="msb", precision=_PRECISION)


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received circuit data for TorchQuantum measurement simulation.")
    if not TORCHQUANTUM_AVAILABLE:
        return runner_error("torchquantum", "TorchQuantum is not installed in this environment.")

    def compile_step(payload):
        qasm, layout, notes = prepare_final_state_sampling(payload["circuit_data"])
        layouts.append(layout)
        return _compile(payload, qasm, notes)

    def execute(compiled, payload):
        state = _run_sv(compiled.circuit[0], compiled.n_qubits)[0].numpy()
        return _draw_statevector_samples(
            state, payload.get("n_shots", 1024), payload.get("seed"))

    def shape_counts(sample_indices, _compiled, _payload):
        """Map the sampled wire outcomes (wire 0 most significant) to classical-bit keys."""
        layout = layouts[0]
        positions = layout.qubit_positions("msb")
        return layout.counts_from_qubit_samples(sample_indices, positions, "msb"), "sv_sample"

    layouts = []
    return run_measured_job(
        simulator="torchquantum", payload=payload, logger=logger, compile_fn=compile_step,
        serialize_fn=_serialize, execute_fn=execute, postprocess_fn=shape_counts,
        qubit_ordering="msb", precision=_PRECISION)


register_runner_endpoints(app, process_run, process_run_measured)

logger.info("TorchQuantum runner API instantiated and ready to receive traffic.")

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "TorchQuantum")
