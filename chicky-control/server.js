import express from 'express';
import fetch from 'node-fetch';
import { WebSocketServer } from 'ws';
import http from 'http';

const app = express();
const port = 3000;
const wsPort = 3001;

// Create an HTTP server for the Express app
const server = http.createServer(app);

app.use(express.static('public')); // Serve static files from the 'public' directory

// Create a WebSocket server on a different port
const wss = new WebSocketServer({ port: wsPort });

let clients = 0;
let lightState = false; // Track the state of the light
let lastCommandTime = 0; // Track the last time a command was sent

wss.on('connection', (ws) => {
  clients++;
  console.log(`New client connected. Total clients: ${clients}`);
  wss.clients.forEach(client => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(JSON.stringify({ clients }));
    }
  });

  ws.on('message', (message) => {
    const data = JSON.parse(message);

    // Handle identification message
    if (data.type === 'identify' && data.name) {
      ws.name = data.name;
      console.log(`Client identified as ${ws.name}`);
    }

    // Handle toggle-light command
    if (data.command === 'toggle-light') {
      console.log('Toggle light command received');

      const currentTime = Date.now();
      if (currentTime - lastCommandTime >= 2000) { // Ensure at least 2 seconds between commands
        lastCommandTime = currentTime;

        // Toggle the light state
        lightState = !lightState;

        // Determine the light state as "on" or "off"
        const lightStateStr = lightState ? 'on' : 'off';

        // Find the client named "chicky"
        wss.clients.forEach(client => {
          if (client.readyState === WebSocket.OPEN && client.name === 'chicky') {
            client.send(JSON.stringify({ command: 'toggle-light', state: lightStateStr }));
          }
        });
      } else {
        console.log('Command ignored to prevent spamming');
      }
    }
  });

  ws.on('close', () => {
    clients--;
    console.log(`Client disconnected. Total clients: ${clients}`);
    wss.clients.forEach(client => {
      if (client.readyState === WebSocket.OPEN) {
        client.send(JSON.stringify({ clients }));
      }
    });
  });
});

// API route
app.post('/api/give-treat', (req, res) => {
  let chickyFound = false;

  // Find the client named "chicky"
  wss.clients.forEach(client => {
    if (client.readyState === WebSocket.OPEN && client.name === 'chicky') {
      chickyFound = true;
      client.send(JSON.stringify({ command: 'feed', servo: 'servo1' }));
    }
  });

  if (chickyFound) {
    res.status(200).send('Treat given!');
  } else {
    res.status(404).send('Failed to give treat: brooder controller not connected :(');
  }
});

server.listen(port, () => {
  console.log(`Server is running on http://localhost:${port}`);
});