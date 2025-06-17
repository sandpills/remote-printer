import cv2
from PIL import Image
import numpy as np
import os
from datetime import datetime
import paho.mqtt.publish as publish
import sys

# ========= CONFIG =========
BROKER = "test.mosquitto.org"
SIZE = (60, 30)  # Wider and shorter for better aspect ratio
CAPTURE_DIR = "captures"
ASCII_CHARS = "█▓▒@%#*+=-:. "

os.makedirs(CAPTURE_DIR, exist_ok=True)

# ========= FUNCTIONS =========

def capture_image():
    # Try to use the default camera first
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        # If default camera fails, try to find any available camera
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                break
        if not cap.isOpened():
            return False, "No camera available."

    # Set camera properties for better quality
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)  # Enable auto exposure
    cap.set(cv2.CAP_PROP_EXPOSURE, -6)  # Set exposure (adjust this value if needed)
    cap.set(cv2.CAP_PROP_GAIN, 1.0)  # Set gain

    # Read multiple frames to let the camera adjust
    for _ in range(5):
        cap.read()

    ret, frame = cap.read()
    cap.release()

    if not ret:
        return False, "Failed to capture image."

    # Apply some basic image processing
    frame = cv2.convertScaleAbs(frame, alpha=1.2, beta=10)  # Increase contrast and brightness

    # Crop to center square for saving
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
    pixels = (pixels - pixels.min()) / (pixels.ptp() + 1e-5)
    pixels = (pixels * 255).astype(np.uint8)
    img = Image.fromarray(pixels)
    ascii_img = ""
    for row in np.array(img):
        for pixel in row:
            ascii_img += ASCII_CHARS[pixel * len(ASCII_CHARS) // 256]
        ascii_img += "\n"

    return ascii_img

# ========= MAIN =========

if __name__ == '__main__':
    # Get sender and recipient from command line arguments
    if len(sys.argv) != 3:
        print("Usage: python3 ascii-cam-sender.py <sender> <recipient>")
        print("Example: python3 ascii-cam-sender.py nyc-boshi shanghai-cedar")
        sys.exit(1)

    SENDER = sys.argv[1]
    RECIPIENT = sys.argv[2]
    TOPIC = f"ascii/{RECIPIENT}"

    success, result = capture_image()
    if not success:
        print("❌", result)
        exit()

    ascii_art = image_to_ascii(result)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Embed metadata
    payload = f"[ascii image from {SENDER} @ {timestamp}]\n{ascii_art}"

    # Save to local file
    ascii_path = os.path.join(CAPTURE_DIR, f"ascii_{SENDER}_{timestamp.replace(' ', '_').replace(':','-')}.txt")
    with open(ascii_path, 'w') as f:
        f.write(payload)

    # Publish over MQTT
    publish.single(
        TOPIC,
        payload=payload,
        hostname=BROKER,
        qos=1,
        retain=False
    )

    print(f"✓ ASCII image sent to topic: {TOPIC}")
    print(f"✓ ASCII saved to: {ascii_path}")
