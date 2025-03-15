"""
Light controller for handling light-related commands
"""
from typing import Dict, Any, Callable, Optional
import asyncio

from src.utils.logger import get_logger
from src.utils.validation import is_within_allowed_hours
from src.hardware.hardware_interface import control_light

logger = get_logger(__name__)

def handle_light_command(data: Dict[str, Any], config: Dict[str, Any], socket) -> Dict[str, Any]:
    """
    Handle light command from remote server
    
    Args:
        data: Command data
        config: Configuration dictionary
        socket: Socket.IO client
        
    Returns:
        Result dictionary with success status and other information
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
            
            # Log at warning level only
            logger.warning(message)
            
            # Return error result
            return {
                "success": False,
                "state": data.get("state", "unknown"),
                "error": error_msg
            }

        # Control the light
        result = control_light(data.get("state", "off"))
        return result
    except Exception as e:
        logger.error(f"Error handling light command: {e}")
        return {
            "success": False,
            "state": data.get("state", "unknown"),
            "error": str(e)
        }

async def auto_shutoff_light(config: Dict[str, Any], socket, connected: bool) -> None:
    """
    Automatically turn off lights at the configured end hour
    
    Args:
        config: Configuration dictionary
        socket: Socket.IO client
        connected: Whether the socket is connected
    """
    # Check if configuration is available
    if config.get("allowed_end_hour") is None:
        logger.warning("Auto-shutdown skipped: configuration not yet available")
        return
    
    # Reduced to warning level
    logger.warning(f"Auto-shutdown: Turning off lights at configured end hour ({config['allowed_end_hour']})")
    
    try:
        # Turn off the light
        result = control_light("off")
        
        # Notify the server about the state change if connected
        if connected and socket and hasattr(socket, 'emit') and result.get("success", False):
            await socket.emit("light_status", {
                "success": True,
                "state": "off",
                "automatic": True
            })
    except Exception as e:
        logger.error(f"Error in automatic light shutdown: {e}") 