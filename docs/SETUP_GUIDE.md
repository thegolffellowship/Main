# TGF Platform - Complete Setup Guide

This guide will walk you through setting up all the external services needed to run the TGF Platform. Follow each step carefully.

---

## Table of Contents

1. [Overview - What We're Setting Up](#overview)
2. [Step 1: Create a Supabase Account (Database)](#step-1-supabase)
3. [Step 2: Create a Stripe Account (Payments)](#step-2-stripe)
4. [Step 3: Create a Vercel Account (Hosting)](#step-3-vercel)
5. [Step 4: Set Up Your Database](#step-4-database-setup)
6. [Step 5: Connect Everything](#step-5-connect)
7. [Step 6: Deploy Your App](#step-6-deploy)
8. [Troubleshooting](#troubleshooting)

---

## Overview - What We're Setting Up {#overview}

Think of the TGF Platform like a restaurant:

| Component | Restaurant Analogy | What It Does |
|-----------|-------------------|--------------|
| **Supabase** | The kitchen & filing cabinets | Stores all your data (members, events, payments) and handles logins |
| **Stripe** | The cash register | Processes credit card payments securely |
| **Vercel** | The building itself | Hosts your website so people can visit it |
| **The Code** | The recipes & staff | The application logic that makes everything work |

**Time needed:** About 1-2 hours for initial setup

**What you'll need:**
- A computer with internet access
- Your email address
- A credit card (for Stripe - you won't be charged during testing)
- Your phone (for two-factor authentication)

---

## Step 1: Create a Supabase Account {#step-1-supabase}

**Supabase** is your database. It stores everything: member info, events, payments, etc.

### 1.1 Create Account

1. Go to [https://supabase.com](https://supabase.com)
2. Click **"Start your project"** (green button)
3. Sign up with your GitHub account OR email
   - If you don't have GitHub, just use email - that's fine
4. Verify your email if prompted

### 1.2 Create Your First Project

1. Click **"New Project"**
2. Fill in the form:
   - **Name:** `tgf-platform`
   - **Database Password:** Create a strong password and **SAVE IT SOMEWHERE SAFE** (you'll need it later)
   - **Region:** Choose "East US" (closest to Texas)
   - **Pricing Plan:** Free tier is fine to start
3. Click **"Create new project"**
4. Wait 2-3 minutes for setup to complete

### 1.3 Get Your API Keys

Once your project is created:

1. In the left sidebar, click **"Settings"** (gear icon)
2. Click **"API"** under "Configuration"
3. You'll see three important values:
   - **Project URL** - looks like `https://xxxxx.supabase.co`
   - **anon public** - a long string starting with `eyJ...`
   - **service_role** - another long string (click "Reveal" to see it)

4. **Copy these somewhere safe** - you'll need them in Step 5

### 1.4 Enable Email Authentication

1. In the left sidebar, click **"Authentication"**
2. Click **"Providers"**
3. Make sure **"Email"** is enabled (should be by default)
4. Under Email settings, ensure:
   - "Enable Email Signup" is ON
   - "Enable Email Confirmations" is ON

**Screenshot Reference:** Your Supabase dashboard should look like this:
```
┌─────────────────────────────────────────────────────────┐
│ Supabase Dashboard                                       │
├─────────────────────────────────────────────────────────┤
│ ☰ tgf-platform                                          │
│                                                          │
│ 📊 Table Editor          │  Welcome to your project!    │
│ 🔐 Authentication        │                              │
│ 📁 Storage               │  Project URL:                │
│ 🔧 Edge Functions        │  https://xxx.supabase.co     │
│ ⚙️ Settings              │                              │
└─────────────────────────────────────────────────────────┘
```

---

## Step 2: Create a Stripe Account {#step-2-stripe}

**Stripe** handles all your payments. Credit cards never touch your server - Stripe handles the security.

### 2.1 Create Account

1. Go to [https://dashboard.stripe.com/register](https://dashboard.stripe.com/register)
2. Fill in your details:
   - Email
   - Full name
   - Password
   - Country: United States
3. Click **"Create account"**
4. Verify your email

### 2.2 Complete Your Profile (Optional for Testing)

For testing, you can skip the business verification. But before going live, you'll need to:
- Add your business details
- Link a bank account for payouts
- Verify your identity

### 2.3 Get Your Test API Keys

**IMPORTANT:** Always use **TEST** keys during development. Real money won't be charged.

1. Make sure you're in **"Test mode"** (toggle in top-right should say "Test mode")
2. In the left sidebar, click **"Developers"**
3. Click **"API keys"**
4. You'll see:
   - **Publishable key** - starts with `pk_test_...`
   - **Secret key** - starts with `sk_test_...` (click "Reveal" to see)

5. **Copy these somewhere safe**

### 2.4 Set Up Webhook (For Later)

Webhooks let Stripe tell your app when payments succeed or fail. We'll set this up after deploying.

**Screenshot Reference:**
```
┌─────────────────────────────────────────────────────────┐
│ Stripe Dashboard                    [Test mode: ON]     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│ Developers > API keys                                    │
│                                                          │
│ Standard keys                                            │
│ ────────────────────────────────────────                │
│ Publishable key: pk_test_51ABC...                       │
│ Secret key: sk_test_51ABC... [Reveal]                   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## Step 3: Create a Vercel Account {#step-3-vercel}

**Vercel** hosts your website. They have a generous free tier.

### 3.1 Create Account

1. Go to [https://vercel.com/signup](https://vercel.com/signup)
2. Sign up with GitHub (recommended) or email
3. If using GitHub, authorize Vercel to access your repositories

### 3.2 That's It For Now!

We'll deploy the app in Step 6. Just having the account ready is enough.

---

## Step 4: Set Up Your Database {#step-4-database-setup}

Now we need to create all the tables in your Supabase database.

### 4.1 Run the Database Migration

1. Go to your Supabase dashboard
2. In the left sidebar, click **"SQL Editor"**
3. Click **"New query"**
4. Open the file `supabase/migrations/00001_initial_schema.sql` from your project
5. Copy the ENTIRE contents of that file
6. Paste it into the SQL Editor
7. Click **"Run"** (or press Cmd+Enter / Ctrl+Enter)

You should see "Success. No rows returned" - this is good!

### 4.2 Verify Tables Were Created

1. In the left sidebar, click **"Table Editor"**
2. You should see all these tables:
   - chapters
   - membership_types
   - members
   - member_memberships
   - games
   - events
   - event_games
   - registrations
   - registration_games
   - transactions
   - wallet_transactions
   - audit_logs
   - feature_flags

### 4.3 Check Initial Data

1. Click on the **"chapters"** table
2. You should see two rows: "San Antonio" and "Austin"
3. Click on the **"games"** table
4. You should see: NET Skins, GROSS Skins, CTP, Long Drive

If you see this data, your database is set up correctly!

---

## Step 5: Connect Everything {#step-5-connect}

Now we connect all the services together using environment variables.

### 5.1 Create Your Environment File

1. In your project folder, find the file `.env.example`
2. Make a copy and rename it to `.env.local`
3. Open `.env.local` in a text editor

### 5.2 Fill In Your Values

Replace the placeholder values with your real keys:

```bash
# SUPABASE
NEXT_PUBLIC_SUPABASE_URL=https://your-project-id.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6...

# STRIPE
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_51ABC...
STRIPE_SECRET_KEY=sk_test_51ABC...

# APP URL (for local development)
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

### 5.3 How to Find Each Value

| Variable | Where to Find It |
|----------|-----------------|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase → Settings → API → Project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase → Settings → API → anon public |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Settings → API → service_role (click Reveal) |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | Stripe → Developers → API keys → Publishable key |
| `STRIPE_SECRET_KEY` | Stripe → Developers → API keys → Secret key |

---

## Step 6: Deploy Your App {#step-6-deploy}

### 6.1 Push Your Code to GitHub

If you haven't already:

1. Create a GitHub repository for your project
2. Push your code to GitHub

### 6.2 Deploy to Vercel

1. Go to [https://vercel.com/new](https://vercel.com/new)
2. Click **"Import Git Repository"**
3. Select your GitHub repository
4. Configure the project:
   - **Framework Preset:** Next.js (should auto-detect)
   - **Root Directory:** Leave as `/`

5. **Add Environment Variables:**
   - Click "Environment Variables"
   - Add each variable from your `.env.local` file:
     - `NEXT_PUBLIC_SUPABASE_URL` = your value
     - `NEXT_PUBLIC_SUPABASE_ANON_KEY` = your value
     - `SUPABASE_SERVICE_ROLE_KEY` = your value
     - `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` = your value
     - `STRIPE_SECRET_KEY` = your value
     - `NEXT_PUBLIC_APP_URL` = your Vercel URL (e.g., `https://tgf-platform.vercel.app`)

6. Click **"Deploy"**
7. Wait 2-3 minutes for the build to complete

### 6.3 Set Up Stripe Webhook

After deploying:

1. Copy your Vercel URL (e.g., `https://tgf-platform.vercel.app`)
2. Go to Stripe Dashboard → Developers → Webhooks
3. Click **"Add endpoint"**
4. Enter: `https://your-vercel-url.vercel.app/api/webhooks/stripe`
5. Select events to listen to:
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
   - `checkout.session.completed`
6. Click **"Add endpoint"**
7. Copy the **"Signing secret"** (starts with `whsec_...`)
8. Add to Vercel:
   - Go to your Vercel project settings
   - Add environment variable: `STRIPE_WEBHOOK_SECRET` = your signing secret
   - Redeploy (Settings → Deployments → Redeploy)

---

## Troubleshooting {#troubleshooting}

### "Cannot connect to database"

- Check that your Supabase URL and keys are correct
- Make sure there are no extra spaces in your environment variables
- Verify your Supabase project is running (check the dashboard)

### "Payment failed"

- Make sure you're using TEST keys (start with `pk_test_` and `sk_test_`)
- Use Stripe's test card: `4242 4242 4242 4242`, any future date, any CVC

### "Page not found" after deployment

- Check that your build succeeded in Vercel dashboard
- Look at the build logs for any errors
- Make sure all environment variables are set

### "Authentication not working"

- Check Supabase Authentication settings
- Verify the Site URL is set correctly in Supabase Auth settings
- Make sure email provider is enabled

### Need More Help?

1. Check the Vercel build logs for specific errors
2. Check the browser console (F12 → Console) for JavaScript errors
3. Check Supabase logs (Database → Logs)

---

## Next Steps After Setup

Once everything is running:

1. **Create Your Admin Account**
   - Sign up through the app
   - In Supabase, go to Table Editor → members
   - Find your record and set `is_admin` to `true`

2. **Create Your First Event**
   - Log in as admin
   - Go to /admin/events
   - Create a test event

3. **Test the Full Flow**
   - Register for the event as a guest
   - Complete a test payment
   - Check that the registration appears

4. **Set Up Your Production Stripe Account**
   - Complete business verification
   - Switch to live API keys
   - Update environment variables in Vercel

---

## Quick Reference - All Your Keys

Keep this filled out and in a secure location:

```
SUPABASE
--------
Project URL: https://________________.supabase.co
Anon Key: eyJ________________________
Service Role Key: eyJ__________________
Database Password: ____________________

STRIPE (TEST)
-------------
Publishable Key: pk_test_________________
Secret Key: sk_test_____________________
Webhook Secret: whsec___________________

VERCEL
------
Project URL: https://________________.vercel.app

STRIPE (PRODUCTION) - Fill in later
------------------------------------
Publishable Key: pk_live_________________
Secret Key: sk_live_____________________
Webhook Secret: whsec___________________
```

---

*Last updated: November 2025*
