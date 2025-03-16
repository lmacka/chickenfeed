"""
Treat controller for handling treat-related commands
"""
import asyncio
from typing import Dict, Any, Optional

from src.utils.logger import get_logger
from src.utils.validation import is_within_allowed_hours
from src.hardware.hardware_interface import dispense_treat

logger = get_logger(__name__)

async def handle_treat_command(data: Dict[str, Any], config: Dict[str, Any], socket) -> Dict[str, Any]:
    """
    Handle treat command from remote server
    """
    try:
        # Check if the command is within allowed hours
        if not is_within_allowed_hours(config):
            # If configuration is not available, provide a generic message
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
        
        # Get servo configuration
        servo = data.get("servo", "servo1")
        servo_pin = config.get(f"{servo}_pin")
        
        # Check if servo is configured
        if not servo_pin:
            message = f"Treat command rejected: {servo} not configured"
            logger.warning(message)
            
            return {
                "success": False,
                "error": f"Sorry, the treat dispenser is not properly configured."
            }
        
        # Dispense the treat
        result = await dispense_treat(servo, servo_pin)
        
        # Emit the result to the server
        if socket and hasattr(socket, "emit"):
            try:
                await socket.emit("treat_result", result)
            except Exception as e:
                logger.error(f"Error emitting treat result: {e}")
        
        return result
    except Exception as e:
        logger.error(f"Error handling treat command: {e}")
        return {
            "success": False,
            "error": str(e)
        } 