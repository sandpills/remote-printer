## Portal project for shanghai(cedar kitchen) <> nyc(boshi's) game exchange

A slower-internet, long-distance, terminal-based messaging system

Currently 2 seperate builds >.<
- /terminal is the perferred version
- /web has a webUI and uses a socket.io server instead of MQTT, made just for testing


## Requirements
- Node.js (v16+)
- Python 3
- Webcam (USB or built-in)
- Terminal-friendly computer
- (Yet to be deployed: thermal printer, Raspberry Pi)

## Installation

```bash
# Clone the repo
git clone https://github.com/sandpills/remote-printer.git
cd remote-printer

# Install Node.js dependencies
npm install

# Install Python dependencies
pip install opencv-python pillow numpy paho-mqtt
```

## Running the chat
```bash
# Start the NYC side:
node terminal/chat-nyc.js

# Start the Shanghai side:
node terminal/chat-sh.js
```

- Type to chat, enter to send
- Type and send "exit" to quit
- Type and send "/p" to capture an image and send over to the other side as ASCII (only available when both are online)