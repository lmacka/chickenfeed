"""
Scheduler service for handling scheduled tasks using the schedule library
"""
import asyncio
import threading
import time
from typing import Dict, Any, Callable, Optional
from datetime import datetime, timezone

import schedule

from src.utils.logger import get_logger
from src.controllers.light_controller import auto_shutoff_light, auto_turn_on_light
from src.hardware.hardware_interface import control_light

logger = get_logger(__name__)

# Global scheduler variables
scheduler_thread = None
stop_scheduler = False
is_scheduler_running = False

def parse_time_config(config: Dict[str, Any]) -> Dict[str, str]:
    """
    Parse time configuration from config dictionary
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Dictionary with on_time and off_time in HH:MM format
    """
    result = {
        "on_time": None,
        "off_time": None
    }
    
    # Parse start hour (on time)
    if config.get("allowed_start_hour") is not None:
        start_hour = int(config["allowed_start_hour"])
        result["on_time"] = f"{start_hour:02d}:00"
    
    # Parse end hour (off time)
    if config.get("allowed_end_hour") is not None:
        end_hour = int(config["allowed_end_hour"])
        result["off_time"] = f"{end_hour:02d}:00"
    
    return result

def schedule_runner():
    """
    Background thread function that runs the scheduler loop
    """
    global stop_scheduler, is_scheduler_running
    
    logger.info("Scheduler thread started")
    is_scheduler_running = True
    
    while not stop_scheduler:
        # Run all pending jobs
        schedule.run_pending()
        time.sleep(1)
    
    logger.info("Scheduler thread stopped")
    is_scheduler_running = False

def setup_light_schedule(
    config: Dict[str, Any],
    socket,
    is_connected: Callable[[], bool]
) -> bool:
    """
    Set up automatic light schedule at the configured hours
    
    Args:
        config: Configuration dictionary
        socket: Socket.io client instance
        is_connected: Function to check if socket is connected
        
    Returns:
        True if schedule was set up successfully, False otherwise
    """
    if not config.get("allowed_start_hour") or not config.get("allowed_end_hour"):
        logger.warning(
            "Light schedule setup skipped: configuration not yet available. "
            "Required: allowed_start_hour and allowed_end_hour"
        )
        return False
    
    # Clear existing schedule
    schedule.clear()
    
    # Parse time configuration
    time_config = parse_time_config(config)
    on_time = time_config["on_time"]
    off_time = time_config["off_time"]
    
    if not on_time or not off_time:
        logger.warning("Failed to parse time configuration")
        return False
    
    logger.info(f"Setting up light schedule: ON at {on_time}, OFF at {off_time}")
    
    # Schedule light turn-on job
    schedule.every().day.at(on_time).do(
        lambda: asyncio.create_task(auto_turn_on_light(socket, is_connected))
    )
    
    # Schedule light turn-off job
    schedule.every().day.at(off_time).do(
        lambda: asyncio.create_task(auto_shutoff_light(socket, is_connected))
    )
    
    # Start the scheduler thread if not already running
    start_scheduler_thread()
    
    logger.info("Light schedule set up successfully")
    return True

def start_scheduler_thread():
    """
    Start the scheduler thread if not already running
    """
    global scheduler_thread, stop_scheduler, is_scheduler_running
    
    if scheduler_thread and scheduler_thread.is_alive():
        logger.info("Scheduler thread already running")
        return
    
    # Reset stop flag
    stop_scheduler = False
    
    # Create and start the thread
    scheduler_thread = threading.Thread(target=schedule_runner, daemon=True)
    scheduler_thread.start()
    
    # Wait for scheduler to indicate it's running
    timeout = 5
    start_time = time.time()
    while not is_scheduler_running and time.time() - start_time < timeout:
        time.sleep(0.1)
    
    if is_scheduler_running:
        logger.info("Scheduler thread started successfully")
    else:
        logger.error("Failed to start scheduler thread")

def update_scheduler(
    config: Dict[str, Any],
    socket,
    is_connected: Callable[[], bool]
) -> None:
    """
    Update scheduler with new configuration
    
    Args:
        config: Configuration dictionary
        socket: Socket.io client instance
        is_connected: Function to check if socket is connected
    """
    try:
        setup_light_schedule(config, socket, is_connected)
    except Exception as e:
        logger.error(f"Error updating scheduler: {e}")

def shutdown_scheduler() -> None:
    """
    Gracefully shutdown the scheduler
    """
    global stop_scheduler, scheduler_thread
    
    logger.info("Shutting down scheduler")
    
    # Set stop flag
    stop_scheduler = True
    
    # Wait for thread to finish (with timeout)
    if scheduler_thread and scheduler_thread.is_alive():
        scheduler_thread.join(timeout=5)
    
    # Clear all scheduled jobs
    schedule.clear()
    
    logger.info("Scheduler shut down successfully") 