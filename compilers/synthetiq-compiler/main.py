"""Synthetiq compiler: Qiskit translates the circuit exactly to h, rz and cx; when every rz
angle is a multiple of pi/4 the circuit is Clifford+T, and Synthetiq synthesises a new
Clifford+T circuit for its unitary by simulated annealing (one thread, one random stream
seeded with 0, at most a fixed number of annealing runs per level)."""

import time

import math
import os
import re
import subprocess
import tempfile

from fastapi import FastAPI
from qiskit import QuantumCircuit

from qrosetta_commons.compile_errors import CompileRefused, OutputRejected
from qrosetta_commons.compile_service import (
    declare_native_component, register_compiler_endpoint, run_compile_job,
    run_compiler_cli_main,
)
from qrosetta_commons.helpers import declare_sdk_packages, with_sdk_versions
from qrosetta_commons.qiskit_circuits import (
    split_final_measurements, translate_to_basis, translation_note, unitary_of,
)

declare_sdk_packages("qiskit")

app = FastAPI(title="Synthetiq Compiler")

SYNTHETIQ_BINARY = "/usr/local/bin/synthetiq"
GATES_DIR = "/usr/local/share/synthetiq/gates"
COMMIT = os.getenv("SYNTHETIQ_COMMIT", "not recorded")
MAX_QUBITS = 3
TIME_CAP_SEC = 280
CIRCUITS_PER_LEVEL = {0: 1, 1: 5}
MAX_RUNS_PER_LEVEL = {0: 1000, 1: 2000}
DECOMPOSITION_BASIS = ("h", "rz", "cx")
ANGLE_TOLERANCE = 1e-12
_T_POWERS = {0: [], 1: ["t"], 2: ["s"], 3: ["s", "t"], 4: ["s", "s"], 5: ["s", "s", "t"],
             6: ["sdg"], 7: ["tdg"]}
_OUTPUT_GATE = re.compile(r"^(h|s|sdg|t|tdg|cx) qubits\[(\d+)\](?:, qubits\[(\d+)\])?;$")
_FILE_NAME = re.compile(r"^(-?[\d.]+)-(\d+)-(\d+)-(\d+)-(\d+)\.qasm$")

declare_native_component(
    "synthetiq", f"commit {COMMIT}",
    source_url=f"https://github.com/eth-sri/synthetiq/archive/{COMMIT}.tar.gz",
    source_sha256=os.getenv("SYNTHETIQ_SHA256", "not recorded"),
    compiler_flags=os.getenv("SYNTHETIQ_CXXFLAGS", "not recorded"),
    patches=["max-runs.patch"])

_BUILD_NOTE = (f"Synthetiq (eth-sri/synthetiq, commit {COMMIT[:12]}) built from source without "
               f"-march=native or -ffast-math, with max-runs.patch (a --max-runs option that "
               f"stops the search after a number of annealing runs).")
_ANGLE_NOTE = ("Each rz(k*pi/4) written as Clifford+T gates for Synthetiq's reader (t, s, s t, "
               "s s, s s t, sdg, tdg for k = 1..7 mod 8), equal up to global phase.")
_REGISTER_NOTE = ("Synthetiq is given the qubits as one register in declaration order; its output "
                  "is renamed onto the input's registers, with the input's final measurements in "
                  "their original order.")


def _search_note(level: int) -> str:
    found, max_runs = CIRCUITS_PER_LEVEL[level], MAX_RUNS_PER_LEVEL[level]
    if found == 1:
        which = ("the first circuit found. Annealing minimises the distance to the target unitary, "
                 "and Synthetiq's resynthesis then lowers the circuit's cost; level 0 does not "
                 "minimise the T-count and can return more T gates than the input")
    else:
        which = (f"the lowest-cost of the circuits found, up to {found}, by Synthetiq's cost (T and "
                 f"T-dagger 1, CX 0.1, H, S, S-dagger 0.01); when the run cap ends the search with "
                 f"fewer, the cheapest of those")
    return (f"synthetiq <input>.qasm --gate-set CliffordT --threads 1 --circuits {found} "
            f"--max-runs {max_runs} --time {TIME_CAP_SEC}: simulated annealing over Clifford+T "
            f"circuits for the input's unitary, then Synthetiq's resynthesis; {which}. With one "
            f"thread Synthetiq draws the whole search from one mt19937 stream seeded with 0 "
            f"(seed = thread + outer run x threads), so the output, or the failure to find a "
            f"circuit within {max_runs} runs, depends only on the input; the time cap or the job's "
            f"timeout can only end a search early, which is reported as an error.")


def equivalent(input_qasm: str, output_qasm: str) -> bool:
    """The output has the input's unitary up to global phase and the same final measurements,
    both read by Qiskit."""
    source, source_measures = split_final_measurements(QuantumCircuit.from_qasm_str(input_qasm), "Synthetiq")
    output, output_measures = split_final_measurements(QuantumCircuit.from_qasm_str(output_qasm), "Synthetiq")
    return source_measures == output_measures and unitary_of(output).equiv(unitary_of(source), atol=1e-8)


def _clifford_t_lines(circuit: QuantumCircuit):
    """(Synthetiq input lines, largest change to an angle in rad, barriers seen) for an
    h/rz/cx circuit; CompileRefused for an rz angle that is not a multiple of pi/4."""
    lines, largest, barriers = [], 0.0, False
    for inst in circuit.data:
        name = inst.operation.name
        wires = [circuit.find_bit(q).index for q in inst.qubits]
        if name == "barrier":
            barriers = True
            continue
        if name == "h":
            lines.append(f"h q[{wires[0]}];")
        elif name == "cx":
            lines.append(f"cx q[{wires[0]}],q[{wires[1]}];")
        elif name == "rz":
            angle = float(inst.operation.params[0])
            steps = angle / (math.pi / 4)
            k = round(steps)
            if abs(steps - k) > ANGLE_TOLERANCE:
                raise CompileRefused(
                    f"Synthetiq is offered for Clifford+T circuits only: after translation to "
                    f"h, rz and cx this circuit has rz({angle!r}), which is not a multiple of "
                    f"pi/4")
            largest = max(largest, abs(angle - k * math.pi / 4))
            lines += [f"{g} q[{wires[0]}];" for g in _T_POWERS[k % 8]]
        else:
            raise CompileRefused(f"decomposition left a gate Synthetiq cannot take: {name}")
    return lines, largest, barriers


def _synthesise(n_qubits: int, lines: list, circuits: int, max_runs: int) -> str:
    """(Synthetiq's chosen output file text, circuits found); ValueError when it found none, or
    fewer than asked when the time cap ended the search."""
    with tempfile.TemporaryDirectory() as workdir:
        os.makedirs(os.path.join(workdir, "data", "input"))
        os.makedirs(os.path.join(workdir, "data", "output"))
        os.symlink(GATES_DIR, os.path.join(workdir, "data", "gates"))
        with open(os.path.join(workdir, "data", "input", "c.qasm"), "w") as fh:
            fh.write("\n".join(['OPENQASM 2.0;', 'include "qelib1.inc";', f"qreg q[{n_qubits}];", *lines]) + "\n")
        started = time.monotonic()
        run = subprocess.run(
            [SYNTHETIQ_BINARY, "c.qasm", "--gate-set", "CliffordT", "--threads", "1",
             "--circuits", str(circuits), "--max-runs", str(max_runs), "--time", str(TIME_CAP_SEC)],
            capture_output=True, text=True, cwd=workdir, timeout=None,
            env={**os.environ, "OMP_NUM_THREADS": "1"})
        elapsed = time.monotonic() - started
        if run.returncode != 0:
            raise ValueError(f"Synthetiq exited with status {run.returncode}")
        folder = os.path.join(workdir, "data", "output", "c")
        found = []
        for name in os.listdir(folder) if os.path.isdir(folder) else []:
            match = _FILE_NAME.match(name)
            if match:
                found.append((float(match.group(1)), int(match.group(5)), name))
        stopped_by_time = elapsed >= TIME_CAP_SEC - 5
        if len(found) < circuits and (stopped_by_time or not found):
            limit = (f"its {TIME_CAP_SEC} s time cap ({elapsed:.0f} s; depends on machine load)"
                     if stopped_by_time else f"{max_runs} annealing runs ({elapsed:.0f} s)")
            raise ValueError(
                f"Synthetiq found {len(found)} of the {circuits} circuit(s) asked for when it "
                f"stopped at {limit}, so none is reported")
        with open(os.path.join(folder, min(found)[2])) as fh:
            return fh.read(), len(found)


def _register_names(circuit: QuantumCircuit) -> list:
    names = []
    for bit in circuit.qubits:
        register, index = circuit.find_bit(bit).registers[0]
        names.append(f"{register.name}[{index}]")
    return names


def _clbit_name(circuit: QuantumCircuit, index: int) -> str:
    register, local = circuit.find_bit(circuit.clbits[index]).registers[0]
    return f"{register.name}[{local}]"


def _encode(original: QuantumCircuit, text: str, measures) -> str:
    """Synthetiq's gate lines on the input's registers, with the input's declarations and
    final measurements; ValueError on any other line."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    header = ["OPENQASM 2.0;", 'include "qelib1.inc";', f"qreg qubits[{original.num_qubits}];"]
    if lines[:3] != header:
        raise ValueError(f"Synthetiq's output starts with {lines[:3]}, expected {header}")
    wires = _register_names(original)
    out = ["OPENQASM 2.0;", 'include "qelib1.inc";']
    out += [f"qreg {r.name}[{r.size}];" for r in original.qregs]
    out += [f"creg {r.name}[{r.size}];" for r in original.cregs]
    for line in lines[3:]:
        match = _OUTPUT_GATE.match(line)
        if not match:
            raise ValueError(f"Synthetiq wrote a line the adapter does not read: {line[:200]}")
        gate, first, second = match.groups()
        if (gate == "cx") != (second is not None):
            raise ValueError(f"Synthetiq wrote a gate with the wrong number of qubits: {line[:200]}")
        operands = wires[int(first)] + (f",{wires[int(second)]}" if second is not None else "")
        out.append(f"{gate} {operands};")
    for qubit, clbit in measures:
        out.append(f"measure {wires[qubit]} -> {_clbit_name(original, clbit)};")
    return "\n".join(out) + "\n"


def _pipeline(level: int):
    def run(qasm: str):
        original = QuantumCircuit.from_qasm_str(qasm)
        if original.num_qubits > MAX_QUBITS:
            raise CompileRefused(
                f"Synthetiq synthesises from the full unitary; this adapter takes circuits of at "
                f"most {MAX_QUBITS} qubits, and this one has {original.num_qubits}")
        unitary, measures = split_final_measurements(original, "Synthetiq")
        translated = translate_to_basis(unitary, DECOMPOSITION_BASIS)
        lines, largest, barriers = _clifford_t_lines(translated)
        if lines:
            text, n_found = _synthesise(original.num_qubits, lines, CIRCUITS_PER_LEVEL[level],
                                        MAX_RUNS_PER_LEVEL[level])
            search = [_search_note(level)]
            if n_found < CIRCUITS_PER_LEVEL[level]:
                search.append(f"Synthetiq found {n_found} of {CIRCUITS_PER_LEVEL[level]} circuits within "
                              f"{MAX_RUNS_PER_LEVEL[level]} runs; the cheapest of those is returned.")
        else:
            text = "\n".join(["OPENQASM 2.0;", 'include "qelib1.inc";', f"qreg qubits[{original.num_qubits}];"])
            search = ["The circuit has no gates after translation (the identity), so it is returned "
                      "with none and Synthetiq is not run."]
        output = _encode(original, text, measures)
        if not equivalent(qasm, output):
            raise OutputRejected("Synthetiq's output does not have the input's unitary, so it is not reported")
        angle_note = _ANGLE_NOTE + (f" The largest change to an angle in this circuit is {largest:.3g} rad "
                                    f"(angles within {ANGLE_TOLERANCE:g} of a multiple of pi/4, in units "
                                    f"of pi/4, are taken as that multiple)." if largest else "")
        notes = [translation_note(DECOMPOSITION_BASIS), angle_note, _BUILD_NOTE, *search,
                 *(["Barriers removed: Synthetiq synthesises the circuit's whole unitary."] if barriers else []),
                 _REGISTER_NOTE,
                 "Checked: the output has the input's unitary (Qiskit Operator equality up to global phase)."]
        return output, notes
    return run


PIPELINES = {level: _pipeline(level) for level in CIRCUITS_PER_LEVEL}

CLIFFORD_T_PROBES = {
    "pauli_then_t": "x q[0];\nt q[0];\ns q[1];\nh q[1];\nh q[2];\n",
    "controlled_phases": "h q[0];\ncu1(pi/2) q[0],q[1];\ncz q[1],q[2];\nh q[2];\n",
    "swap_and_toffoli": "h q[0];\nswap q[0],q[2];\nccx q[0],q[1],q[2];\nt q[1];\n",
    "angles_past_two_pi": "h q[0];\nrz(9*pi/4) q[0];\nrz(-pi/2) q[1];\nh q[2];\nu1(3*pi/4) q[2];\ncx q[0],q[2];\n",
    "classical_register_declared": "creg c[3];\nh q[0];\ncx q[0],q[1];\ntdg q[2];\n",
    "identity_after_translation": "h q[0];\nh q[0];\nrz(2*pi) q[1];\nbarrier q;\n",
}


@with_sdk_versions
def process_compile(payload: dict) -> dict:
    return run_compile_job(compiler="synthetiq", payload=payload, pipelines=PIPELINES)


register_compiler_endpoint(app, process_compile)

if __name__ == "__main__":
    run_compiler_cli_main(app, process_compile, "Synthetiq", levels=sorted(PIPELINES),
                          equivalent=equivalent, probes=CLIFFORD_T_PROBES)
