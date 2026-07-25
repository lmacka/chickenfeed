#!/usr/bin/env python3
"""
Chicky controller for the coop Raspberry Pi.

Two ways in, one set of rules:
  - MQTT, dialled OUT to the cluster broker. This is the path the rebuilt
    chook.cam uses. Nothing on the internet needs a route into the coop.
  - HTTP on :3000, kept for local use and diagnostics.

Both go through SafetyEnvelope, so the daylight window, cooldown, daily quota
and light auto-off hold no matter who is asking. The web app can only request
a treat; this process decides whether one happens.
"""
import os
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
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

from src.safety import SafetyEnvelope
from src.mqtt_bridge import MqttBridge

# Initialize hardware controllers if available
if HARDWARE_AVAILABLE:
    servo = ServoController()
    relay = RelayController()
    sensors = SensorReader()
else:
    servo = None
    relay = None
    sensors = None

safety = SafetyEnvelope(relay=relay)
mqtt_bridge = MqttBridge(servo=servo, relay=relay, sensors=sensors, safety=safety)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Chicky Controller starting up...")
    if HARDWARE_AVAILABLE:
        try:
            if sensors:
                sensors.initialize()
            logger.info("Hardware initialized")
        except Exception as e:
            logger.error(f"Hardware initialization error: {e}")
    else:
        logger.warning("Running in mock mode - no hardware available")

    # Never let a broker problem stop the controller from serving locally.
    try:
        mqtt_bridge.start()
    except Exception as e:
        logger.error(f"MQTT bridge failed to start, continuing without it: {e}")

    yield

    logger.info("Chicky Controller shutting down...")
    try:
        mqtt_bridge.stop()
    except Exception as e:
        logger.error(f"MQTT shutdown error: {e}")
    if HARDWARE_AVAILABLE:
        try:
            if servo:
                servo.cleanup()
            if relay:
                relay.cleanup()
            if sensors:
                sensors.cleanup()
            logger.info("Hardware cleanup complete")
        except Exception as e:
            logger.error(f"Hardware cleanup error: {e}")


app = FastAPI(title="Chicky Controller", version="2.1", lifespan=lifespan)


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "hardware": HARDWARE_AVAILABLE,
        "version": "2.1",
        "mqtt": mqtt_bridge.client is not None,
    }


@app.get("/api/status")
async def status() -> Dict[str, Any]:
    """Current safety-envelope state: quota, cooldown, daylight, light timer."""
    return safety.status()


@app.post("/api/treat")
async def dispense_treat() -> Dict[str, Any]:
    """Dispense a treat, if the safety envelope allows it."""
    allowed, reason = safety.begin_dispense()
    if not allowed:
        # 429 rather than 403: this is a rate/scheduling refusal, not authz.
        raise HTTPException(status_code=429, detail=reason)
    ok = False
    try:
        if HARDWARE_AVAILABLE and servo:
            servo.dispense_treat()
        else:
            logger.info("Mock: Treat would be dispensed")
        ok = True
        return {"success": True, "message": "Treat dispensed", "status": safety.status()}
    except Exception as e:
        logger.error(f"Error dispensing treat: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        safety.end_dispense(ok)


@app.post("/api/light")
async def toggle_light() -> Dict[str, Any]:
    """Toggle the coop light. Turning it on always arms the auto-off timer."""
    try:
        if HARDWARE_AVAILABLE and relay:
            state = relay.toggle_light()
        else:
            state = not getattr(toggle_light, "_mock_state", False)
            toggle_light._mock_state = state
            logger.info("Mock: Light toggled")

        if state:
            safety.note_light_on()
        else:
            safety.note_light_off()

        return {
            "success": True,
            "state": state,
            "message": f"Light turned {'on' if state else 'off'}",
        }
    except Exception as e:
        logger.error(f"Error toggling light: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sensors")
async def get_sensor_readings() -> Dict[str, Any]:
    """Get current sensor readings"""
    units = {
        "temperature": "°C",
        "humidity": "%",
        "pressure": "hPa",
        "light": "lx",
    }
    try:
        if HARDWARE_AVAILABLE and sensors:
            readings = sensors.get_all_readings()
            return {
                "success": True,
                "temperature": readings.get("temperature", 0),
                "humidity": readings.get("humidity", 0),
                "pressure": readings.get("pressure", 0),
                "light": readings.get("light", 0),
                "units": units,
            }
        return {
            "success": True,
            "temperature": 22.5,
            "humidity": 45.0,
            "pressure": 1013.25,
            "light": 250.0,
            "units": units,
        }
    except Exception as e:
        logger.error(f"Error reading sensors: {e}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "3000"))
    logger.info(f"Starting Chicky Controller on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
