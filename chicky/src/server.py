"""
Main server for the Chickenfeed Pi component
"""
import asyncio
import signal
import sys
import platform
import os
from typing import Callable, Dict, Any, Optional

import uvicorn
from fastapi import FastAPI

from src.app import create_app
from src.utils.logger import get_logger
from src.utils.validation import validate_config
from src.services.socket_service import connect_to_server, check_dns, get_socket, is_connected
from src.services.scheduler_service import update_scheduler, shutdown_scheduler

logger = get_logger(__name__)

async def start_server() -> None:
    """
    Start the FastAPI server and connect to the remote server if configured
    """
    # Import config here to avoid circular imports
    from config.default import config
    
    # Validate configuration
    is_config_valid = validate_config(config)
    
    # Create the FastAPI application
    app = create_app(config)
    
    # Set up signal handlers for graceful shutdown
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda s, f: sys.exit(0))
    
    # Create a uvicorn config and server instance
    config_obj = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=config["port"],
        log_level="info"
    )
    server = uvicorn.Server(config_obj)
    
    # Start the server in a separate task
    server_task = asyncio.create_task(server.serve())
    
    # If remote_server is defined, try to connect
    if config["remote_server"]:
        try:
            # Attempt to connect to the server
            logger.info(f"Attempting to connect to {config['remote_server']}...")
            
            # Perform DNS lookup
            try:
                await check_dns(config['remote_server'])
            except Exception as e:
                logger.error(f"DNS lookup failed: {e}")
            
            # Define a simple callback function for configuration updates
            def on_config_update(updated_config):
                try:
                    # Get the socket instance
                    socket = get_socket()
                    
                    # Update the scheduler with the new configuration
                    update_scheduler(updated_config, socket, is_connected)
                except Exception as e:
                    logger.error(f"Error in config update callback: {e}")
            
            # Connect to the server
            socket, connected = await connect_to_server(
                config,
                on_config_update
            )
            
            if not connected:
                logger.warning("Failed to establish initial connection to server")
        except Exception as e:
            logger.error(f"Error connecting to server: {e}")
    else:
        logger.error("No server URL provided. Remote functionality disabled.")
    
    # Wait for the server to complete
    await server_task

def run_server():
    """
    Run the server in the main event loop
    """
    asyncio.run(start_server())

if __name__ == "__main__":
    run_server() 