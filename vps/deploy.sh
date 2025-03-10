#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Config
ENV_FILE=".env"
ENV_ENCRYPTED=false

# Print status message
log() { echo -e "${GREEN}==>${NC} $1"; }

# Check for required commands
for cmd in sops docker; do
    if ! command -v $cmd &> /dev/null; then
        echo -e "${RED}Error: $cmd is not installed${NC}"
        exit 1
    fi
done

# Cleanup function - only runs once
cleanup() {
    # Re-encrypt .env if we decrypted it
    if [ "$ENV_ENCRYPTED" = true ] && [ -f "$ENV_FILE" ]; then
        log "Re-encrypting .env file"
        sops --encrypt --in-place "$ENV_FILE" 2>/dev/null || true
    fi
}

# Set trap
trap cleanup EXIT

# Main script
log "Checking requirements"

# Check if .env exists
[ ! -f "$ENV_FILE" ] && { echo -e "${RED}Error: $ENV_FILE not found${NC}"; exit 1; }

# Check and decrypt .env if needed
if sops filestatus "$ENV_FILE" 2>/dev/null | grep -q '"encrypted":true'; then
    log "Decrypting .env file"
    sops --decrypt --in-place "$ENV_FILE"
    ENV_ENCRYPTED=true
fi

# Deploy with Docker Compose
log "Deploying with Docker Compose"
docker compose up -d --build

log "Deployment completed successfully"

