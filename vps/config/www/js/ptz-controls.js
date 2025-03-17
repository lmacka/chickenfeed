/**
 * PTZ Controls module for handling camera control functionality
 */
import { updateTerminal } from './terminal.js';
import { TERMINAL_MESSAGES, COOLDOWN_TIME } from './constants.js';

/**
 * Initializes the PTZ control panel dragging functionality
 * @param {HTMLElement} ptzPanel - The PTZ control panel element
 * @param {HTMLElement} panelHeader - The panel header element
 */
function initializePanelDrag(ptzPanel, panelHeader) {
  let isDragging = false;
  let offsetX, offsetY;
  const initialHeight = ptzPanel.offsetHeight;
  
  // Make the panel draggable by the header
  panelHeader.addEventListener('mousedown', (e) => {
    if (e.target.closest('#info-button, #close-panel')) return;
    
    isDragging = true;
    offsetX = e.clientX - ptzPanel.getBoundingClientRect().left;
    offsetY = e.clientY - ptzPanel.getBoundingClientRect().top;
    e.preventDefault();
  });

  document.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    
    const x = e.clientX - offsetX;
    const y = e.clientY - offsetY;
    
    // Keep the panel within the viewport
    const maxX = window.innerWidth - ptzPanel.offsetWidth;
    const maxY = window.innerHeight - ptzPanel.offsetHeight;
    
    ptzPanel.style.left = Math.max(0, Math.min(x, maxX)) + 'px';
    ptzPanel.style.top = Math.max(0, Math.min(y, maxY)) + 'px';
    ptzPanel.style.bottom = 'auto'; // Remove bottom positioning when dragged
    ptzPanel.style.height = initialHeight + 'px'; // Maintain initial height
  });

  document.addEventListener('mouseup', () => {
    if (isDragging) {
      isDragging = false;
    }
  });

  // Touch support for mobile devices
  panelHeader.addEventListener('touchstart', (e) => {
    isDragging = true;
    offsetX = e.touches[0].clientX - ptzPanel.getBoundingClientRect().left;
    offsetY = e.touches[0].clientY - ptzPanel.getBoundingClientRect().top;
    e.preventDefault();
  });

  document.addEventListener('touchmove', (e) => {
    if (!isDragging) return;
    
    const x = e.touches[0].clientX - offsetX;
    const y = e.touches[0].clientY - offsetY;
    
    const maxX = window.innerWidth - ptzPanel.offsetWidth;
    const maxY = window.innerHeight - ptzPanel.offsetHeight;
    
    ptzPanel.style.left = Math.max(0, Math.min(x, maxX)) + 'px';
    ptzPanel.style.top = Math.max(0, Math.min(y, maxY)) + 'px';
    ptzPanel.style.bottom = 'auto'; // Remove bottom positioning when dragged
    ptzPanel.style.height = initialHeight + 'px'; // Maintain initial height
    e.preventDefault();
  });

  document.addEventListener('touchend', () => {
    isDragging = false;
  });
}

/**
 * Initializes the control timer functionality
 * @param {HTMLElement} circle - The circle element for the timer
 * @returns {Object} Functions to start and stop the timer
 */
function initializeControlTimer(circle) {
  let controlTimerInterval = null;
  let controlStartTime = 0;
  let onCompleteCallback = null;
  let timerDuration = 0;
  
  // Calculate the circumference of the circle
  const radius = circle.getAttribute('r');
  const circumference = 2 * Math.PI * radius;
  
  // Set the initial dasharray and dashoffset
  circle.style.strokeDasharray = circumference;
  circle.style.strokeDashoffset = circumference;
  
  /**
   * Starts or resets the control timer
   * @param {number} seconds - The duration in seconds
   * @param {Function} onComplete - Callback when timer completes
   */
  function startControlTimer(seconds, onComplete) {
    // Store the callback and duration for resets
    onCompleteCallback = onComplete;
    timerDuration = seconds * 1000;
    
    // Clear any existing interval
    if (controlTimerInterval) {
      clearInterval(controlTimerInterval);
    }
    
    // Reset the circle visual
    circle.style.strokeDashoffset = '0';
    
    // Reset the start time to now
    controlStartTime = Date.now();
    
    // Start the interval to update the progress
    controlTimerInterval = setInterval(() => {
      const elapsed = Date.now() - controlStartTime;
      const remaining = timerDuration - elapsed;
      
      if (remaining <= 0) {
        // Time's up, release control
        stopControlTimer();
        if (onCompleteCallback) onCompleteCallback();
        return;
      }
      
      // Calculate the progress and update the dashoffset
      const progress = remaining / timerDuration;
      const dashoffset = circumference * (1 - progress);
      circle.style.strokeDashoffset = dashoffset;
    }, 100); // Update every 100ms for smooth animation
  }
  
  /**
   * Stops the control timer
   */
  function stopControlTimer() {
    if (controlTimerInterval) {
      clearInterval(controlTimerInterval);
      controlTimerInterval = null;
    }
    
    // Reset the circle
    circle.style.strokeDashoffset = circumference;
    
    // Clear stored callback and duration
    onCompleteCallback = null;
    timerDuration = 0;
  }
  
  return { startControlTimer, stopControlTimer };
}

/**
 * Initializes button cooldown functionality
 * @param {Object} presetButtons - Object containing button elements
 * @param {Object} cooldownOverlays - Object containing cooldown overlay elements
 * @returns {Function} Function to start cooldown for a button
 */
function initializeButtonCooldowns(presetButtons, cooldownOverlays) {
  // Initialize cooldown overlays
  Object.keys(cooldownOverlays).forEach(key => {
    if (cooldownOverlays[key]) {
      cooldownOverlays[key].style.transform = 'scaleX(0)';
    }
  });
  
  /**
   * Starts cooldown for a button
   * @param {string} buttonId - The ID of the button
   */
  function startCooldown(buttonId) {
    const button = presetButtons[buttonId];
    const overlay = cooldownOverlays[buttonId];
    
    if (!button || !overlay) return;
    
    // Apply cooldown to all buttons
    Object.keys(presetButtons).forEach(key => {
      if (presetButtons[key]) {
        presetButtons[key].disabled = true;
      }
    });
    
    // Reset the overlay for the clicked button
    overlay.style.transform = 'scaleX(1)';
    
    // Animate the cooldown
    const startTime = Date.now();
    const animateCooldown = () => {
      const elapsed = Date.now() - startTime;
      const remaining = COOLDOWN_TIME - elapsed;
      
      if (remaining <= 0) {
        // Cooldown complete
        Object.keys(presetButtons).forEach(key => {
          if (presetButtons[key]) {
            presetButtons[key].disabled = false;
          }
        });
        overlay.style.transform = 'scaleX(0)';
        return;
      }
      
      // Update the overlay width
      const progress = remaining / COOLDOWN_TIME;
      overlay.style.transform = `scaleX(${progress})`;
      
      // Continue animation
      requestAnimationFrame(animateCooldown);
    };
    
    // Start the animation
    requestAnimationFrame(animateCooldown);
  }
  
  return { startCooldown };
}

/**
 * Sends a PTZ command to the server
 * @param {string} command - The command to send
 * @param {boolean} updateUI - Whether to update the UI with the response
 * @param {HTMLElement} terminal - The terminal element
 * @param {string} socketId - The socket ID for authentication
 * @param {Function} notifyServer - Function to notify the server about command execution
 * @returns {Promise} A promise that resolves with the command result
 */
function sendPTZCommand(command, updateUI = true, terminal, socketId, notifyServer) {
  // Visual feedback - add active class to button
  const buttonId = command.startsWith('preset-') ? 
                   `preset-${command.split('-')[1]}` : 
                   (command.startsWith('save-preset-') ? 
                    `preset-${command.split('-')[2]}` : 
                    `ptz-${command}`);
  
  const button = document.getElementById(buttonId);
  if (button) {
    // Remove active class from all buttons
    document.querySelectorAll('.control-btn').forEach(btn => {
      btn.classList.remove('active');
    });
    
    // Add active class to current button
    button.classList.add('active');
    
    if (updateUI) {
      setTimeout(() => button.classList.remove('active'), 200);
    }
  }
  
  // Return a promise for the command
  return fetch(`/ptz/control.py?action=${command}`, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
      'X-Socket-ID': socketId || ''
    }
  })
  .then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error ${response.status}`);
    }
    return response.json();
  })
  .then(data => {
    console.log(`PTZ command ${command} result:`, data);
    
    // Notify the server about command execution to reset the control timer
    if (notifyServer) {
      notifyServer();
    }
    
    // Update terminal with response if updateUI is true
    if (updateUI && terminal) {
      if (data.success) {
        updateTerminal(TERMINAL_MESSAGES.COMMAND_SUCCESS
          .replace('{command}', button ? button.textContent.trim() : command)
          .replace('{message}', data.message || 'Camera moved successfully'), terminal);
      } else {
        updateTerminal(TERMINAL_MESSAGES.COMMAND_FAILED
          .replace('{command}', button ? button.textContent.trim() : command)
          .replace('{message}', data.message || 'Error moving camera'), terminal);
      }
    }
    
    return data;
  })
  .catch(error => {
    console.error('Error executing PTZ command:', error);
    
    // Update terminal with error if updateUI is true
    if (updateUI && terminal) {
      updateTerminal(TERMINAL_MESSAGES.COMMAND_ERROR
        .replace('{command}', button ? button.textContent.trim() : command)
        .replace('{message}', error.message), terminal);
    }
    
    throw error;
  });
}

/**
 * Gives a treat to the chickens
 * @param {HTMLElement} terminal - The terminal element
 * @param {string} socketId - The socket ID for authentication
 * @param {Function} notifyServer - Function to notify the server about command execution
 * @returns {Promise} A promise that resolves with the command result
 */
function giveTreat(terminal, socketId, notifyServer) {
  return fetch('/api/give-treat', {
    method: 'POST',
    headers: {
      'X-Socket-ID': socketId || '',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({})
  })
  .then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error ${response.status}`);
    }
    return response.json();
  })
  .then(data => {
    console.log('Treat dispensed:', data);
    
    // Notify the server about command execution to reset the control timer
    if (notifyServer) {
      notifyServer();
    }
    
    // Update terminal with response
    if (terminal) {
      if (data.success) {
        updateTerminal(TERMINAL_MESSAGES.COMMAND_SUCCESS
          .replace('{command}', 'TREAT')
          .replace('{message}', data.message || 'Treat dispensed successfully'), terminal);
      } else {
        updateTerminal(TERMINAL_MESSAGES.COMMAND_FAILED
          .replace('{command}', 'TREAT')
          .replace('{message}', data.message || 'Error dispensing treat'), terminal);
      }
    }
    
    return data;
  })
  .catch(error => {
    console.error('Error dispensing treat:', error);
    
    // Update terminal with error
    if (terminal) {
      updateTerminal(TERMINAL_MESSAGES.COMMAND_ERROR
        .replace('{command}', 'TREAT')
        .replace('{message}', error.message), terminal);
    }
    
    throw error;
  });
}

/**
 * Toggles the light
 * @param {HTMLElement} terminal - The terminal element
 * @param {string} socketId - The socket ID for authentication
 * @param {Function} notifyServer - Function to notify the server about command execution
 * @returns {Promise} A promise that resolves with the command result
 */
function toggleLight(terminal, socketId, notifyServer) {
  return fetch('/api/toggle-light', {
    method: 'POST',
    headers: {
      'X-Socket-ID': socketId || '',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({})
  })
  .then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error ${response.status}`);
    }
    return response.json();
  })
  .then(data => {
    console.log('Light toggled:', data);
    
    // Notify the server about command execution to reset the control timer
    if (notifyServer) {
      notifyServer();
    }
    
    // Update terminal with response
    if (terminal) {
      if (data.success) {
        updateTerminal(TERMINAL_MESSAGES.COMMAND_SUCCESS
          .replace('{command}', 'LIGHT')
          .replace('{message}', data.message || 'Light toggled successfully'), terminal);
      } else {
        updateTerminal(TERMINAL_MESSAGES.COMMAND_FAILED
          .replace('{command}', 'LIGHT')
          .replace('{message}', data.message || 'Error toggling light'), terminal);
      }
    }
    
    return data;
  })
  .catch(error => {
    console.error('Error toggling light:', error);
    
    // Update terminal with error
    if (terminal) {
      updateTerminal(TERMINAL_MESSAGES.COMMAND_ERROR
        .replace('{command}', 'LIGHT')
        .replace('{message}', error.message), terminal);
    }
    
    throw error;
  });
}

/**
 * Initializes control buttons
 * @param {Object} options - Configuration options
 * @param {Object} options.buttons - Object containing button elements
 * @param {HTMLElement} options.terminal - The terminal element
 * @param {Function} options.startCooldown - Function to start cooldown for a button
 * @param {Function} options.startControlTimer - Function to start the control timer
 * @param {number} options.controlTimeout - Control timeout in seconds
 * @param {Object} options.state - State object containing hasControl flag
 * @param {string} options.socketId - The socket ID for authentication
 * @param {Function} options.notifyServer - Function to notify the server about command execution
 */
function initializeControlButtons({ buttons, terminal, startCooldown, startControlTimer, controlTimeout, state, socketId, notifyServer }) {
  // Preset 1 (HEATER) button
  buttons['preset-1'].addEventListener('click', () => {
    if (!buttons['preset-1'].disabled && state.hasControl) {
      updateTerminal(TERMINAL_MESSAGES.COMMAND_EXECUTING.replace('{command}', 'MOVE CAMERA TO HEATER'), terminal);
      sendPTZCommand('preset-1', true, terminal, socketId, notifyServer);
      startCooldown('preset-1');
      // Reset control timer
      startControlTimer(controlTimeout);
    } else if (!state.hasControl) {
      updateTerminal(TERMINAL_MESSAGES.NO_CONTROL_ERROR, terminal);
    }
  });
  
  // Preset 2 (FLOOR) button
  buttons['preset-2'].addEventListener('click', () => {
    if (!buttons['preset-2'].disabled && state.hasControl) {
      updateTerminal(TERMINAL_MESSAGES.COMMAND_EXECUTING.replace('{command}', 'MOVE CAMERA TO FLOOR'), terminal);
      sendPTZCommand('preset-2', true, terminal, socketId, notifyServer);
      startCooldown('preset-2');
      // Reset control timer
      startControlTimer(controlTimeout);
    } else if (!state.hasControl) {
      updateTerminal(TERMINAL_MESSAGES.NO_CONTROL_ERROR, terminal);
    }
  });
  
  // Preset 3 (PERCH) button
  buttons['preset-3'].addEventListener('click', () => {
    if (!buttons['preset-3'].disabled && state.hasControl) {
      updateTerminal(TERMINAL_MESSAGES.COMMAND_EXECUTING.replace('{command}', 'MOVE CAMERA TO PERCH'), terminal);
      sendPTZCommand('preset-3', true, terminal, socketId, notifyServer);
      startCooldown('preset-3');
      // Reset control timer
      startControlTimer(controlTimeout);
    } else if (!state.hasControl) {
      updateTerminal(TERMINAL_MESSAGES.NO_CONTROL_ERROR, terminal);
    }
  });
  
  // Preset 4 (FEEDERS) button
  buttons['preset-4'].addEventListener('click', () => {
    if (!buttons['preset-4'].disabled && state.hasControl) {
      updateTerminal(TERMINAL_MESSAGES.COMMAND_EXECUTING.replace('{command}', 'MOVE CAMERA TO FEEDERS'), terminal);
      sendPTZCommand('preset-4', true, terminal, socketId, notifyServer);
      startCooldown('preset-4');
      // Reset control timer
      startControlTimer(controlTimeout);
    } else if (!state.hasControl) {
      updateTerminal(TERMINAL_MESSAGES.NO_CONTROL_ERROR, terminal);
    }
  });
  
  // Give Treat button
  buttons['give-treat'].addEventListener('click', () => {
    if (!buttons['give-treat'].disabled && state.hasControl) {
      updateTerminal(TERMINAL_MESSAGES.COMMAND_EXECUTING.replace('{command}', 'DISPENSING TREAT'), terminal);
      
      // Start cooldown immediately to prevent multiple clicks
      startCooldown('give-treat');
      // Reset control timer
      startControlTimer(controlTimeout);
      
      // Check if we need to move to perch first
      const currentActiveButton = document.querySelector('.control-btn.active');
      const isPerchActive = currentActiveButton && currentActiveButton.id === 'preset-3';
      
      if (!isPerchActive) {
        updateTerminal(TERMINAL_MESSAGES.TREAT_SEQUENCE, terminal);
        
        // First move to perch
        sendPTZCommand('preset-3', false, terminal, socketId, notifyServer)
          .then(() => {
            // Wait 1 second before dispensing treat
            updateTerminal(TERMINAL_MESSAGES.CAMERA_POSITIONED, terminal);
            return new Promise(resolve => setTimeout(resolve, 1000));
          })
          .then(() => {
            // Then dispense treat
            updateTerminal(TERMINAL_MESSAGES.DISPENSING_TREAT, terminal);
            return giveTreat(terminal, socketId, notifyServer);
          })
          .catch(error => {
            updateTerminal(TERMINAL_MESSAGES.COMMAND_ERROR.replace('{command}', 'TREAT SEQUENCE').replace('{message}', error.message), terminal);
          });
      } else {
        // Already at perch, just dispense treat
        giveTreat(terminal, socketId, notifyServer);
      }
    } else if (!state.hasControl) {
      updateTerminal(TERMINAL_MESSAGES.NO_CONTROL_ERROR, terminal);
    }
  });
  
  // Toggle Light button
  buttons['toggle-light'].addEventListener('click', () => {
    if (!buttons['toggle-light'].disabled && state.hasControl) {
      updateTerminal(TERMINAL_MESSAGES.COMMAND_EXECUTING.replace('{command}', 'TOGGLING LIGHT'), terminal);
      toggleLight(terminal, socketId, notifyServer);
      startCooldown('toggle-light');
      // Reset control timer
      startControlTimer(controlTimeout);
    } else if (!state.hasControl) {
      updateTerminal(TERMINAL_MESSAGES.NO_CONTROL_ERROR, terminal);
    }
  });
}

/**
 * Disables all control buttons
 * @param {Object} presetButtons - Object containing button elements
 */
function disableAllControls(presetButtons) {
  Object.keys(presetButtons).forEach(key => {
    if (presetButtons[key]) {
      presetButtons[key].disabled = true;
    }
  });
}

/**
 * Enables all control buttons
 * @param {Object} presetButtons - Object containing button elements
 */
function enableAllControls(presetButtons) {
  Object.keys(presetButtons).forEach(key => {
    if (presetButtons[key]) {
      presetButtons[key].disabled = false;
    }
  });
}

export {
  initializePanelDrag,
  initializeControlTimer,
  initializeButtonCooldowns,
  initializeControlButtons,
  sendPTZCommand,
  giveTreat,
  toggleLight,
  disableAllControls,
  enableAllControls
}; 