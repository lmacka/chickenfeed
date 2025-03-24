/**
 * Terminal module for handling terminal output
 */

let lastStats = null;
let inactivityTimer = null;

/**
 * Updates the terminal with a message
 * @param {string} message - The message to display in the terminal
 * @param {HTMLElement} terminal - The terminal element
 */
function updateTerminal(message, terminal) {
  // Remove existing cursor
  const existingCursor = terminal.querySelector('.cursor');
  if (existingCursor) {
    existingCursor.remove();
  }
  
  // Add new message
  terminal.innerHTML = message;
  
  // Add cursor back
  const cursor = document.createElement('span');
  cursor.textContent = '█';
  cursor.className = 'cursor';
  terminal.appendChild(cursor);
  
  // Scroll to bottom
  terminal.scrollTop = terminal.scrollHeight;
  
  // Reset inactivity timer
  if (inactivityTimer) {
    clearTimeout(inactivityTimer);
  }
  
  // Start new inactivity timer
  inactivityTimer = setTimeout(() => {
    if (lastStats) {
      displayStats(terminal);
    }
  }, 10000); // 10 seconds
}

/**
 * Updates the terminal with sensor readings
 * @param {Object} readings - The sensor readings
 * @param {HTMLElement} terminal - The terminal element
 */
function updateTerminalWithStats(readings, terminal) {
  lastStats = readings;
  displayStats(terminal);
}

/**
 * Displays stats in the terminal
 * @param {HTMLElement} terminal - The terminal element
 */
function displayStats(terminal) {
  // First check if we have a valid terminal element
  if (!terminal) {
    console.warn('Terminal element not found');
    return;
  }

  // If no stats yet, show waiting message
  if (!lastStats) {
    updateTerminal("Waiting for sensor data...\nSTANDING BY...", terminal);
    return;
  }

  // If stats failed, show error
  if (!lastStats.success) {
    updateTerminal("SENSOR ERROR: " + (lastStats.error || "No data") + "\nSTANDING BY...", terminal);
    return;
  }

  // Safe number formatting helper
  const formatNumber = (num, decimals = 1) => {
    return (typeof num === 'number' && !isNaN(num)) ? num.toFixed(decimals) : '--';
  };

  const stats = [
    "STANDING BY...",
    `TEMP: ${formatNumber(lastStats.temperature)}°C`,
    `HUM: ${formatNumber(lastStats.humidity)}%`,
    `PRESS: ${formatNumber(lastStats.pressure)}hPa`,
    `LUX: ${formatNumber(lastStats.light)}`
  ].join('\n');

  updateTerminal(stats, terminal);
}

export { updateTerminal, updateTerminalWithStats }; 