export class PanelManager {
  constructor() {
    this.panels = new Map();
    this.isMobile = window.innerWidth <= 768;
    this.setupEventListeners();
  }

  setupEventListeners() {
    window.addEventListener('resize', () => {
      this.isMobile = window.innerWidth <= 768;
      this.updatePanelBehavior();
    });
  }

  registerPanel(id, options = {}) {
    const panel = document.getElementById(id);
    if (!panel) return;

    const config = {
      isDraggable: options.isDraggable ?? true,
      isExpandable: options.isExpandable ?? true,
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
    
    if (this.isMobile) {
      this.initializeMobilePanel(element, config);
    } else {
      this.initializeDesktopPanel(element, config);
    }
  }

  initializeMobilePanel(panel, config) {
    if (!config.isExpandable) return;

    // Create handle if it doesn't exist
    let handle = panel.querySelector('.panel-handle');
    if (!handle) {
      handle = document.createElement('div');
      handle.className = 'panel-handle';
      panel.insertBefore(handle, panel.firstChild);
    }

    // Make the panel draggable using interact.js
    interact(panel).draggable({
      handle: '.panel-handle, .panel-header',
      modifiers: [
        interact.modifiers.restrict({
          restriction: 'parent',
          endOnly: true
        })
      ],
      inertia: true,
      autoScroll: true,
      listeners: {
        start(event) {
          panel.style.transition = 'none';
        },
        move(event) {
          const target = event.target;
          const y = (parseFloat(target.getAttribute('data-y')) || 0) + event.dy;
          
          // Only allow vertical dragging
          target.style.transform = `translateY(${y}px)`;
          target.setAttribute('data-y', y);
        },
        end(event) {
          const target = event.target;
          const y = parseFloat(target.getAttribute('data-y')) || 0;
          
          target.style.transition = 'transform 0.3s ease';
          
          // Snap to either fully expanded or collapsed
          if (y > panel.offsetHeight / 2) {
            target.style.transform = `translateY(${panel.offsetHeight - 40}px)`;
            target.classList.add('collapsed');
          } else {
            target.style.transform = 'translateY(0)';
            target.classList.remove('collapsed');
          }
          
          target.setAttribute('data-y', 0);
        }
      }
    });
  }

  initializeDesktopPanel(panel, config) {
    if (!config.isDraggable) return;

    // Make the panel draggable using interact.js
    interact(panel).draggable({
      handle: '.panel-header',
      modifiers: [
        interact.modifiers.restrict({
          restriction: 'parent',
          endOnly: true
        })
      ],
      inertia: true,
      autoScroll: true,
      listeners: {
        start(event) {
          panel.style.transition = 'none';
          panel.classList.add('dragging');
        },
        move(event) {
          const target = event.target;
          const x = (parseFloat(target.getAttribute('data-x')) || 0) + event.dx;
          const y = (parseFloat(target.getAttribute('data-y')) || 0) + event.dy;
          
          target.style.transform = `translate(${x}px, ${y}px)`;
          target.setAttribute('data-x', x);
          target.setAttribute('data-y', y);
        },
        end(event) {
          const target = event.target;
          target.style.transition = 'transform 0.3s ease';
          target.classList.remove('dragging');
        }
      }
    });
  }

  updatePanelBehavior() {
    this.panels.forEach((panel, id) => {
      this.initializePanel(id);
    });
  }
} 