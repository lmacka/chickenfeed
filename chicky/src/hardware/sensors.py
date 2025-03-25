#!/usr/bin/env python3
"""
Sensor controller for environmental sensors
"""
import time
import logging
from smbus2 import SMBus
from bme280 import BME280
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# BH1750 constants
BH1750_ADDR = 0x23  # Default I2C address
BH1750_ONE_TIME_HIGH_RES_MODE = 0x20  # One-time measurement at 1lx resolution

class SensorController:
    """Controller for environmental sensors"""
    
    _instance: Optional['SensorController'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __enter__(self):
        """Context manager entry"""
        self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.cleanup()
    
    def initialize(self) -> None:
        """Initialize I2C bus and sensors"""
        self.bus = SMBus(1)
        self.bme280 = BME280(i2c_dev=self.bus)
        logger.debug("Initialized environmental sensors")
    
    def read_bh1750(self) -> float:
        """Read light level from BH1750 sensor"""
        # Initialize sensor with one-time high res mode
        self.bus.write_byte(BH1750_ADDR, BH1750_ONE_TIME_HIGH_RES_MODE)
        
        # Wait for measurement (max 180ms in this mode)
        time.sleep(0.18)
        
        # Read 2 bytes of data
        data = self.bus.read_i2c_block_data(BH1750_ADDR, BH1750_ONE_TIME_HIGH_RES_MODE, 2)
        
        # Convert raw data to lux
        lux = ((data[0] << 8) | data[1]) / 1.2
        return lux
    
    def read_sensors(self) -> dict:
        """
        Read all sensor values and return in a structured format
        
        Returns:
            Dict containing sensor readings and success status
        """
        try:
            # Discard first reading (seems to be cached/default value)
            _ = self.bme280.get_temperature()
            _ = self.bme280.get_pressure()
            _ = self.bme280.get_humidity()
            
            # Small delay to ensure fresh reading
            time.sleep(0.1)
            
            # Get actual readings
            temperature = self.bme280.get_temperature()
            pressure = self.bme280.get_pressure()
            humidity = self.bme280.get_humidity()
            lux = self.read_bh1750()
            
            return {
                "success": True,
                "temperature": round(temperature, 2),
                "pressure": round(pressure, 2),
                "humidity": round(humidity, 2),
                "light": round(lux, 6),
                "units": {
                    "temperature": "C",
                    "pressure": "hPa",
                    "humidity": "%",
                    "light": "lx"
                }
            }
        except Exception as e:
            logger.error(f"Error reading sensors: {e}")
            return {
                "success": False,
                "error": str(e),
                "temperature": None,
                "pressure": None,
                "humidity": None,
                "light": None,
                "units": None
            }
    
    def cleanup(self) -> None:
        """Close I2C bus"""
        self.bus.close()
        logger.debug("Cleaned up environmental sensors")

def read_bh1750(bus: SMBus) -> float:
    """Read light level from BH1750 sensor (for direct script usage)"""
    # Initialize sensor with one-time high res mode
    bus.write_byte(BH1750_ADDR, BH1750_ONE_TIME_HIGH_RES_MODE)
    
    # Wait for measurement (max 180ms in this mode)
    time.sleep(0.18)
    
    # Read 2 bytes of data
    data = bus.read_i2c_block_data(BH1750_ADDR, BH1750_ONE_TIME_HIGH_RES_MODE, 2)
    
    # Convert raw data to lux
    lux = ((data[0] << 8) | data[1]) / 1.2
    return lux

def read_sensors() -> dict:
    """
    Read all sensor values and return in a structured format (for direct script usage)
    
    Returns:
        Dict containing sensor readings and success status
    """
    try:
        bus = SMBus(1)
        bme280 = BME280(i2c_dev=bus)
        
        # Discard first reading (seems to be cached/default value)
        _ = bme280.get_temperature()
        _ = bme280.get_pressure()
        _ = bme280.get_humidity()
        
        # Small delay to ensure fresh reading
        time.sleep(0.1)
        
        # Get actual readings
        temperature = bme280.get_temperature()
        pressure = bme280.get_pressure()
        humidity = bme280.get_humidity()
        lux = read_bh1750(bus)
        
        return {
            "success": True,
            "temperature": round(temperature, 2),
            "pressure": round(pressure, 2),
            "humidity": round(humidity, 2),
            "light": round(lux, 6),
            "units": {
                "temperature": "C",
                "pressure": "hPa",
                "humidity": "%",
                "light": "lx"
            }
        }
    except Exception as e:
        logger.error(f"Error reading sensors: {e}")
        return {
            "success": False,
            "error": str(e),
            "temperature": None,
            "pressure": None,
            "humidity": None,
            "light": None,
            "units": None
        }
    finally:
        bus.close()

if __name__ == "__main__":
    result = read_sensors()
    if result["success"]:
        print(f"{result['temperature']:05.2f}°C {result['pressure']:05.2f}hPa "
              f"{result['humidity']:05.2f}% {result['light']:05.6f}lx")
    else:
        print(f"Error reading sensors: {result['error']}")