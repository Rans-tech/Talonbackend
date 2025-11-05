#!/usr/bin/env python3
"""
Update document_parser.py to integrate KB and upgrade task generation
"""

# Read the current file
with open('talon/document_parser.py', 'r') as f:
    content = f.read()

# 1. Add pathlib import
if 'from pathlib import Path' not in content:
    content = content.replace(
        'import json\nfrom dotenv import load_dotenv',
        'import json\nfrom pathlib import Path\nfrom dotenv import load_dotenv'
    )

# 2. Add KB loading to __init__
init_addition = '''
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
            return {}'''

if '_load_knowledge_base' not in content:
    # Find where to insert (after openai.api_key = self.api_key)
    content = content.replace(
        '        openai.api_key = self.api_key\n\n    def parse_travel_document',
        '        openai.api_key = self.api_key' + init_addition + '\n\n    def parse_travel_document'
    )

# 3. Replace the generate_smart_tasks function with upgraded version
new_function = '''    def generate_smart_tasks(self, trip_elements):
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

**AVOID obvious tasks** like "pack clothes" or "check in for flight"

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

**Required task types:**
1. Airport-to-hotel transportation (specific: Uber/shuttle, timing based on flight, cost, insider tip about Level 2 vs Level 1)
2. Venue-specific intel (signature dishes with prices, must-knows, phone numbers for calls, insider timing tips)
3. Required apps with setup deadlines (exactly when to download, what to link, why it matters)
4. Advance booking opportunities (Lightning Lane, Genie+, etc. with exact times and costs)
5. Dietary/special needs with specific phone numbers and timing for calls
6. Time-saving strategies (early arrival times, crowd patterns, skip-the-line options)
7. Hidden costs or money-savers (free shuttles, discount opportunities)
8. Between-venue transportation gaps (specific times, costs, options)

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
'''

# Find and replace the old generate_smart_tasks function
import re

# Pattern to match the entire function
pattern = r'    def generate_smart_tasks\(self, trip_elements\):.*?(?=\n    def |\nclass |\Z)'

# Replace with new function
content = re.sub(pattern, new_function.rstrip(), content, flags=re.DOTALL)

# Write updated content
with open('talon/document_parser.py', 'w') as f:
    f.write(content)

print("✅ Updated document_parser.py with KB integration and upgraded task generation!")
print("   - Added Path import")
print("   - Added KB loading in __init__")
print("   - Upgraded generate_smart_tasks to provide insights not homework")
print("   - Added _extract_kb_context helper function")
