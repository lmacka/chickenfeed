/**
 * Unified drag handler using interact.js
 */

/**
 * Initializes draggable functionality for a panel
 * @param {HTMLElement} panel - The panel element to make draggable
 * @param {Object} options - Configuration options
 * @param {string} options.handle - Selector for the drag handle
 * @param {string} options.excludeSelector - Selector for elements to exclude from drag
 * @param {boolean} options.maintainHeight - Whether to maintain panel height during drag
 * @param {Function} options.onDragStart - Callback when drag starts
 * @param {Function} options.onDragEnd - Callback when drag ends
 */
export function initializeDraggablePanel(panel, options = {}) {
  const {
    handle = '.panel-header',
    excludeSelector = '#info-button, #close-panel, #close-chat',
    maintainHeight = true,
    onDragStart = null,
    onDragEnd = null
  } = options;
  
  // Store initial height if needed
  const initialHeight = maintainHeight ? panel.offsetHeight : null;

  // Initialize interact.js draggable
  interact(panel)
    .draggable({
      allowFrom: handle,
      ignoreFrom: excludeSelector,
      modifiers: [
        // Keep within window bounds
        interact.modifiers.restrictRect({
          restriction: 'parent',
          endOnly: true
        })
      ],
      listeners: {
        start(event) {
          // Reset bottom positioning when drag starts
          event.target.style.bottom = 'auto';
          if (maintainHeight) {
            event.target.style.height = `${initialHeight}px`;
          }
          if (onDragStart) onDragStart(event);
        },
        move(event) {
          const target = event.target;
          // Get current position or default to 0
          const x = (parseFloat(target.getAttribute('data-x')) || 0) + event.dx;
          const y = (parseFloat(target.getAttribute('data-y')) || 0) + event.dy;

          // Update element position using transform
          target.style.transform = `translate(${x}px, ${y}px)`;
          
          // Store position
          target.setAttribute('data-x', x);
          target.setAttribute('data-y', y);
        },
        end(event) {
          if (onDragEnd) onDragEnd(event);
        }
      },
      inertia: {
        resistance: 10,
        minSpeed: 100,
        endSpeed: 10
      },
      autoScroll: true
    });
} 