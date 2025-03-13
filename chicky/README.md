# Chickenfeed Pi Component

This is the Raspberry Pi component of the Chickenfeed project. It controls servos and lights based on commands received from the web UI.

## Project Structure

```
/chicky
  /src                  # Source code
    /controllers        # Command handlers
    /services           # Core services
    /hardware           # Hardware interface
    /routes             # API routes
    /utils              # Utility functions
    app.js              # Express application
    server.js           # Main server
  /config               # Configuration
  /tests                # Tests (future)
  package.json          # Dependencies
  Dockerfile.template   # Balena deployment
  docker-compose.yml    # Local development
```

## Configuration

The Chickenfeed Pi component requires only these environment variables to be set locally:

- `PORT`: The port to run the local server on (default: 3000)
- `REMOTE_SERVER`: The WebSocket URL of the remote server
- `AUTH_TOKEN`: The authentication token for the remote server

All other configuration is provided by the server via WebSocket. See [config/README.md](config/README.md) for details.

## Development

```bash
# Install dependencies
npm install

# Run in development mode
npm run dev

# Run in production mode
npm start
```

## Deployment

```bash
# Deploy to Balena
balena push chickenfeed
```