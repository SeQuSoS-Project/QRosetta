# Quantum Rosetta: Timeout Architecture & Guidelines

Due to the heavy computational nature of quantum simulations (especially statevector math on 20+ qubits), managing timeouts across a microservice architecture is critical. If timeouts are misconfigured, infrastructure layers will violently sever connections before the Python application can gracefully report an error, resulting in unhelpful `504 Gateway Time-out` or `502 Bad Gateway` errors instead of structured JSON.

## The "Russian Doll" Principle

Timeouts in Quantum Rosetta must be structured like nested dolls. The outer infrastructure layers must always wait longer than the inner application layers. This ensures that the Python code makes the decision to give up (returning a clean `{"error": "TIMEOUT..."}`), rather than the web server or cloud router killing the process mid-calculation.

## Current Timeout Hierarchy

The system is currently standardized around a 300-second (5 minute) maximum user calculation time, with a 30-second infrastructure buffer (330s total).

| Layer | Component | Current Timeout | Where it is defined |
|-------|-----------|-----------------|---------------------|
| 1 | UI / Client Browser | Fetch API `300s` (Max) | `app.js` (UI Slider input) |
| 2 | App Logic | API Dispatcher (`httpx`) | Dynamic (Max `300s`) | `rosetta-api/services/dispatcher.py` |
| 3 | API Runtime | API Gunicorn Worker | `330s` | `rosetta-api/Dockerfile` |
| 4 | Runner Runtime | Runner Gunicorn Worker | `330s` | `[runner-dir]/Dockerfile` |
| 5 | Cloud Gateway | OpenShift Router | `330s` | `oc annotate route rosetta-api ...` |
| 6 | Local Gateway | Nginx Reverse Proxy | `330s` | `nginx/nginx.conf` |
| 7 | Cloud Run | GCP Frontend Container | `300s+` | `deploy_frontend.sh` |

## How to Safely Increase the Maximum Timeout

If you secure a massive CPU quota on the supercomputer and want to allow simulations to run for 10 minutes (600 seconds), you must update the chain from the outside in:

### 1. Update the Cloud Router (330s):
```bash
oc annotate route rosetta-api --overwrite haproxy.router.openshift.io/timeout=330s -n qrosetta
```

### 2. Update the Dockerfiles (330s):

Change `--timeout 330` to `--timeout 330` in the `rosetta-api` Dockerfile AND all 8 runner Dockerfiles. Rebuild and push the images.

### 3. Update Local Nginx (330s):

In `nginx/nginx.conf`, change `proxy_read_timeout`, `proxy_connect_timeout`, and `proxy_send_timeout` to `330s`.

### 4. Update the UI (300s):

In `app.js` (or `index.html`), change the HTML `<input type="number" id="timeout-input" max="300">` max value to `300`.

## Troubleshooting Timeout Errors

Use this guide to diagnose where a connection is dying based on the error output:

### Error: 504 Gateway Time-out (in browser network tab)

**Cause:** The OpenShift Router or Nginx killed the connection.

**Fix:** Ensure the Router/Nginx timeout is strictly greater than the Gunicorn and httpx timeouts.

### Error: CRITICAL CRASH: The runner container terminated unexpectedly...

**Cause:** The Runner's Gunicorn worker hit its timeout limit and committed suicide (SIGABRT), OR it ran out of memory.

**Fix:** Ensure the Runner's Dockerfile timeout is greater than the API's httpx timeout.

### Error: TIMEOUT (120s): The runner took too long. (Clean JSON response)

**Cause:** The system is perfectly healthy! The circuit simply took longer than the user-specified limit, and the API's httpx client gracefully cancelled the request and reported the failure.