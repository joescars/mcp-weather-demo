import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
from mcp.server.fastmcp import FastMCP


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("weather-mcp")

mcp = FastMCP("Weather Demo", json_response=True)


@dataclass(frozen=True)
class Geo:
    place_name: str
    latitude: float
    longitude: float
    state: Optional[str]


async def _zip_to_geo(zip_code: str, *, country: str = "us") -> Geo:
    url = f"https://api.zippopotam.us/{country}/{zip_code}"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        if resp.status_code == 404:
            raise ValueError(f"Unknown ZIP code: {zip_code}")
        resp.raise_for_status()
        data = resp.json()

    places = data.get("places") or []
    if not places:
        raise ValueError(f"No places found for ZIP code: {zip_code}")

    place = places[0]
    place_name = place.get("place name") or ""
    state = place.get("state")

    try:
        lat = float(place["latitude"])
        lon = float(place["longitude"])
    except Exception as exc:
        raise ValueError("Unexpected geocoding response") from exc

    return Geo(place_name=place_name, latitude=lat, longitude=lon, state=state)


async def _current_weather(lat: float, lon: float) -> Dict[str, Any]:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "auto",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


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

    zip_code = (zip_code or "").strip()
    if not zip_code.isdigit() or len(zip_code) != 5:
        raise ValueError("zip_code must be a 5-digit string")

    geo = await _zip_to_geo(zip_code)
    weather = await _current_weather(geo.latitude, geo.longitude)
    current = weather.get("current") or {}

    return {
        "zip_code": zip_code,
        "location": {
            "place_name": geo.place_name,
            "state": geo.state,
            "latitude": geo.latitude,
            "longitude": geo.longitude,
        },
        "units": {
            "temperature": "F",
            "wind_speed": "mph",
            "precipitation": "inch",
        },
        "observed": {
            "time": current.get("time"),
            "temperature_2m": current.get("temperature_2m"),
            "apparent_temperature": current.get("apparent_temperature"),
            "relative_humidity_2m": current.get("relative_humidity_2m"),
            "precipitation": current.get("precipitation"),
            "weather_code": current.get("weather_code"),
            "wind_speed_10m": current.get("wind_speed_10m"),
        },
        "source": {
            "geocoding": "https://api.zippopotam.us",
            "forecast": "https://api.open-meteo.com",
        },
    }


def main() -> None:
    # MCP stdio servers must keep stdout clean for protocol messages.
    # Python logging defaults to stderr, so this is safe.
    logger.info("Starting MCP server (stdio)")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
