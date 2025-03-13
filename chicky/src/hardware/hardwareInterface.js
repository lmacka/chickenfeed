/**
 * Hardware interface for controlling servos and lights
 */
const { spawnSync } = require('child_process');
const logger = require('../utils/logger');

/**
 * Control the light relay
 * @param {string} state - 'on' or 'off'
 * @returns {Object} Result of the operation
 */
function controlLight(state) {
  if (state !== 'on' && state !== 'off') {
    logger.error('Invalid light state:', state);
    return {
      success: false,
      error: 'Invalid state'
    };
  }
  
  logger.info(`Toggling light to ${state}`);
  
  try {
    // Run the Python script to control the light
    const result = spawnSync('python3', ['src/hardware/light.py', state]);
    
    if (result.error) {
      logger.error('Error executing Python script:', result.error);
      return {
        success: false,
        error: 'Script execution failed'
      };
    }
    
    logger.info('Light toggled successfully');
    return {
      success: true,
      state: state
    };
  } catch (error) {
    logger.error('Error handling light command:', error);
    return {
      success: false,
      error: error.message
    };
  }
}

/**
 * Control a servo motor
 * @param {string} servo - 'servo1' or 'servo2'
 * @param {number} servoPin - GPIO pin number
 * @param {number} angle - Angle to move the servo to (0-180)
 * @returns {Object} Result of the operation
 */
function controlServo(servo, servoPin, angle) {
  if (!servoPin) {
    logger.error('Invalid servo pin:', servoPin);
    return {
      success: false,
      error: 'Invalid servo pin'
    };
  }
  
  logger.info(`Moving ${servo} to ${angle} degrees`);
  
  try {
    // Run the Python script to move the servo
    const result = spawnSync('python3', ['src/hardware/servocontrol.py', servoPin.toString(), angle.toString()]);
    
    if (result.error) {
      logger.error('Error executing Python script:', result.error);
      return {
        success: false,
        error: 'Script execution failed'
      };
    }
    
    logger.info(`Servo ${servo} moved successfully to ${angle} degrees`);
    return {
      success: true,
      servo: servo,
      angle: angle
    };
  } catch (error) {
    logger.error('Error controlling servo:', error);
    return {
      success: false,
      error: error.message
    };
  }
}

/**
 * Dispense a treat by moving a servo back and forth
 * @param {string} servo - 'servo1' or 'servo2'
 * @param {number} servoPin - GPIO pin number
 * @returns {Promise<Object>} Result of the operation
 */
function dispenseTreat(servo, servoPin) {
  return new Promise((resolve, reject) => {
    // Check if servo pin is configured
    if (!servoPin) {
      logger.error(`Cannot dispense treat: ${servo} pin not configured`);
      return reject({
        success: false,
        error: 'Servo pin not configured'
      });
    }
    
    // Move servo to dispense position
    const result1 = controlServo(servo, servoPin, 180);
    
    if (!result1.success) {
      return reject(result1);
    }
    
    // Wait for 0.5 seconds and then move the servo back
    setTimeout(() => {
      const result2 = controlServo(servo, servoPin, 1);
      
      if (!result2.success) {
        return reject(result2);
      }
      
      resolve({
        success: true,
        servo: servo
      });
    }, 500);
  });
}

module.exports = {
  controlLight,
  controlServo,
  dispenseTreat
}; 