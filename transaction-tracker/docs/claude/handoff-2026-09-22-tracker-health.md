# Handoff — TRACKER HEALTH & PERFORMANCE lane (2026-09-22)

Lane "Tracker Health & Performance", branch `claude/tracker-health-perf-q7v2nd`,
spun off the Handicap Surfaces lane (mailbox #607) after Kerry's 41-second
PAIRINGS open. Ack with the `perf_samples` shape: mailbox #609. Digest at
close: see the `tracker-health` / `session-digest` topics after #609.

Kerry's direction, verbatim (2026-09-22): *"Good work adding the 'health'
or 'speed' tool/log. We need to add in those types of elements across the
Tracker so that we can track and improve performance. Probably need an
agent specifically designed for this that will log things and report back
to you and the COO for you to pick up. Should be a standard once a day
routine on your part I think."*

## 1. What shipped

- **`email_parser/perf.py`** — ONE stopwatch for every heavy path.
  `Stopwatch(kind, name)` with `.lap()` / `.snapshot()` / `.finish()`;
  `@timed_route(name)` for Flask views (`perf.current()` inside);
  `timed_job(fn, id)` for scheduler callables; `timed_call()` for a
  block; `record()` for a measured-elsewhere sample. Samples queue in
  memory and a daemon thread writes them (never on the request thread);
  `flush()` for tests and the digest. `summary()` / `samples()` /
  `prune()` / `db_size()` / `probe_db_ms()` read them. SLOW lines per
  name in `SLOW_MS`, overridable by the `perf_slow_ms` dial. A slow
  sample also writes the `agent_action_log` row (`<name>_slow`) Kerry
  already reads. Each sample carries `load1` and `concurrent` (what else
  was running when it started) — the two facts that separate "this code
  is slow" from "something else had the box".
- **`perf_samples` table** — schema.md; created in `init_db`.
- **Instrumented:** the pairings GET (moved off its private `_lap`);
  `/api/events`, `/api/items` (+ `?event_id=` as `items_event`),
  `/api/events/<id>`, the flights board, the print-pack PDF,
  `/api/customers`, `/api/dashboard`, `/api/handicaps/index-map`,
  `/api/rsvps/bulk`, the COO chat (+ its context build as
  `coo_context`); **every scheduler job** (`_TimedScheduler.add_job`
  wraps the callable, so a job added later at runtime is covered too);
  **every `scoring-*` bridge** (`_scoring_dispatch` wraps the inner
  dispatcher; a non-bridge probe leaves no sample).
- **`email_parser/health.py`** — the daily digest agent: the report,
  the findings rules, the markdown, the mailbox post (topic
  `tracker-health`, to tracker-claude + Kerry), COO action items (one
  open item per finding key), retention prune, the once-a-day gate on a
  dial (`health_digest_time`, default 05:00 Central; the job checks
  every 15 min 4–9 AM so the dial is live without a restart).
- **`/admin/health`** (admin page) + `GET /api/admin/health?days=` +
  `POST /api/admin/health/digest {post}`; bridges `scoring-health[:<days>]`
  and `scoring-health-digest[:<days>][|post]`. `/health` is untouched
  (the Railway probe).
- **The PAIRINGS open, server side** (details in pairings.md): the
  roster read ONCE per open instead of three-to-five times; the
  v2.484.3 handicap cache actually hitting (its signature query had
  raised on every call — `hcp_exclude` is on `scoring_rounds`, not
  `handicap_rounds`); three indexes that turn the roster builder's
  SCANs into index searches; `no_network` made absolute; the WAL pragma
  once per file instead of on every one of ~18 connections per request.
  Fixture: **980 ms → 56 ms** warm.

## 2. What the live log said, and what it did not

Kerry's two opens of event 3309 at 20:22:51 / 20:23:01 UTC: 11,456 ms
and 11,105 ms, spread almost evenly across `saved_sheet` (2.0 / 3.1 s),
`roster_and_index` (2.0 / 3.0 s), `standings` (2.1 / 1.6 s), `blind_pool`
(1.9 / 1.2 s). The fixture reproduces the roster-read-three-times cost
and the cache miss, but not seconds per section on a 2,000-row database.
A cost that lands on unrelated sections equally is something every
section pays. The samples now carry what is needed to name it: the
`connect` lap, `load1`, `concurrent` (a scheduler job in flight — the
expense classifier runs every 2 min, the live poll every 5), and the
digest's live probe (`probe_db_ms`: a bare connect + one read). **First
thing the next session should do: read `scoring-health:1` on the live
app and look at the pairings_get samples' `connect` lap, `load1` and
`concurrent`, and the probe.** If `connect` is hundreds of ms, the
volume is the story; if `concurrent` names a job on every slow open,
the GIL is.

## 2b. Second pass (v2.486.0): the lock, the load, the file

- **The lock (#608's "count the CREATE TABLE IF NOT EXISTS per request").**
  `CREATE INDEX IF NOT EXISTS` on an existing index waits on the write
  lock (proven in the sandbox: 1,003 ms behind a writer with a 1 s
  timeout). Four `_ensure_pairing_tables` per PAIRINGS open + the
  standings table's ensure = every section waiting on whichever job was
  writing. All 18 `_ensure_*` helpers now run once per file per process
  (`_once_per_db`).
- **The first live report (3:51 PM CDT):** load average **87.4** on the
  box (host figure), database file **431 MB** for 2,312 orders / 15,580
  rounds / 10,700 scoring rounds, `items_list` p50 532 ms live (94 ms on
  the fixture), `hcp_index_map` max 838 ms. The report now carries
  `cpus`, free pages and the biggest tables (`perf.db_layout`); findings
  for a saturated box, a VACUUM candidate (>20% free pages) and a table
  over half the file. **The next session reads `scoring-health:1` and
  acts on WHERE THE BYTES ARE** — a 431 MB file on a network volume is
  the cold-cache cost every section pays; if free pages dominate, a
  VACUUM is Kerry's decision (off-hours; the file is copied during it).
- **LOADING… (Kerry 3:27 PM):** `static/js/loading.js`, loaded first by
  the shell include — top bar after 150 ms in flight, "Loading…" pill
  after 800 ms, `.tgf-loading` placeholder class; guard `test_loading.js`.
- **Digest hour:** 05:00 Central (Kerry, #611); the Handicap Surfaces
  lane reads at 5:15.

## 2c. The agent is the CTO

Kerry 2026-09-22 (~4 PM): *"I think we would define your Agent Role as
CTO, don't you think?"* Agreed: the digest signs as the CTO agent, the
action items it files are from "CTO", the audit log names `cto-agent`.
Money stays the CFO agent's (finance lane); the C-Suite structure lane
(#614) places both under the COO roll-up. Kerry's data rule the same
afternoon: *"make sure you're not screwing anything up with data"* —
this lane's only writes are its own `perf_samples` rows, additive
action items / settings / log rows, and the mailbox post; no UPDATE,
DELETE, ALTER or VACUUM on any existing table.

## 3. EVENTS landing

Measured, not yet changed (events.md). Server side on the fixture is
small (`/api/events` 20 ms, `/api/items` 94 ms); `/api/items` is a
2.6 MB body the page walks on every load. If the live samples agree, the
fix is the page asking for less — coordinate with the flighting lane.

## 4. How to verify without a browser

- `scoring-health:1` — the report (findings first). `scoring-health:0.25`
  for the last six hours.
- `get_agent_action_log agent_name=app` — the `*_slow` rows, with the
  breakdown and "while <job>" when something else was running.
- `scoring-health-digest` — today's digest text without posting;
  `scoring-health-digest:1|post` runs the real routine now.
- Guards: `test_perf.py` (48 checks), `test_health_digest.py` (28).

## 5. Rule 3b items on the record

- `perf_samples` shape — proposed in #609, built (Kerry may object
  in-session; nothing else depends on its exact columns).
- Three plain indexes — no data shape change, no behaviour change; named
  in schema.md.
- The digest hour — 05:00 Central — Kerry's ruling in #611 (asked in #609). Change it
  with the `health_digest_time` dial (HH:MM), no deploy.

## 6. Open / carried forward

- Read the live samples (§2) and fix what they name. The fixture's
  wins are real but the live 11 s is not fully explained by them.
- The EVENTS page payload (§3).
- Client-side paint timings: `perf.record("client", ...)` exists for a
  beacon from the page (time to first roster paint) — not wired.
- Known pre-existing red on main, unchanged by this lane:
  `test_rsvp_credit_map.py` (2), `test_starting_handicap.py` (exit 1,
  fixture), `test_champ_points_live.py` (1), `test_flights_custom_ui.js`
  (1, root-scoped lookup), `test_print_pack.py` (2 — no PDF engine in
  the sandbox).
- Not this lane: money, member email, GG writes, flighting rules, the
  handicap surfaces, the closeout's content.
