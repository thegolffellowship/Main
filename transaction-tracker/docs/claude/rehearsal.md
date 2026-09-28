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

## Not built, on purpose: getting the copy to the lanes

The copy stays on the production volume. A token-gated download of the
scrubbed copy to the lanes' sandboxes was written on 2026-09-27 and refused
by the session's permission system as data leaving Railway. How the replay
lanes reach real data is Kerry's decision (mailbox, 2026-09-27):
- **A.** Approve a download of the scrubbed copy to the lanes' sandboxes;
- **B.** run the replay ON Railway against the scratch file, in a separate
  process with `TGF_REHEARSAL=1` (needs a runner; no arbitrary code);
- **C.** lanes replay against their own synthetic fixtures now, and the
  real-data run waits for A or B.
