import openai
import os
import base64
import json
from dotenv import load_dotenv

load_dotenv()

class DocumentParser:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        openai.api_key = self.api_key

    def parse_travel_document(self, file_content, file_type):
        """
        Parse a travel document (PDF, image) and extract structured data
        using OpenAI Vision API

        Args:
            file_content: Base64 encoded file content
            file_type: MIME type of the file

        Returns:
            dict: Structured travel data extracted from the document
        """
        try:
            print(f"Parsing document with MIME type: {file_type}")

            # Check if file type is supported
            supported_image_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']

            if file_type not in supported_image_types:
                return {
                    "success": False,
                    "error": f"Unsupported file type: {file_type}. Please upload an image file (JPG, PNG, GIF, or WebP). For PDFs, please take a screenshot or convert to an image first."
                }
            # Create the system prompt for structured extraction
            system_prompt = """You are a travel document parser. Extract ALL relevant information from travel documents (flight confirmations, hotel bookings, car rentals, etc.) into structured JSON format.

IMPORTANT: Extract EVERY piece of information you can find. Be thorough and detailed.

Return ONLY valid JSON in this exact format:
{
  "document_type": "flight|hotel|car_rental|activity|dining|transport|other",
  "elements": [
    {
      "type": "flight|hotel|activity|dining|transport|other",
      "title": "Brief descriptive title",
      "start_datetime": "ISO 8601 format (YYYY-MM-DDTHH:MM:SS) or null",
      "end_datetime": "ISO 8601 format (YYYY-MM-DDTHH:MM:SS) or null",
      "location": "Full location string (address, city, airport code, etc.)",
      "confirmation_number": "Confirmation/booking number or null",
      "price": numeric value only (no currency symbols) or null,
      "currency": "USD|EUR|GBP etc or null",
      "status": "confirmed|pending|cancelled",
      "details": {
        // For flights: airline, flight_number, seat, gate, terminal, baggage_allowance, class
        // For hotels: hotel_name, room_type, check_in, check_out, guests, amenities
        // For cars: company, vehicle_type, pickup_location, dropoff_location, driver_name
        // For activities: venue, description, attendees, category
        // For dining: restaurant_name, cuisine, reservation_time, party_size
        // Any other relevant details specific to this document type
      }
    }
  ],
  "metadata": {
    "traveler_name": "Name of the traveler or null",
    "total_cost": numeric total or null,
    "booking_date": "YYYY-MM-DD or null",
    "vendor": "Company/airline/hotel name or null"
  }
}

CRITICAL RULES:
1. Extract ALL information visible in the document
2. If a flight has multiple segments, create separate elements for each
3. For dates/times, convert to ISO 8601 format (e.g., "2025-11-07T14:30:00")
4. For prices, extract only numeric values (remove $, €, etc symbols)
5. Be specific with locations (include airport codes, full addresses)
6. Include all details in the "details" object
7. Return ONLY the JSON object, no additional text"""

            # Prepare the message for Vision API
            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract all travel information from this document and return structured JSON."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{file_type};base64,{file_content}"
                            }
                        }
                    ]
                }
            ]

            # Call OpenAI Vision API
            response = openai.chat.completions.create(
                model="gpt-4o",  # GPT-4 Vision model
                messages=messages,
                max_tokens=2000,
                temperature=0  # Low temperature for consistent extraction
            )

            # Parse the response
            content = response.choices[0].message.content.strip()

            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]  # Remove ```json
            if content.startswith("```"):
                content = content[3:]  # Remove ```
            if content.endswith("```"):
                content = content[:-3]  # Remove closing ```
            content = content.strip()

            # Parse JSON
            parsed_data = json.loads(content)

            return {
                "success": True,
                "data": parsed_data
            }

        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Raw content: {content}")
            return {
                "success": False,
                "error": "Failed to parse document structure",
                "raw_response": content
            }
        except Exception as e:
            print(f"Error parsing document: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def parse_travel_text(self, text_content):
        """
        Parse pasted email/text confirmation and extract structured data
        using OpenAI GPT-4

        Args:
            text_content: Raw text or HTML from pasted email

        Returns:
            dict: Structured travel data extracted from the text
        """
        try:
            print(f"Parsing text content (length: {len(text_content)} chars)")

            # Create the system prompt for structured extraction
            system_prompt = """You are a travel document parser. Extract ALL relevant information from travel confirmation emails/text into structured JSON format.

IMPORTANT: Extract EVERY piece of information you can find. Be thorough and detailed.

Return ONLY valid JSON in this exact format:
{
  "document_type": "flight|hotel|car_rental|activity|dining|transport|other",
  "elements": [
    {
      "type": "flight|hotel|activity|dining|transport|other",
      "title": "Brief descriptive title",
      "start_datetime": "ISO 8601 format (YYYY-MM-DDTHH:MM:SS) or null",
      "end_datetime": "ISO 8601 format (YYYY-MM-DDTHH:MM:SS) or null",
      "location": "Full location string (address, city, airport code, etc.)",
      "confirmation_number": "Confirmation/booking number or null",
      "price": numeric value only (no currency symbols) or null,
      "currency": "USD|EUR|GBP etc or null",
      "status": "confirmed|pending|cancelled",
      "details": {
        // For flights: airline, flight_number, seat, gate, terminal, baggage_allowance, class, origin_airport, destination_airport
        // For hotels: hotel_name, room_type, check_in_time, check_out_time, guests, amenities, address, phone
        // For cars: company, vehicle_type, pickup_location, dropoff_location, driver_name
        // For activities: venue, description, attendees, category
        // For dining: restaurant_name, cuisine, reservation_time, party_size
        // Any other relevant details from the confirmation
      }
    }
  ],
  "metadata": {
    "traveler_name": "Name of the traveler or null",
    "total_cost": numeric total or null,
    "booking_date": "YYYY-MM-DD or null",
    "vendor": "Company/airline/hotel name or null"
  }
}

CRITICAL RULES:
1. Extract ALL information visible in the text/email with 100% accuracy
2. **FLIGHTS**: ALWAYS create SEPARATE elements for EACH flight leg/segment
   - Round-trip = 2 elements (outbound + return)
   - Connecting flights = separate element for each leg
   - Example: "Flight AA100 DFW->MCO on Nov 7" and "Flight AA200 MCO->DFW on Nov 12" = 2 separate elements
3. **TIMES**: Extract exact departure and arrival times with extreme precision
   - start_datetime = DEPARTURE time (when plane leaves) in LOCAL TIME
   - end_datetime = ARRIVAL time (when plane lands) in LOCAL TIME
   - Format: "2025-11-07T14:30:00" (YYYY-MM-DDTHH:MM:SS) - NO TIMEZONE SUFFIX
   - If time shows "2:30 PM", convert to "14:30:00"
   - DO NOT include +00:00 or any timezone indicator in the datetime string
   - These times are in the LOCAL timezone of the location
4. **LOCATIONS**: For flights, use airport codes and full names
   - Location format for flights: "From [Origin Airport Code] to [Destination Airport Code]"
   - Example: "From DFW (Dallas) to MCO (Orlando)"
5. For prices, extract only numeric values (remove $, €, etc symbols)
6. **CONFIRMATION NUMBERS**: CRITICAL - Extract confirmation/booking numbers
   - ALL elements from the SAME booking share the SAME confirmation number
   - For round-trip flights: BOTH flights get the SAME confirmation number
   - Look for: "Confirmation #", "Booking Reference", "Confirmation Number", etc.
   - Include this in EVERY element from the same booking
7. Include all other details like contact info, seat assignments, amenities
8. **TITLES**: Make descriptive
   - Flight: "[Airline] [Flight#] from [Origin] to [Dest]"
   - Hotel: "[Hotel Name] Stay"
9. Return ONLY the JSON object, no additional text
10. If the text doesn't contain travel information, return document_type: "other" with empty elements array

FLIGHT PARSING EXAMPLE:
If you see:
"Confirmation # ABC123
Outbound: AA1234 DFW-MCO Departs 10:30 AM Nov 7, Arrives 2:15 PM
Return: AA5678 MCO-DFW Departs 6:00 PM Nov 12, Arrives 8:45 PM"

You MUST create 2 separate flight elements WITH THE SAME CONFIRMATION NUMBER:
Element 1: Outbound flight
  - start_datetime: 2025-11-07T10:30:00 (NO timezone)
  - end_datetime: 2025-11-07T14:15:00 (NO timezone)
  - confirmation_number: "ABC123"
Element 2: Return flight
  - start_datetime: 2025-11-12T18:00:00 (NO timezone)
  - end_datetime: 2025-11-12T20:45:00 (NO timezone)
  - confirmation_number: "ABC123" (SAME as outbound)"""

            # Call OpenAI GPT-4 (text model, not vision)
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Extract all travel information from this confirmation:\n\n{text_content}"}
                ],
                max_tokens=2000,
                temperature=0  # Low temperature for consistent extraction
            )

            # Parse the response
            content = response.choices[0].message.content.strip()

            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]  # Remove ```json
            if content.startswith("```"):
                content = content[3:]  # Remove ```
            if content.endswith("```"):
                content = content[:-3]  # Remove closing ```
            content = content.strip()

            # Parse JSON
            parsed_data = json.loads(content)

            # Debug logging for time extraction
            print("=== GPT-4 RAW JSON ===")
            print(json.dumps(parsed_data, indent=2))
            print("======================")
            print("=== GPT-4 PARSED DATA ===")
            if 'elements' in parsed_data:
                for elem in parsed_data['elements']:
                    print(f"Element: {elem.get('title')}")
                    print(f"  Type: {elem.get('type')}")
                    print(f"  start_datetime: {elem.get('start_datetime')}")
                    print(f"  end_datetime: {elem.get('end_datetime')}")
                    print(f"  location: {elem.get('location')}")
                    print(f"  confirmation_number: {elem.get('confirmation_number')}")
            print("========================")

            return {
                "success": True,
                "data": parsed_data
            }

        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Raw content: {content}")
            return {
                "success": False,
                "error": "Failed to parse text structure",
                "raw_response": content
            }
        except Exception as e:
            print(f"Error parsing text: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def validate_element_data(self, element):
        """
        Validate and clean element data before saving to database

        Args:
            element: Dict containing element data

        Returns:
            dict: Cleaned and validated element data
        """
        # Ensure required fields exist
        required_fields = ['type', 'title']
        for field in required_fields:
            if field not in element:
                raise ValueError(f"Missing required field: {field}")

        # Validate type
        valid_types = ['flight', 'hotel', 'activity', 'dining', 'transport', 'other']
        if element['type'] not in valid_types:
            element['type'] = 'other'

        # Ensure status is valid
        valid_statuses = ['confirmed', 'pending', 'cancelled', 'completed']
        if 'status' not in element or element['status'] not in valid_statuses:
            element['status'] = 'confirmed'

        # Ensure details is a dict
        if 'details' not in element or not isinstance(element['details'], dict):
            element['details'] = {}

        return element

    def parse_receipt(self, file_content, file_type):
        """
        Parse a receipt image and extract expense data for auto-filling forms
        
        Args:
            file_content: Base64 encoded image content
            file_type: MIME type of the image
            
        Returns:
            dict: Structured expense data (amount, merchant, date, category)
        """
        try:
            print(f"Parsing receipt with MIME type: {file_type}")
            
            # Check if file type is supported
            supported_image_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
            
            if file_type not in supported_image_types:
                return {
                    "success": False,
                    "error": f"Unsupported file type: {file_type}. Please upload an image file."
                }
            
            # Create receipt-specific prompt
            system_prompt = """You are a receipt parser. Extract expense information from receipt images.

Return ONLY valid JSON in this exact format:
{
  "amount": 45.67,
  "merchant": "Restaurant/Store Name",
  "date": "2025-11-05",
  "category": "food_dining|accommodation|transportation|tours_activities|shopping|other",
  "description": "Brief description of purchase",
  "currency": "USD"
}

Category guidelines:
- food_dining: Restaurants, cafes, bars, food delivery
- accommodation: Hotels, Airbnb, lodging
- transportation: Uber, taxi, gas, parking, public transit
- tours_activities: Tours, attractions, entertainment, tickets
- shopping: Retail purchases, souvenirs, clothing
- other: Everything else

CRITICAL RULES:
1. Extract the TOTAL amount (not subtotal)
2. Use merchant/restaurant name from receipt
3. Convert date to YYYY-MM-DD format
4. Choose the most appropriate category
5. Return ONLY the JSON object, no additional text"""
            
            # Prepare the Vision API message
            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Extract expense information from this receipt and return structured JSON."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{file_type};base64,{file_content}"
                            }
                        }
                    ]
                }
            ]
            
            # Call OpenAI Vision API
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=500,
                temperature=0.1
            )
            
            # Extract and parse the response
            content = response.choices[0].message.content
            print(f"OpenAI receipt response: {content}")
            
            # Clean up response if needed
            content = content.strip()
            if content.startswith('```json'):
                content = content[7:]
            if content.startswith('```'):
                content = content[3:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            
            # Parse JSON
            parsed_data = json.loads(content)
            
            return {
                "success": True,
                "data": parsed_data
            }
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            return {
                "success": False,
                "error": f"Failed to parse AI response as JSON: {str(e)}"
            }
        except Exception as e:
            print(f"Error parsing receipt: {e}")
            return {
                "success": False,
                "error": str(e)
            }
