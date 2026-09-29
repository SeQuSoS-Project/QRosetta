"""Qiskit runner: executes OpenQASM 2.0 circuits on Qiskit Aer (double precision)."""

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

_MULTI_CREG_NOTE = (
    "Counts keys: Aer reports one space-separated field per classical register (last-declared "
    "register leftmost, each register little-endian); the spaces are removed, giving one "
    "bitstring with clbit 0 of the first register rightmost.")


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
        """Capture the QASM before save_statevector() appends an Aer-only instruction."""
        tk_circ, qiskit_circ, preprocessing_applied = _to_qiskit(payload)
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
        execute_fn=execute, qubit_ordering="lsb", precision="complex128")


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for Qiskit simulation.")

    def compile_step(payload):
        tk_circ, qiskit_circ, preprocessing_applied = _to_qiskit(payload)
        if len(qiskit_circ.cregs) > 1:
            preprocessing_applied.append(_MULTI_CREG_NOTE)
        return CompileResult(
            circuit=(AerSimulator(precision="double"), qiskit_circ),
            n_qubits=tk_circ.n_qubits,
            preprocessing_applied=preprocessing_applied)

    def serialize(compiled):
        return qasm2.dumps(compiled.circuit[1])

    def execute(compiled, payload):
        backend, qiskit_circ = compiled.circuit
        return backend.run(
            qiskit_circ, optimization_level=0, shots=payload.get("n_shots", 1024),
            seed_simulator=payload.get("seed")).result()

    def shape_counts(result, compiled, _payload):
        """Normalise Aer counts keys to plain bitstrings zero-padded to the clbit count.

        Aer separates registers with spaces (last-declared register leftmost, each register
        little-endian); the spaces are removed so the key is the full clbit string with
        clbit 0 of the first register rightmost.
        """
        counts = result.get_counts()
        num_clbits = compiled.circuit[1].num_clbits
        if num_clbits == 0:
            return counts, "native"
        counts_dict = {}
        for k, v in counts.items():
            if k.startswith("0x"):
                binary_key = format(int(k, 16), f"0{num_clbits}b")
            else:
                binary_key = k.replace(" ", "").zfill(num_clbits)
            counts_dict[binary_key] = counts_dict.get(binary_key, 0) + v
        return counts_dict, "native"

    return run_measured_job(
        simulator="qiskit", payload=payload, logger=logger, compile_fn=compile_step,
        serialize_fn=serialize, execute_fn=execute, postprocess_fn=shape_counts,
        qubit_ordering="lsb", precision="complex128")


register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Qiskit")
