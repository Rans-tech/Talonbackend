import requests
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class WeatherMonitor:
    """
    Weather monitoring using Open-Meteo API (free, no API key required).
    Provides current weather and forecasts for trip planning.
    """

    def __init__(self):
        self.geocode_url = "https://geocoding-api.open-meteo.com/v1/search"
        self.weather_url = "https://api.open-meteo.com/v1/forecast"

    US_STATE_MAP = {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
        "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
        "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
        "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
        "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
        "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
        "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
        "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
        "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
        "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
        "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
        "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
        "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
    }

    def _geocode_location(self, location: str) -> tuple:
        """Convert location name to lat/lon coordinates."""
        # Extract state hint from "City, ST" pattern
        state_hint = None
        parts = [p.strip() for p in location.split(",")]
        for part in parts:
            if len(part) == 2 and part.isupper() and part in self.US_STATE_MAP:
                state_hint = self.US_STATE_MAP[part]
                break

        # Build search terms: city name first, then full string
        search_terms = []
        if "," in location:
            search_terms.append(parts[0])
        search_terms.append(location)

        for search_term in search_terms:
            try:
                params = {"name": search_term, "count": 5, "language": "en", "format": "json"}
                response = requests.get(self.geocode_url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()

                if "results" in data and len(data["results"]) > 0:
                    # If we have a state hint, find the matching result
                    if state_hint:
                        for result in data["results"]:
                            if result.get("admin1", "").lower() == state_hint.lower():
                                admin1 = result.get("admin1", "")
                                name = result.get("name", search_term)
                                resolved = f"{name}, {admin1}" if admin1 else name
                                return (result["latitude"], result["longitude"], resolved)

                    # Fall back to first result
                    result = data["results"][0]
                    admin1 = result.get("admin1", "")
                    name = result.get("name", search_term)
                    resolved = f"{name}, {admin1}" if admin1 else name
                    return (result["latitude"], result["longitude"], resolved)
            except Exception as e:
                logger.error(f"Geocoding error for {search_term}: {e}")
                continue

        return None, None, None
    def get_status(self, location: str = "Orlando, FL") -> dict:
        """Fetches current weather data from Open-Meteo API."""
        lat, lon, resolved_name = self._geocode_location(location)

        if lat is None:
            return self._error_response(location, f"Could not find location: {location}")

        try:
            params = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "timezone": "auto"
            }

            response = requests.get(self.weather_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            current = data.get("current", {})

            temp = round(current.get("temperature_2m", 0))
            feels_like = round(current.get("apparent_temperature", temp))
            humidity = current.get("relative_humidity_2m", 0)
            wind_speed = round(current.get("wind_speed_10m", 0))
            weather_code = current.get("weather_code", 0)
            condition, icon = self._decode_weather_code(weather_code)

            alert = None
            if temp < 32:
                alert = "Freezing temperatures. Bundle up!"
            elif temp > 95:
                alert = "Extreme heat advisory. Stay hydrated!"
            elif weather_code in [61, 63, 65, 80, 81, 82]:
                alert = f"Weather alert: {condition}"
            elif weather_code in [71, 73, 75, 77, 85, 86]:
                alert = f"Snow expected: {condition}"
            elif weather_code in [95, 96, 99]:
                alert = f"Storm warning: {condition}"

            return {
                "location": resolved_name or location,
                "status": "active_monitoring",
                "alert": alert,
                "temperature": temp,
                "temperature_display": f"{temp}°F",
                "feels_like": feels_like,
                "feels_like_display": f"{feels_like}°F",
                "condition": condition,
                "icon": icon,
                "humidity": humidity,
                "humidity_display": f"{humidity}%",
                "wind_speed": wind_speed,
                "wind_display": f"{wind_speed} mph",
                "coordinates": {"lat": lat, "lon": lon}
            }

        except requests.exceptions.Timeout:
            return self._error_response(location, "Weather service timeout.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching weather for {location}: {e}")
            return self._error_response(location, "Unable to fetch weather data")
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"Error parsing weather data for {location}: {e}")
            return self._error_response(location, "Error parsing weather data")

    def get_forecast(self, location: str, start_date: str = None, end_date: str = None) -> dict:
        """Fetches weather forecast for trip dates."""
        lat, lon, resolved_name = self._geocode_location(location)

        if lat is None:
            return {"location": location, "status": "error", "daily": []}

        try:
            params = {
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
                "temperature_unit": "fahrenheit",
                "timezone": "auto"
            }
            if start_date:
                params["start_date"] = start_date
            if end_date:
                params["end_date"] = end_date

            response = requests.get(self.weather_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            daily = data.get("daily", {})
            days = []

            if "time" in daily:
                num_days = len(daily["time"])
                for i, date in enumerate(daily["time"]):
                    wc = daily.get("weather_code", [0] * num_days)[i]
                    cond, ico = self._decode_weather_code(wc)
                    days.append({
                        "date": date,
                        "temp_max": round(daily.get("temperature_2m_max", [0] * num_days)[i]),
                        "temp_min": round(daily.get("temperature_2m_min", [0] * num_days)[i]),
                        "precipitation_probability": daily.get("precipitation_probability_max", [0] * num_days)[i],
                        "weather_code": wc,
                        "condition": cond,
                        "icon": ico
                    })

            return {"location": resolved_name or location, "status": "success", "daily": days}
        except Exception as e:
            logger.error(f"Error fetching forecast for {location}: {e}")
            return {"location": location, "status": "error", "daily": []}

    def _decode_weather_code(self, code: int) -> tuple:
        """Convert WMO weather code to description and emoji icon."""
        codes = {
            0: ("Clear sky", "☀️"), 1: ("Mainly clear", "🌤️"), 2: ("Partly cloudy", "⛅"),
            3: ("Overcast", "☁️"), 45: ("Foggy", "🌫️"), 48: ("Rime fog", "🌫️"),
            51: ("Light drizzle", "🌧️"), 53: ("Drizzle", "🌧️"), 55: ("Dense drizzle", "🌧️"),
            61: ("Slight rain", "🌧️"), 63: ("Moderate rain", "🌧️"), 65: ("Heavy rain", "🌧️"),
            71: ("Slight snow", "🌨️"), 73: ("Moderate snow", "🌨️"), 75: ("Heavy snow", "🌨️"),
            77: ("Snow grains", "🌨️"), 80: ("Rain showers", "🌦️"), 81: ("Moderate showers", "🌦️"),
            82: ("Violent showers", "🌦️"), 85: ("Snow showers", "🌨️"), 86: ("Heavy snow showers", "🌨️"),
            95: ("Thunderstorm", "⛈️"), 96: ("Thunderstorm + hail", "⛈️"), 99: ("Severe storm", "⛈️"),
        }
        return codes.get(code, ("Unknown", "❓"))

    def _error_response(self, location: str, message: str) -> dict:
        """Returns a standardized error response."""
        return {
            "location": location, "status": "error", "alert": message,
            "temperature": None, "temperature_display": "--°F",
            "condition": "Unknown", "icon": None,
            "humidity": None, "wind_speed": None, "feels_like": None
        }


class PriceMonitor:
    def get_status(self):
        """Returns simulated price monitoring status."""
        return {
            "status": "active_monitoring",
            "tracked_items": 124,
            "latest_finding": "Found 15% price drop on Le Meurice hotel for selected dates.",
            "platforms": ["Expedia", "Booking.com", "Hotels.com", "Marriott Bonvoy"]
        }
