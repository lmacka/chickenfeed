"""
API router for handling HTTP endpoints
"""
import time
import logging
import asyncio
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import socketio

from app.services.socket_service import (
    get_light_state,
    set_light_state,
    get_visitor_count,
    get_chicky_client,
    get_socketio_server,
)

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api")

# Define response models
class HealthResponse(BaseModel):
    status: str
    server: Dict[str, Any]
    chicky: Dict[str, bool]
    light: Dict[str, str]
    visitors: int

class VisitorCountResponse(BaseModel):
    count: int

class WebSocketCheckResponse(BaseModel):
    socketIoRunning: bool
    activeConnections: int
    chickyConnected: bool
    chickyId: Optional[str]
    lightState: str

class LightToggleResponse(BaseModel):
    success: bool
    message: str
    state: str

class TreatResponse(BaseModel):
    success: bool
    message: str

@router.get("/health", response_model=HealthResponse)
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint
    
    Returns:
        Health status information
    """
    chicky_client = get_chicky_client()
    
    return {
        "status": "ok" if chicky_client else "degraded",
        "server": {
            "uptime": time.time(),
            "timestamp": int(time.time() * 1000)
        },
        "chicky": {
            "connected": bool(chicky_client)
        },
        "light": {
            "state": "on" if get_light_state() else "off"
        },
        "visitors": get_visitor_count()
    }

@router.get("/visitors", response_model=VisitorCountResponse)
async def get_visitors() -> Dict[str, int]:
    """
    Get visitor count
    
    Returns:
        Current visitor count
    """
    return {"count": get_visitor_count()}

@router.get("/ws-check", response_model=WebSocketCheckResponse)
async def websocket_check() -> Dict[str, Any]:
    """
    WebSocket connectivity check endpoint
    
    Returns:
        WebSocket connectivity information
    """
    chicky_client = get_chicky_client()
    
    return {
        "socketIoRunning": True,
        "activeConnections": get_visitor_count(),
        "chickyConnected": bool(chicky_client),
        "chickyId": chicky_client["sid"] if chicky_client else None,
        "lightState": "on" if get_light_state() else "off"
    }

@router.post("/toggle-light", response_model=LightToggleResponse)
@router.get("/toggle-light", response_model=LightToggleResponse)
async def toggle_light() -> Dict[str, Any]:
    """
    Toggle light endpoint
    
    Returns:
        Light toggle result
    """
    # Get Socket.IO server and chicky client
    chicky_client = get_chicky_client()
    
    # Check if chicky client is connected
    if not chicky_client:
        logger.error("Toggle light failed: Chicky client not connected")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "success": False,
                "message": "Chicky controller not connected",
                "state": "on" if get_light_state() else "off"
            }
        )
    
    # Get the Socket.IO server instance
    sio = get_socketio_server()
    if not sio:
        logger.error("Toggle light failed: Socket.IO server not available")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "success": False,
                "message": "Socket.IO server not available",
                "state": "on" if get_light_state() else "off"
            }
        )
    
    sid = chicky_client["sid"]
    
    # Toggle the light state
    new_state = not get_light_state()
    set_light_state(new_state)
    light_state_str = "on" if new_state else "off"
    logger.info(f"Toggling light to {light_state_str}")
    
    try:
        # Send command to chicky client with acknowledgement
        response = await sio.call(
            "light_command",
            {"state": light_state_str},
            to=sid,
            timeout=15
        )
        
        # Handle response
        logger.info(f"Received light toggle response: {response}")
        
        # Ensure response has a state field
        if "state" not in response:
            response["state"] = light_state_str
            logger.warning(f"Light toggle response missing 'state' field, using requested state: {light_state_str}")
        
        return {
            "success": response["success"],
            "message": response.get("error", f"Light {'turned on' if response['state'] == 'on' else 'turned off'}"),
            "state": response["state"]
        }
    except (asyncio.TimeoutError, socketio.exceptions.TimeoutError):
        # Handle timeout
        logger.error("Light toggle confirmation timed out")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "success": False,
                "message": "Request timed out waiting for chicky controller response",
                "state": "on" if get_light_state() else "off"
            }
        )

@router.post("/give-treat", response_model=TreatResponse)
@router.get("/give-treat", response_model=TreatResponse)
async def give_treat() -> Dict[str, Any]:
    """
    Give treat endpoint
    
    Returns:
        Treat dispensing result
    """
    # Get Socket.IO server and chicky client
    chicky_client = get_chicky_client()
    
    # Check if chicky client is connected
    if not chicky_client:
        logger.error("Give treat failed: Chicky client not connected")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "success": False,
                "message": "Chicky controller not connected"
            }
        )
    
    # Get the Socket.IO server instance
    sio = get_socketio_server()
    if not sio:
        logger.error("Give treat failed: Socket.IO server not available")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "success": False,
                "message": "Socket.IO server not available"
            }
        )
    
    logger.info("Giving treat")
    
    try:
        # Send command to chicky client with acknowledgement
        response = await sio.call(
            "treat_command",
            {"servo": "servo1"},
            to=chicky_client["sid"],
            timeout=15
        )
        
        # Handle response
        logger.info(f"Received treat dispense response: {response}")
        return {
            "success": response["success"],
            "message": response.get("error", "Treat dispensed successfully!")
        }
    except (asyncio.TimeoutError, socketio.exceptions.TimeoutError):
        # Handle timeout
        logger.error("Treat dispense confirmation timed out")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "success": False,
                "message": "Request timed out waiting for chicky controller response"
            }
        ) 