/**
 * Express application for the Chickenfeed Pi component
 */
const express = require('express');
const logger = require('./utils/logger');
const apiRoutes = require('./routes/api');

/**
 * Create and configure the Express application
 * @param {Object} config - Configuration object
 * @returns {Object} Express application
 */
function createApp(config) {
  const app = express();
  
  // Store config in app.locals for access in routes
  app.locals.config = config;
  
  // Middleware
  app.use(express.json());
  
  // Enable basic logging
  app.use((req, res, next) => {
    logger.info(`${req.method} ${req.url}`);
    next();
  });
  
  // API routes
  app.use('/', apiRoutes);
  
  // Error handler
  app.use((err, req, res, next) => {
    logger.error('Unhandled error:', err);
    res.status(500).json({
      error: 'Internal server error',
      message: err.message
    });
  });
  
  return app;
}

module.exports = createApp; 