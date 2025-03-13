#!/bin/bash
set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Print status message
log() { echo -e "${GREEN}==>${NC} $1"; }

# Main script
log "Checking requirements"

# Check balena login
if ! balena whoami &>/dev/null; then
    log "Logging in to balena"
    balena login
fi

# Deploy
log "Pushing to chickenfeed"
balena push chickenfeed

log "Deployment completed successfully"

