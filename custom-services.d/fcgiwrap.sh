#!/usr/bin/with-contenv bash

echo "Starting fcgiwrap service..."

# Create a directory for the PID file with proper permissions
mkdir -p /config/run
chown abc:abc /config/run

# Check if fcgiwrap is already running
if [ -S /config/run/fcgiwrap.socket ]; then
    echo "fcgiwrap socket already exists, stopping existing process..."
    if [ -f /config/run/fcgiwrap.pid ]; then
        kill $(cat /config/run/fcgiwrap.pid) 2>/dev/null || true
        rm -f /config/run/fcgiwrap.pid
    fi
    rm -f /config/run/fcgiwrap.socket
fi

# Start fcgiwrap and keep it running
echo "Starting fcgiwrap..."
s6-setuidgid abc spawn-fcgi -u abc -g abc -s /config/run/fcgiwrap.socket -P /config/run/fcgiwrap.pid -- /usr/bin/fcgiwrap

# Sleep indefinitely to keep the service running
echo "fcgiwrap started successfully, going to sleep..."
exec sleep infinity