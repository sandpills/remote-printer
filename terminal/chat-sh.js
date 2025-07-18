const mqtt = require('mqtt');
const blessed = require('blessed');

// ==== CONFIG ====
const MY_NAME = 'shanghai-cedar';              // ← your device name
const FRIEND_NAME = 'nyc-boshi';     // ← other party
const BROKER_URL = 'mqtt://test.mosquitto.org';
const SUB_TOPIC = `messages/${MY_NAME}`;
const PUB_TOPIC = `messages/${FRIEND_NAME}`;
const PRESENCE_TOPIC = `presence/${FRIEND_NAME}`;
const MY_PRESENCE_TOPIC = `presence/${MY_NAME}`;
const ASCII_RECEIEVE = `ascii/${MY_NAME}`

const HEARTBEAT_INTERVAL = 5000; // 5 seconds
const PRESENCE_TIMEOUT = 10000; // 10 seconds
let heartbeatTimer = null;
let presenceTimeout = null;

// ==== UI SETUP ====
const screen = blessed.screen({
    smartCSR: true,
    title: `MQTT Chat — ${MY_NAME}`,
});

let isOnline = false;

const presenceBox = blessed.box({
    top: 0,
    left: 0,
    width: '80%',
    height: 1,
    content: '', // will be filled dynamically
    tags: true,
    style: {
        fg: 'yellow'
        // bg: 'black',
    },
});

const log = blessed.log({
    top: 1, // shift one down
    left: 0,
    width: '100%',
    height: '90%',
    label: '', // ← leave empty initially
    border: 'line',
    scrollable: true,
    alwaysScroll: true,
    tags: true,
    keys: true,
    vi: true,
    mouse: true,
    scrollbar: { style: { bg: 'yellow' } },
});

const input = blessed.textbox({
    bottom: 0,
    height: 3,
    width: '100%',
    border: 'line',
    label: ' Type your message | Send "/p" to take photo ',
    inputOnFocus: true,
    style: {
        focus: { border: { fg: 'yellow' } },
    },
});

screen.append(presenceBox);
screen.append(log);
screen.append(input);
input.focus(); // focus on input after setup
screen.render();

// ==== MQTT CONNECTION ====
const client = mqtt.connect(BROKER_URL);

client.on('connect', () => {
    log.add('{green-fg}✓ Connected to MQTT{/green-fg}');
    client.subscribe([SUB_TOPIC, PRESENCE_TOPIC, ASCII_RECEIEVE], () => {
        screen.render();
    });

    // Heartbeat presence
    function sendHeartbeat() {
        client.publish(MY_PRESENCE_TOPIC, 'online', { retain: true });
    }
    heartbeatTimer = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL);
    sendHeartbeat(); // send immediately

    const selfStatus = `♥︎ ${MY_NAME} is online`;
    log.add(selfStatus);
    screen.render();
});

function getTimeString() {
    return new Date().toLocaleString('en-US', { hour12: true });
}

client.on('message', (topic, message) => {
    const msg = message.toString();
    const now = getTimeString();

    if (topic === PRESENCE_TOPIC) {
        updateStatus(msg.trim());
        // Heartbeat timeout logic
        if (presenceTimeout) clearTimeout(presenceTimeout);
        if (msg.trim() === 'online') {
            presenceTimeout = setTimeout(() => {
                updateStatus('offline');
            }, PRESENCE_TIMEOUT);
        }
        return;
    }

    if (topic === ASCII_RECEIEVE) {
        process.stdout.write('\x07'); // play bell sound
        log.add(`{gray-fg}[${now}]{/gray-fg} {cyan-fg}⇠ ${FRIEND_NAME}:{/cyan-fg} sent an ASCII image`);
        log.add(msg); // ASCII art
        screen.render();
        return;
    }

    // Existing message handling
    try {
        const data = JSON.parse(msg);
        process.stdout.write('\x07'); // play bell sound
        const ts = data.time || now;
        const isMe = data.from === MY_NAME;
        const nameColor = isMe ? 'green-fg' : 'cyan-fg';
        const arrow = isMe ? '⇢ you:' : `⇠ ${data.from}:`;
        log.add(`{gray-fg}[${ts}]{/gray-fg} {${nameColor}}${arrow}{/${nameColor}} ${data.text}`);
    } catch (err) {
        log.add(`{red-fg}✖ Invalid message:{/red-fg} ${msg}`);
    }

    screen.render();
});

client.on('error', (err) => {
    log.add(`{red-fg}✖ MQTT error:{/red-fg} ${err.message}`);
    screen.render();
});

// ==== SENDING ====
input.on('submit', (text) => {
    const trimmed = text.trim().toLowerCase();

    // to quit
    if (trimmed === 'exit') {
        clearInterval(heartbeatTimer);
        client.publish(MY_PRESENCE_TOPIC, 'offline', { retain: true, qos: 1 }, () => {
            client.end();
            process.exit(0);
        });
        return;
    }

    // to take photo
    if (trimmed === '/p') {
        if (!isOnline) {
            log.add('{red-fg}✖ Cannot send image: friend is offline{/red-fg}');
            screen.render();
            input.clearValue();
            input.focus();
            return;
        }

        log.add('{yellow-fg}Capturing ASCII image...{/yellow-fg}');
        screen.render();

        const { exec } = require('child_process');
        exec(`python3 terminal/ascii-cam-sender.py ${MY_NAME} ${FRIEND_NAME}`, (err, stdout, stderr) => {
            const now = getTimeString();
            if (err) {
                log.add(`{red-fg}✖ Failed to capture/send image{/red-fg}`);
                log.add(stderr);
            } else {
                log.add(`{gray-fg}[${now}]{/gray-fg} {green-fg}⇢ you:{/green-fg} sent an ASCII image`);
                if (stdout && stdout.trim()) {
                    log.add(stdout.trim());
                }
                log.add('{green-fg}✓ ASCII image captured and sent{/green-fg}');
            }
            screen.render();
        });

        input.clearValue();
        input.focus();
        return;
    }

    const now = getTimeString();
    const msg = {
        from: MY_NAME,
        to: FRIEND_NAME,
        text: text.trim(),
        time: now,
    };

    client.publish(PUB_TOPIC, JSON.stringify(msg));
    log.add(`{gray-fg}[${now}]{/gray-fg} {green-fg}⇢ you:{/green-fg} ${msg.text}`);
    input.clearValue();
    input.focus();
    screen.render();
});

// ==== QUIT ==== -- this doesn't work
screen.key(['q', 'C-c'], () => {
    clearInterval(heartbeatTimer);
    client.publish(MY_PRESENCE_TOPIC, 'offline', { retain: true, qos: 1 }, () => {
        client.end();
        process.exit(0);
    });
});

// ==== PRESENCE UI ====
function updateStatus(status) {
    // log.add(`(presence update from topic: ${PRESENCE_TOPIC} → "${status.trim()}")`);

    const wasOnline = isOnline;

    isOnline = status.trim() === 'online';
    log.setLabel(` ⸜(｡˃ ᵕ ˂ )⸝ chat with ${FRIEND_NAME} `);

    const symbol = isOnline ? '♥︎' : '♡';
    presenceBox.setContent(` ${symbol} {bold}${FRIEND_NAME}{/bold} is ${isOnline ? 'online' : 'offline'}    ♥︎ {bold}${MY_NAME}{/bold} is online`);
    if (isOnline && !wasOnline) {
        process.stdout.write('\x07'); // play bell sound when friend comes online
    }
    screen.render(); // force full UI redraw
}
