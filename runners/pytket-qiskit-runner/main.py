# Execution script for the quantum simulator runner.

from fastapi import FastAPI
import pytket.qasm
from pytket.extensions.qiskit import tk_to_qiskit
from qiskit_aer import AerSimulator
from qiskit import transpile as qiskit_transpile
from qiskit import qasm2
from qrosetta_commons.helpers import (
    CompileResult, get_logger, register_runner_endpoints, run_cli_main,
    run_measured_job, run_statevector_job, with_sdk_versions,
)

logger = get_logger("pytket-qiskit-runner")

app = FastAPI(title="Qiskit Runner")


def _to_qiskit(payload: dict):
    """Parse the QASM, convert to a Qiskit circuit, and apply the requested opt level."""
    tk_circ = pytket.qasm.circuit_from_qasm_str(payload["circuit_data"])
    qiskit_circ = tk_to_qiskit(tk_circ)

    preprocessing_applied = []
    opt_level = payload.get("optimization_level", 0)
    if opt_level > 0:
        qiskit_circ = qiskit_transpile(qiskit_circ, optimization_level=min(opt_level, 3))
        preprocessing_applied.append(
            f"qiskit.compiler.transpile(level={min(opt_level, 3)}): Native Qiskit "
            "transpilation pass applied to optimize the circuit structure for the Aer backend.")

    return tk_circ, qiskit_circ, preprocessing_applied


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for Qiskit simulation.")

    def compile_step(payload):
        tk_circ, qiskit_circ, preprocessing_applied = _to_qiskit(payload)
        # Serialized inside the compilation window: save_statevector mutates the circuit
        # below, so capturing afterwards would record an instruction the user never sent.
        transpiled_qasm = qasm2.dumps(qiskit_circ)
        qiskit_circ.save_statevector()
        return CompileResult(
            circuit=(AerSimulator(precision="double"), qiskit_circ),
            n_qubits=tk_circ.n_qubits,
            preprocessing_applied=preprocessing_applied,
            transpiled_qasm=transpiled_qasm)

    def execute(compiled, _payload):
        backend, qiskit_circ = compiled.circuit
        return backend.run(qiskit_circ, optimization_level=0).result().get_statevector()

    return run_statevector_job(
        simulator="qiskit", payload=payload, logger=logger, compile_fn=compile_step,
        execute_fn=execute, qubit_ordering="lsb")


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for Qiskit simulation.")

    def compile_step(payload):
        tk_circ, qiskit_circ, preprocessing_applied = _to_qiskit(payload)
        return CompileResult(
            circuit=(AerSimulator(precision="double"), qiskit_circ),
            n_qubits=tk_circ.n_qubits,
            preprocessing_applied=preprocessing_applied,
            transpiled_qasm=qasm2.dumps(qiskit_circ))

    def execute(compiled, payload):
        backend, qiskit_circ = compiled.circuit
        # seed_simulator=None keeps Aer's default non-deterministic sampling.
        return backend.run(
            qiskit_circ, optimization_level=0, shots=payload.get("n_shots", 1024),
            seed_simulator=payload.get("seed")).result().get_counts()

    def shape_counts(counts, compiled, _payload):
        num_clbits = compiled.circuit[1].num_clbits
        if num_clbits == 0:
            return counts, "native"
        counts_dict = {}
        for k, v in counts.items():
            binary_key = format(int(k, 16), f"0{num_clbits}b") if k.startswith("0x") \
                else k.zfill(num_clbits)
            counts_dict[binary_key] = v
        return counts_dict, "native"

    return run_measured_job(
        simulator="qiskit", payload=payload, logger=logger, compile_fn=compile_step,
        execute_fn=execute, postprocess_fn=shape_counts, qubit_ordering="lsb")


register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Qiskit")
