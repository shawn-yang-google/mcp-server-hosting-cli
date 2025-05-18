#!/bin/bash
set -e

# Parameters
REGISTRY_DOMAIN=$1
IMAGE_NAME=$2
DOCKERFILE_ABS_PATH=$3        # Absolute path to the Dockerfile
BUILD_CONTEXT_ABS_PATH=$4     # Absolute path to the build context
DEPLOY_DIR_ARG_FOR_BUILD=$5   # Optional: Build argument value for DEPLOY_DIR_ARG (e.g., "deploy/my-server" or empty)

# Log messages with timestamps
log() {
  echo "[$(date +"%Y-%m-%d %H:%M:%S")] $1"
}

log "Authenticating with Docker..."
if ! gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin "${REGISTRY_DOMAIN}"; then
    log "ERROR: Docker login failed. Please check GCP authentication and permissions for ${REGISTRY_DOMAIN}."
    exit 1
fi

CMD_ARGS=()
if [ -n "$DEPLOY_DIR_ARG_FOR_BUILD" ]; then
  log "Passing --build-arg DEPLOY_DIR_ARG=${DEPLOY_DIR_ARG_FOR_BUILD}"
  CMD_ARGS+=(--build-arg "DEPLOY_DIR_ARG=${DEPLOY_DIR_ARG_FOR_BUILD}")
fi

log "Building Docker image: ${IMAGE_NAME} using Dockerfile ${DOCKERFILE_ABS_PATH} and context ${BUILD_CONTEXT_ABS_PATH}"
# shellcheck disable=SC2068 # Pass CMD_ARGS as separate arguments. Docker build will handle them.
if ! docker build ${CMD_ARGS[@]} -t "${IMAGE_NAME}" -f "${DOCKERFILE_ABS_PATH}" "${BUILD_CONTEXT_ABS_PATH}"; then
    log "ERROR: Docker build failed for image ${IMAGE_NAME}."
    exit 1
fi

log "Proceeding to push Docker image ${IMAGE_NAME} to ${REGISTRY_DOMAIN}..."
if ! docker push "${IMAGE_NAME}"; then
    log "ERROR: Docker push failed for image ${IMAGE_NAME} to ${REGISTRY_DOMAIN}."
    exit 1
fi

log "Docker build and push completed successfully for ${IMAGE_NAME}" 