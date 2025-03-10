#!/usr/bin/python3
# Servo control library for Raspberry Pi 5 using lgpio
import lgpio
import time

class pi5RC_lgpio:
    """
    Servo control class for Raspberry Pi 5 using lgpio
    This is a replacement for the pi5RC class that uses the lgpio library
    instead of the pinctrl command and PWM sysfs interface.
    """
    
    def __init__(self, pin):
        # Supported GPIO pins for servos
        self.supported_pins = [12, 13, 14, 15, 18, 19]
        
        if pin not in self.supported_pins:
            self.pin = None
            self.h = None
            print(f"Error: Invalid pin. Supported pins are {self.supported_pins}")
            return
            
        self.pin = pin
        
        try:
            # Open GPIO chip (chip 0 is the main GPIO chip on Raspberry Pi)
            self.h = lgpio.gpiochip_open(0)
            
            # Claim the GPIO pin as output
            lgpio.gpio_claim_output(self.h, self.pin)
            
            print(f"Initialized servo on GPIO pin {self.pin}")
        except Exception as e:
            self.pin = None
            self.h = None
            print(f"Error initializing GPIO: {e}")
    
    def __del__(self):
        """Clean up GPIO resources when the object is destroyed"""
        if self.pin is not None and self.h is not None:
            try:
                # Free the GPIO pin
                lgpio.gpio_free(self.h, self.pin)
                
                # Close the GPIO chip
                lgpio.gpiochip_close(self.h)
                
                print(f"Cleaned up GPIO pin {self.pin}")
            except Exception as e:
                print(f"Error cleaning up GPIO: {e}")
    
    def set(self, pulse_width_us):
        """
        Set the servo position using software PWM
        
        Args:
            pulse_width_us: Pulse width in microseconds (typically 500-2500)
        """
        if self.pin is None or self.h is None:
            print("Error: Servo not properly initialized")
            return
            
        try:
            # Convert pulse width from microseconds to seconds
            pulse_width_sec = pulse_width_us / 1000000.0
            
            # Generate PWM signal for 10 cycles (about 200ms)
            # This is enough to move the servo to the desired position
            for _ in range(10):
                # Set GPIO high
                lgpio.gpio_write(self.h, self.pin, 1)
                
                # Wait for pulse width duration
                time.sleep(pulse_width_sec)
                
                # Set GPIO low
                lgpio.gpio_write(self.h, self.pin, 0)
                
                # Wait for the remainder of the cycle (20ms total)
                time.sleep(0.02 - pulse_width_sec)
                
        except Exception as e:
            print(f"Error setting servo position: {e}") 