"""
Treat controller for handling treat-related commands
"""
import asyncio
from typing import Dict, Any
from src.utils.logger import get_logger
from src.utils.validation import is_within_allowed_hours
from src.hardware.servo import ServoController

logger = get_logger(__name__)

def handle_outside_hours_error(config: Dict[str, Any]) -> Dict[str, Any]:
    """Handle error when command is outside allowed hours"""
    if config.get("allowed_start_hour") is None or config.get("allowed_end_hour") is None:
        message = "Treat command rejected: waiting for configuration from server"
        error_msg = "Sorry, the system is still initializing. Please try again in a moment."
    else:
        allowed_start = config["allowed_start_hour"]
        allowed_end = config["allowed_end_hour"]
        end_display = f"{allowed_end - 12}pm" if allowed_end > 12 else f"{allowed_end}am"
        message = f"Treat command rejected: outside allowed hours ({allowed_start}am-{end_display})"
        error_msg = f"Sorry, treats can only be dispensed between {allowed_start}am and {end_display}."
    
    logger.warning(message)
    return {
        "success": False,
        "error": error_msg
    }

async def handle_treat_command(data: Dict[str, Any], config: Dict[str, Any], socket) -> Dict[str, Any]:
    """
    Handle treat command from remote server
    
    Args:
        data: Command data
        config: System configuration
        socket: Socket connection for server communication
        
    Returns:
        Dict containing command result
    """
    servo = None
    try:
        # Check if command is within allowed hours
        if not is_within_allowed_hours(config):
            return handle_outside_hours_error(config)
        
        # Get and validate servo pin
        servo_pin = config.get("servo_pin")
        if not servo_pin:
            message = "Treat command rejected: servo not configured"
            logger.warning(message)
            return {
                "success": False,
                "error": "Sorry, the treat dispenser is not properly configured."
            }
        
        try:
            # Initialize servo
            servo = ServoController(servo_pin)
            
            # Dispense sequence
            servo.set_angle(180)  # Open dispenser
            await asyncio.sleep(1.0)
            servo.set_angle(0)    # Close dispenser
            await asyncio.sleep(0.5)
            
            result = {
                "success": True,
                "message": "Treat dispensed"
            }
            
            # Notify server
            if socket and hasattr(socket, "emit"):
                try:
                    await socket.emit("treat_result", result)
                except Exception as e:
                    logger.error(f"Error emitting treat result: {e}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error controlling servo: {e}")
            return {
                "success": False,
                "error": f"Failed to dispense treat: {str(e)}"
            }
            
    except Exception as e:
        logger.error(f"Error handling treat command: {e}")
        return {
            "success": False,
            "error": str(e)
        }
    finally:
        if servo:
            servo.cleanup() 