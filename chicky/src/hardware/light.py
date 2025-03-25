#!/usr/bin/env python3
import time
import automationhat
import logging
import sys

# Configure logging
logger = logging.getLogger(__name__)

class LightController:
    """Light controller using automationhat relay"""
    
    def __enter__(self):
        """Context manager entry"""
        try:
            # Initialize automationhat - this is crucial!
            automationhat.setup()
            time.sleep(0.1)  # Allow time for initialization
            return self
        except Exception as e:
            logger.error(f"Failed to initialize automationhat: {e}")
            raise
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - don't turn off relay automatically"""
        # No need to do anything here - we want the relay to stay in its set state
        pass
    
    def set_state(self, state: bool) -> None:
        """
        Set light state
        
        Args:
            state: True for on, False for off
        """
        try:
            if state:
                automationhat.relay.one.on()
                logger.info("Light ON")
            else:
                automationhat.relay.one.off()
                logger.info("Light OFF")
        except Exception as e:
            logger.error(f"Error setting light state: {e}")
            raise

if __name__ == "__main__":
    # Configure logging for CLI usage
    logging.basicConfig(level=logging.INFO)
    
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
            print(f"Light set to {state}")
            # Keep running briefly to ensure command completes
            time.sleep(0.5)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1) 