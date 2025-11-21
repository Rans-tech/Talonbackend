-- ============================================================================
-- SIMPLIFY TO 3-ROLE SYSTEM MIGRATION
-- ============================================================================
-- Purpose: Simplify from 4 roles to 3 roles, remove manager hierarchy
-- Date: November 17, 2025
-- Changes:
--   - Roles: owner/admin/member/viewer → admin/approver/member
--   - Remove manager_id and department columns
--   - Remove manager hierarchy helper functions
--   - Update RLS policies for simpler permission model
--   - Add privacy: members can't see other members' expenses/trips
-- ============================================================================

-- ============================================================================
-- STEP 1: MIGRATE EXISTING DATA
-- ============================================================================

-- Migrate 'viewer' role to 'member' (viewers become regular members)
UPDATE organization_members
SET role = 'member'
WHERE role = 'viewer';

-- Keep 'owner' and 'admin' as 'admin' (both have same permissions now)
-- We'll keep both values in the enum for backward compatibility,
-- but treat them the same in permissions

-- ============================================================================
-- STEP 2: UPDATE ROLE ENUM
-- ============================================================================

-- Drop existing constraint
ALTER TABLE organization_members
DROP CONSTRAINT IF EXISTS organization_members_role_check;

-- Add new constraint with simplified roles
-- Keep 'owner' for backward compatibility, add 'approver'
ALTER TABLE organization_members
ADD CONSTRAINT organization_members_role_check
CHECK (role IN ('owner', 'admin', 'approver', 'member'));

-- ============================================================================
-- STEP 3: REMOVE MANAGER HIERARCHY
-- ============================================================================

-- Drop manager-related columns
ALTER TABLE organization_members
DROP COLUMN IF EXISTS manager_id;

ALTER TABLE organization_members
DROP COLUMN IF EXISTS department;

-- Drop index
DROP INDEX IF EXISTS idx_organization_members_manager_id;

-- Drop helper functions (no longer needed)
DROP FUNCTION IF EXISTS get_user_manager(UUID, UUID);
DROP FUNCTION IF EXISTS is_manager_of(UUID, UUID, UUID);
DROP FUNCTION IF EXISTS get_team_members(UUID, UUID);

-- ============================================================================
-- STEP 4: UPDATE EXPENSE SUBMISSION RLS POLICIES
-- ============================================================================

-- Drop old manager-based policies
DROP POLICY IF EXISTS "Managers can view team submissions" ON expense_submissions;
DROP POLICY IF EXISTS "Managers can update team submissions" ON expense_submissions;

-- Drop old policies that we'll replace
DROP POLICY IF EXISTS "Users can view their own submissions" ON expense_submissions;
DROP POLICY IF EXISTS "Admins can view all org submissions" ON expense_submissions;
DROP POLICY IF EXISTS "Users can create submissions" ON expense_submissions;

-- New simplified policies
-- Members can view only their own submissions
CREATE POLICY "Members can view own submissions" ON expense_submissions
    FOR SELECT USING (
        submitted_by = auth.uid()
    );

-- Admins and Approvers can view all org submissions
CREATE POLICY "Admins and Approvers can view all submissions" ON expense_submissions
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id FROM organization_members
            WHERE user_id = auth.uid()
            AND status = 'active'
            AND role IN ('owner', 'admin', 'approver')
        )
    );

-- Users can create their own submissions
CREATE POLICY "Users can create own submissions" ON expense_submissions
    FOR INSERT WITH CHECK (
        submitted_by = auth.uid()
    );

-- Admins and Approvers can update (approve/reject) submissions
CREATE POLICY "Admins and Approvers can update submissions" ON expense_submissions
    FOR UPDATE USING (
        -- User's own submission (can edit if draft)
        (submitted_by = auth.uid() AND status = 'draft')
        OR
        -- Admin or Approver in the organization
        (organization_id IN (
            SELECT organization_id FROM organization_members
            WHERE user_id = auth.uid()
            AND status = 'active'
            AND role IN ('owner', 'admin', 'approver')
        ))
    );

-- ============================================================================
-- STEP 5: UPDATE TRIP RLS POLICIES FOR PRIVACY
-- ============================================================================

-- Drop existing trip policies
DROP POLICY IF EXISTS "Users can view their trips or org trips" ON trips;
DROP POLICY IF EXISTS "Users can insert trips" ON trips;
DROP POLICY IF EXISTS "Users can update their trips or org trips" ON trips;
DROP POLICY IF EXISTS "Users can delete their trips or org trips as admin" ON trips;

-- Members can only view their own trips (privacy)
-- Admins and Approvers can view all org trips
CREATE POLICY "Users can view trips based on role" ON trips
    FOR SELECT USING (
        user_id = auth.uid()
        OR
        organization_id IN (
            SELECT organization_id FROM organization_members
            WHERE user_id = auth.uid()
            AND status = 'active'
            AND role IN ('owner', 'admin', 'approver')
        )
    );

-- Everyone can create trips for themselves
-- Admins can create trips for others (via user_id parameter)
CREATE POLICY "Users can create trips" ON trips
    FOR INSERT WITH CHECK (
        user_id = auth.uid()
        OR
        EXISTS (
            SELECT 1 FROM organization_members
            WHERE user_id = auth.uid()
            AND organization_id = trips.organization_id
            AND status = 'active'
            AND role IN ('owner', 'admin')
        )
    );

-- Users can update their own trips
-- Admins can update any org trip
CREATE POLICY "Users can update trips based on role" ON trips
    FOR UPDATE USING (
        user_id = auth.uid()
        OR
        organization_id IN (
            SELECT organization_id FROM organization_members
            WHERE user_id = auth.uid()
            AND status = 'active'
            AND role IN ('owner', 'admin')
        )
    );

-- Users can delete their own trips
-- Admins can delete any org trip
CREATE POLICY "Users can delete trips based on role" ON trips
    FOR DELETE USING (
        user_id = auth.uid()
        OR
        organization_id IN (
            SELECT organization_id FROM organization_members
            WHERE user_id = auth.uid()
            AND status = 'active'
            AND role IN ('owner', 'admin')
        )
    );

-- ============================================================================
-- STEP 6: UPDATE EXPENSE RLS POLICIES FOR PRIVACY
-- ============================================================================

-- Note: expenses table RLS needs updating too
-- Drop existing expense policies if they exist
DROP POLICY IF EXISTS "Users can view all org expenses" ON expenses;
DROP POLICY IF EXISTS "Users can view own expenses" ON expenses;
DROP POLICY IF EXISTS "Users can insert expenses" ON expenses;
DROP POLICY IF EXISTS "Users can update expenses" ON expenses;
DROP POLICY IF EXISTS "Users can delete expenses" ON expenses;

-- Members can only view their own expenses
-- Admins and Approvers can view all org expenses
CREATE POLICY "Users can view expenses based on role" ON expenses
    FOR SELECT USING (
        user_id = auth.uid()
        OR
        trip_id IN (
            SELECT id FROM trips
            WHERE organization_id IN (
                SELECT organization_id FROM organization_members
                WHERE user_id = auth.uid()
                AND status = 'active'
                AND role IN ('owner', 'admin', 'approver')
            )
        )
    );

-- Everyone can add expenses to their own trips
-- Admins can add expenses to any org trip
CREATE POLICY "Users can create expenses" ON expenses
    FOR INSERT WITH CHECK (
        user_id = auth.uid()
        OR
        trip_id IN (
            SELECT id FROM trips
            WHERE organization_id IN (
                SELECT organization_id FROM organization_members
                WHERE user_id = auth.uid()
                AND status = 'active'
                AND role IN ('owner', 'admin')
            )
        )
    );

-- Users can update their own expenses
-- Admins can update any org expense
CREATE POLICY "Users can update expenses" ON expenses
    FOR UPDATE USING (
        user_id = auth.uid()
        OR
        trip_id IN (
            SELECT id FROM trips
            WHERE organization_id IN (
                SELECT organization_id FROM organization_members
                WHERE user_id = auth.uid()
                AND status = 'active'
                AND role IN ('owner', 'admin')
            )
        )
    );

-- Users can delete their own expenses
-- Admins can delete any org expense
CREATE POLICY "Users can delete expenses" ON expenses
    FOR DELETE USING (
        user_id = auth.uid()
        OR
        trip_id IN (
            SELECT id FROM trips
            WHERE organization_id IN (
                SELECT organization_id FROM organization_members
                WHERE user_id = auth.uid()
                AND status = 'active'
                AND role IN ('owner', 'admin')
            )
        )
    );

-- ============================================================================
-- STEP 7: UPDATE ORGANIZATION POLICIES
-- ============================================================================

-- Drop and recreate organization update policy
DROP POLICY IF EXISTS "Owners and admins can update organization" ON organizations;

CREATE POLICY "Admins can update organization" ON organizations
    FOR UPDATE USING (
        id IN (
            SELECT organization_id FROM organization_members
            WHERE user_id = auth.uid()
            AND status = 'active'
            AND role IN ('owner', 'admin')
        )
    );

-- ============================================================================
-- STEP 8: UPDATE MEMBER MANAGEMENT POLICIES
-- ============================================================================

-- Drop and recreate member management policy
DROP POLICY IF EXISTS "Admins can manage members" ON organization_members;

CREATE POLICY "Admins can manage members" ON organization_members
    FOR ALL USING (
        organization_id IN (
            SELECT organization_id FROM organization_members
            WHERE user_id = auth.uid()
            AND status = 'active'
            AND role IN ('owner', 'admin')
        )
    );

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================
-- Summary:
--   ✅ Roles simplified: admin, approver, member (viewer removed)
--   ✅ Manager hierarchy removed (manager_id, department)
--   ✅ Helper functions removed
--   ✅ RLS policies updated for 3-role model
--   ✅ Privacy enforced: members can't see others' data
--   ✅ Admins can create/edit trips and expenses for others
-- ============================================================================
