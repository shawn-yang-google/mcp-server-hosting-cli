#!/bin/bash
set -e

# Parameters
REGISTRY_DOMAIN=$1
IMAGE=$2
DEPLOY_DIR=$3
# LOCAL_TEST_PORT=${4:-10000} # Default to 10000 if not provided for local testing

# Log messages with timestamps
log() {
  echo "[$(date +"%Y-%m-%d %H:%M:%S")] $1"
}

# Determine the absolute path to the project root
# Script is in mcp_host/backend/docker.sh, so project root is two levels up.
PROJECT_ROOT=$(cd "$(dirname "$0")/../.." && pwd)

log "Authenticating with Docker..."
gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin ${REGISTRY_DOMAIN}

log "Building Docker image: ${IMAGE} using Dockerfile ${PROJECT_ROOT}/${DEPLOY_DIR}/Dockerfile and context ${PROJECT_ROOT}"
# Use absolute paths for Dockerfile and context
docker build --build-arg DEPLOY_DIR_ARG="${DEPLOY_DIR}" -t "${IMAGE}" -f "${PROJECT_ROOT}/${DEPLOY_DIR}/Dockerfile" "${PROJECT_ROOT}"

# log "Attempting to run the container locally for testing on port ${LOCAL_TEST_PORT}..."
# log "The image to be tested is: ${IMAGE}"
# log "If the container starts successfully, you can test it at http://localhost:${LOCAL_TEST_PORT}"
# log "Press Ctrl+C in this terminal to stop the local container and proceed with pushing to registry, or close this terminal to abort."

# # Run the container locally, mapping the port and setting the PORT env variable
# # It runs in the foreground (-it) and will be removed on exit (--rm)
# docker run -it --rm -p ${LOCAL_TEST_PORT}:${LOCAL_TEST_PORT} -e PORT=${LOCAL_TEST_PORT} ${IMAGE}

log "Local container test finished (or was stopped)."
log "Proceeding to push Docker image to ${REGISTRY_DOMAIN}..."
docker push ${IMAGE}

log "Docker build and push completed successfully" 