/**
 * Socket service for handling WebSocket communication with the VPS
 */
const { io } = require('socket.io-client');
const dns = require('dns');
const logger = require('../utils/logger');
const { parseConfigValue } = require('../utils/validation');
const { handleLightCommand } = require('../controllers/lightController');
const { handleTreatCommand } = require('../controllers/treatController');

let socket;
let connected = false;
let pingInterval;
let configRequested = false;
let lastConfigHash = '';

/**
 * Simple hash function for configuration objects
 * @param {Object} obj - The object to hash
 * @returns {string} A string hash of the object
 */
function hashConfig(obj) {
  return JSON.stringify(obj);
}

/**
 * Connect to the remote server
 * @param {Object} config - Configuration object
 * @param {Function} onConfigUpdate - Callback for configuration updates
 * @returns {Object} Socket and connection status
 */
function connectToServer(config, onConfigUpdate) {
  logger.info(`Connecting to server at ${config.vpsUrl || 'undefined'}`);
  
  // Check if vpsUrl is defined before attempting to connect
  if (!config.vpsUrl) {
    logger.error('Connection failed: Server URL is undefined');
    logger.error('Please set REMOTE_SERVER environment variable in Balena dashboard');
    return { socket: null, connected: false };
  }
  
  // Clear existing ping interval if it exists
  if (pingInterval) {
    clearInterval(pingInterval);
  }
  
  // Reset config requested flag
  configRequested = false;
  lastConfigHash = '';
  
  // Create Socket.IO client with WebSocket-only transport
  const socketOptions = {
    transports: ['websocket'],  // WebSocket only, no polling
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: 1000,
    timeout: 20000  // Increase timeout
  };
  
  socket = io(config.vpsUrl, socketOptions);
  
  // Connection event
  socket.on('connect', () => {
    logger.info('Connected to server');
    logger.info(`Socket ID: ${socket.id}`);
    connected = true;
    
    // Authenticate with the server
    const authData = {
      name: 'chicky',
      token: config.authToken
    };
    socket.emit('authenticate', authData);
    
    // Request configuration from the server
    if (!configRequested) {
      socket.emit('config-request');
      configRequested = true;
    }
  });
  
  // Disconnection event
  socket.on('disconnect', (reason) => {
    logger.info(`Disconnected from server: ${reason}`);
    connected = false;
    configRequested = false;
  });
  
  // Reconnection attempt event
  socket.io.on('reconnect_attempt', (attempt) => {
    logger.info(`Reconnection attempt #${attempt}`);
  });
  
  // Reconnection event
  socket.io.on('reconnect', (attempt) => {
    logger.info(`Reconnected after ${attempt} attempts`);
    connected = true;
    
    // Request updated configuration
    if (!configRequested) {
      socket.emit('config-request');
      configRequested = true;
    }
  });
  
  // Error event
  socket.on('connect_error', (error) => {
    logger.error('Connection error:', error.message);
    
    // Log network status if possible
    try {
      const { networkInterfaces } = require('os');
      const nets = networkInterfaces();
      logger.debug('Network interfaces:');
      for (const name of Object.keys(nets)) {
        for (const net of nets[name]) {
          if (net.family === 'IPv4' && !net.internal) {
            logger.debug(`- ${name}: ${net.address}`);
          }
        }
      }
    } catch (err) {
      logger.error('Error getting network info:', err.message);
    }
  });
  
  // State sync event
  socket.on('state-sync', (data) => {
    logger.info('Received state sync:', data);
  });
  
  // Toggle light command
  socket.on('toggle-light', (data) => {
    logger.info('Received toggle light command:', data);
    handleLightCommand(data, config, socket);
  });
  
  // Give treat command
  socket.on('give-treat', (data) => {
    logger.info('Received give treat command:', data);
    handleTreatCommand(data, config, socket);
  });
  
  // Configuration sync event
  socket.on('config-sync', (serverConfig) => {
    logger.info('Received configuration from server:', serverConfig);
    
    // Check if this is a duplicate configuration
    const configHash = hashConfig(serverConfig);
    if (configHash === lastConfigHash) {
      logger.info('Ignoring duplicate configuration');
      return;
    }
    lastConfigHash = configHash;
    
    // Map server config keys to local config keys if needed
    const configMapping = {
      'chicky_servo1_pin': 'servo1_pin',
      'chicky_servo2_pin': 'servo2_pin',
      'chicky_debug': 'debug',
      'chicky_allowed_start_hour': 'allowed_start_hour',
      'chicky_allowed_end_hour': 'allowed_end_hour',
      'chicky_timezone_offset': 'timezone_offset'
    };
    
    // Update all configuration values
    for (const [key, value] of Object.entries(serverConfig)) {
      // Check if we need to map the key
      const configKey = configMapping[key] || key;
      config[configKey] = parseConfigValue(configKey, value);
    }
    
    // Log the updated configuration
    logger.info('Applied server configuration:');
    for (const [key, value] of Object.entries(config)) {
      if (key !== 'authToken') { // Don't log sensitive information
        logger.info(`- ${key}: ${value}`);
      }
    }
    
    // Call the configuration update callback
    if (onConfigUpdate) {
      onConfigUpdate(config);
    }
  });
  
  return { socket, connected };
}

/**
 * Perform a DNS lookup for the server hostname
 * @param {string} vpsUrl - Server URL
 * @returns {Promise<Object>} DNS lookup result
 */
function checkDns(vpsUrl) {
  return new Promise((resolve, reject) => {
    if (!vpsUrl) {
      reject(new Error('Server URL is not configured'));
      return;
    }

    try {
      const url = new URL(vpsUrl);
      const hostname = url.hostname;
      
      logger.info(`Testing DNS resolution for ${hostname}...`);
      
      dns.lookup(hostname, { all: true }, (err, addresses) => {
        if (err) {
          logger.error(`DNS resolution failed: ${err.message}`);
          reject(err);
          return;
        }
        
        logger.info(`DNS resolution successful: ${JSON.stringify(addresses)}`);
        resolve({ hostname, addresses });
      });
    } catch (error) {
      logger.error(`Invalid URL format: ${error.message}`);
      reject(error);
    }
  });
}

module.exports = {
  connectToServer,
  checkDns,
  getSocket: () => socket,
  isConnected: () => connected
}; 