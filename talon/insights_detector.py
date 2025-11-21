# talon/insights_detector.py
# Purpose: Smart detection logic for TALON Insights - only flags real issues, not false positives

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class InsightsDetector:
    """
    Analyzes trip elements to detect genuine issues and opportunities.
    HIGH SIGNAL, LOW NOISE - only flag actionable insights.
    """

    def __init__(self, trip: Dict[str, Any], elements: List[Dict[str, Any]]):
        self.trip = trip
        self.elements = sorted(elements, key=lambda e: e.get('start_time', ''))
        self.accommodations = [e for e in elements if e.get('type') == 'accommodation']
        self.flights = [e for e in elements if e.get('type') == 'flight']
        self.transportation = [e for e in elements if e.get('type') == 'transportation']
        self.dining = [e for e in elements if e.get('type') == 'dining']
        self.activities = [e for e in elements if e.get('type') == 'activity']

    def analyze(self) -> Dict[str, List[Dict[str, Any]]]:
        """Run all detection logic and return categorized insights."""
        action_required = []
        recommendations = []
        good_to_know = []

        # ACTION REQUIRED - Critical issues only
        action_required.extend(self._detect_accommodation_gaps())
        action_required.extend(self._detect_conflicting_primary_bookings())
        action_required.extend(self._detect_missing_airport_transportation())
        action_required.extend(self._detect_impossible_logistics())

        # RECOMMENDATIONS - Optimization opportunities
        recommendations.extend(self._detect_tight_timing())
        recommendations.extend(self._detect_missing_meals())

        # GOOD TO KNOW - Usually empty, only extreme conditions
        # (These will be populated by AI analysis)

        return {
            'action_required': action_required,
            'recommendations': recommendations,
            'good_to_know': good_to_know
        }

    def _detect_accommodation_gaps(self) -> List[Dict[str, Any]]:
        """Detect if traveler arrives/leaves without hotel coverage."""
        insights = []

        if not self.accommodations:
            return insights

        trip_start = self._parse_datetime(self.trip.get('start_date'))
        trip_end = self._parse_datetime(self.trip.get('end_date'))

        if not trip_start or not trip_end:
            return insights

        # Find earliest arrival time (flight or trip start)
        arrival_time = trip_start
        if self.flights:
            first_flight = min(self.flights, key=lambda f: f.get('end_time', ''))
            if first_flight.get('end_time'):
                arrival_time = self._parse_datetime(first_flight['end_time'])

        # Find latest departure time (flight or trip end)
        departure_time = trip_end
        if self.flights:
            last_flight = max(self.flights, key=lambda f: f.get('start_time', ''))
            if last_flight.get('start_time'):
                departure_time = self._parse_datetime(last_flight['start_time'])

        # Check first accommodation coverage
        first_hotel = min(self.accommodations, key=lambda a: a.get('start_time', ''))
        first_checkin = self._parse_datetime(first_hotel.get('start_time'))

        if first_checkin and arrival_time:
            gap_hours = (first_checkin - arrival_time).total_seconds() / 3600
            if gap_hours > 6:  # More than 6 hours gap
                insights.append({
                    'id': f'accommodation_gap_arrival',
                    'type': 'accommodation_gap',
                    'severity': 'critical',
                    'title': f'Missing accommodation ({arrival_time.strftime("%b %d")})',
                    'description': f'You arrive {arrival_time.strftime("%b %d at %I:%M %p")} but hotel check-in is {first_checkin.strftime("%b %d at %I:%M %p")}. Need lodging for {int(gap_hours)} hours.',
                    'actions': [
                        {'label': 'Extend Current Hotel', 'action': 'extend_booking', 'params': {'element_id': first_hotel['id']}},
                        {'label': 'Add Hotel', 'action': 'search_hotels', 'params': {}},
                        {'label': 'Dismiss', 'action': 'dismiss', 'params': {}}
                    ]
                })

        # Check last accommodation coverage
        last_hotel = max(self.accommodations, key=lambda a: a.get('end_time', ''))
        last_checkout = self._parse_datetime(last_hotel.get('end_time'))

        if last_checkout and departure_time:
            gap_hours = (departure_time - last_checkout).total_seconds() / 3600
            if gap_hours > 6:  # More than 6 hours gap after checkout
                insights.append({
                    'id': f'accommodation_gap_departure',
                    'type': 'accommodation_gap',
                    'severity': 'critical',
                    'title': f'Accommodation gap before departure',
                    'description': f'Hotel checkout is {last_checkout.strftime("%b %d at %I:%M %p")} but departure is {departure_time.strftime("%b %d at %I:%M %p")}. {int(gap_hours)} hour gap.',
                    'actions': [
                        {'label': 'Extend Current Hotel', 'action': 'extend_booking', 'params': {'element_id': last_hotel['id']}},
                        {'label': 'Add Day Room', 'action': 'search_hotels', 'params': {}},
                        {'label': 'Dismiss', 'action': 'dismiss', 'params': {}}
                    ]
                })

        return insights

    def _detect_conflicting_primary_bookings(self) -> List[Dict[str, Any]]:
        """Detect impossible double-bookings (2 hotels same night, 2 flights same time)."""
        insights = []

        # Check for overlapping accommodations
        for i, hotel1 in enumerate(self.accommodations):
            for hotel2 in self.accommodations[i+1:]:
                if self._bookings_conflict(hotel1, hotel2):
                    insights.append({
                        'id': f'conflicting_hotels_{hotel1["id"]}_{hotel2["id"]}',
                        'type': 'conflicting_booking',
                        'severity': 'critical',
                        'title': 'Conflicting hotel bookings',
                        'description': f'{hotel1.get("name", "Hotel 1")} and {hotel2.get("name", "Hotel 2")} overlap on the same dates.',
                        'actions': [
                            {'label': 'Review Bookings', 'action': 'review', 'params': {}},
                            {'label': 'Dismiss', 'action': 'dismiss', 'params': {}}
                        ]
                    })

        # Check for overlapping flights
        for i, flight1 in enumerate(self.flights):
            for flight2 in self.flights[i+1:]:
                if self._bookings_conflict(flight1, flight2):
                    insights.append({
                        'id': f'conflicting_flights_{flight1["id"]}_{flight2["id"]}',
                        'type': 'conflicting_booking',
                        'severity': 'critical',
                        'title': 'Conflicting flight bookings',
                        'description': f'Two flights booked at overlapping times.',
                        'actions': [
                            {'label': 'Review Flights', 'action': 'review', 'params': {}},
                            {'label': 'Dismiss', 'action': 'dismiss', 'params': {}}
                        ]
                    })

        return insights

    def _detect_missing_airport_transportation(self) -> List[Dict[str, Any]]:
        """Detect if arrival flight has no transportation to hotel."""
        insights = []

        if not self.flights or not self.accommodations:
            return insights

        # Check first flight -> hotel transportation
        first_flight = min(self.flights, key=lambda f: f.get('end_time', ''))
        flight_arrival = self._parse_datetime(first_flight.get('end_time'))

        if not flight_arrival:
            return insights

        first_hotel = min(self.accommodations, key=lambda a: a.get('start_time', ''))
        hotel_checkin = self._parse_datetime(first_hotel.get('start_time'))

        # Check if there's transportation scheduled within 4 hours of landing
        has_transport = any(
            self._parse_datetime(t.get('start_time')) and
            abs((self._parse_datetime(t['start_time']) - flight_arrival).total_seconds() / 3600) < 4
            for t in self.transportation
        )

        if not has_transport and hotel_checkin:
            insights.append({
                'id': 'missing_airport_transport',
                'type': 'missing_transportation',
                'severity': 'critical',
                'title': 'No airport transportation scheduled',
                'description': f'Flight lands at {flight_arrival.strftime("%I:%M %p")} but no Uber/rental/shuttle booked to hotel.',
                'actions': [
                    {'label': 'Add Transportation', 'action': 'add_element', 'params': {'type': 'transportation'}},
                    {'label': 'Dismiss', 'action': 'dismiss', 'params': {}}
                ]
            })

        return insights

    def _detect_impossible_logistics(self) -> List[Dict[str, Any]]:
        """Detect impossible timing (dinner before flight lands, etc)."""
        insights = []

        # Check if any dining/activities scheduled before arrival
        if self.flights:
            first_flight = min(self.flights, key=lambda f: f.get('end_time', ''))
            arrival = self._parse_datetime(first_flight.get('end_time'))

            if arrival:
                for element in self.dining + self.activities:
                    event_time = self._parse_datetime(element.get('start_time'))
                    if event_time and event_time < arrival:
                        insights.append({
                            'id': f'impossible_timing_{element["id"]}',
                            'type': 'impossible_logistics',
                            'severity': 'critical',
                            'title': f'{element.get("name", "Event")} before arrival',
                            'description': f'You have {element.get("name")} scheduled at {event_time.strftime("%I:%M %p")} but you don\'t arrive until {arrival.strftime("%I:%M %p")}.',
                            'actions': [
                                {'label': 'Reschedule', 'action': 'edit_element', 'params': {'element_id': element['id']}},
                                {'label': 'Delete', 'action': 'delete_element', 'params': {'element_id': element['id']}},
                                {'label': 'Dismiss', 'action': 'dismiss', 'params': {}}
                            ]
                        })

        return insights

    def _detect_tight_timing(self) -> List[Dict[str, Any]]:
        """Detect risky but not impossible timing."""
        insights = []

        # Check hotel checkout -> flight timing
        if self.accommodations and self.flights:
            last_hotel = max(self.accommodations, key=lambda a: a.get('end_time', ''))
            checkout = self._parse_datetime(last_hotel.get('end_time'))

            departure_flights = [f for f in self.flights if self._parse_datetime(f.get('start_time', '')) and self._parse_datetime(f['start_time']) > checkout] if checkout else []

            if departure_flights:
                next_flight = min(departure_flights, key=lambda f: f.get('start_time', ''))
                flight_time = self._parse_datetime(next_flight.get('start_time'))

                if checkout and flight_time:
                    gap_hours = (flight_time - checkout).total_seconds() / 3600
                    if 1 < gap_hours < 3:  # Between 1-3 hours is tight
                        insights.append({
                            'id': 'tight_timing_checkout_flight',
                            'type': 'tight_timing',
                            'severity': 'warning',
                            'title': 'Tight timing on departure day',
                            'description': f'Checkout at {checkout.strftime("%I:%M %p")}, flight at {flight_time.strftime("%I:%M %p")} - only {gap_hours:.1f} hours. Consider early checkout or later flight.',
                            'actions': [
                                {'label': 'Adjust Checkout', 'action': 'edit_element', 'params': {'element_id': last_hotel['id']}},
                                {'label': 'Dismiss', 'action': 'dismiss', 'params': {}}
                            ]
                        })

        return insights

    def _detect_missing_meals(self) -> List[Dict[str, Any]]:
        """Suggest adding meal planning for days with no dining reservations."""
        insights = []

        if not self.trip.get('start_date') or not self.trip.get('end_date'):
            return insights

        trip_start = self._parse_datetime(self.trip['start_date'])
        trip_end = self._parse_datetime(self.trip['end_date'])

        if not trip_start or not trip_end:
            return insights

        # Only suggest if trip is 2+ days and has NO dining reservations
        trip_days = (trip_end - trip_start).days
        if trip_days >= 2 and len(self.dining) == 0:
            insights.append({
                'id': 'missing_meals',
                'type': 'missing_element',
                'severity': 'info',
                'title': 'No dining reservations',
                'description': f'{trip_days}-day trip with no restaurant reservations. Consider planning meals in advance.',
                'actions': [
                    {'label': 'Add Dining', 'action': 'add_element', 'params': {'type': 'dining'}},
                    {'label': 'Dismiss', 'action': 'dismiss', 'params': {}}
                ]
            })

        return insights

    def _bookings_conflict(self, booking1: Dict[str, Any], booking2: Dict[str, Any]) -> bool:
        """Check if two bookings have impossible time overlap."""
        start1 = self._parse_datetime(booking1.get('start_time'))
        end1 = self._parse_datetime(booking1.get('end_time'))
        start2 = self._parse_datetime(booking2.get('start_time'))
        end2 = self._parse_datetime(booking2.get('end_time'))

        if not all([start1, end1, start2, end2]):
            return False

        # True conflict: overlapping time ranges
        return start1 < end2 and start2 < end1

    def _parse_datetime(self, dt_string: Optional[str]) -> Optional[datetime]:
        """Parse datetime string safely."""
        if not dt_string:
            return None

        try:
            # Try ISO format with timezone
            if 'T' in dt_string:
                return datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
            # Try date only
            return datetime.strptime(dt_string, '%Y-%m-%d')
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse datetime: {dt_string} - {e}")
            return None
