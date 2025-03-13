/**
 * Simple logger utility
 */
const config = require('../../config/default');

const logger = {
  info: (message, ...args) => {
    console.log(`${new Date().toISOString()} - INFO: ${message}`, ...args);
  },
  
  warn: (message, ...args) => {
    console.warn(`${new Date().toISOString()} - WARN: ${message}`, ...args);
  },
  
  error: (message, ...args) => {
    console.error(`${new Date().toISOString()} - ERROR: ${message}`, ...args);
  },
  
  debug: (message, ...args) => {
    if (config.debug) {
      console.log(`${new Date().toISOString()} - DEBUG: ${message}`, ...args);
    }
  }
};

module.exports = logger; 