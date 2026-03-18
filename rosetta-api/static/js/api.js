// =============================================================================
// api.js — Network Layer
// Responsibility: BASE_URL detection, auth headers, and job polling.
// Depends on: getState().authToken (global in app.js), setLoading (utils.js)
// =============================================================================

let BASE_URL = '';
if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    BASE_URL = 'https://rosetta-api-qrosetta.2.rahtiapp.fi';
}

function getAuthHeaders(extraHeaders = {}) {
    const headers = { ...extraHeaders };
    if (getState().authToken) {
        headers['Authorization'] = `Bearer ${getState().authToken}`;
    }
    return headers;
}

async function pollJobStatus(jobId) {
    let startTime = Date.now();
    return new Promise((resolve, reject) => {
        const checkStatus = async () => {
            try {
                const res = await fetch(`${BASE_URL}/jobs/${jobId}`, {
                    headers: getAuthHeaders()
                });
                if (!res.ok) {
                    throw new Error(`Failed to fetch job status: ${res.status}`);
                }
                const data = await res.json();

                if (data.status === "completed") {
                    resolve(data.results);
                } else if (data.status === "failed") {
                    reject(new Error(data.error || "Job failed on backend"));
                } else {
                    const elapsed = Math.floor((Date.now() - startTime) / 1000);
                    const targetName = data.target === "lumi" ? "LUMI (HPC)" : "Rahti";
                    setLoading(true, `Processing on ${targetName}... (${elapsed}s)`);
                    setTimeout(checkStatus, 3000);
                }
            } catch (err) {
                reject(err);
            }
        };
        setTimeout(checkStatus, 1500); // initial small delay
    });
}
