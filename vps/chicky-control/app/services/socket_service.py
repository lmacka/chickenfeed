"""
Socket.IO service for handling WebSocket communication with clients
"""
import os
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime

import socketio
from fastapi import FastAPI
from better_profanity import profanity

from app.utils.user_naming import get_user_identifier

# Configure logging
logger = logging.getLogger(__name__)

# Get control timeout from environment variable with fallback to 30 seconds
CONTROL_TIMEOUT_SECONDS = int(os.environ.get('CONTROL_TIMEOUT_SECONDS', 30))
logger.info(f"Control timeout set to {CONTROL_TIMEOUT_SECONDS} seconds")

# Global state
light_state = False
visitor_count = 0
chicky_client = None
socketio_server = None

# Control system variables
current_controller = None
control_timeout = None

# Add after the global state variables
chat_history: List[Dict[str, str]] = []  # Store last 50 messages
MAX_CHAT_HISTORY = 50

# Initialize profanity filter
profanity.load_censor_words()

def create_socketio_app(auth_token: str) -> socketio.ASGIApp:
    """
    Create and configure the Socket.IO application
    
    Args:
        auth_token: Authentication token for the chicky client
        
    Returns:
        Configured Socket.IO ASGI application
    """
    global socketio_server
    
    # Create Socket.IO server
    sio = socketio.AsyncServer(
        async_mode="asgi",
        cors_allowed_origins="*",
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
        user_id = get_user_identifier(environ)
        logger.info(f"New client connected: {user_id} (sid: {sid})")
        visitor_count += 1
        
        # Store the user ID in the session data
        await sio.save_session(sid, {'user_id': user_id})
        
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
        if not isinstance(data, dict) or 'message' not in data:
            return
        
        # Get session data to access user_id
        session = await sio.get_session(sid)
        user_id = session.get('user_id', sid[:8])  # Fallback to truncated sid if no user_id
        
        # Clean the message
        clean_message = profanity.censor(data['message'][:200])
        
        message = {
            'userId': user_id,  # Use the country-breed identifier
            'message': clean_message,
            'timestamp': datetime.now().isoformat()
        }
        
        chat_history.append(message)
        if len(chat_history) > MAX_CHAT_HISTORY:
            chat_history.pop(0)
        
        # Broadcast to all clients
        await sio.emit('chat_message', message)

    @sio.event
    async def request_chat_history(sid):
        """Send chat history to newly connected clients"""
        await sio.emit('chat_history', {'messages': chat_history}, room=sid)
    
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