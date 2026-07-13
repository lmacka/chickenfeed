#!/usr/bin/env python3
"""
Sensor controller for environmental sensors
"""
import time
import logging
from smbus2 import SMBus
from bme280 import BME280

logger = logging.getLogger(__name__)

# BH1750 constants
BH1750_ADDR = 0x23  # Default I2C address
BH1750_ONE_TIME_HIGH_RES_MODE = 0x20  # One-time measurement at 1lx resolution

class SensorReader:
    """Controller for environmental sensors"""
    
    def __init__(self):
        """Initialize sensor reader"""
        self.bus = None
        self.bme280 = None
        self.initialized = False
        logger.info("SensorReader created")
    
    def initialize(self):
        """Initialize I2C bus and sensors"""
        try:
            self.bus = SMBus(1)
            self.bme280 = BME280(i2c_dev=self.bus)
            self.initialized = True
            logger.info("Initialized environmental sensors")
        except Exception as e:
            logger.error(f"Failed to initialize sensors: {e}")
            raise
    
    def read_bh1750(self) -> float:
        """Read light level from BH1750 sensor"""
        try:
            # Initialize sensor with one-time high res mode
            self.bus.write_byte(BH1750_ADDR, BH1750_ONE_TIME_HIGH_RES_MODE)
            
            # Wait for measurement (max 180ms in this mode)
            time.sleep(0.18)
            
            # Read 2 bytes of data
            data = self.bus.read_i2c_block_data(BH1750_ADDR, BH1750_ONE_TIME_HIGH_RES_MODE, 2)
            
            # Convert raw data to lux
            lux = ((data[0] << 8) | data[1]) / 1.2
            return lux
        except Exception as e:
            logger.error(f"Error reading BH1750: {e}")
            return 0.0
    
    def get_all_readings(self) -> dict:
        """
        Read all sensor values and return in a structured format
        
        Returns:
            Dict containing sensor readings
        """
        if not self.initialized:
            self.initialize()
        
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
            
            # Try to read light sensor, fallback to 0 if it fails
            try:
                light = self.read_bh1750()
            except Exception as e:
                logger.warning(f"Could not read light sensor: {e}")
                light = 0.0
            
            return {
                "temperature": round(temperature, 2),
                "pressure": round(pressure, 2),
                "humidity": round(humidity, 2),
                "light": round(light, 2)
            }
        except Exception as e:
            logger.error(f"Error reading sensors: {e}")
            # Return default values on error
            return {
                "temperature": 0.0,
                "pressure": 0.0,
                "humidity": 0.0,
                "light": 0.0
            }
    
    def cleanup(self):
        """Close I2C bus"""
        if self.bus:
            self.bus.close()
            logger.info("Cleaned up environmental sensors")
        self.initialized = False