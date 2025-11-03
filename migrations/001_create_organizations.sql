-- Organizations table for enterprise multi-tenancy
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    description TEXT,
    logo_url TEXT,
    website TEXT,
    industry TEXT,
    max_seats INTEGER NOT NULL DEFAULT 10,
    current_seats_used INTEGER NOT NULL DEFAULT 0,
    subscription_tier TEXT NOT NULL DEFAULT 'free' CHECK (subscription_tier IN ('free', 'team', 'enterprise')),
    subscription_status TEXT NOT NULL DEFAULT 'active' CHECK (subscription_status IN ('active', 'canceled', 'expired', 'trialing')),
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    billing_email TEXT,
    created_by UUID REFERENCES profiles(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

-- Organization members table
CREATE TABLE IF NOT EXISTS organization_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member', 'viewer')),
    permissions JSONB DEFAULT '{}',
    invited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    accepted_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'removed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(organization_id, user_id)
);

-- Organization settings table
CREATE TABLE IF NOT EXISTS organization_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE CASCADE,
    require_two_factor BOOLEAN DEFAULT false,
    allow_public_trips BOOLEAN DEFAULT false,
    default_trip_visibility TEXT DEFAULT 'org' CHECK (default_trip_visibility IN ('private', 'org', 'public')),
    data_retention_days INTEGER DEFAULT 365,
    max_file_size_mb INTEGER DEFAULT 10,
    ip_whitelist JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Audit logs for enterprise compliance
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID REFERENCES profiles(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id UUID,
    changes JSONB DEFAULT '{}',
    ip_address TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug);
CREATE INDEX IF NOT EXISTS idx_organizations_created_by ON organizations(created_by);
CREATE INDEX IF NOT EXISTS idx_organization_members_org_id ON organization_members(organization_id);
CREATE INDEX IF NOT EXISTS idx_organization_members_user_id ON organization_members(user_id);
CREATE INDEX IF NOT EXISTS idx_organization_members_status ON organization_members(status);
CREATE INDEX IF NOT EXISTS idx_audit_logs_org_id ON audit_logs(organization_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);

-- Add organization_id to trips table
ALTER TABLE trips
ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_trips_organization_id ON trips(organization_id);

-- Add primary_organization_id to profiles
ALTER TABLE profiles
ADD COLUMN IF NOT EXISTS primary_organization_id UUID REFERENCES organizations(id) ON DELETE SET NULL;

-- Updated_at triggers
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_organizations_updated_at BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_organization_members_updated_at BEFORE UPDATE ON organization_members
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_organization_settings_updated_at BEFORE UPDATE ON organization_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Row Level Security (RLS) Policies
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE organization_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;

-- Organizations: Users can see orgs they're members of
CREATE POLICY "Users can view their organizations" ON organizations
    FOR SELECT USING (
        id IN (
            SELECT organization_id FROM organization_members
            WHERE user_id = auth.uid() AND status = 'active'
        )
    );

-- Organizations: Owners and admins can update
CREATE POLICY "Owners and admins can update organization" ON organizations
    FOR UPDATE USING (
        id IN (
            SELECT organization_id FROM organization_members
            WHERE user_id = auth.uid()
            AND status = 'active'
            AND role IN ('owner', 'admin')
        )
    );

-- Organization members: Can view members in their org
CREATE POLICY "Members can view org members" ON organization_members
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id FROM organization_members
            WHERE user_id = auth.uid() AND status = 'active'
        )
    );

-- Organization members: Admins/owners can manage members
CREATE POLICY "Admins can manage members" ON organization_members
    FOR ALL USING (
        organization_id IN (
            SELECT organization_id FROM organization_members
            WHERE user_id = auth.uid()
            AND status = 'active'
            AND role IN ('owner', 'admin')
        )
    );

-- Organization settings: Members can view, admins can update
CREATE POLICY "Members can view settings" ON organization_settings
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id FROM organization_members
            WHERE user_id = auth.uid() AND status = 'active'
        )
    );

CREATE POLICY "Admins can update settings" ON organization_settings
    FOR UPDATE USING (
        organization_id IN (
            SELECT organization_id FROM organization_members
            WHERE user_id = auth.uid()
            AND status = 'active'
            AND role IN ('owner', 'admin')
        )
    );

-- Audit logs: Members can view their org's logs
CREATE POLICY "Members can view audit logs" ON audit_logs
    FOR SELECT USING (
        organization_id IN (
            SELECT organization_id FROM organization_members
            WHERE user_id = auth.uid() AND status = 'active'
        )
    );

-- Update trips RLS to include organization access
DROP POLICY IF EXISTS "Users can view their own trips" ON trips;
CREATE POLICY "Users can view their trips or org trips" ON trips
    FOR SELECT USING (
        user_id = auth.uid()
        OR organization_id IN (
            SELECT organization_id FROM organization_members
            WHERE user_id = auth.uid() AND status = 'active'
        )
    );

DROP POLICY IF EXISTS "Users can insert their own trips" ON trips;
CREATE POLICY "Users can insert trips" ON trips
    FOR INSERT WITH CHECK (
        user_id = auth.uid()
    );

DROP POLICY IF EXISTS "Users can update their own trips" ON trips;
CREATE POLICY "Users can update their trips or org trips" ON trips
    FOR UPDATE USING (
        user_id = auth.uid()
        OR (
            organization_id IN (
                SELECT organization_id FROM organization_members
                WHERE user_id = auth.uid()
                AND status = 'active'
                AND role IN ('owner', 'admin', 'member')
            )
        )
    );

DROP POLICY IF EXISTS "Users can delete their own trips" ON trips;
CREATE POLICY "Users can delete their trips or org trips as admin" ON trips
    FOR DELETE USING (
        user_id = auth.uid()
        OR (
            organization_id IN (
                SELECT organization_id FROM organization_members
                WHERE user_id = auth.uid()
                AND status = 'active'
                AND role IN ('owner', 'admin')
            )
        )
    );
