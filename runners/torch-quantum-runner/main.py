# Execution script for the quantum simulator runner.

from fastapi import FastAPI
from qrosetta_commons.helpers import register_runner_endpoints, run_cli_main
from qrosetta_commons.helpers import MemoryMonitor, get_logger, check_qubits_limit, MAX_QUBITS_STATEVECTOR, MAX_QUBITS_MEASURED, with_sdk_versions, statevector_result, counts_result, runner_error
import numpy as np
import time
import gc
import traceback

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

def _compile(qasm_str: str, optimization_level: int = 0):
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
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_STATEVECTOR)

        t0 = time.perf_counter()
        tq_module, n_qubits, preprocessing_applied, transpiled_qasm = _compile(payload["circuit_data"], payload.get("optimization_level", 0))
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            sv = _run_sv(tq_module, n_qubits)
            t3 = time.perf_counter()
            simulation_time = t3 - t2

        logger.info(
            f"TorchQuantum simulation successful in {compilation_time + simulation_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )
        return statevector_result(
            simulator="torchquantum", statevector=sv, compilation_time=compilation_time,
            simulation_time=simulation_time, monitor=monitor, qubit_ordering="msb",
            n_qubits=n_qubits, preprocessing_applied=preprocessing_applied,
            transpiled_qasm=transpiled_qasm)
    except Exception as e:
        logger.error(f"Error during TorchQuantum simulation: {str(e)}\n{traceback.format_exc()}")
        return runner_error("torchquantum", e)

@with_sdk_versions
def process_run_measured(payload: dict) -> dict:
    logger.info("Received circuit data for TorchQuantum measurement simulation.")
    if not TORCHQUANTUM_AVAILABLE:
        return runner_error("torchquantum", "TorchQuantum is not installed in this environment.")
    try:
        check_qubits_limit(payload["circuit_data"], MAX_QUBITS_MEASURED)

        t0 = time.perf_counter()
        tq_module, n_qubits, preprocessing_applied, transpiled_qasm = _compile(payload["circuit_data"], payload.get("optimization_level", 0))
        t1 = time.perf_counter()
        compilation_time = t1 - t0

        n_shots = payload.get("n_shots", 1024)

        with MemoryMonitor(interval=0.01) as monitor:
            gc.collect()

            t2 = time.perf_counter()
            sv = _run_sv(tq_module, n_qubits)

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

            sample_indices = torch.multinomial(
                probs.float(), num_samples=n_shots, replacement=True, generator=_gen
            ).numpy()

            fmt = f"{{:0{n_qubits}b}}"
            counts: dict[str, int] = {}
            for idx in sample_indices:
                bitstring = fmt.format(int(idx))
                counts[bitstring] = counts.get(bitstring, 0) + 1

            t3 = time.perf_counter()
            simulation_time = t3 - t2

        logger.info(
            f"TorchQuantum measurement simulation successful in {compilation_time + simulation_time:.4f}s "
            f"(Comp: {compilation_time:.4f}s, Sim: {simulation_time:.4f}s)."
        )
        return counts_result(
            simulator="torchquantum", counts=counts, sampling_method="sv_sample",
            compilation_time=compilation_time, simulation_time=simulation_time, monitor=monitor,
            qubit_ordering="msb", n_qubits=n_qubits, preprocessing_applied=preprocessing_applied,
            transpiled_qasm=transpiled_qasm)
    except Exception as e:
        logger.error(f"Error during TorchQuantum measurement simulation: {str(e)}\n{traceback.format_exc()}")
        return runner_error("torchquantum", e)

register_runner_endpoints(app, process_run, process_run_measured)

logger.info("TorchQuantum runner API instantiated and ready to receive traffic.")

if __name__ == "__main__":
    run_cli_main(app, process_run, process_run_measured, "TorchQuantum")
