#!/bin/bash
# Simple deployment script for Chickenfeed Pi Python version

# Check if balena CLI is installed
if ! command -v balena &> /dev/null; then
    echo "Error: balena CLI is not installed. Please install it first."
    echo "https://github.com/balena-io/balena-cli/blob/master/INSTALL.md"
    exit 1
fi

# Check if user is logged in
if ! balena whoami &> /dev/null; then
    echo "You are not logged in to balena. Please login first:"
    balena login
fi

# Deploy to balena
echo "Deploying to balena..."
balena push chickenfeed

echo "Deployment complete!" 