from typing import Dict, List, Optional
import random
import geoip2.database
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Consolidated list of chicken breeds from around the world
CHICKEN_BREEDS = [
    "Australorp", "Wyandotte", "Orpington", "Plymouth", "Rhode", "Bantam",
    "Delaware", "Jersey", "Sussex", "Cornish", "Silkie", "Leghorn",
    "Brahma", "Cochin", "Hamburg", "Marans", "Minorca", "Ancona",
    "Faverolle", "Pekin", "Campine", "Langshan", "Araucana", "Ameraucana",
    "Polish", "Houdan", "Frizzle", "Sebright", "Dominique", "Java",
    "Buckeye", "Chantecler", "Sumatra", "Phoenix", "Sultan", "Malay",
    "Buttercup", "Yokohama", "Rosecomb", "Shamo", "Asil", "Vorwerk",
    "Legbar", "Serama", "Saxony", "Isbar", "Bresse", "Fayoumi",
    "Aseel", "Koeyoshi", "Tomaru", "Brakel", "Nankin", "d'Uccle"
]

# Path to the GeoIP database - adjust as needed
GEOIP_DB_PATH = Path("/config/GeoLite2-Country.mmdb")

def get_country_code(environ: dict) -> tuple[Optional[str], Optional[str]]:
    """
    Get country code using GeoIP lookup
    
    Args:
        environ: WSGI environment dictionary
        
    Returns:
        Tuple of (country_code, client_ip) where either may be None if not resolvable
    """
    client_ip = None
    try:
        # Get client IP from ASGI scope
        scope = environ.get('asgi.scope', {})
        client = scope.get('client', None)
        headers = dict(scope.get('headers', []))
        
        # Try to get IP from headers first
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
        
        # Skip lookup for local IPs but still return country code for local testing
        if client_ip in ('127.0.0.1', 'localhost', '::1'):
            return 'AU', client_ip  # Default to AU for local testing
            
        # Perform GeoIP lookup
        if GEOIP_DB_PATH.exists():
            with geoip2.database.Reader(str(GEOIP_DB_PATH)) as reader:
                response = reader.country(client_ip)
                return response.country.iso_code, client_ip
                
    except FileNotFoundError:
        logger.error(f"GeoIP database not found at {GEOIP_DB_PATH}")
    except Exception as e:
        logger.error(f"Error during GeoIP lookup: {e}")
    
    # Return None if lookup fails instead of a default country
    return None, client_ip

def get_user_identifier(environ: dict) -> tuple[str, Optional[str], Optional[str]]:
    """
    Generate a user identifier based on country code (if available) and random chicken breed
    
    Args:
        environ: WSGI environment dictionary
        
    Returns:
        Tuple of (identifier, country_code, ip_address)
        where identifier is formatted as 'COUNTRY-BREED' or just 'BREED' if no country code
    """
    country_code, client_ip = get_country_code(environ)
    breed = random.choice(CHICKEN_BREEDS)
    
    identifier = f"{country_code}-{breed}" if country_code else breed
    
    return identifier, country_code, client_ip 