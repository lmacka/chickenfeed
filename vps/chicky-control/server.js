const express = require('express');
const { createServer } = require('http');
const { Server } = require('socket.io');
const morgan = require('morgan');

const app = express();
const port = process.env.PORT || 3000;
const authToken = process.env.CHICKY_AUTH_TOKEN || 'default-token-change-me';

// Create HTTP server
const httpServer = createServer(app);

// Create Socket.IO server
const io = new Server(httpServer, {
  cors: {
    origin: "*",
    methods: ["GET", "POST"]
  },
  // Only use WebSockets, disable polling completely
  transports: ['websocket']
});

// State tracking
let lightState = false; // Track the state of the light
let visitorCount = 0; // Track visitor count
let chickyClient = null; // Reference to the chicky client socket

// ===== MIDDLEWARE CONFIGURATION =====
// 1. Request logging middleware (Morgan with combined format to stdout)
app.use(morgan('combined'));

// 2. Parse JSON request bodies
app.use(express.json());

// 3. Enable CORS for API requests
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept');
  next();
});

// 4. Serve static files from the 'public' directory
app.use(express.static('public'));

// ===== SOCKET.IO HANDLERS =====
io.on('connection', (socket) => {
  console.log(`New client connected: ${socket.id}`);
  visitorCount++;
  
  // Send visitor count to all clients
  io.emit('visitor-count', { count: visitorCount });
  
  // Handle authentication
  socket.on('authenticate', (data) => {
    console.log(`Client ${socket.id} attempting to authenticate as ${data.name}`);
    
    // If this is the chicky client with correct auth token
    if (data.name === 'chicky' && data.token === authToken) {
      console.log(`Client ${socket.id} authenticated as chicky`);
      socket.join('chicky');
      chickyClient = socket;
      
      // Send current light state to the chicky client
      socket.emit('state-sync', { lightState });
    }
  });
  
  // Handle light toggle confirmation
  socket.on('light-confirmation', (data) => {
    console.log(`Received light confirmation: ${JSON.stringify(data)}`);
    if (data.success) {
      lightState = data.state === 'on';
      console.log(`Updated light state to: ${lightState ? 'on' : 'off'}`);
    }
  });
  
  // Handle treat confirmation
  socket.on('treat-confirmation', (data) => {
    console.log(`Received treat confirmation: ${JSON.stringify(data)}`);
  });
  
  // Handle disconnection
  socket.on('disconnect', () => {
    console.log(`Client disconnected: ${socket.id}`);
    
    // If the chicky client disconnected, clear the reference
    if (socket === chickyClient) {
      console.log('Chicky client disconnected');
      chickyClient = null;
    }
    
    visitorCount = Math.max(0, visitorCount - 1);
    io.emit('visitor-count', { count: visitorCount });
  });
});

// ===== API ROUTES =====
// Toggle light endpoint
app.all('/api/toggle-light', (req, res) => {
  // Check if chicky client is connected
  if (!chickyClient) {
    console.error('Toggle light failed: Chicky client not connected');
    return res.status(503).json({
      success: false,
      message: 'Chicky controller not connected',
      state: lightState ? 'on' : 'off'
    });
  }
  
  // Toggle the light state
  lightState = !lightState;
  const lightStateStr = lightState ? 'on' : 'off';
  console.log(`Toggling light to ${lightStateStr}`);
  
  // Send command to chicky client
  chickyClient.emit('toggle-light', { state: lightStateStr });
  console.log(`Sent toggle-light command to chicky: ${lightStateStr}`);
  
  res.status(200).json({
    success: true,
    message: `Light toggling to ${lightStateStr}`,
    state: lightStateStr
  });
});

// Give treat endpoint
app.all('/api/give-treat', (req, res) => {
  // Check if chicky client is connected
  if (!chickyClient) {
    console.error('Give treat failed: Chicky client not connected');
    return res.status(503).json({
      success: false,
      message: 'Chicky controller not connected'
    });
  }
  
  console.log('Giving treat');
  
  // Send command to chicky client
  chickyClient.emit('give-treat', { servo: 'servo1' });
  console.log('Sent give-treat command to chicky');
  
  res.status(200).json({
    success: true,
    message: 'Treat dispensing!'
  });
});

// Health check endpoint
app.get('/api/health', (req, res) => {
  res.status(200).json({
    status: chickyClient ? 'ok' : 'degraded',
    server: {
      uptime: process.uptime(),
      timestamp: Date.now()
    },
    chicky: {
      connected: !!chickyClient
    },
    light: {
      state: lightState ? 'on' : 'off'
    },
    visitors: visitorCount
  });
});

// Get visitor count
app.get('/api/visitors', (req, res) => {
  res.status(200).json({ count: visitorCount });
});

// WebSocket connectivity check endpoint
app.get('/api/ws-check', (req, res) => {
  res.status(200).json({
    socketIoRunning: true,
    activeConnections: io.engine.clientsCount,
    chickyConnected: !!chickyClient,
    chickyId: chickyClient ? chickyClient.id : null,
    lightState: lightState ? 'on' : 'off'
  });
});

// Start the server
httpServer.listen(port, () => {
  console.log(`Server is running on http://localhost:${port}`);
  console.log(`Socket.IO server is running`);
  console.log(`Auth token is ${authToken ? 'configured' : 'not configured'}`);
});