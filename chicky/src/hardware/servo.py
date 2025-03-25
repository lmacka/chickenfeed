#!/usr/bin/env python3
"""
Servo controller for treat dispensing
"""
import time
import sys
import RPi.GPIO as GPIO
import logging
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ServoController:
    """Servo controller for treat dispenser"""
    
    _instance: Optional['ServoController'] = None
    _initialized: bool = False
    
    def __new__(cls, pin: Optional[int] = None):
        if cls._instance is None and pin is not None:
            cls._instance = super().__new__(cls)
            cls._instance.pin = pin
            cls._instance._initialized = False
        return cls._instance
    
    def __enter__(self):
        """Context manager entry"""
        if not self._initialized:
            self.initialize()
            self._initialized = True
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if exc_type is not None:
            # Force cleanup on error
            self.cleanup()
            self._initialized = False
    
    def initialize(self) -> None:
        """Initialize GPIO and PWM"""
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.OUT)
        self.pwm = GPIO.PWM(self.pin, 50)
        self.pwm.start(0)
        logger.debug(f"Initialized servo on GPIO pin {self.pin}")
    
    def set_angle(self, angle: int) -> float:
        """
        Set servo angle (0-180 degrees).
        
        Args:
            angle: Angle in degrees (0-180)
                
        Returns:
            float: The duty cycle used
                
        Raises:
            ValueError: If angle is outside valid range
        """
        if not 0 <= angle <= 180:
            raise ValueError("Angle must be between 0 and 180 degrees")
        
        # Convert angle to duty cycle
        # For most servos, 2.5% duty cycle = 0 degrees, 12.5% duty cycle = 180 degrees
        duty_cycle = 2.5 + (angle / 180.0) * 10.0
        
        # Set duty cycle
        self.pwm.ChangeDutyCycle(duty_cycle)
        logger.debug(f"Set servo to {angle}° (duty cycle: {duty_cycle}%)")
        
        return duty_cycle
    
    def cleanup(self) -> None:
        """Release GPIO resources"""
        if hasattr(self, 'pwm'):
            self.pwm.stop()
            delattr(self, 'pwm')  # Remove PWM instance
        GPIO.cleanup(self.pin)  # Clean up only this pin
        self._initialized = False
        logger.debug(f"Cleaned up GPIO pin {self.pin}")

def setup_servo(pin: int) -> GPIO.PWM:
    """Initialize GPIO and PWM (for direct script usage)"""
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(pin, GPIO.OUT)
    pwm = GPIO.PWM(pin, 50)
    pwm.start(0)
    logger.info(f"Initialized servo on GPIO pin {pin}")
    return pwm

def set_angle(pwm: GPIO.PWM, angle: int) -> float:
    """
    Set servo angle (0-180 degrees) (for direct script usage).
    
    Args:
        pwm: PWM instance
        angle: Angle in degrees (0-180)
            
    Returns:
        float: The duty cycle used
            
    Raises:
        ValueError: If angle is outside valid range
    """
    if not 0 <= angle <= 180:
        raise ValueError("Angle must be between 0 and 180 degrees")
    
    # Convert angle to duty cycle
    # For most servos, 2.5% duty cycle = 0 degrees, 12.5% duty cycle = 180 degrees
    duty_cycle = 2.5 + (angle / 180.0) * 10.0
    
    # Set duty cycle
    pwm.ChangeDutyCycle(duty_cycle)
    logger.debug(f"Set servo to {angle}° (duty cycle: {duty_cycle}%)")
    
    return duty_cycle

def cleanup_servo(pwm: GPIO.PWM) -> None:
    """Clean up servo resources (for direct script usage)"""
    pwm.stop()
    GPIO.cleanup()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 servo.py <GPIO_PIN> <ANGLE>")
        sys.exit(1)
    
    try:
        pin = int(sys.argv[1])
        angle = int(sys.argv[2])
        
        pwm = setup_servo(pin)
        duty_cycle = set_angle(pwm, angle)
        print(f"Set to {angle}° (duty cycle: {duty_cycle}%)")
        
        time.sleep(1)
        cleanup_servo(pwm)
    except Exception as e:
        print(f"Error: {e}")
        if 'pwm' in locals():
            cleanup_servo(pwm)
        sys.exit(1) 