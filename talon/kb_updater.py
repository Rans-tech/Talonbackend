# talon/kb_updater.py
# Purpose: Updates TALON_KNOWLEDGE_BASE.md with learned patterns from user feedback

import os
import re
import logging
from typing import List, Dict, Any
from datetime import datetime
from talon.database import db_client

logger = logging.getLogger(__name__)

KB_FILE_PATH = os.path.join(os.path.dirname(__file__), '..', 'TALON_KNOWLEDGE_BASE.md')


class KnowledgeBaseUpdater:
    """
    Updates the TALON Knowledge Base with learned patterns.
    Writes approved learnings back to TALON_KNOWLEDGE_BASE.md.
    """

    def __init__(self):
        self.db = db_client.client
        self.kb_path = KB_FILE_PATH

    def update_kb_with_learnings(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Apply all approved learnings to the Knowledge Base file.

        Args:
            dry_run: If True, don't actually write to file (for testing)

        Returns:
            Summary of updates applied
        """
        try:
            # Get all approved learnings not yet applied
            response = self.db.table('kb_learnings')\
                .select('*')\
                .eq('status', 'approved')\
                .eq('applied_to_kb', False)\
                .order('confidence_score', desc=True)\
                .execute()

            learnings = response.data if response.data else []

            if not learnings:
                logger.info("No approved learnings to apply")
                return {'applied': 0, 'learnings': []}

            # Read current KB content
            if not os.path.exists(self.kb_path):
                logger.error(f"Knowledge Base file not found: {self.kb_path}")
                return {'error': 'KB file not found', 'applied': 0}

            with open(self.kb_path, 'r', encoding='utf-8') as f:
                kb_content = f.read()

            # Apply each learning
            applied_count = 0
            applied_learnings = []

            for learning in learnings:
                updated_content, success = self._apply_learning_to_kb(kb_content, learning)

                if success:
                    kb_content = updated_content
                    applied_count += 1
                    applied_learnings.append({
                        'id': learning['id'],
                        'title': learning['title'],
                        'category': learning['category']
                    })

                    # Mark as applied
                    if not dry_run:
                        self.db.table('kb_learnings').update({
                            'applied_to_kb': True,
                            'kb_last_updated_at': datetime.utcnow().isoformat()
                        }).eq('id', learning['id']).execute()

            # Write updated KB back to file
            if not dry_run and applied_count > 0:
                # Create backup first
                backup_path = f"{self.kb_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                with open(backup_path, 'w', encoding='utf-8') as f:
                    f.write(self._read_original_kb())

                # Write updated content
                with open(self.kb_path, 'w', encoding='utf-8') as f:
                    f.write(kb_content)

                logger.info(f"Applied {applied_count} learnings to Knowledge Base")

            return {
                'applied': applied_count,
                'learnings': applied_learnings,
                'dry_run': dry_run
            }

        except Exception as e:
            logger.error(f"Error updating KB: {e}", exc_info=True)
            return {'error': str(e), 'applied': 0}

    def _apply_learning_to_kb(
        self,
        kb_content: str,
        learning: Dict[str, Any]
    ) -> tuple[str, bool]:
        """
        Apply a single learning to the KB content.

        Returns:
            (updated_content, success)
        """
        try:
            # Find the LEARNING & IMPROVEMENT section
            learning_section_pattern = r'## LEARNING & IMPROVEMENT'
            match = re.search(learning_section_pattern, kb_content)

            if not match:
                logger.error("Could not find LEARNING & IMPROVEMENT section in KB")
                return kb_content, False

            insertion_point = match.end()

            # Generate the learning entry
            learning_entry = self._format_learning_entry(learning)

            # Insert at the beginning of the Learning section
            updated_content = (
                kb_content[:insertion_point] +
                "\n\n" + learning_entry +
                kb_content[insertion_point:]
            )

            return updated_content, True

        except Exception as e:
            logger.error(f"Error applying learning: {e}", exc_info=True)
            return kb_content, False

    def _format_learning_entry(self, learning: Dict[str, Any]) -> str:
        """Format a learning entry for insertion into KB."""

        evidence = learning.get('evidence', {})
        metrics = evidence.get('metrics', {})

        entry = f"""### 🤖 LEARNED PATTERN: {learning['title']}
**Category:** {learning['category']}
**Confidence:** {learning['confidence_score']:.0f}%
**Sample Size:** {learning['sample_size']} user interactions
**Learned:** {learning.get('created_at', 'Unknown')}

**Description:**
{learning['description']}

**Evidence:**
- Acceptance Rate: {metrics.get('acceptance_rate', 0):.0f}%
- Dismissal Rate: {metrics.get('dismissal_rate', 0):.0f}%
- Average Rating: {metrics.get('average_rating', 0):.1f}/5
- Helpful: {metrics.get('helpful_percentage', 0):.0f}%
- Accurate: {metrics.get('accurate_percentage', 0):.0f}%

**User Comments:**
{self._format_comments(evidence.get('sample_comments', []))}

**Recommendation:** {metrics.get('recommendation', 'N/A')}

{learning.get('rule_yaml', '')}

---
"""
        return entry

    def _format_comments(self, comments: List[str]) -> str:
        """Format user comments for KB."""
        if not comments:
            return "_No comments provided_"

        formatted = []
        for i, comment in enumerate(comments[:3], 1):  # Top 3 comments
            formatted.append(f"{i}. \"{comment}\"")

        return "\n".join(formatted)

    def _read_original_kb(self) -> str:
        """Read the original KB content."""
        with open(self.kb_path, 'r', encoding='utf-8') as f:
            return f.read()

    def generate_learning_summary_report(self) -> str:
        """
        Generate a markdown report of all learnings.
        Useful for review before applying to KB.
        """
        try:
            # Get all approved learnings
            response = self.db.table('kb_learnings')\
                .select('*')\
                .eq('status', 'approved')\
                .order('confidence_score', desc=True)\
                .execute()

            learnings = response.data if response.data else []

            if not learnings:
                return "# TALON Insights Learning Report\n\nNo approved learnings to report."

            report = f"""# TALON Insights Learning Report
**Generated:** {datetime.utcnow().isoformat()}
**Total Approved Learnings:** {len(learnings)}

---

"""

            for learning in learnings:
                evidence = learning.get('evidence', {})
                metrics = evidence.get('metrics', {})

                report += f"""## {learning['title']}

**Category:** {learning['category']}
**Type:** {learning['learning_type']}
**Confidence:** {learning['confidence_score']:.0f}%
**Sample Size:** {learning['sample_size']}
**Status:** {'✅ Applied to KB' if learning.get('applied_to_kb') else '⏳ Pending Application'}

### Description
{learning['description']}

### Performance Metrics
- Acceptance Rate: {metrics.get('acceptance_rate', 0):.0f}%
- Dismissal Rate: {metrics.get('dismissal_rate', 0):.0f}%
- Average Rating: {metrics.get('average_rating', 0):.1f}/5
- Recommendation: **{metrics.get('recommendation', 'N/A').upper()}**

### User Feedback
{self._format_comments(evidence.get('sample_comments', []))}

---

"""

            return report

        except Exception as e:
            logger.error(f"Error generating report: {e}", exc_info=True)
            return f"# Error Generating Report\n\n{str(e)}"
