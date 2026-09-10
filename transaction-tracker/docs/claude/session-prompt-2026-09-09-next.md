> **SUPERSEDED — 2026-09-10. Do not work from this document.**
>
> Two of its claims are wrong and one is now stale:
>
> 1. **"`scoring-rounds` returns `[]` for BOTH, no scorecards imported"
>    was FALSE.** `scoring-rounds` filters on an item_name SUBSTRING; the
>    session passed event **ids** (3306 / 3313), which match no name and
>    return `[]`. Silverhorn's 24 cards had been imported 2026-09-08
>    23:10, before the check was ever run. The lookup now treats a numeric
>    value as an events.id and raises on an unknown one
>    (`test_scoring_rounds_lookup.py`), and the closeout skill documents
>    the trap.
> 2. **The "FIRST JOB" is done.** Both events were closed out on
>    2026-09-09/10 — see
>    `docs/claude/handoff-2026-09-09-event-closeout-first-run.md` and
>    mailbox #434 / #447 / #449. Handicap cards went to 31 players, the
>    Silverhorn recap was sent, and the recap house style grew rules
>    20-29 from Kerry's edit.
> 3. The open queue below has moved on. **Read the mailbox
>    (`read_platform_dialogue`) for current state** — CLAUDE.md rule 4
>    now requires that before every response, not just at session start.
>
> Kept for the record of what the 2026-09-08 wave shipped. The durable
> version of that is
> `docs/claude/handoff-2026-09-08-pairings-fellowship-composer.md`.

---

# Start-here prompt — next session (written 2026-09-09)

Paste this to start. It orients you and names the first job.

---

## Where things stand

The 2026-09-08 session shipped **v2.336.0 → v2.347.0**, all live and
verified on production. Full record:
`docs/claude/handoff-2026-09-08-pairings-fellowship-composer.md`.
Digest to CA: mailbox **#429**.

Deploy path unchanged: develop on `claude/mail-from-ca-79xa2a`, push to
BOTH that branch and `main` (Railway deploys from `main`), then poll
`https://tgf-tracker.up.railway.app/static/js/version.js` before
reporting anything done.

## THE FIRST JOB — two events from 2026-09-08 are not closed out

Kerry, 2026-09-09: *"We just had two events yesterday that need to be
closed out."*

| Event | id | Chapter | Registrations |
|---|---|---|---|
| s9.22 Silverhorn | 3306 | San Antonio | 23–24 |
| a9.22 ShadowGlen | 3313 | Austin | 16 |

**Verified 2026-09-09: `scoring-rounds` returns `[]` for BOTH.** No
scorecards imported, so nothing downstream has happened — no handicap
differentials, no MVP, no payout verification, no recap.

**Use the `event-closeout` skill** (`.claude/skills/event-closeout/`).
It is new, written this session, and never run. Work it phase by phase
and report per chapter — rule 3d, both chapters or neither.

Its §OPEN lists five things Kerry has NOT ruled on (timing, who sends
the recap, photos, fellowship attendance, and whether the checklist
should become an app surface). Raise them; do not invent answers.

## What shipped 2026-09-08, in one line each

- **Pairings roster completeness** — the panel built its roster from
  `items`, so a GG-RSVP-only player (Michelle Delcarmen, verified:
  `matched_item_id: null`) was invisible to it while the Players tab
  showed her. Both surfaces now share a roster.
- **Open-seat picker** — click an `— open —` seat, pick from the
  unassigned.
- **Person matching** — `getUnassigned()` compared name strings; now
  `pairPersonKey()`, per CLAUDE.md rule 6.
- **Actions menus** — were `position:absolute` inside a `td` and got
  painted over by the next row. All three now draw in a measured fixed
  layer. Any new menu on a table surface must use it.
- **FELLOWSHIP filter badge** on the roster, desktop and mobile.
- **Fellowship audience + preset** in Message Players, with a **Quick
  Message** button that appears when the filter is on.
- **Chapter managers as a dial** — `chapter_managers`; SA = Kerry
  (210) 838-3948, Austin = Robert Straiton (361) 389-9395. Both given by
  Kerry directly; Straiton's is also on his customer record now (cid 31).
- **Plain-text composer** + server-side paragraph spacing
  (`normalize_email_html`, `EMAIL_P_STYLE`).
- **Three live hazards closed**, none requested: an unrecognised send
  audience mailed the whole roster; the system-template seed could never
  deliver a new or revised template; a template blank could reach a
  member. See the handoff §7 — **read it before touching message
  templates**, especially `_PRIOR_SYSTEM_TEMPLATE_BODIES`.

## Open, in rough priority

1. **Close out events 3306 and 3313.** Above.
2. **CA mailbox #428 — seven asks, none done.** Three need nothing from
   anybody: add Luke Youngs cid 13 to `lsc_accepted`; fix the reply-rate
   denominator (exclude leads under 48h); name four unmapped ad sets
   (120234156686980195, 120227940458140195, 120243369245000195,
   120223064476880195). The others: create the LSC as an event (blocked
   — needs entry price, course cost, prize structure FROM KERRY; $3,300
   of deposits sits against no event record, and it is now four weeks
   out); diagnose why the follow-up notifier never fired for 13 leads;
   promote referral tracking to a real field.
3. **ASK KERRY: the San Antonio `lead_notify_recipients` address.** SA is
   67% of lead volume and the dial is empty. He was available all of
   2026-09-08 and was not asked — that was a miss, do not repeat it.
4. **ASK KERRY: Austin's fellowship meeting spot.** The preset works for
   Austin now; only the venue is missing.
5. **Unreproduced:** Kerry reported the pairings view showing
   "Group 1..6" instead of hole labels. Print packs for both 2026-09-08
   events read correct hole labels. No theory. Needs the event he saw it
   on — ask if it recurs, do not go hunting.
6. **Kerry's own framing as later:** Twilio auto-response to leads, and
   possibly an automatic email reply.

## Standing habits this project expects

- **Verify against production after every deploy.** Green tests are not
  evidence the live site changed. `scoring-msg-templates` exists because
  "it is in the code" said nothing about the live shelf.
- **Protect the class, not the instance** (CLAUDE.md). Every hazard found
  on 2026-09-08 was a safety property attached to one case.
- **Rule 3b** — money, schema, member-facing behavior or scope needs
  Kerry's explicit ratification BEFORE shipping.
- **Rule 3d** — an instruction applies to every chapter unless he names
  one.
- **Say what you did not do.** He reads the gaps.
