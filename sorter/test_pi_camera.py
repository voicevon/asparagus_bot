from picamera2 import Picamera2
from time import sleep

# Create Picamera2 instance
cam = Picamera2()

# Preview configuration (optional)
# preview_config = cam.create_preview_configuration()
# cam.configure(preview_config)

cam.start()        # Initialize camera
cam.start_preview() # Start preview window

sleep(5)           # Keep preview for 5 seconds

# Cleanup resources
cam.stop_preview()
cam.stop()