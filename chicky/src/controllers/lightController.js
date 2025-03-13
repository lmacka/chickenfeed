/**
 * Light controller for handling light-related commands
 */
const logger = require('../utils/logger');
const { isWithinAllowedHours } = require('../utils/validation');
const { controlLight } = require('../hardware/hardwareInterface');

/**
 * Handle light command from remote server
 * @param {Object} data - Command data
 * @param {Object} config - Configuration object
 * @param {Object} socket - Socket.IO client
 */
function handleLightCommand(data, config, socket) {
  try {
    // Check if the command is within allowed hours
    if (!isWithinAllowedHours(config)) {
      // If configuration is not available, provide a generic message
      const message = config.allowed_start_hour === null || config.allowed_end_hour === null
        ? 'Light command rejected: waiting for configuration from server'
        : `Light command rejected: outside allowed hours (${config.allowed_start_hour}am-${config.allowed_end_hour > 12 ? (config.allowed_end_hour - 12) + 'pm' : config.allowed_end_hour + 'am'})`;
      
      logger.warn(message);
      
      socket.emit('light-confirmation', {
        success: false,
        state: data.state,
        error: config.allowed_start_hour === null || config.allowed_end_hour === null
          ? 'Sorry, the system is still initializing. Please try again in a moment.'
          : `Sorry, the chicken coop light can only be operated between ${config.allowed_start_hour}am and ${config.allowed_end_hour > 12 ? (config.allowed_end_hour - 12) + 'pm' : config.allowed_end_hour + 'am'}.`
      });
      return;
    }

    // Control the light
    const result = controlLight(data.state);
    
    // Send confirmation to the server
    socket.emit('light-confirmation', result);
  } catch (error) {
    logger.error('Error handling light command:', error);
    socket.emit('light-confirmation', {
      success: false,
      state: data.state,
      error: error.message
    });
  }
}

/**
 * Automatically turn off lights at the configured end hour
 * @param {Object} config - Configuration object
 * @param {Object} socket - Socket.IO client
 * @param {boolean} connected - Whether the socket is connected
 */
function autoShutoffLight(config, socket, connected) {
  // Check if configuration is available
  if (config.allowed_end_hour === null) {
    logger.warn('Auto-shutdown skipped: configuration not yet available');
    return;
  }
  
  logger.info(`Auto-shutdown: Turning off lights at configured end hour (${config.allowed_end_hour})`);
  
  try {
    // Turn off the light
    const result = controlLight('off');
    
    // Notify the server about the state change if connected
    if (connected && result.success) {
      socket.emit('light-confirmation', {
        success: true,
        state: 'off',
        automatic: true
      });
    }
  } catch (error) {
    logger.error('Error in automatic light shutdown:', error);
  }
}

module.exports = {
  handleLightCommand,
  autoShutoffLight
}; 