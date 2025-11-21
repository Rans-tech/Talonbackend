# talon/insights_learning.py
# Purpose: Self-learning loop for TALON Insights - learns from user behavior and updates Knowledge Base

import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from talon.database import db_client

logger = logging.getLogger(__name__)


class InsightsLearning:
    """
    Implements the self-learning loop for TALON Insights.
    Tracks user behavior, identifies patterns, and updates Knowledge Base.
    """

    def __init__(self):
        self.db = db_client.client

    def record_feedback(
        self,
        user_id: str,
        trip_id: str,
        insight_id: str,
        insight_type: str,
        insight_category: str,
        action_taken: str,
        action_details: Optional[Dict[str, Any]] = None,
        helpful: Optional[bool] = None,
        accurate: Optional[bool] = None,
        rating: Optional[int] = None,
        user_comment: Optional[str] = None,
        trip_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Record user feedback on an insight.

        Args:
            user_id: User who interacted with insight
            trip_id: Trip the insight was for
            insight_id: Unique insight ID
            insight_type: 'action_required', 'recommendations', 'good_to_know'
            insight_category: 'accommodation_gap', 'tight_timing', etc.
            action_taken: 'dismissed', 'acted', 'rated', 'ignored'
            action_details: Which button clicked, etc.
            helpful: Was this insight helpful?
            accurate: Was this insight accurate?
            rating: 1-5 star rating
            user_comment: Optional text feedback
            trip_context: Trip destination, duration, etc.

        Returns:
            Feedback record
        """
        try:
            feedback_data = {
                'user_id': user_id,
                'trip_id': trip_id,
                'insight_id': insight_id,
                'insight_type': insight_type,
                'insight_category': insight_category,
                'action_taken': action_taken,
                'action_details': action_details or {},
                'helpful': helpful,
                'accurate': accurate,
                'rating': rating,
                'user_comment': user_comment,
                'action_at': datetime.utcnow().isoformat(),
            }

            # Add trip context if provided
            if trip_context:
                feedback_data.update({
                    'trip_destination': trip_context.get('destination'),
                    'trip_duration_days': trip_context.get('duration_days'),
                    'user_tier': trip_context.get('user_tier')
                })

            # Insert feedback
            response = self.db.table('insights_feedback').upsert(feedback_data).execute()

            logger.info(f"Recorded feedback: {insight_category} -> {action_taken}")

            # Trigger pattern analysis if we have enough data
            self._check_and_trigger_analysis(insight_category)

            return response.data[0] if response.data else {}

        except Exception as e:
            logger.error(f"Error recording feedback: {e}", exc_info=True)
            return {}

    def analyze_patterns(self, insight_category: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze feedback patterns and update insights_patterns table.

        Args:
            insight_category: Specific category to analyze, or None for all

        Returns:
            Analysis results
        """
        try:
            # Get all feedback, optionally filtered by category
            query = self.db.table('insights_feedback').select('*')
            if insight_category:
                query = query.eq('insight_category', insight_category)

            feedback_response = query.execute()
            feedback_data = feedback_response.data

            if not feedback_data:
                logger.info(f"No feedback data to analyze for {insight_category or 'all categories'}")
                return {}

            # Group by category
            categories = {}
            for fb in feedback_data:
                cat = fb['insight_category']
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(fb)

            # Analyze each category
            results = {}
            for cat, feedbacks in categories.items():
                pattern = self._calculate_pattern_metrics(cat, feedbacks)
                results[cat] = pattern

                # Update insights_patterns table
                self.db.table('insights_patterns').upsert(pattern).execute()

                # Check if we should create a KB learning
                if pattern['confidence_score'] >= 70:
                    self._consider_kb_learning(cat, pattern, feedbacks)

            logger.info(f"Analyzed patterns for {len(results)} categories")
            return results

        except Exception as e:
            logger.error(f"Error analyzing patterns: {e}", exc_info=True)
            return {}

    def _calculate_pattern_metrics(
        self,
        category: str,
        feedbacks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate performance metrics for an insight category."""

        total_shown = len(feedbacks)
        total_dismissed = sum(1 for f in feedbacks if f['action_taken'] == 'dismissed')
        total_acted = sum(1 for f in feedbacks if f['action_taken'] == 'acted')
        total_rated = sum(1 for f in feedbacks if f['rating'] is not None)

        # Calculate rates
        acceptance_rate = (total_acted / total_shown * 100) if total_shown > 0 else 0
        dismissal_rate = (total_dismissed / total_shown * 100) if total_shown > 0 else 0

        # Average rating
        ratings = [f['rating'] for f in feedbacks if f['rating'] is not None]
        average_rating = sum(ratings) / len(ratings) if ratings else None

        # Helpful/accurate percentages
        helpful_count = sum(1 for f in feedbacks if f.get('helpful') is True)
        accurate_count = sum(1 for f in feedbacks if f.get('accurate') is True)
        helpful_percentage = (helpful_count / total_shown * 100) if total_shown > 0 else 0
        accurate_percentage = (accurate_count / total_shown * 100) if total_shown > 0 else 0

        # Calculate confidence score (based on sample size + performance)
        confidence_score = self._calculate_confidence(
            sample_size=total_shown,
            acceptance_rate=acceptance_rate,
            average_rating=average_rating,
            helpful_percentage=helpful_percentage
        )

        # Determine recommendation
        recommendation = self._determine_recommendation(
            acceptance_rate=acceptance_rate,
            dismissal_rate=dismissal_rate,
            average_rating=average_rating,
            confidence_score=confidence_score
        )

        # Determine insight type from first feedback
        insight_type = feedbacks[0]['insight_type'] if feedbacks else 'recommendations'

        return {
            'insight_category': category,
            'insight_type': insight_type,
            'total_shown': total_shown,
            'total_dismissed': total_dismissed,
            'total_acted': total_acted,
            'total_rated': total_rated,
            'acceptance_rate': round(acceptance_rate, 2),
            'dismissal_rate': round(dismissal_rate, 2),
            'average_rating': round(average_rating, 2) if average_rating else None,
            'helpful_percentage': round(helpful_percentage, 2),
            'accurate_percentage': round(accurate_percentage, 2),
            'confidence_score': round(confidence_score, 2),
            'recommendation': recommendation,
            'auto_apply': acceptance_rate > 80 and confidence_score > 80,
            'last_calculated_at': datetime.utcnow().isoformat(),
            'sample_size': total_shown
        }

    def _calculate_confidence(
        self,
        sample_size: int,
        acceptance_rate: float,
        average_rating: Optional[float],
        helpful_percentage: float
    ) -> float:
        """
        Calculate confidence score (0-100) based on sample size and performance.
        Higher score = more confident in the pattern.
        """
        # Sample size confidence (logarithmic scale)
        # 10 samples = 50%, 100 samples = 75%, 1000 samples = 90%
        import math
        size_confidence = min(90, 30 + (20 * math.log10(sample_size + 1)))

        # Performance confidence (weighted average)
        performance_scores = []

        if acceptance_rate is not None:
            # High acceptance or high dismissal both indicate clear signal
            clarity = max(acceptance_rate, 100 - acceptance_rate)
            performance_scores.append(clarity)

        if average_rating is not None:
            # Convert 1-5 rating to 0-100 scale
            rating_score = (average_rating - 1) / 4 * 100
            performance_scores.append(rating_score)

        if helpful_percentage is not None:
            performance_scores.append(helpful_percentage)

        performance_confidence = sum(performance_scores) / len(performance_scores) if performance_scores else 50

        # Weighted average (60% sample size, 40% performance)
        confidence = (size_confidence * 0.6) + (performance_confidence * 0.4)

        return min(100, max(0, confidence))

    def _determine_recommendation(
        self,
        acceptance_rate: float,
        dismissal_rate: float,
        average_rating: Optional[float],
        confidence_score: float
    ) -> str:
        """
        Determine what to do with this insight category.

        Returns: 'upgrade', 'keep', 'downgrade', 'disable'
        """
        # Need high confidence to make changes
        if confidence_score < 60:
            return 'keep'  # Not enough data yet

        # High acceptance = upgrade
        if acceptance_rate > 80:
            return 'upgrade'  # Consider auto-applying

        # Low acceptance = downgrade or disable
        if acceptance_rate < 20:
            if dismissal_rate > 70:
                return 'disable'  # Users actively don't want this
            return 'downgrade'  # Lower priority

        # Check rating if available
        if average_rating is not None:
            if average_rating >= 4.0:
                return 'upgrade'
            elif average_rating < 2.0:
                return 'downgrade'

        # Default: keep as-is
        return 'keep'

    def _consider_kb_learning(
        self,
        category: str,
        pattern: Dict[str, Any],
        feedbacks: List[Dict[str, Any]]
    ):
        """
        Check if this pattern should be added to Knowledge Base as a learning.
        """
        try:
            # Only create learnings for strong patterns
            if pattern['confidence_score'] < 70:
                return

            # Determine learning type
            if pattern['recommendation'] == 'upgrade':
                learning_type = 'rule_adjustment'
                title = f"Upgrade {category} to higher priority"
                description = f"Users accept this insight {pattern['acceptance_rate']:.0f}% of the time with {pattern['average_rating']:.1f}/5 rating. Consider making it more prominent."

            elif pattern['recommendation'] == 'disable':
                learning_type = 'rule_adjustment'
                title = f"Disable or revise {category} detection"
                description = f"Users dismiss this insight {pattern['dismissal_rate']:.0f}% of the time. Consider disabling or improving the detection logic."

            else:
                return  # No strong learning

            # Gather evidence
            evidence = {
                'metrics': pattern,
                'sample_comments': [
                    f['user_comment']
                    for f in feedbacks
                    if f.get('user_comment')
                ][:5],  # Top 5 comments
                'common_actions': self._get_common_actions(feedbacks)
            }

            # Create KB learning entry
            learning_data = {
                'learning_type': learning_type,
                'category': category,
                'title': title,
                'description': description,
                'rule_yaml': self._generate_rule_yaml(category, pattern),
                'evidence': evidence,
                'confidence_score': pattern['confidence_score'],
                'sample_size': pattern['sample_size'],
                'status': 'pending',
                'kb_section': 'LEARNING & IMPROVEMENT'
            }

            self.db.table('kb_learnings').insert(learning_data).execute()
            logger.info(f"Created KB learning for {category}: {title}")

        except Exception as e:
            logger.error(f"Error creating KB learning: {e}", exc_info=True)

    def _get_common_actions(self, feedbacks: List[Dict[str, Any]]) -> Dict[str, int]:
        """Get most common user actions from feedback."""
        actions = {}
        for fb in feedbacks:
            action = fb['action_taken']
            actions[action] = actions.get(action, 0) + 1
        return dict(sorted(actions.items(), key=lambda x: x[1], reverse=True))

    def _generate_rule_yaml(self, category: str, pattern: Dict[str, Any]) -> str:
        """Generate YAML rule format for Knowledge Base."""
        return f"""#### Rule: {category}
```yaml
trigger: insights_analysis
condition: |
  pattern_confidence > {pattern['confidence_score']:.0f}
  acceptance_rate = {pattern['acceptance_rate']:.0f}%
  average_rating = {pattern['average_rating']:.1f}/5
action: {pattern['recommendation']}
priority: {'high' if pattern['recommendation'] == 'upgrade' else 'low' if pattern['recommendation'] == 'downgrade' else 'medium'}
auto_apply: {str(pattern['auto_apply']).lower()}
learned_from: {pattern['sample_size']} user interactions
last_updated: {datetime.utcnow().isoformat()}
```"""

    def _check_and_trigger_analysis(self, category: str):
        """Check if we have enough data to trigger pattern analysis."""
        try:
            # Count feedback for this category
            response = self.db.table('insights_feedback')\
                .select('id', count='exact')\
                .eq('insight_category', category)\
                .execute()

            count = response.count if hasattr(response, 'count') else len(response.data or [])

            # Trigger analysis at milestones (10, 25, 50, 100, etc.)
            milestones = [10, 25, 50, 100, 250, 500, 1000]
            if count in milestones:
                logger.info(f"Milestone reached for {category}: {count} samples. Triggering analysis.")
                self.analyze_patterns(category)

        except Exception as e:
            logger.error(f"Error checking analysis trigger: {e}", exc_info=True)

    def get_pending_kb_learnings(self) -> List[Dict[str, Any]]:
        """Get all pending learnings to be reviewed and added to KB."""
        try:
            response = self.db.table('kb_learnings')\
                .select('*')\
                .eq('status', 'pending')\
                .order('confidence_score', desc=True)\
                .execute()

            return response.data if response.data else []

        except Exception as e:
            logger.error(f"Error fetching pending learnings: {e}", exc_info=True)
            return []

    def approve_kb_learning(self, learning_id: str, reviewer: str) -> bool:
        """Approve a learning and mark it ready for KB integration."""
        try:
            self.db.table('kb_learnings').update({
                'status': 'approved',
                'reviewed_by': reviewer,
                'reviewed_at': datetime.utcnow().isoformat()
            }).eq('id', learning_id).execute()

            logger.info(f"Approved KB learning {learning_id}")
            return True

        except Exception as e:
            logger.error(f"Error approving learning: {e}", exc_info=True)
            return False
