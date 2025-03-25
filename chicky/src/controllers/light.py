"""
Light controller for handling light-related commands
"""
import os
import subprocess
from typing import Dict, Any
from src.utils.logger import get_logger
from src.utils.validation import is_within_allowed_hours
from src.utils.time_utils import parse_time_string

logger = get_logger(__name__)

def handle_outside_hours_error(config: Dict[str, Any], state: str) -> Dict[str, Any]:
    """Handle error when command is outside allowed hours"""
    if config.get("allowed_start_time") is None or config.get("allowed_end_time") is None:
        message = "Light command rejected: waiting for configuration from server"
        error_msg = "Sorry, the system is still initializing. Please try again in a moment."
    else:
        try:
            start_hours, start_minutes = parse_time_string(config["allowed_start_time"])
            end_hours, end_minutes = parse_time_string(config["allowed_end_time"])
            
            if None in (start_hours, start_minutes, end_hours, end_minutes):
                message = "Light command rejected: invalid time configuration"
                error_msg = "Sorry, there is an issue with the time configuration."
            else:
                start_time = f"{start_hours:02d}:{start_minutes:02d}"
                end_time = f"{end_hours:02d}:{end_minutes:02d}"
                message = f"Light command rejected: outside allowed hours ({start_time}-{end_time})"
                error_msg = f"Sorry, the chicken coop light can only be operated between {start_time} and {end_time}."
        except Exception as e:
            logger.error(f"Error formatting time message: {e}")
            message = "Light command rejected: invalid time configuration"
            error_msg = "Sorry, there is an issue with the time configuration."
    
    logger.warning(message)
    return {
        "success": False,
        "state": state,
        "error": error_msg
    }

async def handle_light_command(data: Dict[str, Any], config: Dict[str, Any], socket) -> Dict[str, Any]:
    """
    Handle light command from remote server
    
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
            return handle_outside_hours_error(config, data.get("state", "unknown"))

        # Get desired state
        state = data.get("state", "off").lower()
        if state not in ["on", "off"]:
            return {
                "success": False,
                "state": state,
                "error": "Invalid state. Use 'on' or 'off'."
            }
        
        # Control the light using subprocess to call light.py directly
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                  "hardware", "light.py")
        
        logger.info(f"Running light script: {script_path} {state}")
        process = subprocess.run([script_path, state], 
                               capture_output=True, 
                               text=True,
                               check=False)
        
        if process.returncode == 0:
            logger.info(f"Light command success: {state}")
            result = {
                "success": True,
                "state": state
            }
        else:
            logger.error(f"Light command failed: {process.stderr}")
            result = {
                "success": False,
                "state": state,
                "error": f"Light control failed: {process.stderr}"
            }
        
        # Notify server
        if socket and hasattr(socket, "emit"):
            try:
                await socket.emit("light_result", result)
            except Exception as e:
                logger.error(f"Error emitting light result: {e}")
        
        return result
            
    except Exception as e:
        logger.error(f"Error handling light command: {e}")
        return {
            "success": False,
            "state": data.get("state", "unknown"),
            "error": str(e)
        } 