
## Code for GCLOUD RUN gcloud commands
# Step 1: Recreate the Artifact Registry

This creates the secure remote bin where the local Docker images will be pushed.

gcloud artifacts repositories create cloud-run-source-deploy --repository-format=docker --location=us-central1

# Step 2: Authenticate Local Docker

This securely links the local Ubuntu Docker engine to the newly created Google Cloud repository.
gcloud auth configure-docker us-central1-docker.pkg.dev --quiet

# Step 3: Execute the Deployment Swarm

The deploy.sh script contains all nine gcloud run deploy commands configured with the 20-qubit limits, 3-instance maximums, and 100-second timeouts. Running this will automatically loop through the local builds, registry pushes, and cloud deployments.
bash deploy.sh

Once the script finishes, it will print out the final public URL for your rosetta-api gateway. Click that link to access the live web interface.

## Code for GCLOUD TO DELETE
# 0 Service Lists
gcloud run services list --region=us-central1

# 1. Delete all Cloud Run services to stop any potential compute
gcloud run services delete rosetta-api pytket-qiskit-runner pytket-cirq-runner pytket-qulacs-runner pytket-braket-runner pytket-projectq-runner pytket-quest-runner pennylane-lightning-runner pennylane-default-runner --region=us-central1 --quiet

OR JUST ONE

gcloud run services delete pytket-qulacs-runner --region=us-central1 --quiet

# 2. Delete the Artifact Registry repository holding the heavy images to stop storage billing
gcloud artifacts repositories delete cloud-run-source-deploy --location=us-central1 --quiet

# 3. Turn it on again
sh deploy.sh

## PAUSE THE SERVICE
gcloud run services remove-iam-policy-binding rosetta-api \
    --region=us-central1 \
    --member="allUsers" \
    --role="roles/run.invoker" \
    --quiet

# UNPAUSE THE SERVICE
gcloud run services add-iam-policy-binding rosetta-api \
    --region=us-central1 \
    --member="allUsers" \
    --role="roles/run.invoker" \
    --quiet

## ONE TIME IAM FIX WHEN FIRST SETTING UP
# 1. Fetch the unique Project Number
PROJECT_NUMBER=$(gcloud projects describe qrosetta --format='value(projectNumber)')

# 2. Grant the Cloud Run Service Agent permission to use the VPC network
gcloud projects add-iam-policy-binding qrosetta \
    --member="serviceAccount:service-${PROJECT_NUMBER}@serverless-robot-prod.iam.gserviceaccount.com" \
    --role="roles/compute.networkUser" \
    --condition=None

# 3. Check it with
gcloud compute networks subnets list --regions=us-central1
type y

# 4. Enable Private Google Access

Run this single command in your terminal. It flips the switch in your default virtual network so it knows how to correctly route the API's internal traffic to your runners:
Bash

gcloud compute networks subnets update default \
    --region=us-central1 \
    --enable-private-ip-google-access \
    --quiet