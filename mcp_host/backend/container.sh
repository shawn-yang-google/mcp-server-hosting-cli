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
STARTUP_PROBE_HTTP_PATH=${8} # New optional argument for startup probe HTTP GET path
ENV_VARS=${9}                # New optional argument for environment variables (e.g., "KEY1=VALUE1,KEY2=VALUE2")

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
if [ -n "$STARTUP_PROBE_HTTP_PATH" ]; then
  log "Startup Probe HTTP Path: ${STARTUP_PROBE_HTTP_PATH}"
else
  log "Startup Probe HTTP Path: Not specified (will use default '/')"
fi
if [ -n "$ENV_VARS" ]; then
  log "Environment Variables: ${ENV_VARS}"
else
  log "Environment Variables: None specified"
fi

# Construct startup-probe argument
STARTUP_PROBE_CONFIG="periodSeconds=10,failureThreshold=6,httpGet.port=${CONTAINER_PORT}"
if [ -n "$STARTUP_PROBE_HTTP_PATH" ]; then
  STARTUP_PROBE_CONFIG+=",httpGet.path=${STARTUP_PROBE_HTTP_PATH}"
fi

# Base gcloud deploy command
GCLOUD_COMMAND=(gcloud beta run deploy "${SERVICE_NAME}" \
  --image "${IMAGE_URI}" \
  --port "${CONTAINER_PORT}" \
  --cpu "${CPU}" \
  --memory "${MEMORY}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --platform "managed" \
  --allow-unauthenticated \
  --startup-probe="${STARTUP_PROBE_CONFIG}" \
  --quiet)

# Add environment variables if provided
if [ -n "$ENV_VARS" ]; then
  GCLOUD_COMMAND+=(--set-env-vars "${ENV_VARS}")
fi

# Execute the command
"${GCLOUD_COMMAND[@]}"

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