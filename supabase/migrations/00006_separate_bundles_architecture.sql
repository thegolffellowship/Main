-- =============================================
-- TGF Platform - Revised Schema with Separate Bundles
-- Migration: Separate bundles from games table
-- Date: January 13, 2026
-- Reason: Cleaner architecture - bundles are composite products, not games
-- =============================================

-- This migration assumes you just ran 00005 and want to fix the architecture
-- before building any code against it.

-- Step 1: Drop the views that depend on games table
DROP VIEW IF EXISTS event_roster CASCADE;
DROP VIEW IF EXISTS event_financial_summary CASCADE;

-- Step 2: Recreate games table without bundle fields
DROP TABLE IF EXISTS registration_games CASCADE;
DROP TABLE IF EXISTS games CASCADE;

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

  -- Status
  is_active BOOLEAN DEFAULT TRUE,

  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Step 3: Create new bundles table
CREATE TABLE bundles (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL,
  description TEXT,

  -- Pricing (games total + TGF markup)
  price_9 DECIMAL(10,2) NOT NULL,
  price_18 DECIMAL(10,2) NOT NULL,

  -- TGF markup on this bundle
  tgf_markup_9 DECIMAL(10,2) NOT NULL,
  tgf_markup_18 DECIMAL(10,2) NOT NULL,

  -- Requirements
  requires_membership BOOLEAN DEFAULT FALSE,

  -- Status
  is_active BOOLEAN DEFAULT TRUE,

  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Step 4: Create junction table for bundle composition
CREATE TABLE bundle_games (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  bundle_id UUID NOT NULL REFERENCES bundles(id) ON DELETE CASCADE,
  game_id UUID NOT NULL REFERENCES games(id) ON DELETE CASCADE,

  -- The price component from this game (at 9 and 18 holes)
  game_price_9 DECIMAL(10,2) NOT NULL,
  game_price_18 DECIMAL(10,2) NOT NULL,

  created_at TIMESTAMPTZ DEFAULT NOW(),

  -- Ensure no duplicate games in a bundle
  UNIQUE(bundle_id, game_id)
);

CREATE INDEX idx_bundle_games_bundle_id ON bundle_games(bundle_id);
CREATE INDEX idx_bundle_games_game_id ON bundle_games(game_id);

-- Step 5: Recreate registration_games (now can reference both games AND bundles)
CREATE TABLE registration_games (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  registration_id UUID NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,

  -- Can be either a game OR a bundle (one will be NULL)
  game_id UUID REFERENCES games(id),
  bundle_id UUID REFERENCES bundles(id),

  -- Price paid (locked at registration time)
  price_paid DECIMAL(10,2) NOT NULL,

  created_at TIMESTAMPTZ DEFAULT NOW(),

  -- Ensure at least one is set
  CHECK (
    (game_id IS NOT NULL AND bundle_id IS NULL) OR
    (game_id IS NULL AND bundle_id IS NOT NULL)
  ),

  -- Ensure no duplicate games/bundles per registration
  UNIQUE(registration_id, game_id),
  UNIQUE(registration_id, bundle_id)
);

CREATE INDEX idx_registration_games_registration_id ON registration_games(registration_id);
CREATE INDEX idx_registration_games_game_id ON registration_games(game_id);
CREATE INDEX idx_registration_games_bundle_id ON registration_games(bundle_id);

-- Step 6: Update events.included_games to be JSON instead of UUID array
-- This allows storing both games and bundles
ALTER TABLE events DROP COLUMN IF EXISTS included_games;
ALTER TABLE events ADD COLUMN included_games JSONB DEFAULT '{"games": [], "bundles": []}'::jsonb;

COMMENT ON COLUMN events.included_games IS 'Games/bundles included by default: {"games": [uuid1, uuid2], "bundles": [uuid3]}';

-- Step 7: Recreate seed data

-- Games (atomic products - 100% to prize pool)
INSERT INTO games (name, description, price_9, price_18, requires_membership, is_included_by_default) VALUES
  ('Team MVP', 'Team net best ball competition', 4.00, 8.00, FALSE, TRUE),
  ('Closest to Pins', 'Closest to the pin on par 3s', 2.00, 4.00, FALSE, TRUE),
  ('Hole-In-One Pot', 'Accumulating pot for hole-in-one', 1.00, 2.00, FALSE, TRUE),
  ('Individual Net', 'Individual net score competition (members only)', 9.00, 18.00, TRUE, FALSE),
  ('MVP', 'Most Valuable Player competition', 4.00, 8.00, TRUE, FALSE),
  ('Skins Gross', 'Gross skins game', 9.00, 18.00, FALSE, FALSE),
  ('Individual Gross', 'Individual gross score competition', 4.00, 8.00, FALSE, FALSE),
  ('½ Net Skins', 'Half-net skins (if Gross Skins has < 12 players)', 9.00, 18.00, FALSE, FALSE);

-- Bundles (composite products with TGF markup)

-- NET Bundle: Individual Net ($9/$18) + MVP ($4/$8) + TGF Markup ($3/$4) = $16/$30
INSERT INTO bundles (name, description, price_9, price_18, tgf_markup_9, tgf_markup_18, requires_membership)
VALUES (
  'NET Games Bundle',
  'Individual Net + MVP competition (Members Only)',
  16.00,  -- Total for 9 holes
  30.00,  -- Total for 18 holes
  3.00,   -- TGF markup for 9 holes
  4.00,   -- TGF markup for 18 holes
  TRUE    -- Members only
);

-- GROSS Bundle: Skins Gross ($9/$18) + Individual Gross ($4/$8) + TGF Markup ($3/$4) = $16/$30
INSERT INTO bundles (name, description, price_9, price_18, tgf_markup_9, tgf_markup_18, requires_membership)
VALUES (
  'GROSS Games Bundle',
  'Skins Gross + Individual Gross competition',
  16.00,  -- Total for 9 holes
  30.00,  -- Total for 18 holes
  3.00,   -- TGF markup for 9 holes
  4.00,   -- TGF markup for 18 holes
  FALSE   -- Available to all
);

-- Link games to NET Bundle
INSERT INTO bundle_games (bundle_id, game_id, game_price_9, game_price_18)
SELECT
  b.id as bundle_id,
  g.id as game_id,
  g.price_9,
  g.price_18
FROM bundles b
CROSS JOIN games g
WHERE b.name = 'NET Games Bundle'
  AND g.name IN ('Individual Net', 'MVP');

-- Link games to GROSS Bundle
INSERT INTO bundle_games (bundle_id, game_id, game_price_9, game_price_18)
SELECT
  b.id as bundle_id,
  g.id as game_id,
  g.price_9,
  g.price_18
FROM bundles b
CROSS JOIN games g
WHERE b.name = 'GROSS Games Bundle'
  AND g.name IN ('Skins Gross', 'Individual Gross');

-- Step 8: Recreate views with updated schema

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
  -- Games and bundles summary
  COALESCE(
    (SELECT json_agg(
      json_build_object(
        'type', CASE WHEN rg.game_id IS NOT NULL THEN 'game' ELSE 'bundle' END,
        'name', COALESCE(g.name, b.name),
        'price', rg.price_paid
      )
    )
     FROM registration_games rg
     LEFT JOIN games g ON rg.game_id = g.id
     LEFT JOIN bundles b ON rg.bundle_id = b.id
     WHERE rg.registration_id = r.id),
    '[]'::json
  ) as games_and_bundles
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

-- Step 9: Add public RLS policies for new tables
ALTER TABLE games ENABLE ROW LEVEL SECURITY;
ALTER TABLE bundles ENABLE ROW LEVEL SECURITY;
ALTER TABLE bundle_games ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public can view active games" ON games
  FOR SELECT USING (is_active = TRUE);

CREATE POLICY "Public can view active bundles" ON bundles
  FOR SELECT USING (is_active = TRUE);

CREATE POLICY "Public can view bundle compositions" ON bundle_games
  FOR SELECT USING (TRUE);

-- Step 10: Add comments for documentation
COMMENT ON TABLE games IS 'Atomic game products (Team MVP, CTP, Individual Net, etc.) - 100% to prize pool';
COMMENT ON TABLE bundles IS 'Composite bundle products (NET Bundle, GROSS Bundle) - includes TGF markup';
COMMENT ON TABLE bundle_games IS 'Junction table - which games are included in which bundles';
COMMENT ON COLUMN bundles.tgf_markup_9 IS 'TGF markup on this bundle for 9-hole events';
COMMENT ON COLUMN bundles.tgf_markup_18 IS 'TGF markup on this bundle for 18-hole events';
COMMENT ON COLUMN registration_games.game_id IS 'Reference to atomic game (mutually exclusive with bundle_id)';
COMMENT ON COLUMN registration_games.bundle_id IS 'Reference to bundle (mutually exclusive with game_id)';

-- =============================================
-- VERIFICATION QUERIES
-- =============================================

-- Verify games
SELECT 'Games' as type, COUNT(*) as count FROM games;

-- Verify bundles
SELECT 'Bundles' as type, COUNT(*) as count FROM bundles;

-- Verify bundle compositions
SELECT
  b.name as bundle_name,
  json_agg(json_build_object(
    'game', g.name,
    'price_9', bg.game_price_9,
    'price_18', bg.game_price_18
  )) as games
FROM bundles b
JOIN bundle_games bg ON b.id = bg.bundle_id
JOIN games g ON bg.game_id = g.id
GROUP BY b.id, b.name;

-- =============================================
-- ARCHITECTURE SUMMARY
-- =============================================
-- Tables: 13 (was 11)
--   11 original tables (unchanged)
--   + bundles (new)
--   + bundle_games (new)
--   - games table fields removed: is_bundle, bundle_games, bundle_markup
--   + registration_games updated to reference both games and bundles
--
-- Benefits:
-- ✓ Clean separation: games = atomic, bundles = composite
-- ✓ Flexible: Can create new bundles without changing games
-- ✓ Maintainable: Bundle composition stored in junction table
-- ✓ Extensible: Easy to add new bundle types in v1.1+
-- =============================================
