# Quantum Rosetta

**Quantum Rosetta** is a production-grade microservices architecture designed to benchmark, validate, and analyze quantum circuit simulators. It acts as a translation layer and orchestration engine ("The Brain") that dispatches quantum tasks to isolated simulator containers ("The Hands") to measure fidelity, execution time, and memory efficiency.
QRosetta has been developed by the [Quantum Programming and Algorithms (QPA) Research Group](https://users.jyu.fi/~mhaghpyz/#qpa) at the [University of Jyvaskyla](https://www.jyu.fi/en) in Finland.

# How to Cite?

QRosetta is free-to-use and to modify. However, you must add references [1] in case of any publication/production/execution/etc.

[1] Sh. Sarker, Haghparast, M., Mikkonen, T. (2026). Quantum Rosetta: A Microservice Platform for Quantum Simulator Benchmarking and Verification. SoftwareX, Under Review.


## System Architecture

The system follows a strict **Microservices Architecture** orchestrated by Docker Compose.

### 1. The Shield (Nginx)
* **Role:** Reverse Proxy & Static File Server.
* **Config:** Listens on Port 80. Serves the HTML/JS frontend directly. Proxies API requests to the internal Python backend.
* **Safety:** Prevents direct external access to the application server and handles startup coordination via healthchecks.

### 2. The Brain (rosetta-api)
* **Role:** Orchestration, Content Generation, Comparative Analysis.
* **Runtime:** **Gunicorn** (Process Manager) managing **Uvicorn** (ASGI Workers). Configured with **4 workers** for high concurrency.
* **Key Functions:**
    * **Dynamic Generation:** Creates valid QASM 2.0 for algorithms like GHZ, QFT, Grover, and VQE.
    * **Internal Dispatch:** Uses direct internal async function calls to eliminate loopback network overhead.
    * **Math Engine:** Calculates Fidelity Matrices and Jensen-Shannon Divergence in a non-blocking thread pool.

### 3. The Hands (Simulators)
Eight isolated runner services, each wrapping a specific quantum simulation framework.
* **Runtime:** **Gunicorn** configured with **1 worker** to ensure strict CPU affinity for accurate benchmarking.
* **Standardization:** All runners implement a strict contract (`POST /run`, `POST /run_measured`).
* **Supported Frameworks:**
    * **Qiskit Aer**
    * **Cirq**
    * **Qulacs**
    * **AWS Braket**
    * **ProjectQ**
    * **QuEST**
    * **PennyLane Lightning**
    * **PennyLane Default**

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

2.  **Configure Environment**
    Create a local `.env` file from the example template and fill in your credentials (required for both local deployment and cloud deployment scripts):
    ```bash
    cp .env.example .env
    ```
    *Note: Ensure you edit the `.env` file with your actual database and cloud credentials.*

3.  **Build and Run (Local)**
    The recommended way to deploy the stack locally with graceful failure handling is using the provided boot script:
    ```bash
    ./scripts/safe_boot.sh
    ```
    *Alternatively, you can manually use Docker Compose:*
    ```bash
    docker compose up --build
    ```
    *Note: The first build may take time as it compiles dependencies for 16 separate containers.*

4.  **Deploy to Cloud (GCP)**
    To deploy the backend API and Runners to Google Cloud Run:
    ```bash
    ./scripts/deploy.sh
    ```
    To deploy the static frontend:
    ```bash
    ./scripts/deploy_frontend.sh
    ```

5.  **Access the Interface**
    * **Web UI:** [http://localhost](http://localhost) (Served via Nginx on Port 80)
    * **API Docs:** [http://localhost/docs](http://localhost/docs)


## Security & Reliability Features

This project has undergone a rigorous **Hardening Sprint** to ensure stability and security.

* **Process Supervision:** All Python services run behind **Gunicorn**, ensuring automatic worker restarts in case of segmentation faults or crashes.
* **Startup Coordination:** Nginx waits for the API to pass a healthcheck before accepting traffic, preventing "502 Bad Gateway" errors on boot.
* **Observability:** Implemented **Structured Logging** across all services. Logs are standardized, timestamped, and categorized (INFO/ERROR) in stdout.
* **Non-Root Execution:** All containers run as an unprivileged user (`appuser`) to prevent container breakout attacks.
* **Resource Limits:** Every service is capped at **0.5 CPUs** and **512 MiB RAM** (Docker Compose) to prevent "Logic Bomb" circuits from crashing the host. On Kubernetes (Rahti), runner Jobs are allocated up to **1 GiB** (256 MiB request, 1 GiB limit).
* **Pinned Dependencies:** All `requirements.txt` files use strict version pinning (e.g., `pennylane==0.39.0`, `autoray==0.6.12`) to prevent dependency drift.
* **Event Loop Optimization:** Heavy mathematical operations are offloaded to thread executors to keep the API responsive.

---

## Verification (Smoke Test)

To verify the system is fully operational (Nginx + API + Runners), use the included integration script. This requires the system to be running (`docker compose up`).

1. **Install Test Dependencies:**
   ```bash
   pip install httpx


2.  **Run the Test:**
    ```bash
    python3 tests/integration_test_live.py
    ```
    *Success output:* `Integration Test Passed!`

-----

## Benchmarking Metrics

The system captures three key metrics for every run:

1.  **Execution Time:** Precise `time.perf_counter()` wrapping the simulation kernel.
      * *Note:* For measured runs, this includes both the simulation time **and** the sampling process time to ensure fair comparison between native and statevector simulators.
2.  **Memory Delta:** Real-time RAM usage (RSS) captured via a dedicated background thread (`MemoryMonitor`).
3.  **Process Peak:** The absolute maximum memory footprint of the container during execution.

-----

## Project Structure

```text
.
├── docker-compose.yml          # Orchestration, Healthchecks & Resource Limits
├── nginx/                      # Reverse Proxy Configuration
├── rosetta-api/                # The Brain (FastAPI + Gunicorn)
│   ├── main.py                 # Entrypoint & Logic
│   ├── library.py              # Circuit Generators
│   ├── comparator.py           # Math Engine
│   └── static/                 # Web Frontend
├── shared/                     # Shared Logic
│   └── qrosetta_commons/       # Models, MemoryMonitor, & Logger Factory
├── pytket-qiskit-runner/       # Qiskit Runner
├── pytket-cirq-runner/         # Cirq Runner
├── ...                         # (Other Runners)
└── tests/                      # Unit & Integration Tests
```


# Contributors

- Shaswato Sarker - *University of Jyvaskyla*
- Majid Haghparast - *University of Jyvaskyla*
- Tommi Mikkonen - *University of Jyvaskyla*

# Contact

Majid Haghparast <<majid.m.haghparast@jyu.fi>>


# Acknowledgement

This work has been supported by the Business Finland through project SeQuSoS (Grants No. 112/31/2024), and Research Council of Finland through project Profi 8 - qSIME (Grants No. 365343).


## Contributing

1.  **Add a new Algorithm:** Update `rosetta-api/library.py` and register it in `rosetta-api/main.py`.
2.  **Add a new Runner:** Duplicate an existing runner folder, update the `requirements.txt` (pinned\!), and ensure it uses the `get_logger` helper.


