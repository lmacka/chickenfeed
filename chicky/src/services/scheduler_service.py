"""
Scheduler service for handling scheduled tasks
"""
from typing import Dict, Any, Callable, Optional
from datetime import datetime
import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.utils.logger import get_logger
from src.controllers.light_controller import auto_shutoff_light

logger = get_logger(__name__)

# Global scheduler instance
scheduler = AsyncIOScheduler()
light_shutoff_job = None

def setup_auto_light_shutoff(
    config: Dict[str, Any], 
    socket, 
    is_connected: Callable[[], bool]
) -> Optional[int]:
    """
    Set up automatic light shutoff at the configured end hour
    """
    global light_shutoff_job
    
    if config.get("allowed_end_hour") is None:
        logger.warning("Auto light shutoff setup skipped: configuration not yet available")
        return None
    
    # Cancel existing job if it exists
    if light_shutoff_job:
        try:
            scheduler.remove_job(light_shutoff_job)
        except Exception as e:
            logger.error(f"Error removing existing job: {e}")
        light_shutoff_job = None
    
    # Start the scheduler if it's not running
    if not scheduler.running:
        scheduler.start()
    
    try:
        # Schedule the job to run every hour
        job = scheduler.add_job(
            lambda: check_auto_shutoff(config, socket, is_connected),
            CronTrigger(minute=0),  # Run at the top of every hour
            id="light_shutoff"
        )
        
        light_shutoff_job = job.id
        return job.id
    except Exception as e:
        logger.error(f"Error scheduling light shutoff job: {e}")
        return None

def check_auto_shutoff(
    config: Dict[str, Any], 
    socket, 
    is_connected: Callable[[], bool]
) -> None:
    """
    Check if it's time to turn off the lights
    """
    try:
        if config.get("timezone_offset") is None:
            logger.warning("Auto light shutoff check skipped: timezone_offset not configured")
            return
        
        # Get current hour in the configured timezone
        now = datetime.utcnow()
        current_hour = (now.hour + config["timezone_offset"]) % 24
        
        # Check if it's time to turn off the lights
        if current_hour == config["allowed_end_hour"]:
            # Create a task to run the async function
            asyncio.create_task(auto_shutoff_light(socket, is_connected))
    except Exception as e:
        logger.error(f"Error in auto shutoff check: {e}")

def update_scheduler(
    config: Dict[str, Any], 
    socket, 
    is_connected: Callable[[], bool]
) -> None:
    """
    Update scheduler with new configuration
    """
    global light_shutoff_job
    try:
        light_shutoff_job = setup_auto_light_shutoff(config, socket, is_connected)
    except Exception as e:
        logger.error(f"Error updating scheduler: {e}")

def shutdown_scheduler() -> None:
    """
    Gracefully shutdown all scheduled jobs
    """
    logger.info("Shutting down scheduler")
    
    if scheduler.running:
        scheduler.shutdown() 