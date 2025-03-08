// Simple test to verify Socket.IO can be loaded
console.log('Attempting to load Socket.IO...');
try {
  const socketio = require('socket.io');
  console.log('Socket.IO loaded successfully!');
  console.log('Socket.IO version:', socketio.version);
} catch (error) {
  console.error('Failed to load Socket.IO:', error);
  process.exit(1);
}

// Also try to load express
console.log('\nAttempting to load Express...');
try {
  const express = require('express');
  console.log('Express loaded successfully!');
} catch (error) {
  console.error('Failed to load Express:', error);
  process.exit(1);
} 