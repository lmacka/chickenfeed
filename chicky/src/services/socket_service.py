"""
Socket service for handling WebSocket communication with the VPS
"""
import asyncio
import hashlib
import json
import socket as socket_lib
from typing import Dict, Any, Callable, Tuple, Optional, List
from urllib.parse import urlparse

import socketio

from src.utils.logger import get_logger
from src.utils.validation import parse_config_value
from src.controllers.light_controller import handle_light_command
from src.controllers.treat_controller import handle_treat_command

logger = get_logger(__name__)

# Global socket instance
sio: Optional[socketio.AsyncClient] = None
connected = False
config_requested = False
last_config_hash = ""
config_callback = None

def hash_config(obj: Dict[str, Any]) -> str:
    """
    Simple hash function for configuration objects
    
    Args:
        obj: The object to hash
        
    Returns:
        A string hash of the object
    """
    return hashlib.md5(json.dumps(obj, sort_keys=True).encode()).hexdigest()

async def connect_to_server(
    config: Dict[str, Any], 
    on_config_update: Callable[[Dict[str, Any]], None]
) -> Tuple[Optional[socketio.AsyncClient], bool]:
    """
    Connect to the remote server
    
    Args:
        config: Configuration dictionary
        on_config_update: Callback for configuration updates
        
    Returns:
        Socket and connection status
    """
    global sio, connected, config_requested, last_config_hash, config_callback
    
    # Store the callback function
    config_callback = on_config_update
    
    # Check if remote_server is defined before attempting to connect
    if not config.get("remote_server"):
        logger.error("Connection failed: Server URL is undefined")
        logger.error("Please set REMOTE_SERVER environment variable in Balena dashboard")
        return None, False
    
    logger.info(f"Connecting to server at {config['remote_server']}")
    
    # Reset config requested flag
    config_requested = False
    last_config_hash = ""
    
    # Create Socket.IO client with improved configuration
    sio = socketio.AsyncClient(
        reconnection=True,
        reconnection_attempts=10,
        reconnection_delay=1,
        reconnection_delay_max=5,
        logger=False,
        engineio_logger=False
    )
    
    # Register event handlers
    @sio.event
    async def connect():
        global connected, config_requested
        logger.info("Connected to server")
        logger.info(f"Socket ID: {sio.sid}")
        connected = True
        
        # Authenticate with the server
        try:
            # Retry authentication up to 3 times
            max_retries = 3
            retry_count = 0
            auth_success = False
            
            while retry_count < max_retries and not auth_success:
                try:
                    auth_data = {
                        "name": "chicky",
                        "token": config.get("auth_token")
                    }
                    logger.info(f"Attempting authentication (attempt {retry_count + 1}/{max_retries})")
                    response = await sio.call("authenticate", auth_data, timeout=10)
                    logger.info(f"Authentication response: {response}")
                    
                    if response.get("success", False):
                        auth_success = True
                        logger.info("Authentication successful")
                        
                        # Request configuration from the server if authentication was successful
                        if not config_requested:
                            try:
                                config_response = await sio.call("config_request", {})
                                logger.info(f"Config request response: {config_response}")
                                config_requested = True
                            except Exception as e:
                                logger.error(f"Error requesting configuration: {e}")
                    else:
                        logger.warning(f"Authentication failed: {response.get('message', 'Unknown error')}")
                        retry_count += 1
                        await asyncio.sleep(2)  # Wait before retrying
                except Exception as e:
                    logger.error(f"Error during authentication attempt {retry_count + 1}: {e}")
                    retry_count += 1
                    await asyncio.sleep(2)  # Wait before retrying
            
            if not auth_success:
                logger.error("Authentication failed after multiple attempts")
        except Exception as e:
            logger.error(f"Error during authentication: {e}")
    
    @sio.event
    async def connect_error(error):
        logger.error(f"Connection error: {error}")
    
    @sio.event
    async def disconnect(reason=None):
        global connected, config_requested
        logger.info(f"Disconnected from server: {reason}")
        connected = False
        config_requested = False
    
    @sio.event
    async def config_sync(data):
        global last_config_hash, config_callback
        logger.info("Received configuration from server")
        
        try:
            # Parse configuration values
            parsed_config = {}
            for key, value in data.items():
                parsed_config[key] = parse_config_value(key, value)
            
            # Check if configuration has changed
            new_hash = hash_config(parsed_config)
            if new_hash != last_config_hash:
                logger.info("Configuration has changed, updating...")
                
                # Update local configuration
                for key, value in parsed_config.items():
                    config[key] = value
                
                # Call the configuration update callback
                if config_callback:
                    try:
                        config_callback(config)
                    except Exception as e:
                        logger.error(f"Error in config update callback: {e}")
                
                # Update hash
                last_config_hash = new_hash
            else:
                logger.info("Configuration unchanged")
        except Exception as e:
            logger.error(f"Error processing configuration: {e}")
    
    @sio.event
    async def state_sync(data):
        logger.info(f"Received state sync: {data}")
        # Process state sync data if needed
    
    @sio.event
    async def light_command(data, *args):
        logger.info(f"Received light command: {data}")
        try:
            result = handle_light_command(data, config, sio)
            # Check if a callback was provided (it will be the last argument)
            if args and callable(args[-1]):
                callback = args[-1]
                callback(result)
            return result
        except Exception as e:
            logger.error(f"Error handling light command: {e}")
            error_result = {
                "success": False,
                "state": data.get("state", "unknown"),
                "error": str(e)
            }
            if args and callable(args[-1]):
                callback = args[-1]
                callback(error_result)
            return error_result
    
    @sio.event
    async def treat_command(data, *args):
        logger.info(f"Received treat command: {data}")
        try:
            result = await handle_treat_command(data, config, sio)
            # Check if a callback was provided (it will be the last argument)
            if args and callable(args[-1]):
                callback = args[-1]
                callback(result)
            return result
        except Exception as e:
            logger.error(f"Error handling treat command: {e}")
            error_result = {
                "success": False,
                "error": str(e)
            }
            if args and callable(args[-1]):
                callback = args[-1]
                callback(error_result)
            return error_result
    
    @sio.event
    async def light_status(data):
        logger.info(f"Received light status update: {data}")
        # Process light status update if needed
    
    # Connect to the server
    try:
        # Make sure we're using a valid URL
        url = config["remote_server"]
        if not url.startswith(("http://", "https://", "ws://", "wss://")):
            # If no protocol is specified, assume wss:// for secure WebSocket
            url = f"wss://{url}"
            logger.info(f"No protocol specified, using: {url}")
        
        # Ensure the URL includes the socket.io path
        if "/socket.io" not in url:
            url = f"{url}/socket.io"
            logger.info(f"Adding socket.io path to URL: {url}")
        
        # Connect with WebSocket transport and improved timeout settings
        await sio.connect(
            url, 
            transports=["websocket"],
            wait_timeout=10,
            wait=True
        )
        return sio, True
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        return None, False

def get_socket() -> Optional[socketio.AsyncClient]:
    """
    Get the current socket instance
    
    Returns:
        Socket.IO client or None if not connected
    """
    return sio

def is_connected() -> bool:
    """
    Check if the socket is connected
    
    Returns:
        True if connected, False otherwise
    """
    global sio, connected
    return connected and sio is not None and sio.connected

async def check_dns(url: str) -> Dict[str, List[str]]:
    """
    Perform DNS lookup for the given URL
    
    Args:
        url: URL to check
        
    Returns:
        Dictionary with hostname and addresses
    """
    if not url:
        raise ValueError("URL is undefined")
    
    # Parse the URL to get the hostname
    parsed_url = urlparse(url)
    hostname = parsed_url.netloc or parsed_url.path
    
    # Remove port if present
    if ":" in hostname:
        hostname = hostname.split(":")[0]
    
    # Perform DNS lookup
    try:
        addresses = await asyncio.get_event_loop().run_in_executor(
            None, 
            lambda: socket_lib.gethostbyname_ex(hostname)[2]
        )
        
        logger.info(f"DNS lookup successful for {hostname}: {addresses}")
        return {
            "hostname": hostname,
            "addresses": addresses
        }
    except Exception as e:
        logger.error(f"DNS lookup failed for {hostname}: {e}")
        raise 