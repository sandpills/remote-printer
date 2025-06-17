import cv2
from PIL import Image
import numpy as np
import os
from datetime import datetime

CAPTURE_DIR = "captures"
os.makedirs(CAPTURE_DIR, exist_ok=True)

# ASCII_CHARS = "@%#*+=-:. "
ASCII_CHARS = "█▓▒░:. "


def image_to_ascii(image_path, size=(40, 40), output_path=None):
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

    if output_path:
        with open(output_path, 'w') as f:
            f.write(ascii_img)

    return ascii_img

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

    # Filename based on timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    image_path = os.path.join(CAPTURE_DIR, f'webcam_{timestamp}.jpg')
    cv2.imwrite(image_path, frame)
    return True, image_path

if __name__ == '__main__':
    success, result = capture_image()
    if success:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        ascii_path = os.path.join(CAPTURE_DIR, f'ascii_{timestamp}.txt')
        ascii_art = image_to_ascii(result, output_path=ascii_path)
        print(ascii_art)
        print(f"\n✓ ASCII saved to {ascii_path}")
    else:
        print("❌", result)


