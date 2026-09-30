# Vendor Audit: 2026-09-30 (READ-ONLY)

**tracker-claude (CFO lane).** Kerry, via Chief of Staff #1078-3: "A whole vendor audit should be done for creating all of those. I only did those manually, but I definitely don't want to do them manually."

- Nothing was created or changed to produce this report.
- Creating profiles waits for Kerry's OK. The work belongs with the chart of accounts v2 at the weekend Board session (#1052, #1061-6).

**Source:** every active `acct_transactions` expense row from these sources:
- `statement` and `chase_alert` (card and bank feeds);
- `receipt`;
- `venmo` rows with no customer.

That is 830 rows, from 2025-12 to 2026-09. Each payee name is normalized by pattern: strip processor prefixes (GLF*, LS, 4UP*, FSP*, SQ *, TST*, DNH*, FACEBK *), store numbers, phone numbers and city/state.

## Summary

| Class | Payees | Rows | Spend |
|---|---:|---:|---:|
| **Transfers booked as expense: Chase card payments/fees, Frost transfers (NOT vendors)** | 2 | 57 | **$150,635.66** |
| Golf courses and venues | 29 | 100 | $99,321.20 |
| Software and subscriptions | 20 | 286 | $11,120.62 |
| People or unknown (Venmo with no customer; the people resolver, not vendors) | 30 | 62 | $6,607.98 |
| Tax agencies (Comptroller WebFile, IRS) | 1 | 3 | $5,794.87 |
| Likely personal or mixed (gym, streaming, retail, restaurants, fuel) | 5 | 167 | $6,032.38 |
| Lodging and travel | 3 | 9 | $3,614.46 |
| Supplies and event meals | 5 | 76 | $2,685.16 |
| Marketing, printing, dues | 5 | 20 | $1,519.92 |

## Findings

1. **Only 9 vendor profiles exist, and they are barely used.**
   - The profiles: 393 Costco, 394 Anthropic, 396 Alamo City Golf Trail, 397 TeraVista GC, 398 Royal Pizza, 399 Arcis Golf, 400 HubSpot, 401 Brevo, 402 Vercel.
   - Only 3 ledger rows link to any of them: TeraVista ×1 and Arcis ×1.
   - 395 (John Ohlrich) sits in the id range but is a real member, not a vendor.
   - A vendor is marked only by `acquisition_source = 'vendor'`. There is no role column.
2. **Five vendor profiles were given gender "M" in the 9/30 gender write (#1063):** 393 Costco, 397 TeraVista GC, 398 Royal Pizza, 400 HubSpot, 402 Vercel. The write excluded only 394, 396, 399 and 401. These five need to go back to NULL. The people-list filter should key on the vendor marker, not a hand-kept id list.
3. **Card payments and bank transfers are $150,636 of "expense"** (Chase $136,817 across 46 rows; Frost $13,818 across 11 rows). This is far more than the $26,960 in my audit (#1052), which counted only 8/25–9/30. They are the largest single distortion in the books, and they are not vendors.
4. **Sales-tax payments are booked as expense** ($5,794.87 across 3 rows, 4/14–6/16, including one IRS row).
   - They should reduce Sales Tax Payable, and the IRS row is likely personal.
   - These are also WebFile payment evidence, useful for the `sales_tax_filings` backfill.
5. **Course spend ($99,321) has almost no event link.** Of 100 rows, only a handful carry an event. Each course invoice should attach to its event, so the P&L uses the real bill instead of the estimate (Canyon Springs is waiting on this).
6. **Personal-looking spend on business feeds ($6,032, 167 rows):** Golds Gym, Covenant Eyes, Disney+, Prime Video, Fandango, Google Fiber, H-E-B, Home Depot, medical, restaurants, fuel.
   - These need an owner-draw review in one pass with Kerry. They should not get vendor profiles.
   - Trimble ($399) is probably Horizon or SketchUp work, not TGF.
7. **The Airbnb charge of $2,761.30 (8/19) is LSC lodging.** It nets against the Rideout $560 lodging pass-through and any other lodging collected (#1061-2).
8. **People or unknown ($6,608):** Venmo payouts to named people with no customer link, such as Joe Warring $1,188, Kade Lattimore $550 and Raleigh Kelley $550. These go to the identity resolver, and some may be Two Man Tour payouts.

## Proposed profiles to create (on Kerry's OK)

Create one `role = vendor` profile per business payee in the course, software, lodging/travel, marketing/printing/dues, supplies/meals and tax-agency tables below. That is about 55 new profiles on top of the 9 that exist.

Each profile carries:
- a canonical name;
- a vendor type (course / software / lodging / marketing / supplies / meals / tax agency);
- a default category mapped to the chart of accounts v2 and its Schedule C line;
- a default line of business (TGF core, or Two Man Tour when known);
- alias patterns (the raw strings above).

Profiles are **never** created for:
- transfers between TGF's own accounts;
- people (they go to the people resolver);
- the likely-personal group (it goes to owner-draw review).

Vendor profiles never appear in people lists: rosters, gender, pairings, marketing.

## Proposed auto-create rule (on ingest, with a manager confirm)

1. **Normalize** the raw merchant string: prefixes, store numbers, phones, city/state.
2. **Look it up** in `vendor_aliases`, which maps a normalized pattern to a vendor customer_id.
   - **Hit:** link `customer_id`. Apply the vendor's default category and line of business. For a course vendor, also propose the event: the same course within ±7 days, which the manager confirms.
   - **Miss:** create a **PROPOSED** vendor profile. It lands in the review queue with the suggested name, type and category. The manager confirms it, merges it into an existing vendor, or marks it personal (owner draw) or a transfer.
   - Nothing is attributed until confirmed, and nothing is silently left NULL.
3. **Never vendor:** Chase or Frost payment and transfer patterns are auto-typed as transfers. Person-name payees from Venmo, Zelle or Cash App go to the people resolver.
4. **The known-personal list** (the merchants in finding 6, once Kerry confirms it) auto-suggests entity Personal / Owner Draw.
5. **Guards:** the normalizer is the only entry point, and every create and merge is action-logged. Creating vendors this way fixes the "unattributed expense money" gap from the July audit (F1/F3) at the source.

## Full payee tables

### Golf courses and venues

| Payee | Rows | Spend | First | Last | Profile |
|---|---:|---:|---|---|---|
| The Quarry GC | 7 | $9,684.42 | 2026-03-17 | 2026-08-29 | — |
| Golf Club at Star Ranch | 7 | $9,625.57 | 2026-03-17 | 2026-09-29 | — |
| Hyatt Regency Lost Pines | 1 | $9,534.95 | 2026-08-18 | 2026-08-18 | — |
| TPC San Antonio | 5 | $9,214.75 | 2026-05-12 | 2026-07-01 | — |
| Willow Springs GC | 10 | $6,615.13 | 2026-05-02 | 2026-05-05 | — |
| Silverhorn GC | 10 | $6,057.96 | 2026-05-05 | 2026-09-08 | — |
| ShadowGlen GC | 7 | $4,966.26 | 2026-03-14 | 2026-09-08 | — |
| Cedar Creek GC | 7 | $4,812.65 | 2026-02-07 | 2026-09-24 | — |
| Canyon Springs GC | 7 | $4,512.63 | 2026-03-25 | 2026-09-30 | — |
| Kissing Tree GC | 2 | $4,031.90 | 2026-06-27 | 2026-06-27 | — |
| Comanche Trace | 4 | $3,964.41 | 2026-05-16 | 2026-05-16 | — |
| Teravista GC | 6 | $3,750.51 | 2026-03-25 | 2026-09-22 | 397 |
| Landa Park GC | 2 | $3,240.00 | 2026-04-11 | 2026-08-29 | — |
| Falconhead GC | 2 | $3,058.06 | 2026-07-07 | 2026-08-01 | — |
| Forest Creek GC | 2 | $2,764.71 | 2026-07-14 | 2026-09-12 | — |
| Hyatt Hill Country | 1 | $2,399.37 | 2026-06-18 | 2026-06-18 | — |
| La Cantera Resort | 1 | $2,318.72 | 2026-02-22 | 2026-02-22 | — |
| Flying L Ranch | 2 | $2,139.00 | 2026-05-30 | 2026-05-30 | — |
| GolfNow | 2 | $1,738.78 | 2026-04-11 | 2026-08-18 | — |
| Arcis Golf | 1 | $1,665.01 | 2026-04-29 | 2026-04-29 | 399 |
| Morris Williams GC | 1 | $1,216.00 | 2026-03-01 | 2026-03-01 | — |
| Brackenridge Park GC | 1 | $849.76 | 2026-09-24 | 2026-09-24 | — |
| Avery Ranch GC | 1 | $714.45 | 2026-09-15 | 2026-09-15 | — |
| Alamo City Golf Trail | 2 | $300.00 | 2026-03-02 | 2026-09-11 | 396 |
| Texas Ranger GC | 2 | $70.39 | 2026-06-07 | 2026-06-07 | — |
| Vaaler Creek GC | 3 | $30.00 | 2026-03-21 | 2026-03-22 | — |
| JW Marriott Hill Country | 1 | $25.24 | 2026-05-12 | 2026-05-12 | — |
| Tierra Verde GC | 2 | $14.80 | 2026-06-06 | 2026-06-06 | — |
| Golf Club of Texas | 1 | $5.77 | 2026-09-05 | 2026-09-05 | — |

### Software and subscriptions

| Payee | Rows | Spend | First | Last | Profile |
|---|---:|---:|---|---|---|
| Anthropic | 160 | $4,302.08 | 2025-12-29 | 2026-09-17 | 394 |
| GoDaddy | 9 | $2,043.95 | 2025-12-18 | 2026-04-02 | — |
| Golf Genius | 1 | $895.44 | 2026-01-21 | 2026-01-21 | — |
| Adobe | 9 | $681.84 | 2025-12-19 | 2026-09-18 | — |
| Vercel | 15 | $501.85 | 2026-02-02 | 2026-09-02 | 402 |
| Trimble (SketchUp) | 1 | $399.00 | 2026-09-14 | 2026-09-14 | — |
| HubSpot | 9 | $383.76 | 2025-12-27 | 2026-09-26 | 400 |
| Brevo | 11 | $339.02 | 2025-12-23 | 2026-09-23 | 401 |
| Pantone | 9 | $287.73 | 2025-12-10 | 2026-09-10 | — |
| Railway | 12 | $214.99 | 2026-02-25 | 2026-09-25 | — |
| Aura | 1 | $212.14 | 2025-12-12 | 2025-12-12 | — |
| QR-Code-Generator | 1 | $207.23 | 2026-01-12 | 2026-01-12 | — |
| Ideogram AI | 7 | $140.00 | 2026-02-19 | 2026-09-19 | — |
| Make.com | 12 | $135.48 | 2025-12-03 | 2026-09-03 | — |
| Dropbox | 1 | $127.79 | 2025-12-30 | 2025-12-30 | — |
| Manus AI | 6 | $125.28 | 2026-03-04 | 2026-08-04 | — |
| Zoom | 10 | $74.60 | 2025-12-05 | 2026-09-05 | — |
| Google One | 10 | $21.20 | 2025-12-03 | 2026-09-02 | — |
| Vertafore | 1 | $15.95 | 2026-02-16 | 2026-02-16 | — |
| Celonis | 1 | $11.29 | 2026-04-03 | 2026-04-03 | — |

### Lodging and travel

| Payee | Rows | Spend | First | Last | Profile |
|---|---:|---:|---|---|---|
| Airbnb | 1 | $2,761.30 | 2026-08-19 | 2026-08-19 | — |
| La Quinta | 6 | $830.76 | 2026-05-31 | 2026-08-17 | — |
| Southwest Airlines | 2 | $22.40 | 2026-04-07 | 2026-04-08 | — |

### Marketing, printing, dues

| Payee | Rows | Spend | First | Last | Profile |
|---|---:|---:|---|---|---|
| Meta (Facebook ads) | 15 | $903.97 | 2026-03-02 | 2026-09-09 | — |
| ViralVids LLC | 2 | $448.00 | 2026-02-26 | 2026-03-20 | — |
| Charity Golf International | 1 | $100.00 | 2026-09-18 | 2026-09-18 | — |
| Texas Golf Association | 1 | $48.00 | 2025-12-01 | 2025-12-01 | — |
| Zazzle | 1 | $19.95 | 2026-02-23 | 2026-02-23 | — |

### Supplies and event meals

| Payee | Rows | Spend | First | Last | Profile |
|---|---:|---:|---|---|---|
| Amazon | 58 | $1,944.20 | 2025-12-04 | 2026-06-22 | — |
| Royal Pizza | 2 | $293.60 | 2026-04-23 | 2026-04-23 | 398 |
| Costco | 3 | $271.16 | 2026-02-06 | 2026-05-28 | 393 |
| Aldaco's | 3 | $88.72 | 2026-04-28 | 2026-09-29 | — |
| HP Instant Ink | 10 | $87.48 | 2025-12-13 | 2026-09-13 | — |

### Tax agencies

| Payee | Rows | Spend | First | Last | Profile |
|---|---:|---:|---|---|---|
| Texas Comptroller / IRS | 3 | $5,794.87 | 2026-04-14 | 2026-06-16 | — |

### NOT vendors: transfers between TGF's own accounts (currently booked as expense)

| Payee | Rows | Spend | First | Last | Profile |
|---|---:|---:|---|---|---|
| Chase (card payment/fee) | 46 | $136,817.28 | 2025-12-26 | 2026-09-24 | — |
| Frost (transfer) | 11 | $13,818.38 | 2026-04-01 | 2026-09-13 | — |

### Likely personal or mixed: owner-draw review, not vendor profiles

| Payee | Rows | Spend | First | Last | Profile |
|---|---:|---:|---|---|---|
| Personal (subscriptions/services) | 60 | $2,533.27 | 2025-12-06 | 2026-09-18 | — |
| Restaurants/retail (various) | 61 | $1,946.82 | 2025-12-24 | 2026-09-27 | — |
| Fuel/tolls/parking | 26 | $570.11 | 2025-12-08 | 2026-09-22 | — |
| Retail/grocery | 15 | $554.31 | 2025-12-24 | 2026-06-18 | — |
| Home Depot | 5 | $427.87 | 2026-03-16 | 2026-04-25 | — |
