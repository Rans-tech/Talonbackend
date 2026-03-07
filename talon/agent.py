# talon/agent.py
# Purpose: Houston orchestrator — sole user-facing voice, routes to agents, manages commit pipeline
import openai
import os
import json
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Houston:
    """Houston orchestrator: single user-facing voice for TALON Command Center.

    Manages conversation state, routes planning requests to Atlas,
    tracks commit readiness, and converts itineraries to trip_elements on commit.
    """

    def __init__(self) -> None:
        self.api_key: str = os.getenv("OPENAI_API_KEY", "")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        openai.api_key = self.api_key
        self._kb_houston: str = self._load_kb("KB_HOUSTON.md")
        self._kb_atlas: str = self._load_kb("KB_ATLAS.md")
        self.conversations: dict = {}  # conversation_id -> ConversationState

    # ------------------------------------------------------------------
    # KB helpers
    # ------------------------------------------------------------------
    def _load_kb(self, filename: str) -> str:
        kb_path = os.path.join(os.path.dirname(__file__), filename)
        try:
            with open(kb_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning("KB file not found: %s", kb_path)
            return ""

    # ------------------------------------------------------------------
    # Conversation state
    # ------------------------------------------------------------------
    def _get_or_create_conversation(self, conversation_id: str) -> dict:
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = {
                "messages": [],
                "draft_itinerary": None,
                "commit_ready": False,
                "trip_context": None,
                "uploaded_docs": [],
            }
        return self.conversations[conversation_id]

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------
    def _is_planning_request(self, message: str) -> bool:
        planning_signals = [
            "plan", "trip", "itinerary", "road trip", "vacation", "travel",
            "schedule", "route", "drive to", "fly to", "visit", "day by day",
            "create a trip", "build a trip", "design a trip", "map out",
        ]
        lower = message.lower()
        return any(s in lower for s in planning_signals)

    # ------------------------------------------------------------------
    # Chat — main entry point
    # ------------------------------------------------------------------
    def chat(
        self,
        message: str,
        conversation_id: str,
        trip_id: Optional[str] = None,
        attachment_text: Optional[str] = None,
        user_profile: Optional[dict] = None,
        trip_context: Optional[dict] = None,
    ) -> dict:
        """Process a user message. Returns dict with response, commit_ready, draft_summary."""
        conv = self._get_or_create_conversation(conversation_id)

        # Store trip context if provided (existing trip mode)
        if trip_context and not conv.get("trip_context"):
            conv["trip_context"] = trip_context

        # Append attachment context if present
        user_content = message
        if attachment_text:
            user_content += f"\n\n--- UPLOADED DOCUMENT ---\n{attachment_text}\n--- END DOCUMENT ---"
            conv["uploaded_docs"].append(attachment_text[:500])

        conv["messages"].append({"role": "user", "content": user_content})

        # Route to Atlas for planning, otherwise general Houston response
        if self._is_planning_request(message) or conv["draft_itinerary"]:
            response_text = self._route_to_atlas(conv, user_profile)
        else:
            response_text = self._general_response(conv)

        conv["messages"].append({"role": "assistant", "content": response_text})

        # Evaluate commit readiness
        self._evaluate_commit_ready(conv)

        return {
            "response": response_text,
            "conversation_id": conversation_id,
            "commit_ready": conv["commit_ready"],
            "draft_summary": self._draft_summary(conv),
            "has_trip_context": conv.get("trip_context") is not None,
        }

    # ------------------------------------------------------------------
    # Atlas route
    # ------------------------------------------------------------------
    def _build_trip_context_block(self, conv: dict) -> str:
        """Build context block describing the existing trip and its elements."""
        tc = conv.get("trip_context")
        if not tc:
            return ""

        block = "\n## Existing Trip Context\n"
        block += f"**Trip Name:** {tc.get('name', 'Unknown')}\n"
        block += f"**Dates:** {tc.get('start_date', '?')} to {tc.get('end_date', '?')}\n"
        block += f"**Destination:** {tc.get('destination', '?')}\n"
        if tc.get("budget"):
            block += f"**Budget:** ${tc['budget']}\n"

        elements = tc.get("elements", [])
        if elements:
            block += f"\n**Existing Elements ({len(elements)} total):**\n"
            for el in elements:
                el_type = el.get("type", "unknown")
                title = el.get("title", "Untitled")
                start = el.get("start_datetime", "")
                location = el.get("location", "")
                status = el.get("status", "pending")
                line = f"- [{el_type}] {title}"
                if start:
                    line += f" | {start[:10]}"
                if location:
                    line += f" | {location}"
                line += f" ({status})"
                block += line + "\n"
        else:
            block += "\n**No elements yet.**\n"

        block += "\nIMPORTANT: The user is working on THIS existing trip. "
        block += "Do NOT propose creating a new trip. Plan activities/elements to ADD to this trip. "
        block += "Reference existing elements when relevant (e.g., 'I see you arrive on July 13').\n"
        return block

    def _route_to_atlas(self, conv: dict, user_profile: Optional[dict] = None) -> str:
        from talon.atlas import Atlas
        atlas = Atlas()

        # Build context for Atlas — map stored preferences to Atlas profile contract
        profile_block = ""
        if user_profile:
            atlas_profile = self._map_profile_for_atlas(user_profile)
            profile_block = f"\n## Traveler Profile\n```json\n{json.dumps(atlas_profile, indent=2)}\n```\n"

        docs_block = ""
        if conv["uploaded_docs"]:
            docs_block = "\n## Uploaded Documents\n"
            for i, doc in enumerate(conv["uploaded_docs"], 1):
                docs_block += f"\n### Document {i}\n{doc}\n"

        existing_draft = ""
        if conv["draft_itinerary"]:
            existing_draft = f"\n## Current Draft Itinerary\n{conv['draft_itinerary']}\n"

        # Include existing trip context if in add-to-trip mode
        trip_context_block = self._build_trip_context_block(conv)

        # Call Atlas
        atlas_output = atlas.plan(
            messages=conv["messages"],
            profile_context=profile_block,
            docs_context=docs_block,
            existing_draft=existing_draft,
            trip_context=trip_context_block,
        )

        # Store the draft
        conv["draft_itinerary"] = atlas_output

        # Houston wraps the response with attribution
        return atlas_output

    # ------------------------------------------------------------------
    # Profile mapping for Atlas
    # ------------------------------------------------------------------
    def _map_profile_for_atlas(self, profile: dict) -> dict:
        """Map stored user preferences to Atlas profile contract."""
        prefs = profile.get("preferences") or {}
        travel_style = prefs.get("travel_style", {})
        accommodation = prefs.get("accommodation", {})
        dietary = prefs.get("dietary", {})

        # Determine pace
        pace = "balanced"
        if travel_style.get("relaxation"):
            pace = "relaxed"
        elif travel_style.get("adventure"):
            pace = "aggressive"

        # Determine budget band
        budget_band = "midrange"
        if travel_style.get("luxury"):
            budget_band = "premium"
        elif travel_style.get("budget_conscious"):
            budget_band = "economy"

        # Determine lodging style
        lodging = []
        if accommodation.get("hotels_chain") or accommodation.get("boutique_hotels"):
            lodging.append("hotel")
        if accommodation.get("resorts") or accommodation.get("all_inclusive"):
            lodging.append("resort")
        if accommodation.get("vacation_rentals"):
            lodging.append("airbnb")
        if not lodging:
            lodging = ["hotel"]

        # Dietary restrictions
        dietary_list = []
        for key, val in dietary.items():
            if val:
                dietary_list.append(key.replace("_", " "))
        if not dietary_list:
            dietary_list = ["none"]

        # Children
        has_children = travel_style.get("family_friendly", False)

        return {
            "full_name": profile.get("full_name", "Traveler"),
            "pace_preference": pace,
            "wake_time": "07:00",
            "bed_time": "22:00",
            "budget_band": budget_band,
            "lodging_style": lodging,
            "dietary": dietary_list,
            "mobility_constraints": ["none"],
            "travel_with_children": has_children,
            "max_drive_hours_per_day": 8,
            "risk_tolerance": "medium",
            "always_do": [],
            "never_do": [],
        }

    # ------------------------------------------------------------------
    # General response (non-planning)
    # ------------------------------------------------------------------
    def _general_response(self, conv: dict) -> str:
        trip_context_block = self._build_trip_context_block(conv)
        system_prompt = f"""You are Houston, the TALON Command Center orchestrator for Travel Raven.
You are the sole user-facing voice. Be helpful, concise, and specific.

{self._kb_houston}

{trip_context_block}

You help with travel questions, trip coordination, and can route planning requests to Atlas.
If the user wants to plan a trip, tell them you're routing to Atlas and begin planning.
If an existing trip is loaded, you can see its elements and help the user add to or refine it."""

        messages = [{"role": "system", "content": system_prompt}] + conv["messages"][-20:]

        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=2000,
                temperature=0.7,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error("Houston general response error: %s", e)
            return "I'm experiencing a temporary issue. Please try again."

    # ------------------------------------------------------------------
    # Commit readiness evaluation
    # ------------------------------------------------------------------
    def _evaluate_commit_ready(self, conv: dict) -> None:
        draft = conv.get("draft_itinerary")
        if not draft:
            conv["commit_ready"] = False
            return

        # Check for key indicators of a complete itinerary
        lower = draft.lower()
        has_dates = "day 1" in lower or "day 2" in lower or "july" in lower or "august" in lower
        has_lodging = any(w in lower for w in ["hotel", "lodge", "airbnb", "camp", "resort", "stay", "check-in", "checkin"])
        has_transport = any(w in lower for w in ["drive", "flight", "fly", "transport", "miles", "hours drive"])
        has_multiple_days = "day 3" in lower or "day 4" in lower or has_dates

        conv["commit_ready"] = has_dates and has_lodging and has_transport and has_multiple_days

    # ------------------------------------------------------------------
    # Draft summary for UI
    # ------------------------------------------------------------------
    def _draft_summary(self, conv: dict) -> Optional[str]:
        draft = conv.get("draft_itinerary")
        if not draft:
            return None
        # Return first 500 chars as summary
        return draft[:500] + ("..." if len(draft) > 500 else "")

    # ------------------------------------------------------------------
    # Commit pipeline — convert itinerary to structured trip_elements
    # ------------------------------------------------------------------
    def commit(self, conversation_id: str, trip_name: Optional[str] = None, budget: Optional[float] = None) -> dict:
        """Convert finalized itinerary into structured trip + trip_elements."""
        conv = self.conversations.get(conversation_id)
        if not conv:
            return {"success": False, "error": "Conversation not found"}

        draft = conv.get("draft_itinerary")
        if not draft:
            return {"success": False, "error": "No draft itinerary to commit"}

        # Use GPT-4o to extract structured elements from the itinerary
        elements = self._extract_elements(draft, trip_name)
        if not elements:
            return {"success": False, "error": "Failed to extract trip elements from itinerary"}

        return {
            "success": True,
            "trip_name": elements.get("trip_name", trip_name or "My Trip"),
            "start_date": elements.get("start_date"),
            "end_date": elements.get("end_date"),
            "destination": elements.get("destination"),
            "budget": budget,
            "elements": elements.get("elements", []),
        }

    def _extract_elements(self, itinerary: str, trip_name: Optional[str] = None) -> Optional[dict]:
        """Use GPT-4o to deterministically convert markdown itinerary to structured JSON."""
        system_prompt = """You are a deterministic itinerary-to-JSON converter.

Given a human-readable travel itinerary, extract ALL elements into structured JSON.

Output EXACTLY this JSON schema:
{
  "trip_name": "string",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "destination": "string (primary destination or comma-separated list)",
  "elements": [
    {
      "type": "transport|hotel|activity|dining",
      "title": "string",
      "start_datetime": "YYYY-MM-DDTHH:MM:SS",
      "end_datetime": "YYYY-MM-DDTHH:MM:SS or null",
      "location": "string",
      "status": "pending",
      "price": null,
      "confirmation_number": null,
      "details": {
        "from_location": "string or null (for transport)",
        "to_location": "string or null (for transport)",
        "distance_miles": "number or null",
        "drive_hours": "number or null",
        "transport_type": "personal_vehicle|rental|flight|train|bus or null",
        "hotel_event_type": "hotel_checkin|hotel_checkout or null",
        "description": "string or null"
      }
    }
  ]
}

RULES:
1. For each DRIVE segment, create ONE transport element with from_location, to_location, distance_miles, drive_hours. Set transport_type to "personal_vehicle" unless specified otherwise.
2. For each HOTEL stay, create TWO elements: one hotel with hotel_event_type="hotel_checkin" and one with hotel_event_type="hotel_checkout". Check-in start_datetime is arrival day, check-out start_datetime is departure day.
3. For activities (hiking, surfing, sightseeing, tours), create activity elements.
4. For meals at specific restaurants, create dining elements.
5. All elements get status="pending" and price=null (no invented prices).
6. All elements get confirmation_number=null (nothing is booked yet).
7. Use realistic times based on the itinerary context.
8. Include ALL days and ALL transitions.
9. Return ONLY valid JSON, no markdown, no explanation."""

        user_prompt = f"Convert this itinerary to structured trip elements:\n\n{itinerary}"
        if trip_name:
            user_prompt = f"Trip name: {trip_name}\n\n{user_prompt}"

        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=8000,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content.strip()
            return json.loads(raw)
        except Exception as e:
            logger.error("Element extraction failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # Legacy compatibility — keep old TalonAgent interface working
    # ------------------------------------------------------------------
    def get_current_activity(self) -> str:
        return "Command Center active — monitoring travel platforms."

    def process_message(self, message: str) -> str:
        """Legacy single-message interface for /api/talon/chat."""
        result = self.chat(
            message=message,
            conversation_id="legacy",
        )
        return result["response"]


# Backwards-compatible alias
TalonAgent = Houston
