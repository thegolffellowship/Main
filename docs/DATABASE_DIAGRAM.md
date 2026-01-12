# TGF Platform - Database Diagram

This document shows how the database tables connect to each other.

---

## MVP Core Tables - Visual Map

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                   USERS & ACCESS                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────┐         ┌─────────────────────┐                        │
│  │       users         │         │   organizations     │                        │
│  ├─────────────────────┤         ├─────────────────────┤                        │
│  │ id visib            │         │ id                  │                        │
│  │ email               │    ┌───►│ name (SA, Austin)   │                        │
│  │ first_name          │    │    │ code (SA, AUS)      │                        │
│  │ last_name           │    │    │ parent_id ─────────┐│ (for hierarchy)        │
│  │ phone               │    │    │ level_id           ││                        │
│  │ home_organization_id├────┘    │ timezone           │▼                        │
│  │ status              │         └─────────────────────┘                        │
│  │ wallet_balance      │                   ▲                                    │
│  │ stripe_customer_id  │                   │                                    │
│  │ membership_expires  │         ┌─────────┴───────────┐                        │
│  └─────────────────────┘         │                     │                        │
│           │                      │                     │                        │
│           │              ┌───────┴───────┐    ┌────────┴────────┐               │
│           │              │  user_roles   │    │     roles       │               │
│           │              ├───────────────┤    ├─────────────────┤               │
│           └─────────────►│ user_id       │    │ id              │               │
│                          │ role_id ──────┼───►│ name (Admin,    │               │
│                          │ organization_id    │   Manager, etc) │               │
│                          └───────────────┘    │ level           │               │
│                                               └─────────────────┘               │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                                   MEMBERSHIPS                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────┐         ┌─────────────────────┐                        │
│  │  membership_types   │         │  user_memberships   │                        │
│  ├─────────────────────┤         ├─────────────────────┤                        │
│  │ id                  │◄────────┤ membership_type_id  │                        │
│  │ name (Annual)       │         │ user_id ────────────┼───► users.id           │
│  │ price ($300)        │         │ starts_at           │                        │
│  │ duration_months (12)│         │ expires_at          │                        │
│  │ benefits            │         │ amount_paid         │                        │
│  └─────────────────────┘         │ is_active           │                        │
│                                  │ transaction_id ─────┼───► transactions.id    │
│                                  └─────────────────────┘                        │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                                 COURSES & EVENTS                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────┐         ┌─────────────────────────────┐               │
│  │      courses        │         │          events             │               │
│  ├─────────────────────┤         ├─────────────────────────────┤               │
│  │ id                  │◄────────┤ course_id                   │               │
│  │ name                │         │ organization_id ────────────┼──► organizations
│  │ address             │         │ id                          │               │
│  │ city, state         │         │ title                       │               │
│  │ phone               │         │ event_date                  │               │
│  │ tee_boxes (data)    │         │ start_time                  │               │
│  │ standard_rates      │         │ max_players                 │               │
│  │ contracted_rates    │         │ status (draft/published)    │               │
│  │ cancellation_policy │         │ registration_opens_at       │               │
│  └─────────────────────┘         │ registration_closes_at      │               │
│                                  └─────────────────────────────┘               │
│                                               │                                 │
│                          ┌────────────────────┼────────────────────┐            │
│                          ▼                    ▼                    ▼            │
│              ┌───────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │
│              │   event_pricing   │  │   event_games   │  │  registrations  │   │
│              ├───────────────────┤  ├─────────────────┤  │  (see below)    │   │
│              │ event_id          │  │ event_id        │  └─────────────────┘   │
│              │ player_type       │  │ game_id ────────┼──► games               │
│              │ base_price        │  │ bundle_id ──────┼──► bundles             │
│              │ course_cost       │  │ is_included     │                        │
│              │ tgf_markup        │  │ price_override  │                        │
│              │ tax_rate          │  └─────────────────┘                        │
│              └───────────────────┘                                              │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                                 GAMES & BUNDLES                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────┐         ┌─────────────────────┐                        │
│  │       games         │         │      bundles        │                        │
│  ├─────────────────────┤         ├─────────────────────┤                        │
│  │ id                  │◄──┐     │ id                  │                        │
│  │ name (CTP, Skins)   │   │     │ name (NET, GROSS)   │                        │
│  │ game_type           │   │     │ default_price_9     │                        │
│  │ scoring_type        │   │     │ default_price_18    │                        │
│  │ requires_membership │   │     │ requires_membership │                        │
│  │ default_price_9     │   │     └─────────────────────┘                        │
│  │ default_price_18    │   │              │                                     │
│  │ default_cost_9      │   │              ▼                                     │
│  │ default_cost_18     │   │     ┌─────────────────────┐                        │
│  └─────────────────────┘   │     │   bundle_games      │                        │
│                            │     ├─────────────────────┤                        │
│                            └─────┤ game_id             │                        │
│                                  │ bundle_id           │                        │
│                                  └─────────────────────┘                        │
│                                                                                  │
│  Example:                                                                        │
│  NET Bundle contains: Individual Net + Net Skins                                │
│  GROSS Bundle contains: Individual Gross + Gross Skins                          │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                                 REGISTRATIONS                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────┐                            │
│  │               registrations                      │                            │
│  ├─────────────────────────────────────────────────┤                            │
│  │ id                                              │                            │
│  │ event_id ───────────────────────────────────────┼──► events.id               │
│  │ user_id ────────────────────────────────────────┼──► users.id                │
│  │ player_type (member/guest/first_timer)          │                            │
│  │                                                 │                            │
│  │ ─── PRICING AT TIME OF REGISTRATION ───        │                            │
│  │ subtotal                                        │                            │
│  │ tax_amount                                      │                            │
│  │ late_fee_amount                                 │                            │
│  │ discount_amount                                 │                            │
│  │ total_amount                                    │                            │
│  │                                                 │                            │
│  │ ─── PAYMENT ───                                │                            │
│  │ amount_paid                                     │                            │
│  │ payment_status (pending/paid/refunded)          │                            │
│  │ payment_method (stripe/wallet/cash)             │                            │
│  │ stripe_payment_intent_id                        │                            │
│  │ wallet_amount_used                              │                            │
│  │                                                 │                            │
│  │ ─── STATUS ───                                 │                            │
│  │ is_waitlisted                                   │                            │
│  │ checked_in_at                                   │                            │
│  │ cancelled_at                                    │                            │
│  │                                                 │                            │
│  │ ─── RESPONSES ───                              │                            │
│  │ responses (tee preference, partner request)     │                            │
│  └─────────────────────────────────────────────────┘                            │
│                          │                                                      │
│                          ▼                                                      │
│              ┌─────────────────────┐                                            │
│              │ registration_games  │                                            │
│              ├─────────────────────┤                                            │
│              │ registration_id     │                                            │
│              │ event_game_id ──────┼──► event_games.id                          │
│              │ price (at purchase) │                                            │
│              └─────────────────────┘                                            │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              FINANCIAL TRACKING                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────┐                            │
│  │               transactions                       │                            │
│  ├─────────────────────────────────────────────────┤                            │
│  │ id                                              │                            │
│  │ user_id ────────────────────────────────────────┼──► users.id                │
│  │                                                 │                            │
│  │ ─── WHAT TYPE ───                              │                            │
│  │ type (membership_purchase, event_registration,  │                            │
│  │       wallet_deposit, wallet_credit, refund)    │                            │
│  │                                                 │                            │
│  │ ─── MONEY BREAKDOWN ───                        │                            │
│  │ amount (total)                                  │                            │
│  │ revenue_amount (TGF keeps)                      │                            │
│  │ cost_amount (course fees, prize pools)          │                            │
│  │ tgf_profit (markup)                             │                            │
│  │ tax_amount (sales tax)                          │                            │
│  │                                                 │                            │
│  │ ─── LINKS ───                                  │                            │
│  │ registration_id ────────────────────────────────┼──► registrations.id        │
│  │ membership_id ──────────────────────────────────┼──► user_memberships.id     │
│  │ stripe_payment_intent_id                        │                            │
│  │                                                 │                            │
│  │ ─── STATUS ───                                 │                            │
│  │ status (completed/pending/failed)               │                            │
│  │ idempotency_key (prevents double-charge)        │                            │
│  └─────────────────────────────────────────────────┘                            │
│                                                                                  │
│  ┌─────────────────────────────────────────────────┐                            │
│  │           wallet_transactions                    │                            │
│  ├─────────────────────────────────────────────────┤                            │
│  │ id                                              │                            │
│  │ user_id ────────────────────────────────────────┼──► users.id                │
│  │ amount (+credit / -debit)                       │                            │
│  │ balance_before                                  │                            │
│  │ balance_after                                   │                            │
│  │ description ("Won CTP - Tuesday 9s")            │                            │
│  │ source (deposit/winnings/refund/payment)        │                            │
│  │ transaction_id ─────────────────────────────────┼──► transactions.id         │
│  └─────────────────────────────────────────────────┘                            │
│                                                                                  │
│  ┌─────────────────────────────────────────────────┐                            │
│  │         event_financial_summary                  │                            │
│  ├─────────────────────────────────────────────────┤                            │
│  │ event_id ───────────────────────────────────────┼──► events.id               │
│  │                                                 │                            │
│  │ total_registrations                             │                            │
│  │ total_revenue                                   │                            │
│  │ member_revenue                                  │                            │
│  │ guest_revenue                                   │                            │
│  │ addon_revenue (bundles)                         │                            │
│  │                                                 │                            │
│  │ course_cost (pay to course)                     │                            │
│  │ prize_pool (pay to winners)                     │                            │
│  │ tgf_markup_total (TGF keeps)                    │                            │
│  │ sales_tax_collected                             │                            │
│  │                                                 │                            │
│  │ net_profit                                      │                            │
│  └─────────────────────────────────────────────────┘                            │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## How Data Flows - Registration Example

```
STEP 1: User Visits Event Page
──────────────────────────────
                    ┌──────────────┐
                    │    events    │
                    │  (Tuesday 9s)│
                    └──────┬───────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌─────────────────┐ ┌─────────────┐ ┌─────────────────┐
│  event_pricing  │ │ event_games │ │     courses     │
│ member: $0      │ │ Team MVP ✓  │ │ Canyon Springs  │
│ guest: $45      │ │ CTP ✓       │ │ 123 Golf Lane   │
└─────────────────┘ │ NET Bundle  │ └─────────────────┘
                    │ GROSS Bundle│
                    └─────────────┘


STEP 2: User Registers
──────────────────────
┌──────────────┐
│    users     │
│ John Doe     │◄─────── User logs in or creates account
│ Member       │
│ Wallet: $50  │
└──────┬───────┘
       │
       ▼
┌───────────────────────────────────────────────┐
│              registrations                     │
│ event_id: Tuesday 9s                          │
│ user_id: John Doe                             │
│ player_type: member                           │
│ subtotal: $15 (NET Bundle only, base is $0)   │
│ tax: $1.24                                    │
│ total: $16.24                                 │
│ payment_status: pending                       │
│ responses: {tee: "50-64", fellowship: true}   │
└───────────────────────────────────────────────┘
       │
       ▼
┌───────────────────────────────────────────────┐
│           registration_games                   │
│ NET Bundle: $15                               │
└───────────────────────────────────────────────┘


STEP 3: User Pays
─────────────────
┌──────────────┐     ┌──────────────┐
│    Stripe    │────►│ transactions │
│   $16.24     │     │ amount: 16.24│
└──────────────┘     │ type: event  │
                     │ tgf_profit: 3│
                     │ prize_pool:12│
                     │ tax: 1.24    │
                     └──────────────┘
                            │
       ┌────────────────────┴────────────────────┐
       ▼                                         ▼
┌─────────────────┐                    ┌─────────────────┐
│  registrations  │                    │wallet_transactions│
│ payment_status: │                    │ (if wallet used) │
│   PAID ✓        │                    └─────────────────┘
└─────────────────┘


STEP 4: Manager Views Roster
────────────────────────────
┌────────────────────────────────────────────────────────────┐
│                    MANAGER ROSTER VIEW                      │
├────────────────────────────────────────────────────────────┤
│ Tuesday 9s at Canyon Springs - Jan 21, 2025                │
│ 24 players registered                                       │
├──────────────┬────────┬─────────────┬────────┬─────────────┤
│ Name         │ Type   │ Games       │ Paid   │ Checked In  │
├──────────────┼────────┼─────────────┼────────┼─────────────┤
│ John Doe     │ Member │ NET Bundle  │ ✓ $16  │ ○           │
│ Jane Smith   │ Guest  │ GROSS       │ ✓ $62  │ ○           │
│ Bob Wilson   │ Member │ (base only) │ ✓ $0   │ ○           │
└──────────────┴────────┴─────────────┴────────┴─────────────┘
│                                                             │
│  Financial Summary:                                         │
│  ├── Total Collected: $892.40                              │
│  ├── Course Payment Due: $600.00                           │
│  ├── Prize Pools: $180.00                                  │
│  ├── TGF Profit: $72.00                                    │
│  └── Tax Collected: $40.40                                 │
└────────────────────────────────────────────────────────────┘
```

---

## Financial Flow - Where Every Dollar Goes

```
PLAYER PAYS $64.89 FOR TUESDAY 9s WITH NET BUNDLE

                         $64.89 total
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
   ┌──────────┐      ┌──────────┐      ┌──────────┐
   │  Stripe  │      │   Tax    │      │  TGF     │
   │   Fee    │      │ Collected│      │ Revenue  │
   │  $2.10   │      │  $2.89   │      │  $59.90  │
   └──────────┘      └──────────┘      └──────────┘
                           │                  │
                           ▼                  │
                    ┌──────────┐             │
                    │Texas Tax │             │
                    │ Obligation│             │
                    └──────────┘             │
                                             │
         ┌───────────────────────────────────┼───────────────────────────────────┐
         ▼                   ▼               ▼               ▼                   ▼
   ┌──────────┐      ┌──────────┐     ┌──────────┐    ┌──────────┐       ┌──────────┐
   │ Course   │      │ HIO Pot  │     │Game Pots │    │ TGF      │       │ TGF      │
   │ Green+Cart│      │ (Holding)│     │(Payout)  │    │ Markup   │       │ Markup   │
   │  $35.00  │      │  $2.00   │     │ $12.90   │    │ (Event)  │       │ (Bundle) │
   └──────────┘      └──────────┘     └──────────┘    │  $7.00   │       │  $3.00   │
        │                 │                │          └──────────┘       └──────────┘
        ▼                 ▼                ▼                │                   │
   Pay Course       Accumulates      Pay Winners           └───────────────────┘
   after event      until won        after event                     │
                                                                     ▼
                                                              ┌──────────────┐
                                                              │  TGF Profit  │
                                                              │    $10.00    │
                                                              └──────────────┘


TRACKED IN DATABASE:
────────────────────
transactions table:
├── amount: 64.89
├── revenue_amount: 59.90
├── cost_amount: 49.90 (course + prizes)
├── tgf_profit: 10.00
├── tax_amount: 2.89
└── (Stripe fee tracked separately or in metadata)

event_financial_summary:
├── total_revenue: (sum for event)
├── course_cost: (sum for event)
├── prize_pool: (sum for event)
├── tgf_markup_total: (sum for event)
└── sales_tax_collected: (sum for event)
```

---

## Entity Relationship Summary

```
users ─────────┬─────────────────────────────────────────────────────────────┐
               │                                                             │
               ├──► user_roles ──► roles                                     │
               │                                                             │
               ├──► user_memberships ──► membership_types                    │
               │                                                             │
               ├──► registrations ──┬──► events ──┬──► organizations         │
               │                    │             │                          │
               │                    │             ├──► courses               │
               │                    │             │                          │
               │                    │             ├──► event_pricing         │
               │                    │             │                          │
               │                    │             └──► event_games ──┬──► games
               │                    │                                │
               │                    │                                └──► bundles
               │                    │                                       │
               │                    └──► registration_games                  │
               │                                                             │
               ├──► transactions ───────────────────────────────────────────┤
               │                                                             │
               └──► wallet_transactions ─────────────────────────────────────┘
```

---

## What Each Table Stores (Quick Reference)

| Table | What It Holds | Example |
|-------|---------------|---------|
| `users` | Every person | John Doe, jane@email.com, Member, $50 wallet |
| `organizations` | Chapters, regions | San Antonio, Austin |
| `roles` | Permission levels | Admin, Manager, Member |
| `user_roles` | Who has what role where | John is Manager of Austin |
| `membership_types` | Membership products | Annual Membership, $300/year |
| `user_memberships` | Purchase history | John bought Annual on Jan 1 |
| `courses` | Golf courses | Canyon Springs, 123 Golf Lane |
| `events` | Calendar entries | Tuesday 9s, Jan 21, Canyon Springs |
| `event_pricing` | Price per player type | Member: $0, Guest: $45 |
| `games` | Contest types | Team MVP, CTP, Individual Net |
| `bundles` | Game packages | NET Bundle ($15), GROSS Bundle ($15) |
| `event_games` | Games at each event | Tuesday 9s has: Team MVP, CTP, NET, GROSS |
| `registrations` | Who's playing | John registered for Tuesday 9s |
| `registration_games` | Selected add-ons | John selected NET Bundle |
| `transactions` | Money movement | John paid $16.24 for Tuesday 9s |
| `wallet_transactions` | Wallet changes | John won $20 CTP, balance now $70 |
| `event_financial_summary` | Event totals | Tuesday 9s: $892 revenue, $72 profit |

---

*This diagram reflects the MVP tables. Additional tables (handicaps, teams, promo codes, etc.) exist in the schema but aren't shown here for clarity.*
