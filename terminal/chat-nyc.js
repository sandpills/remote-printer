const mqtt = require('mqtt');
const blessed = require('blessed');
const { spawn } = require('child_process');

// ==== TERMINAL PALETTE & SYMBOLS ====
const isBasicTerminal = ['linux', 'xterm', 'vt100'].includes(process.env.TERM);
const palette = {
    online: 'green-fg',
    offline: 'magenta-fg',
    info: isBasicTerminal ? 'yellow-fg' : 'grey-fg',
    warning: 'magenta-fg',
    error: 'magenta-fg',
    self: isBasicTerminal ? 'white-fg' : 'cyan-fg'
};
const symbols = {
    online: isBasicTerminal ? ':)' : '♥︎',
    offline: isBasicTerminal ? ':(' : '♡',
    printerOn: isBasicTerminal ? '[P]' : '✓',
    printerOff: isBasicTerminal ? '[ ]' : '✘',
    kaomoji: isBasicTerminal ? '(//> w <//)!' : '⸜(｡> ᵕ < )⸝',
    arrowTo: isBasicTerminal ? '->' : '⇢',
    arrowFrom: isBasicTerminal ? '<-' : '⇠',
    check: isBasicTerminal ? '[OK]' : '✓',
    cross: isBasicTerminal ? '[X]' : '✖',
    star: isBasicTerminal ? '*' : '✶'
};

// ==== CONFIG ====
const MY_NAME = 'nyc-boshi';              // ← your device name
const FRIEND_NAME = 'shanghai-cedar';     // ← other party
const BROKER_URL = 'mqtt://test.mosquitto.org';
const SUB_TOPIC = `messages/${MY_NAME}`;
const PUB_TOPIC = `messages/${FRIEND_NAME}`;
const PRESENCE_TOPIC = `presence/${FRIEND_NAME}`;
const MY_PRESENCE_TOPIC = `presence/${MY_NAME}`;
const ASCII_RECEIEVE = `ascii/${MY_NAME}`;

const HEARTBEAT_INTERVAL = 5000; // 5 seconds
const PRESENCE_TIMEOUT = 10000; // 10 seconds
let heartbeatTimer = null;
let presenceTimeout = null;

// ==== PRINTER STATE ====
let printerEnabled = false;
let printerProcess = null;

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
    label: ' Type message to send | /p: take photo | /help: help ',
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
    log.add('{green-fg}✓ Connected to MQTT{/}');
    client.subscribe([SUB_TOPIC, PRESENCE_TOPIC, ASCII_RECEIEVE], () => {
        screen.render();
    });

    // Heartbeat presence
    function sendHeartbeat() {
        client.publish(MY_PRESENCE_TOPIC, 'online', { retain: true });
    }
    heartbeatTimer = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL);
    sendHeartbeat(); // send immediately

    const selfStatus = `{${palette.self}}${symbols.online} ${MY_NAME} is online{/}`;
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
        log.add(`{${palette.info}}[${now}] ⇠ ${FRIEND_NAME}: sent an ASCII image{/}`);
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
        const nameColor = isMe ? palette.self : palette.friend;
        const arrow = isMe ? symbols.arrowTo + ' you:' : `${symbols.arrowFrom} ${data.from}:`;
        log.add(`{${palette.info}}[${ts}]{/} {${nameColor}}${arrow}{/} ${data.text}`);
    } catch (err) {
        log.add(`{${palette.error}}✖ Invalid message: ${msg}{/}`);
    }

    screen.render();
});

client.on('error', (err) => {
    log.add(`{${palette.error}}✖ MQTT error: ${err.message}{/}`);
    screen.render();
});

// ==== SENDING ====
input.on('submit', (text) => {
    const trimmed = text.trim().toLowerCase();

    // to quit
    if (trimmed === '/exit') {
        cleanupPrinter();
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
            log.add(`{${palette.error}}✖ Cannot send image: friend is offline{/}`);
            screen.render();
            input.clearValue();
            input.focus();
            return;
        }

        log.add(`{${palette.warning}}Capturing ASCII image...{/}`);
        screen.render();

        const { exec } = require('child_process');
        exec(`python3 terminal/ascii-cam-sender.py ${MY_NAME} ${FRIEND_NAME}`, (err, stdout, stderr) => {
            const now = getTimeString();
            if (err) {
                log.add(`{${palette.error}}✖ Failed to capture/send image{/}`);
                log.add(stderr);
            } else {
                log.add(`{${palette.info}}[${now}] ⇢ you: sent an ASCII image{/}`);
                if (stdout && stdout.trim()) {
                    log.add(stdout.trim());
                }
                log.add(`{${palette.online}}${symbols.check} ASCII image captured and sent{/}`);
            }
            screen.render();
        });

        input.clearValue();
        input.focus();
        return;
    }

    // to toggle printer
    if (trimmed === '/printer') {
        if (printerProcess) {
            // If portal is running, stop it
            cleanupPrinter();
            printerEnabled = false;
        } else {
            // If portal is not running, start it
            startPrinterPortal();
            printerEnabled = true;
        }
        input.clearValue();
        input.focus();
        return;
    }

    // to check printer status
    if (trimmed === '/status') {
        const printerStatus = printerEnabled ? 'on' : 'off';
        log.add(`{${palette.info}}✶ Printer status: ${printerStatus}{/}`);
        screen.render();
        input.clearValue();
        input.focus();
        return;
    }

    // to show help
    if (trimmed === '/help') {
        log.add(`{${palette.info}}${symbols.star} Available Commands:{/}`);
        log.add(`  /p - Take and send photo`);
        log.add(`  /printer - Toggle printer on/off`);
        log.add(`  /status - Check printer status`);
        log.add(`  /help - Show this help message`);
        log.add(`  /exit - Quit the application`);
        screen.render();
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
    log.add(`{${palette.self}}[${now}] ⇢ you: ${msg.text}{/}`);
    input.clearValue();
    input.focus();
    screen.render();
});

// ==== QUIT ==== -- this doesn't work
screen.key(['q', 'C-c'], () => {
    cleanupPrinter();
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
    log.setLabel(`q(//> w <//)p chat with ${FRIEND_NAME} `);

    const symbol = isOnline ? symbols.online : symbols.offline;
    const printerSymbol = printerEnabled ? symbols.printerOn : symbols.printerOff;
    const myStatus = isOnline ? symbols.online : symbols.offline;
    const friendStatus = isOnline ? symbols.online : symbols.offline;
    presenceBox.setContent(
        ` ${friendStatus} {bold}${FRIEND_NAME}{/bold} is ${isOnline ? 'online' : 'offline'}  ${printerSymbol} printer ${printerEnabled ? 'on' : 'off'}`
    );
    if (isOnline && !wasOnline) {
        process.stdout.write('\x07'); // play bell sound when friend comes online
    }
    screen.render(); // force full UI redraw
}

// ==== PRINTER FUNCTIONS ====
function startPrinterPortal() {
    if (printerProcess) {
        log.add(`{${palette.error}}✖ Printer portal already running{/}`);
        screen.render();
        return;
    }

    log.add(`{${palette.warning}}⇣ Starting printer portal...{/}`);
    screen.render();

    // Start the printer portal as a background process
    printerProcess = spawn('python3', ['nyc-printer-portal.py'], {
        stdio: ['pipe', 'pipe', 'pipe'],
        detached: false
    });

    printerProcess.stdout.on('data', (data) => {
        const output = data.toString().trim();
        if (output) {
            log.add(`{${palette.info}}[Printer] ${output}{/}`);
            screen.render();
        }
    });

    printerProcess.stderr.on('data', (data) => {
        const error = data.toString().trim();
        if (error) {
            log.add(`{${palette.error}}[Printer Error] ${error}{/}`);
            screen.render();
        }
    });

    printerProcess.on('close', (code) => {
        log.add(`{${palette.warning}}⇣ Printer portal stopped (code: ${code}){/}`);
        printerProcess = null;
        printerEnabled = false;
        updateStatus(isOnline ? 'online' : 'offline'); // refresh display
        screen.render();
    });

    printerProcess.on('error', (err) => {
        log.add(`{${palette.error}}✖ Printer portal error: ${err.message}{/}`);
        printerProcess = null;
        printerEnabled = false;
        updateStatus(isOnline ? 'online' : 'offline'); // refresh display
        screen.render();
    });

    // Set printer as enabled when portal starts
    printerEnabled = true;
    updateStatus(isOnline ? 'online' : 'offline'); // refresh display
}

function cleanupPrinter() {
    if (printerProcess) {
        log.add(`{${palette.warning}}⌁ Stopping printer portal...{/}`);
        printerProcess.kill('SIGTERM');
        printerProcess = null;
        printerEnabled = false;
        updateStatus(isOnline ? 'online' : 'offline'); // refresh display
    }
}
