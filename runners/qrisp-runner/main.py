"""Qrisp runner: imports OpenQASM 2.0 into a low-level qrisp.QuantumCircuit and runs Qrisp's built-in simulator."""

import random

from fastapi import FastAPI
from qrosetta_commons.counts import parse_measurement_layout, prepare_statevector_qasm
from qrosetta_commons.helpers import (
    CompileResult, get_logger, get_num_qubits_from_qasm, register_runner_endpoints,
    run_cli_main, run_measured_job, run_statevector_job, with_sdk_versions,
)
import numpy as np

logger = get_logger("qrisp-runner")

app = FastAPI(title="Qrisp Runner")

_PRECISION = "complex64"

_IMPORT_NOTE = (
    "qrisp.QuantumCircuit.from_qasm_str(): Qrisp parses the QASM with "
    "qiskit.QuantumCircuit.from_qasm_str and converts it with QuantumCircuit.from_qiskit. "
    "Qrisp's simulator uses complex64 (qrisp.simulator.unitary_management.np_dtype). "
    "Required by the adapter, applied regardless of apply_preprocessing.")
_SAMPLING_NOTE = (
    "qrisp.QuantumCircuit.run(): Qrisp samples the shots and tallies them in one call, so "
    "the tally is inside simulation_time_sec. Qrisp keys hold one character per measurement "
    "(highest classical bit leftmost); they are re-keyed to one bitstring over every "
    "declared classical bit in declaration order, flat clbit 0 rightmost.")
_CANONICAL_ORDER_NOTE = (
    "qrisp QuantumState.multi_measure(return_res_states=False) is wrapped to return its "
    "outcomes sorted by outcome index. Qrisp builds that outcome list by iterating a set of "
    "tensor factors, whose order differs between processes, so the seeded numpy.random.choice "
    "draw mapped to different outcomes in each process. numpy's and Python's global RNGs are "
    "seeded with the runner seed. Required by the adapter, applied regardless of "
    "apply_preprocessing.")


def _canonical_multi_measure():
    """Wrap QuantumState.multi_measure so its (outcomes, probabilities) come sorted."""
    from qrisp.simulator.quantum_state import QuantumState
    original = QuantumState.multi_measure
    if getattr(original, "_qrosetta_sorted", False):
        return

    def multi_measure(self, mes_qubits, return_res_states=True):
        result = original(self, mes_qubits, return_res_states=return_res_states)
        if return_res_states:
            return result
        outcomes, probabilities = result
        order = sorted(range(len(outcomes)), key=lambda i: int(outcomes[i]))
        if isinstance(outcomes, np.ndarray):
            outcomes = outcomes[order]
        else:
            outcomes = [outcomes[i] for i in order]
        return outcomes, np.asarray(probabilities)[order]

    multi_measure._qrosetta_sorted = True
    QuantumState.multi_measure = multi_measure


def _parse(qasm_str: str, optimization_level: int = 0):
    """Parse QASM 2.0 into a Qrisp QuantumCircuit.

    Qrisp's optimisations target high-level Qrisp programs, so optimization_level is not
    applied to an imported circuit.
    """
    from qrisp import QuantumCircuit
    if optimization_level > 0:
        logger.info(
            f"Qrisp: optimization_level={optimization_level} requested "
            "but not applicable at the QASM circuit level; running at level 0.")
    return QuantumCircuit.from_qasm_str(qasm_str)


def _compile(payload: dict, qasm: str, notes=()) -> CompileResult:
    circuit = _parse(qasm, payload.get("optimization_level", 0))
    return CompileResult(
        circuit=circuit,
        n_qubits=get_num_qubits_from_qasm(qasm),
        preprocessing_applied=[_IMPORT_NOTE, *notes],
        transpiled_qasm=qasm,
        precision=_PRECISION)


def _counts_from_qrisp(counts, layout) -> dict:
    """Re-key Qrisp counts over every declared classical bit (lsb).

    A Qrisp key has one character per measured classical bit, highest bit leftmost.
    """
    char_clbits = sorted({clbit for _, clbit in layout.measures}, reverse=True)
    result: dict = {}
    for qrisp_key, count in counts.items():
        if len(qrisp_key) != len(char_clbits):
            raise ValueError(
                f"Qrisp key {qrisp_key!r} does not match the {len(char_clbits)} measurements")
        bits = [0] * layout.n_clbits
        for char, clbit in zip(qrisp_key, char_clbits):
            bits[clbit] = int(char)
        key = layout.key(bits, "lsb")
        result[key] = result.get(key, 0) + int(count)
    return result


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for Qrisp simulation.")

    def compile_step(payload):
        qasm, notes = prepare_statevector_qasm(payload["circuit_data"])
        return _compile(payload, qasm, notes)

    def execute(compiled, _payload):
        return compiled.circuit.statevector_array()

    def shape_statevector(statevector, _compiled, _payload):
        return np.asarray(statevector, dtype=complex)

    # statevector_array() is big-endian: qubit 0 is the most significant index bit.
    return run_statevector_job(
        simulator="qrisp", payload=payload, logger=logger, compile_fn=compile_step,
        execute_fn=execute, postprocess_fn=shape_statevector, qubit_ordering="msb",
        precision=_PRECISION)


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for Qrisp simulation.")

    def compile_step(payload):
        layout = parse_measurement_layout(payload["circuit_data"])
        if layout.has_reset:
            raise ValueError(
                "reset is not supported by this adapter: Qrisp's simulator returns 1 for "
                "'x q[0]; reset q[0]; measure q[0]'.")
        written = [clbit for _, clbit in layout.measures]
        if len(set(written)) != len(written):
            raise ValueError(
                "measuring into the same classical bit twice is not supported by this "
                "adapter: Qrisp's key order for repeated classical bits varies between runs.")
        _canonical_multi_measure()
        return _compile(payload, payload["circuit_data"], (_SAMPLING_NOTE, _CANONICAL_ORDER_NOTE))

    def seed_rng(_compiled, payload):
        """Qrisp's simulator samples from numpy's global RNG; run() takes no seed."""
        if payload.get("seed") is not None:
            np.random.seed(payload["seed"])
            random.seed(payload["seed"])

    def execute(compiled, payload):
        return compiled.circuit.run(shots=payload.get("n_shots", 1024))

    def shape_counts(counts, _compiled, payload):
        layout = parse_measurement_layout(payload["circuit_data"])
        return _counts_from_qrisp(counts, layout), "native"

    return run_measured_job(
        simulator="qrisp", payload=payload, logger=logger, compile_fn=compile_step,
        pre_execute_fn=seed_rng, execute_fn=execute, postprocess_fn=shape_counts,
        qubit_ordering="lsb", precision=_PRECISION)


register_runner_endpoints(app, process_run, process_run_measured)

logger.info("Qrisp runner API instantiated and ready to receive traffic.")

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "Qrisp")
