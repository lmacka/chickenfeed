"""
Socket.IO service for handling WebSocket communication with clients
"""
import os
import logging
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, DefaultDict
from datetime import datetime, timezone, timedelta
import pytz
from collections import defaultdict
import time
import re

import socketio
from fastapi import FastAPI
from better_profanity import profanity

from app.utils.user_naming import get_user_identifier

# Configure logging
logger = logging.getLogger(__name__)

# Get control timeout from environment variable with fallback to 30 seconds
CONTROL_TIMEOUT_SECONDS = int(os.environ.get('CONTROL_TIMEOUT_SECONDS', 30))
logger.info(f"Control timeout set to {CONTROL_TIMEOUT_SECONDS} seconds")

# Set up file paths for persistence
DATA_DIR = Path("/config/data")
CHAT_HISTORY_FILE = DATA_DIR / "chat_history.json"
CHAT_LOG_FILE = DATA_DIR / "chat_log.txt"

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True, parents=True)

# Configure chat logging
chat_logger = logging.getLogger("chat_logger")
chat_logger.setLevel(logging.INFO)
# Prevent the chat log from propagating to the root logger
chat_logger.propagate = False

# Add a file handler for the chat log with clean timestamp format
chat_file_handler = logging.FileHandler(CHAT_LOG_FILE)
chat_file_handler.setFormatter(logging.Formatter('%(asctime)s | %(message)s', '%Y-%m-%d %H:%M:%S'))
chat_logger.addHandler(chat_file_handler)

# Rate limiting configuration
CHAT_RATE_LIMIT = int(os.environ.get('CHAT_RATE_LIMIT', 5))  # messages per time window
CHAT_RATE_WINDOW = int(os.environ.get('CHAT_RATE_WINDOW', 10))  # time window in seconds
USERNAME_RATE_LIMIT = int(os.environ.get('USERNAME_RATE_LIMIT', 3))  # changes per day
USERNAME_RATE_WINDOW = int(os.environ.get('USERNAME_RATE_WINDOW', 86400))  # 24 hours in seconds

# Rate limiting storage
message_timestamps: DefaultDict[str, List[float]] = defaultdict(list)  # sid -> list of timestamps
username_changes: DefaultDict[str, List[float]] = defaultdict(list)  # sid -> list of timestamps

# URL validation regex (basic pattern)
URL_PATTERN = re.compile(
    r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
)

# Global state
light_state = False
visitor_count = 0
chicky_client = None
socketio_server = None

# Control system variables
current_controller = None
control_timeout = None

# Add after the global state variables
chat_history: List[Dict[str, Any]] = []  # Store last 50 messages
MAX_CHAT_HISTORY = 50

# Define Australian timezone (GMT+10)
AUSTRALIA_TZ = pytz.timezone('Australia/Brisbane')

# Initialize profanity filter
profanity.load_censor_words()

def check_rate_limit(storage: DefaultDict[str, List[float]], sid: str, 
                     limit: int, window: int) -> bool:
    """
    Check if a request is within rate limits
    
    Args:
        storage: DefaultDict storing timestamps of previous requests
        sid: Session ID of the requester
        limit: Maximum number of requests allowed in the time window
        window: Time window in seconds
        
    Returns:
        True if request is allowed, False if rate limited
    """
    current_time = time.time()
    
    # Remove timestamps older than the window
    storage[sid] = [t for t in storage[sid] if current_time - t < window]
    
    # Check if rate limit is exceeded
    if len(storage[sid]) >= limit:
        return False
    
    # Add current timestamp
    storage[sid].append(current_time)
    return True

def is_valid_chat_message(message: str) -> bool:
    """
    Validate chat message content
    
    Args:
        message: Message content to validate
        
    Returns:
        True if message is valid, False otherwise
    """
    # Check if message is empty after trimming
    if not message.strip():
        return False
    
    # Check message length (already limited to 200 chars elsewhere)
    if len(message) > 200:
        return False
        
    return True

def load_chat_history() -> List[Dict[str, Any]]:
    """
    Load chat history from persistence file
    
    Returns:
        List of chat message dictionaries
    """
    if not CHAT_HISTORY_FILE.exists():
        return []
    
    try:
        with open(CHAT_HISTORY_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading chat history: {e}")
        return []

def save_chat_history(history: List[Dict[str, Any]]) -> None:
    """
    Save chat history to persistence file
    
    Args:
        history: List of chat message dictionaries
    """
    try:
        with open(CHAT_HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)
    except IOError as e:
        logger.error(f"Error saving chat history: {e}")

def log_chat_message(message: Dict[str, Any], source_ip: str = None, country: str = None) -> None:
    """
    Log a chat message to the dedicated chat log file
    
    Args:
        message: Chat message dictionary
        source_ip: Source IP address (if available)
        country: Resolved country code (if available)
    """
    try:
        timestamp = datetime.fromisoformat(message['timestamp'])
        local_time = timestamp.astimezone(AUSTRALIA_TZ)
        
        # Prepare location info if available
        location_info = ""
        if source_ip or country:
            location_info = " ["
            if source_ip:
                location_info += f"IP:{source_ip}"
            if country:
                location_info += f"{', ' if source_ip else ''}Country:{country}"
            location_info += "]"
        
        # Format without timestamp since the logger will add one: USERNAME [LOCATION]: MESSAGE
        log_entry = f"{message['userId']}{location_info}: {message['message']}"
        chat_logger.info(log_entry)
    except Exception as e:
        logger.error(f"Error logging chat message: {e}")

def create_socketio_app(auth_token: str) -> socketio.ASGIApp:
    """
    Create and configure the Socket.IO application
    
    Args:
        auth_token: Authentication token for the chicky client
        
    Returns:
        Configured Socket.IO ASGI application
    """
    global socketio_server, chat_history
    
    # Load chat history from file
    chat_history = load_chat_history()
    logger.info(f"Loaded {len(chat_history)} chat messages from persistence")
    
    # Create Socket.IO server
    sio = socketio.AsyncServer(
        async_mode="asgi",
        cors_allowed_origins=[
            "https://chook.cam",
            # Include www subdomain if needed
            "https://www.chook.cam",
            # Include localhost for development if needed
            "http://localhost:3000",
            "http://localhost:8080"
        ],
        logger=False,
        engineio_logger=False,
    )
    
    # Store the Socket.IO server instance globally
    socketio_server = sio
    
    # Create ASGI app
    app = socketio.ASGIApp(
        socketio_server=sio,
        socketio_path="",
    )
    
    # Register event handlers
    @sio.event
    async def connect(sid, environ):
        """
        Handle client connection
        
        Args:
            sid: Session ID
            environ: WSGI environment
        """
        global visitor_count
        
        # Get user identifier, country code, and IP address
        user_id, country_code, ip_address = get_user_identifier(environ)
        
        logger.info(f"New client connected: {user_id} (sid: {sid}, ip: {ip_address}, country: {country_code})")
        visitor_count += 1
        
        # Store the user ID, country code, and IP in the session data
        await sio.save_session(sid, {
            'user_id': user_id, 
            'custom_username': None,
            'country_code': country_code,
            'ip_address': ip_address
        })
        
        # Send visitor count to all clients
        await sio.emit("visitor-count", {"count": visitor_count})
        
        # Send control status to the new client
        await sio.emit("control-status", {
            "inUse": current_controller is not None,
            "userId": current_controller,
            "timeoutSeconds": CONTROL_TIMEOUT_SECONDS
        }, room=sid)
    
    @sio.event
    async def disconnect(sid):
        """
        Handle client disconnection
        
        Args:
            sid: Session ID
        """
        global visitor_count, chicky_client, current_controller, control_timeout
        logger.info(f"Client disconnected: {sid}")
        
        # If the chicky client disconnected, clear the reference
        if chicky_client and sid == chicky_client["sid"]:
            logger.info("Chicky client disconnected")
            chicky_client = None
        
        # If the controller disconnected, release control
        if current_controller == sid:
            logger.info(f"Controller {sid} disconnected, releasing control")
            current_controller = None
            
            if control_timeout:
                control_timeout.cancel()
                control_timeout = None
            
            # Notify all clients that control is released
            await sio.emit("control-status", {
                "inUse": False,
                "userId": None,
                "timeoutSeconds": CONTROL_TIMEOUT_SECONDS
            })
        
        visitor_count = max(0, visitor_count - 1)
        await sio.emit("visitor-count", {"count": visitor_count})
    
    @sio.event
    async def authenticate(sid, data):
        """
        Handle client authentication
        
        Args:
            sid: Session ID
            data: Authentication data
            
        Returns:
            Authentication result
        """
        global chicky_client
        logger.info(f"Client {sid} attempting to authenticate as {data.get('name')}")
        
        # If this is the chicky client with correct auth token
        if data.get("name") == "chicky" and data.get("token") == auth_token:
            logger.info(f"Client {sid} authenticated as chicky")
            
            # Store client info
            chicky_client = {
                "sid": sid
            }
            logger.info(f"Chicky client registered with sid: {sid}")
            
            # Try to add the client to the room
            try:
                await sio.enter_room(sid, "chicky")
                logger.info(f"Client {sid} entered room 'chicky'")
            except Exception as e:
                logger.error(f"Error adding client to room: {e}")
                # Continue even if room operation fails
            
            # Send current light state to the chicky client
            try:
                await sio.emit("state_sync", {"lightState": light_state}, room=sid)
                logger.info(f"State sync sent to client {sid}")
            except Exception as e:
                logger.error(f"Error sending state sync to client {sid}: {e}")
            
            # Send configuration to the chicky client
            try:
                chicky_config = {}
                for key, value in os.environ.items():
                    if key.startswith("chicky_"):
                        # Store without the prefix for cleaner usage on client
                        chicky_config[key[7:]] = value
                
                await sio.emit("config_sync", chicky_config, room=sid)
                logger.info(f"Config sync sent to client {sid}")
            except Exception as e:
                logger.error(f"Error sending config sync to client {sid}: {e}")
            
            # Send acknowledgement
            logger.info(f"Authentication successful for client {sid}")
            return {"success": True, "message": "Authentication successful"}
        else:
            logger.info(f"Client {sid} failed to authenticate as {data.get('name')}")
            # Send error acknowledgement
            return {"success": False, "message": "Authentication failed"}
    
    @sio.event
    async def light_status(sid, data):
        """
        Handle light status updates from the client
        
        Args:
            sid: Session ID
            data: Light status data
        """
        global light_state
        logger.info(f"Received light status update: {data}")
        
        # Update light state if successful
        if data.get("success"):
            light_state = data.get("state") == "on"
            logger.info(f"Updated light state to: {'on' if light_state else 'off'}")
    
    @sio.event
    async def config_request(sid, data):
        """
        Handle configuration request from the client
        
        Args:
            sid: Session ID
            data: Request data
            
        Returns:
            Configuration request result
        """
        global chicky_client
        logger.info(f"Received config request from client {sid}")
        
        if chicky_client and sid == chicky_client["sid"]:
            # Collect all environment variables with chicky_ prefix
            chicky_config = {}
            for key, value in os.environ.items():
                if key.startswith("chicky_"):
                    # Store without the prefix for cleaner usage on client
                    chicky_config[key[7:]] = value
            
            await sio.emit("config_sync", chicky_config, room=sid)
            logger.info(f"Config sync sent to client {sid}")
            return {"success": True}
        else:
            logger.info(f"Config request denied for client {sid} (not authorized)")
            return {"success": False, "message": "Not authorized"}
    
    @sio.event
    async def request_control(sid, data):
        """
        Handle control request from a client
        
        Args:
            sid: Session ID
            data: Request data
            
        Returns:
            Control request result
        """
        global current_controller, control_timeout
        logger.info(f"Client {sid} requesting control")
        
        # Check if control is available
        if current_controller is None:
            # Grant control
            current_controller = sid
            logger.info(f"Control granted to client {sid}")
            
            # Set timeout to automatically release control
            if control_timeout:
                control_timeout.cancel()
            
            # Create a new timeout task
            control_timeout = asyncio.create_task(release_control_after_timeout(sio, sid))
            
            # Notify all clients
            await sio.emit("control-status", {
                "inUse": True,
                "userId": sid,
                "timeoutSeconds": CONTROL_TIMEOUT_SECONDS
            })
            
            return {"success": True}
        elif current_controller == sid:
            # Already has control, reset timeout
            logger.info(f"Client {sid} already has control, resetting timeout")
            
            if control_timeout:
                control_timeout.cancel()
            
            # Create a new timeout task
            control_timeout = asyncio.create_task(release_control_after_timeout(sio, sid))
            
            return {"success": True}
        else:
            # Denied - someone else has control
            logger.info(f"Control request from {sid} denied, already in use by {current_controller}")
            return {
                "success": False,
                "message": "Another user currently has control"
            }
    
    @sio.event
    async def release_control(sid, data):
        """
        Handle control release from a client
        
        Args:
            sid: Session ID
            data: Release data
            
        Returns:
            Control release result
        """
        global current_controller, control_timeout
        logger.info(f"Client {sid} releasing control")
        
        # Check if this client has control
        if current_controller == sid:
            current_controller = None
            logger.info(f"Control released by client {sid}")
            
            # Cancel timeout
            if control_timeout:
                control_timeout.cancel()
                control_timeout = None
            
            # Notify all clients
            await sio.emit("control-status", {
                "inUse": False,
                "userId": None,
                "timeoutSeconds": CONTROL_TIMEOUT_SECONDS
            })
            
            return {"success": True}
        else:
            logger.info(f"Control release from {sid} ignored, not the controller")
            return {
                "success": False,
                "message": "You don't have control"
            }
    
    @sio.event
    async def command_executed(sid, data):
        """
        Handle command execution notification from a client
        
        Args:
            sid: Session ID
            data: Command data
            
        Returns:
            Command execution result
        """
        global current_controller, control_timeout
        logger.info(f"Client {sid} executed a command")
        
        # Check if this client has control
        if current_controller == sid:
            logger.info(f"Resetting control timeout for client {sid}")
            
            # Reset timeout
            if control_timeout:
                control_timeout.cancel()
            
            # Create a new timeout task
            control_timeout = asyncio.create_task(release_control_after_timeout(sio, sid))
            
            return {"success": True}
        else:
            logger.info(f"Command execution from {sid} ignored, not the controller")
            return {
                "success": False,
                "message": "You don't have control"
            }
    
    @sio.event
    async def check_chicky_status(sid, data):
        """
        Check if the chicky client is connected
        
        Args:
            sid: Session ID
            data: Request data
            
        Returns:
            Chicky connection status
        """
        global chicky_client
        logger.info(f"Client {sid} checking chicky status")
        
        is_connected = chicky_client is not None and chicky_client.get("sid") is not None
        
        return {
            "connected": is_connected,
            "timestamp": asyncio.get_event_loop().time()
        }
    
    @sio.event
    async def chat_message(sid, data):
        """Handle incoming chat messages"""
        global chat_history
        
        if not isinstance(data, dict) or 'message' not in data:
            return {"success": False, "error": "Invalid request format"}
        
        # Get message text
        message_text = data['message']
        
        # Input validation
        if not is_valid_chat_message(message_text):
            return {"success": False, "error": "Invalid message content"}
        
        # Rate limiting
        if not check_rate_limit(message_timestamps, sid, CHAT_RATE_LIMIT, CHAT_RATE_WINDOW):
            logger.warning(f"Rate limit exceeded for chat messages from {sid}")
            return {
                "success": False, 
                "error": f"Rate limit exceeded. Maximum {CHAT_RATE_LIMIT} messages per {CHAT_RATE_WINDOW} seconds."
            }
        
        # Get session data to access user information
        session = await sio.get_session(sid)
        user_id = session.get('custom_username') or session.get('user_id', sid[:8])
        
        # Get source IP and country from session data
        source_ip = session.get('ip_address')
        country = session.get('country_code')
        
        # Clean the message
        clean_message = profanity.censor(message_text[:200])
        
        # Get current time in Australian timezone
        now = datetime.now(tz=AUSTRALIA_TZ)
        
        message = {
            'userId': user_id,
            'message': clean_message,
            'timestamp': now.isoformat(),
            'is_custom_username': session.get('custom_username') is not None
        }
        
        # Add message to history
        chat_history.append(message)
        if len(chat_history) > MAX_CHAT_HISTORY:
            chat_history.pop(0)
        
        # Save chat history to file
        save_chat_history(chat_history)
        
        # Log message to dedicated chat log with source IP and country
        log_chat_message(message, source_ip, country)
        
        # Broadcast to all clients
        await sio.emit('chat_message', message)
        
        return {"success": True}
    
    @sio.event
    async def set_username(sid, data):
        """Set a custom username for a client"""
        if not isinstance(data, dict) or 'username' not in data:
            return {'success': False, 'error': 'Invalid request'}
        
        username = data['username'].strip()
        
        # Get current session data
        session = await sio.get_session(sid)
        
        # Check if username is empty - this means reset to default
        if not username:
            session['custom_username'] = None
            await sio.save_session(sid, session)
            return {'success': True, 'message': 'Username reset to default'}
        
        # Rate limiting for username changes
        if not check_rate_limit(username_changes, sid, USERNAME_RATE_LIMIT, USERNAME_RATE_WINDOW):
            logger.warning(f"Rate limit exceeded for username changes from {sid}")
            return {
                'success': False, 
                'error': f'Rate limit exceeded. Maximum {USERNAME_RATE_LIMIT} username changes per day.'
            }
        
        # Validate and clean username
        if len(username) > 20:
            username = username[:20]
        
        # Ensure username has minimum length
        if len(username) < 3:
            return {'success': False, 'error': 'Username must be at least 3 characters long'}
        
        # Check for valid characters (alphanumeric and some special chars)
        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', username):
            return {'success': False, 'error': 'Username contains invalid characters'}
        
        username = profanity.censor(username)
        
        # Store in session
        session['custom_username'] = username
        await sio.save_session(sid, session)
        
        # Log username change
        source_ip = session.get('ip_address')
        country = session.get('country_code')
        original_id = session.get('user_id')
        
        logger.info(f"User {original_id} set custom username to {username} (sid: {sid}, ip: {source_ip}, country: {country})")
        
        return {'success': True, 'username': username}
        
    @sio.event
    async def get_username(sid):
        """Get the current username for a client"""
        session = await sio.get_session(sid)
        return {
            'username': session.get('custom_username') or session.get('user_id', sid[:8]),
            'is_custom': session.get('custom_username') is not None
        }
    
    @sio.event
    async def request_chat_history(sid):
        """Send chat history to newly connected clients"""
        await sio.emit('chat_history', {'messages': chat_history}, room=sid)
    
    @sio.event
    async def get_sensors(sid, data):
        """
        Handle sensor readings request
        
        Args:
            sid: Session ID
            data: Request data
            
        Returns:
            Sensor readings
        """
        logger.info(f"Client {sid} requesting sensor readings")
        
        try:
            # Request sensor readings from chicky client
            response = await sio.call(
                "get_sensors",
                {},
                to=sid,
                timeout=15
            )
            
            # Handle response
            logger.info(f"Received sensor readings: {response}")
            
            return response
        except (asyncio.TimeoutError, socketio.exceptions.TimeoutError):
            # Handle timeout
            logger.error("Get sensors request timed out")
            return {
                "success": False,
                "error": "Request timed out waiting for chicky controller response"
            }
    
    return app

async def release_control_after_timeout(sio, sid):
    """
    Release control after timeout
    
    Args:
        sio: Socket.IO server
        sid: Session ID of the controller
    """
    global current_controller, control_timeout
    
    try:
        # Wait for timeout
        await asyncio.sleep(CONTROL_TIMEOUT_SECONDS)
        
        # Check if this client still has control
        if current_controller == sid:
            logger.info(f"Control timeout for client {sid}, releasing control")
            current_controller = None
            control_timeout = None
            
            # Notify all clients
            await sio.emit("control-status", {
                "inUse": False,
                "userId": None,
                "timeoutSeconds": CONTROL_TIMEOUT_SECONDS
            })
    except asyncio.CancelledError:
        # Task was cancelled, do nothing
        pass
    except Exception as e:
        logger.error(f"Error in release_control_after_timeout: {e}")

def get_socketio_server() -> Optional[socketio.AsyncServer]:
    """
    Get the Socket.IO server instance
    
    Returns:
        Socket.IO server instance or None if not initialized
    """
    global socketio_server
    return socketio_server

def get_light_state() -> bool:
    """
    Get the current light state
    
    Returns:
        Current light state (True for on, False for off)
    """
    global light_state
    return light_state

def set_light_state(state: bool) -> None:
    """
    Set the light state
    
    Args:
        state: New light state (True for on, False for off)
    """
    global light_state
    light_state = state

def get_visitor_count() -> int:
    """
    Get the current visitor count
    
    Returns:
        Current visitor count
    """
    global visitor_count
    return visitor_count

def get_chicky_client() -> Optional[Dict[str, Any]]:
    """
    Get the chicky client
    
    Returns:
        Chicky client or None if not connected
    """
    global chicky_client
    return chicky_client

def get_current_controller() -> Optional[str]:
    """
    Get the current controller
    
    Returns:
        Current controller SID or None if no one has control
    """
    global current_controller
    return current_controller 