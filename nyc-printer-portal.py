#!/usr/bin/env python3
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
import paho.mqtt.client as mqtt
import json
import subprocess
import threading
import base64
import tempfile
import os
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from paho.mqtt.client import CallbackAPIVersion

# ========= CONFIG =========
MY_NAME = 'nyc-boshi'
FRIEND_NAME = 'shanghai-cedar'
BROKER = "test.mosquitto.org"
PRINTER_NAME = 'ITPBigPrinter'

# Topics
MESSAGE_TOPIC = f"messages/{MY_NAME}"
ASCII_TOPIC = f"ascii/{MY_NAME}"
IMAGE_TOPIC = f"images/{MY_NAME}"
PRESENCE_TOPIC = f"presence/{FRIEND_NAME}"
MY_PRESENCE_TOPIC = f"presence/{MY_NAME}"

HEARTBEAT_INTERVAL = 5  # seconds

class PrinterPortal:
    def __init__(self):
        self.client = mqtt.Client(protocol=mqtt.MQTTv311)
        self.is_online = False
        
        # Setup MQTT callbacks
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        print("🖨️  NYC Printer Portal Starting...")
        
    def print_to_hp(self, content):
        """Print text content to HP printer"""
        try:
            process = subprocess.Popen(
                ['lp', '-d', PRINTER_NAME],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout, stderr = process.communicate(input=content)
            
            if process.returncode == 0:
                print("✓ Printed successfully")
                return True
            else:
                print(f"✗ Print failed: {stderr}")
                return False
                
        except Exception as e:
            print(f"✗ Print error: {e}")
            return False
    
    def format_text_message(self, sender, text, timestamp):
        """Format text message for printing"""
        return f"""
{'='*50}
MESSAGE FROM: {sender}
Time: {timestamp}
{'='*50}

{text}

{'='*50}

"""
    
    def on_connect(self, client, userdata, flags, rc):
        """Callback for when client connects to MQTT broker"""
        if rc == 0:
            print("✓ Connected to MQTT broker")
            
            # Subscribe to topics
            topics = [MESSAGE_TOPIC, ASCII_TOPIC, IMAGE_TOPIC, PRESENCE_TOPIC]
            for topic in topics:
                client.subscribe(topic)
                print(f"✓ Subscribed to: {topic}")
            
            # Send presence and start heartbeat
            client.publish(MY_PRESENCE_TOPIC, "online", retain=True)
            self.start_heartbeat()
            self.print_startup_message()
            
        else:
            print(f"✗ Failed to connect to MQTT: {rc}")
    
    def on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages"""
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if topic == PRESENCE_TOPIC:
            self.handle_presence(payload.strip())
            return  # Don't show presence messages in console
            
        # Only show non-presence messages in console
        print(f"\n[{timestamp}] Received on {topic.split('/')[-1]}")
        
        if topic == MESSAGE_TOPIC:
            self.handle_text_message(payload, timestamp)
            
        elif topic == ASCII_TOPIC:
            print("📺 ASCII art received (terminal display only)")
            # ASCII is just for terminal - we'll get the real image separately
            
        elif topic == IMAGE_TOPIC:
            self.handle_image_message(payload, timestamp)
    
    def handle_presence(self, status):
        """Handle friend's presence updates (silently)"""
        was_online = self.is_online
        self.is_online = (status == 'online')
        # No console output, no printing - just track status silently
    
    def handle_text_message(self, payload, timestamp):
        """Handle text messages"""
        try:
            data = json.loads(payload)
            sender = data.get('from', 'Unknown')
            text = data.get('text', '')
            msg_time = data.get('time', timestamp)
            
            print(f"💬 Message from {sender}: {text}")
            
            formatted_msg = self.format_text_message(sender, text, msg_time)
            self.print_to_hp(formatted_msg)
            
        except json.JSONDecodeError:
            print(f"✗ Invalid message format: {payload}")
    
    def handle_image_message(self, payload, timestamp):
        """Handle actual image files - create combined image with text header"""
        try:
            data = json.loads(payload)
            sender = data.get('from', 'Unknown')
            filename = data.get('filename', 'image.jpg')
            image_data = data.get('data', '')
            msg_time = data.get('timestamp', timestamp)
            
            print(f"🖼️ High-res image from {sender}: {filename}")
            
            # Decode base64 image
            image_bytes = base64.b64decode(image_data)
            
            # Save original image to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                temp_file.write(image_bytes)
                original_path = temp_file.name
            
            # Create combined image with text header + photo
            combined_path = self.create_combined_image(sender, original_path, filename, msg_time)
            
            if combined_path:  # Only print if image creation succeeded
                # Print the combined image as one job
                process = subprocess.run([
                    'lp', '-d', PRINTER_NAME, 
                    '-o', 'fit-to-page',
                    combined_path
                ], capture_output=True, text=True)
                
                if process.returncode == 0:
                    print("✓ Combined image printed successfully")
                else:
                    print(f"✗ Image print failed: {process.stderr}")
                
                # Clean up combined image
                if os.path.exists(combined_path):
                    os.unlink(combined_path)
            
            # Clean up original image
            if os.path.exists(original_path):
                os.unlink(original_path)
                
        except Exception as e:
            print(f"✗ Failed to handle image: {e}")
    
    def create_combined_image(self, sender, image_path, filename, timestamp):
        """Create one image with text header + photo"""
        try:
            # Open the original image
            photo = Image.open(image_path)
            
            # Resize photo to fit nicely on paper (not too big)
            max_width = 400
            if photo.width > max_width:
                ratio = max_width / photo.width
                new_height = int(photo.height * ratio)
                photo = photo.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
            # Create header text area
            header_height = 100
            combined_width = max(photo.width, 400)
            combined_height = header_height + photo.height + 50  # padding
            
            # Create combined image (white background)
            combined = Image.new('RGB', (combined_width, combined_height), 'white')
            
            # Draw header text
            draw = ImageDraw.Draw(combined)
            
            try:
                # Try to use a decent font
                font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 16)
                small_font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 12)
            except:
                # Fallback to default font
                font = ImageFont.load_default()
                small_font = ImageFont.load_default()
            
            # Draw header text (no emojis to avoid encoding issues)
            header_text = f"IMAGE FROM: {sender}"
            time_text = f"Time: {timestamp}"
            
            draw.text((10, 10), "="*50, fill='black', font=small_font)
            draw.text((10, 30), header_text, fill='black', font=font)
            draw.text((10, 50), time_text, fill='black', font=small_font)
            draw.text((10, 70), "="*50, fill='black', font=small_font)
            
            # Paste the photo below the header
            photo_x = (combined_width - photo.width) // 2  # center the photo
            combined.paste(photo, (photo_x, header_height))
            
            # Save combined image
            combined_path = tempfile.mktemp(suffix='.jpg')
            combined.save(combined_path, 'JPEG', quality=85)
            
            return combined_path
            
        except Exception as e:
            print(f"✗ Error creating combined image: {e}")
            # Return None if failed
            return None
    
    def print_image_with_header(self, sender, image_path, filename, timestamp):
        """Print image with text header as single document using text overlay"""
        try:
            # Instead of printing separate files, create one combined document
            # We'll use lp with text concatenation
            
            header_text = f"""{'='*50}
📸 IMAGE FROM: {sender}
Time: {timestamp}
File: {filename}
{'='*50}

"""
            
            footer_text = f"""

{'='*50}
✓ Image received from {sender}
{'='*50}
"""
            
            # Create a single print job by piping everything together
            # Method: Use echo + cat + lp in one command
            combined_command = f"""
(echo '{header_text}'; 
 echo '[IMAGE PRINTED BELOW]'; 
 echo; 
 lp -d {PRINTER_NAME} -o fit-to-page '{image_path}' > /dev/null 2>&1; 
 echo '{footer_text}') | lp -d {PRINTER_NAME}
"""
            
            # Actually, let's try a simpler approach - just send text before image
            # Print just the header, then the image (minimal approach)
            
            simple_header = f"""{'='*50}
📸 IMAGE FROM: {sender}
Time: {timestamp}
{'='*50}

"""
            
            # Print header as text
            self.print_to_hp(simple_header)
            
            # Print image immediately after
            process = subprocess.run([
                'lp', '-d', PRINTER_NAME, 
                '-o', 'fit-to-page',
                image_path
            ], capture_output=True, text=True)
            
            if process.returncode == 0:
                print("✓ Image printed successfully")
            else:
                print(f"✗ Image print failed: {process.stderr}")
                
        except Exception as e:
            print(f"✗ Error printing image: {e}")
    
    def print_startup_message(self):
        """Print startup message"""
        startup_msg = f"""
{'='*50}
🖨️  NYC-BOSHI PRINTER PORTAL ONLINE
{'='*50}
Device: {MY_NAME}
Listening for: {FRIEND_NAME}
Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Printer: {PRINTER_NAME}

Ready to receive messages and images!
{'='*50}

"""
        self.print_to_hp(startup_msg)
    
    def start_heartbeat(self):
        """Start sending heartbeat presence"""
        def send_heartbeat():
            self.client.publish(MY_PRESENCE_TOPIC, "online", retain=True)
            timer = threading.Timer(HEARTBEAT_INTERVAL, send_heartbeat)
            timer.daemon = True
            timer.start()
        
        send_heartbeat()
    
    def run(self):
        """Start the printer portal"""
        try:
            print(f"🏠 Connecting to {BROKER}...")
            self.client.connect(BROKER, 1883, 60)
            
            print("🖨️  NYC Printer Portal started!")
            print(f"📍 Device: {MY_NAME}")
            print(f"👤 Listening for: {FRIEND_NAME}")
            print(f"🖨️  Printer: {PRINTER_NAME}")
            print("\nPress Ctrl+C to stop...")
            
            self.client.loop_forever()
            
        except KeyboardInterrupt:
            print("\nShutting down printer portal...")
            self.client.publish(MY_PRESENCE_TOPIC, "offline", retain=True)
            self.client.disconnect()
            
        except Exception as e:
            print(f"✗ Error: {e}")

if __name__ == "__main__":
    portal = PrinterPortal()
    portal.run()