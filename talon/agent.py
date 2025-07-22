import openai
import os
import json
from dotenv import load_dotenv

load_dotenv()

class TalonAgent:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        openai.api_key = self.api_key
        self.current_activity = "Monitoring travel platforms for disruptions."
    
    def get_current_activity(self):
        """Returns the current simulated activity of TALON."""
        return self.current_activity
    
    def is_trip_planning_request(self, message):
        """Detect if the message is a trip planning request"""
        trip_keywords = ['plan', 'trip', 'travel', 'book', 'flight', 'hotel', 'itinerary', 'vacation', 'business trip', 'conference', 'meeting']
        return any(keyword in message.lower() for keyword in trip_keywords)
    
    def process_message(self, message):
        """Processes a user message using OpenAI for an agentic response."""
        try:
            if self.is_trip_planning_request(message):
                return self.create_trip_plan(message)
            else:
                return self.general_chat(message)
        except Exception as e:
            print(f"Error processing message with OpenAI: {e}")
            return "I am currently experiencing a system issue. Please try again later."
    
    def create_trip_plan(self, message):
        """Create a detailed trip plan with structured data"""
        system_prompt = """You are TALON, an expert AI travel planning agent. When users request trip planning, provide detailed, actionable recommendations in a structured format.

ALWAYS include:
1. Specific flight options with times, airlines, and estimated prices
2. Hotel recommendations with locations, amenities, and rates
3. Activity suggestions with times and locations
4. Meeting room/venue options for business trips
5. Transportation between locations
6. A day-by-day timeline

Format your response as a detailed plan with specific recommendations, not generic statements. Include realistic details like:
- Flight numbers and departure times (use realistic airline codes like AA, UA, DL)
- Hotel names and addresses with real-sounding names
- Restaurant recommendations with cuisine types
- Meeting venue options with capacity and amenities
- Estimated costs in USD
- Booking websites (Expedia, Booking.com, etc.)

Structure your response with clear sections:
🛫 FLIGHTS
🏨 ACCOMMODATION  
🏢 MEETING VENUES (for business trips)
🍽️ DINING RECOMMENDATIONS
📅 DAY-BY-DAY ITINERARY
💰 ESTIMATED COSTS
🔗 BOOKING LINKS

Be specific and actionable. Users should be able to take immediate action on your recommendations."""

        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()
    
    def general_chat(self, message):
        """Handle general chat requests"""
        system_prompt = """You are TALON, an AI travel coordination agent that helps prevent travel disruptions and manages travel platforms. You monitor bookings, weather, prices, and logistics to ensure smooth travel experiences. Respond helpfully to general travel questions and coordination requests."""
        
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
