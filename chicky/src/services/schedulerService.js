/**
 * Scheduler service for handling scheduled tasks
 */
const schedule = require('node-schedule');
const logger = require('../utils/logger');
const { autoShutoffLight } = require('../controllers/lightController');

let lightShutoffJob;

/**
 * Set up automatic light shutoff at the configured end hour
 * @param {Object} config - Configuration object
 * @param {Object} socket - Socket.IO client
 * @param {Function} isConnected - Function to check if socket is connected
 * @returns {Object} Scheduled job
 */
function setupAutoLightShutoff(config, socket, isConnected) {
  // Check if configuration is available
  if (config.allowed_end_hour === null) {
    logger.warn('Auto light shutoff setup skipped: configuration not yet available');
    return null;
  }
  
  logger.info(`Setting up automatic light shutoff at hour ${config.allowed_end_hour}`);
  
  // Cancel existing job if it exists
  if (lightShutoffJob) {
    lightShutoffJob.cancel();
  }
  
  // Schedule the job to run every hour
  const job = schedule.scheduleJob('0 * * * *', () => {
    // Get current hour in the configured timezone
    const now = new Date();
    
    // Check if timezone_offset is configured
    if (config.timezone_offset === null) {
      logger.warn('Auto light shutoff check skipped: timezone_offset not configured');
      return;
    }
    
    const currentHour = (now.getUTCHours() + config.timezone_offset) % 24;
    
    // Check if it's time to turn off the lights
    if (currentHour === config.allowed_end_hour) {
      autoShutoffLight(config, socket, isConnected());
    }
  });
  
  logger.info('Automatic light shutoff scheduled');
  return job;
}

/**
 * Update scheduler with new configuration
 * @param {Object} config - Configuration object
 * @param {Object} socket - Socket.IO client
 * @param {Function} isConnected - Function to check if socket is connected
 */
function updateScheduler(config, socket, isConnected) {
  lightShutoffJob = setupAutoLightShutoff(config, socket, isConnected);
}

/**
 * Gracefully shutdown all scheduled jobs
 */
function shutdownScheduler() {
  logger.info('Shutting down scheduler');
  
  if (lightShutoffJob) {
    lightShutoffJob.cancel();
    lightShutoffJob = null;
  }
}

module.exports = {
  setupAutoLightShutoff,
  updateScheduler,
  shutdownScheduler
}; 