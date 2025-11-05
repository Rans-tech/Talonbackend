#!/usr/bin/env python3
"""Script to update the GPT-4o prompt in document_parser.py"""

# Read the file
with open('document_parser.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Define the old system_prompt
old_system_prompt = '''            system_prompt = """You are a travel planning assistant. Generate actionable tasks from trip itineraries.

Return ONLY valid JSON:
{
  "tasks": [
    {
      "title": "Actionable task title",
      "description": "Detailed description",
      "priority": "high|medium|low",
      "category": "pre_trip|in_trip|dining|activities|return",
      "due_date": "ISO datetime or null",
      "trigger_condition": "When to do this"
    }
  ]
}

Examples:
- "Check in for Southwest Flight 3732" (24h before, high priority)
- "Review Narcoossee's menu" (2 days before, medium priority)
- "Pack rain gear for outdoor activities" (before trip, medium priority)"""'''

# Define the new system_prompt
new_system_prompt = '''            system_prompt = """You are an expert travel concierge who identifies gaps and provides insider tips.

FOCUS ON SMART, NON-OBVIOUS TASKS:
- Missing logistics (airport transfers, inter-venue transport)
- Insider tips (apps, advance bookings, skip-the-line, discounts)
- Specific timing based on actual itinerary
- Proactive items travelers forget (dietary calls, mobile check-in, weather prep)
- Money/time savers (early booking, bundled deals, crowd strategies)

AVOID OBVIOUS TASKS like "pack clothes" or "check in for flight"

GOOD EXAMPLES:
- "Book Uber from MCO to Four Seasons for 3:15 PM (flight lands 2:45 PM)"
- "Download My Disney Experience app and link tickets (required for Lightning Lane)"
- "Reserve Genie+ for Animal Kingdom Dec 12 (high crowd forecast)"
- "Call Narcoossee's to confirm seafood allergy accommodations"
- "Pre-order mobile breakfast at Dolphin for 7 AM early park entry"

Return ONLY valid JSON:
{
  "tasks": [
    {
      "title": "Specific actionable task",
      "description": "Why it matters, what to do, insider tips",
      "priority": "high|medium|low",
      "category": "pre_trip|in_trip|dining|activities|return",
      "due_date": "ISO datetime or null",
      "trigger_condition": "Specific timing"
    }
  ]
}"""'''

# Replace the system_prompt
content = content.replace(old_system_prompt, new_system_prompt)

# Define old elements_summary
old_elements = '''            elements_summary = []
            for el in trip_elements:
                elements_summary.append({
                    "type": el.get('type'),
                    "title": el.get('title'),
                    "start_datetime": el.get('start_datetime'),
                    "location": el.get('location'),
                    "confirmation_number": el.get('confirmation_number')
                })'''

# Define new elements_summary
new_elements = '''            elements_summary = []
            for el in trip_elements:
                elements_summary.append({
                    "type": el.get('type'),
                    "title": el.get('title'),
                    "start_datetime": el.get('start_datetime'),
                    "end_datetime": el.get('end_datetime'),
                    "location": el.get('location'),
                    "confirmation_number": el.get('confirmation_number'),
                    "details": el.get('details', {})
                })'''

# Replace elements_summary
content = content.replace(old_elements, new_elements)

# Define old user_prompt
old_user_prompt = '''            user_prompt = f"""Generate 5-10 actionable tasks for this trip:

{json.dumps(elements_summary, indent=2)}

Make tasks specific and helpful."""'''

# Define new user_prompt
new_user_prompt = '''            user_prompt = f"""Analyze this itinerary and generate 8-12 SMART tasks that fill gaps and provide insider value:

{json.dumps(elements_summary, indent=2)}

KEY QUESTIONS:
- How do they get from airport to first hotel?
- Any venue-specific apps/advance bookings needed?
- Any dietary restrictions to confirm?
- Any inter-venue transportation gaps?
- Weather-specific prep for outdoor activities?
- Advance purchase opportunities to save money/time?
- Mobile check-in or digital ticketing setup needed?
- Any crowd-beating strategies or skip-the-line options?

Generate tasks showing REAL intelligence that save time/money/hassle."""'''

# Replace user_prompt
content = content.replace(old_user_prompt, new_user_prompt)

# Write the updated content
with open('document_parser.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Successfully updated document_parser.py!")
print("Backup saved as document_parser.py.bak")
