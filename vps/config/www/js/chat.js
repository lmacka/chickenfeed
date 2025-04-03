import { initializeDraggablePanel } from './drag-handler.js';
import { PanelManager } from './panel-manager.js';

export class ChatWindow {
    constructor(socket) {
        this.socket = socket;
        this.chatPanel = document.getElementById('chat-panel');
        this.customUsername = this.getCookie('chook_username') || null;
        this.setupChatWindow();
    }

    setupChatWindow() {
        // Show the panel
        this.chatPanel.style.display = 'flex';
        
        // Set custom username if it exists in cookies
        if (this.customUsername) {
            this.socket.emit('set_username', { username: this.customUsername });
        } else {
            // If no custom username exists, get the default one from the server and store it
            this.socket.emit('get_username', (response) => {
                if (response && response.username) {
                    this.customUsername = response.username;
                    this.setCookie('chook_username', response.username, 365);
                }
            });
        }
        
        this.setupEventListeners();
    }

    setupEventListeners() {
        const input = this.chatPanel.querySelector('#chat-input');
        const closeBtn = this.chatPanel.querySelector('#close-chat');
        const usernameBtn = document.getElementById('username-settings');
        const messages = this.chatPanel.querySelector('#chat-messages');

        const sendMessage = () => {
            const message = input.value.trim();
            
            // Client-side validation
            if (!message) return;
            
            if (message.length > 200) {
                this.displaySystemMessage('Message too long (max 200 characters)');
                return;
            }
            
            // Send message to server and handle response
            this.socket.emit('chat_message', { message }, (response) => {
                if (!response || !response.success) {
                    // Display error message
                    const errorMessage = response?.error || 'Failed to send message';
                    this.displaySystemMessage(errorMessage);
                }
            });
            
            input.value = '';
        };

        // Handle enter key
        input.onkeypress = (e) => {
            if (e.key === 'Enter') {
                sendMessage();
            }
        };

        // Handle close button
        closeBtn.onclick = () => {
            this.chatPanel.style.display = 'none';
        };

        // Handle username settings button
        usernameBtn.onclick = () => {
            this.showUsernameModal();
        };

        // Socket listeners
        this.socket.on('chat_message', (data) => this.displayMessage(data));
        this.socket.on('chat_history', (data) => this.loadHistory(data.messages));
        
        // Request chat history
        this.socket.emit('request_chat_history');
    }

    displayMessage(data) {
        const messages = this.chatPanel.querySelector('#chat-messages');
        const msg = document.createElement('div');
        msg.className = 'message';
        
        // Parse timestamp (in GMT+10)
        const timestamp = new Date(data.timestamp);
        
        // Format timestamp for hover display (24-hour format)
        const formattedDate = timestamp.toLocaleString('en-AU', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        });
        
        // Determine appropriate class for the username
        let userClass = 'user';
        
        // Add custom-username class if it's a custom username
        if (data.is_custom_username) {
            userClass += ' custom-username';
        }
        // Add no-country class if it's a breed-only username (no country code)
        else if (!data.userId.includes('-')) {
            userClass += ' no-country';
        }

        // Process message text to make URLs clickable
        const messageWithLinks = this.makeLinksClickable(data.message);
        
        msg.innerHTML = `
            <span class="${userClass}" data-timestamp="${formattedDate}">${data.userId}:</span>
            ${messageWithLinks}
        `;
        
        messages.appendChild(msg);
        messages.scrollTop = messages.scrollHeight;
    }

    makeLinksClickable(text) {
        if (!text) return '';
        
        // More comprehensive URL regex for better validation
        const urlRegex = /(https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|www\.[a-zA-Z0-9][a-zA-Z0-9-]+[a-zA-Z0-9]\.[^\s]{2,}|https?:\/\/(?:www\.|(?!www))[a-zA-Z0-9]+\.[^\s]{2,}|www\.[a-zA-Z0-9]+\.[^\s]{2,})/gi;
        
        // Replace URLs with clickable links
        return text.replace(urlRegex, (url) => {
            try {
                // If URL starts with www., add https:// prefix
                const href = url.startsWith('www.') ? 'https://' + url : url;
                
                // Basic URL validation
                const urlObj = new URL(href.startsWith('http') ? href : 'https://' + href);
                
                // Whitelist of allowed protocols
                if (!['http:', 'https:'].includes(urlObj.protocol)) {
                    return url; // Don't make it a link if protocol isn't allowed
                }
                
                // Create link with security attributes
                return `<a href="${href}" target="_blank" rel="noopener noreferrer nofollow" class="chat-link">${url}</a>`;
            } catch (e) {
                // If URL parsing fails, don't make it clickable
                return url;
            }
        });
    }

    loadHistory(messages) {
        const messagesDiv = this.chatPanel.querySelector('#chat-messages');
        messagesDiv.innerHTML = 'LOADING CHAT HISTORY...<br><br>';
        
        setTimeout(() => {
            messagesDiv.innerHTML = '';
            messages.forEach(msg => this.displayMessage(msg));
        }, 1000);
    }
    
    showUsernameModal() {
        // Remove any existing modal
        const existingModal = document.querySelector('.username-modal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // Create modal
        const modal = document.createElement('div');
        modal.className = 'username-modal';
        modal.innerHTML = `
            <h3>Set Chat Username</h3>
            <input type="text" id="username-input" maxlength="20" placeholder="Enter username (3-20 chars)" value="${this.customUsername || ''}">
            <div class="username-error" style="display: none; color: #ff3333; margin: 5px 0; font-size: 12px;"></div>
            <div class="username-modal-buttons">
                <button id="save-username">Save</button>
                <button id="cancel-username">Cancel</button>
                <button id="reset-username" class="reset-btn">Reset</button>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Focus input
        const input = document.getElementById('username-input');
        const errorDiv = modal.querySelector('.username-error');
        input.focus();
        
        // Function to display error message
        const showError = (message) => {
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
        };
        
        // Add event listeners
        document.getElementById('save-username').addEventListener('click', () => {
            const username = input.value.trim();
            
            // Client-side validation
            if (username && username.length < 3) {
                showError('Username must be at least 3 characters long');
                return;
            }
            
            if (username && !/^[a-zA-Z0-9_\-\.]+$/.test(username)) {
                showError('Username can only contain letters, numbers, underscores, hyphens and periods');
                return;
            }
            
            if (username) {
                this.socket.emit('set_username', { username }, (response) => {
                    if (response.success) {
                        this.customUsername = response.username;
                        this.setCookie('chook_username', response.username, 365); // Store for 1 year
                        modal.remove();
                    } else {
                        showError(response.error || 'Failed to set username');
                    }
                });
            }
        });
        
        document.getElementById('cancel-username').addEventListener('click', () => {
            modal.remove();
        });
        
        document.getElementById('reset-username').addEventListener('click', () => {
            this.socket.emit('set_username', { username: '' }, () => {
                this.customUsername = null;
                this.deleteCookie('chook_username');
                modal.remove();
            });
        });
        
        // Allow Enter key to save
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                document.getElementById('save-username').click();
            }
        });
    }
    
    setCookie(name, value, days) {
        const expires = new Date();
        expires.setTime(expires.getTime() + days * 24 * 60 * 60 * 1000);
        document.cookie = `${name}=${value};expires=${expires.toUTCString()};path=/;SameSite=Strict`;
    }
    
    getCookie(name) {
        const nameEQ = `${name}=`;
        const ca = document.cookie.split(';');
        for (let i = 0; i < ca.length; i++) {
            let c = ca[i];
            while (c.charAt(0) === ' ') c = c.substring(1, c.length);
            if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
        }
        return null;
    }
    
    deleteCookie(name) {
        document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/;SameSite=Strict`;
    }
    
    // Helper method to display system messages (errors, notifications)
    displaySystemMessage(message) {
        const messages = this.chatPanel.querySelector('#chat-messages');
        const msg = document.createElement('div');
        msg.className = 'message system-message';
        msg.innerHTML = `<span class="system">SYSTEM:</span> ${message}`;
        messages.appendChild(msg);
        messages.scrollTop = messages.scrollHeight;
    }
} 