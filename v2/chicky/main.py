#!/usr/bin/env python3
"""
Simplified Chicky controller for Raspberry Pi
Provides HTTP endpoints for hardware control
"""
import os
import logging
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import existing hardware controllers
try:
    from src.hardware.servo_controller import ServoController
    from src.hardware.relay_controller import RelayController
    from src.hardware.sensor_reader import SensorReader
    HARDWARE_AVAILABLE = True
except ImportError:
    logger.warning("Hardware modules not available - running in mock mode")
    HARDWARE_AVAILABLE = False

# Create FastAPI app
app = FastAPI(title="Chicky Controller", version="2.0")

# Initialize hardware controllers if available
if HARDWARE_AVAILABLE:
    servo = ServoController()
    relay = RelayController()
    sensors = SensorReader()
else:
    servo = None
    relay = None
    sensors = None

@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "hardware": HARDWARE_AVAILABLE,
        "version": "2.0"
    }

@app.post("/api/treat")
async def dispense_treat() -> Dict[str, Any]:
    """Dispense treat using servo motor"""
    try:
        if HARDWARE_AVAILABLE and servo:
            # Use existing servo control logic
            servo.dispense_treat()
            logger.info("Treat dispensed successfully")
            return {"success": True, "message": "Treat dispensed"}
        else:
            logger.info("Mock: Treat would be dispensed")
            return {"success": True, "message": "Treat dispensed (mock mode)"}
    except Exception as e:
        logger.error(f"Error dispensing treat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/light")
async def toggle_light() -> Dict[str, Any]:
    """Toggle light using relay"""
    try:
        if HARDWARE_AVAILABLE and relay:
            # Use existing relay control logic
            state = relay.toggle_light()
            logger.info(f"Light toggled to: {state}")
            return {"success": True, "state": state, "message": f"Light turned {'on' if state else 'off'}"}
        else:
            logger.info("Mock: Light would be toggled")
            return {"success": True, "state": True, "message": "Light toggled (mock mode)"}
    except Exception as e:
        logger.error(f"Error toggling light: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sensors")
async def get_sensor_readings() -> Dict[str, Any]:
    """Get current sensor readings"""
    try:
        if HARDWARE_AVAILABLE and sensors:
            # Use existing sensor reading logic
            readings = sensors.get_all_readings()
            logger.debug(f"Sensor readings: {readings}")
            return {
                "success": True,
                "temperature": readings.get("temperature", 0),
                "humidity": readings.get("humidity", 0),
                "pressure": readings.get("pressure", 0),
                "light": readings.get("light", 0),
                "units": {
                    "temperature": "°C",
                    "humidity": "%",
                    "pressure": "hPa",
                    "light": "lx"
                }
            }
        else:
            # Return mock data for testing
            return {
                "success": True,
                "temperature": 22.5,
                "humidity": 45.0,
                "pressure": 1013.25,
                "light": 250.0,
                "units": {
                    "temperature": "°C",
                    "humidity": "%",
                    "pressure": "hPa",
                    "light": "lx"
                }
            }
    except Exception as e:
        logger.error(f"Error reading sensors: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.on_event("startup")
async def startup_event():
    """Initialize hardware on startup"""
    logger.info("Chicky Controller starting up...")
    if HARDWARE_AVAILABLE:
        logger.info("Hardware modules loaded successfully")
        # Initialize hardware if needed
        try:
            if sensors:
                sensors.initialize()
            logger.info("Hardware initialized")
        except Exception as e:
            logger.error(f"Hardware initialization error: {e}")
    else:
        logger.warning("Running in mock mode - no hardware available")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup hardware on shutdown"""
    logger.info("Chicky Controller shutting down...")
    if HARDWARE_AVAILABLE:
        try:
            # Cleanup hardware resources
            if servo:
                servo.cleanup()
            if relay:
                relay.cleanup()
            if sensors:
                sensors.cleanup()
            logger.info("Hardware cleanup complete")
        except Exception as e:
            logger.error(f"Hardware cleanup error: {e}")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "3000"))
    logger.info(f"Starting Chicky Controller on port {port}")
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )