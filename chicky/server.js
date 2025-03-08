const express = require('express');
const { spawnSync } = require('child_process');
const config = require('./config');
const { io } = require('socket.io-client');

const app = express();
const port = config.port;
const vpsUrl = config.vps_url;
const authToken = config.auth_token;

// Middleware
app.use(express.json());

// Enable basic logging
app.use((req, res, next) => {
    console.log(`${new Date().toISOString()} - ${req.method} ${req.url}`);
    next();
});

// Health check endpoint (for local monitoring)
app.get('/health', (req, res) => {
    res.status(200).json({
        status: 'ok',
        timestamp: Date.now()
    });
});

// Socket.IO connection to VPS
let socket;
let connected = false;

function connectToServer() {
    console.log(`Connecting to server at ${vpsUrl}`);
    
    // Create Socket.IO client with WebSocket-only transport
    socket = io(vpsUrl, {
        transports: ['websocket'],  // WebSocket only, no polling
        reconnection: true,
        reconnectionAttempts: Infinity,
        reconnectionDelay: 1000
    });
    
    // Connection event
    socket.on('connect', () => {
        console.log('Connected to server');
        connected = true;
        
        // Authenticate with the server
        socket.emit('authenticate', {
            name: 'chicky',
            token: authToken
        });
        
        console.log('Sent authentication request');
    });
    
    // Disconnection event
    socket.on('disconnect', (reason) => {
        console.log(`Disconnected from server: ${reason}`);
        connected = false;
    });
    
    // Reconnection attempt event
    socket.io.on('reconnect_attempt', (attempt) => {
        console.log(`Reconnection attempt #${attempt}`);
    });
    
    // Reconnection event
    socket.io.on('reconnect', (attempt) => {
        console.log(`Reconnected after ${attempt} attempts`);
        connected = true;
    });
    
    // Error event
    socket.on('connect_error', (error) => {
        console.error('Connection error:', error.message);
    });
    
    // State sync event
    socket.on('state-sync', (data) => {
        console.log('Received state sync:', data);
    });
    
    // Toggle light command
    socket.on('toggle-light', (data) => {
        console.log('Received toggle light command:', data);
        handleLightCommand(data);
    });
    
    // Give treat command
    socket.on('give-treat', (data) => {
        console.log('Received give treat command:', data);
        handleTreatCommand(data);
    });
}

// Function to handle light commands
function handleLightCommand(data) {
    try {
        const state = data.state;
        if (state !== 'on' && state !== 'off') {
            console.error('Invalid light state:', state);
            socket.emit('light-confirmation', {
                success: false,
                state: state,
                error: 'Invalid state'
            });
            return;
        }
        
        console.log(`Toggling light to ${state}`);
        
        // Run the Python script to control the light
        const result = spawnSync('python3', ['light.py', state]);
        
        if (result.error) {
            console.error('Error executing Python script:', result.error);
            socket.emit('light-confirmation', {
                success: false,
                state: state,
                error: 'Script execution failed'
            });
            return;
        }
        
        console.log('Light toggled successfully:', result.stdout.toString());
        socket.emit('light-confirmation', {
            success: true,
            state: state
        });
    } catch (error) {
        console.error('Error handling light command:', error);
        socket.emit('light-confirmation', {
            success: false,
            state: data.state,
            error: error.message
        });
    }
}

// Function to handle treat commands
function handleTreatCommand(data) {
    try {
        const servo = data.servo || 'servo1';
        let servoValue;
        
        if (servo === 'servo1') {
            servoValue = config.servo1;
        } else if (servo === 'servo2') {
            servoValue = config.servo2;
        } else {
            console.error('Invalid servo:', servo);
            socket.emit('treat-confirmation', {
                success: false,
                servo: servo,
                error: 'Invalid servo'
            });
            return;
        }
        
        console.log(`Moving ${servo}`);
        
        // Run the Python script to move the servo to 180 degrees
        const result = spawnSync('python3', ['servocontrol.py', servoValue, '180']);
        
        if (result.error) {
            console.error('Error executing Python script:', result.error);
            socket.emit('treat-confirmation', {
                success: false,
                servo: servo,
                error: 'Script execution failed'
            });
            return;
        }
        
        console.log('Servo moved to 180 degrees:', result.stdout.toString());
        
        // Wait for 0.5 seconds and then move the servo to 1 degree
        setTimeout(() => {
            const result2 = spawnSync('python3', ['servocontrol.py', servoValue, '1']);
            
            if (result2.error) {
                console.error('Error executing Python script:', result2.error);
                socket.emit('treat-confirmation', {
                    success: false,
                    servo: servo,
                    error: 'Script execution failed'
                });
                return;
            }
            
            console.log('Servo moved to 1 degree:', result2.stdout.toString());
            socket.emit('treat-confirmation', {
                success: true,
                servo: servo
            });
        }, 500);
    } catch (error) {
        console.error('Error handling treat command:', error);
        socket.emit('treat-confirmation', {
            success: false,
            servo: data.servo,
            error: error.message
        });
    }
}

// Add a connection status endpoint
app.get('/status', (req, res) => {
    res.status(200).json({
        status: 'ok',
        timestamp: Date.now(),
        socket: {
            connected: connected,
            id: socket ? socket.id : null
        }
    });
});

// Start the local server
app.listen(port, '0.0.0.0', () => {
    console.log(`Chicky local server listening on port ${port}`);
    console.log(`Connecting to server at ${vpsUrl}`);
    console.log(`Auth token is ${authToken ? 'configured' : 'not configured'}`);
    
    // Connect to the server
    connectToServer();
});