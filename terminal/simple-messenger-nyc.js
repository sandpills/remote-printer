// sends and receives messages via MQTT

const mqtt = require('mqtt');
const readline = require('readline');

// Create interface for typing messages
const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
});

// Connect to free test broker (no password needed!)
console.log('Connecting to MQTT broker...');
const client = mqtt.connect('mqtt://test.mosquitto.org');

// Your "address" - change this to something unique!
const MY_NAME = 'nyc-boshi';  // Change this!
const FRIEND_NAME = 'shanghai-cedar';  // Your friend changes this!

// When connected
client.on('connect', () => {
    console.log('✓ Connected to MQTT broker!');
    console.log(`✓ Your address: ${MY_NAME}`);
    console.log(`✓ Sending to: ${FRIEND_NAME}`);
    console.log('');
    console.log('Type a message and press Enter to send:');
    console.log('(Type "exit" to quit)');
    console.log('=====================================');

    // Subscribe to messages FOR YOU
    client.subscribe(`messages/${MY_NAME}`);
});

// When you receive a message
client.on('message', (topic, message) => {
    console.log('\n📨 NEW MESSAGE:');
    console.log(message.toString());
    console.log('=====================================');
});

// Function to send a message
function sendMessage(text) {
    const message = {
        from: MY_NAME,
        to: FRIEND_NAME,
        text: text,
        time: new Date().toLocaleString()
    };

    // Send to your friend's "mailbox"
    client.publish(
        `messages/${FRIEND_NAME}`,
        JSON.stringify(message)
    );

    console.log('✓ Message sent!');
}

// Handle typing
rl.on('line', (input) => {
    if (input.toLowerCase() === 'exit') {
        console.log('Goodbye!');
        process.exit(0);
    }

    sendMessage(input);
});

// Handle errors
client.on('error', (err) => {
    console.error('Connection error:', err);
});