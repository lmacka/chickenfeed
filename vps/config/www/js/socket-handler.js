/**
 * Socket handler module for managing WebSocket connections
 */
import { updateTerminal } from './terminal.js';
import { TERMINAL_MESSAGES } from './constants.js';
import { handleControlGranted, handleControlReleased } from './main.js';

/**
 * Sets up a WebSocket connection for viewer count updates
 * @param {Function} updateViewerCount - Function to update the viewer count display
 * @returns {Object} The socket connection
 */
function setupViewerCountSocket(updateViewerCount) {
  // Create a socket connection to the server
  const socket = io({
    path: '/socket.io',
    transports: ['websocket', 'polling'],
    reconnectionAttempts: 5,
    reconnectionDelay: 1000,
    // Force the connection to use the current hostname
    forceNew: true
  });
  
  console.log('Setting up Socket.IO connection to', window.location.origin);
  
  // Initialize with 0 to ensure proper display
  updateViewerCount(0);
  
  // Listen for visitor-count events
  socket.on('visitor-count', (data) => {
    const viewerCount = data.count || 0;
    updateViewerCount(viewerCount);
  });
  
  // Handle connection/reconnection
  socket.on('connect', () => {
    console.log('Connected to server for viewer count updates');
  });
  
  // Handle disconnection
  socket.on('disconnect', () => {
    console.log('Disconnected from server, viewer count updates paused');
    updateViewerCount(0);
  });
  
  // Handle connection errors
  socket.on('connect_error', (error) => {
    console.error('Socket.IO connection error:', error);
    updateViewerCount(0);
    
    // Try to reconnect with a different approach if needed
    if (socket.io.uri !== window.location.origin) {
      console.log('Trying to reconnect with explicit origin:', window.location.origin);
      socket.io.uri = window.location.origin;
      socket.connect();
    }
  });
  
  return socket;
}

/**
 * Sets up control status listeners
 * @param {Object} socket - The socket connection
 * @param {Object} options - Configuration options
 * @param {HTMLElement} options.terminal - The terminal element
 * @param {HTMLElement} options.takeControlButton - The take control button
 * @param {Function} options.disableAllControls - Function to disable all controls
 * @param {Function} options.stopControlTimer - Function to stop the control timer
 * @param {Object} options.state - State object containing hasControl flag
 */
function setupControlStatusListeners(socket, { terminal, takeControlButton, disableAllControls, stopControlTimer, state }) {
  socket.on('control-status', (data) => {
    if (data.userId !== socket.id) {
      // Another user has control or control was released
      if (data.inUse) {
        // Another user has control
        takeControlButton.classList.remove('active');
        takeControlButton.disabled = true;
        disableAllControls();
        
        if (state.hasControl) {
          // We lost control
          state.hasControl = false;
          stopControlTimer();
          updateTerminal(TERMINAL_MESSAGES.CONTROL_OVERRIDE, terminal);
        } else {
          // Just inform the user that control is in use
          updateTerminal(TERMINAL_MESSAGES.CONTROL_IN_USE, terminal);
        }
      } else {
        // No one has control
        takeControlButton.disabled = false;
        
        if (state.hasControl) {
          // We lost control
          state.hasControl = false;
          takeControlButton.classList.remove('active');
          disableAllControls();
          stopControlTimer();
          handleControlReleased(terminal);
        } else {
          // Just inform the user that control is available
          updateTerminal(TERMINAL_MESSAGES.CONTROL_AVAILABLE, terminal);
        }
      }
    }
  });
}

/**
 * Requests control from the server
 * @param {Object} socket - The socket connection
 * @param {Object} options - Configuration options
 * @param {HTMLElement} options.terminal - The terminal element
 * @param {HTMLElement} options.takeControlButton - The take control button
 * @param {Function} options.enableAllControls - Function to enable all controls
 * @param {Function} options.startControlTimer - Function to start the control timer
 * @param {number} options.controlTimeout - Control timeout in seconds
 * @param {Object} options.state - State object to update with control status
 */
function requestControl(socket, { terminal, takeControlButton, enableAllControls, startControlTimer, controlTimeout, state }) {
  socket.emit('request_control', {}, (response) => {
    if (response.success) {
      state.hasControl = true;
      takeControlButton.classList.add('active');
      enableAllControls();
      handleControlGranted(terminal);
      
      // Start the control timer
      startControlTimer(controlTimeout);
    } else {
      takeControlButton.classList.remove('active');
      updateTerminal(TERMINAL_MESSAGES.CONTROL_DENIED.replace('{message}', response.message), terminal);
    }
  });
}

/**
 * Releases control back to the server
 * @param {Object} socket - The socket connection
 * @param {Object} options - Configuration options
 * @param {HTMLElement} options.terminal - The terminal element
 * @param {HTMLElement} options.takeControlButton - The take control button
 * @param {Function} options.disableAllControls - Function to disable all controls
 * @param {Function} options.stopControlTimer - Function to stop the control timer
 * @param {Object} options.state - State object to update with control status
 */
function releaseControl(socket, { terminal, takeControlButton, disableAllControls, stopControlTimer, state }) {
  if (state.hasControl) {
    socket.emit('release_control', {}, (response) => {
      // Even if the server response fails, we'll release control locally
      state.hasControl = false;
      takeControlButton.classList.remove('active');
      disableAllControls();
      
      // Stop the control timer
      stopControlTimer();
      
      handleControlReleased(terminal);
    });
  }
}

/**
 * Notifies the server that a command was executed to reset the control timer
 * @param {Object} socket - The socket connection
 * @param {Object} options - Configuration options
 * @param {Object} options.state - State object containing hasControl flag
 * @returns {Promise} A promise that resolves with the notification result
 */
function notifyCommandExecuted(socket, { state }) {
  if (state.hasControl) {
    return new Promise((resolve) => {
      socket.emit('command_executed', {}, (response) => {
        console.log('Command execution notification result:', response);
        resolve(response);
      });
    });
  }
  return Promise.resolve({ success: false, message: 'No control' });
}

/**
 * Checks if the chicky client is connected to the server
 * @param {Object} socket - The socket connection
 * @returns {Promise} A promise that resolves with the chicky connection status
 */
function checkChickyStatus(socket) {
  return new Promise((resolve) => {
    socket.emit('check_chicky_status', {}, (response) => {
      console.log('Chicky status check result:', response);
      resolve(response);
    });
  });
}

export { 
  setupViewerCountSocket, 
  setupControlStatusListeners,
  requestControl,
  releaseControl,
  notifyCommandExecuted,
  checkChickyStatus
}; 