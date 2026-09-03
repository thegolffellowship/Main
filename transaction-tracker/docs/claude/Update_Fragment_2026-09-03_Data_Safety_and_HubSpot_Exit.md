## UPDATE FRAGMENT — September 3, 2026

**Type:** Strategic / Operational / Financial

---

### DECISION 1 — Decommission HubSpot, with extraction as a hard gate

**Decided:** HubSpot goes away as soon as it is safely viable. Every
piece of data comes out FIRST, verified, before the lead pipe changes.

**Context:** HubSpot ($42.64/mo) has one job left — carrying Facebook
lead submissions into the Tracker. That single job also causes a whole
bug class we keep paying for: duplicate leads, merged survey answers,
the re-submitter sweep, and a 15-minute delay in front of a 48-hour
conversion gate. All of them are HubSpot dedup artifacts, not Facebook
ones. Measured this session: **~7% of leads lose their campaign
attribution in the HubSpot hop** (Meta reports 85 leads, Tracker has 79
attributed + 6 "organic" = 85).

**Next steps:** Raw full export → reconciliation of 1,453 contacts into
confident / ambiguous / no-match → Kerry works the ambiguous queue →
import → signed-off verification. Only then does the pipe change, and
the cutover gate is field parity rather than a time period.

**Integration:** `hubspot-decommission-directive.md` (repo), mailbox
#394-#396.

---

### DECISION 2 — One customer, one record, back to 2007

**Decided:** The customer table is TGF's identity spine, not a list of
active people. Every HubSpot contact gets matched into an existing
customer where certain; unmatched contacts still get a customer record,
marked not-active. "Archived" means not active or opted out — it is a
state on the record, never a reason to withhold one.

**Context:** Golf Genius history keeps arriving and will eventually
reach back to 2007. Kerry wants everything possible matched into single
customer entities.

**Standing rule that comes out of it:** *confident matches merge,
uncertain matches go to Kerry, nothing is ever guessed.* A wrong merge
silently fuses two people's histories with no clean way to find it
later; an unmatched record costs one row in the archive.

**Integration:** decommission directive §10-§11; existing schema already
supports it (`account_status`, `acquisition_source`).

---

### DECISION 3 — Opted-out is its own concept, not a flavor of inactive

**Decided:** Communication consent gets its own field(s), separate from
account status, likely per channel with date and source.

**Context:** Kerry: *"opted out relates to communication correspondence
that we absolutely need to honor for our TGF Platform build and future
consolidated communications."* **Archived is a STATE — ours to change.
Opted-out is a PROMISE — theirs, and it survives every migration.**
Folding consent into account_status would eventually see it overwritten
by a routine status change.

**PARKED deliberately:** whether an active member can fully opt out. The
real line is transactional vs marketing. Not to be designed in passing.

---

### DECISION 4 — Nightly off-site backups, and the restore drill is the gate

**Decided:** The Tracker database is backed up nightly, off Railway, and
a backup is not considered real until a restore has been proven.

**Context:** The entire business — every transaction, customer, event,
membership and payout — was ONE SQLite file on ONE Railway volume. The
only "backup" was a manual endpoint writing a copy **to that same
volume**, using a plain file copy of a database the scheduler actively
writes to, which can produce a file that looks fine and fails on
restore. Kerry's developer friend independently raised the same concern.

**Built:** consistent `VACUUM INTO` snapshot that must pass an integrity
check before shipping → gzip → OneDrive via Microsoft Graph, reusing the
credentials already held for mail. **No new vendor, no new secret, no
new bill.** 7 daily / 4 weekly / 12 monthly. Failures email Kerry.

**Proven 2026-09-03 19:49 UTC:** 198.1 MB → 134.8 MB uploaded, then
pulled back, decompressed, integrity-checked, row counts compared to
live — **every table matched exactly.**

**Remaining:** one destination inside the same M365 tenant as TGF email.
Better than a same-volume copy, but not a second provider. Worth
revisiting, not urgent.

---

### FLAGGED, NOT YET DECIDED

- **Vercel is on the Hobby plan**, which prohibits commercial use. At
  Platform launch the failure mode is the project being pulled, not an
  invoice. Pro is $20/mo. Fix before launch.
- **Azure client secret expiry** (app created 2/22/2026). When it
  expires, email parsing stops and looks like "no new orders."
- **The Platform's language and framework were never actually decided** —
  they are implied by tooling (Supabase, Vercel, v0). The Supabase "TGF
  Platform" project is INACTIVE. Worth an explicit decision before the
  first line is written.
- **The current ad campaign is the best ever run** — $1.51 CPL against a
  previous best of $2.90. New creative is planned for the next campaign;
  what changed here should be preserved deliberately, not by accident.
