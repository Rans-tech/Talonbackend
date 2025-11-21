-- Migration: 005_insights_learning.sql
-- Purpose: Track user interactions with insights to enable self-learning loop
-- Created: 2025-11-21

-- Track detailed feedback on insights (was it helpful? accurate?)
CREATE TABLE IF NOT EXISTS insights_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    trip_id UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    insight_id TEXT NOT NULL,
    insight_type TEXT NOT NULL, -- 'action_required', 'recommendations', 'good_to_know'
    insight_category TEXT NOT NULL, -- 'accommodation_gap', 'tight_timing', etc.

    -- User action taken
    action_taken TEXT NOT NULL, -- 'dismissed', 'acted', 'rated', 'ignored'
    action_details JSONB, -- Which action button clicked, etc.

    -- Feedback (optional)
    helpful BOOLEAN, -- Was this insight helpful?
    accurate BOOLEAN, -- Was this insight accurate?
    rating INTEGER CHECK (rating >= 1 AND rating <= 5), -- 1-5 stars
    user_comment TEXT,

    -- Context for learning
    trip_destination TEXT,
    trip_duration_days INTEGER,
    user_tier TEXT, -- 'family', 'pro', 'enterprise'

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    action_at TIMESTAMP WITH TIME ZONE,

    -- Performance metrics
    time_to_action_seconds INTEGER, -- How long before user took action?

    UNIQUE(user_id, trip_id, insight_id)
);

-- Pattern learning - aggregate insights performance
CREATE TABLE IF NOT EXISTS insights_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Pattern identification
    insight_category TEXT NOT NULL UNIQUE, -- e.g., 'accommodation_gap', 'tight_timing'
    insight_type TEXT NOT NULL, -- 'action_required', 'recommendations', 'good_to_know'

    -- Learning metrics (calculated from feedback)
    total_shown INTEGER DEFAULT 0,
    total_dismissed INTEGER DEFAULT 0,
    total_acted INTEGER DEFAULT 0,
    total_rated INTEGER DEFAULT 0,

    -- Performance scores
    acceptance_rate NUMERIC(5,2), -- % of users who acted on it
    dismissal_rate NUMERIC(5,2), -- % of users who dismissed it
    average_rating NUMERIC(3,2), -- Average 1-5 star rating
    helpful_percentage NUMERIC(5,2), -- % marked as helpful
    accurate_percentage NUMERIC(5,2), -- % marked as accurate

    -- Learning recommendations (auto-calculated)
    confidence_score NUMERIC(5,2), -- 0-100, based on sample size + performance
    recommendation TEXT, -- 'upgrade', 'keep', 'downgrade', 'disable'
    auto_apply BOOLEAN DEFAULT false, -- Should this be auto-applied?

    -- Metadata
    last_calculated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    sample_size INTEGER DEFAULT 0,

    -- Knowledge Base integration
    kb_rule_name TEXT, -- Maps to rule in TALON_KNOWLEDGE_BASE.md
    kb_last_updated_at TIMESTAMP WITH TIME ZONE
);

-- Knowledge Base learnings - store discovered patterns to update KB
CREATE TABLE IF NOT EXISTS kb_learnings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- What was learned?
    learning_type TEXT NOT NULL, -- 'new_rule', 'rule_adjustment', 'user_preference', 'pattern_discovery'
    category TEXT NOT NULL, -- 'accommodation', 'timing', 'transportation', etc.

    -- The learning content (to be added to KB)
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    rule_yaml TEXT, -- Formatted rule for KB

    -- Evidence supporting this learning
    evidence JSONB NOT NULL, -- Stats, examples, user quotes
    confidence_score NUMERIC(5,2) NOT NULL, -- 0-100
    sample_size INTEGER NOT NULL,

    -- Status
    status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'applied', 'rejected'
    reviewed_by TEXT,
    reviewed_at TIMESTAMP WITH TIME ZONE,

    -- KB integration
    applied_to_kb BOOLEAN DEFAULT false,
    kb_section TEXT, -- Which section of KB to update

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Prevent duplicate learnings
    UNIQUE(learning_type, category, title)
);

-- Indexes for fast queries
CREATE INDEX idx_insights_feedback_category ON insights_feedback(insight_category);
CREATE INDEX idx_insights_feedback_action ON insights_feedback(action_taken);
CREATE INDEX idx_insights_feedback_trip ON insights_feedback(trip_id);
CREATE INDEX idx_insights_patterns_category ON insights_patterns(insight_category);
CREATE INDEX idx_kb_learnings_status ON kb_learnings(status);
CREATE INDEX idx_kb_learnings_confidence ON kb_learnings(confidence_score DESC);

-- Enable RLS
ALTER TABLE insights_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE insights_patterns ENABLE ROW LEVEL SECURITY;
ALTER TABLE kb_learnings ENABLE ROW LEVEL SECURITY;

-- RLS Policies for feedback (user-scoped)
CREATE POLICY "Users can view own feedback"
    ON insights_feedback FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY "Users can insert own feedback"
    ON insights_feedback FOR INSERT
    WITH CHECK (user_id = auth.uid());

-- Patterns are read-only for all authenticated users
CREATE POLICY "Authenticated users can view patterns"
    ON insights_patterns FOR SELECT
    USING (auth.uid() IS NOT NULL);

-- KB learnings are read-only for all authenticated users
CREATE POLICY "Authenticated users can view kb learnings"
    ON kb_learnings FOR SELECT
    USING (auth.uid() IS NOT NULL);

-- Add comments for documentation
COMMENT ON TABLE insights_feedback IS 'Tracks user interactions with TALON Insights for self-learning loop';
COMMENT ON TABLE insights_patterns IS 'Aggregated learning patterns from user feedback';
COMMENT ON TABLE kb_learnings IS 'Discovered patterns to be integrated into TALON Knowledge Base';
