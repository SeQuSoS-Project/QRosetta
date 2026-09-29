"""myQLM runner: parses OpenQASM 2.0 with qat.interop's OqasmParser and simulates it on PyLinalg."""

from fastapi import FastAPI
from qrosetta_commons.helpers import (
    CompileResult, get_logger, register_runner_endpoints, run_cli_main,
    run_measured_job, run_statevector_job, with_sdk_versions,
)
import re
import numpy as np
import pytket.qasm
from pytket.passes import auto_rebase_pass
from pytket.circuit import OpType

from qat.interop.openqasm import OqasmParser
from qat.qpus import PyLinalg

logger = get_logger("myqlm-runner")

app = FastAPI(title="myQLM Runner")

_qpu = PyLinalg()

_PRECISION = "complex128"

_REBASE_NOTE = (
    "pytket.passes.auto_rebase_pass({CX, Rz, Rx}): Decomposes every gate into a CX/Rz/Rx "
    "basis, because OqasmParser/PyLinalg reject gates such as cu3, crx and tdg. The global "
    "phase pytket tracks is not carried by the emitted QASM, and pytket emits quantum "
    "registers in alphabetical order of their names rather than declaration order.")
_TDG_NOTE = (
    "Regex substitution tdg -> u1(-pi/4): PyLinalg has no matrix for the parsed tdg gate "
    "(D-T); u1(-pi/4) = diag(1, e^{-i pi/4}) is the identical matrix. Required by the "
    "adapter, applied when apply_preprocessing is False.")
_SAMPLING_NOTE = (
    "PyLinalg SAMPLE job: returns per-state frequencies; counts are rebuilt as "
    "round(frequency * n_shots) after the timed window.")


def _preprocess_qasm(qasm_str: str, apply_preprocessing: bool) -> tuple[str, list[str]]:
    """Rewrite gates PyLinalg cannot simulate; returns (qasm, preprocessing notes)."""
    if apply_preprocessing:
        tk_circ = pytket.qasm.circuit_from_qasm_str(qasm_str)
        auto_rebase_pass({OpType.CX, OpType.Rz, OpType.Rx}).apply(tk_circ)
        return pytket.qasm.circuit_to_qasm_str(tk_circ), [_REBASE_NOTE]
    return re.sub(r"\btdg\b", "u1(-pi/4)", qasm_str), [_TDG_NOTE]


def _compile(payload: dict, extra_notes=()) -> CompileResult:
    """Preprocess and parse into a myQLM Circuit (fresh parser per call: OqasmParser is stateful).

    PyLinalg exposes no circuit optimisation passes, so optimization_level is not applied.
    """
    optimization_level = payload.get("optimization_level", 0)
    if optimization_level > 0:
        logger.info(
            f"myQLM: optimization_level={optimization_level} requested "
            "but not supported by PyLinalg; running at level 0.")
    transpiled_qasm, preprocessing_applied = _preprocess_qasm(
        payload["circuit_data"], payload.get("apply_preprocessing", True))
    circuit = OqasmParser().compile(transpiled_qasm)
    return CompileResult(
        circuit=circuit,
        n_qubits=circuit.nbqbits,
        preprocessing_applied=preprocessing_applied + list(extra_notes),
        transpiled_qasm=transpiled_qasm,
        precision=_PRECISION)


@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for myQLM simulation.")

    def execute(compiled, _payload):
        return _qpu.submit(compiled.circuit.to_job(job_type="SAMPLE", nbshots=0))

    def shape_statevector(result, compiled, _payload):
        sv = np.zeros(2 ** compiled.n_qubits, dtype=np.complex128)
        for sample in result:
            if sample.amplitude is not None:
                sv[sample.state.int] = sample.amplitude
        return sv

    return run_statevector_job(
        simulator="myqlm", payload=payload, logger=logger, compile_fn=_compile,
        execute_fn=execute, postprocess_fn=shape_statevector, qubit_ordering="msb",
        precision=_PRECISION)


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received measured circuit data for myQLM simulation.")

    def compile_step(payload):
        return _compile(payload, extra_notes=(_SAMPLING_NOTE,))

    def seed_rng(_compiled, payload):
        """PyLinalg samples from numpy's global RNG; the QPU exposes no seed argument."""
        if payload.get("seed") is not None:
            np.random.seed(payload["seed"])

    def execute(compiled, payload):
        job = compiled.circuit.to_job(
            job_type="SAMPLE", nbshots=payload.get("n_shots", 1024))
        return _qpu.submit(job)

    def shape_counts(result, compiled, payload):
        """Rebuild integer counts from frequencies, which are exact multiples of 1/n_shots."""
        n_shots = payload.get("n_shots", 1024)
        n_qubits = compiled.n_qubits
        counts_dict = {
            format(sample.state.int, f"0{n_qubits}b"): round(sample.probability * n_shots)
            for sample in result
            if round(sample.probability * n_shots) > 0
        }
        diff = n_shots - sum(counts_dict.values())
        if diff != 0 and counts_dict:
            top = max(counts_dict, key=counts_dict.get)
            counts_dict[top] += diff
        return counts_dict, "native"

    return run_measured_job(
        simulator="myqlm", payload=payload, logger=logger, compile_fn=compile_step,
        pre_execute_fn=seed_rng, execute_fn=execute, postprocess_fn=shape_counts,
        qubit_ordering="msb", precision=_PRECISION)


register_runner_endpoints(app, process_run, process_run_measured)

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "myQLM")
