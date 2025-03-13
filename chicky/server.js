const express = require('express');
const { spawnSync } = require('child_process');
const { io } = require('socket.io-client');
const dns = require('dns');
const schedule = require('node-schedule');

const app = express();
const port = process.env.PORT || 3000;
const vpsUrl = process.env.REMOTE_SERVER;
const authToken = process.env.AUTH_TOKEN;

// Default configuration object (will be updated from server)
const config = {
  servo1_pin: 15,
  servo2_pin: 14,
  debug: false,
  allowed_start_hour: 5,
  allowed_end_hour: 19,
  timezone_offset: 10
};

// Helper function to parse config values with appropriate types
function parseConfigValue(key, value) {
  // Boolean conversion
  if (value === 'true') return true;
  if (value === 'false') return false;
  
  // Number conversion for known numeric fields
  if (['servo1_pin', 'servo2_pin', 'allowed_start_hour', 
       'allowed_end_hour', 'timezone_offset'].includes(key)) {
    return parseInt(value, 10);
  }
  
  // Default: return as is
  return value;
}

// Validate required environment variables
function validateConfig() {
    const missingVars = [];
    
    if (!vpsUrl) missingVars.push('REMOTE_SERVER');
    if (!authToken) missingVars.push('AUTH_TOKEN');
    
    if (missingVars.length > 0) {
        console.warn(`WARNING: Missing environment variables: ${missingVars.join(', ')}`);
        console.warn('Some functionality may be limited');
        return false;
    }
    
    return true;
}

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
let pingInterval; // Add variable to track the ping interval
let lightShutoffJob; // Add variable to track the light shutoff job

function connectToServer() {
    console.log(`Connecting to server at ${vpsUrl || 'undefined'}`);
    console.log(`Debug mode: ${config.debug ? 'enabled' : 'disabled'}`);
    
    // Check if vpsUrl is defined before attempting to connect
    if (!vpsUrl) {
        console.error('Connection failed: Server URL is undefined');
        console.error('Please set REMOTE_SERVER environment variable in Balena dashboard');
        return;
    }
    
    // Clear existing ping interval if it exists
    if (pingInterval) {
        clearInterval(pingInterval);
    }
    
    // Create Socket.IO client with WebSocket-only transport
    const socketOptions = {
        transports: ['websocket'],  // WebSocket only, no polling
        reconnection: true,
        reconnectionAttempts: Infinity,
        reconnectionDelay: 1000,
        timeout: 20000  // Increase timeout
    };
    
    socket = io(vpsUrl, socketOptions);
    
    // Connection event
    socket.on('connect', () => {
        console.log('Connected to server');
        console.log(`Socket ID: ${socket.id}`);
        connected = true;
        
        // Authenticate with the server
        const authData = {
            name: 'chicky',
            token: authToken
        };
        socket.emit('authenticate', authData);
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
        
        // Request updated configuration
        socket.emit('config-request');
    });
    
    // Error event
    socket.on('connect_error', (error) => {
        console.error('Connection error:', error.message);
        
        // Log network status if possible
        try {
            const { networkInterfaces } = require('os');
            const nets = networkInterfaces();
            console.log('Network interfaces:');
            for (const name of Object.keys(nets)) {
                for (const net of nets[name]) {
                    if (net.family === 'IPv4' && !net.internal) {
                        console.log(`- ${name}: ${net.address}`);
                    }
                }
            }
        } catch (err) {
            console.error('Error getting network info:', err.message);
        }
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
    
    // Configuration sync event
    socket.on('config-sync', (serverConfig) => {
        console.log('Received configuration from server:', serverConfig);
        
        // Update all configuration values
        for (const [key, value] of Object.entries(serverConfig)) {
            config[key] = parseConfigValue(key, value);
        }
        
        // Log the updated configuration
        console.log('Applied new configuration:');
        for (const [key, value] of Object.entries(config)) {
            console.log(`- ${key}: ${value}`);
        }
        
        // Restart the light shutoff scheduler with the new end hour
        if (lightShutoffJob) {
            lightShutoffJob.cancel();
        }
        lightShutoffJob = setupAutoLightShutoff();
    });
}

// Function to check if current time is within allowed hours
function isWithinAllowedHours() {
    // Get current UTC time from the Pi
    const now = new Date();
    
    // Convert to AEST+10 by adding the timezone offset
    const aestHour = (now.getUTCHours() + config.timezone_offset) % 24;
    
    // Check if current hour is within allowed range
    return aestHour >= config.allowed_start_hour && aestHour < config.allowed_end_hour;
}

// Function to handle light commands
function handleLightCommand(data) {
    try {
        // Check if the command is within allowed hours
        if (!isWithinAllowedHours()) {
            console.log(`Light command rejected: outside allowed hours (${config.allowed_start_hour}am-${config.allowed_end_hour > 12 ? (config.allowed_end_hour - 12) + 'pm' : config.allowed_end_hour + 'am'})`);
            socket.emit('light-confirmation', {
                success: false,
                state: data.state,
                error: `Sorry, the chicken coop light can only be operated between ${config.allowed_start_hour}am and ${config.allowed_end_hour > 12 ? (config.allowed_end_hour - 12) + 'pm' : config.allowed_end_hour + 'am'}.`
            });
            return;
        }

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
        
        console.log('Light toggled successfully');
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
        // Check if the command is within allowed hours
        if (!isWithinAllowedHours()) {
            console.log(`Treat command rejected: outside allowed hours (${config.allowed_start_hour}am-${config.allowed_end_hour > 12 ? (config.allowed_end_hour - 12) + 'pm' : config.allowed_end_hour + 'am'})`);
            socket.emit('treat-confirmation', {
                success: false,
                servo: data.servo || 'servo1',
                error: `Sorry, treats can only be dispensed between ${config.allowed_start_hour}am and ${config.allowed_end_hour > 12 ? (config.allowed_end_hour - 12) + 'pm' : config.allowed_end_hour + 'am'}.`
            });
            return;
        }

        const servo = data.servo || 'servo1';
        let servoValue;
        
        if (servo === 'servo1') {
            servoValue = config.servo1_pin;
        } else if (servo === 'servo2') {
            servoValue = config.servo2_pin;
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
        
        // Wait for 0.5 seconds and then move the servo to 1 degree
        setTimeout(() => {
            try {
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
                
                console.log('Servo movement completed');
                socket.emit('treat-confirmation', {
                    success: true,
                    servo: servo
                });
            } catch (error) {
                console.error('Error moving servo back:', error);
                socket.emit('treat-confirmation', {
                    success: false,
                    servo: servo,
                    error: error.message
                });
            }
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

// Function to automatically turn off lights at the configured end hour
function setupAutoLightShutoff() {
    console.log(`Setting up automatic light shutoff at hour ${config.allowed_end_hour}`);
    
    // Schedule the job to run every hour
    const job = schedule.scheduleJob('0 * * * *', () => {
        // Get current hour in the configured timezone
        const now = new Date();
        const currentHour = (now.getUTCHours() + config.timezone_offset) % 24;
        
        // Check if it's time to turn off the lights
        if (currentHour === config.allowed_end_hour) {
            console.log(`Auto-shutdown: Turning off lights at configured end hour (${config.allowed_end_hour})`);
            
            try {
                // Run the Python script to turn off the light
                const result = spawnSync('python3', ['light.py', 'off']);
                
                if (result.error) {
                    console.error('Error executing light shutdown script:', result.error);
                } else {
                    console.log('Lights turned off successfully by auto-shutdown');
                    
                    // Notify the server about the state change if connected
                    if (connected) {
                        socket.emit('light-confirmation', {
                            success: true,
                            state: 'off',
                            automatic: true
                        });
                    }
                }
            } catch (error) {
                console.error('Error in automatic light shutdown:', error);
            }
        }
    });
    
    console.log('Automatic light shutoff scheduled');
    return job;
}

// Add a connection status endpoint
app.get('/status', (req, res) => {
    res.status(200).json({
        status: 'ok',
        timestamp: Date.now(),
        socket: {
            connected: connected,
            id: socket ? socket.id : null
        },
        config: {
            vpsUrl: vpsUrl,
            authTokenConfigured: !!authToken,
            debug: config.debug
        },
        system: {
            uptime: process.uptime(),
            memory: process.memoryUsage(),
            nodeVersion: process.version
        }
    });
});

// Add a diagnostic endpoint for testing WebSocket connection
app.get('/test-connection', (req, res) => {
    if (!connected) {
        console.log('Test connection requested but not connected, attempting to reconnect...');
        connectToServer();
        res.status(503).json({
            success: false,
            message: 'Not connected to server, attempting to reconnect'
        });
        return;
    }
    
    console.log('Test connection requested, sending ping...');
    const startTime = Date.now();
    socket.emit('ping', {}, () => {
        const latency = Date.now() - startTime;
        console.log(`Test connection successful. Latency: ${latency}ms`);
    });
    
    res.status(200).json({
        success: true,
        message: 'Ping sent to server',
        socketId: socket.id
    });
});

// Add a DNS lookup test endpoint
app.get('/dns-test', async (req, res) => {
    if (!vpsUrl) {
        return res.status(400).json({
            success: false,
            error: 'Server URL is not configured'
        });
    }

    const dns = require('dns').promises;
    const url = new URL(vpsUrl);
    const hostname = url.hostname;
    
    console.log(`Testing DNS resolution for ${hostname}...`);
    
    try {
        const addresses = await dns.lookup(hostname, { all: true });
        console.log(`DNS resolution successful: ${JSON.stringify(addresses)}`);
        
        res.status(200).json({
            success: true,
            hostname: hostname,
            addresses: addresses
        });
    } catch (error) {
        console.error(`DNS resolution failed: ${error.message}`);
        
        res.status(500).json({
            success: false,
            hostname: hostname,
            error: error.message
        });
    }
});

// Add a WebSocket URL test endpoint
app.get('/url-test', (req, res) => {
    if (!vpsUrl) {
        return res.status(400).json({
            success: false,
            error: 'Server URL is not configured'
        });
    }

    // Parse the WebSocket URL
    try {
        const url = new URL(vpsUrl);
        const alternativeUrls = [
            `wss://${url.hostname}/socket.io/`,
            `wss://${url.hostname}/ws/`,
            `https://${url.hostname}/socket.io/`,
            `https://${url.hostname}`
        ];
        
        const urlInfo = {
            success: true,
            originalUrl: vpsUrl,
            protocol: url.protocol,
            hostname: url.hostname,
            port: url.port || (url.protocol === 'wss:' ? '443' : '80'),
            pathname: url.pathname,
            search: url.search,
            alternatives: alternativeUrls
        };
        
        console.log(`URL test successful for ${url.hostname}`);
        res.status(200).json(urlInfo);
    } catch (error) {
        console.error(`URL test failed: ${error.message}`);
        res.status(400).json({
            success: false,
            originalUrl: vpsUrl,
            error: error.message
        });
    }
});

// Start the local server
app.listen(port, '0.0.0.0', () => {
    console.log(`Chicky local server listening on port ${port}`);
    
    // Log system information
    console.log('=== SYSTEM INFORMATION ===');
    console.log(`Node.js: ${process.version}, Platform: ${process.platform}, Arch: ${process.arch}`);
    console.log(`Working directory: ${process.cwd()}`);
    console.log('=========================');
    
    // Validate configuration
    const isConfigValid = validateConfig();
    
    // Set up the automatic light shutoff
    lightShutoffJob = setupAutoLightShutoff();
    
    // If vpsUrl is defined, try to connect
    if (vpsUrl) {
        try {
            const url = new URL(vpsUrl);
            console.log(`Attempting to connect to ${url.hostname}...`);
            
            // Perform DNS lookup
            dns.lookup(url.hostname, (err, address, family) => {
                if (err) {
                    console.error(`DNS lookup failed: ${err.message}`);
                } else {
                    console.log(`DNS lookup successful: ${address} (IPv${family})`);
                }
                
                // Connect to the server regardless of DNS result
                connectToServer();
            });
        } catch (error) {
            console.error(`Invalid URL format: ${error.message}`);
            // Don't attempt to connect with invalid URL
        }
    } else {
        console.error('No server URL provided. Remote functionality disabled.');
    }
});