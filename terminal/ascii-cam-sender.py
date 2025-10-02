import os
os.environ['OPENCV_LOG_LEVEL'] = 'ERROR'  # Suppress OpenCV warnings
import cv2
from PIL import Image
import numpy as np
from datetime import datetime
import paho.mqtt.publish as publish
import sys
import base64
import json

# ========= CONFIG =========
BROKER = "test.mosquitto.org"
SIZE = (80, 40)  # slightly bigger? lol
CAPTURE_DIR = "captures"
ASCII_CHARS = "█▓▒@%#*+=-:. "

os.makedirs(CAPTURE_DIR, exist_ok=True)

# ========= FUNCTIONS =========

def capture_image():
    print("attempting to access camera...", flush=True)
    
    # try to use the default camera first
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("default camera (0) failed, trying others...", flush=True)
        # if default camera fails, try to find any available camera
        for i in range(1, 5):  # Try cameras 1-4
            print(f"trying camera {i}...", flush=True)
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                break
        if not cap.isOpened():
            return False, "No camera available. Check camera permissions."

    # Set camera properties for better quality
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)  # enable auto exposure
    cap.set(cv2.CAP_PROP_EXPOSURE, -6)  # set exposure (adjust this value if needed)
    cap.set(cv2.CAP_PROP_GAIN, 1.0)  # set gain

    print("camera opened!", flush=True)

    ret, frame = cap.read()
    cap.release()

    if not ret:
        return False, "Failed to capture image from camera."

    # apply some basic image processing
    frame = cv2.convertScaleAbs(frame, alpha=1.2, beta=10)  # Increase contrast and brightness

    # crop to center square for saving
    height, width = frame.shape[:2]
    side = min(height, width)
    start_x = (width - side) // 2
    start_y = (height - side) // 2
    square_frame = frame[start_y:start_y+side, start_x:start_x+side]

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    image_path = os.path.join(CAPTURE_DIR, f'webcam_{timestamp}.jpg')
    cv2.imwrite(image_path, square_frame)
    return True, image_path

def image_to_ascii(image_path, size=SIZE):
    img = Image.open(image_path).convert('L')
    img = img.resize(size)

    # Enhanced brightness normalization
    pixels = np.asarray(img)
    # Apply gamma correction to brighten dark areas
    gamma = 1.5
    pixels = np.power(pixels / 255.0, 1/gamma) * 255.0
    # Normalize to full range
    pixels = (pixels - pixels.min()) / (np.ptp(pixels) + 1e-5)
    pixels = (pixels * 255).astype(np.uint32)
    img = Image.fromarray(pixels)
    ascii_img = ""
    for row in np.array(img):
        for pixel in row:
            ascii_img += ASCII_CHARS[pixel * len(ASCII_CHARS) // 256]
        ascii_img += "\n"

    return ascii_img

# ========= base64 decode =========

def image_to_base64(image_path):
    """Convert image file to base64 string"""
    with open(image_path, 'rb') as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
    return encoded_string

def send_dual_image(sender, recipient, image_path):
    """Send both ASCII (for terminal) and base64 image (for printer)"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Generate ASCII for terminal display
    ascii_art = image_to_ascii(image_path)
    
    # Convert image to base64 for printer
    image_base64 = image_to_base64(image_path)
    
    # Send ASCII version to terminal (existing topic)
    ascii_topic = f"ascii/{recipient}"
    ascii_payload = f"[ascii image from {sender} @ {timestamp}]\n{ascii_art}"
    
    publish.single(
        ascii_topic,
        payload=ascii_payload,
        hostname=BROKER,
        qos=1,
        retain=False
    )
    
    # Send actual image for printer (new topic)
    image_topic = f"images/{recipient}"
    image_payload = {
        "from": sender,
        "timestamp": timestamp,
        "filename": os.path.basename(image_path),
        "type": "image",
        "data": image_base64
    }
    
    publish.single(
        image_topic,
        payload=json.dumps(image_payload),
        hostname=BROKER,
        qos=1,
        retain=False
    )
    
    return ascii_art, len(image_base64)

# ========= MAIN =========

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python3 ascii-cam-sender-enhanced.py <sender> <recipient>")
        print("Example: python3 ascii-cam-sender-enhanced.py nyc-boshi shanghai-cedar")
        sys.exit(1)

    SENDER = sys.argv[1]
    RECIPIENT = sys.argv[2]

    success, result = capture_image()
    if not success:
        print("❌", result)
        exit()

    ascii_art, base64_size = send_dual_image(SENDER, RECIPIENT, result)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# Save locally
    ascii_path = os.path.join(CAPTURE_DIR, f"ascii_{SENDER}_{timestamp.replace(' ', '_').replace(':','-')}.txt")
    with open(ascii_path, 'w') as f:
        f.write(f"[ascii image from {SENDER} @ {timestamp}]\n{ascii_art}")

    # Output ASCII art to console (for sender to see)
    print(ascii_art)  # Display ASCII in sender's console
    
    # Status messages to stderr so they don't interfere with ASCII display
    print(f"\n✓ Dual image sent:", file=sys.stderr)
    print(f"  ASCII to: ascii/{RECIPIENT}", file=sys.stderr)
    print(f"  Image to: images/{RECIPIENT} ({base64_size} bytes)", file=sys.stderr)
    print(f"  Saved locally: {ascii_path}", file=sys.stderr)