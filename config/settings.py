import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # API Keys
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")

    # Application Settings
    DEBUG_MODE = os.getenv("FLASK_DEBUG", "False").lower() in ('true', '1', 't')

# Initialize settings for the app to use
settings = Settings()
