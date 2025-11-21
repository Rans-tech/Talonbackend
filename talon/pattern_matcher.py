# talon/pattern_matcher.py
# Purpose: Query learned patterns BEFORE generating insights for proactive recommendations

import logging
from typing import Dict, Any, List, Optional
from talon.database import db_client

logger = logging.getLogger(__name__)


class PatternMatcher:
    """
    Queries learned patterns from past trips to provide proactive recommendations.
    This is the QUERY layer of the self-learning loop.
    """

    def __init__(self):
        self.db = db_client.client

    def get_proactive_insights(
        self,
        trip: Dict[str, Any],
        elements: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Query learned patterns for this trip and generate proactive insights
        BEFORE issues occur.

        Args:
            trip: Trip details (destination, dates, etc)
            elements: Current trip elements

        Returns:
            Proactive insights based on learned patterns
        """
        proactive = []

        # Extract trip characteristics
        destination = trip.get('destination', '').lower()
        trip_duration = self._calculate_duration(trip)

        # Check for late arrival pattern
        late_arrival_insight = self._check_late_arrival_pattern(trip, elements, destination)
        if late_arrival_insight:
            proactive.append(late_arrival_insight)

        # Check for tight timing pattern
        tight_timing_insight = self._check_tight_timing_pattern(trip, elements, destination)
        if tight_timing_insight:
            proactive.append(tight_timing_insight)

        # Check for missing elements pattern
        missing_elements_insight = self._check_missing_elements_pattern(trip, elements, destination)
        if missing_elements_insight:
            proactive.append(missing_elements_insight)

        return {'proactive_recommendations': proactive}

    def _check_late_arrival_pattern(
        self,
        trip: Dict[str, Any],
        elements: List[Dict[str, Any]],
        destination: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check if trip matches late arrival pattern from KB.
        Returns proactive recommendation if pattern found.
        """
        try:
            # Check if there's a late-arriving flight
            flights = [e for e in elements if e.get('type') == 'flight']
            if not flights:
                return None

            first_flight = min(flights, key=lambda f: f.get('end_time', ''))
            arrival_time = first_flight.get('end_time', '')

            if not arrival_time:
                return None

            # Parse arrival hour (simplified)
            from datetime import datetime
            try:
                arrival_dt = datetime.fromisoformat(arrival_time.replace('Z', '+00:00'))
                arrival_hour = arrival_dt.hour
            except:
                return None

            # Late arrival = after 8 PM
            if arrival_hour < 20:
                return None

            # Query learned patterns for this destination + late arrival
            pattern = self._query_pattern('accommodation_gap', destination, {
                'arrival_time': 'late',
                'issue': 'hotel_gap'
            })

            if not pattern or pattern.get('confidence_score', 0) < 60:
                return None

            # Build proactive recommendation
            evidence = pattern.get('evidence', {})
            metrics = evidence.get('metrics', {})
            acceptance_rate = metrics.get('acceptance_rate', 0)

            # Get common solutions from pattern
            common_solutions = self._get_common_solutions(pattern, 'accommodation_gap')

            description = f"⚡ Proactive Alert (based on {pattern.get('sample_size', 0)} similar trips): "
            description += f"Your flight arrives at {arrival_dt.strftime('%I:%M %p')} - "
            description += f"{acceptance_rate:.0f}% of travelers in {destination} with late arrivals added an airport hotel for the first night. "

            if common_solutions:
                description += f"Most common: {', '.join(common_solutions[:3])}."

            return {
                'id': f'proactive_late_arrival_{destination}',
                'type': 'learned_pattern',
                'severity': 'warning',
                'title': f'Late Arrival Pattern Detected ({destination})',
                'description': description,
                'actions': [
                    {'label': 'Search Airport Hotels', 'action': 'search_hotels', 'params': {'location': 'airport'}},
                    {'label': 'View Similar Trips', 'action': 'view_patterns', 'params': {'pattern_id': pattern.get('id')}},
                    {'label': 'Dismiss', 'action': 'dismiss', 'params': {}}
                ],
                'learned_from': {
                    'sample_size': pattern.get('sample_size', 0),
                    'confidence': pattern.get('confidence_score', 0),
                    'success_rate': acceptance_rate
                }
            }

        except Exception as e:
            logger.error(f"Error checking late arrival pattern: {e}", exc_info=True)
            return None

    def _check_tight_timing_pattern(
        self,
        trip: Dict[str, Any],
        elements: List[Dict[str, Any]],
        destination: str
    ) -> Optional[Dict[str, Any]]:
        """Check for tight timing patterns based on learned data."""
        try:
            # Query pattern
            pattern = self._query_pattern('tight_timing', destination, {
                'issue': 'checkout_flight_gap'
            })

            if not pattern or pattern.get('confidence_score', 0) < 60:
                return None

            evidence = pattern.get('evidence', {})
            metrics = evidence.get('metrics', {})

            # Only suggest if pattern shows users often encounter issues
            if metrics.get('acceptance_rate', 0) < 40:
                return None  # Not a strong pattern

            description = f"💡 Learned Pattern: Based on {pattern.get('sample_size', 0)} trips to {destination}, "
            description += f"{metrics.get('acceptance_rate', 0):.0f}% of travelers with tight departure timing "
            description += "upgraded to early checkout or adjusted their flights. "
            description += "Consider planning extra buffer time."

            return {
                'id': f'proactive_tight_timing_{destination}',
                'type': 'learned_pattern',
                'severity': 'info',
                'title': 'Timing Optimization Opportunity',
                'description': description,
                'actions': [
                    {'label': 'View Recommendations', 'action': 'view_patterns', 'params': {}},
                    {'label': 'Dismiss', 'action': 'dismiss', 'params': {}}
                ],
                'learned_from': {
                    'sample_size': pattern.get('sample_size', 0),
                    'confidence': pattern.get('confidence_score', 0)
                }
            }

        except Exception as e:
            logger.error(f"Error checking tight timing pattern: {e}", exc_info=True)
            return None

    def _check_missing_elements_pattern(
        self,
        trip: Dict[str, Any],
        elements: List[Dict[str, Any]],
        destination: str
    ) -> Optional[Dict[str, Any]]:
        """Check for commonly missing elements based on destination patterns."""
        try:
            # Check what's already in the trip
            element_types = {e.get('type') for e in elements}

            # Query patterns for missing transportation
            if 'transportation' not in element_types and 'flight' in element_types:
                pattern = self._query_pattern('missing_transportation', destination, {})

                if pattern and pattern.get('confidence_score', 0) >= 60:
                    evidence = pattern.get('evidence', {})
                    metrics = evidence.get('metrics', {})

                    description = f"📍 Common Pattern: {metrics.get('acceptance_rate', 0):.0f}% of travelers to {destination} "
                    description += "add ground transportation after booking flights. "
                    description += "Popular options: Uber, rental car, hotel shuttle."

                    return {
                        'id': f'proactive_missing_transport_{destination}',
                        'type': 'learned_pattern',
                        'severity': 'info',
                        'title': 'Transportation Suggestion',
                        'description': description,
                        'actions': [
                            {'label': 'Add Transportation', 'action': 'add_element', 'params': {'type': 'transportation'}},
                            {'label': 'Dismiss', 'action': 'dismiss', 'params': {}}
                        ],
                        'learned_from': {
                            'sample_size': pattern.get('sample_size', 0),
                            'confidence': pattern.get('confidence_score', 0)
                        }
                    }

            return None

        except Exception as e:
            logger.error(f"Error checking missing elements pattern: {e}", exc_info=True)
            return None

    def _query_pattern(
        self,
        category: str,
        destination: str,
        filters: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Query learned patterns from insights_patterns table.

        Args:
            category: Insight category (e.g., 'accommodation_gap')
            destination: Trip destination
            filters: Additional filters

        Returns:
            Pattern data or None
        """
        try:
            # Query insights_patterns
            response = self.db.table('insights_patterns')\
                .select('*')\
                .eq('insight_category', category)\
                .single()\
                .execute()

            if not response.data:
                return None

            pattern = response.data

            # Get sample feedback to extract destination-specific insights
            feedback_response = self.db.table('insights_feedback')\
                .select('*')\
                .eq('insight_category', category)\
                .ilike('trip_destination', f'%{destination}%')\
                .limit(50)\
                .execute()

            if feedback_response.data:
                # Enrich pattern with destination-specific data
                pattern['destination_specific'] = True
                pattern['destination_sample_size'] = len(feedback_response.data)

                # Extract evidence from feedback
                pattern['evidence'] = {
                    'metrics': pattern,
                    'sample_comments': [
                        fb.get('user_comment')
                        for fb in feedback_response.data
                        if fb.get('user_comment')
                    ][:5]
                }

            return pattern

        except Exception as e:
            logger.debug(f"No pattern found for {category}: {e}")
            return None

    def _get_common_solutions(self, pattern: Dict[str, Any], category: str) -> List[str]:
        """Extract common solutions from pattern feedback."""
        try:
            # Get feedback with actions
            response = self.db.table('insights_feedback')\
                .select('action_details')\
                .eq('insight_category', category)\
                .eq('action_taken', 'acted')\
                .limit(100)\
                .execute()

            if not response.data:
                return []

            # Extract common solutions
            solutions = {}
            for fb in response.data:
                details = fb.get('action_details', {})
                solution = details.get('solution') or details.get('hotel_added') or details.get('action')

                if solution:
                    solutions[solution] = solutions.get(solution, 0) + 1

            # Return top 3 solutions
            sorted_solutions = sorted(solutions.items(), key=lambda x: x[1], reverse=True)
            return [sol[0] for sol in sorted_solutions[:3]]

        except Exception as e:
            logger.error(f"Error extracting solutions: {e}", exc_info=True)
            return []

    def _calculate_duration(self, trip: Dict[str, Any]) -> int:
        """Calculate trip duration in days."""
        try:
            from datetime import datetime

            start = datetime.fromisoformat(trip.get('start_date', '').replace('Z', '+00:00'))
            end = datetime.fromisoformat(trip.get('end_date', '').replace('Z', '+00:00'))

            return (end - start).days

        except:
            return 0

    def get_destination_stats(self, destination: str) -> Dict[str, Any]:
        """
        Get aggregated stats for a destination.
        Useful for "X% of trips to Orlando have this issue" messaging.
        """
        try:
            # Query feedback for this destination
            response = self.db.table('insights_feedback')\
                .select('*')\
                .ilike('trip_destination', f'%{destination}%')\
                .execute()

            if not response.data:
                return {}

            feedbacks = response.data
            total_trips = len(set(fb.get('trip_id') for fb in feedbacks))

            # Calculate common issues
            issues = {}
            for fb in feedbacks:
                category = fb.get('insight_category')
                issues[category] = issues.get(category, 0) + 1

            # Calculate acceptance rates
            actions = {}
            for fb in feedbacks:
                action = fb.get('action_taken')
                actions[action] = actions.get(action, 0) + 1

            return {
                'destination': destination,
                'total_trips': total_trips,
                'total_insights': len(feedbacks),
                'common_issues': dict(sorted(issues.items(), key=lambda x: x[1], reverse=True)),
                'action_distribution': actions
            }

        except Exception as e:
            logger.error(f"Error getting destination stats: {e}", exc_info=True)
            return {}
