# Execution script for the quantum simulator runner.

from fastapi import FastAPI
from qrosetta_commons.helpers import (
    CompileResult, get_logger, register_runner_endpoints, run_cli_main,
    run_measured_job, run_statevector_job, runner_error, with_sdk_versions,
)
import numpy as np

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

    # torchquantum 0.1.8 (latest PyPI release) ships 9 gate functions across
    # functional/{u1,u2,paulix,hadamard,single_excitation}.py that reference an
    # unimported module-global `mat_dict`, raising NameError at runtime for any
    # circuit containing u1/cu1/u2/cu2/toffoli/rc3x/rccx/chadamard/singleexcitation
    # (upstream: mit-han-lab/torchquantum#226; fixed on GitHub main for 7 of the 9
    # but never republished to PyPI). Alias the correctly populated package-level
    # dict into each affected module so these gates execute. importlib.import_module
    # is required here: `torchquantum.functional`'s own `from .u2 import u2` rebinds
    # the `u2` attribute on the package to the function of the same name, so a plain
    # `import torchquantum.functional.u2 as m` resolves to that function, not the module.
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

def _to_tq_module(qasm_str: str, optimization_level: int = 0):
    """Parse QASM 2.0 with Qiskit and convert to a TorchQuantum module.

    Level 0: no optimization (but still decomposes to safe basis gates)
    Level 1: Qiskit transpiler level 1 (single-qubit gate consolidation, basic cancellation)
    Level 2: Qiskit transpiler level 2 (unitary synthesis + gate cancellation)

    We always transpile with _TQ_BASIS_GATES regardless of opt level to ensure
    gates like cu1/u1 are decomposed into gates TorchQuantum can handle.

    Returns (tq_module, n_qubits).
    """
    qc = QiskitCircuit.from_qasm_str(qasm_str)

    preprocessing_applied = []
    qc = qiskit_transpile(
        qc,
        optimization_level=min(max(optimization_level, 0), 2),
        basis_gates=_TQ_BASIS_GATES,
    )
    preprocessing_applied.append(f"qiskit.compiler.transpile(level={min(max(optimization_level, 0), 2)}, basis_gates={_TQ_BASIS_GATES}): Native Qiskit transpilation pass applied to ensure all complex gates are decomposed into a safe basis set supported by TorchQuantum.")

    transpiled_qasm = qasm2.dumps(qc)
    qc.remove_final_measurements(inplace=True)
    n_qubits = qc.num_qubits
    tq_module = qiskit2tq(qc)
    return tq_module, n_qubits, preprocessing_applied, transpiled_qasm


def _compile(payload: dict) -> CompileResult:
    tq_module, n_qubits, preprocessing_applied, transpiled_qasm = _to_tq_module(
        payload["circuit_data"], payload.get("optimization_level", 0))
    return CompileResult(
        circuit=tq_module,
        n_qubits=n_qubits,
        preprocessing_applied=preprocessing_applied,
        transpiled_qasm=transpiled_qasm)

def _run_sv(tq_module, n_qubits: int) -> np.ndarray:
    """Execute the TorchQuantum module and return a numpy complex statevector."""
    qdev = tq.QuantumDevice(n_wires=n_qubits, bsz=1, device="cpu")
    with torch.no_grad():
        tq_module(qdev)

    sv = qdev.get_states_1d().detach().cpu().numpy()[0]
    return sv

@with_sdk_versions
def process_run(payload: dict) -> dict:
    logger.info("Received circuit data for TorchQuantum statevector simulation.")
    if not TORCHQUANTUM_AVAILABLE:
        return runner_error("torchquantum", "TorchQuantum is not installed in this environment.")

    def execute(compiled, _payload):
        return _run_sv(compiled.circuit, compiled.n_qubits)

    return run_statevector_job(
        simulator="torchquantum", payload=payload, logger=logger, compile_fn=_compile,
        execute_fn=execute, qubit_ordering="msb")


@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received circuit data for TorchQuantum measurement simulation.")
    if not TORCHQUANTUM_AVAILABLE:
        return runner_error("torchquantum", "TorchQuantum is not installed in this environment.")

    def execute(compiled, payload):
        sv = _run_sv(compiled.circuit, compiled.n_qubits)

        probs = torch.tensor(np.abs(sv) ** 2, dtype=torch.float64)
        probs = torch.clamp(probs, min=0.0)
        probs = probs / probs.sum()

        # Optional reproducible sampling via a local generator; seed=None
        # leaves torch's default (non-deterministic) RNG, the prior behaviour.
        _seed = payload.get("seed")
        _gen = None
        if _seed is not None:
            _gen = torch.Generator()
            _gen.manual_seed(int(_seed))

        return torch.multinomial(
            probs.float(), num_samples=payload.get("n_shots", 1024),
            replacement=True, generator=_gen,
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
        execute_fn=execute, postprocess_fn=shape_counts, qubit_ordering="msb")


register_runner_endpoints(app, process_run, process_run_measured)

logger.info("TorchQuantum runner API instantiated and ready to receive traffic.")

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "TorchQuantum")
