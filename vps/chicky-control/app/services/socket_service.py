"""
Socket.IO service for handling WebSocket communication with clients
"""
import os
import logging
from typing import Dict, Any, Optional, List

import socketio
from fastapi import FastAPI

# Configure logging
logger = logging.getLogger(__name__)

# Global state
light_state = False
visitor_count = 0
chicky_client = None
socketio_server = None

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
        logger.info(f"New client connected: {sid}")
        visitor_count += 1
        
        # Send visitor count to all clients
        await sio.emit("visitor_count", {"count": visitor_count})
    
    @sio.event
    async def disconnect(sid):
        """
        Handle client disconnection
        
        Args:
            sid: Session ID
        """
        global visitor_count, chicky_client
        logger.info(f"Client disconnected: {sid}")
        
        # If the chicky client disconnected, clear the reference
        if chicky_client and sid == chicky_client["sid"]:
            logger.info("Chicky client disconnected")
            chicky_client = None
        
        visitor_count = max(0, visitor_count - 1)
        await sio.emit("visitor_count", {"count": visitor_count})
    
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
    
    return app

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