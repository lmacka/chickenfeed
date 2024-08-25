import express from 'express';
import fetch from 'node-fetch';
import { WebSocketServer } from 'ws';
import http from 'http';

const app = express();
const port = 3000;

// Create an HTTP server
const server = http.createServer(app);

app.use(express.static('public')); // Serve static files from the 'public' directory

// Create a WebSocket server
const wss = new WebSocketServer({ noServer: true });

let clients = 0;

wss.on('connection', (ws) => {
  clients++;
  wss.clients.forEach(client => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(JSON.stringify({ clients }));
    }
  });

  ws.on('close', () => {
    clients--;
    wss.clients.forEach(client => {
      if (client.readyState === WebSocket.OPEN) {
        client.send(JSON.stringify({ clients }));
      }
    });
  });
});

// Handle WebSocket upgrade requests
server.on('upgrade', (request, socket, head) => {
  const pathname = new URL(request.url, `http://${request.headers.host}`).pathname;

  if (pathname === '/ws') {
    wss.handleUpgrade(request, socket, head, (ws) => {
      wss.emit('connection', ws, request);
    });
  } else {
    socket.destroy();
  }
});

// API route
app.post('/api/give-treat', async (req, res) => {
  try {
    const response = await fetch('http://localhost:3080/cycle', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ servo: 'servo1' })
    });

    if (response.ok) {
      console.log('Treat given to the chickens!');
      res.sendStatus(200);
    } else {
      console.error('Failed to give treat.');
      res.sendStatus(500);
    }
  } catch (error) {
    console.error('Error:', error);
    res.sendStatus(500);
  }
});

server.listen(port, '0.0.0.0', () => {
  console.log(`Server running at http://0.0.0.0:${port}`);
});