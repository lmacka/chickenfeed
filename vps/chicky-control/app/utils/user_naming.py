from typing import Dict, List
import random

# Dictionary of chicken breeds by country
CHICKEN_BREEDS: Dict[str, List[str]] = {
    "AU": ["Australorp", "Wyandotte", "Orpington", "Plymouth"],
    "US": ["Rhode-Island", "Bantam", "Delaware", "Jersey-Giant"],
    "GB": ["Dorking", "Sussex", "Cornish", "Silkie"],
    "NL": ["Barnevelder", "Brabanter", "Holland", "Welsummer"],
    "DEFAULT": ["Chicken", "Hen", "Rooster", "Chook"]  # Fallback breeds
}

def get_user_identifier(environ: dict) -> str:
    """
    Generate a user identifier based on country code and random chicken breed
    
    Args:
        environ: WSGI environment dictionary containing client information
        
    Returns:
        Formatted user identifier string (e.g. 'US-Bantam')
    """
    # Try to get country from headers
    headers = environ.get('asgi.scope', {}).get('headers', [])
    cf_country = None
    
    # Look for Cloudflare country header
    for name, value in headers:
        if name == b'cf-ipcountry':
            cf_country = value.decode('utf-8')
            break
    
    # If no country found or country not in our breeds list, use random country
    if not cf_country or cf_country not in CHICKEN_BREEDS:
        country_code = random.choice(list(CHICKEN_BREEDS.keys()))
    else:
        country_code = cf_country
        
    # Get random breed for the country
    breed = random.choice(CHICKEN_BREEDS.get(country_code, CHICKEN_BREEDS["DEFAULT"]))
    
    return f"{country_code}-{breed}" 