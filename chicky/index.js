/**
 * Main entry point for the Chickenfeed Pi component
 * This file is just a wrapper around the actual server implementation
 */

// Import the server
const { startServer } = require('./src/server');

// Start the server
startServer().catch((error) => {
  console.error('Failed to start server:', error);
  process.exit(1);
}); 