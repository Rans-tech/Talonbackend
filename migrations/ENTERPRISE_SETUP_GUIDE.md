# Travel Raven Enterprise Multi-Tenant Architecture Setup Guide

## 🎯 Overview

This guide will help you set up the enterprise multi-tenant architecture for Travel Raven. This system allows organizations to:
- Create and manage team workspaces
- Invite and manage team members with role-based access
- Share trips across the organization
- Track activity with audit logs
- Manage subscriptions at the organization level

## 📊 What's Been Built

### 1. Database Schema
- **organizations** - Company workspaces
- **organization_members** - Team membership and roles
- **organization_settings** - Workspace configuration
- **audit_logs** - Activity tracking for compliance

### 2. Frontend Components
- **OrganizationSwitcher** - Header dropdown to switch between orgs
- **OrganizationsList** - View all organizations
- **CreateOrganization** - Form to create new org
- **OrganizationDashboard** - Admin panel for managing team

### 3. TypeScript Types & Hooks
- Complete type definitions for organizations
- React Query hooks for data fetching
- Permission system with role-based access control

### 4. Routes
- `/organizations` - List all organizations
- `/organizations/new` - Create organization
- `/organizations/:id` - Organization dashboard

## 🚀 Setup Steps

### Step 1: Run Database Migration

1. **Open your Supabase Dashboard**
   - Go to https://supabase.com/dashboard
   - Select your Travel Raven project

2. **Navigate to SQL Editor**
   - Click "SQL Editor" in the left sidebar
   - Click "New Query"

3. **Run the Migration Script**
   - Open `C:\Users\mrcoo\Talonbackend\migrations\001_create_organizations.sql`
   - Copy the entire contents
   - Paste into the Supabase SQL Editor
   - Click "Run" or press Ctrl+Enter

4. **Verify Tables Were Created**
   - Click "Table Editor" in the left sidebar
   - You should see these new tables:
     - `organizations`
     - `organization_members`
     - `organization_settings`
     - `audit_logs`
   - The `trips` table should now have an `organization_id` column
   - The `profiles` table should now have a `primary_organization_id` column

### Step 2: Test the Frontend

1. **Ensure Dev Server is Running**
   ```bash
   cd C:\Users\mrcoo\frontend
   npm run dev
   ```

2. **Test the Flow**
   - Navigate to http://localhost:5174
   - Log in to your account
   - Look for the **Organization Switcher** in the header (Building icon)
   - Click it → "Create Organization"
   - Fill out the form:
     - Name: "Test Company"
     - Slug: "test-company"
     - Industry: "Technology"
   - Click "Create Organization"

3. **Test Member Invitations**
   - Go to Organizations Dashboard
   - Click "Invite Member"
   - Enter an email of an existing Travel Raven user
   - Select role (Member, Admin, etc.)
   - The user will see the invitation in their Organizations page

### Step 3: Update Your 5 Beta Companies

For each of your 5 waiting enterprise companies:

1. **Create Organization**
   - Create an organization with their company name
   - Set the correct billing email
   - Choose "enterprise" tier

2. **Invite Team Members**
   - Invite the company admin as "owner"
   - Invite other team members as needed
   - They'll need to accept invitations

3. **Configure Settings** (Optional)
   - Go to Organization Settings
   - Set workspace preferences
   - Configure security settings

## 🔐 Permission System

### Role Hierarchy

1. **Owner** (Full Control)
   - All permissions
   - Can transfer ownership
   - Can delete organization
   - Manage billing

2. **Admin** (Management)
   - Invite/remove members
   - Manage roles
   - Edit organization details
   - View audit logs
   - Cannot manage billing

3. **Member** (Standard Access)
   - Create and manage trips
   - View all organization trips
   - Cannot invite users
   - Cannot change settings

4. **Viewer** (Read-Only)
   - View organization trips
   - Cannot create or edit

### Permission Checks

The system automatically enforces permissions:
```typescript
// Example: Check if user can invite members
if (hasPermission(currentMembership, 'invite_members')) {
  // Show invite button
}
```

## 📋 Features Included

### ✅ Implemented
- [x] Organization creation and management
- [x] Member invitations and role management
- [x] Organization switcher in header
- [x] Role-based access control
- [x] Audit logging
- [x] Organization settings
- [x] Multi-organization support per user
- [x] Pending invitation system
- [x] Member dashboard with stats

### 🚧 Recommended Next Steps

1. **Billing Integration**
   - Connect organization subscriptions to Stripe
   - Per-seat billing for Enterprise
   - Usage tracking and invoicing

2. **Admin Features**
   - Bulk user import (CSV)
   - SSO/SAML integration
   - Custom branding per organization
   - API keys for integrations

3. **Trip Organization**
   - Assign trips to organizations
   - Organization-wide trip templates
   - Corporate travel policies

4. **Advanced Permissions**
   - Custom role creation
   - Granular permission editing
   - Department-level access control

## 🐛 Troubleshooting

### Issue: "Organization not found" error
**Solution**: User may not be a member. Check `organization_members` table.

### Issue: Can't see organization switcher
**Solution**:
- Ensure you're logged in
- Try creating your first organization at `/organizations/new`
- Check browser console for errors

### Issue: RLS policies blocking access
**Solution**:
- Verify user is in `organization_members` with `status = 'active'`
- Check Supabase logs for policy violations

### Issue: Migrations fail
**Solution**:
- Ensure you have `service_role` permissions
- Check if tables already exist (drop them first if needed)
- Run each section of the migration separately

## 📊 Database Schema Diagram

```
┌─────────────────┐
│  organizations  │
├─────────────────┤
│ id (PK)         │
│ name            │
│ slug (UNIQUE)   │
│ max_seats       │
│ created_by      │◄──────┐
└─────────────────┘        │
         ▲                 │
         │                 │
         │                 │
┌─────────────────────┐   │
│ organization_members│    │
├─────────────────────┤    │
│ id (PK)             │    │
│ organization_id (FK)│────┘
│ user_id (FK)        │────────┐
│ role                │        │
│ status              │        │
└─────────────────────┘        │
                               │
                        ┌──────────┐
                        │ profiles │
                        ├──────────┤
                        │ id (PK)  │
                        └──────────┘
```

## 🎓 Usage Examples

### Creating an Organization (User Flow)
1. User clicks Organization Switcher → "Create Organization"
2. Fills out form with company details
3. System automatically:
   - Creates organization
   - Makes user the "owner"
   - Creates default settings
   - Redirects to dashboard

### Inviting Team Members (Admin Flow)
1. Admin goes to organization dashboard
2. Clicks "Invite Member"
3. Enters email and selects role
4. System checks if user exists
5. Creates pending invitation
6. Invitee sees invitation in their organizations page
7. Accepts → status changes to "active"

### Switching Organizations (User Flow)
1. User clicks Organization Switcher
2. Sees list of all organizations they're a member of
3. Clicks desired organization
4. Sets it as primary organization
5. UI updates to show org context

## 🔗 Related Files

### Frontend
- `src/types/organization.ts` - TypeScript types
- `src/hooks/useOrganization.ts` - React Query hooks
- `src/components/OrganizationSwitcher.tsx` - Header switcher
- `src/pages/OrganizationsList.tsx` - Organizations list
- `src/pages/CreateOrganization.tsx` - Create form
- `src/pages/OrganizationDashboard.tsx` - Admin dashboard

### Backend
- `migrations/001_create_organizations.sql` - Database schema

### Routes
- `src/main.tsx` - Route definitions

## 📞 Support

If you encounter issues:
1. Check the browser console for errors
2. Check Supabase logs in the dashboard
3. Verify RLS policies are active
4. Ensure all migrations ran successfully

## 🎉 Next Phase: Global Assistance

Once enterprise architecture is tested and deployed, we'll move to:
- **Phase 7**: Global Assistance with $85 confirmation modal
- Button to contact 24/7 ops center
- Case initiation charge workflow
- Case credit tracking for Enterprise users

---

**Status**: ✅ Enterprise Architecture Complete - Ready for Testing
**Next**: Run database migration and test with your 5 beta companies!
