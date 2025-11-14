-- ============================================================================
-- EXPENSE APPROVAL WORKFLOW MIGRATION
-- ============================================================================
-- Purpose: Add manager assignments and expense submission/approval workflow
-- Date: November 14, 2025
-- ============================================================================

-- Add manager_id to organization_members for direct manager assignment
ALTER TABLE organization_members
ADD COLUMN IF NOT EXISTS manager_id UUID REFERENCES profiles(id) ON DELETE SET NULL;

-- Add department field for future team-based filtering
ALTER TABLE organization_members
ADD COLUMN IF NOT EXISTS department TEXT;

-- Index for manager lookups
CREATE INDEX IF NOT EXISTS idx_organization_members_manager_id ON organization_members(manager_id);

-- ============================================================================
-- EXPENSE SUBMISSIONS TABLE
-- ============================================================================
-- Tracks expense submission and approval workflow
CREATE TABLE IF NOT EXISTS expense_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expense_id UUID NOT NULL REFERENCES expenses(id) ON DELETE CASCADE,
    trip_id UUID NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

    -- Submission details
    submitted_by UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_amount NUMERIC(10, 2) NOT NULL,
    submission_notes TEXT,

    -- Approval workflow
    status TEXT NOT NULL DEFAULT 'draft' CHECK (
        status IN ('draft', 'submitted', 'approved', 'rejected', 'reimbursed')
    ),

    -- Approver details
    approver_id UUID REFERENCES profiles(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    approved_amount NUMERIC(10, 2), -- Can differ if partially approved
    approval_notes TEXT,
    rejection_reason TEXT,

    -- Reimbursement tracking
    reimbursed_at TIMESTAMPTZ,
    reimbursed_by UUID REFERENCES profiles(id) ON DELETE SET NULL,
    reimbursement_method TEXT, -- 'bank_transfer', 'payroll', 'check', etc.
    reimbursement_reference TEXT, -- Transaction ID, check number, etc.

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- EXPENSE APPROVAL SETTINGS (Per Organization)
-- ============================================================================
CREATE TABLE IF NOT EXISTS expense_approval_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE CASCADE,

    -- Approval thresholds
    require_approval BOOLEAN NOT NULL DEFAULT true,
    auto_approve_below_amount NUMERIC(10, 2) DEFAULT 0, -- Auto-approve expenses under this amount
    require_admin_approval_above NUMERIC(10, 2) DEFAULT 1000, -- Amounts above this need admin approval

    -- Policy settings
    require_receipt BOOLEAN NOT NULL DEFAULT true,
    require_receipt_above_amount NUMERIC(10, 2) DEFAULT 25,
    max_expense_age_days INTEGER DEFAULT 90, -- Can't submit expenses older than this

    -- Notifications
    notify_manager_on_submission BOOLEAN DEFAULT true,
    notify_submitter_on_decision BOOLEAN DEFAULT true,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_expense_submissions_expense_id ON expense_submissions(expense_id);
CREATE INDEX IF NOT EXISTS idx_expense_submissions_trip_id ON expense_submissions(trip_id);
CREATE INDEX IF NOT EXISTS idx_expense_submissions_organization_id ON expense_submissions(organization_id);
CREATE INDEX IF NOT EXISTS idx_expense_submissions_submitted_by ON expense_submissions(submitted_by);
CREATE INDEX IF NOT EXISTS idx_expense_submissions_approver_id ON expense_submissions(approver_id);
CREATE INDEX IF NOT EXISTS idx_expense_submissions_status ON expense_submissions(status);
CREATE INDEX IF NOT EXISTS idx_expense_submissions_submitted_at ON expense_submissions(submitted_at);

-- ============================================================================
-- UPDATED_AT TRIGGERS
-- ============================================================================
CREATE TRIGGER update_expense_submissions_updated_at BEFORE UPDATE ON expense_submissions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_expense_approval_settings_updated_at BEFORE UPDATE ON expense_approval_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================
ALTER TABLE expense_submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE expense_approval_settings ENABLE ROW LEVEL SECURITY;

-- Expense Submissions: Users can view their own submissions
CREATE POLICY "Users can view their own submissions" ON expense_submissions
    FOR SELECT USING (
        submitted_by = auth.uid()
    );

-- Expense Submissions: Managers can view their team's submissions
CREATE POLICY "Managers can view team submissions" ON expense_submissions
    FOR SELECT USING (
        submitted_by IN (
            SELECT user_id FROM organization_members
            WHERE manager_id = auth.uid()
            AND status = 'active'
            AND organization_id = expense_submissions.organization_id
        )
    );

-- Expense Submissions: Admins can view all org submissions
CREATE POLICY "Admins can view all org submissions" ON expense_submissions
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id FROM organization_members
            WHERE user_id = auth.uid()
            AND status = 'active'
            AND role IN ('owner', 'admin')
        )
    );

-- Expense Submissions: Users can insert their own submissions
CREATE POLICY "Users can create submissions" ON expense_submissions
    FOR INSERT WITH CHECK (
        submitted_by = auth.uid()
    );

-- Expense Submissions: Managers and admins can update (approve/reject)
CREATE POLICY "Managers can update team submissions" ON expense_submissions
    FOR UPDATE USING (
        -- User's own submission (can edit if draft)
        (submitted_by = auth.uid() AND status = 'draft')
        OR
        -- Manager of submitter
        (submitted_by IN (
            SELECT user_id FROM organization_members
            WHERE manager_id = auth.uid()
            AND status = 'active'
            AND organization_id = expense_submissions.organization_id
        ))
        OR
        -- Org admin
        (organization_id IN (
            SELECT organization_id FROM organization_members
            WHERE user_id = auth.uid()
            AND status = 'active'
            AND role IN ('owner', 'admin')
        ))
    );

-- Expense Approval Settings: Members can view org settings
CREATE POLICY "Members can view approval settings" ON expense_approval_settings
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id FROM organization_members
            WHERE user_id = auth.uid() AND status = 'active'
        )
    );

-- Expense Approval Settings: Admins can update settings
CREATE POLICY "Admins can update approval settings" ON expense_approval_settings
    FOR ALL USING (
        organization_id IN (
            SELECT organization_id FROM organization_members
            WHERE user_id = auth.uid()
            AND status = 'active'
            AND role IN ('owner', 'admin')
        )
    );

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to get a user's manager
CREATE OR REPLACE FUNCTION get_user_manager(p_user_id UUID, p_org_id UUID)
RETURNS UUID AS $$
BEGIN
    RETURN (
        SELECT manager_id
        FROM organization_members
        WHERE user_id = p_user_id
        AND organization_id = p_org_id
        AND status = 'active'
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to check if user is manager of another user
CREATE OR REPLACE FUNCTION is_manager_of(p_manager_id UUID, p_user_id UUID, p_org_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1
        FROM organization_members
        WHERE user_id = p_user_id
        AND organization_id = p_org_id
        AND manager_id = p_manager_id
        AND status = 'active'
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get all team members for a manager
CREATE OR REPLACE FUNCTION get_team_members(p_manager_id UUID, p_org_id UUID)
RETURNS TABLE (
    user_id UUID,
    full_name TEXT,
    email TEXT,
    department TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        om.user_id,
        p.full_name,
        p.email,
        om.department
    FROM organization_members om
    JOIN profiles p ON p.id = om.user_id
    WHERE om.manager_id = p_manager_id
    AND om.organization_id = p_org_id
    AND om.status = 'active';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================================
-- AUDIT LOG HELPER
-- ============================================================================

-- Function to log expense submission events
CREATE OR REPLACE FUNCTION log_expense_submission_event()
RETURNS TRIGGER AS $$
BEGIN
    -- Log to audit_logs when submission status changes
    IF (TG_OP = 'UPDATE' AND OLD.status IS DISTINCT FROM NEW.status) THEN
        INSERT INTO audit_logs (
            organization_id,
            user_id,
            action,
            resource_type,
            resource_id,
            changes
        ) VALUES (
            NEW.organization_id,
            auth.uid(),
            CASE NEW.status
                WHEN 'submitted' THEN 'expense_submitted'
                WHEN 'approved' THEN 'expense_approved'
                WHEN 'rejected' THEN 'expense_rejected'
                WHEN 'reimbursed' THEN 'expense_reimbursed'
                ELSE 'expense_status_changed'
            END,
            'expense_submission',
            NEW.id,
            jsonb_build_object(
                'old_status', OLD.status,
                'new_status', NEW.status,
                'expense_id', NEW.expense_id,
                'submitted_amount', NEW.submitted_amount,
                'approved_amount', NEW.approved_amount
            )
        );
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Create trigger for audit logging
CREATE TRIGGER expense_submission_audit_log
    AFTER INSERT OR UPDATE ON expense_submissions
    FOR EACH ROW EXECUTE FUNCTION log_expense_submission_event();

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Insert default approval settings for existing organizations
INSERT INTO expense_approval_settings (organization_id)
SELECT id FROM organizations
WHERE id NOT IN (SELECT organization_id FROM expense_approval_settings)
ON CONFLICT (organization_id) DO NOTHING;
