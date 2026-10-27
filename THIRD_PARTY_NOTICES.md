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
exact versions are in that image's `requirements.lock`, and each package keeps its own licence. Three
images are built on the user's machine and not published by this project:

- **myQLM** (`runners/myqlm-runner`) is distributed by Eviden under its own licence agreement. Its
  image is built on the user's machine and is not published by this project.
- **cuQuantum** (`runners/cuquantum-runner`) uses NVIDIA's CUDA and cuStateVec libraries under
  NVIDIA's licence terms. Its image is built on the user's machine and is not published by this
  project.
- **BQSKit** (`compilers/bqskit-compiler`) installs `bqskitrs` 0.4.1, which links NLopt (LGPL-2.1)
  statically and has no published source for that version (below). Until upstream publishes it, the
  image is built on the user's machine and is not published by this project.

Compilers built from source (staq, Synthetiq, Quartz) are downloaded at image build time from the
upstream sources named in each Dockerfile, under their upstream licences: staq MIT, Synthetiq MIT,
Quartz Apache-2.0.

## Published images

The release workflow publishes every other image to `ghcr.io/sequsos-project/qrosetta-<name>`. Each
published image carries the label `org.qrosetta.third-party-notices`, the address of this file at
the commit the image was built from, and has an SPDX software bill of materials (made with syft)
attached to it in the registry as a signed attestation. The SBOM lists every Debian, Alpine and
Python package in the image with its version and declared licence; `gh attestation verify
oci://IMAGE --owner SeQuSoS-Project --predicate-type https://spdx.dev/Document/v2.3` checks it.

### Components under the GPL or the LGPL

The images contain unmodified binaries of the following copyleft components. The table names
where the corresponding source is published; the written offer below covers all of them.

| Component | Licence | Images | Source |
|---|---|---|---|
| Debian base system of `python:3.10-slim` and `python:3.11-slim` (glibc, bash, coreutils, dpkg, tar and others) | GPL-2.0, GPL-3.0, LGPL-2.1 and others, per package | every image except nginx | Debian source packages of the versions in the image's SBOM, at <https://snapshot.debian.org/>; the base image digests are in each Dockerfile |
| `build-essential` (GCC, binutils, make), installed and kept in the image | GPL-3.0-or-later; GCC's runtime libraries GPL-3.0-or-later with the GCC Runtime Library Exception 3.1 | qrisp, quimb and torchquantum runners | Debian source packages, as above |
| Alpine base system of `nginx:alpine` (BusyBox and others) | BusyBox GPL-2.0-only; others per package | nginx | <https://gitlab.alpinelinux.org/alpine/aports> at the Alpine release in the image's SBOM |
| NLopt 2.7.1, statically linked into `bqskitrs` 0.4.1 (`bqskitrs/bqskitrs.abi3.so`) | LGPL-2.1-or-later | bqskit compiler | <https://github.com/stevengj/nlopt/archive/refs/tags/v2.7.1.tar.gz>; bqskitrs itself (BSD-3-Clause; see below) at <https://github.com/BQSKit/bqskitrs> |
| libquadmath (from GCC), bundled in the Linux wheels of numpy, scipy, qiskit-aer and bqskitrs (`*.libs/libquadmath-*.so.0`) | LGPL-2.1-or-later | every image except nginx | GCC source at <https://gcc.gnu.org/>, release named in the library's `.comment` section (GCC 10.2.1, Red Hat devtoolset-10, for bqskitrs) |
| GMP, MPFR, MPC and FLINT, bundled in the Linux wheels of symengine 0.13.0 and 0.14.1 (`symengine.libs/`) | GMP: LGPL-3.0-or-later or GPL-2.0-or-later; MPFR, MPC, FLINT: LGPL-3.0-or-later | qiskit, pennylane-lightning, pennylane-default, qrisp and torchquantum runners | the build recipes at <https://github.com/symengine/symengine-wheels> (tags v0.13.0, v0.14.1) name the upstream releases; <https://gmplib.org/>, <https://www.mpfr.org/>, <https://www.multiprecision.org/mpc/>, <https://flintlib.org/> |
| psycopg2-binary 2.9.12 | LGPL-3.0-or-later with the OpenSSL exception | api | <https://github.com/psycopg/psycopg2/tree/2.9.12> |
| libxcrypt and keyutils, bundled in the psycopg2-binary wheel (`libcrypt`, `libkeyutils`) | LGPL-2.1-or-later | api | <https://github.com/besser82/libxcrypt>, <https://git.kernel.org/pub/scm/linux/kernel/git/dhowells/keyutils.git> |
| libgfortran and libgomp (from GCC), bundled in the Linux wheels of numpy, scipy, qiskit-aer, bqskitrs, qulacs, qsimcirq, pennylane-lightning and pyquest; libgomp from Debian in the quartz and synthetiq compilers | GPL-3.0-or-later with the GCC Runtime Library Exception 3.1 | every image except nginx | GCC source, as for libquadmath |

`bqskitrs` 0.4.1 is published on PyPI as wheels only, with no source distribution, and its
repository has no 0.4.1 tag; the `main` branch declares version 0.4.1 in `pyproject.toml`. Its own
Rust code is under BSD-3-Clause and does not oblige a source offer; the NLopt it links statically
does.

Written offer: for at least three years after the last image of a release is published, the
maintainers will provide anyone, on request, the complete corresponding source code of every GPL-
or LGPL-licensed component in that image, for no more than the cost of performing the transfer.
Ask through the issue tracker of <https://github.com/SeQuSoS-Project/QRosetta>, naming the image and
its digest.

### Components under the MPL-2.0 and the EPL-2.0

certifi, tqdm and tdqm (MPL-2.0) and Qrisp (EPL-2.0) are Python source in the images, in the form
upstream publishes. The pyzmq 27.1.0 wheel bundles a compiled libzmq (MPL-2.0), whose source is at
<https://github.com/zeromq/pyzmq/tree/v27.1.0> (bundled libzmq) and <https://github.com/zeromq/libzmq>.
