"""
API routes for the local server
"""
from typing import Dict, Any, Optional
import time
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel

from src.utils.logger import get_logger
from src.hardware.hardware_interface import control_light
from src.utils.validation import is_within_allowed_hours
from src.services.socket_service import get_socket, is_connected, check_dns

router = APIRouter()
logger = get_logger(__name__)

class LightRequest(BaseModel):
    """Light control request model"""
    state: str

class DNSResponse(BaseModel):
    """DNS test response model"""
    success: bool
    hostname: Optional[str] = None
    addresses: Optional[list] = None
    error: Optional[str] = None

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint"""
    return {
        "status": "ok",
        "timestamp": int(time.time() * 1000)
    }

@router.get("/status")
async def status(request: Request) -> Dict[str, Any]:
    """Connection status endpoint"""
    socket = get_socket()
    config = request.app.state.config
    
    return {
        "status": "ok",
        "timestamp": int(time.time() * 1000),
        "socket": {
            "connected": is_connected(),
            "id": socket.sid if socket else None
        },
        "config": {
            "remote_server": config["remote_server"],
            "auth_token_configured": bool(config["auth_token"]),
            "debug": config["debug"]
        },
        "system": {
            "uptime": time.time() - config.get("start_time", time.time()),
            "memory": {
                "rss": 0  # Not easily available in Python, would need psutil
            },
            "python_version": ".".join(map(str, __import__("sys").version_info[:3]))
        }
    }

@router.get("/test-connection")
async def test_connection() -> Dict[str, Any]:
    """Test WebSocket connection"""
    socket = get_socket()
    
    if not is_connected():
        logger.warning("Test connection requested but not connected")
        raise HTTPException(
            status_code=503,
            detail="Not connected to server"
        )
    
    start_time = time.time()
    
    # This would be implemented in the socket_service.py
    # For now, we just simulate a successful ping
    latency = int((time.time() - start_time) * 1000)
    
    return {
        "success": True,
        "message": "Ping sent to server",
        "socket_id": socket.sid if socket else None
    }

@router.get("/dns-test")
async def dns_test(request: Request) -> DNSResponse:
    """DNS lookup test"""
    try:
        result = await check_dns(request.app.state.config["remote_server"])
        return DNSResponse(
            success=True,
            hostname=result["hostname"],
            addresses=result["addresses"]
        )
    except Exception as e:
        return DNSResponse(
            success=False,
            error=str(e)
        )

@router.get("/url-test")
async def url_test(request: Request) -> Dict[str, Any]:
    """WebSocket URL test"""
    remote_server = request.app.state.config["remote_server"]
    
    if not remote_server:
        raise HTTPException(
            status_code=400,
            detail="Server URL is not configured"
        )

    # Parse the WebSocket URL
    try:
        from urllib.parse import urlparse
        url = urlparse(remote_server)
        hostname = url.netloc or url.path
        
        alternative_urls = [
            f"wss://{hostname}/socket.io/",
            f"wss://{hostname}/ws/",
            f"https://{hostname}/socket.io/",
            f"https://{hostname}"
        ]
        
        url_info = {
            "success": True,
            "original_url": remote_server,
            "protocol": url.scheme,
            "hostname": hostname,
            "port": url.port or ("443" if url.scheme == "wss" else "80"),
            "pathname": url.path,
            "search": url.query,
            "alternatives": alternative_urls
        }
        
        return url_info
    except Exception as e:
        logger.error(f"URL test failed: {e}")
        return {
            "success": False,
            "original_url": remote_server,
            "error": str(e)
        }

@router.post("/light")
async def light_control(request: Request, light_request: LightRequest) -> Dict[str, Any]:
    """Manual light control (for local testing)"""
    state = light_request.state
    config = request.app.state.config
    
    # Check if the command is within allowed hours
    if not is_within_allowed_hours(config):
        allowed_start = config["allowed_start_hour"]
        allowed_end = config["allowed_end_hour"]
        
        end_display = f"{allowed_end - 12}pm" if allowed_end > 12 else f"{allowed_end}am"
        
        message = f"Light command rejected: outside allowed hours ({allowed_start}am-{end_display})"
        logger.warning(message)
        
        raise HTTPException(
            status_code=403,
            detail=f"Sorry, the chicken coop light can only be operated between {allowed_start}am and {end_display}."
        )
    
    # Control the light
    result = control_light(state)
    
    # Return the result
    if not result["success"]:
        raise HTTPException(
            status_code=500,
            detail=result["error"]
        )
    
    return result 