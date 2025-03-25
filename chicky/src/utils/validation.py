"""
Validation utilities
"""
from typing import Dict, Any, Union
from datetime import datetime

from src.utils.logger import get_logger

logger = get_logger(__name__)

def validate_config(config: Dict[str, Any]) -> bool:
    """
    Validate required environment variables
    """
    missing_vars = []
    
    if not config.get("remote_server"):
        missing_vars.append("REMOTE_SERVER")
    if not config.get("auth_token"):
        missing_vars.append("AUTH_TOKEN")
    
    if missing_vars:
        logger.warning(f"Missing environment variables: {', '.join(missing_vars)}")
        logger.warning("Some functionality may be limited")
        return False
    
    return True

def parse_time_string(time_str: str) -> tuple[int, int]:
    """
    Parse a time string in HHMM format into hours and minutes
    
    Args:
        time_str: Time string in HHMM format (e.g. "0630" for 6:30 AM)
        
    Returns:
        Tuple of (hour, minute)
    """
    try:
        time_int = int(time_str)
        hours = time_int // 100
        minutes = time_int % 100
        if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
            raise ValueError("Invalid time format")
        return hours, minutes
    except (ValueError, TypeError):
        logger.error(f"Invalid time format: {time_str}")
        return None, None

def parse_config_value(key: str, value: Union[str, int, bool]) -> Union[str, int, bool]:
    """
    Parse configuration values with appropriate types
    """
    # Boolean conversion
    if value == "true":
        return True
    if value == "false":
        return False
    
    # Number conversion for known numeric fields
    if key in ["servo_pin", "timezone_offset"]:
        try:
            return int(value)
        except (ValueError, TypeError):
            return value
            
    # Time string conversion
    if key in ["allowed_start_time", "allowed_end_time"]:
        return str(value)
    
    # Default: return as is
    return value

def is_within_allowed_hours(config: Dict[str, Any]) -> bool:
    """
    Check if current time is within allowed hours
    
    Args:
        config: Configuration dictionary with allowed_start_time, allowed_end_time, 
               and timezone_offset
               
    Returns:
        True if current time is within allowed hours, False otherwise
    """
    # Add debug logging
    logger.debug(f"Checking time with config: {config}")
    
    # If the configuration is not yet available, default to false
    if (config.get("allowed_start_time") is None or 
        config.get("allowed_end_time") is None or 
        config.get("timezone_offset") is None):
        logger.warning("Time-based validation failed: configuration not yet available")
        return False
    
    # Parse start and end times
    start_hour, start_minute = parse_time_string(config["allowed_start_time"])
    end_hour, end_minute = parse_time_string(config["allowed_end_time"])
    
    # Add debug logging
    logger.debug(f"Parsed times - Start: {start_hour}:{start_minute}, End: {end_hour}:{end_minute}")
    
    if start_hour is None or end_hour is None:
        logger.warning("Time-based validation failed: invalid time format")
        return False
    
    # Get current UTC time
    now = datetime.utcnow()
    
    # Convert to configured timezone by adding the timezone offset
    local_hour = (now.hour + config["timezone_offset"]) % 24
    local_minute = now.minute
    
    # Convert times to minutes since midnight for easier comparison
    current_time = local_hour * 60 + local_minute
    start_time = start_hour * 60 + start_minute
    end_time = end_hour * 60 + end_minute
    
    # Check if current time is within allowed range
    # If start_time < end_time, normal range check
    if start_time < end_time:
        return current_time >= start_time and current_time < end_time
    # If start_time > end_time, we're spanning midnight
    else:
        return current_time >= start_time or current_time < end_time 