-- =============================================================================
-- TGF PLATFORM - INITIAL DATABASE SCHEMA
-- =============================================================================
-- This file creates all the database tables needed for the MVP.
-- Run this in your Supabase SQL Editor to set up the database.
--
-- Tables Overview:
-- 1. chapters          - San Antonio, Austin, etc.
-- 2. membership_types  - Annual, Founding, etc.
-- 3. members           - All users (members, guests, prospects)
-- 4. member_memberships - History of who had what membership when
-- 5. games             - NET Skins, GROSS Skins, CTP, etc.
-- 6. events            - Calendar of golf events
-- 7. event_games       - Which games are offered at each event
-- 8. registrations     - Who's playing in what event
-- 9. registration_games - Which games each player selected
-- 10. transactions     - All financial transactions
-- 11. wallet_transactions - Wallet balance changes
-- 12. audit_logs       - Who changed what when (for troubleshooting)
-- 13. feature_flags    - Toggle features on/off
-- =============================================================================

-- Enable UUID generation (for unique IDs)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- CUSTOM TYPES (Think of these as dropdown options)
-- =============================================================================

-- Member status - what kind of user is this?
CREATE TYPE member_status AS ENUM (
  'active_member',     -- Currently paid up membership
  'expired_member',    -- Was a member, membership lapsed
  'former_member',     -- Explicitly cancelled/left
  'guest',             -- Has played but never been a member
  'prospect'           -- Signed up but never played or joined
);

-- Payment status for registrations
CREATE TYPE payment_status AS ENUM (
  'pending',           -- Registered but not paid yet
  'paid',              -- Payment received
  'partially_paid',    -- Partial payment (credits + card)
  'refunded',          -- Full refund issued
  'partially_refunded',-- Partial refund issued
  'comped'             -- Free registration (manager discretion)
);

-- Event status
CREATE TYPE event_status AS ENUM (
  'draft',             -- Being set up, not visible to public
  'published',         -- Open for registration
  'registration_closed', -- Past deadline but event not happened
  'in_progress',       -- Event is happening now
  'completed',         -- Event finished
  'cancelled'          -- Event cancelled
);

-- Transaction types
CREATE TYPE transaction_type AS ENUM (
  'membership_purchase',    -- Bought a membership
  'membership_renewal',     -- Renewed a membership
  'event_registration',     -- Paid for an event
  'wallet_deposit',         -- Added money to wallet
  'wallet_payment',         -- Paid from wallet balance
  'wallet_credit',          -- Manager credited wallet (winnings, etc)
  'refund',                 -- Money returned
  'adjustment'              -- Manual correction
);

-- =============================================================================
-- TABLE: chapters
-- =============================================================================
-- Your chapter locations: San Antonio, Austin, etc.
-- This is where you define each chapter's basic info.
-- =============================================================================

CREATE TABLE chapters (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  -- Basic info
  name VARCHAR(100) NOT NULL,           -- "San Antonio", "Austin"
  code VARCHAR(10) NOT NULL UNIQUE,     -- "SA", "AUS" (short code)
  city VARCHAR(100) NOT NULL,
  state VARCHAR(2) NOT NULL DEFAULT 'TX',

  -- Display settings
  description TEXT,                      -- About this chapter
  is_active BOOLEAN NOT NULL DEFAULT true,
  display_order INTEGER NOT NULL DEFAULT 0, -- For sorting in dropdowns

  -- Settings (flexible JSON for future options)
  settings JSONB DEFAULT '{}',

  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert your initial chapters
INSERT INTO chapters (name, code, city, state, display_order) VALUES
  ('San Antonio', 'SA', 'San Antonio', 'TX', 1),
  ('Austin', 'AUS', 'Austin', 'TX', 2);

-- =============================================================================
-- TABLE: membership_types
-- =============================================================================
-- Different membership products you offer.
-- Examples: Annual Membership, Founding Member, etc.
-- =============================================================================

CREATE TABLE membership_types (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  -- Basic info
  name VARCHAR(100) NOT NULL,            -- "Annual Membership"
  description TEXT,                       -- What's included

  -- Pricing
  price DECIMAL(10,2) NOT NULL,          -- 300.00
  duration_months INTEGER NOT NULL,       -- 12 for annual

  -- Rules
  is_active BOOLEAN NOT NULL DEFAULT true,
  is_publicly_available BOOLEAN NOT NULL DEFAULT true, -- Can people buy this online?

  -- Chapter restrictions (NULL = all chapters)
  -- If set, this membership only works for specific chapters
  allowed_chapter_ids UUID[] DEFAULT NULL,

  -- Benefits stored as flexible JSON
  -- Example: {"guest_events_per_year": 2, "merchandise_discount": 10}
  benefits JSONB DEFAULT '{}',

  -- Display
  display_order INTEGER NOT NULL DEFAULT 0,

  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert your initial membership type
INSERT INTO membership_types (name, description, price, duration_months, benefits) VALUES
  ('Annual Membership', 'Full TGF membership with access to all chapters, member pricing on events, and eligibility for NET games and season contests.', 300.00, 12, '{"all_chapters": true, "net_games": true, "season_contests": true}');

-- =============================================================================
-- TABLE: members
-- =============================================================================
-- Everyone who interacts with TGF: members, guests, prospects.
-- This is your main "people" table.
-- =============================================================================

CREATE TABLE members (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  -- Link to Supabase Auth (for login)
  auth_user_id UUID UNIQUE,              -- Links to auth.users table

  -- Personal info
  email VARCHAR(255) NOT NULL UNIQUE,
  first_name VARCHAR(100) NOT NULL,
  last_name VARCHAR(100) NOT NULL,
  phone VARCHAR(20),

  -- Golf info
  ghin_number VARCHAR(20),               -- Their USGA handicap ID
  home_chapter_id UUID REFERENCES chapters(id),

  -- Membership status (computed from member_memberships, but cached here for speed)
  status member_status NOT NULL DEFAULT 'prospect',
  current_membership_id UUID,            -- Current active membership (FK added later)
  membership_expires_at TIMESTAMPTZ,     -- When current membership ends

  -- Wallet/Credits
  wallet_balance DECIMAL(10,2) NOT NULL DEFAULT 0.00,

  -- Stripe integration
  stripe_customer_id VARCHAR(255),       -- Their Stripe customer ID

  -- First-timer tracking
  first_event_date DATE,                 -- When they first played
  events_played_count INTEGER NOT NULL DEFAULT 0,

  -- Settings
  email_notifications BOOLEAN NOT NULL DEFAULT true,
  sms_notifications BOOLEAN NOT NULL DEFAULT false,

  -- Admin fields
  is_admin BOOLEAN NOT NULL DEFAULT false,
  is_chapter_manager BOOLEAN NOT NULL DEFAULT false,
  managed_chapter_ids UUID[] DEFAULT '{}',  -- Which chapters they manage

  notes TEXT,                            -- Internal notes (manager use)

  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_login_at TIMESTAMPTZ
);

-- Index for fast lookups
CREATE INDEX idx_members_email ON members(email);
CREATE INDEX idx_members_status ON members(status);
CREATE INDEX idx_members_stripe ON members(stripe_customer_id);

-- =============================================================================
-- TABLE: member_memberships
-- =============================================================================
-- Tracks the HISTORY of memberships.
-- Every time someone buys/renews, a new row is created.
-- This lets you see: when did they join? when did they renew? gaps in membership?
-- =============================================================================

CREATE TABLE member_memberships (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  member_id UUID NOT NULL REFERENCES members(id) ON DELETE CASCADE,
  membership_type_id UUID NOT NULL REFERENCES membership_types(id),

  -- When this membership was active
  starts_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,

  -- Payment info
  amount_paid DECIMAL(10,2) NOT NULL,
  transaction_id UUID,                   -- Link to transactions table

  -- Status
  is_active BOOLEAN NOT NULL DEFAULT true, -- Currently valid?
  cancelled_at TIMESTAMPTZ,              -- If they cancelled early
  cancellation_reason TEXT,

  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Now add the foreign key from members to member_memberships
ALTER TABLE members
  ADD CONSTRAINT fk_current_membership
  FOREIGN KEY (current_membership_id)
  REFERENCES member_memberships(id);

CREATE INDEX idx_member_memberships_member ON member_memberships(member_id);
CREATE INDEX idx_member_memberships_active ON member_memberships(is_active, expires_at);

-- =============================================================================
-- TABLE: games
-- =============================================================================
-- The different games/contests available.
-- Examples: NET Skins, GROSS Skins, CTP, etc.
-- =============================================================================

CREATE TABLE games (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  -- Basic info
  name VARCHAR(100) NOT NULL,            -- "NET Skins"
  short_name VARCHAR(20),                -- "NET" for compact display
  description TEXT,

  -- Pricing
  default_price DECIMAL(10,2) NOT NULL,

  -- Rules
  requires_membership BOOLEAN NOT NULL DEFAULT false, -- Only members can play?
  requires_ghin BOOLEAN NOT NULL DEFAULT false,       -- Need handicap?
  scoring_type VARCHAR(20),               -- 'net', 'gross', 'team', etc.

  -- Display
  is_active BOOLEAN NOT NULL DEFAULT true,
  display_order INTEGER NOT NULL DEFAULT 0,

  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert common games
INSERT INTO games (name, short_name, default_price, requires_membership, scoring_type, display_order) VALUES
  ('NET Skins', 'NET', 20.00, true, 'net', 1),
  ('GROSS Skins', 'GROSS', 20.00, false, 'gross', 2),
  ('Closest to Pin', 'CTP', 5.00, false, 'skill', 3),
  ('Long Drive', 'LD', 5.00, false, 'skill', 4);

-- =============================================================================
-- TABLE: events
-- =============================================================================
-- Your calendar of golf events.
-- This is where all the event details live.
-- =============================================================================

CREATE TABLE events (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  -- Which chapter runs this event?
  chapter_id UUID NOT NULL REFERENCES chapters(id),

  -- Basic info
  title VARCHAR(200) NOT NULL,           -- "Tuesday 9s at Canyon Springs"
  description TEXT,
  event_type VARCHAR(50) NOT NULL DEFAULT 'weekly', -- weekly, championship, special, social

  -- Course info
  course_name VARCHAR(200) NOT NULL,
  course_address TEXT,
  course_phone VARCHAR(20),
  course_website VARCHAR(255),
  course_notes TEXT,                      -- Dress code, cart policy, etc.

  -- Date/Time
  event_date DATE NOT NULL,
  start_time TIME NOT NULL,              -- Shotgun start time
  check_in_time TIME,                    -- When to arrive

  -- Capacity
  max_players INTEGER,                   -- NULL = unlimited
  min_players INTEGER DEFAULT 8,         -- Minimum to run event

  -- Registration
  registration_opens_at TIMESTAMPTZ,     -- When can people sign up?
  registration_closes_at TIMESTAMPTZ,    -- Deadline

  -- Pricing
  base_price DECIMAL(10,2) NOT NULL,     -- Base event fee
  member_price DECIMAL(10,2),            -- Member pays this (NULL = free for members)
  guest_surcharge DECIMAL(10,2) DEFAULT 10.00, -- Extra for non-members
  first_timer_discount DECIMAL(10,2) DEFAULT 25.00, -- Discount for first event ever

  -- Tax
  tax_rate DECIMAL(5,4) DEFAULT 0.0825,  -- 8.25% Texas sales tax

  -- Status
  status event_status NOT NULL DEFAULT 'draft',

  -- Waitlist
  waitlist_enabled BOOLEAN NOT NULL DEFAULT true,

  -- Flexible settings for future options
  settings JSONB DEFAULT '{}',

  -- Results (after event completes)
  results_published_at TIMESTAMPTZ,
  results_data JSONB,                    -- Store results flexibly

  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  published_at TIMESTAMPTZ,

  -- Who created/modified
  created_by_id UUID REFERENCES members(id),
  updated_by_id UUID REFERENCES members(id)
);

CREATE INDEX idx_events_chapter ON events(chapter_id);
CREATE INDEX idx_events_date ON events(event_date);
CREATE INDEX idx_events_status ON events(status);

-- =============================================================================
-- TABLE: event_games
-- =============================================================================
-- Links games to specific events.
-- Allows price overrides per event.
-- =============================================================================

CREATE TABLE event_games (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  game_id UUID NOT NULL REFERENCES games(id),

  -- Override the default price for this event?
  price_override DECIMAL(10,2),          -- NULL = use game's default price

  -- Is this game required for the event? (Usually false)
  is_mandatory BOOLEAN NOT NULL DEFAULT false,

  -- Display order for this event
  display_order INTEGER NOT NULL DEFAULT 0,

  -- Results for this game at this event
  results JSONB,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(event_id, game_id)
);

-- =============================================================================
-- TABLE: registrations
-- =============================================================================
-- Who's playing in what event.
-- This is the core of event management.
-- =============================================================================

CREATE TABLE registrations (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  member_id UUID NOT NULL REFERENCES members(id),

  -- Player type at time of registration
  player_type VARCHAR(20) NOT NULL,      -- 'member', 'guest', 'first_timer'

  -- Payment
  subtotal DECIMAL(10,2) NOT NULL,       -- Before tax
  tax_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
  total_amount DECIMAL(10,2) NOT NULL,   -- What they owe
  amount_paid DECIMAL(10,2) NOT NULL DEFAULT 0, -- What they've paid

  payment_status payment_status NOT NULL DEFAULT 'pending',

  -- How they paid
  payment_method VARCHAR(50),            -- 'stripe', 'wallet', 'cash', 'venmo', 'check', 'comp'
  stripe_payment_intent_id VARCHAR(255), -- For Stripe payments

  -- Wallet usage
  wallet_amount_used DECIMAL(10,2) DEFAULT 0, -- How much came from wallet

  -- Waitlist
  is_waitlisted BOOLEAN NOT NULL DEFAULT false,
  waitlist_position INTEGER,
  waitlist_promoted_at TIMESTAMPTZ,      -- When they got off waitlist

  -- Check-in
  checked_in_at TIMESTAMPTZ,
  checked_in_by_id UUID REFERENCES members(id),

  -- Cancellation
  cancelled_at TIMESTAMPTZ,
  cancellation_reason TEXT,
  refund_amount DECIMAL(10,2),

  -- Notes
  player_notes TEXT,                     -- Player can add notes
  manager_notes TEXT,                    -- Internal notes

  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Prevent duplicate registrations
  UNIQUE(event_id, member_id)
);

CREATE INDEX idx_registrations_event ON registrations(event_id);
CREATE INDEX idx_registrations_member ON registrations(member_id);
CREATE INDEX idx_registrations_status ON registrations(payment_status);

-- =============================================================================
-- TABLE: registration_games
-- =============================================================================
-- Which games each player selected for an event.
-- =============================================================================

CREATE TABLE registration_games (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  registration_id UUID NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
  event_game_id UUID NOT NULL REFERENCES event_games(id),

  -- Price at time of registration (in case prices change later)
  price_at_registration DECIMAL(10,2) NOT NULL,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE(registration_id, event_game_id)
);

-- =============================================================================
-- TABLE: transactions
-- =============================================================================
-- Complete financial audit trail.
-- Every dollar in or out is recorded here.
-- =============================================================================

CREATE TABLE transactions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  -- Who (nullable for system transactions)
  member_id UUID REFERENCES members(id),

  -- What type of transaction
  type transaction_type NOT NULL,

  -- Money
  amount DECIMAL(10,2) NOT NULL,         -- Positive = money in, Negative = money out

  -- Description for display
  description TEXT NOT NULL,

  -- Links to related records
  registration_id UUID REFERENCES registrations(id),
  membership_id UUID REFERENCES member_memberships(id),

  -- Stripe info
  stripe_payment_intent_id VARCHAR(255),
  stripe_charge_id VARCHAR(255),
  stripe_refund_id VARCHAR(255),

  -- Idempotency (prevents double-processing)
  idempotency_key VARCHAR(255) UNIQUE,

  -- Status
  status VARCHAR(20) NOT NULL DEFAULT 'completed', -- completed, pending, failed

  -- Metadata
  metadata JSONB DEFAULT '{}',

  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  processed_at TIMESTAMPTZ
);

CREATE INDEX idx_transactions_member ON transactions(member_id);
CREATE INDEX idx_transactions_type ON transactions(type);
CREATE INDEX idx_transactions_stripe ON transactions(stripe_payment_intent_id);

-- =============================================================================
-- TABLE: wallet_transactions
-- =============================================================================
-- Detailed wallet balance changes.
-- This gives a clear history of wallet activity.
-- =============================================================================

CREATE TABLE wallet_transactions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  member_id UUID NOT NULL REFERENCES members(id),

  -- Balance change
  amount DECIMAL(10,2) NOT NULL,         -- Positive = credit, Negative = debit
  balance_before DECIMAL(10,2) NOT NULL,
  balance_after DECIMAL(10,2) NOT NULL,

  -- What caused this change
  description TEXT NOT NULL,

  -- Links
  transaction_id UUID REFERENCES transactions(id),
  registration_id UUID REFERENCES registrations(id),

  -- Who made this change (for credits)
  created_by_id UUID REFERENCES members(id),

  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_wallet_transactions_member ON wallet_transactions(member_id);

-- =============================================================================
-- TABLE: audit_logs
-- =============================================================================
-- Track important changes for troubleshooting.
-- "Who changed what, when?"
-- =============================================================================

CREATE TABLE audit_logs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  -- Who made the change
  user_id UUID REFERENCES members(id),
  user_email VARCHAR(255),

  -- What was changed
  table_name VARCHAR(100) NOT NULL,
  record_id UUID NOT NULL,
  action VARCHAR(20) NOT NULL,           -- 'create', 'update', 'delete'

  -- The actual changes
  old_values JSONB,
  new_values JSONB,

  -- Context
  ip_address VARCHAR(45),
  user_agent TEXT,

  -- When
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_table ON audit_logs(table_name, record_id);
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id);

-- =============================================================================
-- TABLE: feature_flags
-- =============================================================================
-- Toggle features on/off without deploying code.
-- Great for gradual rollouts and testing.
-- =============================================================================

CREATE TABLE feature_flags (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

  key VARCHAR(100) NOT NULL UNIQUE,      -- 'wallet_enabled', 'season_contests'
  name VARCHAR(200) NOT NULL,            -- Human-readable name
  description TEXT,

  enabled BOOLEAN NOT NULL DEFAULT false,

  -- Optional: Enable only for specific members
  enabled_for_member_ids UUID[] DEFAULT '{}',

  -- Optional: Enable only for specific chapters
  enabled_for_chapter_ids UUID[] DEFAULT '{}',

  metadata JSONB DEFAULT '{}',

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert initial feature flags
INSERT INTO feature_flags (key, name, description, enabled) VALUES
  ('wallet_system', 'Wallet/Credits System', 'Allow members to maintain a wallet balance for payments', true),
  ('guest_registration', 'Guest Registration', 'Allow non-members to register for events', true),
  ('waitlist', 'Waitlist System', 'Enable waitlist when events are full', true),
  ('season_contests', 'Season Contests', 'Points races and season-long competitions', false);

-- =============================================================================
-- FUNCTIONS: Auto-update timestamps
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply to all tables with updated_at
CREATE TRIGGER update_chapters_updated_at BEFORE UPDATE ON chapters FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_membership_types_updated_at BEFORE UPDATE ON membership_types FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_members_updated_at BEFORE UPDATE ON members FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_member_memberships_updated_at BEFORE UPDATE ON member_memberships FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_games_updated_at BEFORE UPDATE ON games FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_events_updated_at BEFORE UPDATE ON events FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_registrations_updated_at BEFORE UPDATE ON registrations FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_feature_flags_updated_at BEFORE UPDATE ON feature_flags FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- ROW LEVEL SECURITY (RLS)
-- =============================================================================
-- These policies control who can see and modify what data.
-- This is Supabase's way of securing data at the database level.
-- =============================================================================

-- Enable RLS on all tables
ALTER TABLE chapters ENABLE ROW LEVEL SECURITY;
ALTER TABLE membership_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE members ENABLE ROW LEVEL SECURITY;
ALTER TABLE member_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE games ENABLE ROW LEVEL SECURITY;
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE event_games ENABLE ROW LEVEL SECURITY;
ALTER TABLE registrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE registration_games ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE wallet_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE feature_flags ENABLE ROW LEVEL SECURITY;

-- PUBLIC READ policies (anyone can see these)
CREATE POLICY "Chapters are viewable by everyone" ON chapters FOR SELECT USING (true);
CREATE POLICY "Active membership types are viewable by everyone" ON membership_types FOR SELECT USING (is_active = true);
CREATE POLICY "Active games are viewable by everyone" ON games FOR SELECT USING (is_active = true);
CREATE POLICY "Published events are viewable by everyone" ON events FOR SELECT USING (status != 'draft');
CREATE POLICY "Event games for published events are viewable" ON event_games FOR SELECT USING (
  EXISTS (SELECT 1 FROM events WHERE events.id = event_games.event_id AND events.status != 'draft')
);
CREATE POLICY "Feature flags are viewable by everyone" ON feature_flags FOR SELECT USING (true);

-- MEMBER policies (logged-in users)
CREATE POLICY "Members can view their own profile" ON members FOR SELECT USING (auth.uid() = auth_user_id);
CREATE POLICY "Members can update their own profile" ON members FOR UPDATE USING (auth.uid() = auth_user_id);
CREATE POLICY "Members can view their own memberships" ON member_memberships FOR SELECT USING (
  member_id IN (SELECT id FROM members WHERE auth_user_id = auth.uid())
);
CREATE POLICY "Members can view their own registrations" ON registrations FOR SELECT USING (
  member_id IN (SELECT id FROM members WHERE auth_user_id = auth.uid())
);
CREATE POLICY "Members can view their own transactions" ON transactions FOR SELECT USING (
  member_id IN (SELECT id FROM members WHERE auth_user_id = auth.uid())
);
CREATE POLICY "Members can view their own wallet transactions" ON wallet_transactions FOR SELECT USING (
  member_id IN (SELECT id FROM members WHERE auth_user_id = auth.uid())
);

-- ADMIN policies (full access for admins)
-- These use service role key, so admins bypass RLS through the API

-- =============================================================================
-- DONE!
-- =============================================================================
-- Your database is now ready for the TGF Platform MVP.
-- =============================================================================
