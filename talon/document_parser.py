import openai
import os
import base64
import json
import io
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Try to import PDF libraries
try:
    import fitz  # PyMuPDF
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    print("Warning: PyMuPDF not installed. PDF support disabled. Install with: pip install pymupdf")

class DocumentParser:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        openai.api_key = self.api_key

        # Load travel knowledge base
        self.knowledge_base = self._load_knowledge_base()

    def _load_knowledge_base(self):
        """Load travel intelligence knowledge base"""
        try:
            kb_path = Path(__file__).parent / 'travel_knowledge_base.json'
            with open(kb_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Could not load knowledge base: {e}")
            return {}

    def _extract_pdf_images(self, pdf_content_base64):
        """
        Extract images from PDF pages for Vision API processing

        Args:
            pdf_content_base64: Base64 encoded PDF content

        Returns:
            list: List of base64 encoded PNG images (one per page)
        """
        if not PDF_SUPPORT:
            return None

        try:
            # Decode base64 PDF content
            pdf_bytes = base64.b64decode(pdf_content_base64)

            # Open PDF with PyMuPDF
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            images = []
            # Convert each page to image (limit to first 5 pages for performance)
            for page_num in range(min(len(doc), 5)):
                page = doc[page_num]
                # Render page to image (300 DPI for good quality)
                pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))

                # Convert to PNG bytes
                img_bytes = pix.tobytes("png")

                # Convert to base64
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')
                images.append(img_base64)

            doc.close()
            return images

        except Exception as e:
            print(f"Error extracting PDF images: {e}")
            return None

    def _extract_pdf_text(self, pdf_content_base64):
        """
        Extract text from all PDF pages - much more efficient than images.
        This is the preferred method for most travel confirmations.
        """
        if not PDF_SUPPORT:
            return None

        try:
            import base64
            pdf_bytes = base64.b64decode(pdf_content_base64)
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")

            all_text = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                if text.strip():
                    all_text.append(f"\n--- PAGE {page_num + 1} ---\n{text}")

            page_count = len(doc)
            doc.close()
            combined = "\n".join(all_text).strip()
            print(f"PDF text extraction: {page_count} pages, {len(combined)} chars")
            if len(combined) > 100:
                print(f"Text preview (first 500 chars): {combined[:500]}")
                return combined
            else:
                print(f"Text extraction insufficient: only {len(combined)} chars")
                return None

        except Exception as e:
            print(f"Error extracting PDF text: {e}")
            return None

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
            supported_pdf_types = ['application/pdf']

            # Handle PDF files - TEXT extraction first, then fall back to images
            if file_type in supported_pdf_types:
                if not PDF_SUPPORT:
                    return {
                        "success": False,
                        "error": "PDF support is not available. Please install PyMuPDF: pip install pymupdf"
                    }

                # PRIMARY: Try text extraction (fast, handles multi-page, low memory)
                print("Attempting PDF text extraction...")
                pdf_text = self._extract_pdf_text(file_content)

                if pdf_text and len(pdf_text) > 100:
                    print(f"=== USING TEXT EXTRACTION PATH ===")
                    print(f"Text length: {len(pdf_text)} chars")
                    result = self.parse_travel_text(pdf_text)
                    print(f"Text parser result success: {result.get('success')}")
                    if not result.get('success'):
                        print(f"Text parser error: {result.get('error')}")
                        if 'raw_response' in result:
                            print(f"Raw response: {result.get('raw_response', '')[:500]}")
                    return result

                # FALLBACK: Image processing for scanned/image-based PDFs
                print("Text extraction insufficient, falling back to image processing...")
                pdf_images = self._extract_pdf_images(file_content)
                if not pdf_images:
                    return {
                        "success": False,
                        "error": "Failed to extract content from PDF. The file may be corrupted or password-protected."
                    }
                print(f"Using IMAGE extraction (first of {len(pdf_images)} pages)")
                file_content = pdf_images[0]
                file_type = 'image/png'

            if file_type not in supported_image_types:
                return {
                    "success": False,
                    "error": f"Unsupported file type: {file_type}. Please upload an image (JPG, PNG, GIF, WebP) or PDF file."
                }
            # Create the system prompt for structured extraction with fine print analysis
            system_prompt = """You are an expert travel document parser. Extract ALL information from travel documents including THE FINE PRINT that travelers often miss.

IMPORTANT: Look beyond basic dates and prices. Extract cancellation policies, refund deadlines, deposit requirements, and other details that could save money if plans change.

Return ONLY valid JSON in this exact format:
{
  "document_type": "flight|hotel|car_rental|activity|dining|transport|other",
  "elements": [
    {
      "type": "flight|hotel_checkin|hotel_checkout|activity|dining|transport|other",
      "title": "Brief descriptive title",
      "start_datetime": "ISO 8601 format (YYYY-MM-DDTHH:MM:SS)",
      "end_datetime": "ISO 8601 format (YYYY-MM-DDTHH:MM:SS) or null",
      "location": "Full location string (address, city, country)",
      "confirmation_number": "Confirmation/booking number or null",
      "price": numeric value only (no currency symbols) or null,
      "currency": "EUR|GBP|USD|JPY|CAD|AUD|CHF|CNY etc - DETECT FROM DOCUMENT",
      "refundable": true or false,
      "status": "confirmed|pending|cancelled",
      "details": {
        // For flights: airline, flight_number, seat, gate, terminal, baggage_allowance, class
        // For hotels: hotel_name, room_type, guests, amenities, num_nights
        // For cars: company, vehicle_type, pickup_location, dropoff_location, driver_name
        // For activities: venue, description, attendees, category
        // For dining: restaurant_name, cuisine, reservation_time, party_size
      },
      "policies": {
        "cancellation_deadline": "ISO datetime - last date/time for free cancellation or null",
        "cancellation_fee": numeric fee amount or null,
        "cancellation_policy": "Full text of cancellation policy or summary",
        "refund_policy": "How refunds work - full/partial/credit/none",
        "modification_policy": "Can booking be changed? Fees?",
        "deposit_amount": numeric deposit paid or null,
        "deposit_refundable": true/false/partial,
        "balance_due_date": "ISO date when remaining balance is due or null",
        "no_show_fee": numeric fee for no-show or null,
        "early_checkout_fee": numeric fee or null (hotels),
        "change_fee": numeric fee for changes or null
      }
    }
  ],
  "metadata": {
    "traveler_name": "Name of the traveler or null",
    "total_cost": numeric total or null,
    "currency": "EUR|GBP|USD|JPY|CAD|AUD|CHF|CNY etc - DETECT FROM DOCUMENT",
    "amount_paid": numeric amount already paid or null,
    "balance_due": numeric remaining balance or null,
    "booking_date": "YYYY-MM-DD or null",
    "vendor": "Company/airline/hotel name or null",
    "vendor_phone": "Contact phone number or null",
    "vendor_email": "Contact email or null"
  },
  "important_deadlines": [
    {
      "type": "cancellation|payment|check_in|modification",
      "deadline": "ISO datetime",
      "description": "What happens at this deadline",
      "financial_impact": "Amount at risk if deadline missed"
    }
  ],
  "cost_recovery_notes": "Any opportunities to recover costs if trip is disrupted - travel insurance mentions, credit card protections, airline credits, etc."
}

=== CRITICAL: CURRENCY DETECTION - DO NOT ASSUME USD ===
You MUST detect the actual currency from the document:
- Look for currency CODES: "EUR", "GBP", "USD", "JPY", "CAD", "AUD", "CHF", etc.
- Look for currency SYMBOLS: € = EUR, £ = GBP, $ = USD (but $ in Canada = CAD, Australia = AUD), ¥ = JPY/CNY
- Consider COUNTRY CONTEXT: Ireland/Europe = EUR, UK = GBP, Japan = JPY, USA = USD
- If document shows "2,060.00 EUR" - the currency is EUR, NOT USD!
- If document shows "€2,060" - the currency is EUR!
- European hotels (Ireland, France, Germany, Italy, Spain, etc.) = EUR
- NEVER default to USD for non-US documents!

=== CRITICAL: HOTEL BOOKING RULES - CREATE TWO EVENTS ===
For HOTEL reservations, you MUST create TWO separate elements to show on the timeline:

1. **hotel_checkin** element (FIRST):
   - type: "hotel_checkin"
   - title: "Check-in: [Hotel Name]"
   - start_datetime: Arrival date with CHECK-IN TIME
     - Use hotel's stated check-in time if available
     - Default to 16:00 (4pm) if not specified
   - end_datetime: null
   - price: Put the FULL booking price on CHECK-IN element
   - currency: Detected currency
   - Include all hotel details and policies

2. **hotel_checkout** element (SECOND):
   - type: "hotel_checkout"
   - title: "Check-out: [Hotel Name]"
   - start_datetime: Departure date with CHECK-OUT TIME
     - Use hotel's stated check-out time if available
     - Default to 11:00 (11am) if not specified
   - end_datetime: null
   - price: null (already on check-in)
   - currency: Same as check-in
   - confirmation_number: SAME as check-in element

HOTEL EXAMPLE - Ashford Castle, April 2-4, check-in 3pm, checkout 12noon, 2060 EUR:
[
  {
    "type": "hotel_checkin",
    "title": "Check-in: Ashford Castle",
    "start_datetime": "2026-04-02T15:00:00",
    "location": "Ashford Castle, Cong, Co. Mayo, Ireland",
    "confirmation_number": "419331031",
    "price": 2060,
    "currency": "EUR",
    "details": {"hotel_name": "Ashford Castle", "room_type": "Lake View Deluxe", "guests": "2 Adults, 1 Child", "num_nights": 2}
  },
  {
    "type": "hotel_checkout",
    "title": "Check-out: Ashford Castle",
    "start_datetime": "2026-04-04T12:00:00",
    "location": "Ashford Castle, Cong, Co. Mayo, Ireland",
    "confirmation_number": "419331031",
    "price": null,
    "currency": "EUR"
  }
]

=== CRITICAL: FLIGHT BOOKING RULES - CREATE SEPARATE ELEMENTS ===
For FLIGHT reservations, you MUST:

1. **CREATE SEPARATE ELEMENTS** for EACH flight leg:
   - Outbound flight = 1 element
   - Return flight = 1 element
   - Connecting flights = separate element for each leg
   - Round-trip booking = MINIMUM 2 elements

2. **EXTRACT ALL FLIGHT DETAILS**:
   - type: "flight"
   - title: "[Airline] [Flight#] [Origin] to [Destination]"
   - start_datetime: DEPARTURE time in LOCAL time (e.g., "2026-04-01T06:25:00")
   - end_datetime: ARRIVAL time in LOCAL time (e.g., "2026-04-01T07:35:00")
   - location: "From [Origin Airport/Code] to [Destination Airport/Code]"
   - confirmation_number: Booking reference (SAME for all legs of same booking)
   - price: Total cost on FIRST leg only, null on subsequent legs
   - currency: Detected currency (EUR for European airlines like Aer Lingus, Ryanair)

3. **FLIGHT DETAILS object must include**:
   - airline: "Aer Lingus", "Ryanair", "Delta", etc.
   - flight_number: "EI123", "FR456", etc.
   - origin_airport: Full name with code
   - destination_airport: Full name with code
   - class: "Economy", "Business", etc.
   - passengers: Number and names if available
   - baggage_allowance: What's included

FLIGHT EXAMPLE - Round-trip:
[
  {
    "type": "flight",
    "title": "Aer Lingus EI3123 Dublin to Shannon",
    "start_datetime": "2026-04-01T06:25:00",
    "end_datetime": "2026-04-01T07:35:00",
    "location": "From Dublin (DUB) to Shannon (SNN)",
    "confirmation_number": "2EC2ZW",
    "price": 245.50,
    "currency": "EUR",
    "details": {"airline": "Aer Lingus", "flight_number": "EI3123", "origin_airport": "Dublin (DUB)", "destination_airport": "Shannon (SNN)"}
  },
  {
    "type": "flight",
    "title": "Aer Lingus EI3128 Shannon to Dublin",
    "start_datetime": "2026-04-05T19:30:00",
    "end_datetime": "2026-04-05T20:40:00",
    "location": "From Shannon (SNN) to Dublin (DUB)",
    "confirmation_number": "2EC2ZW",
    "price": null,
    "currency": "EUR",
    "details": {"airline": "Aer Lingus", "flight_number": "EI3128", "origin_airport": "Shannon (SNN)", "destination_airport": "Dublin (DUB)"}
  }
]

CRITICAL EXTRACTION RULES:
1. FINE PRINT IS GOLD: Scan every corner for cancellation policies, deadlines, fees
2. CURRENCY: Detect actual currency - NEVER assume USD!
   - Aer Lingus, Ryanair, Irish Ferries = EUR
   - British Airways from UK = GBP
   - American carriers = USD
3. HOTELS: ALWAYS create TWO elements (hotel_checkin + hotel_checkout) with correct times
4. FLIGHTS: ALWAYS create SEPARATE elements for EACH flight leg (outbound AND return)
5. DATES & TIMES: Extract EXACT departure/arrival times - these are CRITICAL
6. PRICES: Find the total cost - often on a payment summary page
7. REFUNDABILITY: Note if booking is refundable or non-refundable
8. DEADLINES: Extract ALL deadlines - cancellation, payment, check-in
9. Convert all dates to ISO 8601 format (YYYY-MM-DDTHH:MM:SS)
10. Extract numeric values only for prices (no currency symbols)
11. Return ONLY the JSON object, no additional text
12. SCAN ALL PAGES for complete information - DO NOT MISS THE RETURN FLIGHT"""

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
                                "url": f"data:{file_type};base64,{file_content}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ]

            # Call OpenAI Vision API
            response = openai.chat.completions.create(
                model="gpt-4o",  # GPT-4 Vision model
                messages=messages,
                max_tokens=4000,
                temperature=0  # Low temperature for consistent extraction
            )

            # Parse the response
            content = response.choices[0].message.content.strip()
            print(f"=== GPT-4 RAW RESPONSE (first 1000 chars) ===")
            print(content[:1000])
            print(f"=== END RAW RESPONSE ===")

            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]  # Remove ```json
            if content.startswith("```"):
                content = content[3:]  # Remove ```
            if content.endswith("```"):
                content = content[:-3]  # Remove closing ```
            content = content.strip()

            print(f"After cleanup (first 500 chars): {content[:500]}")

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
      "type": "flight|hotel_checkin|hotel_checkout|activity|dining|transport|other",
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
5. **PRICES - CRITICAL**:
   - Put the TOTAL booking price on the FIRST flight element only
   - Subsequent flight elements (return leg) should have price: null
   - Extract only numeric values (remove $, €, etc symbols)
   - Detect currency: USD for US bookings, EUR for European airlines booked in Europe
   - Example: Total "$12,517.73" → put 12517.73 on FIRST flight, currency: "USD"
6. **CONFIRMATION NUMBERS**: CRITICAL - Extract confirmation/booking numbers
   - ALL elements from the SAME booking share the SAME confirmation number
   - For round-trip flights: BOTH flights get the SAME confirmation number
   - Look for: "Confirmation #", "Booking Reference", "Confirmation Number", etc.
   - Include this in EVERY element from the same booking
7. Include all other details like contact info, seat assignments, amenities
8. **TITLES**: Make descriptive
   - Flight: "[Airline] [Flight#] from [Origin] to [Dest]"
   - Hotel Check-in: "Check-in: [Hotel Name]"
   - Hotel Check-out: "Check-out: [Hotel Name]"
9. Return ONLY the JSON object, no additional text
10. If the text doesn't contain travel information, return document_type: "other" with empty elements array
11. **HOTELS - CREATE TWO ELEMENTS**: For HOTEL reservations, ALWAYS create TWO separate elements:
   - **hotel_checkin**: type="hotel_checkin", title="Check-in: [Hotel Name]", start_datetime=check-in date/time (default 4:00 PM if not specified), price=FULL booking price
   - **hotel_checkout**: type="hotel_checkout", title="Check-out: [Hotel Name]", start_datetime=check-out date/time (default 11:00 AM if not specified), price=null, SAME confirmation_number as check-in

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
  - confirmation_number: "ABC123" (SAME as outbound)

HOTEL PARSING EXAMPLE:
If you see:
"Big Sky Resort - Confirmation #1144RW
Check-in: Feb 26, 2026
Check-out: Mar 3, 2026
Total: $7,279.25"

You MUST create 2 separate hotel elements:
Element 1: hotel_checkin
  - type: "hotel_checkin"
  - title: "Check-in: Big Sky Resort"
  - start_datetime: 2026-02-26T16:00:00 (default 4pm)
  - price: 7279.25
  - confirmation_number: "1144RW"
Element 2: hotel_checkout
  - type: "hotel_checkout"
  - title: "Check-out: Big Sky Resort"
  - start_datetime: 2026-03-03T11:00:00 (default 11am)
  - price: null
  - confirmation_number: "1144RW" (SAME as check-in)"""

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
        valid_types = ['flight', 'hotel', 'hotel_checkin', 'hotel_checkout', 'activity', 'dining', 'transport', 'other']
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
            supported_pdf_types = ['application/pdf']
            
            # Handle PDF files by extracting images from pages
            if file_type in supported_pdf_types:
                if not PDF_SUPPORT:
                    return {
                        "success": False,
                        "error": "PDF support is not available. Please install PyMuPDF: pip install pymupdf"
                    }
                pdf_images = self._extract_pdf_images(file_content)
                if not pdf_images:
                    return {
                        "success": False,
                        "error": "Failed to extract images from PDF. The file may be corrupted or password-protected."
                    }
                # Use the first page image for processing
                file_content = pdf_images[0]
                file_type = 'image/png'
            
            if file_type not in supported_image_types:
                return {
                    "success": False,
                    "error": f"Unsupported file type: {file_type}. Please upload an image (JPG, PNG, GIF, WebP) or PDF file."
                }
            
            # Create receipt-specific prompt with currency detection
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

CURRENCY DETECTION - CRITICAL:
- Look for currency symbols: $ (USD), € (EUR), £ (GBP), ¥ (JPY/CNY), ₹ (INR), etc.
- Look for currency codes: USD, EUR, GBP, JPY, CAD, AUD, CHF, etc.
- Consider the country/location context (European restaurant = likely EUR)
- Common mappings: $ in USA = USD, $ in Canada = CAD, $ in Australia = AUD
- If unclear, check language on receipt for hints

CRITICAL RULES:
1. Extract the TOTAL amount (not subtotal) - numeric value only
2. Use merchant/restaurant name from receipt
3. Convert date to YYYY-MM-DD format
4. Choose the most appropriate category
5. DETECT THE CORRECT CURRENCY from the receipt - do not assume USD
6. Return ONLY the JSON object, no additional text"""
            
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

    def generate_smart_tasks(self, trip_elements):
        """Generate smart travel tasks using KB and GPT-4o - provides INSIGHTS not homework"""
        try:
            print(f"Generating smart tasks for {len(trip_elements)} elements")

            # Extract KB insights for this trip
            kb_context = self._extract_kb_context(trip_elements)

            system_prompt = """You are an expert travel concierge who PROVIDES INSIGHTS, not homework assignments.

**CRITICAL**: Your tasks should GIVE users the answer/insight, not tell them to research.

❌ WRONG: "Review Narcoossee's menu"
✅ RIGHT: "Narcoossee's specializes in butter-poached lobster ($58) and pan-seared scallops. Request window table at 8:45 PM for Magic Kingdom fireworks view at 9:15 PM. Call 407-939-3463 for dietary accommodations."

❌ WRONG: "Check hotel amenities"
✅ RIGHT: "Four Seasons offers free Disney shuttle (book 24h advance at concierge). Request Tower room for Magic Kingdom fireworks view. Spa is adults-only."

❌ WRONG: "Research airport transportation"
✅ RIGHT: "Book Uber from MCO Level 2 to Four Seasons for 3:15 PM ($48, 28min). Level 2 avoids surge pricing. Mears shuttle is $16pp but adds 45min with stops."

**FOCUS ON:**
1. **Fill transportation gaps** - specific provider, timing, cost, insider tip
2. **Provide venue intel** - signature dishes, insider tips, timing strategies, specific prices
3. **Surface hidden requirements** - apps needed with setup deadlines, advance bookings with times/costs
4. **Share money/time savers** - skip lines, discounts, crowd strategies with specific actions
5. **Anticipate problems** - dietary needs with phone numbers, weather prep, timing conflicts

**AVOID:**
- Obvious tasks like "pack clothes" or "check in for flight"
- NEVER suggest "arrange transportation" or "book ground transportation" for elements with transport_type="driving" - that means they're driving their OWN car!
- NEVER suggest booking for personal vehicle trips - look at details.transport_type field

Return ONLY valid JSON:
{
  "tasks": [
    {
      "title": "Specific actionable task WITH the insight",
      "description": "The full intel: costs, timing, phone numbers, insider tips, alternatives",
      "priority": "high|medium|low",
      "category": "pre_trip|in_trip|dining|activities|return",
      "due_date": "ISO datetime or null",
      "trigger_condition": "Specific timing based on itinerary"
    }
  ]
}"""

            # Format trip elements with KB enrichment
            elements_summary = []
            for el in trip_elements:
                element_data = {
                    "type": el.get('type'),
                    "title": el.get('title'),
                    "start_datetime": el.get('start_datetime'),
                    "end_datetime": el.get('end_datetime'),
                    "location": el.get('location'),
                    "confirmation_number": el.get('confirmation_number'),
                    "details": el.get('details', {})
                }
                elements_summary.append(element_data)

            user_prompt = f"""Trip itinerary:
{json.dumps(elements_summary, indent=2)}

Knowledge base context (use this to provide specific intel):
{json.dumps(kb_context, indent=2)}

Generate 8-12 SMART tasks that PROVIDE INSIGHTS (not homework):

**CRITICAL RULES:**
- If a transport element has details.transport_type="driving" or "driving_personal", DO NOT suggest "book transportation" - they're driving their OWN CAR
- Only suggest transportation booking if there's NO transport element for that leg, or if transport_type is "rental_car" or "uber_taxi"

**Required task types:**
1. Airport-to-hotel transportation (ONLY if no transport element exists for this leg - skip if they have personal driving planned)
2. Venue-specific intel (signature dishes with prices, must-knows, phone numbers for calls, insider timing tips)
3. Required apps with setup deadlines (exactly when to download, what to link, why it matters)
4. Advance booking opportunities (Lightning Lane, Genie+, etc. with exact times and costs)
5. Dietary/special needs with specific phone numbers and timing for calls
6. Time-saving strategies (early arrival times, crowd patterns, skip-the-line options)
7. Hidden costs or money-savers (free shuttles, discount opportunities)
8. Between-venue transportation gaps (ONLY if no transport exists - skip if driving personal vehicle)

Each task should answer: What? When? How much? Who to call? Why? Any insider tips?"""

            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=2500
            )

            response_text = response.choices[0].message.content.strip()

            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            parsed_data = json.loads(response_text)

            return {
                "success": True,
                "tasks": parsed_data.get('tasks', [])
            }

        except Exception as e:
            print(f"Error generating tasks: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _extract_kb_context(self, trip_elements):
        """Extract relevant KB data for these trip elements"""
        if not self.knowledge_base:
            return {}

        context = {}

        for element in trip_elements:
            el_type = element.get('type', '')
            title = element.get('title', '').lower()
            location = element.get('location', '').lower()

            # Match airports
            for code, airport_data in self.knowledge_base.get('airports', {}).items():
                if code.lower() in title or code.lower() in location:
                    context[f'airport_{code}'] = airport_data

            # Match airlines
            for airline, airline_data in self.knowledge_base.get('airlines', {}).items():
                if airline.lower() in title:
                    context[f'airline_{airline}'] = airline_data

            # Match destinations
            if 'disney' in location or 'disney' in title:
                context['destination_disney'] = self.knowledge_base.get('destinations', {}).get('orlando_disney', {})

            # Match hotels
            for hotel_key, hotel_data in self.knowledge_base.get('hotels', {}).items():
                hotel_name = hotel_data.get('name', '').lower()
                if any(word in title for word in hotel_name.split()):
                    context[f'hotel_{hotel_key}'] = hotel_data

            # Match restaurants
            for restaurant_key, restaurant_data in self.knowledge_base.get('restaurants', {}).items():
                restaurant_name = restaurant_data.get('name', '').lower()
                if restaurant_name in title:
                    context[f'restaurant_{restaurant_key}'] = restaurant_data

            # Match activities
            for activity_key, activity_data in self.knowledge_base.get('activities', {}).items():
                activity_name = activity_data.get('name', '').lower()
                if any(word in title for word in activity_name.split()):
                    context[f'activity_{activity_key}'] = activity_data

        # Always include task generation patterns
        context['patterns'] = self.knowledge_base.get('task_generation_patterns', {})

        return context
