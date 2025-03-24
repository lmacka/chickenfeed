"""
API router for handling HTTP endpoints
"""
import time
import logging
import asyncio
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel
import socketio

from app.services.socket_service import (
    get_light_state,
    set_light_state,
    get_visitor_count,
    get_chicky_client,
    get_socketio_server,
    get_current_controller,
    CONTROL_TIMEOUT_SECONDS,
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

class ControlStatusResponse(BaseModel):
    inUse: bool
    userId: Optional[str]
    timeoutSeconds: int

class SensorReadingsResponse(BaseModel):
    success: bool
    temperature: Optional[float] = None
    pressure: Optional[float] = None
    humidity: Optional[float] = None
    light: Optional[float] = None
    units: Optional[Dict[str, str]] = None
    error: Optional[str] = None

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

@router.get("/control-status", response_model=ControlStatusResponse)
async def control_status() -> Dict[str, Any]:
    """
    Get control status
    
    Returns:
        Current control status
    """
    current_controller = get_current_controller()
    
    return {
        "inUse": current_controller is not None,
        "userId": current_controller,
        "timeoutSeconds": CONTROL_TIMEOUT_SECONDS
    }

@router.post("/toggle-light", response_model=LightToggleResponse)
@router.get("/toggle-light", response_model=LightToggleResponse)
async def toggle_light(request: Request) -> Dict[str, Any]:
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
    
    # Check if the client has control
    client_id = request.headers.get("X-Socket-ID")
    current_controller = get_current_controller()
    
    if client_id != current_controller:
        logger.error(f"Toggle light failed: Client {client_id} does not have control (current controller: {current_controller})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "message": "You do not have control",
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
        
        # Reset control timeout
        if client_id and client_id == current_controller:
            await sio.emit("command_executed", {}, room=client_id)
        
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
async def give_treat(request: Request) -> Dict[str, Any]:
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
    
    # Check if the client has control
    client_id = request.headers.get("X-Socket-ID")
    current_controller = get_current_controller()
    
    if client_id != current_controller:
        logger.error(f"Give treat failed: Client {client_id} does not have control (current controller: {current_controller})")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "success": False,
                "message": "You do not have control"
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
        
        # Reset control timeout
        if client_id and client_id == current_controller:
            await sio.emit("command_executed", {}, room=client_id)
        
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

@router.get("/sensors", response_model=SensorReadingsResponse)
async def get_sensors() -> Dict[str, Any]:
    """
    Get sensor readings from the chicky controller
    
    Returns:
        Current sensor readings
    """
    # Get Socket.IO server and chicky client
    chicky_client = get_chicky_client()
    
    # Check if chicky client is connected
    if not chicky_client:
        logger.error("Get sensors failed: Chicky client not connected")
        return {
            "success": False,
            "error": "Chicky controller not connected"
        }
    
    # Get the Socket.IO server instance
    sio = get_socketio_server()
    if not sio:
        logger.error("Get sensors failed: Socket.IO server not available")
        return {
            "success": False,
            "error": "Socket.IO server not available"
        }
    
    try:
        # Request sensor readings from chicky client
        response = await sio.call(
            "get_sensors",
            {},
            to=chicky_client["sid"],
            timeout=15
        )
        
        # Handle response
        logger.debug(f"Received sensor readings: {response}")
        
        # Return the readings data instead of the whole response
        return response.get("readings", {
            "success": False,
            "error": "No readings data in response"
        })
    except (asyncio.TimeoutError, socketio.exceptions.TimeoutError):
        # Handle timeout
        logger.error("Get sensors request timed out")
        return {
            "success": False,
            "error": "Request timed out waiting for chicky controller response"
        } 