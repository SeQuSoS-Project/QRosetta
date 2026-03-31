
# Quantum Rosetta: Cloud Operations Runbook

This document outlines the standard operating procedures for managing the Quantum Rosetta microservice swarm on Google Cloud Run.

## 1. First-Time Infrastructure Initialization (Run Once)

Before deploying code to a fresh Google Cloud project, you must configure the underlying networking, security permissions, and storage infrastructure.

### A. Network & IAM Configuration

Because this architecture uses a secure "Air Gap" (where the API routes internal traffic to hidden runners), the automated Cloud Run Service Agent requires explicit permission to use your default Virtual Private Cloud (VPC).

```bash
# 1. Fetch the unique Project Number for the current project
PROJECT_NUMBER=$(gcloud projects describe qrosetta --format='value(projectNumber)')

# 2. Grant the Cloud Run Service Agent permission to use the VPC network
gcloud projects add-iam-policy-binding qrosetta \
    --member="serviceAccount:service-${PROJECT_NUMBER}@serverless-robot-prod.iam.gserviceaccount.com" \
    --role="roles/compute.networkUser" \
    --condition=None

# 3. Verify the subnet exists (If prompted to enable the Compute API, type 'y')
gcloud compute networks subnets list --regions=us-central1

# 4. Enable "Private Google Access" on the subnet
# This allows the API to securely reach the internal runner URLs
gcloud compute networks subnets update default \
    --region=us-central1 \
    --enable-private-ip-google-access \
    --quiet

```

### B. Artifact Registry Setup

Create the secure remote storage repository where your local Docker images will be hosted, and authenticate your local Docker engine to access it.

```bash
# Create the Docker repository
gcloud artifacts repositories create cloud-run-source-deploy --repository-format=docker --location=us-central1

# Authenticate local Docker to push to GCP
gcloud auth configure-docker us-central1-docker.pkg.dev --quiet

```

---

## 2. Deployment Workflows

### Option A: The Full Swarm Deployment

Use this when initializing the project or when you have modified the `Dockerfile` or `requirements.txt` of the quantum runners. It iterates through all 8 runners and the API gateway, applying strict 20-qubit limits and 100s timeouts.

```bash
# Executes the full local-cache build, push, and deploy loop
bash deploy.sh

```

### Option B: The "Fast-Path" API Deploy (Recommended for UI/API updates)

Deploying the full swarm takes ~10 minutes due to Google's infrastructure provisioning. If you only modified frontend HTML/JS or the `rosetta-api` Python code, bypass the runners entirely. This updates the live site in ~20 seconds.

```bash
# 1. Build using the local cache
docker build -t us-central1-docker.pkg.dev/qrosetta/cloud-run-source-deploy/rosetta-api:latest -f ./rosetta-api/Dockerfile .

# 2. Push the updated layers
docker push us-central1-docker.pkg.dev/qrosetta/cloud-run-source-deploy/rosetta-api:latest

# 3. Deploy the new revision instantly
gcloud run deploy rosetta-api \
    --image us-central1-docker.pkg.dev/qrosetta/cloud-run-source-deploy/rosetta-api:latest \
    --region us-central1 \
    --quiet

```

---

## 3. Access Control (Pause / Unpause)

Cloud Run bills on a pay-per-use model. To temporarily take the application offline without destroying the infrastructure, simply lock the public "front door" of the API Gateway. The 8 backend runners are already internal-only.

**Pause the Service (Lock public access):**

```bash
gcloud run services remove-iam-policy-binding rosetta-api \
    --region=us-central1 \
    --member="allUsers" \
    --role="roles/run.invoker" \
    --quiet

```

**Unpause the Service (Restore public access):**

```bash
gcloud run services add-iam-policy-binding rosetta-api \
    --region=us-central1 \
    --member="allUsers" \
    --role="roles/run.invoker" \
    --quiet

```

---

## 4. Monitoring & Teardown

When the project is not in active use, clean up the resources to ensure zero accidental billing.

**List all active URLs and services:**

```bash
gcloud run services list --region=us-central1

```

**Nuke Compute (Delete all Cloud Run services):**

```bash
for service in rosetta-api pytket-qiskit-runner pytket-cirq-runner pytket-qulacs-runner pytket-braket-runner pytket-projectq-runner pytket-quest-runner pennylane-lightning-runner pennylane-default-runner; do
    echo "Deleting $service..."
    gcloud run services delete $service --region=us-central1 --quiet
done

```

*(Note: To delete a specific service, replace the list with a single name, e.g., `gcloud run services delete pytket-qulacs-runner ...`)*

**Nuke Storage (Delete heavy Docker images):**
First get list of storage repositories:

```bash
gcloud artifacts repositories list
```

Then delete the storage repository:

```bash
gcloud artifacts repositories delete <repository-name> --location=us-central1 --quiet

gcloud artifacts repositories delete cloud-run-source-deploy --location=us-central1 --quiet

gcloud artifacts repositories delete gcr.io --location=us --quiet

```

*To restore the environment after a full teardown, simply run `bash deploy.sh` again.*