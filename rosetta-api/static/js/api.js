// =============================================================================
// api.js — Network Layer
// Responsibility: BASE_URL detection, auth headers, and job polling.
// Depends on: getState().authToken (global in app.js), setLoading (utils.js)
// =============================================================================

let BASE_URL = '';
if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    BASE_URL = 'https://rosetta-api-route-qrosetta.2.rahtiapp.fi';
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
        const MAX_NETWORK_ERRORS = 4; // tolerate ~12 s of transient connectivity issues

        const checkStatus = async () => {
            try {
                const res = await fetch(`${BASE_URL}/jobs/${jobId}`, {
                    headers: getAuthHeaders()
                });
                if (!res.ok) {
                    throw new Error(`Failed to fetch job status: ${res.status}`);
                }
                const data = await res.json();
                networkErrorCount = 0; // reset on any successful response

                if (data.runner_statuses) {
                    updateRunnerStatuses(data.runner_statuses);
                }

                if (data.status === "completed") {
                    resolve(data.results);
                } else if (data.status === "failed") {
                    // Partial results may still be present even on a failed job
                    // (e.g. analysis threw but runners completed).
                    if (data.results) {
                        resolve(data.results);
                    } else {
                        reject(new Error(data.error || "Job failed on backend"));
                    }
                } else {
                    // Only update the loader message text — don't call setLoading()
                    // to avoid any interaction with the elapsed timer.
                    const targetName = data.target === "lumi" ? "LUMI (HPC)" : "Rahti";
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
        setTimeout(checkStatus, 1500); // initial small delay
    });
}
