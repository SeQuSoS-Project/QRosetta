"""Shared helpers of the live-stack tests: the stack's address, the runners a test may use,
requests that wait out a rate limit, and job polling."""

import os
import time
import urllib.parse

import httpx

BASE_URL = os.environ.get("QROSETTA_BASE_URL", "http://localhost:8080").rstrip("/")
_parts = urllib.parse.urlsplit(BASE_URL)
ORIGIN = f"{_parts.scheme}://{_parts.netloc}"

RATE_LIMIT_ATTEMPTS = 4
RETRY_AFTER_CAP_SEC = 65


def selected_runners(default: list) -> list:
    """QROSETTA_TEST_RUNNERS (comma list, a subset of ``default``) or ``default``."""
    raw = os.environ.get("QROSETTA_TEST_RUNNERS", "").strip()
    if not raw:
        return list(default)
    chosen = [name.strip() for name in raw.split(",") if name.strip()]
    unknown = [name for name in chosen if name not in default]
    if unknown:
        raise ValueError(f"QROSETTA_TEST_RUNNERS names runners this test does not cover: {unknown}")
    return chosen


def send(client: httpx.Client, method: str, path: str, **kwargs) -> httpx.Response:
    """One request; a 429 is retried after its Retry-After, at most RATE_LIMIT_ATTEMPTS times."""
    for _ in range(RATE_LIMIT_ATTEMPTS):
        resp = client.request(method, f"{BASE_URL}{path}", **kwargs)
        if resp.status_code != 429:
            return resp
        wait = min(float(resp.headers.get("Retry-After") or 10), RETRY_AFTER_CAP_SEC)
        print(f"  {method} {path}: 429, retrying in {wait:.0f} s")
        time.sleep(wait)
    return resp


def poll_job(client: httpx.Client, job_id: str, timeout: float = 300) -> dict:
    """The job envelope once the job is completed or failed."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = client.get(f"{BASE_URL}/jobs/{job_id}", timeout=10)
        assert resp.status_code == 200, f"Job poll HTTP {resp.status_code}: {resp.text}"
        data = resp.json()
        if data.get("status") in ("completed", "failed"):
            return data
        time.sleep(1)
    raise TimeoutError(f"Job {job_id} did not finish within {timeout:.0f} s")
