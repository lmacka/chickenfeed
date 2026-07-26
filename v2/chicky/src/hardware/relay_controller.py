#!/usr/bin/env python3
import logging
import time

import automationhat

logger = logging.getLogger(__name__)

class RelayController:
    """Light controller using automationhat relay"""
    
    def __init__(self):
        """Initialize automationhat"""
        try:
            automationhat.setup()
            time.sleep(0.1)  # Allow time for initialization
            self.light_state = False
            logger.info("RelayController initialized with automationhat")
        except Exception as e:
            logger.error(f"Failed to initialize automationhat: {e}")
            raise
    
    def toggle_light(self) -> bool:
        """Toggle light state and return new state"""
        try:
            self.light_state = not self.light_state
            
            if self.light_state:
                automationhat.relay.one.on()
                logger.info("Light ON")
            else:
                automationhat.relay.one.off()
                logger.info("Light OFF")
            
            return self.light_state
        except Exception as e:
            logger.error(f"Error toggling light: {e}")
            raise
    
    def set_state(self, state: bool) -> None:
        """
        Set light state directly
        
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
            self.light_state = state
        except Exception as e:
            logger.error(f"Error setting light state: {e}")
            raise
    
    def cleanup(self):
        """Cleanup resources - relay stays in set state"""
        logger.info("RelayController cleanup (relay state preserved)")