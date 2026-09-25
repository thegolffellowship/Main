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
  `tracker-health`, addressed `TO: front-desk` since v2.489.5 — it was tracker-claude + Kerry), COO action items (one
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

## 2d. The first live report of the new build (v2.486.1, 4:02 PM CDT)

- **WHERE THE BYTES ARE:** `gg_raw_archive` **364 MB of the 431 MB file**
  (already-zlib'd raw Golf Genius pages, the gg-history lane's verbatim
  hedge; `gg_history_results` 7 MB; everything else under 4 MB); free
  pages 0. Reads of other tables do not touch those pages, but the
  nightly backup (`VACUUM INTO` → gzip → OneDrive) copies 431 MB every
  night, and the file is 6× what the business data needs. DECISION FOR
  KERRY / the gg-history lane: move the archive to its own SQLite file
  (ATTACH) or to OneDrive as files, and the main DB drops to ~65 MB.
  The CTO digest files it as `db_big_table:gg_raw_archive`.
- **The EVENTS page polls every 30 s** and each tick pulls `/api/items`
  (every order row, ~2.6 MB; p50 523 ms on the live box, 25 samples in
  18 minutes from one tab), the index map, payouts, events, RSVPs. Fixed
  the cheap half (a hidden tab no longer refreshes — v2.486.3); the
  cadence and what a tick should fetch are the events page's call
  (flighting lane / Kerry). This is also a steady write-lock-free load on
  the single process that every PAIRINGS open competes with.
- **Load:** load1 105 on 48 visible cpus (host figure) — ratio 2.2,
  under the 4.0 rule; the box is busy, not proven starved.
- **Jobs on the same process:** `expense_inbox_check` ~5.2 s every 2 min,
  `inbox_check` ~4.5 s every 5 min, `rsvp_inbox_check` ~1.3 s, live poll
  9 ms. With the once-per-process DDL guard those no longer hold a
  PAIRINGS read on the lock; their samples sit beside the route samples
  so the next slow open's `concurrent` says whether one was running.
- No `pairings_get` sample yet on the new build — Kerry has not opened
  PAIRINGS since the deploy. The first one is the before/after.

## 2e. Morning two (2026-09-23, v2.486.5): the digest worked, the response loop did not exist

- 5:00 digest #620 posted on time and named the 9/22 outage (five jobs
  failing with `disk I/O error` 5:29–8:57 PM — the 500 MB Railway
  volume was full; Kerry resized it to 250 GB at 9:10 PM, no data lost;
  incident record #619). The sibling lane shipped v2.486.4 (volume
  watch, 80/90% findings) at 5:15.
- What was missing: nothing woke THIS lane to act on the digest. Now a
  Routine fires into this session at 5:10 AM Central daily
  (trig_01NFYQB2DbAjpC9J3CeexG33; cron 10 10 UTC — re-set after Nov 1).
- Digest improvements from the first real morning: RECOVERED job errors
  (medium, worded so nobody chases a fixed problem); OPEN provider
  alerts named as HIGH until closed (Railway's 9/19 "95% full" mail sat
  at confidence 45); `scoring-health-ack` to close HEALTH items with
  the reason; db_backup line 300 s.
- Still Kerry's: `gg_raw_archive` (368 MB of the file, the backup and
  the volume both pay for it) — move it out; the EVENTS 30 s poll cadence.

## 2f. Morning three (2026-09-24, v2.488.8)

- Digest #642: the only real finding was `scoring-hcp-cards` at 18.7 s
  (23 card emails, Graph API — line raised to 60 s); the rest were the
  provider-alert rule's own noise (ten HEALTH items filed about ten
  existing Railway mails back to May). Fixed the mechanism (`file:
  False`, 14-day window, one stale line) and closed the ten.
- PAIRINGS on the new build, live: **p50 347 ms, max 520 ms** (was
  8.9–11.5 s) — the before/after Kerry asked for.
- Every page's main data route is on the stopwatch (#630 ask 4).
- Spotlight (#630 asks 1–3): instrumented (per-builder laps + cold
  mark); the 90 s `spotlight_warm` job pays the cold cost off the page;
  scaling answer in coo.md (warm 14 ms, cold ~3.5 s, does not grow with
  players; only the handicap map does, ~0.4 s at 5k).
- `gg_raw_archive` move (#627, Kerry: "Yes, move the GG archive to its
  own file"): NOT yet built — a schema + VACUUM step that needs an
  off-hours window; the CTO lane takes it next unless the gg-history
  lane claims it first (said so on the mailbox).

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

## 7. Incident 2026-09-22, 8:46–9:12 PM CDT — the volume was full (v2.486.4)

`main-volume` was a 500 MB Railway volume; the database file is ~431 MB
(368 MB of it `gg_raw_archive`, §4). At 99% SQLite could not grow the
WAL/shm, so every data read raised `disk I/O error`: `/events` returned
`{"error":"Internal server error"}`, `/api/health` said
`database_readable: false`, and the inbox / RSVP / expense / lead jobs
failed from 5:29 PM until the resize (111 of 392 expense_inbox_check
runs in the 9/23 digest). `/health` (`SELECT 1`) stayed green, so Railway
never restarted anything. Railway had e-mailed "Main volume is 95% full"
on 9/19 — twice — and the COO filed both at confidence 45 where they sat
unread. Kerry live-resized the volume to 250 GB from his phone (Railway
bills bytes stored, not the size set); the site answered at 9:12 PM with
every row intact. No commit caused it and nothing was restored.

What v2.486.4 adds (Handicap Surfaces lane, mailbox #619 asks 1 and 3):

- `perf.disk_usage()` — total / used / free / `pct_used` of the volume
  the DB file sits on (`shutil.disk_usage` of its directory).
- The health report carries it as `db.disk`; the digest prints a
  **VOLUME** line under **DATABASE**; `find()` files `volume_full`
  (medium at `volume_pct_warn` 80%, high at `volume_pct_alarm` 90%) with
  the fix in the text. One open COO action item per key, as for every
  finding.
- `/api/health` carries `volume: {pct_used, free_mb, total_mb}` — a phone
  check now says "99% full" instead of "database unreadable".
- The WAL size was already on the DATABASE line (`wal_bytes`); ask 3 was
  met before it was asked.

Still open from the incident: the `gg_raw_archive` move (§4, Kerry /
gg-history lane's decision — the 500 MB ceiling is gone, the 431 MB
nightly upload is not); and the COO's handling of a hosting-provider
alert at confidence 45 — a `support@railway.app` "volume is N% full"
mail should be urgency high, confidence 90, and named in the morning
brief (COO lane).

