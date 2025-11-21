#!/usr/bin/env python3
# test_insights.py
# Purpose: Quick test of insights detection logic

from talon.insights_detector import InsightsDetector
from talon.insights_ai import InsightsAI
from datetime import datetime, timedelta

# Test data: Disney trip with known issues
trip = {
    'id': 'test-123',
    'destination': 'Orlando, FL',
    'start_date': '2025-11-05',
    'end_date': '2025-11-12',
    'notes': 'Family trip to Disney World'
}

# Scenario 1: Accommodation gap (should trigger ACTION REQUIRED)
elements_with_gap = [
    {
        'id': 'flight-1',
        'type': 'flight',
        'name': 'Southwest 1234',
        'start_time': '2025-11-05T20:00:00Z',
        'end_time': '2025-11-05T22:00:00Z'  # Arrive 10 PM Nov 5
    },
    {
        'id': 'hotel-1',
        'type': 'accommodation',
        'name': 'Four Seasons Orlando',
        'start_time': '2025-11-07T15:00:00Z',  # Check-in Nov 7 3 PM (GAP!)
        'end_time': '2025-11-12T11:00:00Z'
    },
    {
        'id': 'flight-2',
        'type': 'flight',
        'name': 'Southwest 5678',
        'start_time': '2025-11-12T12:40:00Z',  # Depart 12:40 PM
        'end_time': '2025-11-12T14:30:00Z'
    }
]

# Scenario 2: Tight timing (should trigger RECOMMENDATION)
elements_with_tight_timing = [
    {
        'id': 'hotel-1',
        'type': 'accommodation',
        'name': 'Four Seasons Orlando',
        'start_time': '2025-11-05T15:00:00Z',
        'end_time': '2025-11-12T11:00:00Z'  # Checkout 11 AM
    },
    {
        'id': 'flight-2',
        'type': 'flight',
        'name': 'Southwest 5678',
        'start_time': '2025-11-12T12:40:00Z',  # Flight 12:40 PM (only 1h 40m gap)
        'end_time': '2025-11-12T14:30:00Z'
    }
]

# Scenario 3: Normal overlaps (should NOT trigger alerts)
elements_normal = [
    {
        'id': 'hotel-1',
        'type': 'accommodation',
        'name': 'Four Seasons Orlando',
        'start_time': '2025-11-05T15:00:00Z',
        'end_time': '2025-11-12T11:00:00Z'
    },
    {
        'id': 'dinner-1',
        'type': 'dining',
        'name': "Narcoossee's",
        'start_time': '2025-11-06T19:00:00Z',  # During hotel stay - NORMAL
        'end_time': '2025-11-06T21:00:00Z'
    },
    {
        'id': 'activity-1',
        'type': 'activity',
        'name': 'Magic Kingdom',
        'start_time': '2025-11-07T09:00:00Z',  # During hotel stay - NORMAL
        'end_time': '2025-11-07T22:00:00Z'
    }
]

def test_scenario(name: str, trip_data: dict, elements: list):
    """Test a scenario and print results."""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")

    # Run detection
    detector = InsightsDetector(trip_data, elements)
    insights = detector.analyze()

    # Print results
    print(f"\n🚨 ACTION REQUIRED: {len(insights['action_required'])}")
    for insight in insights['action_required']:
        print(f"   - {insight['title']}")
        print(f"     {insight['description']}")

    print(f"\n⚠️  RECOMMENDATIONS: {len(insights['recommendations'])}")
    for insight in insights['recommendations']:
        print(f"   - {insight['title']}")
        print(f"     {insight['description']}")

    print(f"\nℹ️  GOOD TO KNOW: {len(insights['good_to_know'])}")
    for insight in insights['good_to_know']:
        print(f"   - {insight['title']}")

    # Summary
    total = (len(insights['action_required']) +
             len(insights['recommendations']) +
             len(insights['good_to_know']))
    print(f"\nTOTAL INSIGHTS: {total}")

if __name__ == '__main__':
    print("TALON Insights Detection Test")
    print("Testing smart detection logic (no false positives)")

    # Test 1: Accommodation gap
    test_scenario(
        "Accommodation Gap",
        trip,
        elements_with_gap
    )

    # Test 2: Tight timing
    test_scenario(
        "Tight Timing",
        trip,
        elements_with_tight_timing
    )

    # Test 3: Normal overlaps (should be clean)
    test_scenario(
        "Normal Overlaps (Should be clean)",
        trip,
        elements_normal
    )

    print(f"\n{'='*60}")
    print("✅ TEST COMPLETE")
    print(f"{'='*60}\n")
