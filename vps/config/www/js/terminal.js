/**
 * Terminal module for handling terminal output
 */

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
}

export { updateTerminal }; 