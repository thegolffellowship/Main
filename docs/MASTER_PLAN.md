# Gap Analysis Plan: claude.ai Project vs Claude Code Codebase

## Phase 1: Initial Understanding (COMPLETE)

### Documents Reviewed:

**From claude.ai Project:**
- TGF Master Business Context v3.3 (January 5, 2026)
- 18+ year business history
- Current tech stack: Golf Genius, GoDaddy, Make.com, Excel
- Key pain points: Manual credit tracking, founder dependency, no member self-service
- Financial reality: $900-1,200/mo profit with ~$6,800 liabilities
- Brand messaging established: "Turning Foursomes into Friendships"

**From Claude Code Codebase (MVP branch):**
- README.md - Project overview
- ARCHITECTURE.md - Next.js/Supabase/Stripe architecture
- DATABASE_DIAGRAM.md - Comprehensive 16+ table schema with visual diagrams
- SETUP_GUIDE.md - Complete setup instructions
- Database schema (00003_mvp_schema.sql)

### Current State Summary:

**What EXISTS in Claude Code:**
1. ✅ Full Next.js MVP platform architecture (scaffolded on `claude/membership-transaction-mvp-KZ1Ol` branch)
2. ✅ Comprehensive database schema with 16+ tables
3. ✅ Supabase integration for database and auth
4. ✅ Stripe payment integration architecture
5. ✅ Wallet/credits system designed
6. ✅ Member, Manager, and Admin portal structure
7. ✅ Event registration flow designed
8. ✅ Financial tracking (transactions, wallet_transactions, event_financial_summary)
9. ✅ Excellent documentation (ARCHITECTURE, DATABASE_DIAGRAM, SETUP_GUIDE)
10. ✅ Games and bundles system designed

**What DOES NOT EXIST in Claude Code:**
1. ❌ Golf Genius API integration (documented but not implemented)
2. ❌ Make.com automation bridge
3. ❌ Excel workbook connections
4. ❌ Migration plan from current system
5. ❌ Actual implementation (pages/components exist as scaffolding only)

### Key Observations:

**ALIGNMENT**: The Claude Code architecture aligns well with business goals:
- Replaces manual credit tracking with automated wallet system ✅
- Provides member self-service portal ✅
- Centralizes payments through Stripe ✅
- Creates manager tools for event management ✅
- Eliminates founder dependency through systemization ✅

**POTENTIAL GAPS TO EXPLORE:**
1. **Golf Genius Integration**: Business context mentions Golf Genius as critical system, but integration strategy unclear
2. **Migration Strategy**: How to move from current GoDaddy/Make.com/Excel to new platform
3. **Games/Bundles Pricing**: Business context mentions $10 markup model, need to verify pricing logic matches
4. **Hole-in-One Pot**: Not obvious in schema (may be in games system)
5. **Points Race System**: Mentioned in business context, unclear if in MVP scope
6. **Under the Lights Event**: Mentioned as special event type, unclear if supported
7. **Communication Templates**: Business context mentions 90% time saved, unclear if email system designed
8. **Member Portal Features**: Business context emphasizes credit balance visibility - need to verify this is prominent
9. **Late Fees**: Mentioned in business context, need to verify implementation
10. **Waitlist**: Mentioned in registrations table, need to verify full workflow

## Phase 2: Requirements Clarification (IN PROGRESS)

### User Priorities (Confirmed):

1. **Primary Focus**: Feature completeness - does MVP include all critical business features?
2. **Golf Genius Strategy**:
   - MVP: Export-only (generate files for Golf Genius import)
   - Future V3+: Full replacement of Golf Genius (by beginning of 2027)
3. **Timeline**:
   - **MVP launch target: Within the month** (January 2026)
   - Golf Genius full replacement: By beginning of 2027
4. **Credit System Complexity**: TWO DIFFERENT SYSTEMS
   - **System A (Priority)**: Rain-out/cancellation credits (operational necessity)
   - **System B (Failed experiment)**: Loyalty credits for playing/achievements - caused $4K liability nightmare, may discontinue
5. **Additional Documents**: User has more artifacts to share before comprehensive analysis

### CLARIFICATIONS RECEIVED:

**Credit System (NOT IN MVP SCOPE):**
- Two types exist: Operational (rain-outs) and Loyalty (achievements)
- Both would use wallet system financially
- Loyalty credits have usage restrictions (need X credits for free event)
- **MVP DOES NOT REQUIRE CREDIT/WALLET SYSTEM**
- $4K liability is only Loyalty credits (can be handled later)

**Golf Genius "Export" (NOT IN MVP SCOPE):**
- NO automated Golf Genius integration needed for MVP
- NO export files needed
- Manager just needs live dashboard to VIEW registrations
- Optional: Export to Excel/PDF from manager dashboard (nice-to-have)

### MVP SCOPE - SIMPLIFIED (Confirmed):

The MVP is much simpler than the comprehensive schema suggests:

**Core Features for MVP (Month Timeline):**
1. ✅ Product setup (events) and availability on web interface
2. ✅ User shopping cart features (browse events, add to cart, checkout)
3. ✅ User login/authentication
4. ✅ Manager interface to see and filter transaction data
5. ✅ Export feature (Excel/PDF) for manager reports

**NOT Required for MVP:**
- ❌ Credit/wallet system (future version)
- ❌ Golf Genius integration/export (future version)
- ❌ Games/bundles system (unclear if needed)
- ❌ Loyalty program (discontinuing)
- ❌ Membership purchase flow (unclear if needed for MVP)

### MVP SCOPE - UPDATED (January 13, 2026):

**Core Features for MVP v1.0:**
1. ✅ User login/authentication
2. ✅ Event browsing with available products/options
3. ✅ Shopping cart functionality
4. ✅ Event registration with:
   - Games/bundles selection (user chooses what they want)
   - Preferences (tee time, partner, dietary) - prepopulated by membership tier
5. ✅ Dynamic pricing calculation (based on editable components/criteria)
6. ✅ Payment processing (Stripe)
7. ✅ Manager dashboard to view registrations and filter transaction data
8. ✅ Export functionality (Excel/PDF for managers)
9. ⚠️ **Event creator/admin interface** - for creating events with product details
10. ⚠️ **Membership signup/renewal** - needed soon after v1.0, but user wants recommendation on timing

**Membership Onboarding Challenge:**
- ~130 current members need to be onboarded into new subscription system
- Customer history data needs import/integration consideration
- User wants recommendation: Include in v1.0 or phase in after?

**NOT in MVP v1.0:**
- ❌ Credit/wallet system (future version)
- ❌ Golf Genius integration (future version)
- ❌ Loyalty program (discontinuing)

### DOCUMENTS RECEIVED:

**Document 1: TGF Master Business Context v3.3 (January 5, 2026)**
- 18+ year history, current state, pain points
- Current tech: Golf Genius, GoDaddy, Make.com, Excel
- Financial: $900-1,200/mo profit, $6,800 liabilities
- Brand: "Turning Foursomes into Friendships"
- **Membership Price: $300/year**

**Document 2: TGF Database Architecture & Strategic Foundation (December 19, 2024)**
- Sophisticated multi-chapter architecture vision
- Universal TGF membership model
- Contest/points system hierarchy
- Modified Stableford scoring engine with 7-stage approval cascade
- Event sourcing with pace analytics
- AI-optimized grouping
- 5-phase implementation plan
- Vision: "Automated tournament platform rivaling SPARK GOLF"
- **Membership Price: $75 universal for all chapters**

**Document 3: TGF Platform - Future Planning & Technical Requirements (August 21, 2025)**
- Dual product strategy: TGF + sellable platform
- USGA Course & Handicap Directory integration (HIGH PRIORITY)
- **Venmo as PRIMARY payment processor** (vs Stripe in Claude Code)
- Phase 1 MVP investment: $50-75K
- Q1 2026 timeline for Core MVP build
- Golf Genius transition/replacement strategy
- 4-phase development roadmap

**Document 4: TGF Complete Database Architecture & Schema v2.0 (December 19, 2024)**
- Complete SQL schema with 10+ table groups
- Component-based financial tracking innovation
- **Phase 1 (2026): Airtable bridge solution ($20/month)**
- **Phase 2 (2027): Supabase full platform**
- Detailed tables: players, events, transactions, allocations, games, prizes, scoring
- Transfer queue for manual financial management
- Manager dashboard and Golf Genius export prep
- 30-day and 90-day implementation targets

**Document 5: TGF Pricing & Services Master Document (August 21, 2025)**
- **ACTUAL Membership Pricing:** $50 new members, $75 returning (NOT $300, NOT $75 universal)
- Guest rate: Member + $10
- 1st Timer: Guest - $25 + free drink
- **Event Pricing Formula:** Course Fees + Side Games (included) + TGF Admin Fees ($6 for 9-hole, $15 for 18-hole)
- **Side Games Included:** Team Net, CTPs, HIO Pot
- **Add-on Bundles:** NET Bundle (members only) and GROSS Bundle (all) - $16 for 9-hole, $30 for 18-hole
- Season contests: À la carte ($30-$100), NOT subscription
- Special events: Unique pricing structures (Championship $260-285, Lone Star Cup $310-350)
- Sales tax: Typically 8.25%, sometimes 6.75%
- Payment methods: Venmo (primary), PayPal, Cash App, credit system
- **NOTE: User says "pricing needs to be reviewed" and "editability needed"**

**Document 6: TGF MVP Automation Roadmap (August 29, 2025)**
- Philosophy: Zero-risk, incremental automation
- Budget: $0-50/month maximum per MVP
- Timeline: One MVP every 2-4 weeks (18 weeks total for 5 MVPs)
- **MVP 1:** Real-time payment tracking (Venmo logger with Excel/Google Sheets)
- **MVP 2:** Communication automation (MailChimp or Gmail templates)
- **MVP 3:** Profit tracking dashboard
- **MVP 4:** Registration automation (Google Forms/Typeform → Golf Genius import)
- **MVP 5:** Player relationship management (Airtable)
- Mentions Filipino VA as potential solution for documented systems
- **DIY automation approach with off-the-shelf tools, NOT custom development**

### 🚨 CRITICAL DISCREPANCIES IDENTIFIED:

**1. MEMBERSHIP PRICING CONFLICT:**
- Master Business Context (Jan 5, 2026): **$300/year**
- Database Architecture (Dec 19, 2024): **$75 universal**
- **QUESTION:** Which is correct? Did pricing change between December and January?

**2. VISION vs MVP SCOPE:**
The Database Architecture describes incredibly sophisticated features:
- Modified Stableford scoring calculations
- 7-stage approval cascade (DRAFT → PENDING_APPROVAL → FOURSOME_APPROVED → MANAGER_WINDOW → PROCESSING → FINAL → ADMIN_ONLY)
- Event sourcing with complete audit trails
- Pace of play analytics
- AI-driven group staging
- Cross-chapter contest enrollment and points portability
- Real-time leaderboards
- Hole-in-one pot tracking

**QUESTION:** Is this Database Architecture document describing:
- A) The FULL vision (through V3+ by 2027)?
- B) What needs to be in MVP v1.0 (this month)?
- C) Something in between?

**3. SCORING ENGINE COMPLEXITY:**
The Database Architecture describes:
- Raw hole-by-hole gross scores as source of truth
- Modified Stableford NET/GROSS calculations
- Multiple contest calculations simultaneously
- Event sourcing with atomic processing

**QUESTION:** Does MVP v1.0 need ANY of this scoring functionality, or is this all future (Golf Genius replacement 2027)?

**4. CURRENT STATE vs ARCHITECTURE:**
- Master Business Context emphasizes current MANUAL processes and Excel dependency
- Database Architecture describes highly AUTOMATED system
- **QUESTION:** Is the Claude Code MVP branch implementation aligned with the simpler "v1.0 this month" or the sophisticated "Database Architecture vision"?

### REMAINING QUESTIONS FOR USER:

**Critical Clarifications Needed:**

1. **Membership Pricing:** $75 or $300? Which is current/correct?

2. **Database Architecture Scope:** Is that December document describing:
   - The full 2027 vision (Phases 1-5)?
   - OR the MVP v1.0 needed this month?

3. **Scoring System:** Does MVP v1.0 need:
   - NO scoring (Golf Genius handles that)?
   - Basic score entry only?
   - Full Modified Stableford calculation engine?

4. **Contest/Points System:** Does MVP v1.0 need:
   - NO contest functionality (future)?
   - Basic contest enrollment during registration?
   - Full points tracking and leaderboards?

5. **Member Onboarding:** Should MVP v1.0 include:
   - A) Full membership signup/renewal flow (delays launch)?
   - B) Admin bulk import for 130 members + manual entry (faster launch)?
   - C) Phase 1: Event registration only, Phase 2: Add membership signup?

6. **Event Creation:** For MVP v1.0, does Kerry need to:
   - Create events with all the pricing components/options?
   - OR keep creating events in Golf Genius and just handle registration in new platform?

### KERRY'S CLARIFICATIONS RECEIVED (January 13, 2026):

**Membership Pricing (CORRECTED):**
- Standard Membership: $75/year (NOT $300)
- TGF Plus: $200/year (saves $10 per 9-hole, $15 per 18-hole event)
- Guest: $0 (pays premium at each event: +$10 for 9s, +$15 for 18s)
- First Timer: Guest rate - $25 (ONE TIME, first event ever)

**Game Pricing (CORRECTED):**
- Team MVP: $4/$8 (100% to prize pool)
- Closest to Pins: $2/$4 (100% to prize pool)
- Hole-in-One Pot: $1/$2 (100% to prize pool, accumulates until won)
- Individual Net: $9/$18 (100% to prize pool)
- MVP: $4/$8 (100% to prize pool, can split 50/50 local/TGF-wide)
- Skins Gross: $9/$18 (100% to prize pool)
- Individual Gross: $4/$8 (100% to prize pool)
- ½ Net Skins: Conditional (Gross Skins changes to this if < 12 players)

**Bundles (CORRECTED):**
- NET Games: $16/$30 (Individual Net $9/$18 + MVP $4/$8 + TGF Markup $3/$4)
- GROSS Games: $16/$30 (Skins Gross $9/$18 + Individual Gross $4/$8 + TGF Markup $3/$4)
- GROSS Bundle rule: If < 16 players, Individual Gross money goes to Skins Gross only

**Event Pricing:**
- Course costs vary: $30-$90 for 9-hole (includes course's sales tax)
- TGF markup: $8 for 9-hole, $15 for 18-hole (standard events)
- Transaction fees: Pass Stripe's actual fees to customer (not 3.5% fixed)
- 18-hole option: Often available even on "Tuesday 9s" events
- Included games: Team MVP + CTP + HIO Pot = $7 total

**Tee Requirements:**
- Under 50: 6300-6800 yards (age-based OR approved)
- 50-64: 5800-6299 yards (available once you turn 50)
- 65+: 5300-5799 yards (available once you turn 65)
- Forward: 4800-5299 yards (WOMEN ONLY unless admin override)
- Players can always choose LONGER tees than age group
- Need date_of_birth in users table for auto-eligibility

**Games - Product vs Operations:**
- MVP = Product configuration (what players buy)
- Event operations (scoring, pairings, Golf Genius replacement) = v3.0
- Need ability to create custom games with flexible pricing
- Prize payout matrix exists (player count-dependent) - for v1.5+

**Key Insights:**
1. ALL game revenue = 100% prize pool
2. TGF markup ONLY on bundles and event base price
3. Need version tracking for prices (old purchases show old prices)
4. Stripe fees calculated on TOTAL (base + add-ons), not per item
5. User wants to track: DOB, social media, how they heard about TGF, demographics

### GAP ANALYSIS STATUS:

**What EXISTS in Claude Code MVP branch:**
✅ Comprehensive schema designed (18 tables for MVP)
✅ Users table (not "members")
✅ Games, bundles, events structure
✅ Financial tracking with profit breakdown
✅ Database diagram documentation
✅ Next.js + Supabase + Stripe architecture

**What NEEDS UPDATING:**
⚠️ Membership pricing ($75 Standard, $200 TGF Plus)
⚠️ Game pricing (corrected values)
⚠️ Bundle structure (prize pool + markup breakdown)
⚠️ Tee restrictions (Forward = women only)
⚠️ Transaction fee calculation (Stripe actual, not 3.5%)
⚠️ Users table (add date_of_birth, tee_override_approved)
⚠️ Version tracking for prices

**What's MISSING for MVP:**
❌ Event creation UI (admin interface)
❌ Registration flow UI (multi-step form)
❌ Stripe integration code (payment processing)
❌ Manager roster view UI
❌ Email confirmation templates
❌ Setup documentation for Kerry

### REVISED MVP SCOPE:

**Must Have (v1.0 - This Month):**
1. User accounts (sign up, login, magic link)
2. Admin: Add courses, games, bundles
3. Admin: Create events with dynamic pricing
4. Public: Browse events, event details
5. Public: Register + pay (Stripe)
6. Manager: View roster, payment status
7. Basic confirmation emails
8. Stripe fee pass-through to customer

**Should Have (v1.1 - Within 1 Month):**
- Smart autofill (tee preference, fellowship after)
- Email templates (customizable)
- Waitlist basic functionality
- Promo codes (manual)
- Export roster to Excel/PDF

**Nice to Have (v1.5 - Based on Feedback):**
- Preferred partners (basic)
- Custom registration questions
- Action items queue
- Prize payout matrix visibility
- Player game payout communication

**Future (v2.0+):**
- Handicap tracking module
- Multi-day events
- Team events
- Batch operations
- Course portal
- AI assistant

### FINAL MVP SCOPE:

**Target Event:** TBD - March 15 Season Kickoff (recommended) OR Late Feb event (aggressive)
**Timeline:** 5-9 weeks depending on target event chosen (see Timeline Options below)

**Critical Insight:** MVP is not just event registration - it's **member onboarding + event registration** as integrated flow. Current pain: GoDaddy doesn't know who anyone is. Solution: System recognizes members, remembers preferences, makes registration effortless.

---

## EXECUTIVE SUMMARY

**What We're Building:**
A membership and event registration platform that replaces GoDaddy for TGF events, starting with either a late Feb or March 15 season kickoff event.

**Key Features (MVP):**
1. ✅ Member accounts with email/password + magic link (social auth in v1.1)
2. ✅ Import existing members AND guests/expired members from Excel
3. ✅ Members recognized automatically at events (no manual status selection)
4. ✅ First-timers get $25 discount automatically (only if NEVER registered before)
5. ✅ Smart registration with auto-fill preferences
6. ✅ Stripe payment processing (fees passed to customer)
7. ✅ Manager roster dashboard with CSV export for Golf Genius
8. ✅ **Event setup dashboard** - Create events with pricing, games, all product details

**What's NOT in MVP:**
- ❌ Social auth (Google, Facebook, Apple) - v1.1
- ❌ TGF Plus tier (v1.1)
- ❌ Wallet/credits system (v2.0)
- ❌ Email reminders (v1.1)
- ❌ Golf Genius replacement (v3.0 by 2027)

**Timeline Options:**
- **Option A (Recommended): March 15 Season Kickoff** - 9 weeks, safer, better showcase
- **Option B (Aggressive): Late Feb Event** - 5-6 weeks, tight but possible
- **Option C (Not Realistic): Next week** - 7 days, will fail
- **Decision needed:** See Timeline Options section below

**Database:**
11 tables (vs 50+ in comprehensive schema):
- `users`, `membership_types`, `user_memberships`
- `courses`, `events`, `games`, `registrations`
- `transactions`, `audit_logs`, `feature_flags`

**Success Metric:**
Kerry spends < 30 minutes managing March 15 registrations (vs 4-10 hours currently)

---

## THE THREE CORE USER JOURNEYS

### Journey A: New Member Joins TGF

**Current State (Manual):**
1. Person hears about TGF
2. Pays $75 via GoDaddy product
3. Kerry manually adds to Excel tracking
4. System still doesn't recognize them at events

**MVP Required State:**
1. Person visits thegolffellowship.com
2. Clicks "Become a Member" ($75/year)
3. Creates account (name, email, phone + password OR magic link)
4. Completes profile:
   - Golf info (GHIN optional, DOB for tee eligibility)
   - Preferences (tee, home chapter)
   - Can skip and complete later during first event registration
5. Pays $75 via Stripe
6. Gets welcome email
7. **System now recognizes them** - all future events show member pricing automatically

### Journey B: Member Registers for Jan 24 Event

**Current State (10 manual steps):**
1. Gets email from Golf Genius
2. Clicks separate GoDaddy link
3. MANUALLY selects "Member" status (no verification)
4. MANUALLY selects tees
5. MANUALLY enters partner request, fellowship preference
6. Adds to cart, applies coupon code
7. Checks out
8. Kerry gets GoDaddy notification
9. Kerry MANUALLY adds to Golf Genius roster
10. Kerry MANUALLY sets up divisions/pairings

**MVP Required State (3 steps, zero manual):**
1. Gets announcement about Jan 24 event
2. Clicks link → Already logged in (or quick login)
3. Sees smart registration form:
   ```
   Willow Springs 18-Hole Event - Jan 24

   Your Price: $79 (Member Rate) ✓

   Included:
   • Green fee ($50)
   • Team MVP, CTP, HIO Pot ($14)
   • TGF event fee ($15)

   Add-ons:
   ☐ NET Games Bundle (+$30) - Members only
   ☐ GROSS Games Bundle (+$30)

   Your Preferences (auto-filled from last time OR profile):
   Tees: 50-64 ✓
   Playing Partner: [text field]
   Fellowship After: Yes ✓
   Special Notes: [text field]

   Total: $79.00
   Stripe fee: $2.59
   ──────────────
   Total Due: $81.59

   [Pay with Stripe]
   ```
4. Clicks Pay → Done
5. Gets confirmation email
6. Kerry sees them on roster dashboard immediately

### Journey C: Guest Registers for Jan 24

**MVP Required State:**
1. Clicks event link (not logged in)
2. Prompted: "Sign up or continue as guest"
3. Enters name, email, phone (creates account OR guest checkout)
4. Sees pricing:
   ```
   Your Price: $94 (Guest Rate)

   💡 Save $15 per event! Become a member for $75/year
   [Learn More]
   ```
5. Selects tees (age-based auto-suggest if DOB provided)
6. Selects add-ons, preferences
7. Pays → Done
8. Follow-up email: "Enjoyed TGF? Become a member!"

### Journey D: First-Timer Registers

**MVP Required State:**
1. Same as Guest journey
2. System checks email against database
3. If NEW email → Apply $25 first-timer discount automatically
4. Shows: "First Timer Special: $69 (Guest $94 - $25 discount)"
5. Completes registration
6. Follow-up: "Welcome to TGF! Consider membership..."

### Journey E: Existing Member Import & Onboarding

**User Has:** ~130 active members in Excel with:
- Name, email, phone, chapter
- Membership purchase date & expiration date
- DOB (most), address (most), GHIN (some), tee preference (current)

**MVP Required:**
1. Admin bulk import tool
2. Creates user accounts for all active members
3. Sets status = "active_member" with calculated expiration date
4. Sends onboarding email:
   ```
   Welcome to the New TGF Platform!

   We've created your account using your existing membership.

   Please complete your profile:
   - Confirm your information
   - Set a password (or use magic link login)
   - Add payment method for easy checkout
   - Set your preferences (tees, fellowship, etc.)

   Your membership expires: [calculated date]

   [Complete Profile]
   ```
5. When they first register for an event:
   - System recognizes them as member
   - Prompts to complete missing profile fields during registration
   - Saves preferences for next time

---

## RUTHLESSLY SCOPED MVP FEATURES

### MUST BUILD (For Jan 24 Success):

| # | Feature | Why Essential | Tables Needed |
|---|---------|---------------|---------------|
| 1 | **User signup/login** | System must recognize members | `users`, auth |
| 2 | **Member profile** | Capture golf info, preferences | `users` (extended) |
| 3 | **Membership purchase** | New members can join | `membership_types`, `user_memberships` |
| 4 | **Member import tool** | Onboard 130 existing members | Admin interface |
| 5 | **Course management** | Admin adds Willow Springs | `courses` |
| 6 | **Event creation** | Admin creates Jan 24 event | `events`, `event_pricing`, `event_games` |
| 7 | **Event display** | Public can see Jan 24 event | Public pages |
| 8 | **Smart registration** | Member status → correct pricing → auto-fill preferences | `registrations`, `registration_games` |
| 9 | **Stripe payment** | Take money securely | Stripe integration |
| 10 | **Confirmation email** | Player knows they're registered | Email system |
| 11 | **Manager roster** | Kerry sees: Name, Status, 9/18, Games, Tees, Partner, Notes, Total | Admin interface |
| 12 | **CSV Export** | Kerry exports for Golf Genius import | Export functionality |

### EXPLICITLY NOT BUILDING (For Jan 24):

| Feature | Why Deferred | When |
|---------|-------------|------|
| Email reminders (7-day, 1-day) | Kerry will send manually | v1.1 |
| Waitlist | 24 players, unlikely to fill | v1.1 |
| Wallet/credits | No winnings to credit yet | v2.0 |
| Multi-day events | Jan 24 is single day | v1.5 |
| Teams/pairings | Golf Genius handles | v3.0 (2027) |
| Scoring/leaderboards | Golf Genius handles | v3.0 (2027) |
| Handicap tracking | Golf Genius handles | v2.0+ |
| Batch operations | Only one event to manage | v1.5 |
| Advanced games matrix | Payout rules for later | v1.5 |
| AI assistant | Future vision | v3.0+ |
| SMS notifications | Email sufficient for now | v2.0 |
| Course portal | Phone/email works | v2.0 |
| Promo codes system | Can add manually in pricing | v1.1 |

---

## MINIMAL VIABLE DATABASE SCHEMA

Based on Jan 24 requirements, here are the ONLY tables needed:

### Core Tables (8):

1. **users** - All people (members, guests, admins)
   - Basic: id, email, first_name, last_name, phone, password_hash
   - Golf: ghin_number, date_of_birth, home_chapter_id, tee_preference
   - System: status (active_member, guest, first_timer), stripe_customer_id, created_at
   - Preferences: playing_partner_default, fellowship_after_default

2. **membership_types** - Standard ($75), TGF Plus ($200)
   - id, name, price, duration_months, savings_per_9, savings_per_18, version

3. **user_memberships** - Membership purchase history
   - id, user_id, membership_type_id, purchased_at, expires_at, amount_paid, stripe_payment_id

4. **courses** - Golf courses
   - id, name, address, phone, standard_rate_9, standard_rate_18, tgf_negotiated_rate_9, tgf_negotiated_rate_18

5. **events** - Calendar
   - id, course_id, title, event_date, event_type (9_hole, 18_hole, both), base_price_member, base_price_guest, tgf_markup, max_players, registration_deadline

6. **games** - Contest types
   - id, name, price_9, price_18, requires_membership, is_included_by_default

7. **registrations** - Who signed up
   - id, event_id, user_id, player_status (member, guest, first_timer), total_paid, stripe_payment_id, tee_preference, playing_partner_request, fellowship_after, special_notes, created_at

8. **registration_games** - Selected add-ons
   - id, registration_id, game_id, price_paid

### Optional But Highly Recommended (3):

9. **transactions** - Financial audit log
   - id, user_id, type (membership, event_registration, refund), amount, stripe_payment_id, created_at

10. **audit_logs** - Who changed what
    - id, user_id, action, table_name, record_id, old_value, new_value, created_at

11. **feature_flags** - Toggle features on/off
    - key, enabled, metadata

**Total: 8-11 tables (vs. 20+ in comprehensive schema)**

---

## TIMELINE OPTIONS - CRITICAL DECISION NEEDED

Kerry wants faster delivery. Here are realistic options:

### Option A: March 15 Season Kickoff (RECOMMENDED)
**Timeline:** 9 weeks from now
**Registration opens:** Early March (~2 weeks before)
**Why this is best:**
- ✅ Enough time for quality development and testing
- ✅ Members have 3-4 weeks to onboard after import
- ✅ Time to fix bugs found during testing
- ✅ Can do proper user testing with 10-20 members
- ✅ Kerry has time to learn the admin interface
- ✅ Buffer for unexpected issues
- ✅ Proper season kickoff event (higher stakes = better showcase)

**Risk:** Lower

### Option B: Late February Event (AGGRESSIVE)
**Timeline:** 5-6 weeks from now
**Target:** Feb 22-28 event
**Registration opens:** Mid-Feb (~2 weeks before)
**Challenges:**
- ⚠️ Tight timeline, little margin for error
- ⚠️ Members have only 2 weeks to onboard after import
- ⚠️ Less time for bug fixes
- ⚠️ Kerry learning admin tools under time pressure

**Risk:** Medium

### Option C: "Next Week" (NOT REALISTIC)
**Timeline:** 7 days
**Why it won't work:**
- ❌ Cannot build auth + admin tools + registration + payment + testing in 7 days
- ❌ No time for member onboarding
- ❌ No time for testing
- ❌ High probability of broken launch
- ❌ Would damage member trust

**Risk:** Critical - DO NOT ATTEMPT

### My Recommendation:
**Target March 15 Season Kickoff.** Here's why:
1. Registration doesn't need to open until late Feb/early March
2. Gives members proper time to onboard and get comfortable
3. Season kickoff is a bigger event - better showcase for new platform
4. Buffer time for inevitable bugs/issues
5. Kerry can dedicate time to learning admin interface properly

**Compressed Option:**
If Kerry can dedicate 15-20 hrs/week to this (testing, data prep, learning admin tools), we could potentially target a late Feb event (Option B), but March 15 is safer.

---

## IMPLEMENTATION PLAN (March 15 Target - 9 Weeks)

### Week 1: Foundation & Setup (Jan 13-19)
**Kerry's Tasks:**
- [✅] Create Supabase account (COMPLETED - Jan 13, 2026)
  - Project URL: https://gpjvdqzilfuqsghkmpcr.supabase.co
  - Anon key: Secured
  - Service role key: Secured
- [ ] Create Stripe account (20 min, guided)
- [ ] Create Vercel account (5 min, guided)
- [ ] Provide event details for target event (see Data Requirements below)

**My Tasks:**
- [ ] Create simplified database schema (11 tables)
- [ ] Deploy schema to Supabase
- [ ] Set up Next.js app structure
- [ ] Deploy to Vercel (test environment)
- [ ] Build authentication:
  - [ ] Email/password signup and login
  - [ ] Magic link login
  - [ ] ~~Social auth~~ (deferred to v1.1)
- [ ] Basic user profile page

**Deliverable:** Kerry can create an account and log in

### Week 2: Member Import & Admin Tools (Jan 20-26)
**Kerry's Tasks:**
- [ ] Prepare Excel file with 130 members (clean data)
- [ ] Test admin interface (add a test course, test event)

**My Tasks:**
- [ ] Build admin dashboard
- [ ] Build member import tool (CSV upload)
- [ ] Build course management (add/edit courses)
- [ ] Build games/bundles management (pre-populate standard games)
- [ ] Build event creation interface
- [ ] Import 130 real members
- [ ] Send onboarding emails to all members

**Deliverable:** All 130 members imported, receiving onboarding emails

### Week 3: Member Onboarding & Registration Flow (Jan 27 - Feb 2)
**Members' Tasks (happening in background):**
- Receiving onboarding emails
- Completing profiles
- Setting preferences

**Kerry's Tasks:**
- [ ] Create March 15 season kickoff event in system
- [ ] Test registration as different user types

**My Tasks:**
- [ ] Build public event listing page
- [ ] Build event details page
- [ ] Build registration flow (multi-step form):
  - [ ] Step 1: Login or continue as guest
  - [ ] Step 2: Select add-ons (NET/GROSS bundles)
  - [ ] Step 3: Preferences (tees, partner, fellowship)
  - [ ] Step 4: Review and pay
- [ ] Build pricing calculation engine
- [ ] Integrate Stripe payment processing
- [ ] Build confirmation email system

**Deliverable:** Kerry can register for March 15 event end-to-end

### Week 4: Refinement & Polish (Feb 3-9)
**Kerry's Tasks:**
- [ ] Review event setup dashboard, suggest improvements
- [ ] Test creating multiple events with different configurations
- [ ] Prepare historical player data (guests/expired members) for import

**My Tasks:**
- [ ] Build configurable registration questions
- [ ] Add custom question capability to event setup
- [ ] Refine UI/UX based on Kerry's feedback
- [ ] Add data validation and error handling
- [ ] Write user documentation (how to create events, import members)

**Deliverable:** Event setup dashboard fully functional with all options

### Week 5: Manager Tools (Feb 10-16)
**Kerry's Tasks:**
- [ ] Invite 5-10 members to test registration
- [ ] Test roster dashboard
- [ ] Test CSV export → import to Golf Genius
- [ ] Report any bugs or issues

**My Tasks:**
- [ ] Build manager roster dashboard
- [ ] Build filtering (by event, status, games)
- [ ] Build CSV export for Golf Genius
- [ ] Fix any bugs found during testing
- [ ] Performance optimization
- [ ] Security audit

**Deliverable:** System tested with real members, ready for launch

### Week 5: Manager Tools (Feb 10-16)
**Kerry's Tasks:**
- [ ] Test roster dashboard with test registrations
- [ ] Test CSV export format with Golf Genius import
- [ ] Report any bugs or issues

**My Tasks:**
- [ ] Build manager roster dashboard
- [ ] Build filtering (by event, status, games)
- [ ] Build CSV export for Golf Genius
- [ ] Build search functionality
- [ ] Add real-time updates (when new registrations come in)

**Deliverable:** Manager can see and export registrations

### Week 6: Testing & Bug Fixes (Feb 17-23)
**Kerry's Tasks:**
- [ ] Invite 10-15 members to test registration
- [ ] Test end-to-end flow as different user types
- [ ] Document all bugs/issues found

**My Tasks:**
- [ ] Fix all bugs found during testing
- [ ] Performance optimization
- [ ] Security audit
- [ ] Mobile responsiveness testing
- [ ] Cross-browser testing

**Deliverable:** System tested and ready for production

### Week 7: Launch Preparation (Feb 24 - Mar 2)
**Kerry's Tasks:**
- [ ] Create March 15 event in production
- [ ] Finalize event details (course confirmation, pricing)
- [ ] Prepare announcement for members
- [ ] Import historical player data (if ready)

**My Tasks:**
- [ ] Final deployment to production
- [ ] Set up monitoring and alerts
- [ ] Create backup/recovery procedures
- [ ] Final security review
- [ ] Prepare support documentation

**Deliverable:** Production system ready for real registrations

### Week 8: Registration Opens (Mar 3-9)
**Kerry's Tasks:**
- [ ] Announce March 15 event to members
- [ ] Monitor registrations daily
- [ ] Answer member questions
- [ ] Provide immediate feedback on any issues

**My Tasks:**
- [ ] Monitor system performance in real-time
- [ ] Fix any critical issues within hours
- [ ] Track analytics (signup rate, completion rate, bounce rate)
- [ ] Provide daily status updates to Kerry

**Deliverable:** Smooth registration experience for members

### Week 9: Final Week & Event Execution (Mar 10-16)
**Kerry's Tasks:**
- [ ] Export final roster on Mar 13 (2 days before event)
- [ ] Import to Golf Genius
- [ ] Run March 15 season kickoff event
- [ ] Collect member feedback

**My Tasks:**
- [ ] Monitor for any last-minute issues
- [ ] Support any emergency requests
- [ ] Collect analytics on full registration cycle
- [ ] Begin planning v1.1 features based on feedback

**Deliverable:** Successful season kickoff on new platform! 🎉

---

## DATA REQUIREMENTS

### From Kerry's Excel (for import):

**IMPORTANT:** Kerry needs to provide TWO datasets:

**Dataset 1: Current Active Members (~130 people)**
- ✅ Name (first, last)
- ✅ Email
- ✅ Phone
- ✅ Chapter (SA or Austin)
- ✅ Membership purchase date
- ✅ Membership expiration date
- ✅ Date of birth (most members)
- ✅ Address (most members)
- ✅ GHIN (those who have it)
- ✅ Tee preference (current)
- Status = "active_member"

**Dataset 2: Past Guests & Expired Members (everyone who ever played)**
- ✅ Name, Email, Phone (at minimum)
- ✅ Last event played (if available)
- ✅ Chapter (if known)
- Status = "guest" or "expired_member"
- **Why we need this:** To prevent them from getting first-timer discount

### Missing data to collect during onboarding:
- Password (or they use magic link)
- Stripe payment method (for future one-click checkout)
- Playing partner default (optional)
- Fellowship after default (optional)

### For March 15 Season Kickoff Event:
Kerry needs to provide (by Week 7):
- Golf course details (name, address, phone)
- Negotiated rate (9-hole and/or 18-hole)
- Exact event date/time
- Registration deadline (when does registration close?)
- Max players (if any)
- Special notes (season kickoff announcements, etc.)

---

## KEY TECHNICAL DECISIONS

### 1. Member Status Recognition
**How it works:**
- User logs in
- System checks `users.status` and `user_memberships.expires_at`
- If `status = 'active_member'` AND `expires_at > today` → Member pricing
- If `status = 'guest'` → Guest pricing
- If email not in database → Check for first-timer discount eligibility

### 2. Pricing Calculation Engine
**Dynamic pricing formula (works for any event):**
```javascript
// Step 1: Calculate base price for this event
const course_cost = event.course_negotiated_rate  // e.g., $50 for 18-hole
const included_games_total = calculateIncludedGames(event)  // Team MVP + CTP + HIO
const tgf_markup = event.tgf_markup  // $8 for 9s, $15 for 18s
const base_member_price = course_cost + included_games_total + tgf_markup

// Step 2: Adjust for player type
let player_price
if (user.status === 'active_member') {
  if (user.membership_type === 'TGF Plus') {
    // TGF Plus saves $10 on 9s, $15 on 18s (NOT IN MVP - v1.1)
    const savings = event.event_type === '18_hole' ? 15 : 10
    player_price = base_member_price - savings
  } else {
    // Standard member pays base price
    player_price = base_member_price
  }
} else if (user.status === 'guest') {
  // Guest pays premium ($10 for 9s, $15 for 18s)
  const surcharge = event.event_type === '18_hole' ? 15 : 10
  player_price = base_member_price + surcharge
} else if (is_first_timer(user.email)) {
  // First-timer = guest rate minus $25 (one time only)
  const surcharge = event.event_type === '18_hole' ? 15 : 10
  player_price = (base_member_price + surcharge) - 25
}

// Step 3: Add selected bundles
const bundles_total = selected_bundles.reduce((sum, bundle) => {
  return sum + (event.event_type === '18_hole' ? bundle.price_18 : bundle.price_9)
}, 0)
player_price += bundles_total

// Step 4: Calculate Stripe fee on total (passed to customer)
const stripe_fee = (player_price * 0.029) + 0.30
const total = player_price + stripe_fee

// Example for Feb 22 (18-hole, $50 course cost):
// Standard Member: $50 + $14 (games) + $15 (markup) = $79
// + $30 NET Bundle = $109
// + Stripe fee ($3.46) = $112.46
```

### 3. Auto-Fill Preferences Logic
**First registration:**
- Check if user has profile preferences set → pre-fill
- If not, show empty form
- After registration, prompt: "Save these preferences for next time? ✓"

**Subsequent registrations:**
- Pre-fill from last registration OR profile defaults
- User can change any field
- Option to update defaults: "Make this my new default ✓"

### 4. Tee Eligibility
**Rules:**
- Calculate age from `date_of_birth`
- Auto-suggest appropriate tee based on age
- Show all tees they're eligible for (can always play longer)
- Forward tees: Women only UNLESS `tee_override_approved = true`

### 5. Golf Genius Export Format
**CSV columns needed:**
- Name (First Last)
- Email
- GHIN (if available)
- Tee
- NET Bundle (Yes/No)
- GROSS Bundle (Yes/No)
- Playing Partner Request
- Notes

---

## SUCCESS CRITERIA

**MVP is successful if on March 15:**
1. ✅ All players for season kickoff registered through new system (not GoDaddy)
2. ✅ Zero manual data entry for Kerry (besides Golf Genius CSV import)
3. ✅ Members recognized automatically (didn't have to select status)
4. ✅ First-timers get $25 discount automatically
5. ✅ Pricing calculated correctly for all player types (member, guest, first-timer)
6. ✅ Kerry can see complete roster with all details in one view
7. ✅ CSV export imports cleanly to Golf Genius
8. ✅ No payment processing errors
9. ✅ Registration took < 3 minutes per player
10. ✅ Members can login with email/password OR magic link

**Bonus success indicators:**
- Members comment on how easy and fast the new system is
- No phone calls/texts asking "did you get my registration?"
- Kerry spends < 30 minutes total on registration management (vs. 4-10 hours currently)
- 80%+ of imported members complete their profiles during onboarding period
- Members save payment methods for future one-click checkout

---

## RISKS & MITIGATIONS

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|---------|-----------|
| Members don't complete onboarding | Medium | High | Send clear, simple onboarding email with 3-step process |
| Stripe payment fails | Low | Critical | Test extensively; keep GoDaddy as backup for 1st event |
| Members can't remember login | Medium | Medium | Magic link as primary method (no password to forget) |
| Pricing calculation error | Medium | High | Extensive testing with all player types; manual verification |
| Golf Genius import fails | Medium | Medium | CSV format tested in advance; manual entry as backup |
| Site goes down during registration | Low | High | Vercel has 99.99% uptime; monitor closely |
| Members resistant to change | Medium | Medium | Clear communication about benefits; support availability |

---

## IMMEDIATE NEXT STEPS:

1. ✅ **Planning complete** - Kerry approves this scoped plan
2. **Create simplified database schema** - 11 tables for MVP (Week 1)
3. **Set up external accounts** - Kerry creates Supabase, Stripe, Vercel with step-by-step guidance (Week 1)
4. **Build authentication** - Email/password + magic link (Week 1)
5. **Build admin tools** - Event setup dashboard, member import (Week 2)
6. **Import active members** - 130 members onboarded (Week 2)
7. **Build registration flow** - Public pages + Stripe payment (Week 3)
8. **Build manager dashboard** - Roster view + CSV export (Week 5)
9. **Testing & launch** - Weeks 6-8
10. **March 15 season kickoff** - First event on new platform! (Week 9)

---

---

## 📋 QUICK REFERENCE - FINAL DECISIONS

**Target Event:** March 15, 2026 Season Kickoff (9 weeks from today)
**Timeline:** Week 1-2: Build foundation + import members → Week 3-5: Registration + manager tools → Week 6-8: Testing + launch prep → Week 9: Event!
**MVP Features:** Auth (email/password + magic link), Event setup dashboard, Member import, Registration flow, Stripe payments, Manager roster + CSV export
**NOT in MVP:** Social auth, TGF Plus tier, Wallet/credits, Email reminders
**First Dataset:** 130 active members (Week 2)
**Second Dataset:** Historical guests/expired (import Week 3-4 or later)

---

## KERRY'S DECISIONS (FINAL):

1. **Timeline:** ✅ **Option A - March 15 Season Kickoff** - 9 weeks to build
   - Registration opens: Early March (~2 weeks before event)
   - Kerry has day job but this is priority #1
   - More time for quality, testing, member onboarding
   - Better showcase (season kickoff is bigger event)

2. **Member onboarding:** ✅ **Import in Week 2-3 (after auth is built)**
   - Week 1: Build auth system
   - Week 2: Build import tool + import active members (~130)
   - Week 2-5: Members receive onboarding emails, complete profiles (3-4 weeks)
   - Week 3-4: Build registration flow
   - Week 5-6: Testing with real members who are already onboarded

3. **Historical player data (guests/expired members):** ✅ **Import later if needed**
   - Kerry has the data but will take time to collect/clean
   - Can import in Week 3-4 or even post-launch
   - First-timer discount risk is minimal for March 15 (most people who would register have played before)

3. **TGF Plus tier:** ✅ **v1.1 - NOT IN MVP**
   - Focus MVP on Standard $75 membership only
   - Add TGF Plus ($200) in v1.1 after Standard is proven
   - Database will still have structure for future tier

4. **Pro-rated upgrade:** ✅ **Option B - Pro-rate based on remaining months**
   - Example: Paid $75 Standard in Jan, upgrades in June
   - Calculation: ($200 TGF Plus) × (6 months remaining / 12) = $100 for remainder
   - Will implement in v1.1 when TGF Plus launches

5. **First-timer tracking:** ✅ **Auto-detect - NEVER registered before**
   - System checks if email exists in `users` table OR `registrations` table
   - If email found ANYWHERE in database → NOT a first-timer (no discount)
   - If email completely new → Apply $25 first-timer discount
   - This means: Guests who played before, expired members, anyone who ever registered = no discount
   - Only people who have NEVER interacted with TGF = first-timer discount

6. **Authentication:** ✅ **Email/Password + Magic link ONLY (MVP)**
   - Social auth (Google, Facebook, Apple) deferred to v1.1
   - MVP keeps it simple: Email/password OR magic link
   - Supabase supports both natively

7. **Event Setup Dashboard Requirements:** ✅ **Confirmed + Enhanced**

   **Core Fields:**
   - Course selection (from course database)
   - Event date/time
   - Event type (9-hole, 18-hole, or both options)
   - **Base pricing** = What the HOST COURSE charges TGF (NOT what members pay)
     - Example: Course charges $50 for 18 holes → this is the base price
     - Should auto-populate from course database (future enhancement in v1.1)
     - MUST be editable (can override course's standard rate)
   - TGF markup ($8 for 9s, $15 for 18s, or custom)
   - Included games (Team MVP, CTP, HIO Pot selected by default)
   - Available add-on bundles (NET Games, GROSS Games)
   - Max players (optional)
   - Registration deadline (date/time when registration closes)

   **Registration Questions (Configurable):**
   - Toggle on/off: "Playing Partner Request?" (text field)
   - Toggle on/off: "Fellowship After?" (yes/no)
   - Ability to add custom questions (text field, dropdown, yes/no)
   - Questions can be marked as required or optional

   **Future Enhancement (v1.1):**
   - Auto-populate base pricing from `courses.tgf_negotiated_rate_9/18`
   - Save event as template for future reuse
