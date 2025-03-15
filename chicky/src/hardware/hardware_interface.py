"""
Hardware interface for controlling servos and lights
"""
import subprocess
import time
import asyncio
from typing import Dict, Any, Union

from src.utils.logger import get_logger

logger = get_logger(__name__)

def control_light(state: str) -> Dict[str, Any]:
    """
    Control the light relay
    
    Args:
        state: 'on' or 'off'
        
    Returns:
        Result of the operation
    """
    if state not in ["on", "off"]:
        logger.error(f"Invalid light state: {state}")
        return {
            "success": False,
            "error": "Invalid state"
        }
    
    # Log light action
    logger.info(f"Toggling light to {state}")
    
    try:
        # Run the Python script to control the light
        result = subprocess.run(
            ["python3", "src/hardware/light.py", state],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Log success
        logger.info(f"Light toggled successfully to {state}")
        return {
            "success": True,
            "state": state
        }
    except subprocess.CalledProcessError as e:
        logger.error(f"Error executing Python script: {e}")
        return {
            "success": False,
            "error": "Script execution failed"
        }
    except Exception as e:
        logger.error(f"Error handling light command: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def control_servo(servo: str, servo_pin: int, angle: int) -> Dict[str, Any]:
    """
    Control a servo motor
    
    Args:
        servo: 'servo1' or 'servo2'
        servo_pin: GPIO pin number
        angle: Angle to move the servo to (0-180)
        
    Returns:
        Result of the operation
    """
    if not servo_pin:
        logger.error(f"Invalid servo pin: {servo_pin}")
        return {
            "success": False,
            "error": "Invalid servo pin"
        }
    
    # Log servo action
    logger.info(f"Moving {servo} to {angle} degrees")
    
    try:
        # Run the Python script to move the servo
        result = subprocess.run(
            ["python3", "src/hardware/servocontrol.py", str(servo_pin), str(angle)],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Log success
        logger.info(f"Servo {servo} moved successfully to {angle} degrees")
        return {
            "success": True,
            "servo": servo,
            "angle": angle
        }
    except subprocess.CalledProcessError as e:
        logger.error(f"Error executing Python script: {e}")
        return {
            "success": False,
            "error": "Script execution failed"
        }
    except Exception as e:
        logger.error(f"Error controlling servo: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def dispense_treat(servo: str, servo_pin: int) -> Dict[str, Any]:
    """
    Dispense a treat by moving a servo back and forth
    
    Args:
        servo: 'servo1' or 'servo2'
        servo_pin: GPIO pin number
        
    Returns:
        Result of the operation
    """
    # Check if servo pin is configured
    if not servo_pin:
        logger.error(f"Cannot dispense treat: {servo} pin not configured")
        return {
            "success": False,
            "error": "Servo pin not configured"
        }
    
    # Move servo to dispense position
    result1 = control_servo(servo, servo_pin, 180)
    
    if not result1["success"]:
        return result1
    
    # Wait for 0.5 seconds and then move the servo back
    await asyncio.sleep(0.5)
    
    result2 = control_servo(servo, servo_pin, 1)
    
    if not result2["success"]:
        return result2
    
    return {
        "success": True,
        "servo": servo
    } 