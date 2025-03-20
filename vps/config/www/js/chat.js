export class ChatWindow {
    constructor(socket) {
        this.socket = socket;
        this.panel = document.getElementById('chat-panel');
        this.setupChatWindow();
    }

    setupChatWindow() {
        // Show the panel
        this.panel.style.display = 'block';
        
        // Position it initially
        this.panel.style.bottom = '20px';
        this.panel.style.right = '20px';
        
        this.setupEventListeners();
        this.setupDraggable();
    }

    setupEventListeners() {
        const input = this.panel.querySelector('#chat-input');
        const closeBtn = this.panel.querySelector('#close-chat');

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
            this.panel.style.display = 'none';
        };

        // Socket listeners
        this.socket.on('chat_message', (data) => this.displayMessage(data));
        this.socket.on('chat_history', (data) => this.loadHistory(data.messages));
        
        // Request chat history
        this.socket.emit('request_chat_history');
    }

    setupDraggable() {
        const header = this.panel.querySelector('.panel-header');
        let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;

        const elementDrag = (e) => {
            e.preventDefault();
            pos1 = pos3 - e.clientX;
            pos2 = pos4 - e.clientY;
            pos3 = e.clientX;
            pos4 = e.clientY;
            this.panel.style.top = (this.panel.offsetTop - pos2) + "px";
            this.panel.style.left = (this.panel.offsetLeft - pos1) + "px";
        };

        const closeDragElement = () => {
            document.onmouseup = null;
            document.onmousemove = null;
        };

        const dragMouseDown = (e) => {
            e.preventDefault();
            pos3 = e.clientX;
            pos4 = e.clientY;
            document.onmouseup = closeDragElement;
            document.onmousemove = elementDrag;
        };
        
        header.onmousedown = dragMouseDown;
    }

    displayMessage(data) {
        const messages = this.panel.querySelector('#chat-messages');
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
        const messagesDiv = this.panel.querySelector('#chat-messages');
        messagesDiv.innerHTML = 'LOADING CHAT HISTORY...<br><br>';
        
        setTimeout(() => {
            messagesDiv.innerHTML = '';
            messages.forEach(msg => this.displayMessage(msg));
        }, 1000);
    }
} 