"""
Weather MCP Server - A Model Context Protocol server for weather data.

This module implements an MCP server that provides weather information for US ZIP codes.
It exposes a single tool that fetches current weather conditions by:
1. Converting ZIP codes to geographic coordinates using Zippopotam.us API
2. Fetching weather data from Open-Meteo API

No API keys are required for either service.
"""

# Standard library imports for async operations, logging, and type hints
import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

# Third-party imports
import httpx  # Modern async HTTP client for API requests
from mcp.server.fastmcp import FastMCP  # MCP SDK for building protocol-compliant servers


# Configure logging to stderr (stdout is reserved for MCP protocol messages)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("weather-mcp")

# Initialize the MCP server instance
# - "Weather Demo" is the server name exposed to MCP clients
# - json_response=True ensures all responses are JSON-serializable
mcp = FastMCP("Weather Demo", json_response=True)


@dataclass(frozen=True)
class Geo:
    """
    Geographic location information for a ZIP code.
    
    This immutable dataclass stores the location details returned from the
    geocoding API. The frozen=True parameter makes instances immutable,
    preventing accidental modifications.
    
    Attributes:
        place_name: The city or place name associated with the ZIP code
        latitude: Geographic latitude in decimal degrees
        longitude: Geographic longitude in decimal degrees
        state: US state abbreviation (e.g., "MA" for Massachusetts), can be None
    """
    place_name: str
    latitude: float
    longitude: float
    state: Optional[str]


async def _zip_to_geo(zip_code: str, *, country: str = "us") -> Geo:
    """
    Convert a ZIP code to geographic coordinates using the Zippopotam.us API.
    
    This is a helper function (prefixed with _) that performs geocoding without
    requiring an API key. It makes an HTTP request to Zippopotam.us and parses
    the response to extract location details.
    
    Args:
        zip_code: The postal code to look up
        country: Country code (keyword-only argument, defaults to "us")
    
    Returns:
        Geo object containing place name, coordinates, and state
        
    Raises:
        ValueError: If the ZIP code is not found or the response is invalid
        httpx.HTTPStatusError: If the API request fails
    """
    # Build the API URL for the geocoding request
    url = f"https://api.zippopotam.us/{country}/{zip_code}"
    
    # Create an async HTTP client with a 15-second timeout to prevent hanging
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        
        # Handle 404 (not found) as a user-friendly error
        if resp.status_code == 404:
            raise ValueError(f"Unknown ZIP code: {zip_code}")
        
        # Raise an exception for any other HTTP error status codes
        resp.raise_for_status()
        
        # Parse the JSON response
        data = resp.json()

    # Extract the list of places from the response
    # Use .get() with a default to safely handle missing keys
    places = data.get("places") or []
    if not places:
        raise ValueError(f"No places found for ZIP code: {zip_code}")

    # Use the first place in the list (most ZIP codes map to one location)
    place = places[0]
    place_name = place.get("place name") or ""
    state = place.get("state")

    # Parse latitude and longitude as floats
    # Wrap in try/except to handle unexpected data formats gracefully
    try:
        lat = float(place["latitude"])
        lon = float(place["longitude"])
    except Exception as exc:
        raise ValueError("Unexpected geocoding response") from exc

    # Return the structured Geo object
    return Geo(place_name=place_name, latitude=lat, longitude=lon, state=state)


async def _current_weather(lat: float, lon: float) -> Dict[str, Any]:
    """
    Fetch current weather conditions from the Open-Meteo API.
    
    This helper function queries the Open-Meteo forecast API to retrieve
    current weather observations for a specific location. No API key is required.
    
    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees
    
    Returns:
        Dictionary containing the full API response with current weather data
        
    Raises:
        httpx.HTTPStatusError: If the API request fails
    """
    # Open-Meteo API endpoint for weather forecasts
    url = "https://api.open-meteo.com/v1/forecast"
    
    # Configure the API request parameters
    params = {
        "latitude": lat,
        "longitude": lon,
        # Request specific current weather variables:
        # - temperature_2m: Temperature at 2 meters above ground
        # - relative_humidity_2m: Humidity percentage at 2 meters
        # - apparent_temperature: "Feels like" temperature
        # - precipitation: Current precipitation amount
        # - weather_code: WMO weather code (0=clear, 1=mainly clear, etc.)
        # - wind_speed_10m: Wind speed at 10 meters above ground
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
        # Use imperial units for US audiences
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        # Automatically detect timezone based on coordinates
        "timezone": "auto",
    }

    # Make the async HTTP request with a 15-second timeout
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()  # Raise exception for HTTP errors
        return resp.json()  # Return the full weather data response


@mcp.tool()
async def get_weather(zip_code: str) -> Dict[str, Any]:
    """Get current weather for a US ZIP code.

    This demo uses:
    - Zippopotam.us to convert ZIP -> lat/lon (no API key)
    - Open-Meteo to fetch current conditions (no API key)

    Args:
        zip_code: 5-digit US ZIP code as a string.

    Returns:
        A JSON-serializable object with location + current weather.
    """
    # Validate and clean the input ZIP code
    # Strip whitespace and ensure it's a 5-digit number
    zip_code = (zip_code or "").strip()
    if not zip_code.isdigit() or len(zip_code) != 5:
        raise ValueError("zip_code must be a 5-digit string")

    # Step 1: Convert ZIP code to geographic coordinates
    geo = await _zip_to_geo(zip_code)
    
    # Step 2: Fetch current weather for those coordinates
    weather = await _current_weather(geo.latitude, geo.longitude)
    
    # Extract the "current" section from the weather API response
    current = weather.get("current") or {}

    # Build and return a structured response with all relevant information
    return {
        # Original input for reference
        "zip_code": zip_code,
        
        # Location details from the geocoding step
        "location": {
            "place_name": geo.place_name,
            "state": geo.state,
            "latitude": geo.latitude,
            "longitude": geo.longitude,
        },
        
        # Document the units used for all measurements
        "units": {
            "temperature": "F",
            "wind_speed": "mph",
            "precipitation": "inch",
        },
        
        # Current weather observations
        "observed": {
            "time": current.get("time"),                            # Observation timestamp
            "temperature_2m": current.get("temperature_2m"),        # Actual temperature
            "apparent_temperature": current.get("apparent_temperature"),  # Feels like temp
            "relative_humidity_2m": current.get("relative_humidity_2m"),  # Humidity %
            "precipitation": current.get("precipitation"),          # Precipitation amount
            "weather_code": current.get("weather_code"),           # WMO weather code
            "wind_speed_10m": current.get("wind_speed_10m"),       # Wind speed
        },
        
        # Attribute the data sources for transparency
        "source": {
            "geocoding": "https://api.zippopotam.us",
            "forecast": "https://api.open-meteo.com",
        },
    }


def main() -> None:
    """
    Start the MCP server in stdio (standard input/output) mode.
    
    This function is the entry point for the server. It configures the MCP
    server to communicate over stdio, which is the standard transport for
    local MCP servers that are launched as child processes by MCP clients
    (like VS Code).
    
    Important: stdout is reserved for MCP protocol messages. All logging
    must go to stderr (which Python's logging module does by default).
    """
    # Log startup message (goes to stderr, not stdout)
    logger.info("Starting MCP server (stdio)")
    
    # Start the MCP server using stdio transport
    # This will block and handle incoming MCP requests until terminated
    mcp.run(transport="stdio")


# Standard Python idiom: execute main() only when run as a script
# This allows the module to be imported without starting the server
if __name__ == "__main__":
    main()
