# TGF Platform - Architecture Overview

This document explains how the TGF Platform is organized and how the pieces fit together.

---

## Folder Structure

```
tgf-platform/
│
├── src/                          # All source code lives here
│   │
│   ├── app/                      # Pages and routes (Next.js App Router)
│   │   ├── page.tsx              # Home page (/)
│   │   ├── layout.tsx            # Root layout (wraps all pages)
│   │   ├── globals.css           # Global styles
│   │   │
│   │   ├── auth/                 # Authentication pages
│   │   │   ├── login/            # Login page (/auth/login)
│   │   │   ├── signup/           # Signup page (/auth/signup)
│   │   │   └── callback/         # Magic link handler
│   │   │
│   │   ├── events/               # Public event pages
│   │   │   ├── page.tsx          # Event list (/events)
│   │   │   └── [id]/             # Event details (/events/123)
│   │   │
│   │   ├── dashboard/            # Member portal (requires login)
│   │   │   ├── page.tsx          # Dashboard home
│   │   │   ├── wallet/           # Wallet management
│   │   │   └── registrations/    # My registrations
│   │   │
│   │   ├── manager/              # Chapter manager portal
│   │   │   ├── page.tsx          # Manager dashboard
│   │   │   └── events/           # Event management
│   │   │
│   │   └── admin/                # Admin portal (Kerry only)
│   │       ├── page.tsx          # Admin dashboard
│   │       ├── events/           # Event CRUD
│   │       ├── members/          # Member management
│   │       └── chapters/         # Chapter management
│   │
│   ├── components/               # Reusable UI components
│   │   ├── ui/                   # Basic components (buttons, inputs)
│   │   ├── layouts/              # Page layouts
│   │   └── forms/                # Form components
│   │
│   ├── domains/                  # Business logic by feature
│   │   ├── members/              # Member-related code
│   │   │   ├── components/       # Member-specific components
│   │   │   ├── services/         # Member business logic
│   │   │   └── hooks/            # Member React hooks
│   │   │
│   │   ├── events/               # Event-related code
│   │   ├── payments/             # Payment-related code
│   │   └── admin/                # Admin-related code
│   │
│   ├── lib/                      # Shared utilities
│   │   ├── supabase/             # Database client
│   │   ├── stripe/               # Payment client
│   │   ├── auth/                 # Authentication helpers
│   │   └── utils.ts              # General utilities
│   │
│   └── types/                    # TypeScript type definitions
│       └── database.ts           # Database types
│
├── supabase/
│   └── migrations/               # Database setup scripts
│
├── docs/                         # Documentation
│   ├── SETUP_GUIDE.md           # How to set up the project
│   └── ARCHITECTURE.md          # This file
│
├── public/                       # Static files (images, etc.)
│
└── Configuration files
    ├── package.json              # Dependencies
    ├── next.config.js            # Next.js settings
    ├── tailwind.config.ts        # Styling settings
    ├── tsconfig.json             # TypeScript settings
    └── middleware.ts             # Auth protection
```

---

## How Things Connect

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER'S BROWSER                          │
│  (Views pages, fills forms, clicks buttons)                     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         VERCEL (Hosting)                        │
│  Serves your website to visitors                                │
│  URL: https://tgf-platform.vercel.app                          │
└─────────────────────────────────────────────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│        SUPABASE          │    │         STRIPE           │
│  (Database + Auth)       │    │  (Payment Processing)    │
│                          │    │                          │
│  • Member data           │    │  • Credit card payments  │
│  • Event data            │    │  • Saved payment methods │
│  • Registrations         │    │  • Refunds               │
│  • Login sessions        │    │  • Webhooks              │
└──────────────────────────┘    └──────────────────────────┘
```

---

## Key Concepts

### 1. Pages vs Components

**Pages** are full screens that users visit via URL:
- `/` → Home page
- `/events` → Event list
- `/dashboard` → Member dashboard

**Components** are reusable building blocks:
- Buttons
- Forms
- Cards
- Navigation

### 2. Client vs Server

**Server Code** runs on Vercel's servers:
- Database queries
- Payment processing
- Protected operations

**Client Code** runs in the user's browser:
- Form interactions
- Button clicks
- Real-time updates

Files with `'use client'` at the top run in the browser.
Everything else runs on the server by default.

### 3. Authentication Flow

```
User clicks "Log In"
        │
        ▼
Enters email
        │
        ▼
System sends magic link to email
        │
        ▼
User clicks link in email
        │
        ▼
Link redirects to /auth/callback
        │
        ▼
Callback exchanges code for session
        │
        ▼
User is now logged in!
```

### 4. Payment Flow

```
User clicks "Pay"
        │
        ▼
App creates Stripe Payment Intent (server)
        │
        ▼
Stripe checkout form appears (client)
        │
        ▼
User enters card details
        │
        ▼
Stripe processes payment
        │
        ▼
Stripe sends webhook to our server
        │
        ▼
Server updates registration status
        │
        ▼
User sees confirmation
```

---

## Database Tables (Quick Reference)

| Table | What It Stores |
|-------|---------------|
| `chapters` | San Antonio, Austin, etc. |
| `membership_types` | Types of memberships you sell |
| `members` | All people (members, guests, prospects) |
| `member_memberships` | Membership purchase history |
| `games` | NET Skins, CTP, etc. |
| `events` | Your golf events |
| `event_games` | Which games are at each event |
| `registrations` | Who's signed up for what |
| `registration_games` | Which games each player selected |
| `transactions` | All money movement |
| `wallet_transactions` | Wallet balance changes |
| `feature_flags` | Toggle features on/off |

---

## Adding New Features

### Adding a New Page

1. Create a folder in `src/app/` matching the URL you want
2. Add a `page.tsx` file inside
3. Export a default React component

Example: To add `/about`:
```
src/app/about/page.tsx
```

### Adding a New Database Table

1. Create a migration file in `supabase/migrations/`
2. Write the SQL to create the table
3. Add types in `src/types/database.ts`
4. Run the migration in Supabase SQL Editor

### Adding a New API Endpoint

1. Create a folder in `src/app/api/`
2. Add a `route.ts` file inside
3. Export HTTP methods (GET, POST, etc.)

Example: To add `/api/members`:
```
src/app/api/members/route.ts
```

---

## Security Notes

1. **Never commit `.env.local`** - It contains secrets
2. **Use the service role key only on the server** - Never in client code
3. **All database queries from clients go through Row Level Security** - Users can only see their own data
4. **Card numbers never touch our server** - Stripe handles them

---

## Common Tasks

### View Database Data
1. Go to Supabase Dashboard
2. Click "Table Editor"
3. Select a table

### Check Logs
1. **App logs:** Vercel Dashboard → Your Project → Functions
2. **Database logs:** Supabase → Database → Logs
3. **Payment logs:** Stripe Dashboard → Payments

### Update Something
1. Make changes to code
2. Commit and push to GitHub
3. Vercel auto-deploys (takes ~2 minutes)

---

*For setup instructions, see [SETUP_GUIDE.md](./SETUP_GUIDE.md)*
