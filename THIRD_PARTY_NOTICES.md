# Third-party material

Quantum Rosetta is licensed under the Apache License 2.0 (`LICENSE`). This repository also contains
files from other projects, each under its own licence.

## Files in this repository

| Path | Origin | Licence |
|---|---|---|
| `rosetta-api/benchmarks/mqtbench/*.qasm` | Generated with MQT Bench (`mqt.bench` 1.1.9), Chair for Design Automation, Technical University of Munich | MIT; text in `rosetta-api/benchmarks/mqtbench/LICENSE` |
| `rosetta-api/benchmarks/qasmbench/*.qasm` | Subset of QASMBench, Battelle Memorial Institute / PNNL | Battelle licence; text in `rosetta-api/benchmarks/qasmbench/LICENSE` |
| `shared/qrosetta_commons/qelib1_qiskit.inc` | `qelib1.inc` as distributed with Qiskit 2.5.2 | Apache-2.0 |
| `compilers/quartz-compiler/shift10-normalise.patch`, `compilers/quartz-compiler/Nam_complete_ECC_set.json` | A patch to, and an ECC set generated with, Quartz (quantum-compiler/quartz) | Apache-2.0 (Quartz) |

## Container images

Each runner and compiler image installs one simulator SDK or compiler and its dependencies. Their
exact versions are in that image's `requirements.lock`, and each package keeps its own licence. Two
images have terms that restrict redistribution:

- **myQLM** (`runners/myqlm-runner`) is distributed by Eviden under its own licence agreement. Its
  image is built on the user's machine and is not published by this project.
- **cuQuantum** (`runners/cuquantum-runner`) uses NVIDIA's CUDA and cuStateVec libraries under
  NVIDIA's licence terms.

Compilers built from source (staq, Synthetiq, Quartz) are downloaded at image build time from the
upstream sources named in each Dockerfile, under their upstream licences.
