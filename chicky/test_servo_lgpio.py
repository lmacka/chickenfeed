#!/usr/bin/python3
import sys
import time
from lib.pi5RC_lgpio import pi5RC_lgpio

def test_servo(pin, angle):
    """Test a servo by moving it to the specified angle"""
    print(f"Testing servo on GPIO pin {pin}")
    print(f"Setting to angle {angle}°")
    
    # Initialize the servo
    servo = pi5RC_lgpio(pin)
    
    # Calculate pulse width
    min_pw = 500   # 0.5ms for 0 degrees
    max_pw = 2500  # 2.5ms for 180 degrees
    pulse_width = int(min_pw + (angle / 180.0) * (max_pw - min_pw))
    
    print(f"Pulse width: {pulse_width}µs")
    
    # Set the servo position
    servo.set(pulse_width)
    
    # Wait for 1 second
    time.sleep(1)
    
    # Clean up
    del servo
    
    print("Test complete")

def sweep_servo(pin):
    """Test a servo by sweeping it from 0 to 180 degrees and back"""
    print(f"Sweeping servo on GPIO pin {pin}")
    
    # Initialize the servo
    servo = pi5RC_lgpio(pin)
    
    # Sweep from 0 to 180 degrees
    for angle in range(0, 181, 45):
        pulse_width = int(500 + (angle / 180.0) * 2000)
        print(f"Setting to angle {angle}° (pulse width: {pulse_width}µs)")
        servo.set(pulse_width)
        time.sleep(0.5)
    
    # Sweep from 180 to 0 degrees
    for angle in range(180, -1, -45):
        pulse_width = int(500 + (angle / 180.0) * 2000)
        print(f"Setting to angle {angle}° (pulse width: {pulse_width}µs)")
        servo.set(pulse_width)
        time.sleep(0.5)
    
    # Clean up
    del servo
    
    print("Sweep complete")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 test_servo_lgpio.py <GPIO_PIN> [ANGLE]")
        print("  GPIO_PIN: The GPIO pin number (e.g., 14 or 15)")
        print("  ANGLE: Angle between 0 and 180 degrees (optional, defaults to sweep)")
        sys.exit(1)
    
    pin = int(sys.argv[1])
    
    if len(sys.argv) >= 3:
        angle = int(sys.argv[2])
        if angle < 0 or angle > 180:
            print("Error: Angle must be between 0 and 180")
            sys.exit(1)
        test_servo(pin, angle)
    else:
        sweep_servo(pin) 