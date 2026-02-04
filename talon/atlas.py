# talon/atlas.py
# Purpose: Atlas planning agent — produces human-readable, time-blocked itineraries
import openai
import os
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class Atlas:
    """Atlas: Master Trip Designer.

    Produces human-readable, day-by-day, time-blocked itineraries
    optimized for realism, pacing, preferences, and safety.
    Not user-facing — Houston is the sole voice.
    """

    def __init__(self) -> None:
        self.api_key: str = os.getenv("OPENAI_API_KEY", "")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found")
        openai.api_key = self.api_key
        self._kb: str = self._load_kb()

    def _load_kb(self) -> str:
        kb_path = os.path.join(os.path.dirname(__file__), "KB_ATLAS.md")
        try:
            with open(kb_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            logger.warning("KB_ATLAS.md not found")
            return ""

    def plan(
        self,
        messages: list,
        profile_context: str = "",
        docs_context: str = "",
        existing_draft: str = "",
    ) -> str:
        """Generate or refine a human-readable itinerary.

        Args:
            messages: Full conversation history.
            profile_context: Traveler profile block.
            docs_context: Uploaded document text.
            existing_draft: Previous draft to refine.

        Returns:
            Markdown itinerary string.
        """
        system_prompt = self._build_system_prompt(profile_context, docs_context, existing_draft)
        api_messages = [{"role": "system", "content": system_prompt}] + messages[-20:]

        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=api_messages,
                max_tokens=6000,
                temperature=0.6,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error("Atlas planning error: %s", e)
            return "I encountered an issue while planning. Please try again."

    def _build_system_prompt(
        self,
        profile_context: str = "",
        docs_context: str = "",
        existing_draft: str = "",
    ) -> str:
        refinement_block = ""
        if existing_draft:
            refinement_block = f"""
## REFINEMENT MODE
The user already has a draft itinerary. They are asking you to MODIFY it.
Produce the FULL UPDATED itinerary (not just the changes).

{existing_draft}
"""

        return f"""You are ATLAS, the Master Trip Designer for Travel Raven.

{self._kb}

{profile_context}
{docs_context}
{refinement_block}

## Your Task
Produce a COMPLETE, COMMIT-READY itinerary in human-readable markdown format.

## Output Format
Use this exact structure:

### Assumptions
- List any assumptions you're making (pace, budget, lodging style, etc.)

### Trip Summary
- **Trip Name:** [descriptive name]
- **Dates:** [start] to [end]
- **Destinations:** [list]
- **Duration:** [X days, Y nights]
- **Total Driving:** [estimated miles]

### Day-by-Day Itinerary

**Day 1 — [Date] — [City/Location]**
- 🚗 [TIME] Drive: [From] → [To] ([X] miles, ~[Y] hours)
- 🏨 [TIME] Check-in: [Hotel/Lodge/Camp Name], [City]
- 🎯 [TIME] [Activity]: [Description]
- 🍽️ [TIME] Dinner: [Restaurant or area suggestion]

**Day 2 — [Date] — [City/Location]**
...continue for ALL days...

### Booking Needs
List everything that needs to be booked:
- [ ] Hotels/lodging for each stop
- [ ] Activities requiring reservations
- [ ] Any special arrangements

## Rules
1. Include EVERY drive segment with from/to, estimated miles, estimated hours.
2. Include hotel check-in AND check-out for every lodging stop.
3. Include specific activities, not just "explore the area."
4. Use realistic drive times (account for stops, not just Google estimate).
5. Add buffer time between transitions (minimum 30 min).
6. Respect max 8 hours driving per day unless user specifies otherwise.
7. Include meals (at least dinner) with location suggestions.
8. If an uploaded document contains an existing itinerary, use it as the foundation and enhance it.
9. Never invent confirmation numbers or prices.
10. Mark all items as needing booking (nothing is confirmed yet).
"""
