"""
Default configuration for the Chickenfeed Pi component
"""
import os
import time
from typing import Dict, Any

# Configuration dictionary
config: Dict[str, Any] = {
    # Server configuration - these are the only required local settings
    "port": int(os.getenv("PORT", "3000")),
    "remote_server": os.getenv("REMOTE_SERVER"),
    "auth_token": os.getenv("AUTH_TOKEN"),
    
    # Hardware configuration - these will be provided by the server
    "servo1_pin": None,
    "servo2_pin": None,
    
    # Operation settings - these will be provided by the server
    "debug": os.getenv("DEBUG", "false").lower() == "true",
    "allowed_start_hour": None,
    "allowed_end_hour": None,
    "timezone_offset": None,
    
    # Internal settings
    "start_time": time.time()
} 