"""
Simple logger utility
"""
import logging
import sys
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    
    # Import here to avoid circular imports
    try:
        from config.default import config
        if config.get("debug", False):
            logger.setLevel(logging.DEBUG)
    except (ImportError, AttributeError):
        pass
    
    return logger 