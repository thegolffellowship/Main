-- =============================================
-- TGF Platform - Simplified MVP Schema
-- Target: March 15, 2026 Season Kickoff
-- Tables: 11 core tables only
-- =============================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================
-- CORE TABLES
-- =============================================

-- 1. USERS - All people (members, guests, admins)
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email TEXT UNIQUE NOT NULL,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  phone TEXT,

  -- Golf info
  ghin_number TEXT,
  date_of_birth DATE,
  home_chapter TEXT DEFAULT 'San Antonio',
  tee_preference TEXT CHECK (tee_preference IN ('under_50', '50_64', '65_plus', 'forward')),
  tee_override_approved BOOLEAN DEFAULT FALSE, -- For men who need forward tees

  -- User status
  status TEXT NOT NULL DEFAULT 'guest' CHECK (status IN ('active_member', 'guest', 'first_timer', 'expired_member', 'admin')),

  -- Stripe integration
  stripe_customer_id TEXT,

  -- Preferences (auto-fill for future registrations)
  playing_partner_default TEXT,
  fellowship_after_default BOOLEAN DEFAULT TRUE,

  -- Timestamps
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for email lookups
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status ON users(status);

-- 2. MEMBERSHIP_TYPES - Standard ($75), TGF Plus ($200)
CREATE TABLE membership_types (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL,
  description TEXT,
  price DECIMAL(10,2) NOT NULL,
  duration_months INTEGER NOT NULL DEFAULT 12,

  -- Savings per event (TGF Plus only)
  savings_per_9 DECIMAL(10,2) DEFAULT 0,
  savings_per_18 DECIMAL(10,2) DEFAULT 0,

  -- Version tracking (for price changes over time)
  version INTEGER DEFAULT 1,
  effective_date DATE NOT NULL DEFAULT CURRENT_DATE,

  -- Status
  is_active BOOLEAN DEFAULT TRUE,

  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. USER_MEMBERSHIPS - Membership purchase history
CREATE TABLE user_memberships (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  membership_type_id UUID NOT NULL REFERENCES membership_types(id),

  -- Purchase details
  purchased_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL,
  amount_paid DECIMAL(10,2) NOT NULL,

  -- Payment
  stripe_payment_id TEXT,
  stripe_subscription_id TEXT,

  -- Status
  status TEXT DEFAULT 'active' CHECK (status IN ('active', 'expired', 'cancelled', 'refunded')),

  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_user_memberships_user_id ON user_memberships(user_id);
CREATE INDEX idx_user_memberships_expires_at ON user_memberships(expires_at);

-- 4. COURSES - Golf courses
CREATE TABLE courses (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL,
  address TEXT,
  city TEXT,
  state TEXT DEFAULT 'TX',
  zip TEXT,
  phone TEXT,
  website TEXT,

  -- Pricing (what the course charges TGF)
  standard_rate_9 DECIMAL(10,2),
  standard_rate_18 DECIMAL(10,2),
  tgf_negotiated_rate_9 DECIMAL(10,2),
  tgf_negotiated_rate_18 DECIMAL(10,2),

  -- Course details
  yardage_under_50 INTEGER,
  yardage_50_64 INTEGER,
  yardage_65_plus INTEGER,
  yardage_forward INTEGER,

  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. EVENTS - Calendar
CREATE TABLE events (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  course_id UUID NOT NULL REFERENCES courses(id),

  -- Event details
  title TEXT NOT NULL,
  description TEXT,
  event_date DATE NOT NULL,
  event_time TIME,
  event_type TEXT NOT NULL CHECK (event_type IN ('9_hole', '18_hole', 'both')),

  -- Pricing (base cost from course)
  base_price_9 DECIMAL(10,2), -- What course charges TGF for 9 holes
  base_price_18 DECIMAL(10,2), -- What course charges TGF for 18 holes

  -- TGF markup
  tgf_markup_9 DECIMAL(10,2) DEFAULT 8.00,
  tgf_markup_18 DECIMAL(10,2) DEFAULT 15.00,

  -- Member vs Guest pricing differential
  guest_surcharge_9 DECIMAL(10,2) DEFAULT 10.00,
  guest_surcharge_18 DECIMAL(10,2) DEFAULT 15.00,

  -- Included games (selected by default)
  included_games UUID[], -- Array of game IDs

  -- Registration
  max_players INTEGER,
  registration_deadline TIMESTAMPTZ,
  registration_opens TIMESTAMPTZ DEFAULT NOW(),

  -- Custom registration questions (JSONB for flexibility)
  custom_questions JSONB DEFAULT '[]'::jsonb,

  -- Status
  status TEXT DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'closed', 'completed', 'cancelled')),

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_events_date ON events(event_date);
CREATE INDEX idx_events_status ON events(status);

-- 6. GAMES - Contest types (NET, GROSS, CTP, etc.)
CREATE TABLE games (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL,
  description TEXT,

  -- Pricing (100% to prize pool)
  price_9 DECIMAL(10,2) NOT NULL,
  price_18 DECIMAL(10,2) NOT NULL,

  -- Requirements
  requires_membership BOOLEAN DEFAULT FALSE,
  is_included_by_default BOOLEAN DEFAULT FALSE, -- Team MVP, CTP, HIO Pot
  is_bundle BOOLEAN DEFAULT FALSE, -- NET Bundle, GROSS Bundle

  -- Bundle composition (for NET/GROSS bundles)
  bundle_games UUID[], -- Array of game IDs in this bundle
  bundle_markup DECIMAL(10,2) DEFAULT 0, -- TGF markup on bundle

  -- Status
  is_active BOOLEAN DEFAULT TRUE,

  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. REGISTRATIONS - Who signed up for what event
CREATE TABLE registrations (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  event_id UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

  -- Player type at time of registration
  player_status TEXT NOT NULL CHECK (player_status IN ('member', 'guest', 'first_timer')),
  membership_type_id UUID REFERENCES membership_types(id), -- NULL if guest/first_timer

  -- Hole selection
  holes INTEGER NOT NULL CHECK (holes IN (9, 18)),

  -- Preferences
  tee_preference TEXT NOT NULL CHECK (tee_preference IN ('under_50', '50_64', '65_plus', 'forward')),
  playing_partner_request TEXT,
  fellowship_after BOOLEAN DEFAULT TRUE,
  special_notes TEXT,
  dietary_restrictions TEXT,

  -- Custom answers (JSONB to match event's custom_questions)
  custom_answers JSONB DEFAULT '{}'::jsonb,

  -- Pricing breakdown
  base_price DECIMAL(10,2) NOT NULL, -- Course cost
  tgf_markup DECIMAL(10,2) NOT NULL,
  games_total DECIMAL(10,2) DEFAULT 0,
  first_timer_discount DECIMAL(10,2) DEFAULT 0,
  subtotal DECIMAL(10,2) NOT NULL,
  stripe_fee DECIMAL(10,2) NOT NULL,
  total_paid DECIMAL(10,2) NOT NULL,

  -- Payment
  stripe_payment_intent_id TEXT,
  stripe_charge_id TEXT,
  payment_status TEXT DEFAULT 'pending' CHECK (payment_status IN ('pending', 'succeeded', 'failed', 'refunded')),
  paid_at TIMESTAMPTZ,

  -- Status
  status TEXT DEFAULT 'registered' CHECK (status IN ('registered', 'checked_in', 'no_show', 'cancelled')),

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_registrations_event_id ON registrations(event_id);
CREATE INDEX idx_registrations_user_id ON registrations(user_id);
CREATE INDEX idx_registrations_payment_status ON registrations(payment_status);

-- 8. REGISTRATION_GAMES - Selected add-ons for each registration
CREATE TABLE registration_games (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  registration_id UUID NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
  game_id UUID NOT NULL REFERENCES games(id),

  -- Price paid (locked at registration time)
  price_paid DECIMAL(10,2) NOT NULL,

  created_at TIMESTAMPTZ DEFAULT NOW(),

  -- Ensure no duplicate games per registration
  UNIQUE(registration_id, game_id)
);

CREATE INDEX idx_registration_games_registration_id ON registration_games(registration_id);

-- 9. TRANSACTIONS - Financial audit log
CREATE TABLE transactions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID NOT NULL REFERENCES users(id),

  -- Transaction type
  type TEXT NOT NULL CHECK (type IN ('membership', 'event_registration', 'refund', 'adjustment')),

  -- Amount
  amount DECIMAL(10,2) NOT NULL,
  stripe_fee DECIMAL(10,2) DEFAULT 0,
  net_amount DECIMAL(10,2) NOT NULL, -- amount - stripe_fee

  -- Reference
  reference_id UUID, -- registration_id or user_membership_id
  reference_type TEXT CHECK (reference_type IN ('registration', 'membership', 'other')),

  -- Stripe
  stripe_payment_id TEXT,
  stripe_refund_id TEXT,

  -- Notes
  description TEXT,
  notes TEXT,

  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_transactions_user_id ON transactions(user_id);
CREATE INDEX idx_transactions_type ON transactions(type);
CREATE INDEX idx_transactions_created_at ON transactions(created_at);

-- 10. AUDIT_LOGS - Who changed what
CREATE TABLE audit_logs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES users(id),

  -- Action
  action TEXT NOT NULL, -- 'create', 'update', 'delete'
  table_name TEXT NOT NULL,
  record_id UUID NOT NULL,

  -- Changes
  old_value JSONB,
  new_value JSONB,

  -- Context
  ip_address TEXT,
  user_agent TEXT,

  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_table_record ON audit_logs(table_name, record_id);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);

-- 11. FEATURE_FLAGS - Toggle features on/off
CREATE TABLE feature_flags (
  key TEXT PRIMARY KEY,
  enabled BOOLEAN DEFAULT FALSE,
  description TEXT,
  metadata JSONB DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================
-- SEED DATA
-- =============================================

-- Membership Types
INSERT INTO membership_types (name, description, price, duration_months, savings_per_9, savings_per_18, effective_date) VALUES
  ('Standard Membership', 'Full TGF membership with member pricing at all events', 75.00, 12, 0, 0, '2026-01-01'),
  ('TGF Plus Membership', 'Premium membership with additional savings per event', 200.00, 12, 10.00, 15.00, '2026-01-01');

-- Games (ALL games = 100% to prize pool)
INSERT INTO games (name, description, price_9, price_18, requires_membership, is_included_by_default) VALUES
  ('Team MVP', 'Team net best ball competition', 4.00, 8.00, FALSE, TRUE),
  ('Closest to Pins', 'Closest to the pin on par 3s', 2.00, 4.00, FALSE, TRUE),
  ('Hole-In-One Pot', 'Accumulating pot for hole-in-one', 1.00, 2.00, FALSE, TRUE),
  ('Individual Net', 'Individual net score competition (members only)', 9.00, 18.00, TRUE, FALSE),
  ('MVP', 'Most Valuable Player competition', 4.00, 8.00, TRUE, FALSE),
  ('Skins Gross', 'Gross skins game', 9.00, 18.00, FALSE, FALSE),
  ('Individual Gross', 'Individual gross score competition', 4.00, 8.00, FALSE, FALSE),
  ('½ Net Skins', 'Half-net skins (if Gross Skins has < 12 players)', 9.00, 18.00, FALSE, FALSE);

-- NET Bundle (Individual Net $9/$18 + MVP $4/$8 + TGF Markup $3/$4)
INSERT INTO games (name, description, price_9, price_18, requires_membership, is_bundle, bundle_markup) VALUES
  ('NET Games Bundle', 'Individual Net + MVP (Members Only)', 16.00, 30.00, TRUE, TRUE, 3.00);

-- GROSS Bundle (Skins Gross $9/$18 + Individual Gross $4/$8 + TGF Markup $3/$4)
INSERT INTO games (name, description, price_9, price_18, requires_membership, is_bundle, bundle_markup) VALUES
  ('GROSS Games Bundle', 'Skins Gross + Individual Gross', 16.00, 30.00, FALSE, TRUE, 3.00);

-- Feature Flags (MVP defaults)
INSERT INTO feature_flags (key, enabled, description) VALUES
  ('registration_enabled', TRUE, 'Allow new event registrations'),
  ('membership_signup_enabled', TRUE, 'Allow new membership signups'),
  ('magic_link_auth', TRUE, 'Enable magic link authentication'),
  ('social_auth', FALSE, 'Enable social authentication (Google, Facebook, Apple) - v1.1'),
  ('tgf_plus_tier', FALSE, 'Enable TGF Plus membership tier - v1.1'),
  ('wallet_system', FALSE, 'Enable wallet/credits system - v2.0'),
  ('email_reminders', FALSE, 'Enable automated email reminders - v1.1');

-- =============================================
-- FUNCTIONS & TRIGGERS
-- =============================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at trigger to relevant tables
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_events_updated_at BEFORE UPDATE ON events
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_registrations_updated_at BEFORE UPDATE ON registrations
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to check if email has ever registered (for first-timer discount)
CREATE OR REPLACE FUNCTION is_first_timer(check_email TEXT)
RETURNS BOOLEAN AS $$
BEGIN
  -- Check if email exists in users table OR has any registrations
  RETURN NOT EXISTS (
    SELECT 1 FROM users WHERE email = check_email
    UNION
    SELECT 1 FROM registrations r
    JOIN users u ON r.user_id = u.id
    WHERE u.email = check_email
  );
END;
$$ LANGUAGE plpgsql;

-- Function to check if user has active membership
CREATE OR REPLACE FUNCTION has_active_membership(check_user_id UUID)
RETURNS BOOLEAN AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM user_memberships
    WHERE user_id = check_user_id
    AND status = 'active'
    AND expires_at > NOW()
  );
END;
$$ LANGUAGE plpgsql;

-- Function to calculate age from date of birth
CREATE OR REPLACE FUNCTION calculate_age(dob DATE)
RETURNS INTEGER AS $$
BEGIN
  RETURN DATE_PART('year', AGE(dob));
END;
$$ LANGUAGE plpgsql;

-- Function to get eligible tees based on age and gender
CREATE OR REPLACE FUNCTION get_eligible_tees(user_dob DATE, is_override_approved BOOLEAN DEFAULT FALSE)
RETURNS TEXT[] AS $$
DECLARE
  age INTEGER;
  eligible_tees TEXT[];
BEGIN
  age := calculate_age(user_dob);

  IF age >= 65 THEN
    eligible_tees := ARRAY['65_plus', '50_64', 'under_50'];
  ELSIF age >= 50 THEN
    eligible_tees := ARRAY['50_64', 'under_50'];
  ELSE
    eligible_tees := ARRAY['under_50'];
  END IF;

  -- Add forward tees if override approved (for men who need them)
  IF is_override_approved THEN
    eligible_tees := array_append(eligible_tees, 'forward');
  END IF;

  RETURN eligible_tees;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- ROW LEVEL SECURITY (RLS)
-- =============================================

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE registrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;

-- Users can view and update their own data
CREATE POLICY "Users can view own data" ON users
  FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update own data" ON users
  FOR UPDATE USING (auth.uid() = id);

-- Users can view their own memberships
CREATE POLICY "Users can view own memberships" ON user_memberships
  FOR SELECT USING (auth.uid() = user_id);

-- Users can view their own registrations
CREATE POLICY "Users can view own registrations" ON registrations
  FOR SELECT USING (auth.uid() = user_id);

-- Users can view their own transactions
CREATE POLICY "Users can view own transactions" ON transactions
  FOR SELECT USING (auth.uid() = user_id);

-- Admins can do everything (bypass RLS with service role)
-- Public tables (courses, events, games) are readable by everyone
CREATE POLICY "Public can view courses" ON courses
  FOR SELECT USING (TRUE);

CREATE POLICY "Public can view published events" ON events
  FOR SELECT USING (status = 'published' OR auth.uid() IS NOT NULL);

CREATE POLICY "Public can view active games" ON games
  FOR SELECT USING (is_active = TRUE);

-- =============================================
-- VIEWS FOR COMMON QUERIES
-- =============================================

-- View: Active members with membership details
CREATE VIEW active_members AS
SELECT
  u.id,
  u.email,
  u.first_name,
  u.last_name,
  u.phone,
  u.home_chapter,
  mt.name as membership_type,
  um.expires_at as membership_expires,
  u.created_at as member_since
FROM users u
JOIN user_memberships um ON u.id = um.user_id
JOIN membership_types mt ON um.membership_type_id = mt.id
WHERE u.status = 'active_member'
  AND um.status = 'active'
  AND um.expires_at > NOW()
ORDER BY u.last_name, u.first_name;

-- View: Event roster (manager dashboard)
CREATE VIEW event_roster AS
SELECT
  e.id as event_id,
  e.title as event_title,
  e.event_date,
  r.id as registration_id,
  u.first_name,
  u.last_name,
  u.email,
  u.phone,
  r.player_status,
  r.holes,
  r.tee_preference,
  r.playing_partner_request,
  r.fellowship_after,
  r.total_paid,
  r.payment_status,
  r.status as registration_status,
  r.created_at as registered_at,
  -- Games summary
  COALESCE(
    (SELECT json_agg(json_build_object('name', g.name, 'price', rg.price_paid))
     FROM registration_games rg
     JOIN games g ON rg.game_id = g.id
     WHERE rg.registration_id = r.id),
    '[]'::json
  ) as games
FROM events e
JOIN registrations r ON e.id = r.event_id
JOIN users u ON r.user_id = u.id
ORDER BY e.event_date DESC, r.created_at;

-- View: Financial summary by event
CREATE VIEW event_financial_summary AS
SELECT
  e.id as event_id,
  e.title as event_title,
  e.event_date,
  COUNT(r.id) as total_registrations,
  SUM(CASE WHEN r.payment_status = 'succeeded' THEN 1 ELSE 0 END) as paid_registrations,
  SUM(CASE WHEN r.player_status = 'member' THEN 1 ELSE 0 END) as members,
  SUM(CASE WHEN r.player_status = 'guest' THEN 1 ELSE 0 END) as guests,
  SUM(CASE WHEN r.player_status = 'first_timer' THEN 1 ELSE 0 END) as first_timers,
  SUM(r.total_paid) as total_revenue,
  SUM(r.stripe_fee) as total_stripe_fees,
  SUM(r.total_paid - r.stripe_fee) as net_revenue,
  SUM(r.base_price) as total_course_costs,
  SUM(r.tgf_markup) as total_tgf_markup,
  SUM(r.games_total) as total_game_revenue
FROM events e
LEFT JOIN registrations r ON e.id = r.event_id
WHERE r.payment_status = 'succeeded'
GROUP BY e.id, e.title, e.event_date
ORDER BY e.event_date DESC;

-- =============================================
-- INDEXES FOR PERFORMANCE
-- =============================================

-- Already created inline above, but documenting here for reference:
-- users: email, status
-- user_memberships: user_id, expires_at
-- events: event_date, status
-- registrations: event_id, user_id, payment_status
-- registration_games: registration_id
-- transactions: user_id, type, created_at
-- audit_logs: table_name+record_id, user_id, created_at

-- =============================================
-- COMMENTS FOR DOCUMENTATION
-- =============================================

COMMENT ON TABLE users IS 'All people (members, guests, admins) in the system';
COMMENT ON TABLE membership_types IS 'Types of memberships available for purchase';
COMMENT ON TABLE user_memberships IS 'Membership purchase history and active memberships';
COMMENT ON TABLE courses IS 'Golf courses where events are held';
COMMENT ON TABLE events IS 'TGF events calendar';
COMMENT ON TABLE games IS 'Contest types and bundles available at events';
COMMENT ON TABLE registrations IS 'Player registrations for events';
COMMENT ON TABLE registration_games IS 'Games/bundles selected by each player';
COMMENT ON TABLE transactions IS 'Financial audit log of all money movement';
COMMENT ON TABLE audit_logs IS 'System audit trail of data changes';
COMMENT ON TABLE feature_flags IS 'Feature toggles for gradual rollout';

COMMENT ON COLUMN users.tee_override_approved IS 'Allows men to play forward tees if approved by admin';
COMMENT ON COLUMN users.status IS 'User type: active_member, guest, first_timer, expired_member, admin';
COMMENT ON COLUMN registrations.first_timer_discount IS 'One-time $25 discount for first-time players';
COMMENT ON COLUMN games.is_included_by_default IS 'Team MVP, CTP, HIO Pot are included in base price';
COMMENT ON COLUMN games.is_bundle IS 'NET Bundle and GROSS Bundle are special composite products';
COMMENT ON COLUMN events.custom_questions IS 'Event-specific registration questions in JSON format';
COMMENT ON COLUMN registrations.custom_answers IS 'Player answers to custom registration questions';

-- =============================================
-- SCHEMA COMPLETE
-- =============================================
-- Total tables: 11
-- Total views: 3
-- Total functions: 5
-- Target event: March 15, 2026
-- =============================================
