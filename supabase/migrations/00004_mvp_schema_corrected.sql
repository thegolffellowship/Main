-- =============================================================================
-- TGF PLATFORM - MVP SCHEMA (CORRECTED)
-- =============================================================================
-- Version: 2.0
-- Date: January 2026
--
-- This version incorporates Kerry's corrections:
-- - Correct membership tiers (Standard $75, TGF Plus $200)
-- - Correct game pricing (100% to prize pool)
-- - Correct bundle pricing with TGF markup
-- - Tee configurations with gender/age rules
-- - Stripe fee pass-through on total
-- - Price version tracking
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- TABLE 1: organizations
-- =============================================================================
-- PURPOSE: Your chapters (San Antonio, Austin, etc.)
-- =============================================================================

CREATE TABLE organizations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Basic info
  name VARCHAR(100) NOT NULL,             -- "San Antonio"
  code VARCHAR(20) NOT NULL UNIQUE,       -- "SA" (short code)

  -- Location
  city VARCHAR(100),
  state VARCHAR(50) DEFAULT 'Texas',
  timezone VARCHAR(50) DEFAULT 'America/Chicago',

  -- For future hierarchy
  parent_id UUID REFERENCES organizations(id),

  -- Settings
  settings JSONB DEFAULT '{}',

  -- Status
  is_active BOOLEAN DEFAULT true,

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert chapters
INSERT INTO organizations (name, code, city) VALUES
  ('San Antonio', 'SA', 'San Antonio'),
  ('Austin', 'AUS', 'Austin');


-- =============================================================================
-- TABLE 2: users
-- =============================================================================
-- PURPOSE: Every person in the system (players, guests, managers, etc.)
-- =============================================================================

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Links to Supabase Auth
  auth_user_id UUID UNIQUE,

  -- Basic info
  email VARCHAR(255) NOT NULL UNIQUE,
  first_name VARCHAR(100) NOT NULL,
  last_name VARCHAR(100) NOT NULL,
  phone VARCHAR(20),

  -- Demographics (for tee eligibility)
  date_of_birth DATE,                     -- NEW: For age-based tee selection
  gender VARCHAR(20),                     -- NEW: 'male', 'female', 'other'

  -- Golf info
  ghin_number VARCHAR(20),
  current_handicap DECIMAL(4,1),

  -- Tee preferences
  tee_preference VARCHAR(30),             -- 'under_50', '50_64', '65_plus', 'forward'
  tee_override_approved BOOLEAN DEFAULT false,  -- Manager approved different tees
  tee_override_reason TEXT,               -- Why override was granted
  tee_override_approved_by UUID,          -- Who approved it

  -- Home chapter
  home_organization_id UUID REFERENCES organizations(id),

  -- Status
  status VARCHAR(30) DEFAULT 'prospect',
  membership_tier VARCHAR(30),            -- 'standard', 'tgf_plus', null
  membership_expires_at TIMESTAMPTZ,

  -- Wallet
  wallet_balance DECIMAL(10,2) DEFAULT 0.00,

  -- Stripe
  stripe_customer_id VARCHAR(255),

  -- Activity
  first_event_date DATE,
  last_event_date DATE,
  total_events_played INTEGER DEFAULT 0,

  -- Preferences
  preferences JSONB DEFAULT '{}',

  -- Notifications
  email_notifications BOOLEAN DEFAULT true,
  sms_notifications BOOLEAN DEFAULT false,

  -- Admin/Manager flags
  is_admin BOOLEAN DEFAULT false,
  is_manager BOOLEAN DEFAULT false,
  managed_organization_ids UUID[],

  -- Notes
  notes TEXT,

  -- Social media (future)
  social_links JSONB DEFAULT '{}',

  -- Referral tracking (future)
  referred_by_user_id UUID REFERENCES users(id),
  how_heard_about_tgf VARCHAR(100),

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  last_login_at TIMESTAMPTZ,
  deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status ON users(status);


-- =============================================================================
-- TABLE 3: tee_configurations
-- =============================================================================
-- PURPOSE: Define TGF tee categories and eligibility rules
--
-- TGF Tee Categories:
-- - Under 50: 6300-6800 yards (default for players < 50 years old)
-- - 50-64: 5800-6299 yards (available at age 50)
-- - 65+: 5300-5799 yards (available at age 65)
-- - Forward: 4800-5299 yards (women only by default)
-- =============================================================================

CREATE TABLE tee_configurations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Basic info
  code VARCHAR(30) NOT NULL UNIQUE,       -- 'under_50', '50_64', '65_plus', 'forward'
  name VARCHAR(100) NOT NULL,             -- "Under 50", "50-64", etc.
  description TEXT,

  -- Yardage range
  min_yardage INTEGER NOT NULL,
  max_yardage INTEGER NOT NULL,

  -- Eligibility rules
  min_age INTEGER,                        -- Minimum age to select these tees
  max_age INTEGER,                        -- Maximum age (null = no max)
  gender_restriction VARCHAR(20),         -- 'female' = women only, null = all
  requires_override BOOLEAN DEFAULT false, -- Needs manager approval

  -- Display
  display_order INTEGER DEFAULT 0,
  is_active BOOLEAN DEFAULT true,

  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert TGF tee configurations
INSERT INTO tee_configurations (code, name, description, min_yardage, max_yardage, min_age, max_age, gender_restriction, display_order) VALUES
  ('under_50', 'Under 50', 'Championship tees for players under 50', 6300, 6800, NULL, 49, NULL, 1),
  ('50_64', '50-64', 'Standard tees for players 50-64', 5800, 6299, 50, 64, NULL, 2),
  ('65_plus', '65+', 'Senior tees for players 65 and over', 5300, 5799, 65, NULL, NULL, 3),
  ('forward', 'Forward', 'Forward tees (typically for women)', 4800, 5299, NULL, NULL, 'female', 4);


-- =============================================================================
-- TABLE 4: membership_types
-- =============================================================================
-- PURPOSE: Membership products
--
-- CORRECTED:
-- - Standard: $75/year (lower upfront, pays more per event)
-- - TGF Plus: $200/year (higher upfront, saves $10/9s, $15/18s per event)
-- =============================================================================

CREATE TABLE membership_types (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Basic info
  name VARCHAR(100) NOT NULL,
  code VARCHAR(30) NOT NULL UNIQUE,       -- 'standard', 'tgf_plus'
  description TEXT,

  -- Pricing
  price DECIMAL(10,2) NOT NULL,
  duration_months INTEGER NOT NULL,

  -- Event pricing discounts
  event_discount_9 DECIMAL(10,2) DEFAULT 0,  -- $ off on 9-hole events
  event_discount_18 DECIMAL(10,2) DEFAULT 0, -- $ off on 18-hole events

  -- Availability
  is_active BOOLEAN DEFAULT true,
  is_publicly_available BOOLEAN DEFAULT true,
  display_order INTEGER DEFAULT 0,

  -- Benefits
  benefits JSONB DEFAULT '{}',

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert membership types
INSERT INTO membership_types (name, code, description, price, duration_months, event_discount_9, event_discount_18, display_order, benefits) VALUES
  ('Standard Membership', 'standard',
   'TGF membership with access to all chapters and NET games. Pay less upfront, standard pricing at events.',
   75.00, 12, 0, 0, 1,
   '{"all_chapters": true, "net_games_included": true, "season_contests_eligible": true}'),

  ('TGF Plus Membership', 'tgf_plus',
   'Premium TGF membership with event discounts. Pay more upfront, save on every event.',
   200.00, 12, 10.00, 15.00, 2,
   '{"all_chapters": true, "net_games_included": true, "season_contests_eligible": true, "event_discounts": true}');


-- =============================================================================
-- TABLE 5: membership_type_versions
-- =============================================================================
-- PURPOSE: Track price changes over time
--
-- When membership prices change, old purchases still show their original price.
-- =============================================================================

CREATE TABLE membership_type_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  membership_type_id UUID NOT NULL REFERENCES membership_types(id),

  -- Pricing at this version
  price DECIMAL(10,2) NOT NULL,
  event_discount_9 DECIMAL(10,2) DEFAULT 0,
  event_discount_18 DECIMAL(10,2) DEFAULT 0,

  -- When this version was active
  effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  effective_until TIMESTAMPTZ,            -- NULL = current version

  -- Who made the change
  created_by_id UUID REFERENCES users(id),

  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert initial versions
INSERT INTO membership_type_versions (membership_type_id, price, event_discount_9, event_discount_18, effective_from)
SELECT id, price, event_discount_9, event_discount_18, NOW()
FROM membership_types;


-- =============================================================================
-- TABLE 6: user_memberships
-- =============================================================================
-- PURPOSE: Track membership purchase history
-- =============================================================================

CREATE TABLE user_memberships (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  user_id UUID NOT NULL REFERENCES users(id),
  membership_type_id UUID NOT NULL REFERENCES membership_types(id),
  membership_version_id UUID REFERENCES membership_type_versions(id),

  -- When active
  starts_at TIMESTAMPTZ NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,

  -- Pricing at time of purchase
  price_paid DECIMAL(10,2) NOT NULL,
  event_discount_9 DECIMAL(10,2) DEFAULT 0,
  event_discount_18 DECIMAL(10,2) DEFAULT 0,

  -- Payment
  transaction_id UUID,

  -- Status
  is_active BOOLEAN DEFAULT true,
  cancelled_at TIMESTAMPTZ,
  cancellation_reason TEXT,
  auto_renew BOOLEAN DEFAULT false,

  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_user_memberships_user ON user_memberships(user_id);


-- =============================================================================
-- TABLE 7: courses
-- =============================================================================
-- PURPOSE: Golf courses where events are held
-- =============================================================================

CREATE TABLE courses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Basic info
  name VARCHAR(200) NOT NULL,

  -- Location
  address TEXT,
  city VARCHAR(100),
  state VARCHAR(50) DEFAULT 'Texas',
  zip VARCHAR(20),

  -- Contact
  phone VARCHAR(20),
  email VARCHAR(255),
  website TEXT,

  -- Primary contact
  contact_name VARCHAR(200),
  contact_phone VARCHAR(20),
  contact_email VARCHAR(255),

  -- Course data
  holes INTEGER DEFAULT 18,
  par INTEGER,

  -- Tee box data (for mapping TGF tees to course tees)
  tee_boxes JSONB DEFAULT '[]',
  /*
    [
      {"name": "Black", "yardage": 6850, "rating": 73.2, "slope": 135},
      {"name": "Blue", "yardage": 6400, "rating": 71.5, "slope": 130},
      {"name": "White", "yardage": 5900, "rating": 69.8, "slope": 125},
      {"name": "Gold", "yardage": 5400, "rating": 67.5, "slope": 118},
      {"name": "Red", "yardage": 4900, "rating": 65.2, "slope": 112}
    ]
  */

  -- TGF tee mapping (which course tees match TGF categories)
  tee_mapping JSONB DEFAULT '{}',
  /*
    {
      "under_50": "Blue",
      "50_64": "White",
      "65_plus": "Gold",
      "forward": "Red"
    }
  */

  -- Standard rates
  standard_rates JSONB DEFAULT '{}',

  -- TGF contracted rates
  tgf_rates JSONB DEFAULT '{}',

  -- Policies
  cancellation_notice_hours INTEGER DEFAULT 48,
  minimum_players INTEGER,
  payment_terms VARCHAR(50),

  -- Notes
  notes TEXT,
  dress_code TEXT,
  special_instructions TEXT,

  -- Status
  is_active BOOLEAN DEFAULT true,

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);


-- =============================================================================
-- TABLE 8: games
-- =============================================================================
-- PURPOSE: Individual game types (contests)
--
-- CORRECTED PRICING (100% to prize pool):
-- - Team MVP: $4/$8
-- - CTP: $2/$4
-- - HIO: $1/$2
-- - Individual Net: $9/$18
-- - MVP: $4/$8
-- - Skins Gross: $9/$18
-- - Individual Gross: $4/$8
-- =============================================================================

CREATE TABLE games (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Basic info
  name VARCHAR(100) NOT NULL,
  short_name VARCHAR(20),
  description TEXT,

  -- Type
  game_type VARCHAR(30) NOT NULL,

  -- Requirements
  requires_membership BOOLEAN DEFAULT false,
  requires_ghin BOOLEAN DEFAULT false,

  -- Default pricing
  default_price_9 DECIMAL(10,2) DEFAULT 0,
  default_price_18 DECIMAL(10,2) DEFAULT 0,

  -- Prize pool portion (how much of the price goes to winnings)
  -- For individual games, this is typically 100%
  prize_pool_percent DECIMAL(5,2) DEFAULT 100.00,

  -- Is this typically included free with event entry?
  typically_included BOOLEAN DEFAULT false,

  -- Minimum players for game to run (for dynamic game changes)
  minimum_players INTEGER,

  -- Special rules
  rules JSONB DEFAULT '{}',
  /*
    For MVP: {"can_split_tgf_wide": true}
    For Gross Bundle: {"converts_to": "half_net_skins", "when_players_below": 12}
  */

  display_order INTEGER DEFAULT 0,
  is_active BOOLEAN DEFAULT true,

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert games with CORRECTED pricing (100% to prize pool)
INSERT INTO games (name, short_name, game_type, requires_membership, typically_included, default_price_9, default_price_18, prize_pool_percent, display_order) VALUES
  -- Included games (these values go to prize pool)
  ('Team MVP', 'Team MVP', 'team', false, true, 4.00, 8.00, 100, 1),
  ('Closest to Pin', 'CTP', 'skill_contest', false, true, 2.00, 4.00, 100, 2),
  ('Hole-in-One Pot', 'HIO', 'pot', false, true, 1.00, 2.00, 100, 3),

  -- NET games (members only)
  ('Individual Net', 'Ind Net', 'individual_net', true, false, 9.00, 18.00, 100, 4),
  ('MVP', 'MVP', 'individual_net', true, false, 4.00, 8.00, 100, 5),  -- Can split local/TGF-wide

  -- GROSS games
  ('Skins Gross', 'Skins', 'skins', false, false, 9.00, 18.00, 100, 6),
  ('Individual Gross', 'Ind Gross', 'individual_gross', false, false, 4.00, 8.00, 100, 7),

  -- Conditional game (when GROSS bundle has < 12 players)
  ('Half Net Skins', '1/2 Net', 'skins', false, false, 9.00, 18.00, 100, 8);

-- Update MVP with split rule
UPDATE games SET rules = '{"can_split_tgf_wide": true, "local_percent": 50, "tgf_wide_percent": 50}'
WHERE short_name = 'MVP';


-- =============================================================================
-- TABLE 9: bundles
-- =============================================================================
-- PURPOSE: Game bundles sold as packages
--
-- CORRECTED:
-- NET Games = $16/$30 (contains: Individual Net $9/$18 + MVP $4/$8 + TGF Markup $3/$4)
-- GROSS Games = $16/$30 (contains: Skins Gross $9/$18 + Individual Gross $4/$8 + TGF Markup $3/$4)
-- =============================================================================

CREATE TABLE bundles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Basic info
  name VARCHAR(100) NOT NULL,
  short_name VARCHAR(20),
  description TEXT,

  -- Requirements
  requires_membership BOOLEAN DEFAULT false,

  -- Pricing
  default_price_9 DECIMAL(10,2) NOT NULL,
  default_price_18 DECIMAL(10,2) NOT NULL,

  -- Cost breakdown
  prize_pool_9 DECIMAL(10,2) NOT NULL,     -- Amount that goes to prize pool
  prize_pool_18 DECIMAL(10,2) NOT NULL,
  tgf_markup_9 DECIMAL(10,2) NOT NULL,     -- TGF keeps this
  tgf_markup_18 DECIMAL(10,2) NOT NULL,
  -- (price = prize_pool + tgf_markup)

  -- Special rules
  rules JSONB DEFAULT '{}',
  /*
    For GROSS: {"min_players": 12, "fallback_game": "half_net_skins"}
  */

  display_order INTEGER DEFAULT 0,
  is_active BOOLEAN DEFAULT true,

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert bundles with CORRECTED pricing
INSERT INTO bundles (name, short_name, description, requires_membership,
                     default_price_9, default_price_18,
                     prize_pool_9, prize_pool_18,
                     tgf_markup_9, tgf_markup_18,
                     display_order, rules) VALUES
  ('NET Games', 'NET', 'Includes Individual Net and MVP', true,
   16.00, 30.00,
   13.00, 26.00,   -- Prize pool: Ind Net ($9/$18) + MVP ($4/$8)
   3.00, 4.00,     -- TGF Markup
   1, '{}'),

  ('GROSS Games', 'GROSS', 'Includes Skins Gross and Individual Gross', false,
   16.00, 30.00,
   13.00, 26.00,   -- Prize pool: Skins ($9/$18) + Ind Gross ($4/$8)
   3.00, 4.00,     -- TGF Markup
   2, '{"min_players": 12, "fallback_description": "If fewer than 12 players, converts to 1/2 Net Skins"}');


-- =============================================================================
-- TABLE 10: bundle_games
-- =============================================================================
-- PURPOSE: Which games are in each bundle
-- =============================================================================

CREATE TABLE bundle_games (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  bundle_id UUID NOT NULL REFERENCES bundles(id) ON DELETE CASCADE,
  game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,

  display_order INTEGER DEFAULT 0,

  UNIQUE(bundle_id, game_id)
);

-- Link NET bundle to games
INSERT INTO bundle_games (bundle_id, game_id, display_order)
SELECT b.id, g.id,
  CASE g.short_name
    WHEN 'Ind Net' THEN 1
    WHEN 'MVP' THEN 2
  END
FROM bundles b, games g
WHERE b.short_name = 'NET' AND g.short_name IN ('Ind Net', 'MVP');

-- Link GROSS bundle to games
INSERT INTO bundle_games (bundle_id, game_id, display_order)
SELECT b.id, g.id,
  CASE g.short_name
    WHEN 'Skins' THEN 1
    WHEN 'Ind Gross' THEN 2
  END
FROM bundles b, games g
WHERE b.short_name = 'GROSS' AND g.short_name IN ('Skins', 'Ind Gross');


-- =============================================================================
-- TABLE 11: events
-- =============================================================================
-- PURPOSE: Calendar of golf events
--
-- NOTES:
-- - Can offer both 9 and 18 hole options in same event
-- - TGF markup is $8 for 9s, $15 for 18s standard (can override)
-- =============================================================================

CREATE TABLE events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- Which chapter hosts this?
  organization_id UUID NOT NULL REFERENCES organizations(id),
  course_id UUID REFERENCES courses(id),

  -- Basic info
  title VARCHAR(200) NOT NULL,
  description TEXT,

  -- Event format
  event_type VARCHAR(30) DEFAULT '9_hole',
  offers_18_option BOOLEAN DEFAULT false,  -- Can players choose 18 instead of 9?

  -- Date/Time
  event_date DATE NOT NULL,
  start_time_9 TIME NOT NULL,              -- Start time for 9-hole players
  start_time_18 TIME,                      -- Start time for 18-hole players (if offered)
  check_in_time TIME,

  -- TGF Standard Markup (can override per event)
  tgf_markup_9 DECIMAL(10,2) DEFAULT 8.00,
  tgf_markup_18 DECIMAL(10,2) DEFAULT 15.00,

  -- Capacity
  max_players INTEGER,
  min_players INTEGER DEFAULT 8,

  -- Registration windows
  registration_opens_at TIMESTAMPTZ,
  registration_closes_at TIMESTAMPTZ,

  -- Late fee
  late_fee_enabled BOOLEAN DEFAULT false,
  late_fee_amount DECIMAL(10,2),
  late_fee_after TIMESTAMPTZ,

  -- Registration lock (for course communication)
  registration_lock_enabled BOOLEAN DEFAULT false,
  registration_lock_at TIMESTAMPTZ,         -- When foursomes are locked

  -- Status
  status VARCHAR(30) DEFAULT 'draft',

  -- Waitlist
  waitlist_enabled BOOLEAN DEFAULT true,

  -- Settings
  settings JSONB DEFAULT '{}',

  -- Who created
  created_by_id UUID REFERENCES users(id),

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  published_at TIMESTAMPTZ,
  cancelled_at TIMESTAMPTZ,
  cancellation_reason TEXT,
  deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_events_org ON events(organization_id);
CREATE INDEX idx_events_date ON events(event_date);
CREATE INDEX idx_events_status ON events(status);


-- =============================================================================
-- TABLE 12: event_pricing
-- =============================================================================
-- PURPOSE: Pricing breakdown per player type and format (9 or 18)
--
-- PRICING LOGIC:
-- - Standard Member = Course Cost + Included Games + TGF Markup
-- - TGF Plus Member = Standard Member - $10/$15
-- - Guest = Standard Member + $10/$15
-- - First Timer = Guest - $25 (one-time, first ever event)
-- =============================================================================

CREATE TABLE event_pricing (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,

  -- Which format and player type
  holes INTEGER NOT NULL,                  -- 9 or 18
  player_type VARCHAR(30) NOT NULL,        -- 'standard_member', 'tgf_plus', 'guest', 'first_timer'

  -- Price components
  course_cost DECIMAL(10,2) NOT NULL,      -- What TGF pays course (includes their tax)
  included_games_cost DECIMAL(10,2) NOT NULL,  -- Team MVP + CTP + HIO prize pool
  tgf_markup DECIMAL(10,2) NOT NULL,       -- TGF keeps this

  -- Adjustments
  membership_discount DECIMAL(10,2) DEFAULT 0,  -- TGF Plus discount
  guest_surcharge DECIMAL(10,2) DEFAULT 0,      -- Guest premium
  first_timer_discount DECIMAL(10,2) DEFAULT 0, -- First-timer discount

  -- Final price
  base_price DECIMAL(10,2) NOT NULL,       -- Player pays this (before tax)

  -- Tax
  is_taxable BOOLEAN DEFAULT true,
  tax_rate DECIMAL(5,4) DEFAULT 0.0825,

  created_at TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE(event_id, holes, player_type)
);


-- =============================================================================
-- TABLE 13: event_games
-- =============================================================================
-- PURPOSE: Which games/bundles are available at each event
-- =============================================================================

CREATE TABLE event_games (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,

  -- Either a game OR a bundle
  game_id UUID REFERENCES games(id),
  bundle_id UUID REFERENCES bundles(id),
  CHECK ((game_id IS NOT NULL AND bundle_id IS NULL) OR (game_id IS NULL AND bundle_id IS NOT NULL)),

  -- Is this included free?
  is_included BOOLEAN DEFAULT false,

  -- Price override for this event
  price_override_9 DECIMAL(10,2),
  price_override_18 DECIMAL(10,2),

  display_order INTEGER DEFAULT 0,

  created_at TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE(event_id, game_id),
  UNIQUE(event_id, bundle_id)
);


-- =============================================================================
-- TABLE 14: registrations
-- =============================================================================
-- PURPOSE: Who's signed up for which event
-- =============================================================================

CREATE TABLE registrations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id),

  -- What format they selected
  holes INTEGER NOT NULL DEFAULT 9,         -- 9 or 18

  -- Player type at registration
  player_type VARCHAR(30) NOT NULL,
  membership_tier VARCHAR(30),              -- 'standard', 'tgf_plus', null

  -- Is this their first ever TGF event? (for first-timer discount)
  is_first_event BOOLEAN DEFAULT false,

  -- === PRICING ===
  base_price DECIMAL(10,2) NOT NULL,        -- Event base price
  games_price DECIMAL(10,2) DEFAULT 0,      -- Add-on games/bundles
  subtotal DECIMAL(10,2) NOT NULL,          -- base + games
  tax_amount DECIMAL(10,2) DEFAULT 0,
  stripe_fee DECIMAL(10,2) DEFAULT 0,       -- Passed to customer
  late_fee_amount DECIMAL(10,2) DEFAULT 0,
  discount_amount DECIMAL(10,2) DEFAULT 0,
  total_amount DECIMAL(10,2) NOT NULL,      -- Final amount

  -- === PAYMENT ===
  amount_paid DECIMAL(10,2) DEFAULT 0,
  payment_status VARCHAR(30) DEFAULT 'pending',
  payment_method VARCHAR(30),
  stripe_payment_intent_id VARCHAR(255),
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
  refund_to VARCHAR(30),

  -- === RESPONSES ===
  tee_preference VARCHAR(30),               -- Selected tees for this event
  playing_partner_request VARCHAR(200),
  fellowship_after BOOLEAN,
  special_requests TEXT,

  -- Notes
  player_notes TEXT,
  manager_notes TEXT,

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE(event_id, user_id)
);

CREATE INDEX idx_registrations_event ON registrations(event_id);
CREATE INDEX idx_registrations_user ON registrations(user_id);


-- =============================================================================
-- TABLE 15: registration_games
-- =============================================================================
-- PURPOSE: Which add-on games/bundles each player selected
-- =============================================================================

CREATE TABLE registration_games (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  registration_id UUID NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
  event_game_id UUID NOT NULL REFERENCES event_games(id),

  -- Pricing at registration time
  price DECIMAL(10,2) NOT NULL,
  prize_pool_amount DECIMAL(10,2) NOT NULL, -- Amount going to prize pool
  tgf_markup_amount DECIMAL(10,2) NOT NULL, -- TGF portion

  created_at TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE(registration_id, event_game_id)
);


-- =============================================================================
-- TABLE 16: transactions
-- =============================================================================
-- PURPOSE: Every financial transaction
-- =============================================================================

CREATE TABLE transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  user_id UUID REFERENCES users(id),

  type VARCHAR(50) NOT NULL,
  amount DECIMAL(10,2) NOT NULL,

  -- Breakdown
  revenue_amount DECIMAL(10,2),
  course_cost_amount DECIMAL(10,2),
  prize_pool_amount DECIMAL(10,2),
  tgf_profit DECIMAL(10,2),
  tax_amount DECIMAL(10,2),
  stripe_fee DECIMAL(10,2),                -- Track Stripe fees separately

  description TEXT NOT NULL,

  -- Links
  registration_id UUID REFERENCES registrations(id),
  membership_id UUID REFERENCES user_memberships(id),
  event_id UUID REFERENCES events(id),

  -- Stripe
  stripe_payment_intent_id VARCHAR(255),
  stripe_charge_id VARCHAR(255),
  stripe_refund_id VARCHAR(255),

  -- Idempotency
  idempotency_key VARCHAR(255) UNIQUE,

  status VARCHAR(30) DEFAULT 'completed',
  metadata JSONB DEFAULT '{}',

  created_at TIMESTAMPTZ DEFAULT NOW(),
  processed_at TIMESTAMPTZ,
  deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_transactions_user ON transactions(user_id);
CREATE INDEX idx_transactions_type ON transactions(type);


-- =============================================================================
-- TABLE 17: wallet_transactions
-- =============================================================================
-- PURPOSE: Wallet balance changes
-- =============================================================================

CREATE TABLE wallet_transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  user_id UUID NOT NULL REFERENCES users(id),

  amount DECIMAL(10,2) NOT NULL,
  balance_before DECIMAL(10,2) NOT NULL,
  balance_after DECIMAL(10,2) NOT NULL,

  description TEXT NOT NULL,
  source VARCHAR(50) NOT NULL,

  transaction_id UUID REFERENCES transactions(id),
  registration_id UUID REFERENCES registrations(id),
  event_id UUID REFERENCES events(id),

  created_by_id UUID REFERENCES users(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_wallet_user ON wallet_transactions(user_id);


-- =============================================================================
-- TABLE 18: event_financial_summary
-- =============================================================================
-- PURPOSE: Pre-calculated event totals
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

  -- Costs
  course_cost DECIMAL(10,2) DEFAULT 0,
  prize_pool DECIMAL(10,2) DEFAULT 0,

  -- Profit
  tgf_markup_total DECIMAL(10,2) DEFAULT 0,
  gross_profit DECIMAL(10,2) DEFAULT 0,

  -- Tax
  sales_tax_collected DECIMAL(10,2) DEFAULT 0,

  -- Stripe fees (passed to customers)
  total_stripe_fees DECIMAL(10,2) DEFAULT 0,

  calculated_at TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE(event_id)
);


-- =============================================================================
-- TABLE 19: audit_logs
-- =============================================================================
CREATE TABLE audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  user_id UUID REFERENCES users(id),
  user_email VARCHAR(255),

  table_name VARCHAR(100) NOT NULL,
  record_id UUID NOT NULL,
  action VARCHAR(20) NOT NULL,

  old_values JSONB,
  new_values JSONB,

  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_table ON audit_logs(table_name, record_id);


-- =============================================================================
-- TABLE 20: feature_flags
-- =============================================================================
CREATE TABLE feature_flags (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  key VARCHAR(100) NOT NULL UNIQUE,
  name VARCHAR(200) NOT NULL,
  description TEXT,

  enabled BOOLEAN DEFAULT false,

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO feature_flags (key, name, description, enabled) VALUES
  ('wallet_system', 'Wallet System', 'Allow wallet balances and credits', true),
  ('guest_registration', 'Guest Registration', 'Allow non-members to register', true),
  ('waitlist', 'Waitlist', 'Enable waitlist when events are full', true),
  ('late_fees', 'Late Fees', 'Charge late fees after deadline', true),
  ('stripe_payments', 'Stripe Payments', 'Accept credit card payments', true),
  ('stripe_fee_passthrough', 'Stripe Fee Passthrough', 'Pass Stripe fees to customers', true),
  ('eighteen_hole_option', '18-Hole Option', 'Allow 18-hole option on 9-hole events', true);


-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Auto-update timestamps
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers
CREATE TRIGGER update_users_timestamp BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_organizations_timestamp BEFORE UPDATE ON organizations FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_membership_types_timestamp BEFORE UPDATE ON membership_types FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_courses_timestamp BEFORE UPDATE ON courses FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_games_timestamp BEFORE UPDATE ON games FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_bundles_timestamp BEFORE UPDATE ON bundles FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_events_timestamp BEFORE UPDATE ON events FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_registrations_timestamp BEFORE UPDATE ON registrations FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- =============================================================================
-- FUNCTION: Calculate Registration Total
-- =============================================================================
-- Calculates the total for a registration including Stripe fee on total
-- =============================================================================

CREATE OR REPLACE FUNCTION calculate_registration_total(
  p_base_price DECIMAL,
  p_games_price DECIMAL,
  p_tax_rate DECIMAL,
  p_late_fee DECIMAL DEFAULT 0,
  p_discount DECIMAL DEFAULT 0,
  p_use_wallet BOOLEAN DEFAULT false,
  p_wallet_balance DECIMAL DEFAULT 0
)
RETURNS TABLE (
  subtotal DECIMAL,
  tax_amount DECIMAL,
  late_fee DECIMAL,
  discount DECIMAL,
  pre_stripe_total DECIMAL,
  stripe_fee DECIMAL,
  final_total DECIMAL,
  wallet_applied DECIMAL,
  amount_to_charge DECIMAL
) AS $$
DECLARE
  v_subtotal DECIMAL;
  v_tax DECIMAL;
  v_pre_stripe DECIMAL;
  v_stripe_fee DECIMAL;
  v_final DECIMAL;
  v_wallet DECIMAL := 0;
  v_charge DECIMAL;
BEGIN
  -- Calculate subtotal
  v_subtotal := p_base_price + p_games_price;

  -- Calculate tax
  v_tax := ROUND(v_subtotal * p_tax_rate, 2);

  -- Pre-Stripe total
  v_pre_stripe := v_subtotal + v_tax + p_late_fee - p_discount;

  -- Apply wallet if requested
  IF p_use_wallet AND p_wallet_balance > 0 THEN
    v_wallet := LEAST(p_wallet_balance, v_pre_stripe);
    v_charge := v_pre_stripe - v_wallet;
  ELSE
    v_charge := v_pre_stripe;
  END IF;

  -- Calculate Stripe fee ONLY on the amount being charged to card
  -- Stripe fee = 2.9% + $0.30
  IF v_charge > 0 THEN
    v_stripe_fee := ROUND(v_charge * 0.029 + 0.30, 2);
  ELSE
    v_stripe_fee := 0;
  END IF;

  -- Final total
  v_final := v_pre_stripe + v_stripe_fee;

  RETURN QUERY SELECT
    v_subtotal,
    v_tax,
    p_late_fee,
    p_discount,
    v_pre_stripe,
    v_stripe_fee,
    v_final,
    v_wallet,
    v_charge + v_stripe_fee;  -- Amount to actually charge to Stripe
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- FUNCTION: Check Tee Eligibility
-- =============================================================================
-- Determines which tees a user is eligible for based on age and gender
-- =============================================================================

CREATE OR REPLACE FUNCTION get_eligible_tees(
  p_user_id UUID
)
RETURNS TABLE (
  tee_code VARCHAR,
  tee_name VARCHAR,
  is_default BOOLEAN,
  requires_override BOOLEAN
) AS $$
DECLARE
  v_age INTEGER;
  v_gender VARCHAR;
  v_override_approved BOOLEAN;
BEGIN
  -- Get user info
  SELECT
    EXTRACT(YEAR FROM AGE(date_of_birth))::INTEGER,
    gender,
    tee_override_approved
  INTO v_age, v_gender, v_override_approved
  FROM users
  WHERE id = p_user_id;

  RETURN QUERY
  SELECT
    tc.code,
    tc.name,
    -- Default tee based on age
    CASE
      WHEN v_age < 50 AND tc.code = 'under_50' THEN true
      WHEN v_age >= 50 AND v_age < 65 AND tc.code = '50_64' THEN true
      WHEN v_age >= 65 AND tc.code = '65_plus' THEN true
      ELSE false
    END AS is_default,
    -- Does this tee require override?
    CASE
      -- Can always play LONGER tees
      WHEN tc.code = 'under_50' THEN false
      WHEN tc.code = '50_64' AND v_age >= 50 THEN false
      WHEN tc.code = '65_plus' AND v_age >= 65 THEN false
      -- Forward tees: women always, others need override
      WHEN tc.code = 'forward' AND v_gender = 'female' THEN false
      WHEN tc.code = 'forward' AND v_override_approved THEN false
      -- Moving to shorter tees than age allows needs override
      WHEN v_override_approved THEN false
      ELSE true
    END AS requires_override
  FROM tee_configurations tc
  WHERE tc.is_active = true
  ORDER BY tc.display_order;
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- MVP SCHEMA v2.0 COMPLETE
-- =============================================================================
--
-- Tables created (20 total):
--
-- CORE:
--   1. organizations          - Chapters
--   2. users                  - All people (with DOB, gender for tee rules)
--   3. tee_configurations     - TGF tee categories and rules
--   4. membership_types       - Membership products (Standard $75, TGF Plus $200)
--   5. membership_type_versions - Price history
--   6. user_memberships       - Membership purchase history
--   7. courses                - Golf courses
--
-- GAMES:
--   8. games                  - Individual games (corrected pricing)
--   9. bundles                - Game bundles (with TGF markup)
--   10. bundle_games          - Games in bundles
--
-- EVENTS:
--   11. events                - Calendar (with 18-hole option)
--   12. event_pricing         - Price per player type and format
--   13. event_games           - Games at each event
--
-- REGISTRATIONS:
--   14. registrations         - Who's signed up
--   15. registration_games    - Games they selected
--
-- FINANCIAL:
--   16. transactions          - All money movement
--   17. wallet_transactions   - Wallet history
--   18. event_financial_summary - Event totals
--
-- SYSTEM:
--   19. audit_logs            - Change tracking
--   20. feature_flags         - Feature toggles
--
-- KEY CORRECTIONS:
-- - Membership: Standard $75, TGF Plus $200 (with event discounts)
-- - Games: 100% to prize pool
-- - Bundles: Prize pool + TGF markup
-- - Stripe fee: Applied to total, passed to customer
-- - Tees: Age/gender based eligibility with override option
-- - Events: Can offer both 9 and 18 hole options
-- =============================================================================
