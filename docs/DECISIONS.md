# TGF Platform - Architectural Decisions & Context

This document captures the key decisions, reasoning, and context from the platform architecture discussions. It serves as a reference for understanding *why* things were built a certain way.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Technology Stack Decisions](#technology-stack-decisions)
3. [Database Architecture](#database-architecture)
4. [User & Membership Model](#user--membership-model)
5. [Event & Registration System](#event--registration-system)
6. [Pricing & Financial Tracking](#pricing--financial-tracking)
7. [Games & Bundles](#games--bundles)
8. [Wallet System](#wallet-system)
9. [Tee Box Clarification](#tee-box-clarification)
10. [MVP vs Future Features](#mvp-vs-future-features)
11. [Open Questions](#open-questions)

---

## Project Overview

### The Problem
TGF was using multiple disconnected systems:
- **GoDaddy** - Website and basic forms
- **Golf Genius** - Event management
- **Excel** - Financial tracking, member lists
- **Manual processes** - Email coordination, roster management

This caused:
- Data duplication and inconsistency
- Manual reconciliation between systems
- No real-time visibility into registration/payment status
- Time-consuming administrative work

### The Solution
A unified platform that handles:
- Membership management (purchase, renewal, tracking)
- Event registration with integrated payment
- Real-time roster management
- Financial tracking with clear TGF profit visibility
- Role-based access for members, managers, and admins

---

## Technology Stack Decisions

### Next.js 14 (App Router)
**Why:** Modern React framework with:
- Server-side rendering for SEO and performance
- API routes built-in (no separate backend needed)
- File-based routing (intuitive structure)
- Strong TypeScript support

### Supabase (PostgreSQL)
**Why:**
- Full PostgreSQL database (not limited NoSQL)
- Built-in authentication (magic links, password)
- Row Level Security for data protection
- Real-time subscriptions available
- Generous free tier for MVP

### Stripe
**Why:**
- Industry standard for payments
- Saved payment methods (no re-entering cards)
- Webhooks for reliable payment confirmation
- Good documentation and support
- PCI compliance handled by Stripe

### Vercel
**Why:**
- Seamless Next.js deployment
- Automatic deploys from GitHub
- Edge functions for performance
- Free tier sufficient for launch

### Tailwind CSS
**Why:**
- Utility-first CSS (fast development)
- Consistent design system
- Small bundle size (only used styles)
- Works well with component architecture

---

## Database Architecture

### Two Schema Versions

We have two schema files:

1. **`00002_comprehensive_schema.sql`** - The full vision
   - All features discussed
   - Complex hierarchy (country/region/state/chapter)
   - Roles and permissions system
   - Multi-day events, teams, season contests
   - Course communications and quotes
   - Gift cards, promo codes

2. **`00003_mvp_schema.sql`** - What we actually deploy
   - Simplified for launch
   - 18 core tables
   - Same structure, fewer features
   - Can migrate to comprehensive later

**Decision:** Start with MVP schema, expand as needed. The comprehensive schema is our "north star" blueprint.

### Key Table Naming

| Original Idea | Final Decision | Reasoning |
|---------------|----------------|-----------|
| `members` | `users` | Not everyone is a member (guests, prospects, course contacts) |
| `chapters` | `organizations` | Allows future hierarchy (regions, countries) |
| `membership_purchases` | `user_memberships` | Clearer relationship |

### Soft Deletes
Most tables have `deleted_at` column instead of hard deletes. This preserves:
- Historical data for reporting
- Audit trail
- Ability to restore mistakes

---

## User & Membership Model

### User Status Flow

```
prospect → guest → active_member → expired_member
    ↓         ↓           ↓              ↓
(never    (played     (paying       (lapsed,
 played)   once)       member)       can renew)
                          ↓
                    former_member
                    (explicitly left)
```

**Decision:** Track the full lifecycle, not just "member or not"

### Why "Users" Not "Members"

The system tracks multiple person types:
- **Prospects** - Signed up but never played
- **Guests** - Played but not members (pay guest rate)
- **First-timers** - Special pricing for first event
- **Active Members** - Paid membership, get member pricing
- **Expired Members** - Lapsed, need to renew
- **Course Contacts** - Staff at golf courses (future)
- **Managers** - Chapter managers with elevated access

**Decision:** One table for all people, with `status` field to differentiate

### Membership Tracking

**Current membership is denormalized:**
```sql
users.membership_expires_at -- Quick lookup for pricing
users.current_membership_id -- Link to active membership record
```

**Full history in `user_memberships`:**
- Every purchase/renewal creates a new row
- Can see: when they first joined, gaps in membership, renewal patterns

---

## Event & Registration System

### Event Types

| Type | Description | Example |
|------|-------------|---------|
| `9_hole` | Standard 9-hole event | Tuesday 9s |
| `18_hole` | Standard 18-hole event | Saturday 18s |
| `championship` | Special tournament | Club Championship |
| `scramble` | Team scramble format | Member-Guest |
| `social` | Non-golf gathering | Holiday Party |

### Event Status Lifecycle

```
draft → published → registration_closed → completed
                         ↓
                     cancelled
```

- **Draft:** Manager setting up, not visible to players
- **Published:** Open for registration
- **Registration Closed:** Past deadline, event upcoming
- **Completed:** Event finished, results posted
- **Cancelled:** Event cancelled (refunds processed)

### Player Types at Registration

When a player registers, we capture their type *at that moment*:

| Player Type | Description | Pricing |
|-------------|-------------|---------|
| `member` | Has active membership | Member rate (often $0 base) |
| `guest` | No membership | Guest rate (includes surcharge) |
| `first_timer` | First TGF event ever | Special discounted rate |

**Decision:** Capture player type at registration time because:
- Their status might change later
- Need accurate historical pricing data
- First-timer discount only applies once

### Registration Pricing Capture

All pricing is captured at registration time:
```
subtotal       -- Base + add-ons (before tax)
tax_amount     -- Calculated tax
late_fee_amount -- If registered after deadline
discount_amount -- First-timer or promo discount
total_amount   -- Final amount owed
```

**Why:** Prices may change, but we need to know what they actually owed/paid.

### Waitlist System

When event is full:
1. New registrations go to waitlist
2. `is_waitlisted = true`, `waitlist_position` assigned
3. If spot opens, player gets notified
4. They have limited time to confirm/pay
5. If they don't, next in line gets offer

---

## Pricing & Financial Tracking

### Price Breakdown per Event

Each event has pricing for each player type:

```sql
event_pricing:
  event_id
  player_type      -- 'member', 'guest', 'first_timer'
  base_price       -- What player pays
  course_cost      -- What TGF pays the course
  tgf_markup       -- TGF keeps this (base_price - course_cost)
  tax_rate         -- Texas sales tax (8.25%)
```

**Example:**
- Guest pays $45
- TGF pays course $35
- TGF markup = $10
- Tax = $45 × 8.25% = $3.71
- Total to guest = $48.71

### Where Every Dollar Goes

```
Player Payment ($64.89)
├── Stripe Fee ($2.10) → Stripe
├── Tax ($2.89) → Texas tax obligation
└── TGF Revenue ($59.90)
    ├── Course Cost ($35.00) → Pay course after event
    ├── Prize Pools ($14.90) → Pay winners
    └── TGF Profit ($10.00) → TGF keeps
```

### Transaction Table Purpose

The `transactions` table records every dollar movement:
- Membership purchases
- Event registrations
- Wallet deposits/credits
- Refunds
- Adjustments

Each transaction includes:
- `amount` - Total money
- `revenue_amount` - TGF revenue portion
- `cost_amount` - Costs (course, prizes)
- `tgf_profit` - TGF profit (markup)
- `tax_amount` - Sales tax

**Decision:** Full financial breakdown for reporting, tax filing, and profit tracking

### Stripe Fee Clarification

**Important:** Stripe fee is applied to the total transaction amount (base + add-ons), not calculated separately per line item. The Stripe fee comes out of what TGF receives.

---

## Games & Bundles

### Game Types

| Game | Type | Membership Required | Included Free |
|------|------|---------------------|---------------|
| Team MVP | team | No | Yes |
| CTP (Closest to Pin) | skill_contest | No | Yes |
| Hole-in-One Pot | pot | No | Yes |
| Individual Net | individual_net | **Yes** | No |
| Net Skins | skins | **Yes** | No |
| Individual Gross | individual_gross | No | No |
| Gross Skins | skins | No | No |
| Long Drive | skill_contest | No | No |

### Bundles

Bundles package multiple games at a discount:

| Bundle | Contains | Price | Requires Membership |
|--------|----------|-------|---------------------|
| NET Games | Individual Net + Net Skins | $15-25 | Yes |
| GROSS Games | Individual Gross + Gross Skins | $15-25 | No |

**Decision:** NET games require membership because they use handicap-adjusted scoring (members' primary benefit)

### Price vs Cost

Every game/bundle has:
- **Price** - What player pays
- **Cost** - What goes to prize pool

The difference is TGF markup.

Example NET Bundle:
- Player pays: $25
- Prize pool: $20
- TGF markup: $5

---

## Wallet System

### Purpose

The wallet system handles:
- **Credits** - Winnings from games
- **Refunds** - Money back goes to wallet (optional)
- **Prepayment** - Add funds for faster checkout
- **Comps** - Manager-added credits

### How It Works

User has `wallet_balance` on their profile.

Every balance change creates a `wallet_transactions` row:
- `amount` - Change (+credit, -debit)
- `balance_before` - Previous balance
- `balance_after` - New balance
- `source` - Why (winnings, deposit, payment, refund)
- `description` - Human readable ("Won CTP - Tuesday 9s")

### Using Wallet at Checkout

Players can:
1. Pay full amount from wallet
2. Pay full amount from card
3. Split payment (wallet + card)

**Decision:** Wallet is always optional - player chooses at checkout

---

## Tee Box Clarification

### The Preference Question

Registration asks: "Which tees will you play?"

Options:
- Under 50 (typically plays back/championship tees)
- 50-64 (mid tees)
- 65+ (forward tees)
- Forward (typically women)

### Important Clarification

**Women-only rule for Forward tees:**
> Only women can select Forward tees unless we provide an override for someone like a junior.

This means:
- Forward tees are primarily for women players
- Exceptions can be made (juniors, physical limitations)
- System should allow manager override

**Implementation note:** This requires either:
- Gender field on user profile, OR
- Manager override capability for exceptions

---

## MVP vs Future Features

### MVP (Phase 1) - Launch Features

| Category | Features |
|----------|----------|
| **Auth** | Magic link email login, password option |
| **Members** | Profile, membership purchase, wallet |
| **Events** | Browse, register, pay, cancel |
| **Payments** | Stripe cards, wallet balance |
| **Manager** | Roster view, manual registration, check-in |
| **Admin** | Event CRUD, member management |

### Future (V1.5/V2) Features

| Feature | Priority | Notes |
|---------|----------|-------|
| Automated email reminders | High | Event reminders, payment reminders |
| Waitlist auto-promotion | High | Auto-offer spots to waitlist |
| Smart partner matching | Medium | Auto-pair mutual preferred partners |
| Season contests | Medium | Points races, leaderboards |
| SMS notifications | Medium | Optional text alerts |
| Custom handicap tracking | Low | TGF's own handicap system |
| GHIN sync | Low | Import handicaps from GHIN |
| Course portal | Low | Course contacts can view bookings |
| Gift cards | Low | Purchase and redemption |
| Promo codes | Low | Discount codes |

### Feature Flags

The system uses feature flags to enable/disable features:

```sql
feature_flags:
  - wallet_system (enabled)
  - guest_registration (enabled)
  - waitlist (enabled)
  - late_fees (enabled)
  - stripe_payments (enabled)
  - season_contests (disabled)
  - ghin_sync (disabled)
```

**Decision:** Build the comprehensive schema but use flags to expose features gradually

---

## Open Questions

These questions were raised but may not have been fully resolved:

### Member Information
- What other info do you collect about people?
- Do you track how they heard about TGF when they join?
- Any referral tracking needed?

### Tee Preferences
- Do we need a gender field to enforce Forward tee rules?
- What's the process for manager overrides?

### Course Management
- What other course info needs tracking?
- Do you track course contact people separately?
- Any course-specific policies needed?

### Games
- Complete list of all games currently offered?
- What are exact prices for 9 vs 18?
- Any games missing from the current list?

### Financial
- What's typical markup on events?
- Different markup for 9 vs 18?
- How do you currently categorize income/expenses for reporting?

### Event Management
- What other info needs capturing per event?
- Any special event types with different rules?
- What notifications go out and when?

---

## Summary

The TGF Platform consolidates multiple disconnected systems into one unified solution. Key architectural decisions include:

1. **PostgreSQL with Supabase** - Full relational database for complex business logic
2. **Users table for all people** - Not just members, enables full lifecycle tracking
3. **Captured pricing at registration** - Historical accuracy even if prices change
4. **Comprehensive transaction tracking** - Every dollar accounted for with breakdown
5. **MVP + Comprehensive schemas** - Start simple, expand to full vision
6. **Feature flags** - Gradual rollout of functionality

The platform is designed to grow with TGF while solving immediate pain points around registration, payment, and roster management.

---

*Document created from architecture discussions - January 2025*
