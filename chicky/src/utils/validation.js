/**
 * Validation utilities
 */
const logger = require('./logger');

/**
 * Validate required environment variables
 * @returns {boolean} True if all required variables are present
 */
function validateConfig(config) {
  const missingVars = [];
  
  if (!config.vpsUrl) missingVars.push('REMOTE_SERVER');
  if (!config.authToken) missingVars.push('AUTH_TOKEN');
  
  if (missingVars.length > 0) {
    logger.warn(`Missing environment variables: ${missingVars.join(', ')}`);
    logger.warn('Some functionality may be limited');
    return false;
  }
  
  return true;
}

/**
 * Parse configuration values with appropriate types
 * @param {string} key - Configuration key
 * @param {string|number|boolean} value - Configuration value
 * @returns {string|number|boolean} Parsed value
 */
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

/**
 * Check if current time is within allowed hours
 * @param {Object} config - Configuration object
 * @returns {boolean} True if current time is within allowed hours
 */
function isWithinAllowedHours(config) {
  // If the configuration is not yet available, default to false
  if (config.allowed_start_hour === null || config.allowed_end_hour === null || config.timezone_offset === null) {
    logger.warn('Time-based validation failed: configuration not yet available');
    return false;
  }
  
  // Get current UTC time
  const now = new Date();
  
  // Convert to configured timezone by adding the timezone offset
  const localHour = (now.getUTCHours() + config.timezone_offset) % 24;
  
  // Check if current hour is within allowed range
  return localHour >= config.allowed_start_hour && localHour < config.allowed_end_hour;
}

module.exports = {
  validateConfig,
  parseConfigValue,
  isWithinAllowedHours
}; 