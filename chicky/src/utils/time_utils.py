"""
Time-related utility functions
"""
from typing import Tuple, Optional
from src.utils.logger import get_logger

logger = get_logger(__name__)

def parse_time_string(time_str: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Parse a time string in HHMM format into hours and minutes
    
    Args:
        time_str: Time string in HHMM format (e.g. "0630" for 6:30 AM)
        
    Returns:
        Tuple of (hour, minute) or (None, None) if invalid
    """
    try:
        time_int = int(time_str)
        hours = time_int // 100
        minutes = time_int % 100
        if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
            raise ValueError(f"Invalid time values: hours={hours}, minutes={minutes}")
        return hours, minutes
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid time format '{time_str}': {e}")
        return None, None 