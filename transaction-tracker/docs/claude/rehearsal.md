# Dress rehearsal scratch copy + restore drill (CA #800/#801, #728)

Kerry 2026-09-27: "Why not have it test run tonight?" CA's dress rehearsal
replays real past events on a copy restored from last night's backup, with
every outbound channel off. Code: `email_parser/rehearsal.py`; guard
`test_rehearsal.py`.

## What is built (v2.510.3)

1. **The restore drill on production** (bridge `scoring-rehearsal:restore`):
   the newest nightly backup → gunzip → `PRAGMA integrity_check` +
   foreign-key check → row counts vs the live file → scrub → gzip, into
   `<volume>/rehearsal/tracker_rehearsal.db(.gz)`. Never at `DB_PATH`; the
   live file is only read (counts). Timings and the result go in the app
   setting `rehearsal_drill`; `scoring-rehearsal:status` reads them back.
2. **The scrub** blanks every contact detail and secret in the COPY:
   emails → `r<table>-<rowid>@rehearsal.invalid`, phones / addresses /
   birthdays / Venmo & payment handles / tokens / message bodies → NULL or
   '', secret-looking app_settings → ''. Then `VACUUM INTO`, so no freed page
   keeps the old value. Names, ids, events, orders, money, scores and
   handicaps stay.
3. **`TGF_REHEARSAL=1`**: `import email_parser` installs a socket guard —
   every non-loopback connection raises `RehearsalOutboundBlocked`, a local
   egress proxy is blocked and its env vars dropped — and `app.py` does not
   start the scheduler. One check covers Graph mail, SMTP, Brevo, Stripe,
   Twilio/SMS, Golf Genius, Meta, HubSpot and Anthropic, and any channel
   added later. `test_rehearsal.py` proves it (run it with
   `REHEARSAL_DB=<copy>` to prove it on a given copy).

## The entry takeover tool (CA #811, GO in #829, v2.510.11)

`tools/scratch_entry_takeover.py <scratch.db> --events 3309,3315 --i-am-scratch`
makes entered scores the scoring record for the chosen events ON THE SCRATCH
COPY, so the downstream lanes run on entered rows. Per event it: (1) saves the
SHADOW DIFF first (`takeover-shadow-diff-<utc>.json` beside the file: the
dry-run publish plus `entry_parity`; this file is the G-0 parity result);
(2) moves the event's non-entry `scoring_rounds` / `scoring_holes` into
`scoring_rounds_gg_parked` / `scoring_holes_gg_parked` inside the scratch file,
same ids; (3) moves the file's `entry_record_from` back to the earliest chosen
event date (old value kept as `entry_record_from_before_takeover`); (4) runs
`publish_event(apply=True)`, now authoritative. `--undo` restores the GG rows
under their own ids, removes the entry rows and restores the cutover.
`handicap_rounds` links to parked rounds are left in place (and counted in the
report), so undo brings them back whole.

Guards: always needs `--i-am-scratch`; the file must be in a `rehearsal/`
directory or carry "scratch" in its name; `/data/transactions.db` and this
environment's `DATABASE_PATH` are refused; it prints the file before changing
it and sets `TGF_REHEARSAL=1`. It is not imported by the app and has no route
or bridge. Under Kerry's B it runs inside the rehearsal runner on Railway,
against `<volume>/rehearsal/`. Guard: `test_scratch_takeover.py`.

## The Railway runner (Kerry chose B, CA #832, 2026-09-28)

The copy never leaves the volume. The lanes run their rehearsal steps ON
Railway through the bridge; each job is a SEPARATE PROCESS:

- its environment is an allow-list (PATH, HOME, locale, Python paths) plus
  `TGF_REHEARSAL=1`, `TGF_REHEARSAL_RUNNER=1`, `TGF_REHEARSAL_DIR`. No Graph,
  Brevo, Stripe, Twilio, Anthropic, HubSpot or Meta secret and no `RAILWAY_*`
  variable reaches it; importing `email_parser` installs the outbound guard
  before anything runs;
- one job at a time on the shared copy; 30-minute limit; output kept in
  `<volume>/rehearsal/jobs/<id>.log` (plus `-report.json` for tools).

```
# (re)make the scratch copy from last night's backup: the restore drill
scoring-rehearsal:restore
# a lane harness: the runner fills in the scratch path and --i-am-scratch;
# only each tool's listed flags are accepted
scoring-rehearsal:run|tool|se_replay|--events 3309,3315 --workers 8
scoring-rehearsal:run|tool|takeover|--events 3309,3315          (add --undo to revert)
scoring-rehearsal:run|tool|lsc_weekend|--synthetic-index
# any read or write bridge, against the scratch copy instead of production
scoring-rehearsal:run|bridge|scoring-closeout-final:3309
scoring-rehearsal:run|bridge|scoring-engine-payouts:s9.24 Brackenridge
# read a job back (status, parsed bridge answer, report, log tail)
scoring-rehearsal:job|<id>
scoring-rehearsal:status        (includes the last 20 jobs)
```

Refused in a rehearsal: `scoring-rehearsal` itself, `scoring-gg-archive`,
order import, Brevo, Insider, and the recap, handicap-card, print-pack and
backup sends. They either reach outside or act on the volume, and the guard
would stop the outside ones anyway. The lane tools' own "never on Railway,
never under /data" guards admit exactly one case: `runner_scratch_ok(path)`,
true only in a runner child for a file inside `<volume>/rehearsal/`.
Guard: `test_rehearsal_runner.py`.

### Jobs stay out of live events (Front Desk #851, 2026-09-28)

The runner shares the production host. A job is REFUSED ("held: …",
nothing started) while a live score-entry round is on:
`live_event_hold()` holds from an hour before the first tee (`events.start_time`)
of any OPEN round dated today (Central) until that round is closed, and all
day if the tee time can't be read. App setting `rehearsal_hold` = 1 holds
every job by hand. The open rounds are read through
`score_entry.open_rounds_on()` (only score_entry.py touches se_*). Every job
runs under `nice -n 19`, so it loses every contest for the CPU to live
requests.

Why: Track A's 8-worker replay on 9/28 saw p95 1.77 s / max 4.65 s per save
(sandbox 137 ms). A single write on the production volume costs about
40 ms (three timed `scoring-setting-set` writes, 9/28), so eight writers
with no pause between saves queue behind each other on SQLite's one write
lock; in the sandbox a commit is ~1 ms and the queue never forms. Proven the
same hour on the same host at the same load (~95): the replay with
`--workers 1` ran p50 54 ms, p95 122 ms, max 204 ms (job
20260928T171738-tool-se-replay), against p95 1.77 s with `--workers 8`. Live entry
is not that shape (a group saves a hole every few minutes), and the child
writes its own file, so it takes no lock on the live database. The live
score-entry routes are timed from v2.513.11 (`se_write`, `se_claim`,
`se_sign`, `se_submit`, `se_card` in `/admin/health`) so Tuesday's real
numbers are on record.

The download path (option A) was written on 2026-09-27, refused by the
session's permission system as data leaving Railway, removed, and not
pursued. Kerry chose B.
