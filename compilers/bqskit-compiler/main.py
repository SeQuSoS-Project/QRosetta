"""BQSKit compiler: bqskit.compile partitions the circuit into blocks and resynthesises
them numerically, at BQSKit optimization levels 1 to 3."""

from fastapi import FastAPI
from bqskit import compile as bqskit_compile
from bqskit.compiler import Compiler
from bqskit.ir.lang.qasm2 import OPENQASM2Language

from qrosetta_commons.compile_service import (
    register_compiler_endpoint, run_compile_job, run_compiler_cli_main,
)
from qrosetta_commons.helpers import declare_sdk_packages, with_sdk_versions

declare_sdk_packages("bqskit", "bqskitrs")

app = FastAPI(title="BQSKit Compiler")

SEED = 0
MAX_SYNTHESIS_SIZE = 3
SYNTHESIS_EPSILON = 1e-8

_PARSE_NOTE = "bqskit.ir.lang.qasm2.OPENQASM2Language().decode(): BQSKit's OpenQASM 2.0 parser."
_ENCODE_NOTE = ("OPENQASM2Language().encode(): the output circuit as OpenQASM 2.0, one register "
                "q; resynthesised blocks equal the input blocks up to synthesis_epsilon in "
                "Hilbert-Schmidt distance, so the output approximates the input unitary.")


def _pipeline(level: int):
    def run(qasm: str):
        language = OPENQASM2Language()
        circuit = language.decode(qasm)
        with Compiler(num_workers=1) as compiler:
            output = bqskit_compile(circuit, optimization_level=level, seed=SEED,
                                    max_synthesis_size=MAX_SYNTHESIS_SIZE,
                                    synthesis_epsilon=SYNTHESIS_EPSILON, compiler=compiler)
        compile_note = (f"bqskit.compile(optimization_level={level}, "
                        f"max_synthesis_size={MAX_SYNTHESIS_SIZE}, "
                        f"synthesis_epsilon={SYNTHESIS_EPSILON}, seed={SEED}) with one "
                        f"worker and no machine model (all-to-all, BQSKit's default gate set).")
        return language.encode(output), [_PARSE_NOTE, compile_note, _ENCODE_NOTE]
    return run


PIPELINES = {level: _pipeline(level) for level in (1, 2, 3)}


def equivalent(input_qasm: str, output_qasm: str) -> bool:
    """Output unitary within 1e-6 Hilbert-Schmidt distance of the input's, both built by BQSKit."""
    language = OPENQASM2Language()
    distance = language.decode(input_qasm).get_unitary().get_distance_from(
        language.decode(output_qasm).get_unitary())
    return distance < 1e-6


# bqskit.compiler.Compiler binds fixed ports (7472 and 7474) for its runtime server and
# workers, so two compiles in one container collide.
SINGLE_COMPILE = 1

@with_sdk_versions
def process_compile(payload: dict) -> dict:
    return run_compile_job(compiler="bqskit", payload=payload, pipelines=PIPELINES)


register_compiler_endpoint(app, process_compile, max_concurrent=SINGLE_COMPILE)

if __name__ == "__main__":
    run_compiler_cli_main(app, process_compile, "BQSKit", levels=sorted(PIPELINES), equivalent=equivalent)
