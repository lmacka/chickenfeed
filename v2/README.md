# Chickenfeed v2 - Simplified Architecture

## Overview

This is a complete rewrite of the Chickenfeed chicken cam system, reducing complexity by ~90% while maintaining all core functionality.

### Key Improvements
- **Single Go binary** instead of complex Node.js/Python stack
- **HTMX for interactivity** - no React/Vue, no build process
- **SSE instead of WebSockets** - simpler, auto-reconnecting
- **Direct HTTP calls** instead of complex message passing
- **~1,000 lines of code** vs ~10,000 in original

## Architecture

```
VPS:
├── chook-server (Go + HTMX)
│   ├── Serves web UI
│   ├── Handles all API endpoints
│   ├── SSE for real-time updates
│   └── Direct HTTP to Pi & CGI
├── MediaMTX (unchanged)
├── SWAG/nginx (unchanged)
└── Tailscale (unchanged)

Pi:
└── chicky (Simplified FastAPI)
    ├── /health - Status check
    ├── /api/treat - Dispense treat
    ├── /api/light - Toggle light
    └── /api/sensors - Get readings
```

## Completed Features (Phases 1-5)

### ✅ Phase 1: Core Infrastructure
- Go server with embedded filesystem
- HTMX templates for UI
- Docker containerization
- Static file serving

### ✅ Phase 2: Camera Control
- Integration with existing PTZ CGI script
- 4 preset positions (HEATER, FEEDER, WINDOW, TREATS)
- Rate limiting (1 command per 5 seconds)
- Status feedback messages

### ✅ Phase 3: Pi Communication
- Simplified FastAPI server for Pi
- Direct HTTP endpoints (no WebSockets)
- Mock hardware modules for testing
- Balena-compatible Dockerfile

### ✅ Phase 4: Hardware & Sensors
- Treat dispenser with auto-camera positioning
- Light toggle control
- Live sensor display (temp, humidity, pressure, light)
- 30-second auto-refresh
- Background sensor fetching

### ✅ Phase 5: Real-time Updates
- Server-Sent Events (SSE) implementation
- Live viewer count
- Pi health status indicator
- Real-time sensor updates
- Auto-reconnecting on disconnect

### ✅ Phase 6: Chat System
- SQLite database storage (persistent chat history)
- In-memory message buffer (last 50)
- Load messages from database on restart
- Rate limiting (5 messages per 10 seconds per IP)
- Anonymous username generation (`Chook%d` format)
- SSE broadcasting of messages to all clients
- Full HTMX integration with real-time updates
- Chat error handling and user feedback

## Additional Features Implemented

**Beyond Original Scope:**
- Direct ONVIF camera control (camera_wrapper.go)
- OpenGraph/Twitter meta tags for social sharing
- Google Analytics integration
- Custom favicon and screenshot assets
- Filesystem-based static serving (no embedding)
- Docker volume mounts for live development
- Comprehensive environment variable configuration
- SQLite database for persistent chat storage
- Advanced rate limiting and error handling

## Outstanding Tasks

### 🔲 Phase 7: Polish & Deployment
- [x] Improved CSS styling (responsive, mobile-optimized)
- [x] Mobile-optimized touch targets
- [x] Error handling improvements (rate limiting, offline states)
- [x] Production environment configuration (.env variables)
- [ ] Integration with existing SWAG/nginx (testing needed)
- [ ] Final testing and debugging

## Current File Structure

```
v2/
├── vps/
│   ├── chook-server/
│   │   ├── main.go              # Complete server (1,122 lines)
│   │   ├── camera_wrapper.go    # Direct ONVIF camera control
│   │   ├── go.mod               # Dependencies
│   │   ├── templates/
│   │   │   └── index.html       # Standalone main page
│   │   ├── static/
│   │   │   ├── style.css        # Responsive styling
│   │   │   ├── htmx.min.js      # HTMX library
│   │   │   ├── htmx-sse.js      # SSE extension
│   │   │   ├── hls.min.js       # Video player
│   │   │   ├── favicon.webp     # Custom favicon
│   │   │   └── screenshot-lg.png # Social sharing image
│   │   └── Dockerfile
│   ├── .env                     # Environment configuration
│   ├── docker-compose.yml       # VPS services
│   └── chat-logs/              # Chat database storage
└── chicky/
    ├── main.py                  # FastAPI server (169 lines)
    ├── requirements.txt         # Python deps
    ├── Dockerfile.template      # Balena deployment
    └── src/
        └── hardware/           # Mock hardware modules
            ├── servo_controller.py
            ├── relay_controller.py
            └── sensor_reader.py
```

## Testing Instructions

### Local Testing (without hardware)

1. **Start the Go server:**
```bash
cd ~/chickenfeed/v2/vps/chook-server
go run main.go
```

2. **Start the mock Pi server:**
```bash
cd ~/chickenfeed/v2/chicky
pip install -r requirements.txt
python main.py
```

3. **Access the UI:**
- Open http://localhost:3000
- Camera controls will fail (no CGI script locally)
- Hardware controls will work in mock mode
- Sensors will show mock data

### Docker Testing

```bash
cd ~/chickenfeed/v2/vps
docker-compose up --build
```

## Configuration

### Environment Variables

**VPS (chook-server):**
- `PORT` - Server port (default: 3000)
- `PI_URL` - Tailscale URL of Pi (e.g., http://100.64.0.1:3000)
- `CGI_URL` - Camera CGI script URL (default: http://localhost/ptz/control.py)

**Pi (chicky):**
- `PORT` - Server port (default: 3000)

## Migration from v1

1. Copy existing hardware control code from v1 to v2/chicky/src/hardware/
2. Update docker-compose.yml with correct Tailscale IPs
3. Configure MediaMTX for HLS streaming
4. Update SWAG/nginx to proxy to new chook-server
5. Deploy to Balena (Pi) and VPS

## Benefits Over Original

| Aspect | Original (v1) | New (v2) | Improvement |
|--------|--------------|----------|-------------|
| Backend Languages | Python + Node.js | Go + Python | Simpler |
| Frontend Framework | React-like with build | HTMX (no build) | 90% less complexity |
| Real-time | WebSockets (complex) | SSE (simple) | Auto-reconnecting |
| Code Size | ~10,000 lines | ~1,000 lines | 90% reduction |
| Dependencies | 100s of npm packages | 1 Go dependency | Minimal |
| State Management | Complex sync | Server-side only | No sync issues |
| Deployment | Multiple services | Single binary | Much simpler |

## Known Limitations

1. No historical data storage (sensors)
2. No user authentication (by design) 
3. No profanity filtering in chat
4. Video stream URL hardcoded (by design)

## Next Steps

1. Test integration with existing SWAG/nginx setup
2. Test with actual hardware on Pi
3. Deploy to production
4. Optional: Add profanity filtering to chat