# COO Dashboard & AI Chat

## Architecture
- **COO page** at `/coo` — dashboard with action items, financial snapshot, and AI chat
- **AI Chat** uses Anthropic Claude API (`claude-sonnet-4-5-20250929`) with full business context
- **Agent routing** — `route_to_agent()` maps user questions to specialist agents (Financial,
  Operations, Course Correspondent, Member Relations, Compliance)
- **Chief of Staff** is the primary voice — always responds, with specialist context injected
- **Chat sessions** persist in `coo_chat_sessions` / `coo_chat_messages` tables
- **Master context** — summaries of all past sessions injected as "persistent memory"

## COO Agent System (`coo_agents` table)
Six specialist agents seeded on first run via `_seed_coo_agents()`:
1. **Chief of Staff** — primary voice, synthesizes all specialist input
2. **Financial Agent** — allocations, expenses, reconciliation, tax reserve
3. **Operations Agent** — events, registrations, rosters, breakeven
4. **Course Correspondent Agent** — course relationships, contracts, confirmations
5. **Member Relations Agent** — member communications, winnings, credits
6. **Compliance Agent** — sales tax, IRS installments, filing deadlines

Prompt updates: Use `_seed_coo_agents()` for new installs. For existing DBs, add a
migration check in `init_db()` (see "vigilant analyst" check pattern).

## `build_coo_full_context()` — Live Business Intelligence
Located in `database.py`, generates a text briefing from 10 modules for the AI.
All sections wrapped in try/except with `logger.warning()` logging.

**Section 2 — Events & Operations (key data):**
- **Upcoming events:** player counts (9/18 split), revenue (includes add-on payments),
  pricing structure (course_cost, markup, side_game_fee for 9h and 18h variants)
- **Player counts:** `parent_item_id IS NULL` filter in COUNT expression only —
  ensures child payment items excluded from player count but included in revenue SUM
- **Recent events:** last 30 days with player/revenue data
- **RSVP breakdown:** per-event playing vs not-playing counts
- **Cost allocations:** from `acct_allocations` table — course_payable, prize_pool,
  godaddy_fee, tgf_operating, total_collected (penny-accurate)
- **TGF payouts:** tournament prize pools with category breakdowns
- **Full profitability:** from allocations table, formula:
  `Net = Revenue - Course Fees - Prize Fund - Processing Fees`

## Event Pricing Data Model
The `events` table has extensive pricing columns:
- `course_cost` / `course_cost_9` / `course_cost_18` — post-tax course fee per player
- `tgf_markup` / `tgf_markup_9` / `tgf_markup_18` — TGF margin per player
- `side_game_fee` / `side_game_fee_9` / `side_game_fee_18` — side games fee
- `transaction_fee_pct` REAL DEFAULT 3.5 — blanket fee charged to players
- `course_surcharge` — per-player surcharge (e.g., $1 ACGT printing)
- `course_cost_breakdown` / `_9` / `_18` — JSON with tax-inclusive line items

**Course cost calculation:**
- Base amount × (1 + tax_pct/100) = post-tax cost (e.g., $39 × 1.0825 = $42.22)
- Player-facing price rounds up to nearest dollar ($43)
- `acct_allocations.course_payable` stores the exact post-tax amount (not rounded)

**Course cost rounding fix (Issue #242):**
- **Per-player allocations** store individual post-tax amounts (individually correct)
- **Aggregate calculations** (Financial tab, COO dashboard) use corrected formula:
  `base_rate × player_count × (1 + tax_rate)` — totals first, tax second
- Old way: $54 × 1.0825 = $58.46/player → $58.46 × 32 = **$1,870.72** (rounding drift)
- New way: $54 × 32 = $1,728 × 1.0825 = **$1,870.40** (correct)
- Server: `_calc_aggregate_course_cost()` in database.py
- Client: `calcAggregateCost()` in events.html (fallback path)

**Processing fee (GoDaddy merchant fee):**
- Actual formula: `order_total × 2.9% + $0.30` per order
- Stored in `acct_allocations.godaddy_fee` per player
- The 3.5% `transaction_fee_pct` is the blanket fee charged to players —
  the difference between 3.5% revenue and actual 2.9%+$0.30 cost is TGF margin

## COO Chat UI Features
- **Copy button** — clipboard icon on hover for all AI responses (coo-dashboard.js)
- **Chat session rename** — pencil icon on hover in sidebar, calls `PATCH /api/coo/chat-sessions/<id>`
- **Session management** — new chat, delete, load previous sessions
- **Collapse state** — `COO.collapsedGroups` Set tracks which topic groups are open/closed
- **Dismiss persistence** — dismissed action items survive re-renders

## Key COO endpoints
- `POST /api/coo/chat` — send message, get AI response
- `GET /api/coo/chat-sessions` — list all sessions
- `GET /api/coo/chat-sessions/<id>` — load session with messages
- `PATCH /api/coo/chat-sessions/<id>` — rename session
- `DELETE /api/coo/chat-sessions/<id>` — delete session
- `GET /api/coo/agents` — list active agents
