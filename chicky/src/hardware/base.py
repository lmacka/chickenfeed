"""
Base hardware controller class
"""
from typing import Dict, Any
from abc import ABC, abstractmethod
from src.utils.logger import get_logger

logger = get_logger(__name__)

class HardwareController(ABC):
    """Base class for hardware controllers"""
    
    @abstractmethod
    def initialize(self) -> None:
        """Initialize hardware"""
        pass
    
    @abstractmethod
    def cleanup(self) -> None:
        """Cleanup hardware resources"""
        pass
    
    def __enter__(self):
        self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup() 