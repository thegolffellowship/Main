# The Golf Fellowship Platform

A modern membership and event management platform for The Golf Fellowship golf community.

## Overview

This platform replaces multiple disconnected systems (GoDaddy, Golf Genius, Excel) with a unified solution that:

- **Handles memberships** - Purchase, renewal, tracking, auto-expiration
- **Manages events** - Calendar, registration, payment in one flow
- **Processes payments** - Stripe integration with saved cards and wallet credits
- **Provides manager tools** - Real-time rosters, check-in, payment tracking
- **Delivers admin control** - Full CRUD for events, members, chapters

## Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | Next.js 14 (React) |
| Database | Supabase (PostgreSQL) |
| Authentication | Supabase Auth (Magic Link + Password) |
| Payments | Stripe |
| Hosting | Vercel |
| Styling | Tailwind CSS |
| Language | TypeScript |

## Getting Started

### Prerequisites

- Node.js 18.17 or later
- A Supabase account
- A Stripe account
- A Vercel account (for deployment)

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/thegolffellowship/Main.git
   cd Main
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env.local
   # Edit .env.local with your Supabase and Stripe keys
   ```

4. **Set up the database**
   - Go to your Supabase project
   - Open SQL Editor
   - Run the contents of `supabase/migrations/00001_initial_schema.sql`

5. **Start the development server**
   ```bash
   npm run dev
   ```

6. **Open in browser**
   - Visit [http://localhost:3000](http://localhost:3000)

## Documentation

- [**Setup Guide**](docs/SETUP_GUIDE.md) - Complete walkthrough for setting up Supabase, Stripe, and Vercel
- [**Architecture**](docs/ARCHITECTURE.md) - How the codebase is organized

## Project Structure

```
src/
├── app/                 # Pages and routes
│   ├── auth/           # Login, signup, callback
│   ├── events/         # Public event pages
│   ├── dashboard/      # Member portal
│   ├── manager/        # Chapter manager portal
│   └── admin/          # Admin portal
├── components/          # Reusable UI components
├── domains/            # Feature-specific business logic
├── lib/                # Shared utilities
│   ├── supabase/       # Database client
│   ├── stripe/         # Payment client
│   └── auth/           # Auth helpers
└── types/              # TypeScript types
```

## Key Features (MVP)

### For Members
- Sign up and manage profile
- Browse and register for events
- Pay with card or wallet balance
- View registration history
- Receive email confirmations

### For Managers
- View real-time event rosters
- Manual registration for cash payments
- Check-in players at events
- Export data for Golf Genius

### For Admins
- Create and manage events
- Manage membership types
- View all transactions
- Manage chapters and managers

## Development Roadmap

### Phase 1 - MVP (Current)
- Member accounts and authentication
- Event listing and registration
- Stripe payment integration
- Wallet/credits system
- Manager roster view
- Admin event management

### Phase 2 - Enhancement
- Automated email reminders
- Waitlist management
- Season contests
- Advanced reporting

### Phase 3 - Advanced
- SMS notifications
- Social features
- Player achievements
- Custom handicap tracking

## Contributing

This is a private project for The Golf Fellowship.

## License

Proprietary - All rights reserved.
