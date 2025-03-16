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
    if key in ["servo1_pin", "servo2_pin", "allowed_start_hour", 
               "allowed_end_hour", "timezone_offset"]:
        try:
            return int(value)
        except (ValueError, TypeError):
            return value
    
    # Default: return as is
    return value

def is_within_allowed_hours(config: Dict[str, Any]) -> bool:
    """
    Check if current time is within allowed hours
    """
    # If the configuration is not yet available, default to false
    if (config.get("allowed_start_hour") is None or 
        config.get("allowed_end_hour") is None or 
        config.get("timezone_offset") is None):
        logger.warning("Time-based validation failed: configuration not yet available")
        return False
    
    # Get current UTC time
    now = datetime.utcnow()
    
    # Convert to configured timezone by adding the timezone offset
    local_hour = (now.hour + config["timezone_offset"]) % 24
    
    # Check if current hour is within allowed range
    return local_hour >= config["allowed_start_hour"] and local_hour < config["allowed_end_hour"] 