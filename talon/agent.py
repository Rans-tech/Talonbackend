import openai
import os
from dotenv import load_dotenv

load_dotenv()

class TalonAgent:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables.")
        openai.api_key = self.api_key
        self.current_activity = "Monitoring travel platforms for disruptions."

    def get_current_activity(self):
        """Returns the current simulated activity of TALON."""
        return self.current_activity

    def process_message(self, message):
        """Processes a user message using OpenAI for an agentic response."""
        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are TALON, an AI travel agent that unifies fragmented travel systems. Your goal is to identify problems, find solutions, and coordinate across platforms. Be proactive and intelligent."},
                    {"role": "user", "content": message}
                ],
                max_tokens=150
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error processing message with OpenAI: {e}")
            return "I am currently experiencing a system issue. Please try again later."
