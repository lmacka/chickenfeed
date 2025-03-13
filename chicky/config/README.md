# Configuration

This directory contains the configuration for the Chickenfeed Pi component.

## Essential Environment Variables

The Chickenfeed Pi component requires only these environment variables to be set locally:

- `PORT`: The port to run the local server on (default: 3000)
- `REMOTE_SERVER`: The WebSocket URL of the remote server (e.g., wss://onlychicks.tv)
- `AUTH_TOKEN`: The authentication token for the remote server

## Server-Provided Configuration

All other configuration is provided by the server via WebSocket:

### Hardware Configuration
- `servo1_pin`: The GPIO pin for servo 1
- `servo2_pin`: The GPIO pin for servo 2

### Operation Settings
- `debug`: Enable debug logging
- `allowed_start_hour`: The hour when operations are allowed to start (e.g., 5, meaning 5am)
- `allowed_end_hour`: The hour when operations are no longer allowed (e.g., 22, meaning 10pm)
- `timezone_offset`: The timezone offset in hours (e.g., 10, meaning AEST+10)

## Configuration Flow

1. The Chicky component connects to the server using the `REMOTE_SERVER` and `AUTH_TOKEN` variables
2. After connecting, it requests configuration from the server
3. The server sends the configuration, which is then applied to the Chicky component
4. If the configuration changes on the server, it will be automatically updated on the Chicky component 