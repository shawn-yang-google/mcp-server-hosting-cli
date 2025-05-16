#!/bin/bash
set -e

# Parameters - These would typically be passed as arguments or set as environment variables
SERVICE_NAME=$1
IMAGE_URI=$2
PROJECT_ID=$3
REGION=$4
CONTAINER_PORT=${5:-10000} # Default to 10000 if not provided
CPU=${6:-1}                # Default to 1 CPU if not provided
MEMORY=${7:-512Mi}         # Default to 512Mi if not provided

# Log messages with timestamps
log() {
  echo "[$(date +"%Y-%m-%d %H:%M:%S")] $1"
}

# Exit immediately if a command exits with a non-zero status.
#trap 'log "Script failed at line $LINENO with exit code $?. Command: $BASH_COMMAND"; exit 1' ERR

log "Deploying service '${SERVICE_NAME}' to Cloud Run..."
log "Image URI: ${IMAGE_URI}"
log "Project ID: ${PROJECT_ID}"
log "Region: ${REGION}"
log "Container Port: ${CONTAINER_PORT}"
log "CPU: ${CPU}"
log "Memory: ${MEMORY}"

# The --platform managed flag specifies Cloud Run (fully managed).
# The --allow-unauthenticated flag makes the service publicly accessible. Adjust as needed.
# Using 'beta' and adding startup probes to address potential IAM and container startup issues.
gcloud beta run deploy "${SERVICE_NAME}" \
  --image "${IMAGE_URI}" \
  --port "${CONTAINER_PORT}" \
  --cpu "${CPU}" \
  --memory "${MEMORY}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --platform managed \
  --allow-unauthenticated \
  --startup-probe=periodSeconds=10,failureThreshold=6,httpGet.port="${CONTAINER_PORT}" \
  --quiet

log "Service '${SERVICE_NAME}' deployment/update initiated successfully."

# Optional: Add IAM policy binding if needed, for example, to allow public access.
# This step might require specific permissions for the service account running the script.
# log "Setting IAM policy for '${SERVICE_NAME}' to allow unauthenticated invocations..."
# gcloud beta run services add-iam-policy-binding "${SERVICE_NAME}" \
#   --member="allUsers" \
#   --role="roles/run.invoker" \
#   --region "${REGION}" \
#   --project "${PROJECT_ID}" \
#   --quiet && log "IAM policy updated for '${SERVICE_NAME}'." || \
#   log "Warning: Failed to set IAM policy for '${SERVICE_NAME}'. Manual configuration might be needed."

log "Deployment script for service '${SERVICE_NAME}' finished."

# To get the service URL after deployment (optional, as gcloud deploy also shows it):
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --platform managed --project "${PROJECT_ID}" --region "${REGION}" --format="value(status.url)")
if [ -n "$SERVICE_URL" ]; then
  log "Service URL: ${SERVICE_URL}"
  log "Service is running on container port: ${CONTAINER_PORT}"
else
  log "Could not retrieve service URL. The service might still be deploying or an error occurred."
fi 