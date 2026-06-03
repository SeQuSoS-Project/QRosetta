// Frontend logic for api functionality.

let BASE_URL = '';
if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    BASE_URL = window.location.origin;
}

function getAuthHeaders(extraHeaders = {}) {
    const headers = { ...extraHeaders };
    if (getState().authToken) {
        headers['Authorization'] = `Bearer ${getState().authToken}`;
    }
    return headers;
}

async function pollJobStatus(jobId) {
    return new Promise((resolve, reject) => {
        let networkErrorCount = 0;
        const MAX_NETWORK_ERRORS = 4;

        const checkStatus = async () => {
            try {
                const res = await fetch(`${BASE_URL}/jobs/${jobId}`, {
                    headers: getAuthHeaders()
                });
                if (!res.ok) {
                    throw new Error(`Failed to fetch job status: ${res.status}`);
                }
                const data = await res.json();
                networkErrorCount = 0;

                if (data.runner_statuses) {
                    updateRunnerStatuses(data.runner_statuses);
                }

                if (data.status === "completed") {
                    resolve(data.results);
                } else if (data.status === "failed") {

                    if (data.results) {
                        resolve(data.results);
                    } else {
                        reject(new Error(data.error || "Job failed on backend"));
                    }
                } else {

                    const targetName = data.target === "lumi" ? "LUMI (HPC)" : "Kubernetes Cluster";
                    const loaderText = document.getElementById('loader-text');
                    if (loaderText) loaderText.textContent = `Running on ${targetName}...`;
                    setTimeout(checkStatus, 3000);
                }
            } catch (err) {
                networkErrorCount++;
                if (networkErrorCount <= MAX_NETWORK_ERRORS) {
                    console.warn(`[poll] Network error for job ${jobId} (attempt ${networkErrorCount}/${MAX_NETWORK_ERRORS}):`, err.message);
                    setTimeout(checkStatus, 3000);
                } else {
                    reject(err);
                }
            }
        };
        setTimeout(checkStatus, 1500);
    });
}

async function fetchMQTBench(algorithm, qubits) {
    const res = await fetch(`${BASE_URL}/benchmarks/mqt?algorithm=${encodeURIComponent(algorithm)}&qubits=${encodeURIComponent(qubits)}`, {
        headers: getAuthHeaders()
    });
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.error || `Failed to fetch MQT Bench: ${res.status}`);
    }
    return await res.json();
}

async function fetchQASMBench(circuit) {
    const res = await fetch(`${BASE_URL}/benchmarks/qasmbench?circuit=${encodeURIComponent(circuit)}`, {
        headers: getAuthHeaders()
    });
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.error || `Failed to fetch QASMBench: ${res.status}`);
    }
    return await res.json();
}

async function fetchMQTList() {
    const res = await fetch(`${BASE_URL}/benchmarks/mqt/list`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error(`Failed to fetch MQT list: ${res.status}`);
    return await res.json();
}

async function fetchQASMBenchList() {
    const res = await fetch(`${BASE_URL}/benchmarks/qasmbench/list`, { headers: getAuthHeaders() });
    if (!res.ok) throw new Error(`Failed to fetch QASMBench list: ${res.status}`);
    return await res.json();
}