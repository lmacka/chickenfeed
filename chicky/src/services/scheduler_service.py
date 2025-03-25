"""
Scheduler service for managing automated tasks
"""
import os
import subprocess
import time
import asyncio
import threading
import schedule
import logging
from typing import Dict, Any, Callable, Optional
from datetime import datetime, timezone, time as dt_time

from src.utils.logger import get_logger
from src.utils.time_utils import parse_time_string

logger = get_logger(__name__)

# Global variables to control scheduler
stop_scheduler = False
scheduler_thread: Optional[threading.Thread] = None

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
    
    # Parse start time
    if config.get("allowed_start_time") is not None:
        try:
            hours, minutes = parse_time_string(config["allowed_start_time"])
            if hours is not None and minutes is not None:
                result["on_time"] = f"{hours:02d}:{minutes:02d}"
        except Exception as e:
            logger.error(f"Error parsing start time: {e}")
    
    # Parse end time
    if config.get("allowed_end_time") is not None:
        try:
            hours, minutes = parse_time_string(config["allowed_end_time"])
            if hours is not None and minutes is not None:
                result["off_time"] = f"{hours:02d}:{minutes:02d}"
        except Exception as e:
            logger.error(f"Error parsing end time: {e}")
    
    return result

def schedule_runner():
    """
    Background thread function that runs the scheduler loop
    """
    global stop_scheduler, is_scheduler_running
    
    logger.info("Scheduler thread started")
    is_scheduler_running = True
    
    # Create an event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while not stop_scheduler:
        try:
            # Run all pending jobs
            for job in schedule.get_jobs():
                if job.should_run:
                    # Run the job and get its coroutine
                    coro = job.job_func()
                    # Run the coroutine in the event loop
                    if asyncio.iscoroutine(coro):
                        loop.run_until_complete(coro)
                    job.last_run = schedule.datetime.datetime.now()
                    job._schedule_next_run()
            time.sleep(1)
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}")
    
    # Clean up the event loop
    loop.close()
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
    if not config.get("allowed_start_time") or not config.get("allowed_end_time"):
        logger.warning(
            "Light schedule setup skipped: configuration not yet available. "
            "Required: allowed_start_time and allowed_end_time"
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
    
    # Create wrapper functions that capture the current socket
    async def turn_on_job():
        from src.services.socket_service import get_socket, is_connected
        socket = get_socket()
        return await auto_turn_on_light(socket, is_connected)
    
    async def turn_off_job():
        from src.services.socket_service import get_socket, is_connected
        socket = get_socket()
        return await auto_shutoff_light(socket, is_connected)
    
    # Schedule light turn-on job
    schedule.every().day.at(on_time).do(turn_on_job)
    
    # Schedule light turn-off job
    schedule.every().day.at(off_time).do(turn_off_job)
    
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

async def auto_turn_on_light(socket, is_connected: Callable[[], bool]) -> Dict[str, Any]:
    """
    Automatically turn on the light at the start of the allowed hours
    """
    try:
        logger.info("Auto turn-on: turning light on")
        
        # Path to the light script
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                  "hardware", "light.py")
        
        # Run the light script to turn on the light
        process = subprocess.run(
            [script_path, "on"],
            capture_output=True,
            text=True,
            check=False
        )
        
        if process.returncode == 0:
            logger.info("Auto light-on success")
            result = {
                "success": True,
                "state": "on",
                "auto": True
            }
        else:
            logger.error(f"Auto light-on failed: {process.stderr}")
            result = {
                "success": False,
                "state": "on",
                "auto": True,
                "error": f"Failed to turn on light: {process.stderr}"
            }
        
        # Emit the result to the server if connected
        if is_connected() and socket and hasattr(socket, "emit"):
            try:
                await socket.emit("light_result", result)
            except Exception as e:
                logger.error(f"Error emitting auto turn-on result: {e}")
        
        return result
    except Exception as e:
        logger.error(f"Error in auto turn-on: {e}")
        return {
            "success": False,
            "error": str(e)
        }

async def auto_shutoff_light(socket, is_connected: Callable[[], bool]) -> Dict[str, Any]:
    """
    Automatically shut off the light at the end of the allowed hours
    """
    try:
        logger.info("Auto shutoff: turning light off")
        
        # Path to the light script
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                  "hardware", "light.py")
        
        # Run the light script to turn off the light
        process = subprocess.run(
            [script_path, "off"],
            capture_output=True,
            text=True,
            check=False
        )
        
        if process.returncode == 0:
            logger.info("Auto light-off success")
            result = {
                "success": True,
                "state": "off",
                "auto": True
            }
        else:
            logger.error(f"Auto light-off failed: {process.stderr}")
            result = {
                "success": False,
                "state": "off",
                "auto": True,
                "error": f"Failed to turn off light: {process.stderr}"
            }
        
        # Emit the result to the server if connected
        if is_connected() and socket and hasattr(socket, "emit"):
            try:
                await socket.emit("light_result", result)
            except Exception as e:
                logger.error(f"Error emitting auto shutoff result: {e}")
        
        return result
    except Exception as e:
        logger.error(f"Error in auto shutoff: {e}")
        return {
            "success": False,
            "error": str(e)
        } 