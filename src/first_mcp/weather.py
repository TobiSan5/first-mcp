"""
Weather API integration using Yr.no (MET Norway) API

Based on:
- https://developer.yr.no/doc/GettingStarted/
- https://developer.yr.no/doc/TermsOfService/

Terms of Service Requirements:
- Attribution required under CC BY 4.0 license
- Rate limit: 20 requests/second max
- Use proper User-Agent with contact info
- Cache responses and respect Expires headers
"""

import requests
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import os


class WeatherAPI:
    """
    Yr.no weather API client following their terms of service.
    
    Attribution: Weather data provided by MET Norway under CC BY 4.0 license.
    """
    
    BASE_URL = "https://api.met.no/weatherapi"
    
    def __init__(self, user_agent: str = "FirstMCP/1.0 (test application)"):
        """
        Initialize weather API client.
        
        Args:
            user_agent: User-Agent string with app name and contact info
        """
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept-Encoding': 'gzip'
        })
    
    def _round_coordinates(self, lat: float, lon: float) -> tuple[float, float]:
        """
        Round coordinates to 4 decimal places as required by API.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Tuple of rounded (lat, lon)
        """
        return round(lat, 4), round(lon, 4)
    
    def get_forecast(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Get weather forecast for given coordinates.
        
        Args:
            lat: Latitude (-90 to 90)
            lon: Longitude (-180 to 180)
            
        Returns:
            Weather forecast data
            
        Raises:
            requests.RequestException: If API request fails
        """
        lat, lon = self._round_coordinates(lat, lon)
        
        url = f"{self.BASE_URL}/locationforecast/2.0/compact"
        params = {
            'lat': lat,
            'lon': lon
        }
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            # Store expires header for caching info
            expires = response.headers.get('Expires')
            if expires:
                print(f"API response expires: {expires}")
            
            return response.json()
            
        except requests.RequestException as e:
            raise Exception(f"Weather API request failed: {e}")
    
    def get_current_weather(self, lat: float, lon: float) -> Dict[str, Any]:
        """
        Get current weather conditions for given coordinates.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Current weather data with simplified format
        """
        forecast_data = self.get_forecast(lat, lon)
        
        # Extract current conditions from the forecast
        properties = forecast_data.get('properties', {})
        timeseries = properties.get('timeseries', [])
        
        if not timeseries:
            return {"error": "No weather data available"}
        
        # Get the first (current) time period
        current = timeseries[0]
        instant_details = current.get('data', {}).get('instant', {}).get('details', {})
        
        # Try to get next 1 hour summary if available
        next_1h = current.get('data', {}).get('next_1_hours', {})
        summary = next_1h.get('summary', {})
        details = next_1h.get('details', {})
        
        return {
            "location": {
                "latitude": lat,
                "longitude": lon
            },
            "time": current.get('time'),
            "temperature": instant_details.get('air_temperature'),
            "humidity": instant_details.get('relative_humidity'),
            "pressure": instant_details.get('air_pressure_at_sea_level'),
            "wind_speed": instant_details.get('wind_speed'),
            "wind_direction": instant_details.get('wind_from_direction'),
            "cloud_cover": instant_details.get('cloud_area_fraction'),
            "precipitation_1h": details.get('precipitation_amount'),
            "weather_symbol": summary.get('symbol_code'),
            "attribution": "Weather data provided by MET Norway under CC BY 4.0 license"
        }


class GeocodingAPI:
    """
    OpenWeatherMap geocoding API client.
    
    Requires OPENWEATHERMAPORG_API_KEY environment variable.
    """
    
    BASE_URL = "http://api.openweathermap.org/geo/1.0"
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize geocoding API client.
        
        Args:
            api_key: OpenWeatherMap API key (or uses env var)
        """
        self.api_key = api_key or os.getenv('OPENWEATHERMAPORG_API_KEY')
        if not self.api_key:
            raise ValueError("OpenWeatherMap API key required. Set OPENWEATHERMAPORG_API_KEY environment variable.")
        
        self.session = requests.Session()
    
    def geocode(self, location: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get coordinates for a location name.
        
        Args:
            location: Location name (e.g., "Oslo,,NO" or "London,GB")
            limit: Maximum number of results (1-5)
            
        Returns:
            List of location objects with coordinates
            
        Raises:
            requests.RequestException: If API request fails
        """
        url = f"{self.BASE_URL}/direct"
        params = {
            'q': location,
            'limit': min(limit, 5),
            'appid': self.api_key
        }
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            return response.json()
            
        except requests.RequestException as e:
            raise Exception(f"Geocoding API request failed: {e}")
    
    def get_coordinates(self, location: str) -> Optional[tuple[float, float]]:
        """
        Get the first matching coordinates for a location.
        
        Args:
            location: Location name
            
        Returns:
            Tuple of (latitude, longitude) or None if not found
        """
        results = self.geocode(location, limit=1)
        
        if results:
            first_result = results[0]
            return first_result.get('lat'), first_result.get('lon')
        
        return None


def test_weather_api():
    """Test the weather API with geocoding for Oslo, Norway."""
    location = "Oslo,,NO"
    
    try:
        # Step 1: Geocode the location
        print("Testing Geocoding API...")
        geocoding = GeocodingAPI()
        
        print(f"Geocoding location: {location}")
        coordinates = geocoding.get_coordinates(location)
        
        if not coordinates:
            print(f"Could not find coordinates for {location}")
            return
        
        lat, lon = coordinates
        print(f"Found coordinates: {lat}, {lon}")
        
        # Show full geocoding results
        geocoding_results = geocoding.geocode(location, limit=3)
        print(f"\nGeocoding results:")
        for i, result in enumerate(geocoding_results):
            print(f"{i+1}. {result.get('name', 'Unknown')}, {result.get('country', 'Unknown')}")
            print(f"   Coordinates: {result.get('lat')}, {result.get('lon')}")
            if result.get('state'):
                print(f"   State: {result.get('state')}")
        
        # Step 2: Get weather for the geocoded coordinates
        print(f"\nTesting Weather API...")
        weather = WeatherAPI()
        
        print(f"Getting weather for {location} at coordinates: {lat}, {lon}")
        current_weather = weather.get_current_weather(lat, lon)
        
        print("\nCurrent Weather in Oslo:")
        print(json.dumps(current_weather, indent=2))
        
        print("\nFull forecast sample (first entry):")
        forecast = weather.get_forecast(lat, lon)
        if forecast.get('properties', {}).get('timeseries'):
            first_entry = forecast['properties']['timeseries'][0]
            print(json.dumps(first_entry, indent=2))
            
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure OPENWEATHERMAPORG_API_KEY environment variable is set!")


if __name__ == "__main__":
    test_weather_api()