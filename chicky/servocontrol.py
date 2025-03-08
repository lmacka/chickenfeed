#!/usr/bin/python3
import sys
import time
from lib.pi5RC import pi5RC

# Function to convert angle to PWM pulse width in microseconds
def angle_to_pulsewidth(angle):
    min_pulsewidth = 500  # Corresponds to 0.5ms pulse (0 degrees)
    max_pulsewidth = 2500  # Corresponds to 2.5ms pulse (180 degrees)
    return int(min_pulsewidth + (angle / 180.0) * (max_pulsewidth - min_pulsewidth))

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 servocontrol.py <GPIO_PIN> <ANGLE>")
        sys.exit(1)

    gpio_pin = int(sys.argv[1])
    angle = int(sys.argv[2])

    if angle < 0 or angle > 180:
        print("Error: Angle must be between 0 and 180")
        sys.exit(1)

    # Initialize pi5RC
    servo = pi5RC(gpio_pin)

    pulsewidth = angle_to_pulsewidth(angle)

    print(f"GPIO Pin: {gpio_pin}")
    print(f"Angle: {angle}")
    print(f"Pulse Width: {pulsewidth} µs")

    try:
        # Set servo pulse width
        servo.set(pulsewidth)

        # Keep the servo at the specified angle for a short time
        time.sleep(1)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Cleanup
        del servo