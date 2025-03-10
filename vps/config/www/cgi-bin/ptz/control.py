#!/usr/bin/env python3
# Camera PTZ control script using ONVIF
# For Tapo C220 IP Camera

import cgi
import cgitb
import json
import os
import sys
import traceback
from time import sleep
import math
from pathlib import Path

# Enable CGI traceback for debugging
cgitb.enable()

# Set a temporary directory for cache that the abc user can write to
os.environ['TMPDIR'] = '/config/tmp'
os.environ['TEMP'] = '/config/tmp'
os.environ['TMP'] = '/config/tmp'

# Create the temp directory if it doesn't exist
if not os.path.exists('/config/tmp'):
    try:
        os.makedirs('/config/tmp', exist_ok=True)
    except Exception as e:
        print("Content-Type: application/json")
        print("")
        print(json.dumps({
            "success": False,
            "message": f"Failed to create temp directory: {str(e)}"
        }))
        sys.exit(1)

try:
    # Import ONVIF library
    from onvif import ONVIFCamera
    from zeep.cache import SqliteCache
    from zeep.transports import Transport
except ImportError:
    # Return error if library not installed
    print("Content-Type: application/json")
    print("")
    print(json.dumps({
        "success": False,
        "message": "ONVIF library not installed. Please run: pip install onvif_zeep"
    }))
    sys.exit(1)

# Path to WSDL files
WSDL_PATH = '/config/www/cgi-bin/ptz/wsdl'

# Ensure schema files are in the correct location
def ensure_schema_files():
    """Ensure schema files are in the correct location"""
    # The schema files should already be in place from the initialization script
    # This function is kept for compatibility but doesn't need to do anything
    return True

def log_to_file(message):
    """Log message to a file for debugging"""
    with open('/config/www/cgi-bin/ptz/ptz_log.txt', 'a') as f:
        f.write(f"{message}\n")

def init_camera():
    """Initialize camera connection"""
    try:
        # Get camera configuration from environment variables
        camera_ip = os.environ.get('CAMERA_IP')
        camera_port = os.environ.get('CAMERA_PORT')
        camera_user = os.environ.get('CAMERA_USERNAME')
        camera_pass = os.environ.get('CAMERA_PASSWORD')
        pan_speed = os.environ.get('CAMERA_PAN_SPEED')
        tilt_speed = os.environ.get('CAMERA_TILT_SPEED')
        timeout = os.environ.get('CAMERA_TIMEOUT')
        
        # Check if all required environment variables are present
        if not all([camera_ip, camera_port, camera_user, camera_pass, pan_speed, tilt_speed, timeout]):
            log_to_file("Missing required environment variables for camera configuration")
            return None, None, None, None, None, None
        
        # Convert string values from environment variables to appropriate types
        camera_port = int(camera_port)
        pan_speed = float(pan_speed)
        tilt_speed = float(tilt_speed)
        timeout = float(timeout)
        
        # Create a custom transport with a cache in a writable location
        cache_file = os.path.join('/config/tmp', 'zeep_cache.db')
        transport = Transport(cache=SqliteCache(path=cache_file))
        
        # Connect to the camera with custom transport
        camera = ONVIFCamera(
            camera_ip, 
            camera_port,
            camera_user,
            camera_pass,
            WSDL_PATH,
            transport=transport
        )
        
        # Create media service
        media = camera.create_media_service()
        
        # Get profiles
        profiles = media.GetProfiles()
        
        if not profiles:
            log_to_file("No profiles found")
            return None, None, None, None, None, None
            
        # Use the first profile
        token = profiles[0].token
        
        # Create PTZ service
        ptz = camera.create_ptz_service()
        
        return camera, ptz, token, pan_speed, tilt_speed, timeout
        
    except Exception as e:
        log_to_file(f"Error initializing camera: {str(e)}")
        log_to_file(traceback.format_exc())
        return None, None, None, None, None, None

def move_camera(direction, camera=None, ptz=None, token=None, pan_speed=None, tilt_speed=None, timeout=None):
    """Move the camera in the specified direction"""
    try:
        # If camera, ptz, or token is not provided, initialize the camera
        if camera is None or ptz is None or token is None:
            camera, ptz, token, pan_speed, tilt_speed, timeout = init_camera()
            
        if camera is None or ptz is None or token is None:
            return {"success": False, "message": "Failed to initialize camera"}
        
        # Handle preset movement
        if direction.startswith('preset-'):
            preset_number = direction.split('-')[1]
            
            # Map preset numbers to names
            preset_names = {
                "1": "Heater",
                "2": "Window",
                "3": "Feeders"
            }
            
            preset_name = preset_names.get(preset_number, f"Preset {preset_number}")
            
            # Get available presets
            presets = ptz.GetPresets({'ProfileToken': token})
            
            # Find the preset by name or token
            preset_found = False
            for preset in presets:
                current_preset_name = preset.Name if hasattr(preset, 'Name') else None
                preset_token = preset.token if hasattr(preset, 'token') else None
                
                if (current_preset_name and (current_preset_name == preset_name or current_preset_name == f"Preset {preset_number}")) or \
                   (preset_token and preset_token == f"preset{preset_number}"):
                    preset_found = True
                    goto_request = ptz.create_type('GotoPreset')
                    goto_request.ProfileToken = token
                    goto_request.PresetToken = preset_token
                    ptz.GotoPreset(goto_request)
                    return {"success": True, "message": f"Moving to {preset_name}"}
            
            if not preset_found:
                return {"success": False, "message": f"Preset {preset_name} not found"}
        
        # Handle directional movement
        if direction == 'stop':
            # Stop movement
            ptz.Stop({'ProfileToken': token})
            return {"success": True, "message": "Camera stopped"}
            
        # Create request template
        req = ptz.create_type('ContinuousMove')
        req.ProfileToken = token
        
        if not hasattr(req, 'Velocity'):
            return {"success": False, "message": "Camera does not support continuous move"}
            
        # Set velocity based on direction - use very small values for precise control
        if direction == 'left':
            req.Velocity = {'PanTilt': {'x': -pan_speed, 'y': 0}}
        elif direction == 'right':
            req.Velocity = {'PanTilt': {'x': pan_speed, 'y': 0}}
        elif direction == 'up':
            req.Velocity = {'PanTilt': {'x': 0, 'y': tilt_speed}}
        elif direction == 'down':
            req.Velocity = {'PanTilt': {'x': 0, 'y': -tilt_speed}}
        else:
            return {"success": False, "message": f"Invalid direction: {direction}"}
        
        # Execute the move
        ptz.ContinuousMove(req)
        
        # Stop after a short timeout for more precise movements
        sleep(timeout)
        ptz.Stop({'ProfileToken': token})
        
        return {"success": True, "message": f"Camera moved {direction}"}
        
    except Exception as e:
        log_to_file(f"Error moving camera: {str(e)}")
        log_to_file(traceback.format_exc())
        return {"success": False, "message": str(e)}

def save_preset(preset_number, camera=None, ptz=None, token=None):
    """Save the current position as a preset"""
    try:
        # If camera, ptz, or token is not provided, initialize the camera
        if camera is None or ptz is None or token is None:
            camera, ptz, token, _, _, _ = init_camera()
            
        if camera is None or ptz is None or token is None:
            return {"success": False, "message": "Failed to initialize camera"}
        
        # Map preset numbers to names
        preset_names = {
            "1": "Heater",
            "2": "Window",
            "3": "Feeders"
        }
        
        preset_name = preset_names.get(preset_number, f"Preset {preset_number}")
        
        # Create preset request
        preset_request = ptz.create_type('SetPreset')
        preset_request.ProfileToken = token
        preset_request.PresetName = preset_name
        
        # Set the preset
        preset_token = ptz.SetPreset(preset_request)
        
        return {"success": True, "message": f"Preset {preset_name} saved"}
        
    except Exception as e:
        log_to_file(f"Error saving preset: {str(e)}")
        log_to_file(traceback.format_exc())
        return {"success": False, "message": str(e)}

def main():
    """Main CGI function"""
    # Print HTTP headers
    print("Content-Type: application/json")
    print("")
    
    try:
        # Parse CGI parameters
        form = cgi.FieldStorage()
        action = form.getvalue('action', '')
        
        if not action:
            print(json.dumps({
                "success": False,
                "message": "No action specified"
            }))
            return
            
        log_to_file(f"Received action: {action}")
        
        if action.startswith('save-preset-'):
            # Handle save preset command
            preset_number = action.split('-')[2]
            result = save_preset(preset_number)
            print(json.dumps(result))
        else:
            # Handle movement command
            result = move_camera(action)
            print(json.dumps(result))
            
    except Exception as e:
        # Log any exceptions
        log_to_file(f"Unhandled exception: {str(e)}")
        log_to_file(traceback.format_exc())
        
        # Return error response
        error_response = {
            "success": False,
            "message": f"Internal server error: {str(e)}"
        }
        print(json.dumps(error_response))

if __name__ == "__main__":
    main() 