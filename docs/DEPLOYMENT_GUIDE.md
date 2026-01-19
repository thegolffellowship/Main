# TGF Platform - Deployment Guide

This guide walks you through deploying the MVP database schema to your Supabase project.

---

## Step 1: Deploy Database Schema to Supabase

Your database schema has been created and is ready to deploy. It includes:
- ✅ 11 core tables (users, events, registrations, etc.)
- ✅ Seed data (membership types, games, feature flags)
- ✅ Functions for calculations (age, tee eligibility, first-timer check)
- ✅ Views for reporting (active members, event roster, financial summary)
- ✅ Row Level Security (RLS) policies
- ✅ All your corrected pricing ($75 Standard, games at 100% to prize pool, etc.)

### Deploy via Supabase Dashboard (Recommended for MVP):

1. **Go to your Supabase project:**
   - Visit: https://app.supabase.com
   - Open your project: `tgf-platform` (https://gpjvdqzilfuqsghkmpcr.supabase.co)

2. **Open SQL Editor:**
   - Click **"SQL Editor"** in the left sidebar
   - Click **"+ New query"**

3. **Copy the migration file:**
   - Open: `/home/user/Main/supabase/migrations/00005_mvp_simplified_schema.sql`
   - Copy ALL the contents (it's about 500 lines)

4. **Paste and run:**
   - Paste into the SQL Editor
   - Click **"Run"** (or press Cmd/Ctrl + Enter)
   - Wait for it to complete (should take 5-10 seconds)

5. **Verify it worked:**
   - Click **"Table Editor"** in left sidebar
   - You should see 11 tables:
     - users
     - membership_types
     - user_memberships
     - courses
     - events
     - games
     - registrations
     - registration_games
     - transactions
     - audit_logs
     - feature_flags

6. **Check seed data:**
   - Click on `membership_types` table
   - You should see 2 rows:
     - Standard Membership ($75)
     - TGF Plus Membership ($200)
   - Click on `games` table
   - You should see 10 rows (Team MVP, CTP, HIO Pot, NET Bundle, GROSS Bundle, etc.)

### What This Schema Includes:

**Tables:**
1. `users` - All people (members, guests, admins)
2. `membership_types` - Standard ($75) and TGF Plus ($200)
3. `user_memberships` - Membership purchase history
4. `courses` - Golf courses
5. `events` - Event calendar
6. `games` - Contest types and bundles
7. `registrations` - Who signed up for what
8. `registration_games` - Games selected per registration
9. `transactions` - Financial audit trail
10. `audit_logs` - Data change tracking
11. `feature_flags` - Feature toggles

**Seed Data Included:**
- ✅ Standard Membership ($75/year)
- ✅ TGF Plus Membership ($200/year, disabled until v1.1)
- ✅ Team MVP ($4/$8)
- ✅ Closest to Pins ($2/$4)
- ✅ Hole-In-One Pot ($1/$2)
- ✅ Individual Net ($9/$18, members only)
- ✅ MVP ($4/$8, members only)
- ✅ Skins Gross ($9/$18)
- ✅ Individual Gross ($4/$8)
- ✅ NET Games Bundle ($16/$30, members only)
- ✅ GROSS Games Bundle ($16/$30)
- ✅ Feature flags (registration enabled, social auth disabled, etc.)

**Helper Functions:**
- `is_first_timer(email)` - Checks if email has EVER registered before
- `has_active_membership(user_id)` - Checks for valid membership
- `calculate_age(dob)` - Calculates age from date of birth
- `get_eligible_tees(dob, override_approved)` - Returns eligible tee options

**Views for Reporting:**
- `active_members` - Current members with membership details
- `event_roster` - Complete roster for manager dashboard
- `event_financial_summary` - Revenue breakdown by event

**Security:**
- ✅ Row Level Security (RLS) enabled
- ✅ Users can only see their own data
- ✅ Public can view courses, events, games
- ✅ Admins bypass RLS with service role key

---

## Step 2: Verify Authentication is Enabled

1. In Supabase Dashboard, click **"Authentication"** in left sidebar
2. Click **"Providers"**
3. Verify these are enabled:
   - ✅ Email (should be ON by default)
   - ✅ "Enable Email Signup" is ON
   - ✅ "Enable Email Confirmations" is ON

4. Click **"URL Configuration"**
   - Leave defaults for now (we'll update when we deploy to Vercel)

---

## Step 3: Get Your Environment Variables

You'll need these values to connect your Next.js app to Supabase:

1. In Supabase Dashboard, click **"Settings"** (gear icon)
2. Click **"API"**
3. Copy these three values:

```
NEXT_PUBLIC_SUPABASE_URL=https://gpjvdqzilfuqsghkmpcr.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdwanZkcXppbGZ1cXNnaGttcGNyIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjgzNDYxMTUsImV4cCI6MjA4MzkyMjExNX0.FCCrQCEzG47ygRsT5ptkEf7s1PhNZ-jMaxmozzLVlmU
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdwanZkcXppbGZ1cXNnaGttcGNyIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2ODM0NjExNSwiZXhwIjoyMDgzOTIyMTE1fQ.19XLNy2EtDhEMJ51mvT6arCRxohvBj1HU06G_N_-sck
```

**⚠️ IMPORTANT:**
- The `ANON_KEY` is safe to use in your frontend (public)
- The `SERVICE_ROLE_KEY` must NEVER be exposed in frontend code
- Keep the service role key secret! Only use it in server-side code

---

## Step 4: Test Your Database

Let's verify everything is working:

1. In SQL Editor, run this test query:

```sql
-- Test 1: Check membership types
SELECT * FROM membership_types;
-- Should return 2 rows (Standard $75, TGF Plus $200)

-- Test 2: Check games
SELECT name, price_9, price_18, is_included_by_default, is_bundle
FROM games
ORDER BY is_included_by_default DESC, is_bundle DESC;
-- Should return 10 rows with correct pricing

-- Test 3: Test first-timer function
SELECT is_first_timer('test@example.com');
-- Should return TRUE (no one with this email exists)

-- Test 4: Check feature flags
SELECT * FROM feature_flags;
-- Should return 7 rows with registration_enabled = TRUE
```

2. All tests should pass! If any fail, let me know and I'll help debug.

---

## Next Steps

Once the database is deployed and verified:

1. ✅ Database schema deployed
2. ⏭️ Next: Create `.env.local` file with your credentials
3. ⏭️ Then: Build authentication system (Week 1)
4. ⏭️ Then: Build admin tools (Week 2)
5. ⏭️ Then: Import your 130 members (Week 2)

---

## Troubleshooting

### Error: "relation does not exist"
- You likely have an older schema still in place
- Solution: Drop all tables first, then run the migration again
- **Warning:** This will delete all data!

### Error: "permission denied"
- Make sure you're logged into your Supabase project
- Try refreshing the page and running again

### Schema runs but no data appears
- The seed data (membership types, games) should auto-insert
- If missing, scroll to the "SEED DATA" section in the migration file
- Run just that section separately

### Need to start over?
If you need to completely reset:

```sql
-- ⚠️ WARNING: This deletes EVERYTHING!
DROP TABLE IF EXISTS registration_games CASCADE;
DROP TABLE IF EXISTS registrations CASCADE;
DROP TABLE IF EXISTS events CASCADE;
DROP TABLE IF EXISTS games CASCADE;
DROP TABLE IF EXISTS courses CASCADE;
DROP TABLE IF EXISTS user_memberships CASCADE;
DROP TABLE IF EXISTS membership_types CASCADE;
DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS feature_flags CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP VIEW IF EXISTS active_members CASCADE;
DROP VIEW IF EXISTS event_roster CASCADE;
DROP VIEW IF EXISTS event_financial_summary CASCADE;
DROP FUNCTION IF EXISTS is_first_timer(TEXT);
DROP FUNCTION IF EXISTS has_active_membership(UUID);
DROP FUNCTION IF EXISTS calculate_age(DATE);
DROP FUNCTION IF EXISTS get_eligible_tees(DATE, BOOLEAN);
DROP FUNCTION IF EXISTS update_updated_at_column();

-- Then run the migration file again
```

---

## Questions?

If you run into any issues deploying the schema, just let me know and I'll help troubleshoot!
