#!/usr/bin/with-contenv bash

echo "=== Setting up PTZ Camera Control ==="

# Install required packages
echo "Installing Python, pip, fcgiwrap, and spawn-fcgi..."
apk add --no-cache python3 py3-pip fcgiwrap spawn-fcgi

# Install Python ONVIF library
echo "Installing Python ONVIF library..."
pip3 install onvif_zeep requests

# Ensure temp directory exists with proper permissions
mkdir -p /config/tmp
chown abc:abc /config/tmp
chmod 755 /config/tmp

# Make Python scripts executable
chmod +x /config/www/cgi-bin/ptz/*.py 2>/dev/null || true

echo "=== PTZ Camera Control Setup Completed ==="