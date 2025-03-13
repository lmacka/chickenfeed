/**
 * API routes for the local server
 */
const express = require('express');
const router = express.Router();
const logger = require('../utils/logger');
const { controlLight } = require('../hardware/hardwareInterface');
const { isWithinAllowedHours } = require('../utils/validation');
const { getSocket, isConnected, checkDns } = require('../services/socketService');

/**
 * Health check endpoint
 */
router.get('/health', (req, res) => {
  res.status(200).json({
    status: 'ok',
    timestamp: Date.now()
  });
});

/**
 * Connection status endpoint
 */
router.get('/status', (req, res) => {
  const socket = getSocket();
  
  res.status(200).json({
    status: 'ok',
    timestamp: Date.now(),
    socket: {
      connected: isConnected(),
      id: socket ? socket.id : null
    },
    config: {
      vpsUrl: req.app.locals.config.vpsUrl,
      authTokenConfigured: !!req.app.locals.config.authToken,
      debug: req.app.locals.config.debug
    },
    system: {
      uptime: process.uptime(),
      memory: process.memoryUsage(),
      nodeVersion: process.version
    }
  });
});

/**
 * Test WebSocket connection
 */
router.get('/test-connection', (req, res) => {
  const socket = getSocket();
  
  if (!isConnected()) {
    logger.info('Test connection requested but not connected');
    res.status(503).json({
      success: false,
      message: 'Not connected to server'
    });
    return;
  }
  
  logger.info('Test connection requested, sending ping...');
  const startTime = Date.now();
  socket.emit('ping', {}, () => {
    const latency = Date.now() - startTime;
    logger.info(`Test connection successful. Latency: ${latency}ms`);
  });
  
  res.status(200).json({
    success: true,
    message: 'Ping sent to server',
    socketId: socket.id
  });
});

/**
 * DNS lookup test
 */
router.get('/dns-test', async (req, res) => {
  try {
    const result = await checkDns(req.app.locals.config.vpsUrl);
    res.status(200).json({
      success: true,
      hostname: result.hostname,
      addresses: result.addresses
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

/**
 * WebSocket URL test
 */
router.get('/url-test', (req, res) => {
  const vpsUrl = req.app.locals.config.vpsUrl;
  
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
    
    logger.info(`URL test successful for ${url.hostname}`);
    res.status(200).json(urlInfo);
  } catch (error) {
    logger.error(`URL test failed: ${error.message}`);
    res.status(400).json({
      success: false,
      originalUrl: vpsUrl,
      error: error.message
    });
  }
});

/**
 * Manual light control (for local testing)
 */
router.post('/light', (req, res) => {
  const state = req.body.state;
  const config = req.app.locals.config;
  
  // Check if the command is within allowed hours
  if (!isWithinAllowedHours(config)) {
    const message = `Light command rejected: outside allowed hours (${config.allowed_start_hour}am-${config.allowed_end_hour > 12 ? (config.allowed_end_hour - 12) + 'pm' : config.allowed_end_hour + 'am'})`;
    logger.warn(message);
    
    return res.status(403).json({
      success: false,
      error: `Sorry, the chicken coop light can only be operated between ${config.allowed_start_hour}am and ${config.allowed_end_hour > 12 ? (config.allowed_end_hour - 12) + 'pm' : config.allowed_end_hour + 'am'}.`
    });
  }
  
  // Control the light
  const result = controlLight(state);
  
  // Send the result
  if (result.success) {
    res.status(200).json(result);
  } else {
    res.status(500).json(result);
  }
});

module.exports = router; 