#!/usr/bin/env python3
import time
import sys
import RPi.GPIO as GPIO

class ServoController:
    def __init__(self, pin):
        """
        Initialize a servo controller using RPi.GPIO, or in our case rpi-lgpio since it's a RPi5.
        
        Args:
            pin: GPIO pin number (BCM numbering)
        """
        self.pin = pin
        self.pwm = None
        
        # Set up GPIO
        GPIO.setwarnings(False)  # Disable warnings
        GPIO.setmode(GPIO.BCM)   # Use BCM pin numbering
        GPIO.setup(self.pin, GPIO.OUT)
        
        # Initialize PWM on the pin with 50Hz frequency (standard for servos)
        self.pwm = GPIO.PWM(self.pin, 50)
        
        # Start PWM with 0% duty cycle
        self.pwm.start(0)
        
        print(f"Initialized servo on GPIO pin {pin}")
    
    def set_angle(self, angle):
        """
        Set servo angle (0-180 degrees).
        
        Args:
            angle: Angle in degrees (0-180)
        """
        if angle < 0 or angle > 180:
            raise ValueError("Angle must be between 0 and 180 degrees")
        
        # Convert angle to duty cycle
        # For most servos, 2.5% duty cycle = 0 degrees, 12.5% duty cycle = 180 degrees
        duty_cycle = 2.5 + (angle / 180.0) * 10.0
        
        # Set duty cycle
        self.pwm.ChangeDutyCycle(duty_cycle)
        
        return duty_cycle
    
    def cleanup(self):
        """Release GPIO resources."""
        if self.pwm:
            self.pwm.stop()
            # Clean up only this specific pin to avoid interfering with automationhat
            GPIO.cleanup(self.pin)
            self.pwm = None
            print(f"Cleaned up GPIO pin {self.pin}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 servo.py <GPIO_PIN> <ANGLE>")
        print("Example: python3 servo.py 14 90")
        sys.exit(1)

    try:
        gpio_pin = int(sys.argv[1])
        angle = int(sys.argv[2])
        
        if angle < 0 or angle > 180:
            print("Error: Angle must be between 0 and 180")
            sys.exit(1)

        # Initialize servo controller
        servo = ServoController(gpio_pin)
        
        print(f"GPIO Pin: {gpio_pin}")
        print(f"Angle: {angle}")
        
        # Set servo angle
        duty_cycle = servo.set_angle(angle)
        print(f"Duty Cycle: {duty_cycle}%")
        
        # Keep the servo at the specified angle for a short time
        time.sleep(1)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Cleanup
        if 'servo' in locals():
            servo.cleanup() 