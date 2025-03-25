"""
Simple logger utility
"""
import logging
import sys
from typing import Optional
import os

# Configure logging with environment variable override
log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()

logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance
    """
    logger = logging.getLogger(name)
    
    # Add debug logging to see if this code path is reached
    print("Configuring logger:", name, file=sys.stderr)
    
    # Set log level based on config
    try:
        from config.default import config
        print("Loaded config:", config, file=sys.stderr)  # Debug line
        if config.get("debug", False):
            logger.setLevel(logging.DEBUG)
            print("Debug logging enabled", file=sys.stderr)  # Debug line
    except (ImportError, AttributeError) as e:
        print("Failed to load config:", str(e), file=sys.stderr)  # Debug line
        pass
    
    return logger 