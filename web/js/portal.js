class Portal {
    constructor(myName, friendName, portalType) {
        this.socket = io();
        this.myName = myName;
        this.friendName = friendName;
        this.portalType = portalType;

        this.log = document.getElementById('log');
        this.status = document.getElementById('status');
        this.messageInput = document.getElementById('message');

        this.initializeSocket();
        this.setupEventListeners();
    }

    initializeSocket() {
        console.log(`Connecting as ${this.myName}, looking for ${this.friendName}`);
        this.socket.emit('register', this.myName);

        this.socket.on('message', (msg) => {
            const entry = document.createElement('p');
            entry.textContent = `[${msg.time} (${msg.timezone})] ${msg.from}: ${msg.text}`;
            this.log.appendChild(entry);
            this.log.scrollTop = this.log.scrollHeight;
        });
    }

    setupEventListeners() {
        document.querySelector('button').addEventListener('click', () => this.sendMessage());
    }

    sendMessage() {
        const text = this.messageInput.value;
        if (!text.trim()) return;

        const now = new Date();
        const msg = {
            from: this.myName,
            to: this.friendName,
            text,
            time: now.toLocaleString(),
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        };

        this.socket.emit('sendMessage', msg);
        this.messageInput.value = '';
    }
} 