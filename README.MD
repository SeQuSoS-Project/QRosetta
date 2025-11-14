# Quantum Rosetta

**Quantum Rosetta** is a production-grade microservices architecture designed to benchmark, validate, and analyze quantum circuit simulators. It acts as a translation layer and orchestration engine ("The Brain") that dispatches quantum tasks to isolated simulator containers ("The Hands") to measure fidelity, execution time, and memory efficiency.

## System Architecture

The system follows a strict **Microservices Architecture** orchestrated by Docker Compose.

### 1. The Brain (rosetta-api)
* **Role:** Orchestration, Content Generation, Comparative Analysis, UI Hosting.
* **Tech Stack:** Python 3.10, FastAPI, Pytket, NumPy, SciPy.
* **Key Functions:**
    * **Dynamic Generation:** Creates valid QASM 2.0 for algorithms like GHZ, QFT, Grover, and VQE on-the-fly.
    * **Asynchronous Dispatch:** Sends tasks to runners in parallel without blocking.
    * **Math Engine:** Calculates Fidelity Matrices and Jensen-Shannon Divergence in a non-blocking thread pool.

### 2. The Hands (Simulators)
Eight isolated runner services, each wrapping a specific quantum simulation framework.
* **Standardization:** All runners implement a strict contract (`POST /run`, `POST /run_measured`).
* **Supported Frameworks:**
    * **Qiskit Aer** (Statevector & Measurement)
    * **Cirq** (Google)
    * **Qulacs** (High-performance C++ backend)
    * **AWS Braket** (Local Simulator)
    * **ProjectQ**
    * **QuEST** (Quantum Exact Simulation Toolkit)
    * **PennyLane Lightning** (C++ optimized)
    * **PennyLane Default** (Python reference)

---

## Getting Started

### Prerequisites
* **Docker Engine** (v20.10+)
* **Docker Compose** (v2.0+)

### Deployment
This project is configured for **production deployment** by default (no volume mounts, non-root users).

1.  **Clone the Repository**
    ```bash
    git clone [https://github.com/SeQuSoS-Project/qrosetta.git](https://github.com/SeQuSoS-Project/qrosetta.git)
    cd qrosetta
    ```

2.  **Build and Run**
    ```bash
    docker compose up --build
    ```
    *Note: The first build may take time as it compiles dependencies for 9 separate containers.*

3.  **Access the Interface**
    * **Web UI:** [http://localhost:8000](http://localhost:8000)
    * **API Docs (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Security & Reliability Features

This project has undergone a rigorous **Hardening Sprint** to ensure stability and security.

* **Non-Root Execution:** All containers run as an unprivileged user (`appuser`) to prevent container breakout attacks.
* **Resource Limits:** Every service is capped at **0.5 CPUs** and **512MB RAM** to prevent "Logic Bomb" circuits from crashing the host.
* **Pinned Dependencies:** All `requirements.txt` files use strict version pinning (e.g., `pennylane==0.39.0`, `autoray==0.6.12`) to prevent dependency drift.
* **Event Loop Optimization:** Heavy mathematical operations (Fidelity calculation) are offloaded to thread executors to keep the API responsive under load.
* **Internal Optimization:** Batch processing uses direct internal awaits instead of network loopbacks, eliminating TCP overhead.

---

## API Reference

### Core Endpoints

#### 1. Run Batch Suite
Executes a playlist of quantum tasks across all available runners.

* **POST** `/run_batch_suite`
* **Payload:**
    ```json
    {
      "mode": "statevector",
      "n_shots": 1024,
      "tasks": [
        {"algorithm": "ghz", "qubits": 5},
        {"algorithm": "qft", "qubits": 3}
      ]
    }
    ```

#### 2. Generate Circuit
Returns the raw QASM 2.0 string for a specific algorithm.

* **POST** `/generate_circuit`
* **Payload:** `{"algorithm": "grover", "qubits": 4}`

#### 3. Compare Single Circuit
Parses a raw QASM string and runs it against all simulators.

* **POST** `/compare`
* **Payload:** `{"qasm_string": "OPENQASM 2.0; ..."}`

---

## Project Structure

```text
.
├── docker-compose.yml          # Orchestration & Resource Limits
├── rosetta-api/                # The Brain
│   ├── main.py                 # API Entrypoint & Logic
│   ├── library.py              # Circuit Generators (GHZ, QFT, etc.)
│   ├── comparator.py           # Fidelity & JS Divergence Math
│   └── static/                 # Web Frontend
├── shared/                     # Shared Logic
│   └── qrosetta_commons/       # Pydantic Models & MemoryMonitor
├── pytket-qiskit-runner/       # Qiskit Runner
├── pytket-cirq-runner/         # Cirq Runner
├── ...                         # (Other Runners)
└── tests/                      # Unit Tests
```

---

## Benchmarking Metrics

The system captures three key metrics for every run:

1.  **Execution Time:** Precise `time.perf_counter()` wrapping the simulation kernel.
2.  **Memory Delta:** Real-time RAM usage (RSS) captured via a dedicated background thread (`MemoryMonitor`).
3.  **Process Peak:** The absolute maximum memory footprint of the container during execution.

## Contributing

1.  **Add a new Algorithm:** Update `rosetta-api/library.py` and register it in `rosetta-api/main.py`.
2.  **Add a new Runner:** Duplicate an existing runner folder, update the `requirements.txt` (pinned\!), and ensure it adheres to the `appuser` Dockerfile standard.