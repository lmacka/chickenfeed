from typing import Dict, List, Optional
import random
import geoip2.database
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Dictionary of chicken breeds by country
CHICKEN_BREEDS: Dict[str, List[str]] = {
    "AU": ["Australorp", "Wyandotte", "Orpington", "Plymouth"],
    "US": ["Rhode-Island", "Bantam", "Delaware", "Jersey-Giant"],
    "GB": ["Dorking", "Sussex", "Cornish", "Silkie"],
    "NL": ["Barnevelder", "Brabanter", "Holland", "Welsummer"],
    "DEFAULT": ["Chicken", "Hen", "Rooster", "Chook"]  # Fallback breeds
}

# Path to the GeoIP database - adjust as needed
GEOIP_DB_PATH = Path("/config/GeoLite2-Country.mmdb")

def get_country_code(environ: dict) -> str:
    """
    Get country code using GeoIP lookup
    
    Args:
        environ: WSGI environment dictionary
        
    Returns:
        Two-letter country code (e.g. 'US', 'GB')
    """
    try:
        # Get client IP from ASGI scope
        scope = environ.get('asgi.scope', {})
        client = scope.get('client', None)
        headers = dict(scope.get('headers', []))
        
        # Try to get IP from headers first
        client_ip = None
        if b'x-real-ip' in headers:
            client_ip = headers[b'x-real-ip'].decode('utf-8')
        elif b'x-forwarded-for' in headers:
            # Get the first IP in the chain
            client_ip = headers[b'x-forwarded-for'].decode('utf-8').split(',')[0].strip()
        
        # Fallback to direct client IP if no headers
        if not client_ip and client:
            client_ip = client[0]
            
        # If still no IP, use localhost
        if not client_ip:
            client_ip = '127.0.0.1'
        
        # Skip lookup for local IPs
        if client_ip in ('127.0.0.1', 'localhost', '::1'):
            return 'AU'  # Default to AU for local testing
            
        # Perform GeoIP lookup
        if GEOIP_DB_PATH.exists():
            with geoip2.database.Reader(str(GEOIP_DB_PATH)) as reader:
                response = reader.country(client_ip)
                return response.country.iso_code
                
    except FileNotFoundError:
        logger.error(f"GeoIP database not found at {GEOIP_DB_PATH}")
    except Exception as e:
        logger.error(f"Error during GeoIP lookup: {e}")
    
    # Fallback to AU if lookup fails
    return 'AU'

def get_user_identifier(environ: dict) -> str:
    """
    Generate a user identifier based on country code and random chicken breed
    
    Args:
        environ: WSGI environment dictionary
        
    Returns:
        Formatted user identifier string (e.g. 'US-Bantam')
    """
    country_code = get_country_code(environ)
    breed = random.choice(CHICKEN_BREEDS.get(country_code, CHICKEN_BREEDS["DEFAULT"]))
    return f"{country_code}-{breed}" 