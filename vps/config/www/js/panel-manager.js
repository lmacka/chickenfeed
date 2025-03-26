export class PanelManager {
  constructor() {
    this.panels = new Map();
    this.isMobile = window.innerWidth <= 768;
    this.setupEventListeners();
  }

  setupEventListeners() {
    window.addEventListener('resize', () => {
      const wasMobile = this.isMobile;
      this.isMobile = window.innerWidth <= 768;
      
      // If mobile state changed, reinitialize panels
      if (wasMobile !== this.isMobile) {
        this.panels.forEach((_, id) => {
          this.initializePanel(id);
        });
      }
    });
  }

  registerPanel(id, options = {}) {
    const panel = document.getElementById(id);
    if (!panel) return;

    const config = {
      isDraggable: options.isDraggable ?? true,
      minWidth: options.minWidth ?? 280,
      maxWidth: options.maxWidth ?? 400,
      minHeight: options.minHeight ?? 300,
      maxHeight: options.maxHeight ?? '80vh',
      ...options
    };

    this.panels.set(id, { element: panel, config });
    this.initializePanel(id);
  }

  initializePanel(id) {
    const { element, config } = this.panels.get(id);
    
    // Reset any previous interact instance
    if (interact.isSet(element)) {
      interact(element).unset();
    }
    
    // Reset styles
    element.style.transform = '';
    element.removeAttribute('data-x');
    element.removeAttribute('data-y');
    
    // Set panel styles
    element.style.position = 'fixed';
    element.style.width = `${config.minWidth}px`;
    element.style.touchAction = 'none';
    element.style.userSelect = 'none';
    
    if (this.isMobile) {
      // Mobile: Center panels at bottom of screen using transform
      element.style.left = '50%';
      element.style.bottom = '20px';
      element.style.transform = 'translateX(-50%)'; // This centers perfectly regardless of width
      element.style.top = 'auto';
      element.style.right = 'auto';
      element.style.marginLeft = '0'; // Reset any margin-left
      
      // No dragging on mobile
      return;
    } else {
      // Desktop: Position as configured
      if (id === 'ptz-control-panel') {
        element.style.left = '20px';
        element.style.bottom = '20px';
        element.style.marginLeft = '0';
        element.style.top = 'auto';
        element.style.right = 'auto';
      } else if (id === 'chat-panel') {
        element.style.right = '20px';
        element.style.bottom = '20px';
        element.style.marginLeft = '0';
        element.style.left = 'auto';
        element.style.top = 'auto';
      }
    }
    
    // Only make draggable on desktop
    if (config.isDraggable) {
      // Initialize interact.js
      interact(element).draggable({
        handle: '.panel-header',
        ignoreFrom: '.panel-control',
        inertia: true,
        listeners: {
          start(event) {
            const target = event.target;
            const rect = target.getBoundingClientRect();
            
            // Convert bottom/right positioning to top/left for dragging
            if (target.style.bottom !== 'auto' && target.style.bottom !== '') {
              target.style.top = `${window.innerHeight - rect.bottom}px`;
              target.style.bottom = 'auto';
            }
            
            if (target.style.right !== 'auto' && target.style.right !== '') {
              target.style.left = `${window.innerWidth - rect.right}px`;
              target.style.right = 'auto';
            }
            
            target.classList.add('dragging');
          },
          move(event) {
            const target = event.target;
            // Get current position
            const x = (parseFloat(target.getAttribute('data-x')) || 0) + event.dx;
            const y = (parseFloat(target.getAttribute('data-y')) || 0) + event.dy;
            
            // Apply transform
            target.style.transform = `translate(${x}px, ${y}px)`;
            
            // Store position
            target.setAttribute('data-x', x);
            target.setAttribute('data-y', y);
          },
          end(event) {
            const target = event.target;
            // Get current rect
            const rect = target.getBoundingClientRect();
            const x = parseFloat(target.getAttribute('data-x')) || 0;
            const y = parseFloat(target.getAttribute('data-y')) || 0;
            
            // Apply the current position directly
            target.style.transform = '';
            target.style.left = `${rect.left}px`;
            target.style.top = `${rect.top}px`;
            target.setAttribute('data-x', 0);
            target.setAttribute('data-y', 0);
            
            target.classList.remove('dragging');
          }
        },
        modifiers: [
          // Keep the element within the viewport
          interact.modifiers.restrictRect({
            restriction: 'parent',
            endOnly: true
          })
        ]
      });
    }
  }

  updatePanelPositions() {
    this.panels.forEach(({ element }) => {
      // Check if panel is now outside viewport after resize
      const rect = element.getBoundingClientRect();
      const x = parseFloat(element.getAttribute('data-x')) || 0;
      const y = parseFloat(element.getAttribute('data-y')) || 0;
      
      let newX = x;
      let newY = y;
      
      // Adjust if out of bounds
      if (rect.right > window.innerWidth) {
        newX = x - (rect.right - window.innerWidth);
      }
      
      if (rect.bottom > window.innerHeight) {
        newY = y - (rect.bottom - window.innerHeight);
      }
      
      if (newX !== x || newY !== y) {
        element.style.transform = `translate(${newX}px, ${newY}px)`;
        element.setAttribute('data-x', newX);
        element.setAttribute('data-y', newY);
      }
    });
  }

  setupChatWindow() {
    // Don't show the panel by default - it should be hidden until the chat button is clicked
    // KEEP this line commented out to prevent automatic display: this.chatPanel.style.display = 'flex';
    
    // Set custom username if it exists in cookies
    if (this.customUsername) {
      this.socket.emit('set_username', { username: this.customUsername });
    }
    
    this.setupEventListeners();
  }
} 