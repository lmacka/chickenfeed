import { initializeDraggablePanel } from './drag-handler.js';

export class ChatWindow {
    constructor(socket) {
        this.socket = socket;
        this.chatPanel = document.getElementById('chat-panel');
        this.setupChatWindow();
    }

    setupChatWindow() {
        // Show the panel
        this.chatPanel.style.display = 'block';
        
        // Position it initially
        this.chatPanel.style.bottom = '20px';
        this.chatPanel.style.right = '20px';
        
        this.setupEventListeners();
    }

    setupEventListeners() {
        const input = this.chatPanel.querySelector('#chat-input');
        const closeBtn = this.chatPanel.querySelector('#close-chat');

        const sendMessage = () => {
            const message = input.value.trim();
            if (message) {
                this.socket.emit('chat_message', { message });
                input.value = '';
            }
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
        
        const timestamp = new Date(data.timestamp).toLocaleTimeString();
        msg.innerHTML = `
            <span class="timestamp">[${timestamp}]</span>
            <span class="user">${data.userId}:</span>
            ${data.message}
        `;
        
        messages.appendChild(msg);
        messages.scrollTop = messages.scrollHeight;
    }

    loadHistory(messages) {
        const messagesDiv = this.chatPanel.querySelector('#chat-messages');
        messagesDiv.innerHTML = 'LOADING CHAT HISTORY...<br><br>';
        
        setTimeout(() => {
            messagesDiv.innerHTML = '';
            messages.forEach(msg => this.displayMessage(msg));
        }, 1000);
    }
} 