"""A compile-only processor for test_compile_service: the identity pipeline at level 0 and
a pipeline that drops every gate at level 1."""
from qrosetta_commons.compile_service import run_compile_job


def _identity(qasm):
    return qasm, ["identity"]


def _drop_gates(qasm):
    head = [line for line in qasm.splitlines() if line.startswith(("OPENQASM", "include", "qreg"))]
    return "\n".join(head) + "\n", ["drop every gate"]


PIPELINES = {0: _identity, 1: _drop_gates}


def process_compile(payload):
    return run_compile_job(compiler="fixture", payload=payload, pipelines=PIPELINES)


def same_text(input_qasm, output_qasm):
    return input_qasm == output_qasm
