#!/usr/bin/env python3
import logging
import time

import RPi.GPIO as GPIO

logger = logging.getLogger(__name__)

class ServoController:
    def __init__(self, pin=14):
        """
        Initialize a servo controller using RPi.GPIO
        
        Args:
            pin: GPIO pin number (BCM numbering), default 14
        """
        self.pin = pin
        self.pwm = None
        self.last_dispense = 0
        self.dispense_cooldown = 5  # seconds between dispenses
        
        try:
            # Set up GPIO
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.OUT)
            
            # Initialize PWM on the pin with 50Hz frequency
            self.pwm = GPIO.PWM(self.pin, 50)
            self.pwm.start(0)
            
            logger.info(f"Initialized servo on GPIO pin {pin}")
        except Exception as e:
            logger.error(f"Failed to initialize servo on pin {pin}: {e}")
            self.cleanup()
            raise
    
    def set_angle(self, angle):
        """Set servo angle (0-180 degrees)"""
        try:
            if angle < 0 or angle > 180:
                raise ValueError("Angle must be between 0 and 180 degrees")
            
            # Convert angle to duty cycle
            duty_cycle = 2.5 + (angle / 180.0) * 10.0
            
            # Set duty cycle
            self.pwm.ChangeDutyCycle(duty_cycle)
            
            logger.info(f"Servo set to angle {angle} (duty cycle: {duty_cycle}%)")
            return duty_cycle
        except Exception as e:
            logger.error(f"Error setting servo angle: {e}")
            raise
    
    def dispense_treat(self):
        """Dispense a treat by rotating the servo"""
        current_time = time.time()
        
        # Check cooldown
        if current_time - self.last_dispense < self.dispense_cooldown:
            remaining = self.dispense_cooldown - (current_time - self.last_dispense)
            raise Exception(f"Please wait {remaining:.1f} seconds before dispensing again")
        
        try:
            # Rotate to dispense position
            self.set_angle(0)
            time.sleep(0.5)
            
            # Rotate to release treats
            self.set_angle(90)
            time.sleep(0.5)
            
            # Return to home position
            self.set_angle(0)
            time.sleep(0.5)
            
            # Stop sending PWM signal
            self.pwm.ChangeDutyCycle(0)
            
            self.last_dispense = current_time
            logger.info("Treat dispensed successfully")
        except Exception as e:
            logger.error(f"Error dispensing treat: {e}")
            raise
    
    def cleanup(self):
        """Release GPIO resources"""
        try:
            if self.pwm:
                self.pwm.stop()
                GPIO.cleanup(self.pin)
                self.pwm = None
                logger.info(f"Cleaned up GPIO pin {self.pin}")
        except Exception as e:
            logger.error(f"Error cleaning up servo: {e}")