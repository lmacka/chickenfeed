/**
 * Main server for the Chickenfeed Pi component
 */
const createApp = require('./app');
const config = require('../config/default');
const logger = require('./utils/logger');
const { validateConfig } = require('./utils/validation');
const { connectToServer, checkDns } = require('./services/socketService');
const { updateScheduler, shutdownScheduler } = require('./services/schedulerService');

/**
 * Start the server
 */
async function startServer() {
  // Log system information
  logger.info('=== SYSTEM INFORMATION ===');
  logger.info(`Node.js: ${process.version}, Platform: ${process.platform}, Arch: ${process.arch}`);
  logger.info(`Working directory: ${process.cwd()}`);
  logger.info('=========================');
  
  // Validate configuration
  const isConfigValid = validateConfig(config);
  
  // Create the Express application
  const app = createApp(config);
  
  // Start the local server
  const server = app.listen(config.port, '0.0.0.0', () => {
    logger.info(`Chicky local server listening on port ${config.port}`);
    
    // If vpsUrl is defined, try to connect
    if (config.vpsUrl) {
      try {
        const url = new URL(config.vpsUrl);
        logger.info(`Attempting to connect to ${url.hostname}...`);
        
        // Perform DNS lookup
        checkDns(config.vpsUrl)
          .then(() => {
            // Connect to the server
            const { socket } = connectToServer(config, (updatedConfig) => {
              // Update scheduler when config changes
              updateScheduler(updatedConfig, socket, () => true);
            });
            
            // Set up the automatic light shutoff
            updateScheduler(config, socket, () => true);
          })
          .catch((error) => {
            logger.error(`DNS lookup failed: ${error.message}`);
            
            // Connect to the server anyway
            const { socket } = connectToServer(config, (updatedConfig) => {
              // Update scheduler when config changes
              updateScheduler(updatedConfig, socket, () => true);
            });
            
            // Set up the automatic light shutoff
            updateScheduler(config, socket, () => true);
          });
      } catch (error) {
        logger.error(`Invalid URL format: ${error.message}`);
        // Don't attempt to connect with invalid URL
      }
    } else {
      logger.error('No server URL provided. Remote functionality disabled.');
    }
  });
  
  // Handle graceful shutdown
  process.on('SIGTERM', () => gracefulShutdown(server));
  process.on('SIGINT', () => gracefulShutdown(server));
  
  return server;
}

/**
 * Gracefully shutdown the server
 * @param {Object} server - HTTP server
 */
function gracefulShutdown(server) {
  logger.info('Received shutdown signal');
  
  // Shutdown scheduler
  shutdownScheduler();
  
  // Close server
  server.close(() => {
    logger.info('Server closed');
    process.exit(0);
  });
  
  // Force close after timeout
  setTimeout(() => {
    logger.error('Could not close connections in time, forcefully shutting down');
    process.exit(1);
  }, 10000);
}

// Start the server if this file is run directly
if (require.main === module) {
  startServer().catch((error) => {
    logger.error('Failed to start server:', error);
    process.exit(1);
  });
}

module.exports = { startServer }; 