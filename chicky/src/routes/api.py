"""
API routes for the Chicky app
"""
from typing import Dict, Any, Optional
import time
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from src.utils.logger import get_logger
from src.utils.validation import is_within_allowed_hours
from src.services.socket_service import get_socket, is_connected, check_dns
from src.hardware.sensors import SensorController

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
            "auth_token_configured": bool(config["auth_token"])
        },
        "system": {
            "uptime": time.time() - config.get("start_time", time.time()),
            "memory": {
                "rss": 0  # Would need psutil for accurate measurement
            },
            "python_version": ".".join(map(str, __import__("sys").version_info[:3]))
        }
    }

@router.get("/test-connection")
async def test_connection() -> Dict[str, Any]:
    """Test WebSocket connection"""
    socket = get_socket()
    
    if not is_connected():
        raise HTTPException(
            status_code=503,
            detail="Not connected to server"
        )
    
    start_time = time.time()
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
        logger.error("URL test failed")
        logger.debug(f"URL test error details: {e}")
        return {
            "success": False,
            "original_url": remote_server,
            "error": str(e)
        }

@router.get("/sensors")
async def get_sensors() -> Dict[str, Any]:
    """Get current sensor readings"""
    try:
        with SensorController() as sensors:
            return sensors.read_sensors()
    except Exception as e:
        logger.error(f"Error reading sensors: {e}")
        return {
            "success": False,
            "error": str(e),
            "temperature": None,
            "pressure": None,
            "humidity": None,
            "light": None
        }

@router.post("/light")
async def control_light(state: str) -> Dict[str, Any]:
    """Control the light"""
    try:
        import os
        import subprocess
        
        # Path to the light script
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                  "hardware", "light.py")
        
        logger.info(f"API call to control light: {state}")
        process = subprocess.run(
            [script_path, state], 
            capture_output=True, 
            text=True,
            check=False
        )
        
        if process.returncode == 0:
            logger.info(f"Light set to {state} successfully")
            return {
                "success": True,
                "state": state
            }
        else:
            logger.error(f"Error controlling light: {process.stderr}")
            return {
                "success": False,
                "state": state,
                "error": f"Light command failed: {process.stderr}"
            }
    except Exception as e:
        logger.error(f"Error controlling light: {e}")
        # Don't convert to HTTPException - return consistent error format
        return {
            "success": False,
            "state": state,
            "error": str(e)
        }
