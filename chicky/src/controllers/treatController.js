/**
 * Treat controller for handling treat dispensing commands
 */
const logger = require('../utils/logger');
const { isWithinAllowedHours } = require('../utils/validation');
const { dispenseTreat } = require('../hardware/hardwareInterface');

/**
 * Handle treat command from remote server
 * @param {Object} data - Command data
 * @param {Object} config - Configuration object
 * @param {Object} socket - Socket.IO client
 */
async function handleTreatCommand(data, config, socket) {
  try {
    // Check if the command is within allowed hours
    if (!isWithinAllowedHours(config)) {
      // If configuration is not available, provide a generic message
      const message = config.allowed_start_hour === null || config.allowed_end_hour === null
        ? 'Command rejected: waiting for configuration from server'
        : `Command rejected: outside allowed hours (${config.allowed_start_hour}am-${config.allowed_end_hour > 12 ? (config.allowed_end_hour - 12) + 'pm' : config.allowed_end_hour + 'am'})`;
      
      logger.warn(message);
      
      socket.emit('treat-confirmation', {
        success: false,
        servo: data.servo || 'servo1',
        error: config.allowed_start_hour === null || config.allowed_end_hour === null
          ? 'Sorry, the system is still initializing. Please try again in a moment.'
          : `Sorry, treats can only be dispensed between ${config.allowed_start_hour}am and ${config.allowed_end_hour > 12 ? (config.allowed_end_hour - 12) + 'pm' : config.allowed_end_hour + 'am'}.`
      });
      return;
    }

    const servo = data.servo || 'servo1';
    let servoPin;
    
    // Determine which servo to use
    if (servo === 'servo1') {
      servoPin = config.servo1_pin;
    } else if (servo === 'servo2') {
      servoPin = config.servo2_pin;
    } else {
      logger.error('Invalid servo:', servo);
      socket.emit('treat-confirmation', {
        success: false,
        servo: servo,
        error: 'Invalid servo'
      });
      return;
    }
    
    // Check if servo pin is configured
    if (servoPin === null) {
      logger.error(`Servo pin not configured for ${servo}`);
      socket.emit('treat-confirmation', {
        success: false,
        servo: servo,
        error: 'Servo not configured. Please wait for system initialization to complete.'
      });
      return;
    }
    
    logger.info(`Dispensing treat using ${servo}`);
    
    // Dispense the treat
    try {
      const result = await dispenseTreat(servo, servoPin);
      socket.emit('treat-confirmation', result);
    } catch (error) {
      logger.error('Error dispensing treat:', error);
      socket.emit('treat-confirmation', {
        success: false,
        servo: servo,
        error: error.error || error.message
      });
    }
  } catch (error) {
    logger.error('Error handling treat command:', error);
    socket.emit('treat-confirmation', {
      success: false,
      servo: data.servo || 'servo1',
      error: error.message
    });
  }
}

module.exports = {
  handleTreatCommand
}; 