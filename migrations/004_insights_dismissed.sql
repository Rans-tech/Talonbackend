-- Migration: 004_insights_dismissed.sql
-- Purpose: Track which insights users have dismissed to avoid showing them repeatedly
-- Created: 2025-11-21

-- Create insights_dismissed table
CREATE TABLE IF NOT EXISTS insights_dismissed (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    trip_id UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    insight_id TEXT NOT NULL, -- Matches the insight.id from the insights response
    insight_type TEXT NOT NULL, -- 'action_required', 'recommendations', 'good_to_know'
    dismissed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Prevent duplicate dismissals
    UNIQUE(user_id, trip_id, insight_id)
);

-- Add indexes for fast lookups
CREATE INDEX idx_insights_dismissed_user_trip ON insights_dismissed(user_id, trip_id);
CREATE INDEX idx_insights_dismissed_trip ON insights_dismissed(trip_id);

-- Enable RLS
ALTER TABLE insights_dismissed ENABLE ROW LEVEL SECURITY;

-- RLS Policies: Users can only see/manage their own dismissed insights
CREATE POLICY "Users can view own dismissed insights"
    ON insights_dismissed FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY "Users can insert own dismissed insights"
    ON insights_dismissed FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can delete own dismissed insights"
    ON insights_dismissed FOR DELETE
    USING (user_id = auth.uid());

-- Add comment for documentation
COMMENT ON TABLE insights_dismissed IS 'Tracks which TALON Insights users have dismissed to prevent showing them repeatedly';
