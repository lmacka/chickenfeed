#!/usr/bin/python3
import sys
import time
from gpiozero import Servo
from gpiozero.pins.rpigpio import RPiGPIOFactory

# Usage function
def print_usage():
    print("Usage: python3 test_servo.py <GPIO_PIN> <ANGLE>")
    print("  GPIO_PIN: The GPIO pin number (e.g., 14 or 15)")
    print("  ANGLE: Angle between -90 and 90 degrees")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print_usage()
        sys.exit(1)
    
    try:
        gpio_pin = int(sys.argv[1])
        angle = float(sys.argv[2])
        
        # Convert angle from 0-180 to -1 to 1 (gpiozero uses -1 to 1 range)
        if angle < 0 or angle > 180:
            print("Error: Angle must be between 0 and 180 degrees")
            sys.exit(1)
            
        # Convert from 0-180 to -1 to 1
        value = (angle / 90.0) - 1
        
        print(f"Testing servo on GPIO pin {gpio_pin}")
        print(f"Setting to angle {angle}° (value: {value})")
        
        # Create a servo object
        servo = Servo(gpio_pin)
        
        # Set the servo position
        servo.value = value
        
        # Hold position for 2 seconds
        print("Holding position for 2 seconds...")
        time.sleep(2)
        
        # Cleanup
        servo.detach()
        print("Test complete")
        
    except ValueError:
        print("Error: Invalid pin number or angle value")
        print_usage()
    except Exception as e:
        print(f"Error: {e}") 