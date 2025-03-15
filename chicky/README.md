# Chickenfeed Pi (Python Version)

This is the Python version of the Raspberry Pi component for the Chickenfeed project, rewritten from the original NodeJS implementation.

## Overview

The Chickenfeed Pi component is responsible for:

1. Controlling the chicken coop light via a relay
2. Dispensing treats via servo motors
3. Communicating with a remote server for control and configuration

## Requirements

### Python Dependencies

- FastAPI
- Uvicorn
- Python-SocketIO
- APScheduler
- Pydantic
- AutomationHAT
- Python-dotenv

### System Dependencies

These should be installed via apt:

- python3-gpiozero
- python3-rpi.gpio
- python3-libgpiod
- python3-smbus

## Installation

1. Install system dependencies:

```bash
sudo apt-get update
sudo apt-get install -y python3-gpiozero python3-rpi.gpio python3-libgpiod python3-smbus
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

Configuration is loaded from environment variables:

- `PORT`: The port for the local server (default: 3000)
- `REMOTE_SERVER`: URL of the remote WebSocket server
- `AUTH_TOKEN`: Authentication token for the remote server
- `DEBUG`: Enable debug logging (default: false)

Additional configuration is received from the remote server:

- `servo1_pin`: GPIO pin for servo 1
- `servo2_pin`: GPIO pin for servo 2
- `allowed_start_hour`: Hour when operations are allowed to start (24-hour format)
- `allowed_end_hour`: Hour when operations must end (24-hour format)
- `timezone_offset`: Offset from UTC for the local timezone

## Running

```bash
python main.py
```

## API Endpoints

- `GET /health`: Health check endpoint
- `GET /status`: Connection status endpoint
- `GET /test-connection`: Test WebSocket connection
- `GET /dns-test`: DNS lookup test
- `GET /url-test`: WebSocket URL test
- `POST /light`: Manual light control (for local testing)

## License

ISC 