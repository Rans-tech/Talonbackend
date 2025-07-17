import requests
import os
from dotenv import load_dotenv

load_dotenv()

class WeatherMonitor:
    def __init__(self):
        self.api_key = os.getenv("OPENWEATHERMAP_API_KEY")

    def get_status(self, location="Orlando, FL"):
        """Returns simulated weather monitoring status."""
        if not self.api_key:
            return {
                "location": location,
                "status": "active_monitoring",
                "alert": "API Key for OpenWeatherMap not configured. Using mock data.",
                "temperature": "78°F",
                "condition": "Partly Cloudy"
            }
        return {
            "location": location,
            "status": "active_monitoring",
            "alert": "No critical weather alerts.",
            "temperature": "82°F",
            "condition": "Scattered thunderstorms expected in 3 hours."
        }

class PriceMonitor:
    def get_status(self):
        """Returns simulated price monitoring status."""
        return {
            "status": "active_monitoring",
            "tracked_items": 124,
            "latest_finding": "Found 15% price drop on 'Le Meurice' hotel for selected dates.",
            "platforms": ["Expedia", "Booking.com", "Hotels.com", "Marriott Bonvoy"]
        }
