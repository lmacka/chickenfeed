/**
 * Main application entry point
 */
import { TERMINAL_MESSAGES, DEFAULT_CONTROL_TIMEOUT } from './constants.js';
import { updateTerminal, updateTerminalWithStats } from './terminal.js';
import { 
  setupViewerCountSocket, 
  setupControlStatusListeners,
  requestControl,
  releaseControl,
  notifyCommandExecuted,
  checkChickyStatus
} from './socket-handler.js';
import {
  initializeControlTimer,
  initializeButtonCooldowns,
  initializeControlButtons,
  disableAllControls,
  enableAllControls
} from './ptz-controls.js';
import { initializeHLSPlayer } from './video-player.js';
import { ChatWindow } from './chat.js';
import { PanelManager } from './panel-manager.js';

// Function to format sensor readings
function formatSensorReadings(readings) {
  if (!readings.success) {
    return `SENSOR ERROR: ${readings.error}`;
  }
  
  const { temperature, pressure, humidity, light, units } = readings;
  return `${temperature.toFixed(2)}${units.temperature} ${pressure.toFixed(2)}${units.pressure} ${humidity.toFixed(2)}${units.humidity} ${light.toFixed(6)}${units.light}`;
}

// Function to fetch sensor readings
async function fetchSensorReadings() {
  try {
    const response = await fetch('/api/sensors');
    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching sensor readings:', error);
    return {
      success: false,
      error: 'Failed to fetch sensor readings'
    };
  }
}

// Function to handle control granted
function handleControlGranted(terminal) {
  updateTerminal(TERMINAL_MESSAGES.CONTROL_GRANTED, terminal);
  // Fetch and display sensor readings
  fetchSensorReadings().then(readings => {
    updateTerminalWithStats(readings, terminal);
  });
}

// Function to handle control released
function handleControlReleased(terminal) {
  updateTerminal(TERMINAL_MESSAGES.CONTROL_RELEASED, terminal);
  // Fetch and display sensor readings
  fetchSensorReadings().then(readings => {
    updateTerminalWithStats(readings, terminal);
  });
}

// Export handler functions
export { handleControlGranted, handleControlReleased };

// Initialize the application when the DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  // Initialize panel manager
  const panelManager = new PanelManager();
  
  // Register panels with interact.js configuration
  panelManager.registerPanel('ptz-control-panel', {
    isDraggable: true,
    minWidth: 280,
    maxWidth: 280,
    minHeight: 350,
    initialPosition: { x: 20, y: window.innerHeight - 370 }
  });
  
  panelManager.registerPanel('chat-panel', {
    isDraggable: true,
    minWidth: 400,
    maxWidth: 400,
    minHeight: 300,
    initialPosition: { x: window.innerWidth - 420, y: window.innerHeight - 320 } // Bottom right
  });

  // Application state
  const state = {
    hasControl: false,
    controlTimeout: DEFAULT_CONTROL_TIMEOUT,
    chickyConnected: false
  };
  
  // Get DOM elements
  const videoElement = document.getElementById('chicken-stream');
  const ptzPanel = document.getElementById('ptz-control-panel');
  const panelHeader = document.querySelector('.panel-header');
  const terminal = document.getElementById('response-terminal');
  const takeControlButton = document.getElementById('take-control-button');
  const controlTimerCircle = document.getElementById('control-timer-circle');
  
  // Get control buttons
  const presetButtons = {
    'preset-1': document.getElementById('preset-1'),
    'preset-2': document.getElementById('preset-2'),
    'preset-3': document.getElementById('preset-3'),
    'preset-4': document.getElementById('preset-4'),
    'give-treat': document.getElementById('give-treat'),
    'toggle-light': document.getElementById('toggle-light')
  };
  
  // Get cooldown overlays
  const cooldownOverlays = {
    'preset-1': document.getElementById('cooldown-1'),
    'preset-2': document.getElementById('cooldown-2'),
    'preset-3': document.getElementById('cooldown-3'),
    'preset-4': document.getElementById('cooldown-4'),
    'give-treat': document.getElementById('cooldown-treat'),
    'toggle-light': document.getElementById('cooldown-light')
  };
  
  // Initialize the seven segment display
  $("#seven-seg-display").sevenSeg({
    digits: 3,
    value: 0,
    colorOff: "#121212",
    colorOn: "#00ff00"
  });
  
  // Function to update viewer count display
  function updateViewerCount(count) {
    // Update the hidden original display
    const viewersDisplay = document.getElementById('viewers-count');
    if (viewersDisplay) {
      viewersDisplay.textContent = count;
    }
    
    // Update the seven segment display with the new count
    try {
      $("#seven-seg-display").sevenSeg({ value: count });
    } catch (error) {
      console.error('Error updating seven segment display:', error);
    }
  }
  
  // Function to check chicky status and update UI accordingly
  function updateChickyStatus(socket) {
    checkChickyStatus(socket).then(response => {
      const wasConnected = state.chickyConnected;
      state.chickyConnected = response.connected;
      
      if (state.chickyConnected) {
        // Chicky is connected, enable control button if not already in use
        if (!wasConnected) {
          updateTerminal(TERMINAL_MESSAGES.CONTROL_PI_ONLINE, terminal);
          // Fetch and display sensor readings
          fetchSensorReadings().then(readings => {
            updateTerminalWithStats(readings, terminal);
          });
          if (!state.hasControl && !document.querySelector('.control-btn.active')) {
            takeControlButton.disabled = false;
          }
        }
      } else {
        // Chicky is not connected, disable control
        takeControlButton.disabled = true;
        updateTerminal(TERMINAL_MESSAGES.CONTROL_PI_OFFLINE, terminal);
        
        // If we had control, release it
        if (state.hasControl) {
          releaseControl(socket, {
            terminal,
            takeControlButton,
            disableAllControls: () => disableAllControls(presetButtons),
            stopControlTimer,
            state
          });
        }
      }
    }).catch(error => {
      console.error('Error checking chicky status:', error);
      state.chickyConnected = false;
      takeControlButton.disabled = true;
      updateTerminal(TERMINAL_MESSAGES.CONTROL_PI_OFFLINE, terminal);
    });
  }
  
  // Initialize the video player
  const player = initializeHLSPlayer(videoElement);
  
  // Initialize the control timer
  const { startControlTimer, stopControlTimer } = initializeControlTimer(controlTimerCircle);
  
  // Initialize button cooldowns
  const { startCooldown } = initializeButtonCooldowns(presetButtons, cooldownOverlays);
  
  // Initialize terminal with welcome message
  updateTerminal(TERMINAL_MESSAGES.INITIALIZING, terminal);
  
  // Setup WebSocket connection for viewer count
  const socket = setupViewerCountSocket(updateViewerCount);
  
  // Wait for socket to be connected before initializing controls
  socket.on('connect', () => {
    console.log('Socket connected, initializing controls with socket ID:', socket.id);
    
    // Check chicky status immediately after connection
    updateChickyStatus(socket);
    
    // Set up periodic chicky status check (every 30 seconds)
    const chickyStatusInterval = setInterval(() => {
      updateChickyStatus(socket);
    }, 30000);
    
    // Setup control status listeners
    setupControlStatusListeners(socket, {
      terminal,
      takeControlButton,
      disableAllControls: () => disableAllControls(presetButtons),
      stopControlTimer,
      state
    });
    
    // Initialize control buttons
    initializeControlButtons({
      buttons: presetButtons,
      terminal,
      startCooldown,
      startControlTimer: (timeout) => startControlTimer(timeout, () => {
        releaseControl(socket, {
          terminal,
          takeControlButton,
          disableAllControls: () => disableAllControls(presetButtons),
          stopControlTimer,
          state
        });
      }),
      controlTimeout: state.controlTimeout,
      state,
      socketId: socket.id,
      notifyServer: () => notifyCommandExecuted(socket, { state })
    });
    
    // Event listener for the power button
    takeControlButton.addEventListener('click', () => {
      // First check if chicky is connected
      updateChickyStatus(socket);
      
      if (!state.chickyConnected) {
        updateTerminal(TERMINAL_MESSAGES.CONTROL_PI_OFFLINE, terminal);
        return;
      }
      
      if (!state.hasControl) {
        requestControl(socket, {
          terminal,
          takeControlButton,
          enableAllControls: () => enableAllControls(presetButtons),
          startControlTimer: (timeout) => startControlTimer(timeout, () => {
            releaseControl(socket, {
              terminal,
              takeControlButton,
              disableAllControls: () => disableAllControls(presetButtons),
              stopControlTimer,
              state
            });
          }),
          controlTimeout: state.controlTimeout,
          state
        });
      } else {
        releaseControl(socket, {
          terminal,
          takeControlButton,
          disableAllControls: () => disableAllControls(presetButtons),
          stopControlTimer,
          state
        });
      }
    });
    
    // Clean up interval on disconnect
    socket.on('disconnect', () => {
      clearInterval(chickyStatusInterval);
      state.chickyConnected = false;
      takeControlButton.disabled = true;
    });
  });
  
  // Panel control handlers
  document.getElementById('info-button').addEventListener('click', () => {
    window.open('https://github.com/lmacka/chickenfeed', '_blank');
  });

  document.getElementById('close-panel').addEventListener('click', () => {
    ptzPanel.style.display = 'none';
  });
  
  // Initialize controls as disabled
  disableAllControls(presetButtons);
  takeControlButton.disabled = true;
  
  // Clean up socket connection when page unloads
  window.addEventListener('beforeunload', () => {
    if (socket && socket.connected) {
      console.log('Closing socket connection');
      socket.disconnect();
    }
    
    // Clean up video player
    if (player) {
      player.dispose();
    }
  });

  // Add inside the DOMContentLoaded event listener
  document.getElementById('chat-button').addEventListener('click', () => {
    new ChatWindow(socket);  // socket is your existing Socket.IO connection
  });

  // Add periodic stats update
  setInterval(() => {
    if (state.chickyConnected) {
      fetchSensorReadings().then(readings => {
        updateTerminalWithStats(readings, terminal);
      });
    }
  }, 5000); // Update every 5 seconds
}); 

function initializePanel(id) {
  const { element, config } = this.panels.get(id);
  
  // Set panel styles
  element.style.position = 'fixed';
  element.style.width = `${config.minWidth}px`;
  
  // Set initial position based on device
  const isMobile = window.innerWidth <= 768;
  let initialX = config.initialPosition.x;
  let initialY = config.initialPosition.y;
  
  // Adjust for mobile
  if (isMobile) {
    initialX = Math.min(initialX, window.innerWidth - element.offsetWidth - 10);
    initialY = Math.min(initialY, window.innerHeight - 100);
  }
  
  // Position directly using left/top instead of transform
  element.style.left = `${initialX}px`;
  element.style.top = `${initialY}px`;
  element.style.transform = 'translate(0, 0)'; // Reset any transform
  
  element.style.touchAction = 'none'; // Prevent scrolling when dragging on touch devices
  element.style.userSelect = 'none'; // Prevent text selection during drag
  
  if (!config.isDraggable) return;

  // Initialize interact.js
  interact(element).draggable({
    handle: '.panel-header',
    ignoreFrom: '.panel-control', // Don't drag when clicking buttons
    modifiers: [
      // Keep within window bounds
      interact.modifiers.restrictRect({
        restriction: 'parent',
        endOnly: true
      })
    ],
    inertia: {
      resistance: 10,
      minSpeed: 100,
      endSpeed: 10
    },
    listeners: {
      start(event) {
        event.target.classList.add('dragging');
      },
      move(event) {
        const target = event.target;
        
        // Get current left/top position
        const rect = target.getBoundingClientRect();
        const left = rect.left + event.dx;
        const top = rect.top + event.dy;
        
        // Keep within bounds
        const maxX = window.innerWidth - target.offsetWidth;
        const maxY = window.innerHeight - target.offsetHeight;
        const boundedLeft = Math.min(Math.max(0, left), maxX);
        const boundedTop = Math.min(Math.max(0, top), maxY);
        
        // Update element position
        target.style.left = `${boundedLeft}px`;
        target.style.top = `${boundedTop}px`;
      },
      end(event) {
        event.target.classList.remove('dragging');
      }
    }
  });
} 