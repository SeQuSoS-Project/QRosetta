# MQTBench (bundled, algorithm level)

Source: MQT Bench (Munich Quantum Toolkit, https://www.cda.cit.tum.de/mqtbench/), generated with
`mqt.bench` 1.1.9. MIT licence, Copyright (c) 2024 Chair for Design Automation, Technical University
of Munich; the full text is in `LICENSE` in this directory.

Algorithm-level circuits are only available via the `mqt.bench` Python package, so they
are generated once (offline) by scripts/generate_mqtbench.py and committed as static
`*.qasm` files named `<algorithm>_n<qubits>.qasm`. The production API reads these files
directly and has no mqt.bench / qiskit dependency.

Re-generate / extend with:  python scripts/generate_mqtbench.py
