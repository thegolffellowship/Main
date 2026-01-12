-- =============================================================================
-- TGF PLATFORM - MVP SCHEMA
-- =============================================================================
-- This is the SIMPLIFIED schema for MVP launch.
-- Only includes tables we'll actually use on day one.
--
-- The comprehensive schema (00002_comprehensive_schema.sql) is our blueprint
-- for the future. This file is what we'll actually deploy for launch.
-- =============================================================================

-- =============================================================================
-- TABLE 1: organizations
-- =============================================================================
-- PURPOSE: Your chapters (San Antonio, Austin, etc.)
--
-- For MVP, we're just using this for chapters. The hierarchy features
-- (regions, countries) exist in the comprehensive schema for later.
--
-- KERRY: Do you need any other info stored about chapters?
-- =============================================================================

CREATE TABLE organizations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Basic info
  name VARCHAR(100) NOT NULL,             -- "San Antonio"
  code VARCHAR(20) NOT NULL UNIQUE,       -- "SA" (short code for URLs, reports)

  -- Location
  city VARCHAR(100),                      -- "San Antonio"
  state VARCHAR(50) DEFAULT 'Texas',
  timezone VARCHAR(50) DEFAULT 'America/Chicago',

  -- For future hierarchy (not used in MVP, but column exists)
  parent_id UUID REFERENCES organizations(id),

  -- Settings that can vary per chapter
  settings JSONB DEFAULT '{}',
  /*
    MVP settings we might use:
    {
      "default_tax_rate": 0.0825,
      "late_fee_amount": 10.00,
      "late_fee_cutoff_hours": 48
    }
  */

  -- Status
  is_active BOOLEAN DEFAULT true,

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert your chapters
INSERT INTO organizations (name, code, city) VALUES
  ('San Antonio', 'SA', 'San Antonio'),
  ('Austin', 'AUS', 'Austin');


-- =============================================================================
-- TABLE 2: users
-- =============================================================================
-- PURPOSE: Every person in the system
--
-- This replaces "members" because not everyone is a member.
-- Includes: players, guests, prospects, managers, course contacts
--
-- KERRY:
-- - What other info do you collect about people?
-- - Do you track anything else about first-timers?
-- - Any other contact info (social media, etc.)?
-- =============================================================================

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Links to Supabase Auth (for login)
  auth_user_id UUID UNIQUE,

  -- Basic info
  email VARCHAR(255) NOT NULL UNIQUE,
  first_name VARCHAR(100) NOT NULL,
  last_name VARCHAR(100) NOT NULL,
  phone VARCHAR(20),

  -- Golf info
  ghin_number VARCHAR(20),                -- Their USGA handicap number
  current_handicap DECIMAL(4,1),          -- We'll track our own too

  -- Home chapter preference
  home_organization_id UUID REFERENCES organizations(id),

  -- Status: Where are they in their TGF journey?
  status VARCHAR(30) DEFAULT 'prospect',
  /*
    Values:
    - 'prospect'        = Signed up but never played or joined
    - 'guest'           = Has played but never been a member
    - 'active_member'   = Currently paid membership
    - 'expired_member'  = Was a member, membership lapsed
    - 'former_member'   = Explicitly cancelled/left
  */

  -- Current membership (denormalized for quick lookups)
  membership_expires_at TIMESTAMPTZ,

  -- Wallet balance (for credits, winnings, prepayment)
  wallet_balance DECIMAL(10,2) DEFAULT 0.00,

  -- Stripe customer ID (for saved payment methods)
  stripe_customer_id VARCHAR(255),

  -- Activity tracking
  first_event_date DATE,                  -- When they first played with TGF
  last_event_date DATE,                   -- Most recent event
  total_events_played INTEGER DEFAULT 0,  -- Lifetime count

  -- Preferences (for smart autofill during registration)
  preferences JSONB DEFAULT '{}',
  /*
    {
      "tee_preference": "50-64",
      "fellowship_after": true,
      "dietary_restrictions": "vegetarian"
    }
  */

  -- Notification settings
  email_notifications BOOLEAN DEFAULT true,
  sms_notifications BOOLEAN DEFAULT false,

  -- Admin flags
  is_admin BOOLEAN DEFAULT false,         -- Kerry = true
  is_manager BOOLEAN DEFAULT false,       -- Chapter managers
  managed_organization_ids UUID[],        -- Which chapters they manage

  -- Internal notes (manager use only, player doesn't see)
  notes TEXT,

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  last_login_at TIMESTAMPTZ,

  -- Soft delete (don't lose history)
  deleted_at TIMESTAMPTZ
);

-- Indexes for fast lookups
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_home_org ON users(home_organization_id);


-- =============================================================================
-- TABLE 3: membership_types
-- =============================================================================
-- PURPOSE: The membership products you sell
--
-- Currently just "Annual Membership" at $300
-- But this allows you to add others later (founding member, etc.)
--
-- KERRY:
-- - Do you have different membership tiers or prices?
-- - Any legacy/grandfathered pricing?
-- - Different durations (6-month, etc.)?
-- =============================================================================

CREATE TABLE membership_types (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Basic info
  name VARCHAR(100) NOT NULL,             -- "Annual Membership"
  description TEXT,                       -- What's included

  -- Pricing
  price DECIMAL(10,2) NOT NULL,           -- 300.00
  duration_months INTEGER NOT NULL,       -- 12

  -- Is this available for purchase?
  is_active BOOLEAN DEFAULT true,
  is_publicly_available BOOLEAN DEFAULT true,  -- Show on website?

  -- Display order (for listing multiple types)
  display_order INTEGER DEFAULT 0,

  -- What benefits does this membership include?
  benefits JSONB DEFAULT '{}',
  /*
    {
      "all_chapters": true,
      "net_games_included": true,
      "season_contests_eligible": true
    }
  */

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert your membership
INSERT INTO membership_types (name, description, price, duration_months, benefits) VALUES
  ('Annual Membership',
   'Full TGF membership with access to all chapters, member pricing on events, and eligibility for NET games and season contests.',
   300.00,
   12,
   '{"all_chapters": true, "net_games_included": true, "season_contests_eligible": true}');


-- =============================================================================
-- TABLE 4: user_memberships
-- =============================================================================
-- PURPOSE: Track membership purchase HISTORY
--
-- Every time someone buys or renews, a new row is created.
-- This lets you see:
-- - When did they first join?
-- - Have they renewed every year?
-- - Any gaps in membership?
--
-- KERRY:
-- - Do you track HOW they heard about TGF when they join?
-- - Any referral tracking?
-- =============================================================================

CREATE TABLE user_memberships (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Who and what type
  user_id UUID NOT NULL REFERENCES users(id),
  membership_type_id UUID NOT NULL REFERENCES membership_types(id),

  -- When active
  starts_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,

  -- Payment
  amount_paid DECIMAL(10,2) NOT NULL,     -- What they actually paid
  transaction_id UUID,                    -- Link to transactions table

  -- Status
  is_active BOOLEAN DEFAULT true,

  -- If cancelled early
  cancelled_at TIMESTAMPTZ,
  cancellation_reason TEXT,

  -- Auto-renewal preference
  auto_renew BOOLEAN DEFAULT false,

  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_user_memberships_user ON user_memberships(user_id);


-- =============================================================================
-- TABLE 5: courses
-- =============================================================================
-- PURPOSE: Golf courses where you hold events
--
-- Stores course info, your negotiated rates, and policies.
--
-- KERRY:
-- - What other course info do you need to track?
-- - Do you track course contact people here or separately?
-- - Any course-specific policies we need?
-- =============================================================================

CREATE TABLE courses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Basic info
  name VARCHAR(200) NOT NULL,             -- "Canyon Springs Golf Club"

  -- Location
  address TEXT,
  city VARCHAR(100),
  state VARCHAR(50) DEFAULT 'Texas',
  zip VARCHAR(20),

  -- Contact
  phone VARCHAR(20),
  email VARCHAR(255),
  website TEXT,

  -- Primary contact person at the course
  contact_name VARCHAR(200),
  contact_phone VARCHAR(20),
  contact_email VARCHAR(255),

  -- Course data
  holes INTEGER DEFAULT 18,
  par INTEGER,

  -- Standard rates (what public pays)
  standard_rates JSONB DEFAULT '{}',
  /*
    {
      "weekday_9": 35.00,
      "weekday_18": 55.00,
      "weekend_9": 45.00,
      "weekend_18": 70.00,
      "twilight": 30.00,
      "cart_included": true
    }
  */

  -- TGF contracted rates (what you pay)
  tgf_rates JSONB DEFAULT '{}',
  /*
    {
      "rate_9": 25.00,
      "rate_18": 40.00,
      "cart_included": true,
      "range_included": false,
      "valid_until": "2025-12-31"
    }
  */

  -- Policies
  cancellation_notice_hours INTEGER DEFAULT 48,
  minimum_players INTEGER,                -- Minimum guaranteed?
  payment_terms VARCHAR(50),              -- "net_30", "due_on_play"

  -- Notes
  notes TEXT,                             -- Internal notes
  dress_code TEXT,                        -- Player-facing info
  special_instructions TEXT,              -- Player-facing info

  -- Status
  is_active BOOLEAN DEFAULT true,

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);


-- =============================================================================
-- TABLE 6: games
-- =============================================================================
-- PURPOSE: The different contests/games you offer
--
-- Examples: Team MVP, CTP, Skins, Individual Net, etc.
-- Each game has its own pricing and rules.
--
-- KERRY:
-- - List all the games you currently offer
-- - Which require membership?
-- - What are the prices for 9 vs 18?
-- - Any games I'm missing?
-- =============================================================================

CREATE TABLE games (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Basic info
  name VARCHAR(100) NOT NULL,             -- "Team MVP"
  short_name VARCHAR(20),                 -- "MVP" (for compact display)
  description TEXT,

  -- Type of game
  game_type VARCHAR(30) NOT NULL,
  /*
    Values:
    - 'team'           = Team-based (Team MVP)
    - 'individual_net' = Individual net scoring
    - 'individual_gross' = Individual gross scoring
    - 'skins'          = Skins game
    - 'skill_contest'  = CTP, Long Drive
    - 'pot'            = Hole-in-One pot (accumulates)
  */

  -- Requirements
  requires_membership BOOLEAN DEFAULT false,
  requires_ghin BOOLEAN DEFAULT false,

  -- Default pricing (can be overridden per event)
  default_price_9 DECIMAL(10,2) DEFAULT 0,   -- Price for 9-hole events
  default_price_18 DECIMAL(10,2) DEFAULT 0,  -- Price for 18-hole events

  -- Cost structure (what goes to prize pool vs TGF)
  default_cost_9 DECIMAL(10,2) DEFAULT 0,    -- Prize pool portion
  default_cost_18 DECIMAL(10,2) DEFAULT 0,
  -- (Price minus Cost = TGF markup)

  -- Is this typically included free with event entry?
  typically_included BOOLEAN DEFAULT false,

  -- Display order
  display_order INTEGER DEFAULT 0,
  is_active BOOLEAN DEFAULT true,

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert your standard games
INSERT INTO games (name, short_name, game_type, requires_membership, typically_included, default_price_9, default_price_18, display_order) VALUES
  -- Included games (no extra charge)
  ('Team MVP', 'Team MVP', 'team', false, true, 0, 0, 1),
  ('Closest to Pin', 'CTP', 'skill_contest', false, true, 0, 0, 2),
  ('Hole-in-One Pot', 'HIO', 'pot', false, true, 0, 0, 3),

  -- NET games (members only)
  ('Individual Net', 'Ind Net', 'individual_net', true, false, 10.00, 15.00, 4),
  ('Net Skins', 'Net Skins', 'skins', true, false, 10.00, 15.00, 5),

  -- GROSS games (open to all)
  ('Individual Gross', 'Ind Gross', 'individual_gross', false, false, 10.00, 15.00, 6),
  ('Gross Skins', 'Gross Skins', 'skins', false, false, 10.00, 15.00, 7),

  -- Other
  ('Long Drive', 'LD', 'skill_contest', false, false, 5.00, 5.00, 8);


-- =============================================================================
-- TABLE 7: bundles
-- =============================================================================
-- PURPOSE: Game bundles (like "NET Games" package)
--
-- A bundle is a package of multiple games sold together at a discount.
--
-- KERRY:
-- - What bundles do you currently offer?
-- - What's the pricing for each?
-- - Any other bundle options?
-- =============================================================================

CREATE TABLE bundles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Basic info
  name VARCHAR(100) NOT NULL,             -- "NET Games"
  short_name VARCHAR(20),                 -- "NET"
  description TEXT,                       -- "Includes Individual Net and Net Skins"

  -- Requirements
  requires_membership BOOLEAN DEFAULT false,

  -- Pricing
  default_price_9 DECIMAL(10,2) NOT NULL,
  default_price_18 DECIMAL(10,2) NOT NULL,

  -- Cost (prize pool portion)
  default_cost_9 DECIMAL(10,2) DEFAULT 0,
  default_cost_18 DECIMAL(10,2) DEFAULT 0,

  display_order INTEGER DEFAULT 0,
  is_active BOOLEAN DEFAULT true,

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert your bundles
INSERT INTO bundles (name, short_name, description, requires_membership, default_price_9, default_price_18, default_cost_9, default_cost_18, display_order) VALUES
  ('NET Games', 'NET', 'Includes Individual Net and Net Skins', true, 15.00, 25.00, 12.00, 20.00, 1),
  ('GROSS Games', 'GROSS', 'Includes Individual Gross and Gross Skins', false, 15.00, 25.00, 12.00, 20.00, 2);


-- =============================================================================
-- TABLE 8: bundle_games
-- =============================================================================
-- PURPOSE: Which games are in each bundle
--
-- Links games to bundles (many-to-many relationship)
-- =============================================================================

CREATE TABLE bundle_games (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  bundle_id UUID NOT NULL REFERENCES bundles(id) ON DELETE CASCADE,
  game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,

  display_order INTEGER DEFAULT 0,

  UNIQUE(bundle_id, game_id)
);

-- Link NET bundle to its games
INSERT INTO bundle_games (bundle_id, game_id, display_order)
SELECT b.id, g.id,
  CASE g.short_name
    WHEN 'Ind Net' THEN 1
    WHEN 'Net Skins' THEN 2
  END
FROM bundles b, games g
WHERE b.short_name = 'NET' AND g.short_name IN ('Ind Net', 'Net Skins');

-- Link GROSS bundle to its games
INSERT INTO bundle_games (bundle_id, game_id, display_order)
SELECT b.id, g.id,
  CASE g.short_name
    WHEN 'Ind Gross' THEN 1
    WHEN 'Gross Skins' THEN 2
  END
FROM bundles b, games g
WHERE b.short_name = 'GROSS' AND g.short_name IN ('Ind Gross', 'Gross Skins');


-- =============================================================================
-- TABLE 9: events
-- =============================================================================
-- PURPOSE: Your calendar of golf events
--
-- This is where all event details live.
--
-- KERRY:
-- - What other info do you need to capture per event?
-- - Any special event types with different rules?
-- - What notifications go out and when?
-- =============================================================================

CREATE TABLE events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Which chapter hosts this?
  organization_id UUID NOT NULL REFERENCES organizations(id),

  -- Where?
  course_id UUID REFERENCES courses(id),

  -- Basic info
  title VARCHAR(200) NOT NULL,            -- "Tuesday 9s at Canyon Springs"
  description TEXT,

  -- Event type
  event_type VARCHAR(30) DEFAULT '9_hole',
  /*
    Values:
    - '9_hole'        = Standard 9-hole event
    - '18_hole'       = Standard 18-hole event
    - 'championship'  = Championship event
    - 'scramble'      = Team scramble
    - 'social'        = Social event (no golf)
  */

  -- Date/Time
  event_date DATE NOT NULL,
  start_time TIME NOT NULL,               -- Shotgun/tee time
  check_in_time TIME,                     -- When to arrive

  -- Capacity
  max_players INTEGER,                    -- NULL = unlimited
  min_players INTEGER DEFAULT 8,          -- Minimum to run event

  -- Registration windows
  registration_opens_at TIMESTAMPTZ,
  registration_closes_at TIMESTAMPTZ,

  -- Late fee settings
  late_fee_enabled BOOLEAN DEFAULT false,
  late_fee_amount DECIMAL(10,2),
  late_fee_after TIMESTAMPTZ,             -- When does late fee kick in?

  -- Status
  status VARCHAR(30) DEFAULT 'draft',
  /*
    Values:
    - 'draft'               = Being set up, not visible
    - 'published'           = Open for registration
    - 'registration_closed' = Past deadline
    - 'completed'           = Event finished
    - 'cancelled'           = Event cancelled
  */

  -- Waitlist
  waitlist_enabled BOOLEAN DEFAULT true,

  -- Flexible settings
  settings JSONB DEFAULT '{}',

  -- Who created/modified
  created_by_id UUID REFERENCES users(id),

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  published_at TIMESTAMPTZ,
  cancelled_at TIMESTAMPTZ,
  cancellation_reason TEXT,

  -- Soft delete
  deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_events_org ON events(organization_id);
CREATE INDEX idx_events_date ON events(event_date);
CREATE INDEX idx_events_status ON events(status);


-- =============================================================================
-- TABLE 10: event_pricing
-- =============================================================================
-- PURPOSE: Pricing breakdown per player type for each event
--
-- This tracks:
-- - What the player pays
-- - What goes to the course
-- - What TGF keeps (markup)
-- - Tax
--
-- KERRY:
-- - What's your typical markup on events?
-- - Different for 9 vs 18?
-- - Any other fees we need to track?
-- =============================================================================

CREATE TABLE event_pricing (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,

  -- Which player type is this pricing for?
  player_type VARCHAR(30) NOT NULL,       -- 'member', 'guest', 'first_timer'

  -- Price breakdown
  base_price DECIMAL(10,2) NOT NULL,      -- What player pays (before tax)
  course_cost DECIMAL(10,2) NOT NULL,     -- What TGF pays course
  tgf_markup DECIMAL(10,2) NOT NULL,      -- TGF keeps this
  -- Note: base_price should = course_cost + tgf_markup

  -- Tax
  is_taxable BOOLEAN DEFAULT true,
  tax_rate DECIMAL(5,4) DEFAULT 0.0825,   -- 8.25%

  -- Any discount applied
  discount_amount DECIMAL(10,2) DEFAULT 0,
  discount_description VARCHAR(200),       -- "First-timer discount"

  created_at TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE(event_id, player_type)
);


-- =============================================================================
-- TABLE 11: event_games
-- =============================================================================
-- PURPOSE: Which games/bundles are available at each event
--
-- Links events to games and bundles with optional price overrides.
-- =============================================================================

CREATE TABLE event_games (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,

  -- Either a game OR a bundle (not both)
  game_id UUID REFERENCES games(id),
  bundle_id UUID REFERENCES bundles(id),
  CHECK ((game_id IS NOT NULL AND bundle_id IS NULL) OR (game_id IS NULL AND bundle_id IS NOT NULL)),

  -- Is this included free with registration?
  is_included BOOLEAN DEFAULT false,

  -- Price override for this event (NULL = use default)
  price_override DECIMAL(10,2),
  cost_override DECIMAL(10,2),

  display_order INTEGER DEFAULT 0,

  created_at TIMESTAMPTZ DEFAULT NOW(),

  -- Prevent duplicates
  UNIQUE(event_id, game_id),
  UNIQUE(event_id, bundle_id)
);


-- =============================================================================
-- TABLE 12: registrations
-- =============================================================================
-- PURPOSE: Who's signed up for which event
--
-- This is the core table for tracking event signups.
-- Contains all payment and status info.
--
-- KERRY:
-- - What other info do you collect during registration?
-- - Any special statuses we need?
-- =============================================================================

CREATE TABLE registrations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id),

  -- Player type at time of registration
  player_type VARCHAR(30) NOT NULL,       -- 'member', 'guest', 'first_timer'

  -- === PRICING (captured at time of registration) ===
  subtotal DECIMAL(10,2) NOT NULL,        -- Base + games, before tax
  tax_amount DECIMAL(10,2) DEFAULT 0,
  late_fee_amount DECIMAL(10,2) DEFAULT 0,
  discount_amount DECIMAL(10,2) DEFAULT 0,
  total_amount DECIMAL(10,2) NOT NULL,    -- Final amount owed

  -- === PAYMENT ===
  amount_paid DECIMAL(10,2) DEFAULT 0,    -- What they've paid so far

  payment_status VARCHAR(30) DEFAULT 'pending',
  /*
    Values:
    - 'pending'       = Registered, not paid
    - 'paid'          = Fully paid
    - 'partial'       = Partially paid
    - 'refunded'      = Refund issued
    - 'comped'        = Free (manager comp)
  */

  payment_method VARCHAR(30),
  /*
    Values:
    - 'stripe'        = Credit card via Stripe
    - 'wallet'        = Paid from wallet balance
    - 'split'         = Part wallet, part card
    - 'cash'          = Cash at course
    - 'venmo'         = Venmo
    - 'check'         = Check
    - 'comp'          = Comped by manager
  */

  -- Stripe tracking
  stripe_payment_intent_id VARCHAR(255),

  -- Wallet usage
  wallet_amount_used DECIMAL(10,2) DEFAULT 0,

  -- === WAITLIST ===
  is_waitlisted BOOLEAN DEFAULT false,
  waitlist_position INTEGER,
  waitlist_promoted_at TIMESTAMPTZ,

  -- === CHECK-IN ===
  checked_in_at TIMESTAMPTZ,
  checked_in_by_id UUID REFERENCES users(id),

  -- === CANCELLATION ===
  cancelled_at TIMESTAMPTZ,
  cancellation_reason TEXT,
  refund_amount DECIMAL(10,2),
  refund_to VARCHAR(30),                  -- 'original', 'wallet'

  -- === REGISTRATION RESPONSES ===
  responses JSONB DEFAULT '{}',
  /*
    {
      "tee_preference": "50-64",
      "playing_partner_request": "John Smith",
      "fellowship_after": true,
      "special_requests": "Need cart with hand controls"
    }
  */

  -- Notes
  player_notes TEXT,                      -- Player can add
  manager_notes TEXT,                     -- Manager internal notes

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  -- Prevent duplicate registrations
  UNIQUE(event_id, user_id)
);

CREATE INDEX idx_registrations_event ON registrations(event_id);
CREATE INDEX idx_registrations_user ON registrations(user_id);
CREATE INDEX idx_registrations_status ON registrations(payment_status);


-- =============================================================================
-- TABLE 13: registration_games
-- =============================================================================
-- PURPOSE: Which games/bundles each player selected
--
-- When someone registers and adds NET Games bundle, a row goes here.
-- =============================================================================

CREATE TABLE registration_games (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  registration_id UUID NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
  event_game_id UUID NOT NULL REFERENCES event_games(id),

  -- Price at time of registration (in case prices change later)
  price DECIMAL(10,2) NOT NULL,
  cost DECIMAL(10,2) NOT NULL,            -- Prize pool portion

  created_at TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE(registration_id, event_game_id)
);


-- =============================================================================
-- TABLE 14: transactions
-- =============================================================================
-- PURPOSE: Every financial transaction in the system
--
-- This is your complete money trail. Every dollar in or out.
-- Used for reporting, reconciliation, tax filing.
--
-- KERRY:
-- - What categories do you need for reporting?
-- - How do you currently categorize income/expenses?
-- =============================================================================

CREATE TABLE transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Who (can be null for system transactions)
  user_id UUID REFERENCES users(id),

  -- What type
  type VARCHAR(50) NOT NULL,
  /*
    Values:
    - 'membership_purchase'
    - 'membership_renewal'
    - 'event_registration'
    - 'game_addon'
    - 'late_fee'
    - 'wallet_deposit'
    - 'wallet_credit'        (winnings added)
    - 'wallet_payout'        (winnings paid out)
    - 'refund'
    - 'adjustment'
  */

  -- Money amount (positive = money in, negative = money out)
  amount DECIMAL(10,2) NOT NULL,

  -- Breakdown
  revenue_amount DECIMAL(10,2),           -- TGF revenue portion
  cost_amount DECIMAL(10,2),              -- Cost portion (course, prizes)
  tgf_profit DECIMAL(10,2),               -- TGF profit (markup)
  tax_amount DECIMAL(10,2),               -- Sales tax

  -- Description
  description TEXT NOT NULL,              -- "Registration for Tuesday 9s"

  -- Links to related records
  registration_id UUID REFERENCES registrations(id),
  membership_id UUID REFERENCES user_memberships(id),
  event_id UUID REFERENCES events(id),

  -- Stripe tracking
  stripe_payment_intent_id VARCHAR(255),
  stripe_charge_id VARCHAR(255),
  stripe_refund_id VARCHAR(255),

  -- Prevent double-processing
  idempotency_key VARCHAR(255) UNIQUE,

  -- Status
  status VARCHAR(30) DEFAULT 'completed',
  /*
    Values:
    - 'pending'       = Payment in progress
    - 'completed'     = Success
    - 'failed'        = Payment failed
    - 'refunded'      = Refunded
  */

  -- Extra data
  metadata JSONB DEFAULT '{}',

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  processed_at TIMESTAMPTZ,

  -- Soft delete
  deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_transactions_user ON transactions(user_id);
CREATE INDEX idx_transactions_type ON transactions(type);
CREATE INDEX idx_transactions_event ON transactions(event_id);
CREATE INDEX idx_transactions_date ON transactions(created_at);


-- =============================================================================
-- TABLE 15: wallet_transactions
-- =============================================================================
-- PURPOSE: Detailed wallet balance changes
--
-- Every time a wallet balance changes, record it here.
-- This gives complete history for disputes, audits.
-- =============================================================================

CREATE TABLE wallet_transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  user_id UUID NOT NULL REFERENCES users(id),

  -- Change amount
  amount DECIMAL(10,2) NOT NULL,          -- Positive = credit, Negative = debit

  -- Balance tracking
  balance_before DECIMAL(10,2) NOT NULL,
  balance_after DECIMAL(10,2) NOT NULL,

  -- What caused this
  description TEXT NOT NULL,              -- "Won CTP - Tuesday 9s Jan 21"

  source VARCHAR(50) NOT NULL,
  /*
    Values:
    - 'deposit'       = Added funds
    - 'payment'       = Used for registration
    - 'winnings'      = Game winnings credited
    - 'refund'        = Refund credited
    - 'adjustment'    = Manual adjustment
    - 'payout'        = Funds withdrawn
  */

  -- Links
  transaction_id UUID REFERENCES transactions(id),
  registration_id UUID REFERENCES registrations(id),
  event_id UUID REFERENCES events(id),

  -- Who made this change (for adjustments)
  created_by_id UUID REFERENCES users(id),

  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_wallet_trans_user ON wallet_transactions(user_id);
CREATE INDEX idx_wallet_trans_date ON wallet_transactions(created_at);


-- =============================================================================
-- TABLE 16: event_financial_summary
-- =============================================================================
-- PURPOSE: Pre-calculated financial totals per event
--
-- Makes reporting fast. Updated after each registration/change.
-- =============================================================================

CREATE TABLE event_financial_summary (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,

  -- Counts
  total_registrations INTEGER DEFAULT 0,
  member_count INTEGER DEFAULT 0,
  guest_count INTEGER DEFAULT 0,
  first_timer_count INTEGER DEFAULT 0,

  -- Revenue
  total_revenue DECIMAL(10,2) DEFAULT 0,
  registration_revenue DECIMAL(10,2) DEFAULT 0,
  addon_revenue DECIMAL(10,2) DEFAULT 0,
  late_fee_revenue DECIMAL(10,2) DEFAULT 0,

  -- Costs
  course_cost DECIMAL(10,2) DEFAULT 0,
  prize_pool DECIMAL(10,2) DEFAULT 0,
  total_cost DECIMAL(10,2) DEFAULT 0,

  -- Profit
  tgf_markup_total DECIMAL(10,2) DEFAULT 0,
  gross_profit DECIMAL(10,2) DEFAULT 0,

  -- Tax
  sales_tax_collected DECIMAL(10,2) DEFAULT 0,

  -- Net
  net_profit DECIMAL(10,2) DEFAULT 0,

  -- Last calculated
  calculated_at TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE(event_id)
);


-- =============================================================================
-- TABLE 17: audit_logs (simplified for MVP)
-- =============================================================================
-- PURPOSE: Track important changes for troubleshooting
--
-- "Who changed what, when?"
-- =============================================================================

CREATE TABLE audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Who made the change
  user_id UUID REFERENCES users(id),
  user_email VARCHAR(255),

  -- What was changed
  table_name VARCHAR(100) NOT NULL,
  record_id UUID NOT NULL,
  action VARCHAR(20) NOT NULL,            -- 'create', 'update', 'delete'

  -- The changes
  old_values JSONB,
  new_values JSONB,

  -- When
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_table ON audit_logs(table_name, record_id);


-- =============================================================================
-- TABLE 18: feature_flags
-- =============================================================================
-- PURPOSE: Toggle features on/off without code changes
--
-- Useful for gradual rollout or quick disable if something breaks.
-- =============================================================================

CREATE TABLE feature_flags (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  key VARCHAR(100) NOT NULL UNIQUE,       -- 'wallet_enabled'
  name VARCHAR(200) NOT NULL,             -- "Wallet System"
  description TEXT,

  enabled BOOLEAN DEFAULT false,

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- MVP feature flags
INSERT INTO feature_flags (key, name, description, enabled) VALUES
  ('wallet_system', 'Wallet System', 'Allow wallet balances and credits', true),
  ('guest_registration', 'Guest Registration', 'Allow non-members to register', true),
  ('waitlist', 'Waitlist', 'Enable waitlist when events are full', true),
  ('late_fees', 'Late Fees', 'Charge late fees after deadline', true),
  ('stripe_payments', 'Stripe Payments', 'Accept credit card payments', true);


-- =============================================================================
-- AUTOMATIC TIMESTAMP UPDATES
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to tables with updated_at
CREATE TRIGGER update_users_timestamp BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_organizations_timestamp BEFORE UPDATE ON organizations FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_membership_types_timestamp BEFORE UPDATE ON membership_types FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_courses_timestamp BEFORE UPDATE ON courses FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_games_timestamp BEFORE UPDATE ON games FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_bundles_timestamp BEFORE UPDATE ON bundles FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_events_timestamp BEFORE UPDATE ON events FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_registrations_timestamp BEFORE UPDATE ON registrations FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- =============================================================================
-- MVP SCHEMA COMPLETE
-- =============================================================================
--
-- Tables created (18 total):
--
-- CORE:
--   1. organizations        - Chapters
--   2. users               - All people
--   3. membership_types    - Membership products
--   4. user_memberships    - Membership history
--   5. courses             - Golf courses
--
-- GAMES:
--   6. games               - Individual games
--   7. bundles             - Game bundles
--   8. bundle_games        - Games in bundles
--
-- EVENTS:
--   9. events              - Calendar
--   10. event_pricing      - Price per player type
--   11. event_games        - Games at each event
--
-- REGISTRATIONS:
--   12. registrations      - Who's signed up
--   13. registration_games - Games they selected
--
-- FINANCIAL:
--   14. transactions       - All money movement
--   15. wallet_transactions - Wallet history
--   16. event_financial_summary - Event totals
--
-- SYSTEM:
--   17. audit_logs         - Change tracking
--   18. feature_flags      - Feature toggles
--
-- =============================================================================
