"""
Hardware interface for controlling servos and lights
"""
import subprocess
import time
import asyncio
from typing import Dict, Any, Union

from src.utils.logger import get_logger
from src.hardware.sensors import read_sensors

logger = get_logger(__name__)

def control_light(state: str) -> Dict[str, Any]:
    """
    Control the light relay
    """
    if state not in ["on", "off"]:
        logger.error(f"Invalid light state: {state}")
        return {
            "success": False,
            "error": "Invalid state"
        }
    
    logger.info(f"Toggling light to {state}")
    
    try:
        result = subprocess.run(
            ["python3", "src/hardware/light.py", state],
            capture_output=True,
            text=True,
            check=True
        )
        
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
    """
    if not servo_pin:
        logger.error(f"Invalid servo pin: {servo_pin}")
        return {
            "success": False,
            "error": "Invalid servo pin"
        }
    
    logger.info(f"Moving {servo} to {angle} degrees")
    
    try:
        result = subprocess.run(
            ["python3", "src/hardware/servocontrol.py", str(servo_pin), str(angle)],
            capture_output=True,
            text=True,
            check=True
        )
        
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
    """
    if not servo_pin:
        logger.error(f"Cannot dispense treat: {servo} pin not configured")
        return {
            "success": False,
            "error": "Servo pin not configured"
        }
    
    result1 = control_servo(servo, servo_pin, 180)
    
    if not result1["success"]:
        return result1
    
    await asyncio.sleep(0.5)
    
    result2 = control_servo(servo, servo_pin, 1)
    
    if not result2["success"]:
        return result2
    
    return {
        "success": True,
        "servo": servo
    }

def get_sensor_readings() -> Dict[str, Any]:
    """
    Get readings from all environmental sensors
    
    Returns:
        Dict containing sensor readings and success status
    """
    try:
        return read_sensors()
    except Exception as e:
        logger.error(f"Error reading sensors: {e}")
        return {
            "success": False,
            "error": str(e)
        }