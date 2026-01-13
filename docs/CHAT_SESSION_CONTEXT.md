# TGF Platform - Chat Session Context & Decisions

This document captures all key decisions and context from the Kerry/Claude development sessions so nothing is lost if a session disconnects.

---

## Session: TGF App Architecture and MVP 1 (claude/membership-transaction-mvp-KZ1Ol)

**Status:** Recovered - all code saved to GitHub

### Key Decisions Made

#### 1. Membership Tiers

| Tier | Annual Cost | Event Discount | Strategy |
|------|-------------|----------------|----------|
| Standard | $75 | $0 | Lower upfront, standard event pricing |
| TGF Plus | $200 | -$10 on 9s, -$15 on 18s | Higher upfront, save on every event |
| Guest | $0 | +$10 on 9s, +$15 on 18s | Non-member premium |
| First Timer | $0 | Guest rate -$25 | One-time discount, first ever TGF event |

**Important:** First Timer discount is only for a player's very first TGF event EVER (anywhere), not per chapter.

#### 2. Game Pricing (100% to Prize Pool)

| Game | 9-Hole | 18-Hole | Notes |
|------|--------|---------|-------|
| Team MVP | $4 | $8 | Included free with entry |
| Closest to Pin | $2 | $4 | Included free with entry |
| Hole-in-One Pot | $1 | $2 | Included free with entry, accumulates |
| Individual Net | $9 | $18 | Members only |
| MVP | $4 | $8 | Members only, can split local/TGF-wide |
| Skins Gross | $9 | $18 | Open to all |
| Individual Gross | $4 | $8 | Open to all |

**Key:** All game revenue goes 100% to prize pool. TGF markup is on the BUNDLES.

#### 3. Bundle Pricing

**NET Games Bundle:** $16/$30
- Individual Net: $9/$18 (to prize pool)
- MVP: $4/$8 (to prize pool)
- TGF Markup: $3/$4

**GROSS Games Bundle:** $16/$30
- Skins Gross: $9/$18 (to prize pool)
- Individual Gross: $4/$8 (to prize pool)
- TGF Markup: $3/$4
- **Special Rule:** If < 12 players in GROSS bundle, converts to ½ Net Skins

**MVP Split Rule:** If multiple chapters have events on same day, MVP can split 50% local / 50% TGF-wide.

#### 4. Tee Configurations

| Category | Yardage | Age Requirement | Gender |
|----------|---------|-----------------|--------|
| Under 50 | 6300-6800 | < 50 years old | Any |
| 50-64 | 5800-6299 | 50-64 years old | Any |
| 65+ | 5300-5799 | 65+ years old | Any |
| Forward | 4800-5299 | Any | Women only* |

*Manager/admin can approve override for juniors, disability, special circumstances.

**Players can always choose LONGER tees than their age group.** A 51-year-old can still play Under 50 tees if they prefer.

#### 5. Event Pricing Formula

```
Standard Member = Course Cost + Included Games ($7) + TGF Markup ($8/$15)
TGF Plus Member = Standard Member - $10/$15
Guest           = Standard Member + $10/$15
First Timer     = Guest - $25
```

#### 6. Stripe Fees

- Stripe fee (2.9% + $0.30) is **passed to customer**
- Applied to the **total amount** (not calculated separately per item)
- Only applies to Stripe transactions, NOT wallet payments

#### 7. Events Can Offer Both 9 and 18

Tuesday 9-hole events can also offer an 18-hole option for players who want to come early and play a full round.

---

## Technical Decisions

### Tech Stack
- **Frontend:** Next.js 14 (React)
- **Database:** Supabase (PostgreSQL)
- **Payments:** Stripe
- **Hosting:** Vercel
- **Auth:** Supabase Auth (Magic link primary, password optional)

### Database Design Philosophy
- Comprehensive schema is the **blueprint** for the future
- MVP uses a **subset** of tables
- Tables exist from day 1, features are activated later
- No rebuilding required as features are added

### Data Storage
- All code in GitHub (version controlled)
- All documentation in `/docs` folder
- Database migrations in `/supabase/migrations`

---

## Still To Be Implemented

### MVP (v1.0)
- [ ] Auth flow (sign up, login, magic link)
- [ ] Admin: Create/edit events
- [ ] Admin: Manage courses, games, bundles
- [ ] Public: Event listing and details
- [ ] Registration flow with game selection
- [ ] Stripe payment integration
- [ ] Manager roster view
- [ ] Basic confirmation emails

### v1.1 (Quick Follows)
- [ ] Smart autofill (user preferences)
- [ ] Email templates
- [ ] Waitlist management
- [ ] Promo codes

### v2.0 (Major Features)
- [ ] Preferred partners system
- [ ] Handicap tracking
- [ ] Multi-day events
- [ ] Team events
- [ ] Batch operations
- [ ] AI assistant for managers

### v3.0 (Golf Genius Replacement)
- [ ] Scoring system
- [ ] Live leaderboards
- [ ] Pairings management
- [ ] Results entry
- [ ] Player development program

---

## Kerry's "ZERO Time" Philosophy

The core goal is reducing manager time to as close to zero as possible. TGF is about building community, not technical operations. Every feature should be evaluated against this principle:

1. **Automate everything possible**
2. **Make customer-facing operations self-service**
3. **Managers should be people managers, not technical managers**
4. **AI assistance where helpful**
5. **Quick, easy mobile experience (approaching "Amazon one-click")**

---

## Outstanding Questions (Answered)

1. ✅ **Refund policy:** Full refund up to 24 hours before event (minus transaction fees), after that refund side games but not green fees
2. ✅ **Membership expiration edge case:** If registered while active, can still play at member rate
3. ✅ **Cross-chapter play:** Free with active membership
4. ✅ **Waitlist priority:** FIFO (first in, first out)
5. ✅ **First-timer verification:** Auto-confirm members, first-timers just get the discount automatically for their very first event

---

## Files Created

### Core Application
- `/package.json` - Dependencies
- `/next.config.js` - Next.js config
- `/tsconfig.json` - TypeScript config
- `/tailwind.config.ts` - Styling config
- `/middleware.ts` - Auth middleware

### Database
- `/supabase/migrations/00001_initial_schema.sql` - Initial (deprecated)
- `/supabase/migrations/00002_comprehensive_schema.sql` - Full blueprint
- `/supabase/migrations/00003_mvp_schema.sql` - Original MVP
- `/supabase/migrations/00004_mvp_schema_corrected.sql` - **USE THIS ONE** (corrected)

### Documentation
- `/docs/SETUP_GUIDE.md` - How to set up external services
- `/docs/ARCHITECTURE.md` - System architecture
- `/docs/DATABASE_DIAGRAM.md` - Visual database map
- `/docs/CHAT_SESSION_CONTEXT.md` - This file

### Application Code
- `/src/app/page.tsx` - Home page
- `/src/app/auth/login/` - Login page
- `/src/app/auth/signup/` - Signup page
- `/src/app/events/page.tsx` - Events listing
- `/src/app/dashboard/page.tsx` - Member dashboard
- `/src/lib/supabase/` - Database utilities
- `/src/lib/stripe/` - Payment utilities
- `/src/lib/auth/` - Auth helpers
- `/src/types/` - TypeScript types

---

## Next Steps (When Resuming)

1. Set up external accounts (Supabase, Stripe, Vercel) - follow `/docs/SETUP_GUIDE.md`
2. Run database migration using `00004_mvp_schema_corrected.sql`
3. Build admin UI for event creation
4. Build registration flow
5. Integrate Stripe payments
6. Build manager roster view
7. Test with real event

---

*Last updated: January 2026*
