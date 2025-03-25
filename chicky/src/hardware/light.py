#!/usr/bin/env python3
"""
Light controller for chicken coop lighting
"""
import time
import automationhat
import logging
import sys
from typing import Optional

# Configure logging
logger = logging.getLogger(__name__)

class LightController:
    """Light controller using automationhat relay"""
    
    _instance: Optional['LightController'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        pass
    
    def set_state(self, state: bool) -> None:
        """
        Set light state
        
        Args:
            state: True for on, False for off
        """
        if state:
            automationhat.relay.one.on()
            logger.info("Light ON")
        else:
            automationhat.relay.one.off()
            logger.info("Light OFF")

# For direct script usage
def set_state(state: bool) -> None:
    """Set light state (for direct script usage)"""
    if state:
        automationhat.relay.one.on()
        logger.info("Light ON")
    else:
        automationhat.relay.one.off()
        logger.info("Light OFF")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 light.py <on|off>")
        sys.exit(1)
    
    try:
        state = sys.argv[1].lower()
        if state not in ["on", "off"]:
            print("Invalid argument. Use 'on' or 'off'.")
            sys.exit(1)
        
        with LightController() as light:
            light.set_state(state == "on")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1) 