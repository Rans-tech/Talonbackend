# app.py Update Required

## Add datetime import at top
```python
from datetime import datetime
```

## Replace get_trip_insights() function (around line 1565)

Find this code:
```python
# Check if we have cached insights (1 hour cache)
cache_key = f"insights_{trip_id}"
# TODO: Implement Redis caching for production
# For now, generate fresh insights each time

# Run rule-based detection
detector = InsightsDetector(trip, elements)
base_insights = detector.analyze()
```

Replace with:
```python
# SELF-LEARNING LOOP: Query learned patterns FIRST (proactive)
pattern_matcher = PatternMatcher()
proactive = pattern_matcher.get_proactive_insights(trip, elements)

# Run rule-based detection (critical issues)
detector = InsightsDetector(trip, elements)
base_insights = detector.analyze()
```

Then after the AI enhancement, add this before the result:
```python
# Merge proactive learned patterns into recommendations
for proactive_insight in proactive.get('proactive_recommendations', []):
    confidence = proactive_insight.get('learned_from', {}).get('confidence', 0)
    if confidence >= 70:
        enhanced_insights['recommendations'].insert(0, proactive_insight)
    elif confidence >= 50:
        enhanced_insights['good_to_know'].append(proactive_insight)
```

And update result to:
```python
result = {
    'success': True,
    'trip_id': trip_id,
    'generated_at': datetime.utcnow().isoformat(),
    'insights': enhanced_insights,
    'counts': {
        'action_required': len(enhanced_insights.get('action_required', [])),
        'recommendations': len(enhanced_insights.get('recommendations', [])),
        'good_to_know': len(enhanced_insights.get('good_to_know', []))
    },
    'learning_data': {
        'proactive_patterns_used': len(proactive.get('proactive_recommendations', [])),
        'uses_learned_patterns': len(proactive.get('proactive_recommendations', [])) > 0
    }
}
```

## OR: Just copy the entire updated endpoint from updated_insights_endpoint.py
