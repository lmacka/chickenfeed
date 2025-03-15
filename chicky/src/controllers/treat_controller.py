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
                message = "Treat command rejected: waiting for configuration from server"
                error_msg = "Sorry, the system is still initializing. Please try again in a moment."
            else:
                allowed_start = config["allowed_start_hour"]
                allowed_end = config["allowed_end_hour"]
                end_display = f"{allowed_end - 12}pm" if allowed_end > 12 else f"{allowed_end}am"
                message = f"Treat command rejected: outside allowed hours ({allowed_start}am-{end_display})"
                error_msg = f"Sorry, treats can only be dispensed between {allowed_start}am and {end_display}."
            
            # Log at warning level only
            logger.warning(message)
            
            # Return error result
            return {
                "success": False,
                "error": error_msg
            }
        
        # Get servo configuration
        servo = data.get("servo", "servo1")
        servo_pin = config.get(f"{servo}_pin")
        
        # Check if servo is configured
        if not servo_pin:
            error_msg = f"Treat command rejected: {servo} not configured"
            logger.warning(error_msg)
            
            # Return error result
            return {
                "success": False,
                "error": error_msg
            }
        
        # Dispense treat
        result = await dispense_treat(servo, servo_pin)
        return result
    except Exception as e:
        logger.error(f"Error handling treat command: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def auto_treat_schedule(config: Dict[str, Any], socket, connected: bool) -> None:
    """
    Automatically dispense treats at scheduled times
    
    Args:
        config: Configuration dictionary
        socket: Socket.IO client
        connected: Whether the socket is connected
    """
    # Check if configuration is available
    if not config.get("treat_schedule"):
        logger.warning("Auto-treat skipped: treat_schedule not configured")
        return
    
    # Get servo configuration
    servo = "servo1"  # Default to servo1 for scheduled treats
    servo_pin = config.get(f"{servo}_pin")
    
    # Check if servo is configured
    if not servo_pin:
        logger.warning(f"Auto-treat skipped: {servo} not configured")
        return
    
    # Reduced to warning level
    logger.warning(f"Auto-treat: Dispensing treat according to schedule")
    
    try:
        # Dispense treat
        await dispense_treat(servo, servo_pin)
    except Exception as e:
        logger.error(f"Error in automatic treat dispensing: {e}") 