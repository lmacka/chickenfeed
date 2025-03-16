"""
Lifecycle management for the FastAPI application
"""
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI

from src.utils.logger import get_logger
from src.services.scheduler_service import shutdown_scheduler

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup and shutdown events
    """
    # Startup - minimal logging
    logger.info("Starting Chickenfeed Pi server")
    
    # Yield control back to FastAPI
    yield
    
    # Shutdown
    logger.info("Shutting down server")
    shutdown_scheduler() 