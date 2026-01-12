-- =============================================================================
-- TGF PLATFORM - COMPREHENSIVE DATABASE SCHEMA v2.0
-- =============================================================================
-- This migration builds on the initial schema with all discussed enhancements:
-- - Flexible organization hierarchy
-- - Users with roles & permissions (renamed from members)
-- - Smart partner preferences
-- - Course database with contacts & policies
-- - Games, bundles, and event templates
-- - Multi-day events and team events
-- - Custom handicap tracking with GHIN sync
-- - Financial tracking with TGF markup
-- - Promo codes and gift cards
-- - Action items and batch operations
-- - Soft deletes and audit logging
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For fuzzy text search

-- =============================================================================
-- SECTION 1: CUSTOM TYPES (Enums)
-- =============================================================================

-- Drop existing types if they exist (for clean migration)
DROP TYPE IF EXISTS user_status CASCADE;
DROP TYPE IF EXISTS payment_status CASCADE;
DROP TYPE IF EXISTS event_status CASCADE;
DROP TYPE IF EXISTS transaction_type CASCADE;

-- User status - tracks relationship with TGF
CREATE TYPE user_status AS ENUM (
  'prospect',           -- Signed up but never played or joined
  'guest',              -- Has played but never been a member
  'active_member',      -- Currently has paid membership
  'expired_member',     -- Was a member, membership lapsed
  'former_member',      -- Explicitly cancelled/left
  'inactive'            -- Dormant account
);

-- Payment status for registrations
CREATE TYPE payment_status AS ENUM (
  'pending',            -- Registered but not paid
  'processing',         -- Payment in progress
  'paid',               -- Payment complete
  'partially_paid',     -- Partial payment (credits + card)
  'refunded',           -- Full refund issued
  'partially_refunded', -- Partial refund
  'failed',             -- Payment failed
  'comped'              -- Free registration
);

-- Event status
CREATE TYPE event_status AS ENUM (
  'draft',              -- Being set up, not visible
  'published',          -- Open for registration
  'registration_closed',-- Past deadline, event upcoming
  'in_progress',        -- Event happening now
  'completed',          -- Event finished
  'cancelled',          -- Event cancelled
  'postponed'           -- Event postponed
);

-- Transaction types
CREATE TYPE transaction_type AS ENUM (
  'membership_purchase',
  'membership_renewal',
  'event_registration',
  'game_addon',
  'wallet_deposit',
  'wallet_payment',
  'wallet_credit',      -- Winnings, adjustments
  'refund',
  'promo_discount',
  'gift_card_purchase',
  'gift_card_redemption',
  'late_fee',
  'adjustment'
);

-- Registration question types
CREATE TYPE question_type AS ENUM (
  'text',
  'select',
  'multi_select',
  'yes_no',
  'number',
  'date',
  'time'
);

-- Action item status
CREATE TYPE action_status AS ENUM (
  'pending',
  'in_progress',
  'waiting_response',
  'resolved',
  'escalated',
  'expired',
  'cancelled'
);

-- Approval status
CREATE TYPE approval_status AS ENUM (
  'pending',
  'approved',
  'denied',
  'expired',
  'cancelled'
);

-- =============================================================================
-- SECTION 2: ORGANIZATION HIERARCHY
-- =============================================================================

-- Organization level definitions (customizable hierarchy)
CREATE TABLE organization_levels (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  name VARCHAR(50) NOT NULL,              -- "Chapter", "Region", etc.
  name_singular VARCHAR(50) NOT NULL,     -- "Chapter"
  name_plural VARCHAR(50) NOT NULL,       -- "Chapters"

  level_order INTEGER NOT NULL,           -- 1=highest (Country), 5=lowest (Sub-chapter)

  description TEXT,
  is_active BOOLEAN NOT NULL DEFAULT true,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(level_order)
);

-- Insert default hierarchy levels
INSERT INTO organization_levels (name, name_singular, name_plural, level_order) VALUES
  ('Country', 'Country', 'Countries', 1),
  ('Super-Region', 'Super-Region', 'Super-Regions', 2),
  ('State', 'State', 'States', 3),
  ('Chapter', 'Chapter', 'Chapters', 4),
  ('Sub-Chapter', 'Sub-Chapter', 'Sub-Chapters', 5);

-- Organizations (chapters, regions, etc.)
CREATE TABLE organizations (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  -- Hierarchy
  level_id UUID NOT NULL REFERENCES organization_levels(id),
  parent_id UUID REFERENCES organizations(id),
  path TEXT,                              -- Materialized path for fast queries: "tgf/usa/texas/san_antonio"

  -- Basic info
  name VARCHAR(100) NOT NULL,
  code VARCHAR(20) NOT NULL,              -- Short code: "SA", "AUS", "TX"
  description TEXT,

  -- Location (optional, mainly for chapters)
  city VARCHAR(100),
  state_province VARCHAR(100),
  country VARCHAR(100),
  timezone VARCHAR(50) DEFAULT 'America/Chicago',

  -- Settings (flexible JSON)
  settings JSONB DEFAULT '{}',
  /*
    Example settings:
    {
      "default_late_fee": 10.00,
      "late_fee_cutoff_hours": 48,
      "registration_lock_hours": 24,
      "default_tax_rate": 0.0825,
      "allow_guest_registration": true,
      "require_ghin": false
    }
  */

  -- Display
  logo_url TEXT,
  is_active BOOLEAN NOT NULL DEFAULT true,
  display_order INTEGER NOT NULL DEFAULT 0,

  -- Soft delete
  deleted_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(code)
);

-- Create indexes
CREATE INDEX idx_organizations_parent ON organizations(parent_id);
CREATE INDEX idx_organizations_path ON organizations(path);
CREATE INDEX idx_organizations_level ON organizations(level_id);
CREATE INDEX idx_organizations_active ON organizations(is_active) WHERE deleted_at IS NULL;

-- Insert initial organizations
INSERT INTO organizations (level_id, parent_id, name, code, city, state_province, country, path) VALUES
  -- Country
  ((SELECT id FROM organization_levels WHERE level_order = 1), NULL, 'United States', 'USA', NULL, NULL, 'United States', 'usa'),
  -- State (Texas)
  ((SELECT id FROM organization_levels WHERE level_order = 3),
   (SELECT id FROM organizations WHERE code = 'USA'),
   'Texas', 'TX', NULL, 'Texas', 'United States', 'usa/tx'),
  -- Chapters
  ((SELECT id FROM organization_levels WHERE level_order = 4),
   (SELECT id FROM organizations WHERE code = 'TX'),
   'San Antonio', 'SA', 'San Antonio', 'Texas', 'United States', 'usa/tx/sa'),
  ((SELECT id FROM organization_levels WHERE level_order = 4),
   (SELECT id FROM organizations WHERE code = 'TX'),
   'Austin', 'AUS', 'Austin', 'Texas', 'United States', 'usa/tx/aus');

-- =============================================================================
-- SECTION 3: ROLES & PERMISSIONS
-- =============================================================================

-- Permission definitions
CREATE TABLE permissions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  key VARCHAR(100) NOT NULL UNIQUE,       -- "events.create", "refunds.override"
  name VARCHAR(200) NOT NULL,             -- Human readable
  description TEXT,
  category VARCHAR(50) NOT NULL,          -- "Events", "Members", "Financial"

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert core permissions
INSERT INTO permissions (key, name, category, description) VALUES
  -- Events
  ('events.view', 'View Events', 'Events', 'View event details'),
  ('events.create', 'Create Events', 'Events', 'Create new events'),
  ('events.edit', 'Edit Events', 'Events', 'Modify existing events'),
  ('events.delete', 'Delete Events', 'Events', 'Delete events'),
  ('events.publish', 'Publish Events', 'Events', 'Make events visible to public'),
  ('events.cancel', 'Cancel Events', 'Events', 'Cancel scheduled events'),

  -- Registrations
  ('registrations.view', 'View Registrations', 'Registrations', 'View registration details'),
  ('registrations.create_manual', 'Manual Registration', 'Registrations', 'Register players manually'),
  ('registrations.cancel', 'Cancel Registrations', 'Registrations', 'Cancel player registrations'),
  ('registrations.checkin', 'Check-in Players', 'Registrations', 'Check in players at events'),

  -- Financial
  ('financial.view_reports', 'View Financial Reports', 'Financial', 'Access financial reports'),
  ('financial.process_refunds', 'Process Refunds', 'Financial', 'Process standard refunds'),
  ('financial.override_refund_policy', 'Override Refund Policy', 'Financial', 'Process refunds outside policy'),
  ('financial.credit_wallets', 'Credit Wallets', 'Financial', 'Add credits to member wallets'),
  ('financial.comp_registrations', 'Comp Registrations', 'Financial', 'Register players for free'),
  ('financial.view_all', 'View All Financials', 'Financial', 'View all financial data across orgs'),

  -- Members
  ('members.view', 'View Members', 'Members', 'View member profiles'),
  ('members.edit', 'Edit Members', 'Members', 'Modify member profiles'),
  ('members.manage_memberships', 'Manage Memberships', 'Members', 'Grant/revoke memberships'),

  -- System
  ('system.manage_roles', 'Manage Roles', 'System', 'Create and modify roles'),
  ('system.manage_permissions', 'Manage Permissions', 'System', 'Assign permissions to roles'),
  ('system.manage_organizations', 'Manage Organizations', 'System', 'Create/modify chapters and regions'),
  ('system.view_audit_logs', 'View Audit Logs', 'System', 'Access audit trail'),
  ('system.batch_operations', 'Batch Operations', 'System', 'Perform bulk changes'),
  ('system.feature_flags', 'Manage Feature Flags', 'System', 'Toggle features on/off');

-- Role definitions
CREATE TABLE roles (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  name VARCHAR(100) NOT NULL,             -- "Admin", "Chapter Manager"
  description TEXT,

  level INTEGER NOT NULL,                 -- Hierarchy: 100=admin, 80=director, 60=manager, etc.

  is_system_role BOOLEAN NOT NULL DEFAULT false,  -- Can't be deleted
  is_active BOOLEAN NOT NULL DEFAULT true,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(name)
);

-- Insert default roles
INSERT INTO roles (name, description, level, is_system_role) VALUES
  ('Admin', 'Full system access', 100, true),
  ('Regional Director', 'Manages multiple chapters in a region', 80, true),
  ('Chapter Manager', 'Manages a single chapter', 60, true),
  ('Sub-Chapter Manager', 'Manages a league or sub-chapter', 40, true),
  ('Event Coordinator', 'Can create and manage events', 30, false),
  ('Player Ambassador', 'Community leader with limited access', 20, false);

-- Role-Permission mapping
CREATE TABLE role_permissions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
  permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,

  -- Scope of permission
  scope VARCHAR(20) NOT NULL DEFAULT 'own_org',  -- 'own_org', 'child_orgs', 'all'

  -- Some actions may require approval from higher role
  requires_approval BOOLEAN NOT NULL DEFAULT false,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(role_id, permission_id)
);

-- Grant all permissions to Admin
INSERT INTO role_permissions (role_id, permission_id, scope)
SELECT
  (SELECT id FROM roles WHERE name = 'Admin'),
  id,
  'all'
FROM permissions;

-- Grant relevant permissions to Chapter Manager
INSERT INTO role_permissions (role_id, permission_id, scope, requires_approval)
SELECT
  (SELECT id FROM roles WHERE name = 'Chapter Manager'),
  id,
  'own_org',
  CASE
    WHEN key IN ('financial.override_refund_policy', 'financial.comp_registrations') THEN true
    ELSE false
  END
FROM permissions
WHERE key IN (
  'events.view', 'events.create', 'events.edit', 'events.publish', 'events.cancel',
  'registrations.view', 'registrations.create_manual', 'registrations.cancel', 'registrations.checkin',
  'financial.view_reports', 'financial.process_refunds', 'financial.override_refund_policy',
  'financial.credit_wallets', 'financial.comp_registrations',
  'members.view', 'members.edit'
);

-- =============================================================================
-- SECTION 4: USERS (renamed from members)
-- =============================================================================

-- Main users table
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  -- Link to Supabase Auth
  auth_user_id UUID UNIQUE,

  -- Personal info
  email VARCHAR(255) NOT NULL,
  first_name VARCHAR(100) NOT NULL,
  last_name VARCHAR(100) NOT NULL,
  phone VARCHAR(20),
  date_of_birth DATE,

  -- Profile
  profile_photo_url TEXT,
  bio TEXT,
  profession VARCHAR(200),               -- For networking features
  company VARCHAR(200),
  linkedin_url TEXT,

  -- Golf info
  ghin_number VARCHAR(20),
  ghin_sync_enabled BOOLEAN DEFAULT false,  -- Auto-sync with GHIN
  home_organization_id UUID REFERENCES organizations(id),

  -- Status
  status user_status NOT NULL DEFAULT 'prospect',

  -- Current membership (denormalized for speed)
  current_membership_id UUID,            -- FK added after user_memberships created
  membership_expires_at TIMESTAMPTZ,

  -- Wallet
  wallet_balance DECIMAL(10,2) NOT NULL DEFAULT 0.00,

  -- Stripe
  stripe_customer_id VARCHAR(255),
  default_payment_method_id VARCHAR(255),

  -- Activity tracking
  first_event_date DATE,
  last_event_date DATE,
  events_played_count INTEGER NOT NULL DEFAULT 0,

  -- Notification preferences
  email_notifications BOOLEAN NOT NULL DEFAULT true,
  sms_notifications BOOLEAN NOT NULL DEFAULT false,
  push_notifications BOOLEAN NOT NULL DEFAULT true,

  -- Internal
  notes TEXT,                            -- Manager notes
  tags TEXT[],                           -- For filtering/segmentation

  -- Soft delete
  deleted_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_login_at TIMESTAMPTZ,

  UNIQUE(email)
);

-- Indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_stripe ON users(stripe_customer_id);
CREATE INDEX idx_users_home_org ON users(home_organization_id);
CREATE INDEX idx_users_search ON users USING gin(
  (first_name || ' ' || last_name) gin_trgm_ops
);
CREATE INDEX idx_users_active ON users(id) WHERE deleted_at IS NULL;

-- User role assignments
CREATE TABLE user_roles (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role_id UUID NOT NULL REFERENCES roles(id),
  organization_id UUID NOT NULL REFERENCES organizations(id),  -- Which org they have this role for

  granted_by_id UUID REFERENCES users(id),
  granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ,                -- Optional expiration

  is_active BOOLEAN NOT NULL DEFAULT true,

  notes TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(user_id, role_id, organization_id)
);

CREATE INDEX idx_user_roles_user ON user_roles(user_id);
CREATE INDEX idx_user_roles_org ON user_roles(organization_id);

-- =============================================================================
-- SECTION 5: USER PREFERENCES & PARTNER SYSTEM
-- =============================================================================

-- User preferences for smart autofill
CREATE TABLE user_preferences (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

  preference_key VARCHAR(100) NOT NULL,   -- "tee_preference", "fellowship_after", etc.
  preference_value TEXT NOT NULL,

  -- Tracking
  times_used INTEGER NOT NULL DEFAULT 1,
  last_used_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(user_id, preference_key)
);

-- Preferred playing partners (ordered list)
CREATE TABLE user_preferred_partners (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  partner_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

  preference_order INTEGER NOT NULL,      -- 1 = first choice, 2 = second, etc.

  -- If both users have each other, auto-accept pairing requests
  -- This is computed, not stored

  notes TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(user_id, partner_user_id),
  CHECK(user_id != partner_user_id)
);

CREATE INDEX idx_preferred_partners_user ON user_preferred_partners(user_id);

-- Pairing preferences (more general preferences)
CREATE TABLE user_pairing_preferences (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

  -- Handicap preferences
  preferred_handicap_min INTEGER,         -- Min handicap of playing partners
  preferred_handicap_max INTEGER,         -- Max handicap

  -- Networking preferences
  preferred_professions TEXT[],           -- Industries/professions for networking

  -- Pace preferences
  preferred_pace VARCHAR(20),             -- 'fast', 'moderate', 'relaxed'

  -- Other
  preferences_json JSONB DEFAULT '{}',    -- Flexible additional preferences

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(user_id)
);

-- =============================================================================
-- SECTION 6: MEMBERSHIPS
-- =============================================================================

-- Membership type definitions
CREATE TABLE membership_types (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  name VARCHAR(100) NOT NULL,
  description TEXT,

  -- Pricing
  price DECIMAL(10,2) NOT NULL,
  duration_months INTEGER NOT NULL,

  -- Rules
  is_active BOOLEAN NOT NULL DEFAULT true,
  is_publicly_available BOOLEAN NOT NULL DEFAULT true,

  -- Organization restrictions (NULL = all)
  allowed_organization_ids UUID[],

  -- Benefits
  benefits JSONB DEFAULT '{}',
  /*
    {
      "all_chapters": true,
      "net_games": true,
      "season_contests": true,
      "guest_events_per_year": 2,
      "merchandise_discount_percent": 10
    }
  */

  display_order INTEGER NOT NULL DEFAULT 0,

  -- Soft delete
  deleted_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert default membership
INSERT INTO membership_types (name, description, price, duration_months, benefits) VALUES
  ('Annual Membership', 'Full TGF membership with access to all chapters', 300.00, 12,
   '{"all_chapters": true, "net_games": true, "season_contests": true}');

-- User membership history
CREATE TABLE user_memberships (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  membership_type_id UUID NOT NULL REFERENCES membership_types(id),

  starts_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,

  -- Payment
  amount_paid DECIMAL(10,2) NOT NULL,
  transaction_id UUID,                    -- Link to transactions
  promo_code_id UUID,                     -- If discount applied

  -- Status
  is_active BOOLEAN NOT NULL DEFAULT true,
  cancelled_at TIMESTAMPTZ,
  cancellation_reason TEXT,

  -- Auto-renewal
  auto_renew BOOLEAN NOT NULL DEFAULT false,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_user_memberships_user ON user_memberships(user_id);
CREATE INDEX idx_user_memberships_active ON user_memberships(is_active, expires_at);

-- Add FK from users to user_memberships
ALTER TABLE users
  ADD CONSTRAINT fk_current_membership
  FOREIGN KEY (current_membership_id) REFERENCES user_memberships(id);

-- =============================================================================
-- SECTION 7: HANDICAP TRACKING
-- =============================================================================

-- Handicap records (TGF's own tracking)
CREATE TABLE handicap_records (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

  -- Current handicap
  handicap_index DECIMAL(4,1) NOT NULL,

  -- Source
  source VARCHAR(20) NOT NULL,            -- 'tgf_calculated', 'ghin_sync', 'manual'
  ghin_handicap DECIMAL(4,1),             -- If synced from GHIN

  -- Calculation details
  rounds_used INTEGER,
  scoring_average DECIMAL(5,2),

  effective_date DATE NOT NULL,

  -- Metadata
  calculation_details JSONB,              -- Detailed breakdown

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_handicap_records_user ON handicap_records(user_id);
CREATE INDEX idx_handicap_records_date ON handicap_records(user_id, effective_date DESC);

-- Score history for handicap calculation
CREATE TABLE score_history (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

  -- Round info
  played_date DATE NOT NULL,
  course_id UUID,                         -- FK to courses (added later)
  tee_played VARCHAR(50),

  -- Course data at time of play
  course_rating DECIMAL(4,1) NOT NULL,
  slope_rating INTEGER NOT NULL,
  par INTEGER NOT NULL,

  -- Scores
  gross_score INTEGER NOT NULL,
  adjusted_gross_score INTEGER NOT NULL,  -- For handicap purposes
  score_differential DECIMAL(4,1) NOT NULL,

  -- Holes (for 9-hole rounds)
  holes_played INTEGER NOT NULL DEFAULT 18,

  -- Source
  source VARCHAR(50) NOT NULL,            -- 'tgf_event', 'ghin_sync', 'manual_entry'
  source_event_id UUID,                   -- If from TGF event

  -- Whether this counts for TGF handicap
  included_in_handicap BOOLEAN NOT NULL DEFAULT true,
  exclusion_reason TEXT,

  -- GHIN posting
  posted_to_ghin BOOLEAN NOT NULL DEFAULT false,
  ghin_post_date TIMESTAMPTZ,
  ghin_score_id VARCHAR(100),

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_score_history_user ON score_history(user_id);
CREATE INDEX idx_score_history_date ON score_history(user_id, played_date DESC);
CREATE INDEX idx_score_history_handicap ON score_history(user_id, included_in_handicap, played_date DESC);

-- =============================================================================
-- SECTION 8: COURSES
-- =============================================================================

-- Golf courses
CREATE TABLE courses (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  name VARCHAR(200) NOT NULL,

  -- Location
  address TEXT,
  city VARCHAR(100),
  state_province VARCHAR(100),
  postal_code VARCHAR(20),
  country VARCHAR(100) DEFAULT 'United States',
  latitude DECIMAL(10,7),
  longitude DECIMAL(10,7),
  timezone VARCHAR(50),

  -- Contact
  phone VARCHAR(20),
  email VARCHAR(255),
  website TEXT,

  -- USGA Data
  usga_course_id VARCHAR(50),

  -- Course details
  holes INTEGER DEFAULT 18,
  par INTEGER,

  -- Tee box data
  tee_boxes JSONB DEFAULT '[]',
  /*
    [
      {
        "name": "Blue",
        "color": "#0000FF",
        "yardage": 6800,
        "course_rating": 72.5,
        "slope_rating": 131,
        "par": 72
      },
      ...
    ]
  */

  -- Standard rates (before TGF negotiation)
  standard_rates JSONB DEFAULT '{}',
  /*
    {
      "weekday_9": 35.00,
      "weekday_18": 55.00,
      "weekend_9": 45.00,
      "weekend_18": 70.00,
      "twilight": 30.00,
      "cart_included": true,
      "range_included": false
    }
  */

  -- TGF contracted rates
  contracted_rates JSONB DEFAULT '{}',
  /*
    {
      "9_hole_rate": 25.00,
      "18_hole_rate": 40.00,
      "cart_included": true,
      "valid_until": "2025-12-31"
    }
  */

  -- Policies
  cancellation_notice_hours INTEGER DEFAULT 48,
  minimum_player_guarantee INTEGER,
  payment_terms VARCHAR(50),              -- 'net_30', 'due_on_play', 'prepay'

  -- TGF relationship
  relationship_status VARCHAR(20) DEFAULT 'prospect',  -- 'preferred', 'active', 'prospect', 'inactive'
  relationship_notes TEXT,

  -- Amenities/features
  amenities TEXT[],                       -- ['driving_range', 'putting_green', 'restaurant', 'bar']
  dress_code TEXT,
  special_notes TEXT,

  -- Soft delete
  deleted_at TIMESTAMPTZ,

  is_active BOOLEAN NOT NULL DEFAULT true,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_courses_city ON courses(city, state_province);
CREATE INDEX idx_courses_active ON courses(is_active) WHERE deleted_at IS NULL;
CREATE INDEX idx_courses_search ON courses USING gin(name gin_trgm_ops);

-- Course contacts
CREATE TABLE course_contacts (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id),

  role VARCHAR(50) NOT NULL,              -- 'head_pro', 'tournament_coordinator', 'gm', 'billing'
  is_primary BOOLEAN NOT NULL DEFAULT false,

  -- Direct contact override (if different from user profile)
  direct_phone VARCHAR(20),
  direct_email VARCHAR(255),

  notes TEXT,
  is_active BOOLEAN NOT NULL DEFAULT true,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_course_contacts_course ON course_contacts(course_id);

-- Add FK from score_history to courses
ALTER TABLE score_history
  ADD CONSTRAINT fk_score_course
  FOREIGN KEY (course_id) REFERENCES courses(id);

-- =============================================================================
-- SECTION 9: GAMES & BUNDLES
-- =============================================================================

-- Individual game types
CREATE TABLE games (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  name VARCHAR(100) NOT NULL,
  short_name VARCHAR(20),
  description TEXT,

  -- Type
  game_type VARCHAR(30) NOT NULL,         -- 'individual', 'team', 'skill_contest', 'pot'
  scoring_type VARCHAR(20),               -- 'net', 'gross', 'points', 'proximity'

  -- Requirements
  requires_membership BOOLEAN NOT NULL DEFAULT false,
  requires_ghin BOOLEAN NOT NULL DEFAULT false,
  min_players INTEGER,
  max_players INTEGER,

  -- Default pricing (can be overridden per event)
  default_price_9 DECIMAL(10,2) NOT NULL DEFAULT 0,
  default_price_18 DECIMAL(10,2) NOT NULL DEFAULT 0,

  -- Cost structure (for profit tracking)
  default_cost_9 DECIMAL(10,2) NOT NULL DEFAULT 0,   -- What goes to prize pool
  default_cost_18 DECIMAL(10,2) NOT NULL DEFAULT 0,

  -- Rules configuration
  rules_config JSONB DEFAULT '{}',
  /*
    {
      "payout_structure": "60/30/10",
      "carryover_enabled": true,
      "handicap_percentage": 100,
      ...
    }
  */

  -- Payout configuration
  payout_config JSONB DEFAULT '{}',
  /*
    {
      "method": "percentage",  // or "fixed", "per_player"
      "places": [60, 30, 10],
      "min_players_for_payout": 4
    }
  */

  display_order INTEGER NOT NULL DEFAULT 0,
  is_active BOOLEAN NOT NULL DEFAULT true,

  -- Soft delete
  deleted_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert default games
INSERT INTO games (name, short_name, game_type, scoring_type, requires_membership, default_price_9, default_price_18, display_order) VALUES
  ('Team MVP', 'Team MVP', 'team', 'net', false, 0, 0, 1),
  ('Closest to Pin', 'CTP', 'skill_contest', 'proximity', false, 0, 0, 2),
  ('Hole-in-One Pot', 'HIO', 'pot', 'points', false, 0, 0, 3),
  ('Individual Net', 'Ind Net', 'individual', 'net', true, 10, 15, 4),
  ('Net Skins', 'Net Skins', 'individual', 'net', true, 10, 15, 5),
  ('Individual Gross', 'Ind Gross', 'individual', 'gross', false, 10, 15, 6),
  ('Gross Skins', 'Gross Skins', 'individual', 'gross', false, 10, 15, 7),
  ('Long Drive', 'LD', 'skill_contest', 'proximity', false, 5, 5, 8);

-- Game bundles
CREATE TABLE bundles (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  name VARCHAR(100) NOT NULL,
  short_name VARCHAR(20),
  description TEXT,

  -- Requirements
  requires_membership BOOLEAN NOT NULL DEFAULT false,

  -- Default pricing
  default_price_9 DECIMAL(10,2) NOT NULL,
  default_price_18 DECIMAL(10,2) NOT NULL,

  -- Cost structure
  default_cost_9 DECIMAL(10,2) NOT NULL DEFAULT 0,
  default_cost_18 DECIMAL(10,2) NOT NULL DEFAULT 0,

  display_order INTEGER NOT NULL DEFAULT 0,
  is_active BOOLEAN NOT NULL DEFAULT true,

  -- Soft delete
  deleted_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert default bundles
INSERT INTO bundles (name, short_name, description, requires_membership, default_price_9, default_price_18, display_order) VALUES
  ('NET Games', 'NET', 'Individual Net + Net Skins', true, 15.00, 25.00, 1),
  ('GROSS Games', 'GROSS', 'Individual Gross + Gross Skins', false, 15.00, 25.00, 2);

-- Games in bundles
CREATE TABLE bundle_games (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  bundle_id UUID NOT NULL REFERENCES bundles(id) ON DELETE CASCADE,
  game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,

  display_order INTEGER NOT NULL DEFAULT 0,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(bundle_id, game_id)
);

-- Link NET bundle to its games
INSERT INTO bundle_games (bundle_id, game_id, display_order)
SELECT
  (SELECT id FROM bundles WHERE short_name = 'NET'),
  id,
  ROW_NUMBER() OVER ()
FROM games WHERE short_name IN ('Ind Net', 'Net Skins');

-- Link GROSS bundle to its games
INSERT INTO bundle_games (bundle_id, game_id, display_order)
SELECT
  (SELECT id FROM bundles WHERE short_name = 'GROSS'),
  id,
  ROW_NUMBER() OVER ()
FROM games WHERE short_name IN ('Ind Gross', 'Gross Skins');

-- =============================================================================
-- SECTION 10: EVENT TEMPLATES
-- =============================================================================

-- Reusable event configurations
CREATE TABLE event_templates (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  name VARCHAR(100) NOT NULL,             -- "Standard Tuesday 9s"
  description TEXT,

  -- Organization scope (who can use this template)
  organization_id UUID REFERENCES organizations(id),  -- NULL = global

  -- Event type
  event_type VARCHAR(30) NOT NULL,        -- '9_hole', '18_hole', 'championship', 'scramble'

  -- Included games (free with registration)
  included_game_ids UUID[],

  -- Available add-on bundles
  available_bundle_ids UUID[],

  -- Default pricing structure
  default_pricing JSONB DEFAULT '{}',
  /*
    {
      "base_price": 45.00,
      "member_price": 0,
      "guest_surcharge": 10.00,
      "first_timer_discount": 25.00,
      "tgf_markup": 10.00,
      "tax_rate": 0.0825
    }
  */

  -- Registration settings
  registration_settings JSONB DEFAULT '{}',
  /*
    {
      "opens_days_before": 14,
      "closes_hours_before": 24,
      "lock_hours_before": 48,
      "late_fee_enabled": true,
      "late_fee_amount": 10.00,
      "late_fee_cutoff_hours": 48,
      "max_players": 40,
      "waitlist_enabled": true
    }
  */

  -- Registration questions to include
  registration_question_ids UUID[],

  is_active BOOLEAN NOT NULL DEFAULT true,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- SECTION 11: EVENTS
-- =============================================================================

-- Events
CREATE TABLE events (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  -- Organization & template
  organization_id UUID NOT NULL REFERENCES organizations(id),
  template_id UUID REFERENCES event_templates(id),

  -- Basic info
  title VARCHAR(200) NOT NULL,
  description TEXT,
  event_type VARCHAR(30) NOT NULL,        -- '9_hole', '18_hole', 'championship', 'scramble', 'social'

  -- Course
  course_id UUID REFERENCES courses(id),
  course_notes TEXT,                      -- Event-specific course notes

  -- For multi-day events
  is_multi_day BOOLEAN NOT NULL DEFAULT false,

  -- Date/Time (for single-day events)
  event_date DATE,
  start_time TIME,
  check_in_time TIME,

  -- Capacity
  max_players INTEGER,
  min_players INTEGER DEFAULT 8,

  -- Registration windows
  registration_opens_at TIMESTAMPTZ,
  registration_closes_at TIMESTAMPTZ,
  registration_lock_at TIMESTAMPTZ,       -- When foursomes are locked for course notification

  -- Late fee
  late_fee_enabled BOOLEAN NOT NULL DEFAULT false,
  late_fee_amount DECIMAL(10,2),
  late_fee_after TIMESTAMPTZ,

  -- Status
  status event_status NOT NULL DEFAULT 'draft',

  -- Waitlist
  waitlist_enabled BOOLEAN NOT NULL DEFAULT true,

  -- Visibility (for cross-organization events)
  visibility VARCHAR(20) NOT NULL DEFAULT 'organization',  -- 'private', 'organization', 'invited', 'public'

  -- Flexible settings
  settings JSONB DEFAULT '{}',

  -- Results
  results_published_at TIMESTAMPTZ,
  results_data JSONB,

  -- Audit
  created_by_id UUID REFERENCES users(id),
  updated_by_id UUID REFERENCES users(id),
  published_at TIMESTAMPTZ,
  cancelled_at TIMESTAMPTZ,
  cancellation_reason TEXT,

  -- Soft delete
  deleted_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_events_org ON events(organization_id);
CREATE INDEX idx_events_date ON events(event_date);
CREATE INDEX idx_events_status ON events(status);
CREATE INDEX idx_events_course ON events(course_id);
CREATE INDEX idx_events_active ON events(id) WHERE deleted_at IS NULL;

-- Multi-day event days
CREATE TABLE event_days (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,

  day_number INTEGER NOT NULL,            -- 1, 2, 3...
  day_date DATE NOT NULL,
  start_time TIME NOT NULL,
  check_in_time TIME,

  -- Can have different course per day
  course_id UUID REFERENCES courses(id),

  -- Day-specific pricing (optional override)
  day_pricing JSONB,

  -- Day-specific settings
  settings JSONB DEFAULT '{}',

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(event_id, day_number)
);

-- Event invitations (for cross-org events)
CREATE TABLE event_invitations (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  invited_organization_id UUID NOT NULL REFERENCES organizations(id),

  invitation_type VARCHAR(20) NOT NULL DEFAULT 'open',  -- 'required', 'optional', 'open'
  max_players INTEGER,                    -- Cap per invited org

  invited_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  invited_by_id UUID REFERENCES users(id),

  UNIQUE(event_id, invited_organization_id)
);

-- Event pricing breakdown
CREATE TABLE event_pricing (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,

  -- What this pricing is for
  player_type VARCHAR(20) NOT NULL,       -- 'member', 'guest', 'first_timer'

  -- Pricing breakdown
  base_price DECIMAL(10,2) NOT NULL,      -- What player pays
  course_cost DECIMAL(10,2) NOT NULL,     -- What TGF pays course
  tgf_markup DECIMAL(10,2) NOT NULL,      -- TGF profit

  -- Tax
  is_taxable BOOLEAN NOT NULL DEFAULT true,
  tax_rate DECIMAL(5,4) DEFAULT 0.0825,

  -- Discounts
  discount_amount DECIMAL(10,2) DEFAULT 0,
  discount_reason VARCHAR(100),

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(event_id, player_type)
);

-- Games available at event
CREATE TABLE event_games (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  game_id UUID REFERENCES games(id),
  bundle_id UUID REFERENCES bundles(id),

  -- Must have either game_id or bundle_id
  CHECK ((game_id IS NOT NULL AND bundle_id IS NULL) OR (game_id IS NULL AND bundle_id IS NOT NULL)),

  -- Whether included free or add-on
  is_included BOOLEAN NOT NULL DEFAULT false,

  -- Price override
  price_override DECIMAL(10,2),
  cost_override DECIMAL(10,2),

  -- Is this mandatory?
  is_mandatory BOOLEAN NOT NULL DEFAULT false,

  display_order INTEGER NOT NULL DEFAULT 0,

  -- Results for this game
  results JSONB,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(event_id, game_id),
  UNIQUE(event_id, bundle_id)
);

-- =============================================================================
-- SECTION 12: REGISTRATION QUESTIONS
-- =============================================================================

-- Configurable registration questions
CREATE TABLE registration_questions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  question_key VARCHAR(100) NOT NULL UNIQUE,  -- 'tee_preference', 'playing_partner', etc.

  question_text VARCHAR(500) NOT NULL,
  help_text TEXT,

  question_type question_type NOT NULL,

  -- Options for select/multi_select
  options JSONB,                          -- ["<50", "50-64", "65+", "Forward"]

  -- Validation
  is_required BOOLEAN NOT NULL DEFAULT false,
  validation_rules JSONB,                 -- min, max, pattern, etc.

  -- Who sees this question
  applies_to VARCHAR(20) DEFAULT 'all',   -- 'all', 'members', 'guests', 'first_timers'

  -- Smart autofill
  autofill_source VARCHAR(50),            -- 'preference', 'profile', 'calculated'
  autofill_key VARCHAR(100),              -- Which preference/profile field

  display_order INTEGER NOT NULL DEFAULT 0,
  is_active BOOLEAN NOT NULL DEFAULT true,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert default questions
INSERT INTO registration_questions (question_key, question_text, question_type, options, is_required, autofill_source, autofill_key, display_order) VALUES
  ('tee_preference', 'Which tees will you play?', 'select', '["Under 50", "50-64", "65+", "Forward"]', true, 'preference', 'tee_preference', 1),
  ('playing_partner', 'Playing partner request (optional)', 'text', NULL, false, NULL, NULL, 2),
  ('fellowship_after', 'Will you join us for fellowship after?', 'yes_no', NULL, false, 'preference', 'fellowship_after', 3),
  ('dietary_restrictions', 'Any dietary restrictions?', 'text', NULL, false, 'preference', 'dietary_restrictions', 4),
  ('special_requests', 'Special requests or notes', 'text', NULL, false, NULL, NULL, 5);

-- =============================================================================
-- SECTION 13: REGISTRATIONS
-- =============================================================================

-- Event registrations
CREATE TABLE registrations (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id),

  -- For multi-day: which days they're playing
  event_day_ids UUID[],

  -- Player classification at time of registration
  player_type VARCHAR(20) NOT NULL,       -- 'member', 'guest', 'first_timer'

  -- Pricing at time of registration
  subtotal DECIMAL(10,2) NOT NULL,
  tax_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
  late_fee_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
  discount_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
  total_amount DECIMAL(10,2) NOT NULL,

  -- What's been paid
  amount_paid DECIMAL(10,2) NOT NULL DEFAULT 0,

  -- Payment details
  payment_status payment_status NOT NULL DEFAULT 'pending',
  payment_method VARCHAR(50),             -- 'stripe', 'wallet', 'cash', 'venmo', 'check', 'comp'
  stripe_payment_intent_id VARCHAR(255),
  wallet_amount_used DECIMAL(10,2) DEFAULT 0,

  -- Waitlist
  is_waitlisted BOOLEAN NOT NULL DEFAULT false,
  waitlist_position INTEGER,
  waitlist_offered_at TIMESTAMPTZ,
  waitlist_expires_at TIMESTAMPTZ,
  waitlist_promoted_at TIMESTAMPTZ,

  -- Check-in
  checked_in_at TIMESTAMPTZ,
  checked_in_by_id UUID REFERENCES users(id),

  -- Cancellation
  cancelled_at TIMESTAMPTZ,
  cancellation_reason TEXT,
  refund_amount DECIMAL(10,2),
  refund_method VARCHAR(50),              -- 'original_payment', 'wallet'

  -- Notes
  player_notes TEXT,
  manager_notes TEXT,

  -- Responses to registration questions
  responses JSONB DEFAULT '{}',
  /*
    {
      "tee_preference": "50-64",
      "fellowship_after": true,
      "playing_partner": "John Doe"
    }
  */

  -- Soft delete
  deleted_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(event_id, user_id)
);

CREATE INDEX idx_registrations_event ON registrations(event_id);
CREATE INDEX idx_registrations_user ON registrations(user_id);
CREATE INDEX idx_registrations_status ON registrations(payment_status);
CREATE INDEX idx_registrations_waitlist ON registrations(event_id, is_waitlisted, waitlist_position);

-- Games/bundles selected per registration
CREATE TABLE registration_games (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  registration_id UUID NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
  event_game_id UUID NOT NULL REFERENCES event_games(id),

  -- Price at time of registration
  price DECIMAL(10,2) NOT NULL,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(registration_id, event_game_id)
);

-- =============================================================================
-- SECTION 14: PLAYING PARTNER REQUESTS
-- =============================================================================

-- Partner requests with smart logic
CREATE TABLE playing_partner_requests (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  registration_id UUID NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
  requested_partner_id UUID NOT NULL REFERENCES users(id),

  -- Status
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  /*
    'pending' - Waiting for response
    'auto_accepted' - Both have each other as preferred
    'accepted' - Partner accepted
    'declined' - Partner declined
    'unavailable' - Partner not registered
    'overridden' - System override (match play, etc.)
    'expired' - No response in time
  */

  -- Tracking
  partner_registered BOOLEAN NOT NULL DEFAULT false,
  partner_notified_at TIMESTAMPTZ,
  partner_responded_at TIMESTAMPTZ,
  response_deadline TIMESTAMPTZ,

  -- If overridden
  override_reason TEXT,
  overridden_by_id UUID REFERENCES users(id),

  -- If partner wasn't registered and we invited them
  invitation_sent_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_partner_requests_reg ON playing_partner_requests(registration_id);
CREATE INDEX idx_partner_requests_partner ON playing_partner_requests(requested_partner_id);

-- Required pairings (match play, teams)
CREATE TABLE required_pairings (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,

  pairing_type VARCHAR(30) NOT NULL,      -- 'match_play', 'team', 'mandatory'

  player_1_id UUID NOT NULL REFERENCES users(id),
  player_2_id UUID NOT NULL REFERENCES users(id),

  -- Source of this pairing
  source VARCHAR(30) NOT NULL,            -- 'season_contest', 'manager_assigned', 'team_event'
  source_id UUID,                         -- contest_id, team_id, etc.

  -- Priority (higher = can't be overridden)
  priority INTEGER NOT NULL DEFAULT 50,

  notes TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CHECK(player_1_id != player_2_id)
);

CREATE INDEX idx_required_pairings_event ON required_pairings(event_id);

-- =============================================================================
-- SECTION 15: TEAMS (for scrambles, Ryder Cup, etc.)
-- =============================================================================

-- Teams
CREATE TABLE teams (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,

  name VARCHAR(100) NOT NULL,

  -- For Ryder Cup style (two sides)
  side VARCHAR(50),                       -- 'USA', 'Europe', 'Team A', 'Team B'

  -- Captains
  captain_id UUID REFERENCES users(id),
  co_captain_id UUID REFERENCES users(id),

  -- Scoring
  total_score INTEGER,
  total_points DECIMAL(5,1),

  -- Metadata
  settings JSONB DEFAULT '{}',

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_teams_event ON teams(event_id);

-- Team members
CREATE TABLE team_members (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  team_id UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id),
  registration_id UUID REFERENCES registrations(id),

  role VARCHAR(30) DEFAULT 'member',      -- 'captain', 'co_captain', 'member'

  -- Individual contribution
  individual_score INTEGER,
  individual_points DECIMAL(5,1),

  joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(team_id, user_id)
);

CREATE INDEX idx_team_members_team ON team_members(team_id);
CREATE INDEX idx_team_members_user ON team_members(user_id);

-- =============================================================================
-- SECTION 16: TRANSACTIONS & WALLET
-- =============================================================================

-- All financial transactions
CREATE TABLE transactions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  user_id UUID REFERENCES users(id),

  type transaction_type NOT NULL,

  -- Money
  amount DECIMAL(10,2) NOT NULL,          -- Positive = money in, Negative = money out

  -- Financial breakdown
  revenue_amount DECIMAL(10,2),           -- Amount that's revenue to TGF
  cost_amount DECIMAL(10,2),              -- Amount that's cost (course fees, prize pool)
  tgf_profit DECIMAL(10,2),               -- TGF markup/profit
  tax_amount DECIMAL(10,2),               -- Sales tax collected

  description TEXT NOT NULL,

  -- Related records
  registration_id UUID REFERENCES registrations(id),
  membership_id UUID REFERENCES user_memberships(id),
  gift_card_id UUID,                      -- FK added later
  promo_code_id UUID,                     -- FK added later

  -- Stripe
  stripe_payment_intent_id VARCHAR(255),
  stripe_charge_id VARCHAR(255),
  stripe_refund_id VARCHAR(255),

  -- Idempotency
  idempotency_key VARCHAR(255) UNIQUE,

  -- Status
  status VARCHAR(20) NOT NULL DEFAULT 'completed',

  -- Metadata
  metadata JSONB DEFAULT '{}',

  -- Soft delete
  deleted_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  processed_at TIMESTAMPTZ
);

CREATE INDEX idx_transactions_user ON transactions(user_id);
CREATE INDEX idx_transactions_type ON transactions(type);
CREATE INDEX idx_transactions_registration ON transactions(registration_id);
CREATE INDEX idx_transactions_stripe ON transactions(stripe_payment_intent_id);
CREATE INDEX idx_transactions_date ON transactions(created_at);

-- Wallet transactions (detailed balance changes)
CREATE TABLE wallet_transactions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  user_id UUID NOT NULL REFERENCES users(id),

  amount DECIMAL(10,2) NOT NULL,          -- Positive = credit, Negative = debit
  balance_before DECIMAL(10,2) NOT NULL,
  balance_after DECIMAL(10,2) NOT NULL,

  description TEXT NOT NULL,

  -- Related records
  transaction_id UUID REFERENCES transactions(id),
  registration_id UUID REFERENCES registrations(id),

  -- Source of credit (for winnings)
  source VARCHAR(50),                     -- 'deposit', 'winnings', 'refund', 'adjustment', 'gift_card'
  source_details JSONB,

  -- Who made this change
  created_by_id UUID REFERENCES users(id),

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_wallet_transactions_user ON wallet_transactions(user_id);
CREATE INDEX idx_wallet_transactions_date ON wallet_transactions(created_at);

-- Financial summary per event (pre-calculated)
CREATE TABLE event_financial_summary (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,

  -- Revenue
  total_registrations INTEGER NOT NULL DEFAULT 0,
  total_revenue DECIMAL(10,2) NOT NULL DEFAULT 0,

  -- By type
  member_revenue DECIMAL(10,2) DEFAULT 0,
  guest_revenue DECIMAL(10,2) DEFAULT 0,
  addon_revenue DECIMAL(10,2) DEFAULT 0,
  late_fee_revenue DECIMAL(10,2) DEFAULT 0,

  -- Costs
  course_cost DECIMAL(10,2) DEFAULT 0,
  prize_pool DECIMAL(10,2) DEFAULT 0,
  other_costs DECIMAL(10,2) DEFAULT 0,
  total_cost DECIMAL(10,2) DEFAULT 0,

  -- Profit
  gross_profit DECIMAL(10,2) DEFAULT 0,
  tgf_markup_total DECIMAL(10,2) DEFAULT 0,

  -- Tax
  sales_tax_collected DECIMAL(10,2) DEFAULT 0,

  -- Net
  net_profit DECIMAL(10,2) DEFAULT 0,

  calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(event_id)
);

-- Tax obligations (for reporting)
CREATE TABLE tax_obligations (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  period VARCHAR(7) NOT NULL,             -- '2025-01' (YYYY-MM)
  organization_id UUID REFERENCES organizations(id),  -- NULL = all TGF

  taxable_sales DECIMAL(12,2) NOT NULL DEFAULT 0,
  tax_rate DECIMAL(5,4) NOT NULL,
  tax_owed DECIMAL(10,2) NOT NULL DEFAULT 0,

  status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- 'pending', 'calculated', 'filed', 'paid'

  filed_at TIMESTAMPTZ,
  paid_at TIMESTAMPTZ,
  confirmation_number VARCHAR(100),

  notes TEXT,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(period, organization_id)
);

-- =============================================================================
-- SECTION 17: PROMO CODES & GIFT CARDS
-- =============================================================================

-- Promo codes
CREATE TABLE promo_codes (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  code VARCHAR(50) NOT NULL UNIQUE,
  description TEXT,

  -- Discount type
  discount_type VARCHAR(20) NOT NULL,     -- 'percentage', 'fixed_amount'
  discount_value DECIMAL(10,2) NOT NULL,  -- 10 for 10% or $10

  -- Limits
  max_uses INTEGER,
  max_uses_per_user INTEGER DEFAULT 1,
  current_uses INTEGER NOT NULL DEFAULT 0,

  -- Validity
  valid_from TIMESTAMPTZ,
  valid_until TIMESTAMPTZ,

  -- Restrictions
  applies_to VARCHAR(30) DEFAULT 'all',   -- 'all', 'membership', 'events', 'specific_events'
  applicable_event_ids UUID[],
  minimum_purchase DECIMAL(10,2),

  -- Who can use
  user_restrictions VARCHAR(30) DEFAULT 'all',  -- 'all', 'new_users', 'members', 'specific_users'
  allowed_user_ids UUID[],

  is_active BOOLEAN NOT NULL DEFAULT true,

  -- Soft delete
  deleted_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Promo code usage tracking
CREATE TABLE promo_code_uses (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  promo_code_id UUID NOT NULL REFERENCES promo_codes(id),
  user_id UUID NOT NULL REFERENCES users(id),

  used_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- What it was used for
  registration_id UUID REFERENCES registrations(id),
  membership_id UUID REFERENCES user_memberships(id),

  discount_applied DECIMAL(10,2) NOT NULL
);

CREATE INDEX idx_promo_uses_code ON promo_code_uses(promo_code_id);
CREATE INDEX idx_promo_uses_user ON promo_code_uses(user_id);

-- Gift cards
CREATE TABLE gift_cards (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  code VARCHAR(20) NOT NULL UNIQUE,

  -- Value
  original_value DECIMAL(10,2) NOT NULL,
  current_balance DECIMAL(10,2) NOT NULL,

  -- Purchase info
  purchased_by_id UUID REFERENCES users(id),
  purchased_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  purchase_transaction_id UUID REFERENCES transactions(id),

  -- Recipient
  recipient_email VARCHAR(255),
  recipient_name VARCHAR(200),
  personal_message TEXT,

  -- Delivery
  delivered_at TIMESTAMPTZ,
  delivery_method VARCHAR(20),            -- 'email', 'print'

  -- Redemption
  redeemed_by_id UUID REFERENCES users(id),
  redeemed_at TIMESTAMPTZ,

  -- Validity
  expires_at TIMESTAMPTZ,

  is_active BOOLEAN NOT NULL DEFAULT true,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_gift_cards_code ON gift_cards(code);

-- Add FKs to transactions
ALTER TABLE transactions
  ADD CONSTRAINT fk_gift_card FOREIGN KEY (gift_card_id) REFERENCES gift_cards(id);
ALTER TABLE transactions
  ADD CONSTRAINT fk_promo_code FOREIGN KEY (promo_code_id) REFERENCES promo_codes(id);

-- =============================================================================
-- SECTION 18: ACTION ITEMS & APPROVALS
-- =============================================================================

-- Outstanding action items
CREATE TABLE action_items (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  -- Type
  item_type VARCHAR(50) NOT NULL,
  /*
    'customer_response_needed' - Player needs to answer something
    'manager_followup' - Manager needs to follow up
    'course_confirmation' - Need confirmation from course
    'approval_needed' - Something needs approval
    'payment_issue' - Payment problem to resolve
  */

  -- What needs action
  title VARCHAR(200) NOT NULL,
  description TEXT,

  -- Related records
  related_type VARCHAR(50),               -- 'registration', 'event', 'user', 'refund'
  related_id UUID,

  -- Organization
  organization_id UUID REFERENCES organizations(id),

  -- Assignment
  assigned_to_id UUID REFERENCES users(id),
  regarding_user_id UUID REFERENCES users(id),

  -- Urgency
  priority VARCHAR(20) NOT NULL DEFAULT 'medium',  -- 'low', 'medium', 'high', 'urgent'
  due_at TIMESTAMPTZ,
  escalate_at TIMESTAMPTZ,
  escalate_to_id UUID REFERENCES users(id),

  -- Status
  status action_status NOT NULL DEFAULT 'pending',

  -- Resolution
  resolved_at TIMESTAMPTZ,
  resolved_by_id UUID REFERENCES users(id),
  resolution_notes TEXT,

  -- Metadata
  metadata JSONB DEFAULT '{}',

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_action_items_status ON action_items(status);
CREATE INDEX idx_action_items_assigned ON action_items(assigned_to_id);
CREATE INDEX idx_action_items_org ON action_items(organization_id);
CREATE INDEX idx_action_items_due ON action_items(due_at) WHERE status = 'pending';

-- Messages on action items
CREATE TABLE action_item_messages (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  action_item_id UUID NOT NULL REFERENCES action_items(id) ON DELETE CASCADE,

  sender_id UUID REFERENCES users(id),
  message TEXT NOT NULL,

  sent_via VARCHAR(20),                   -- 'system', 'email', 'sms', 'in_app'

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_action_messages_item ON action_item_messages(action_item_id);

-- Approval requests
CREATE TABLE approval_requests (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  -- What needs approval
  action_type VARCHAR(50) NOT NULL,
  /*
    'comp_registration', 'override_refund', 'wallet_adjustment',
    'batch_operation', 'event_cancellation'
  */

  title VARCHAR(200) NOT NULL,
  description TEXT,

  -- Related records
  related_type VARCHAR(50),
  related_id UUID,

  -- Details of the action
  action_details JSONB NOT NULL,

  -- Who's requesting
  requested_by_id UUID NOT NULL REFERENCES users(id),
  organization_id UUID REFERENCES organizations(id),

  -- Who can approve
  required_role_level INTEGER NOT NULL,   -- Minimum role level to approve

  -- Status
  status approval_status NOT NULL DEFAULT 'pending',

  -- Response
  responded_by_id UUID REFERENCES users(id),
  responded_at TIMESTAMPTZ,
  response_notes TEXT,

  -- Expiration
  expires_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_approval_requests_status ON approval_requests(status);
CREATE INDEX idx_approval_requests_requester ON approval_requests(requested_by_id);

-- =============================================================================
-- SECTION 19: BATCH OPERATIONS
-- =============================================================================

-- Batch operation tracking
CREATE TABLE batch_operations (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  operation_type VARCHAR(50) NOT NULL,
  /*
    'update_events', 'update_registrations', 'send_communications',
    'apply_pricing', 'cancel_events'
  */

  name VARCHAR(200),
  description TEXT,

  -- Scope
  scope_type VARCHAR(30) NOT NULL,        -- 'single', 'selection', 'organization', 'global'
  scope_filter JSONB,                     -- Criteria used to select records

  -- What to change
  changes JSONB NOT NULL,

  -- Status
  status VARCHAR(20) NOT NULL DEFAULT 'draft',
  /*
    'draft', 'pending_approval', 'approved', 'executing',
    'completed', 'partially_completed', 'failed', 'cancelled'
  */

  -- Approval
  requires_approval BOOLEAN NOT NULL DEFAULT false,
  approval_request_id UUID REFERENCES approval_requests(id),

  -- Execution
  created_by_id UUID NOT NULL REFERENCES users(id),
  approved_by_id UUID REFERENCES users(id),
  executed_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,

  -- Results
  records_affected INTEGER,
  records_succeeded INTEGER,
  records_failed INTEGER,
  failure_details JSONB,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Batch operation templates
CREATE TABLE batch_operation_templates (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  name VARCHAR(200) NOT NULL,
  description TEXT,

  operation_type VARCHAR(50) NOT NULL,
  scope_template JSONB,
  changes_template JSONB NOT NULL,

  created_by_id UUID REFERENCES users(id),

  is_active BOOLEAN NOT NULL DEFAULT true,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- SECTION 20: COMMUNICATIONS & NOTIFICATIONS
-- =============================================================================

-- Email templates
CREATE TABLE email_templates (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  key VARCHAR(100) NOT NULL UNIQUE,       -- 'registration_confirmation', 'event_reminder', etc.
  name VARCHAR(200) NOT NULL,
  description TEXT,

  -- Content
  subject_template TEXT NOT NULL,
  body_template TEXT NOT NULL,            -- Supports variables like {{first_name}}, {{event_title}}

  -- Availability
  organization_id UUID REFERENCES organizations(id),  -- NULL = global

  is_active BOOLEAN NOT NULL DEFAULT true,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Notification preferences (granular)
CREATE TABLE notification_preferences (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

  notification_type VARCHAR(50) NOT NULL,
  /*
    'event_registration', 'event_reminder', 'event_results',
    'partner_request', 'waitlist_promotion', 'membership_expiring',
    'wallet_activity', 'marketing'
  */

  email_enabled BOOLEAN NOT NULL DEFAULT true,
  sms_enabled BOOLEAN NOT NULL DEFAULT false,
  push_enabled BOOLEAN NOT NULL DEFAULT true,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(user_id, notification_type)
);

-- Notification history
CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  user_id UUID NOT NULL REFERENCES users(id),

  notification_type VARCHAR(50) NOT NULL,
  title VARCHAR(200) NOT NULL,
  body TEXT NOT NULL,

  -- Channels used
  sent_via_email BOOLEAN NOT NULL DEFAULT false,
  sent_via_sms BOOLEAN NOT NULL DEFAULT false,
  sent_via_push BOOLEAN NOT NULL DEFAULT false,

  -- Related records
  related_type VARCHAR(50),
  related_id UUID,

  -- Delivery status
  email_sent_at TIMESTAMPTZ,
  email_delivered_at TIMESTAMPTZ,
  email_opened_at TIMESTAMPTZ,

  sms_sent_at TIMESTAMPTZ,
  sms_delivered_at TIMESTAMPTZ,

  push_sent_at TIMESTAMPTZ,
  push_opened_at TIMESTAMPTZ,

  -- In-app status
  read_at TIMESTAMPTZ,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_notifications_user ON notifications(user_id);
CREATE INDEX idx_notifications_unread ON notifications(user_id, read_at) WHERE read_at IS NULL;

-- Course communications
CREATE TABLE course_communications (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  course_id UUID NOT NULL REFERENCES courses(id),
  event_id UUID REFERENCES events(id),

  comm_type VARCHAR(30) NOT NULL,
  /*
    'quote_request', 'booking_confirmation', 'player_count_update',
    'final_count', 'invoice_request', 'payment_confirmation', 'general'
  */

  subject VARCHAR(200) NOT NULL,
  body TEXT NOT NULL,
  attachments JSONB DEFAULT '[]',

  -- Recipient
  sent_to_contact_id UUID REFERENCES course_contacts(id),
  sent_to_email VARCHAR(255),

  -- Delivery
  sent_at TIMESTAMPTZ,
  sent_by_id UUID REFERENCES users(id),
  sent_via VARCHAR(20),                   -- 'email', 'portal'

  -- Response
  response_received_at TIMESTAMPTZ,
  response_content TEXT,
  responded_by_contact_id UUID REFERENCES course_contacts(id),

  status VARCHAR(20) NOT NULL DEFAULT 'draft',

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_course_comms_course ON course_communications(course_id);
CREATE INDEX idx_course_comms_event ON course_communications(event_id);

-- Course quotes
CREATE TABLE course_quotes (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  course_id UUID NOT NULL REFERENCES courses(id),
  event_id UUID REFERENCES events(id),
  communication_id UUID REFERENCES course_communications(id),

  -- Quote details
  quoted_by_contact_id UUID REFERENCES course_contacts(id),
  quoted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  valid_until DATE,

  -- Pricing
  green_fee_per_player DECIMAL(10,2),
  cart_fee_per_player DECIMAL(10,2),
  range_included BOOLEAN DEFAULT false,
  food_credit_per_player DECIMAL(10,2),

  minimum_players INTEGER,
  maximum_players INTEGER,

  -- Terms
  payment_terms VARCHAR(50),
  cancellation_policy TEXT,
  special_conditions TEXT,

  -- Full quote data
  quote_details JSONB,

  -- Status
  status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- 'pending', 'accepted', 'declined', 'expired', 'countered'

  accepted_at TIMESTAMPTZ,
  accepted_by_id UUID REFERENCES users(id),
  declined_reason TEXT,

  counter_quote_id UUID REFERENCES course_quotes(id),

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_course_quotes_course ON course_quotes(course_id);
CREATE INDEX idx_course_quotes_event ON course_quotes(event_id);

-- =============================================================================
-- SECTION 21: AUDIT & FEATURE FLAGS
-- =============================================================================

-- Audit logs
CREATE TABLE audit_logs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  -- Who
  user_id UUID REFERENCES users(id),
  user_email VARCHAR(255),

  -- What
  table_name VARCHAR(100) NOT NULL,
  record_id UUID NOT NULL,
  action VARCHAR(20) NOT NULL,            -- 'create', 'update', 'delete', 'restore'

  -- Changes
  old_values JSONB,
  new_values JSONB,
  changed_fields TEXT[],

  -- Context
  ip_address VARCHAR(45),
  user_agent TEXT,
  request_id VARCHAR(100),

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_table ON audit_logs(table_name, record_id);
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_date ON audit_logs(created_at);

-- Feature flags
CREATE TABLE feature_flags (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  key VARCHAR(100) NOT NULL UNIQUE,
  name VARCHAR(200) NOT NULL,
  description TEXT,

  enabled BOOLEAN NOT NULL DEFAULT false,

  -- Granular enabling
  enabled_for_user_ids UUID[],
  enabled_for_organization_ids UUID[],
  enabled_percentage INTEGER,             -- For gradual rollout (0-100)

  metadata JSONB DEFAULT '{}',

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert feature flags
INSERT INTO feature_flags (key, name, description, enabled) VALUES
  ('wallet_system', 'Wallet/Credits System', 'Allow members to maintain wallet balance', true),
  ('guest_registration', 'Guest Registration', 'Allow non-members to register', true),
  ('waitlist', 'Waitlist System', 'Enable waitlist when events full', true),
  ('smart_partner_matching', 'Smart Partner Matching', 'Auto-pair mutual preferred partners', true),
  ('handicap_tracking', 'Custom Handicap Tracking', 'TGF handicap calculation system', false),
  ('ghin_sync', 'GHIN Synchronization', 'Sync handicaps with GHIN', false),
  ('season_contests', 'Season Contests', 'Points races and season competitions', false),
  ('ai_assistant', 'AI Assistant', 'AI chat interface for managers and players', false),
  ('course_portal', 'Course Portal', 'External portal for course contacts', false),
  ('batch_operations', 'Batch Operations', 'Bulk edit functionality', true),
  ('promo_codes', 'Promo Codes', 'Discount code system', true),
  ('gift_cards', 'Gift Cards', 'Gift card purchase and redemption', false);

-- =============================================================================
-- SECTION 22: FUNCTIONS & TRIGGERS
-- =============================================================================

-- Auto-update timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply to all tables with updated_at
DO $$
DECLARE
  t text;
BEGIN
  FOR t IN
    SELECT table_name
    FROM information_schema.columns
    WHERE column_name = 'updated_at'
    AND table_schema = 'public'
  LOOP
    EXECUTE format('
      DROP TRIGGER IF EXISTS update_%I_updated_at ON %I;
      CREATE TRIGGER update_%I_updated_at
        BEFORE UPDATE ON %I
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    ', t, t, t, t);
  END LOOP;
END;
$$;

-- Function to check mutual preferred partners
CREATE OR REPLACE FUNCTION check_mutual_preferred_partners(
  user_a UUID,
  user_b UUID
) RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM user_preferred_partners upp1
    JOIN user_preferred_partners upp2 ON upp1.user_id = upp2.partner_user_id
      AND upp1.partner_user_id = upp2.user_id
    WHERE upp1.user_id = user_a AND upp1.partner_user_id = user_b
  );
END;
$$ LANGUAGE plpgsql;

-- Function to calculate registration total
CREATE OR REPLACE FUNCTION calculate_registration_total(
  p_event_id UUID,
  p_user_id UUID,
  p_player_type VARCHAR,
  p_game_ids UUID[]
) RETURNS TABLE (
  subtotal DECIMAL(10,2),
  tax_amount DECIMAL(10,2),
  total_amount DECIMAL(10,2)
) AS $$
DECLARE
  v_base_price DECIMAL(10,2);
  v_tax_rate DECIMAL(5,4);
  v_subtotal DECIMAL(10,2) := 0;
  v_tax DECIMAL(10,2) := 0;
  v_game_price DECIMAL(10,2);
BEGIN
  -- Get base price for player type
  SELECT ep.base_price, ep.tax_rate INTO v_base_price, v_tax_rate
  FROM event_pricing ep
  WHERE ep.event_id = p_event_id AND ep.player_type = p_player_type;

  v_subtotal := COALESCE(v_base_price, 0);

  -- Add game prices
  FOR v_game_price IN
    SELECT COALESCE(eg.price_override, g.default_price_9, b.default_price_9)
    FROM event_games eg
    LEFT JOIN games g ON eg.game_id = g.id
    LEFT JOIN bundles b ON eg.bundle_id = b.id
    WHERE eg.event_id = p_event_id
    AND eg.id = ANY(p_game_ids)
    AND eg.is_included = false
  LOOP
    v_subtotal := v_subtotal + v_game_price;
  END LOOP;

  -- Calculate tax
  v_tax := ROUND(v_subtotal * COALESCE(v_tax_rate, 0.0825), 2);

  RETURN QUERY SELECT v_subtotal, v_tax, v_subtotal + v_tax;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- DONE!
-- =============================================================================
-- Comprehensive TGF Platform schema complete.
-- This schema supports:
-- - Flexible organization hierarchy
-- - Role-based permissions
-- - Smart partner matching
-- - Multi-day and team events
-- - Custom handicap tracking
-- - Full financial tracking with TGF markup
-- - Promo codes and gift cards
-- - Action items and approvals
-- - Batch operations
-- - Course communications
-- - Audit logging
-- =============================================================================
