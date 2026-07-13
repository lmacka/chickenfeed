# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chickenfeed is an interactive chicken coop livestream system with two main components:
- **Raspberry Pi controller** (`/chicky/`) - Hardware interface running on-site
- **Cloud server** (`/vps/`) - Public-facing web infrastructure

## Common Development Commands

### VPS (Cloud Server) Deployment
```bash
cd vps/
./deploy.sh              # Deploy with encrypted secrets via SOPS
docker compose up -d      # Standard Docker Compose deployment
docker compose logs -f   # View live logs
docker compose down      # Stop all services
```

### Raspberry Pi Development
```bash
cd chicky/
python main.py           # Run development server locally
docker compose up -d     # Deploy to Raspberry Pi
```

### Python Development
```bash
# Install dependencies
pip install -r chicky/requirements.txt              # Pi hardware dependencies
pip install -r vps/chicky-control/requirements.txt  # VPS server dependencies

# Run servers locally
cd chicky && python main.py                         # Pi controller (port 3000)
cd vps/chicky-control && python run.py             # Control server (port 3000)
```

## Architecture Overview

### Distributed System Design
- **Home Network**: Raspberry Pi + hardware controllers + IP camera
- **Cloud Infrastructure**: Docker containers (SWAG, MediaMTX, Control Server, Tailscale)
- **Secure Tunnel**: Tailscale VPN connects home and cloud without port forwarding

### Key Components
- **Hardware Controllers** (`chicky/src/hardware/`): GPIO interfaces for servos, relays, sensors
- **Control Server** (`vps/chicky-control/`): FastAPI + Socket.IO for real-time web control
- **Video Pipeline**: RTSP → Tailscale tunnel → MediaMTX → HLS for web browsers
- **Security Layer**: HTTPS termination, auth tokens, rate limiting, profanity filtering

### Configuration Management
- **Environment Variables**: SOPS-encrypted `.env` files for secrets
- **Hardware Config**: `chicky/config/default.py` for Pi-specific settings
- **Streaming Config**: `vps/mediamtx.yml` for video pipeline
- **Web Server**: `vps/config/nginx/` for SWAG/Nginx configuration

### Communication Flow
1. Web UI sends WebSocket commands to control server
2. Control server validates permissions and forwards via Tailscale
3. Raspberry Pi receives commands and controls hardware
4. Sensor data flows back through same encrypted tunnel
5. All video streams through single RTSP → HLS conversion

## Technology Stack

### Backend
- **Python FastAPI**: REST APIs and WebSocket servers
- **Socket.IO**: Real-time bidirectional communication
- **Hardware Libraries**: automationhat, rpi-lgpio, BME280, BH1750

### Infrastructure  
- **Docker**: Containerized deployment with health checks
- **SWAG**: Nginx + Let's Encrypt SSL automation
- **MediaMTX**: RTSP to HLS video streaming
- **Tailscale**: Zero-trust mesh VPN networking

### Frontend
- **Vanilla Web**: HTML5, CSS3, JavaScript (no build system)
- **Video.js**: HLS video playback
- **Socket.IO Client**: Real-time UI updates

## Development Notes

### Hardware Controllers
Hardware abstraction uses context managers for safe resource cleanup. All GPIO controllers inherit from base classes in `chicky/src/hardware/`.

### Security Architecture
- No direct home network exposure via Tailscale mesh networking
- Authentication tokens for inter-service communication
- Rate limiting and cooldown periods on all hardware controls
- HTTPS everywhere with automatic certificate renewal

### Deployment Strategy
The `vps/deploy.sh` script handles SOPS decryption, Docker builds, and service orchestration. Secrets are encrypted at rest and only decrypted during deployment.

### Sensor Integration
Environmental monitoring via I2C sensors (BME280 for temperature/humidity/pressure, BH1750 for light levels) with data flowing to web clients via WebSocket.