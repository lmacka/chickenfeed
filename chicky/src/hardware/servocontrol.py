#!/usr/bin/env python3
import sys
import time
from gpiozero import Servo
from gpiozero.pins.rpigpio import RPiGPIOFactory

# Function to convert angle from 0-180 to -1 to 1 (gpiozero range)
def angle_to_value(angle):
    if angle < 0 or angle > 180:
        raise ValueError("Angle must be between 0 and 180 degrees")
    return (angle / 90.0) - 1

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 servocontrol.py <GPIO_PIN> <ANGLE>")
        sys.exit(1)

    try:
        gpio_pin = int(sys.argv[1])
        angle = int(sys.argv[2])

        if angle < 0 or angle > 180:
            print("Error: Angle must be between 0 and 180")
            sys.exit(1)

        # Convert angle to gpiozero value (-1 to 1)
        value = angle_to_value(angle)

        print(f"GPIO Pin: {gpio_pin}")
        print(f"Angle: {angle}")
        print(f"Value: {value}")

        # Create a servo object
        servo = Servo(gpio_pin)
        
        # Set the servo position
        servo.value = value
        
        # Hold position for 1 second
        time.sleep(1)
        
        # Cleanup
        servo.detach()
        
    except ValueError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Error: {e}")
