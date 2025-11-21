# talon/insights_ai.py
# Purpose: OpenAI GPT-4o integration for generating intelligent travel insights

import os
import json
import logging
from typing import List, Dict, Any
from openai import OpenAI

logger = logging.getLogger(__name__)


class InsightsAI:
    """
    Uses OpenAI GPT-4o to analyze trip itineraries and generate actionable insights.
    Focuses on optimization opportunities and experience enhancements.
    """

    def __init__(self):
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.warning("OPENAI_API_KEY not found, AI insights will be disabled")
            self.client = None
        else:
            self.client = OpenAI(api_key=api_key)

    def analyze_itinerary(
        self,
        trip: Dict[str, Any],
        elements: List[Dict[str, Any]],
        base_insights: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Use GPT-4o to analyze trip and generate AI-powered insights.

        Args:
            trip: Trip details (destination, dates, etc)
            elements: List of trip elements (flights, hotels, etc)
            base_insights: Rule-based insights from InsightsDetector

        Returns:
            Enhanced insights with AI recommendations
        """
        if not self.client:
            logger.info("OpenAI API not available, returning base insights only")
            return base_insights

        try:
            # Format trip data for AI
            itinerary_text = self._format_itinerary(trip, elements)

            # Build prompt
            prompt = self._build_analysis_prompt(trip, itinerary_text, base_insights)

            # Call OpenAI API
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role": "system",
                    "content": "You are a travel optimization expert. Analyze itineraries and provide specific, actionable recommendations. Return only valid JSON."
                }, {
                    "role": "user",
                    "content": prompt
                }],
                max_tokens=2000,
                temperature=0.3,  # Low temperature for consistent, factual analysis
                response_format={"type": "json_object"}
            )

            # Parse response
            ai_insights = self._parse_ai_response(response.choices[0].message.content)

            # Merge with base insights (avoid duplicates)
            enhanced_insights = self._merge_insights(base_insights, ai_insights)

            logger.info(f"Generated {len(enhanced_insights.get('recommendations', []))} AI recommendations")
            return enhanced_insights

        except Exception as e:
            logger.error(f"OpenAI API error: {e}", exc_info=True)
            # Return base insights if AI fails
            return base_insights

    def _format_itinerary(self, trip: Dict[str, Any], elements: List[Dict[str, Any]]) -> str:
        """Format trip elements into readable timeline."""
        lines = []

        for element in sorted(elements, key=lambda e: e.get('start_time', '')):
            type_emoji = {
                'flight': '✈️',
                'accommodation': '🏨',
                'transportation': '🚗',
                'dining': '🍽️',
                'activity': '🎭'
            }.get(element.get('type'), '📍')

            name = element.get('name', 'Unnamed')
            start = element.get('start_time', '')
            end = element.get('end_time', '')

            if start and end:
                lines.append(f"{type_emoji} {name}: {start} - {end}")
            elif start:
                lines.append(f"{type_emoji} {name}: {start}")

        return '\n'.join(lines) if lines else "No trip elements scheduled yet"

    def _build_analysis_prompt(
        self,
        trip: Dict[str, Any],
        itinerary: str,
        base_insights: Dict[str, List[Dict[str, Any]]]
    ) -> str:
        """Build prompt for trip analysis."""

        action_count = len(base_insights.get('action_required', []))

        return f"""Analyze this travel itinerary and provide HIGH-VALUE optimization recommendations.

TRIP DETAILS:
Destination: {trip.get('destination', 'Unknown')}
Dates: {trip.get('start_date', '')} to {trip.get('end_date', '')}
Travelers: {trip.get('notes', 'Not specified')}

CURRENT ITINERARY:
{itinerary}

CRITICAL ISSUES ALREADY DETECTED: {action_count}
(Don't duplicate - focus on optimizations and enhancements)

YOUR TASK:
Generate 2-5 actionable RECOMMENDATIONS for improving this trip. Focus on:

1. **Missing elements** - Transportation gaps, meal planning, downtime activities
2. **Timing optimizations** - Activities in wrong order, too rushed, better scheduling
3. **Experience enhancements** - Hidden gems near existing bookings, better alternatives, insider tips
4. **Practical improvements** - Weather considerations, crowd strategies, booking windows

RULES:
- Be SPECIFIC (not "consider restaurant" but "Add dinner near Universal before 8 PM - try The Cowfish for sushi burgers")
- Be BRIEF (1-2 sentences max per insight)
- HIGH VALUE ONLY (don't suggest obvious things)
- Include WHY it matters (save money/time, better experience, avoid problems)
- Return valid JSON only

OUTPUT FORMAT (JSON only):
{{
  "recommendations": [
    {{
      "id": "unique_id",
      "type": "missing_element|timing_optimization|experience_enhancement",
      "severity": "info",
      "title": "Brief title (5-8 words)",
      "description": "Specific actionable recommendation with context (1-2 sentences)",
      "actions": [
        {{"label": "Action button text", "action": "add_element|search|dismiss", "params": {{}}}},
        {{"label": "Dismiss", "action": "dismiss", "params": {{}}}}
      ]
    }}
  ],
  "good_to_know": [
    {{
      "id": "unique_id",
      "type": "weather|local_event|general",
      "severity": "info",
      "title": "Brief title",
      "description": "Helpful context (only if EXTREME weather or major events)",
      "actions": []
    }}
  ]
}}

Return ONLY the JSON object."""

    def _parse_ai_response(self, response_text: str) -> Dict[str, List[Dict[str, Any]]]:
        """Parse AI JSON response."""
        try:
            parsed = json.loads(response_text)

            # Ensure proper structure
            return {
                'recommendations': parsed.get('recommendations', []),
                'good_to_know': parsed.get('good_to_know', [])
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}\nResponse: {response_text}")
            return {'recommendations': [], 'good_to_know': []}

    def _merge_insights(
        self,
        base: Dict[str, List[Dict[str, Any]]],
        ai: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Merge base insights with AI insights, avoiding duplicates."""

        # Keep all action_required from base (critical issues)
        merged = {
            'action_required': base.get('action_required', []),
            'recommendations': base.get('recommendations', []).copy(),
            'good_to_know': base.get('good_to_know', []).copy()
        }

        # Add AI recommendations (check for duplicates by type/title similarity)
        existing_titles = {
            insight.get('title', '').lower()
            for insight in merged['recommendations']
        }

        for rec in ai.get('recommendations', []):
            title = rec.get('title', '').lower()
            # Simple duplicate check - could be more sophisticated
            if title and title not in existing_titles:
                merged['recommendations'].append(rec)
                existing_titles.add(title)

        # Add good_to_know items (usually empty unless extreme conditions)
        for item in ai.get('good_to_know', []):
            merged['good_to_know'].append(item)

        return merged
