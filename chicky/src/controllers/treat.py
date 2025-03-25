"""
Treat controller for handling treat-related commands
"""
import os
import asyncio
import subprocess
from typing import Dict, Any
from src.utils.logger import get_logger
from src.utils.validation import is_within_allowed_hours

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
        
        # Path to the servo script
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                   "hardware", "servo.py")
        
        try:
            # Dispense sequence - first open
            logger.info(f"Dispensing treat: opening servo on pin {servo_pin} to 180 degrees")
            open_process = subprocess.run(
                [script_path, str(servo_pin), "180"],
                capture_output=True,
                text=True,
                check=False
            )
            
            if open_process.returncode != 0:
                logger.error(f"Failed to open treat dispenser: {open_process.stderr}")
                return {
                    "success": False,
                    "error": f"Failed to dispense treat: {open_process.stderr}"
                }
            
            # Wait briefly
            await asyncio.sleep(1.0)
            
            # Close the dispenser
            logger.info(f"Dispensing treat: closing servo on pin {servo_pin} to 0 degrees")
            close_process = subprocess.run(
                [script_path, str(servo_pin), "0"],
                capture_output=True,
                text=True,
                check=False
            )
            
            if close_process.returncode != 0:
                logger.warning(f"Failed to close treat dispenser: {close_process.stderr}")
                # Continue anyway as the treat was already dispensed
            
            # Wait briefly
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