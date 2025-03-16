"""
Light controller for handling light-related commands
"""
from typing import Dict, Any, Callable, Optional
import asyncio

from src.utils.logger import get_logger
from src.utils.validation import is_within_allowed_hours
from src.hardware.hardware_interface import control_light

logger = get_logger(__name__)

async def handle_light_command(data: Dict[str, Any], config: Dict[str, Any], socket) -> Dict[str, Any]:
    """
    Handle light command from remote server
    """
    try:
        # Check if the command is within allowed hours
        if not is_within_allowed_hours(config):
            # If configuration is not available, provide a generic message
            if config.get("allowed_start_hour") is None or config.get("allowed_end_hour") is None:
                message = "Light command rejected: waiting for configuration from server"
                error_msg = "Sorry, the system is still initializing. Please try again in a moment."
            else:
                allowed_start = config["allowed_start_hour"]
                allowed_end = config["allowed_end_hour"]
                end_display = f"{allowed_end - 12}pm" if allowed_end > 12 else f"{allowed_end}am"
                message = f"Light command rejected: outside allowed hours ({allowed_start}am-{end_display})"
                error_msg = f"Sorry, the chicken coop light can only be operated between {allowed_start}am and {end_display}."
            
            logger.warning(message)
            
            return {
                "success": False,
                "state": data.get("state", "unknown"),
                "error": error_msg
            }

        # Control the light
        result = control_light(data.get("state", "off"))
        
        # Emit the result to the server
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

async def auto_shutoff_light(socket, is_connected: Callable[[], bool]) -> Dict[str, Any]:
    """
    Automatically shut off the light at the end of the allowed hours
    """
    try:
        logger.info("Auto shutoff: turning light off")
        
        # Control the light
        result = control_light("off")
        
        # Emit the result to the server if connected
        if is_connected() and socket and hasattr(socket, "emit"):
            try:
                await socket.emit("light_result", {
                    "success": result["success"],
                    "state": "off",
                    "auto": True
                })
            except Exception as e:
                logger.error(f"Error emitting auto shutoff result: {e}")
        
        return result
    except Exception as e:
        logger.error(f"Error in auto shutoff: {e}")
        return {
            "success": False,
            "error": str(e)
        }