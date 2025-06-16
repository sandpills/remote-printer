const express = require('express');
const http = require('http');
const socketIO = require('socket.io');

const app = express();
const server = http.createServer(app);
const io = socketIO(server);

app.use(express.static(__dirname)); // serves index.html + socket.io

io.on('connection', (socket) => {
    let who = 'a user';

    socket.on('register', (name) => {
        socket.username = name;
        who = name;
        console.log(`✅ ${name} connected`);
    });

    socket.on('sendMessage', (msg) => {
        console.log(`📨 ${msg.from} → ${msg.to}: ${msg.text}`);
        io.emit('message', msg);
    });

    socket.on('disconnect', () => {
        if (socket.username) {
            console.log(`❌ ${socket.username} disconnected`);
        } else {
            console.log(`❌ An anonymous user disconnected`);
        }
    });
});

const PORT = 3000;
server.listen(PORT, () => {
    console.log(`🚀 Web chat portal running at http://localhost:${PORT}`);
});
