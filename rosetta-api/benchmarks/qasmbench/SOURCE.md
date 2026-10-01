# QASMBench (bundled subset)

Source: https://github.com/pnnl/QASMBench (PNNL / Battelle, BSD/MIT-style — see LICENSE).

Bundled here: the base `*.qasm` circuits (excluding the repo's `*_transpiled.qasm`
siblings) that are runnable on this platform — i.e. ≤ MAX_QUBITS_MEASURED qubits,
≤ MAX_QASM_SIZE bytes, ≤ MAX_QASM_GATES gates. Circuits exceeding those limits (the
medium/large categories run to hundreds of qubits) are intentionally omitted because
the API would reject them anyway.

These are served as static files by services/benchmark_library.py — the API has no
quantum-SDK dependency for benchmark loading.

Three bundled files are not valid OpenQASM 2.0 as distributed upstream and are not listed:
`sat_n11` (no `OPENQASM 2.0;` header) and `vqe_uccsd_n4`, `vqe_uccsd_n6` (they measure
`q[...]` while declaring only `qreg reg[...]` and no classical register). Fetching one returns
422 with that reason.
