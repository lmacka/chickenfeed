#!/usr/bin/env python3
import time
from typing import Dict, Any, Union
from smbus2 import SMBus
from bme280 import BME280

# BH1750 constants
BH1750_ADDR = 0x23  # Default I2C address
BH1750_ONE_TIME_HIGH_RES_MODE = 0x20  # One-time measurement at 1lx resolution

def read_bh1750(bus: SMBus) -> float:
    # Initialize sensor with one-time high res mode
    bus.write_byte(BH1750_ADDR, BH1750_ONE_TIME_HIGH_RES_MODE)
    
    # Wait for measurement (max 180ms in this mode)
    time.sleep(0.18)
    
    # Read 2 bytes of data
    data = bus.read_i2c_block_data(BH1750_ADDR, BH1750_ONE_TIME_HIGH_RES_MODE, 2)
    
    # Convert raw data to lux
    lux = ((data[0] << 8) | data[1]) / 1.2
    return lux

def read_sensors() -> Dict[str, Union[float, bool]]:
    """
    Read all sensor values and return in a structured format
    
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
        return {
            "success": False,
            "error": str(e)
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