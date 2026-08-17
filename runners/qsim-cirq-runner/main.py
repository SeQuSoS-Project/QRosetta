# Execution script for the quantum simulator runner.

from fastapi import FastAPI
from qrosetta_commons.helpers import (
    CompileResult, get_logger, register_runner_endpoints, run_cli_main,
    run_measured_job, run_statevector_job, runner_error, with_sdk_versions,
)
import pytket.qasm
from pytket.extensions.cirq import tk_to_cirq
from pytket.passes import RemoveBarriers, auto_rebase_pass
from pytket.circuit import OpType
from pytket.transform import Transform
import cirq

try:
    import qsimcirq
    QSIM_AVAILABLE = True
except ImportError:
    QSIM_AVAILABLE = False

logger = get_logger("qsim-cirq-runner")

app = FastAPI(title="qsim-Cirq Runner")

def _to_cirq_circuit(qasm_str: str, optimization_level: int = 0, apply_preprocessing: bool = True) -> tuple[cirq.Circuit, list[str], "pytket.circuit.Circuit"]:
    """Parse QASM string via pytket, convert to Cirq, then apply Cirq-native optimizations.

    Returns the pytket Circuit (not its QASM string) so the caller can serialize it
    for provenance outside the timed compilation window.
    """
    tk_circ = pytket.qasm.circuit_from_qasm_str(qasm_str)

    preprocessing_applied = []
    if apply_preprocessing:
        RemoveBarriers().apply(tk_circ)
        preprocessing_applied.append("pytket.passes.RemoveBarriers(): Removes barrier instructions from the circuit to prevent parsing failures in the backend adapter.")
        auto_rebase_pass({OpType.CX, OpType.Rz, OpType.Rx}).apply(tk_circ)
        preprocessing_applied.append("pytket.passes.auto_rebase_pass({CX, Rz, Rx}): Universally decomposes complex multi-qubit and single-qubit gates (like CU3, CRX) into a standard CX/Rz/Rx basis to prevent parsing failures in the backend.")
    else:
        Transform.RebaseToRzRx().apply(tk_circ)

    circ = tk_to_cirq(tk_circ)

    if optimization_level >= 1:
        circ = cirq.drop_empty_moments(circ)
        circ = cirq.align_left(circ)

    if optimization_level >= 2:
        circ = cirq.eject_z(circ)
        circ = cirq.eject_phased_paulis(circ)
        circ = cirq.merge_single_qubit_gates_to_phxz(circ)
        circ = cirq.drop_empty_moments(circ)

    return circ, preprocessing_applied, tk_circ

def _strip_measurements(circ: cirq.Circuit) -> cirq.Circuit:
    """Return a copy of the circuit with all measurement gates removed."""
    return cirq.Circuit(
        op for op in circ.all_operations()
        if not isinstance(op.gate, cirq.MeasurementGate)
    )


def _serialize(compiled: CompileResult) -> str:
    return pytket.qasm.circuit_to_qasm_str(compiled.circuit[-1])


@with_sdk_versions
def process_run(payload: dict) -> dict:
    if not QSIM_AVAILABLE:
        return runner_error("qsim-cirq", "qsimcirq package not installed")

    logger.info("Received circuit data for qsim-Cirq simulation.")

    def compile_step(payload):
        cirq_circ, preprocessing_applied, tk_export = _to_cirq_circuit(
            payload["circuit_data"], payload.get("optimization_level", 0),
            payload.get("apply_preprocessing", True))
        cirq_circ_no_meas = _strip_measurements(cirq_circ)
        return CompileResult(
            circuit=(qsimcirq.QSimSimulator(), cirq_circ_no_meas, tk_export),
            n_qubits=len(cirq_circ_no_meas.all_qubits()),
            preprocessing_applied=preprocessing_applied)

    def execute(compiled, _payload):
        simulator, circ, _ = compiled.circuit
        return simulator.simulate(circ).final_state_vector

    return run_statevector_job(
        simulator="qsim-cirq", payload=payload, logger=logger, compile_fn=compile_step,
        serialize_fn=_serialize, execute_fn=execute, qubit_ordering="lsb")


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    if not QSIM_AVAILABLE:
        return runner_error("qsim-cirq", "qsimcirq package not installed")

    logger.info("Received measured circuit data for qsim-Cirq simulation.")

    def compile_step(payload):
        cirq_circ, preprocessing_applied, tk_export = _to_cirq_circuit(
            payload["circuit_data"], payload.get("optimization_level", 0),
            payload.get("apply_preprocessing", True))
        all_qubits = sorted(cirq_circ.all_qubits())
        circ_with_meas = _strip_measurements(cirq_circ) + cirq.measure(
            *all_qubits, key="result"
        )
        # seed=None keeps qsim's default non-deterministic sampling.
        simulator = qsimcirq.QSimSimulator(seed=payload.get("seed"))
        return CompileResult(
            circuit=(simulator, circ_with_meas, tk_export),
            n_qubits=len(all_qubits),
            preprocessing_applied=preprocessing_applied)

    def execute(compiled, payload):
        simulator, circ, _ = compiled.circuit
        return simulator.run(circ, repetitions=payload.get("n_shots", 1024))

    def shape_counts(run_result, _compiled, _payload):
        counts_dict: dict = {}
        for shot in run_result.measurements["result"]:
            bitstring = "".join(str(int(b)) for b in shot)
            counts_dict[bitstring] = counts_dict.get(bitstring, 0) + 1
        return counts_dict, "native"

    return run_measured_job(
        simulator="qsim-cirq", payload=payload, logger=logger, compile_fn=compile_step,
        serialize_fn=_serialize, execute_fn=execute, postprocess_fn=shape_counts,
        qubit_ordering="msb")


register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "qsim-Cirq")
