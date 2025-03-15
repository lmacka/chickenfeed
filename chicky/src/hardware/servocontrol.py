#!/usr/bin/env python3
import sys
import time
import gpiod
import threading

class SoftwarePWM:
    def __init__(self, chip_name, pin, frequency=50):
        """
        Initialize software PWM using libgpiod.
        
        Args:
            chip_name: GPIO chip name (e.g., "gpiochip0")
            pin: GPIO pin number
            frequency: PWM frequency in Hz (default: 50Hz for servos)
        """
        self.pin = pin
        self.chip_name = chip_name
        self.frequency = frequency
        self.period = 1.0 / frequency
        self.duty_cycle = 0
        self.running = False
        self.thread = None
        
        # Open GPIO chip
        self.chip = gpiod.Chip(self.chip_name)
        
        # Get GPIO line
        self.line = self.chip.get_line(self.pin)
        
        # Request line for output
        self.line.request(consumer="servo", type=gpiod.LINE_REQ_DIR_OUT)
        
        print(f"Initialized software PWM on {chip_name}, pin {pin}")
    
    def start(self, duty_cycle):
        """
        Start PWM with the specified duty cycle.
        
        Args:
            duty_cycle: Duty cycle (0-100)
        """
        self.duty_cycle = max(0, min(100, duty_cycle))
        
        if self.thread is None or not self.thread.is_alive():
            self.running = True
            self.thread = threading.Thread(target=self._pwm_thread)
            self.thread.daemon = True
            self.thread.start()
    
    def change_duty_cycle(self, duty_cycle):
        """
        Change the duty cycle.
        
        Args:
            duty_cycle: Duty cycle (0-100)
        """
        self.duty_cycle = max(0, min(100, duty_cycle))
    
    def stop(self):
        """Stop PWM and release resources."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=self.period * 2)
        
        # Set line to low
        self.line.set_value(0)
        
        # Release line and close chip
        self.line.release()
        self.chip.close()
    
    def _pwm_thread(self):
        """PWM generation thread."""
        while self.running:
            if self.duty_cycle > 0:
                # Calculate on and off times
                on_time = self.period * (self.duty_cycle / 100.0)
                off_time = self.period - on_time
                
                # Generate PWM cycle
                self.line.set_value(1)
                time.sleep(on_time)
                
                if off_time > 0:
                    self.line.set_value(0)
                    time.sleep(off_time)
            else:
                # 0% duty cycle - just keep the line low
                self.line.set_value(0)
                time.sleep(self.period)

class ServoController:
    def __init__(self, pin, chip_name="gpiochip0"):
        """
        Initialize a servo controller using software PWM.
        
        Args:
            pin: GPIO pin number
            chip_name: GPIO chip name (default: "gpiochip0")
        """
        self.pin = pin
        self.pwm = SoftwarePWM(chip_name, pin)
        
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
        self.pwm.change_duty_cycle(duty_cycle)
        
        return duty_cycle
    
    def cleanup(self):
        """Release GPIO resources."""
        self.pwm.stop()
        print(f"Cleaned up GPIO pin {self.pin}")

def find_gpio_chips():
    """Find available GPIO chips in the system."""
    import glob
    return [chip.split('/')[-1] for chip in glob.glob('/dev/gpiochip*')]

if __name__ == "__main__":
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print("Usage: python3 servocontrol.py <GPIO_PIN> <ANGLE> [CHIP_NAME]")
        print("Example: python3 servocontrol.py 15 90")
        print("Example with chip: python3 servocontrol.py 15 90 gpiochip0")
        sys.exit(1)

    try:
        gpio_pin = int(sys.argv[1])
        angle = int(sys.argv[2])
        
        # Use specified chip or try to find one
        if len(sys.argv) == 4:
            chip_name = sys.argv[3]
        else:
            chips = find_gpio_chips()
            if not chips:
                print("Error: No GPIO chips found")
                sys.exit(1)
            chip_name = chips[0]
            print(f"Using GPIO chip: {chip_name}")

        if angle < 0 or angle > 180:
            print("Error: Angle must be between 0 and 180")
            sys.exit(1)

        # Initialize servo controller
        servo = ServoController(gpio_pin, chip_name)
        
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