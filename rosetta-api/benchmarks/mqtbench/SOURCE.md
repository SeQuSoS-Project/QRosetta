# MQTBench (bundled, algorithm level)

Source: MQT Bench (Munich Quantum Toolkit, https://www.cda.cit.tum.de/mqtbench/, MIT).

Algorithm-level circuits are only available via the `mqt.bench` Python package, so they
are generated once (offline) by scripts/generate_mqtbench.py and committed as static
`*.qasm` files named `<algorithm>_n<qubits>.qasm`. The production API reads these files
directly and has no mqt.bench / qiskit dependency.

Re-generate / extend with:  python scripts/generate_mqtbench.py
