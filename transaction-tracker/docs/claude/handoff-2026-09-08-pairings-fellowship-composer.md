# Session record — 2026-09-08 · pairings roster, fellowship outreach, plain-text composer

**Versions v2.336.0 → v2.346.0. All live and verified on production.**
Branch `claude/mail-from-ca-79xa2a`, pushed to `main` (Railway deploys from
`main`).

This session ran on Kerry's short directives and screenshots during the
run-up to the 2026-09-08 events (s9.22 Silverhorn, a9.22 ShadowGlen). It
is written for whoever picks up next: what changed, what was verified
against live data rather than assumed, and the three hazards found on the
way that were live and are now closed.

---

## 1. Golf Genius pairing ingests (applied)

Kerry ratified "Apply both" for the championship rounds. Three applies,
all with `unresolved_names: []`:

| Ingest | Groups | Blind seats | Rows | Pairs |
|---|---|---|---|---|
| `team\|sa\|1591015\|apply\|3289` — SA CHAMPIONSHIP | 8 | 0 | 32 | 48 |
| `team\|champ26\|1692724\|apply\|3291` — 2026 TGF CHAMPIONSHIP R1 | 9 | 2 | 34 | 48 |
| `team\|champ26\|1692725\|apply\|3291` — R2 | 8 | 3 | 29 | 39 |

135 pairs restored. **Both championship rounds coexist on event 3291**,
which is what the v2.341.0 per-round uniqueness index exists for —
verified by reading the history back: Neal Cloer appears with the Wades in
one round and with Straiton / Vasquez / Jenkins in the other. Blind draw
seats excluded per Kerry's ruling.

---

## 2. The pairings roster was not the roster (v2.342.0)

> *"If someone is not in pairings, it needs to show. Like Michelle
> DelCarmen. For the open spots, I need to be able to click and select
> from a list of those players."*

`GET /api/events/<id>/pairings` builds `event_players` from the **items**
table. Michelle had only RSVP'd in Golf Genius — **verified on live data:
her RSVP rows carry `matched_item_id: null`, no order row exists** — so
she was invisible to the Unassigned panel while the Players tab showed her
all along, as a synthetic `gg_rsvp` row derived client-side.

`renderPairingsPanel(ev, registrants, rosterExtra)` now receives those
rows from both the desktop and mobile call sites and merges them onto
`state.rosterExtra`. RSVP-only entries carry a `pairing-rsvp-badge`.

**This is deliberately a CLIENT-side merge.** The unmatched-RSVP
derivation (email overrides, `matched_item_id` sanity, first-name
heuristics) lives in the page; duplicating it server-side would guarantee
divergence. When that derivation moves to the server, `event_players`
should absorb it and `rosterExtra` should go away.

`getUnassigned()` also compared lowercased name **strings** — CLAUDE.md
rule 6, and inconsistent with the stale-roster banner three lines above it
that already keyed people with `pairPersonKey()`. Both ends now use
`pairPersonKey` and the merged roster dedupes on it.

**Open seats are a first-class entry point.** Clicking an `— open —` seat
with nothing selected opens `openPairingPicker()`: the unassigned roster
with index, tee, RSVP flag and a 9/18 mismatch marker. The old behaviour
(seats as drop targets) is unchanged when something IS selected.

Test: `test_pairings_roster.js`. Docs: `docs/claude/pairings.md`.

---

## 3. Menus inside tables (v2.342.0)

> *"Can't read options in actions drop down menu."*

The Events actions menus were `position: absolute` inside a `td`, so the
next row's gear button painted over them and swallowed the text. An
earlier instance of the same class (2026-08-18) had been patched by giving
`.mobile-card` `overflow: visible` — the instance, not the mechanism.

All three menus — event card, Registrations header, per-row gear — now go
through `evOpenActionsMenu(btn)` / `evCloseActionsMenus()`, which measure
the button's rect and draw in a `position: fixed` layer at `z-index:
9000`, clamped into the viewport and flipped above when there is no room
below. Scroll and resize close them. `openPairingPicker()` uses the same
technique.

**Any new menu on a table surface must use it.** Do not add another
per-case `overflow` patch.

---

## 4. FELLOWSHIP filter badge (v2.343.0)

`items.fellowship` holds `'YES' / 'NO' / NULL` and was readable only one
player at a time behind the info icon. A `FELLOWSHIP <n>` badge in the
roster's sub-filter row (desktop + mobile) filters to the YES answers and
hides itself at zero. Silverhorn 2026-09-08: **13 YES / 9 NO / 2 blank**
of 24.

**The trap it had to avoid:** on day-games events (`gamesAxisFor()`) the
roster filter short-circuits to `axisFilterMatch()` on its first line,
which reads `activeFilter` as YES/SAT/SUN/NO. A fellowship filter arriving
there would have silently produced a games-axis roster. Both filters
answer `FELLOWSHIP_FILTER` above that branch. **Any future filter that is
orthogonal to the games axis must do the same.**

Test: `test_fellowship_filter.js`.

---

## 5. Fellowship preset in Message Players (v2.344.0 → v2.346.0)

> *"Wire up a preset selection and email in the Message Players option
> where I can quickly send an email to those who have selected Fellowship
> … Needs to be editable by me within the message modal."*

**Audience.** `fellowship` joins the audience list, client-side in
`getComposeRecipients()` and server-side in `/api/messages/send`. Both
match a leading `Y`. GG RSVP rows carry no answer and drop out.

**Preset.** System template `Fellowship — Where We're Meeting`. Selecting
it loads subject and body into the editable fields and switches the
audience to `fellowship` ONLY if the audience is still on its default
`all`, so a deliberate choice is never overridden.

**Copy as shipped** (Kerry revised the second paragraph the same day):

```
Hi {player_name},

You said YES to fellowship after **{event_name}**, so here is where we
are headed once we are off the course:

**[MEETING SPOT]**

Come over when your group finishes.

If your plans have changed and you cannot join us, just reply and let me
know, or text {manager_name} at {manager_phone}. We give the restaurant a
headcount, so an accurate number genuinely helps.

Looking forward to it,
{manager_name}
The Golf Fellowship
```

Two notes on the copy: *"the people you just played with"* was chosen over
*"the guys"* because Michelle Delcarmen, Mary Wade and Michele McCormick
are all in the fellowship-YES list; and the ask is framed as helping the
**headcount** rather than confirming attendance, which gives someone a
graceful way to drop.

**Chapter managers are data.** `{manager_name}` / `{manager_phone}`
resolve per event from the `chapter_managers` app setting via
`get_chapter_manager(chapter)`, merged over `DEFAULT_CHAPTER_MANAGERS`.
One template serves both chapters; a third chapter is a dial edit, not a
release.

| Chapter | Manager | Cell |
|---|---|---|
| San Antonio | Kerry | (210) 838-3948 |
| Austin | Robert (Straiton, cid 31) | (361) 389-9395 |

**Both numbers came from Kerry directly, not from a customer record.**
Austin shipped with an empty phone at first — Kerry said only "Robert",
and the roster holds several (Robert Straiton, Robert Light). Guessing was
not an option for a number about to be mailed to members, so the send
refused until he gave it. He then confirmed his own and supplied
Straiton's, and asked for it on the customer record too: `customers.phone`
cid 31 went `null → (361) 389-9395` via `update_customer_info` (validated,
canonical), 35 item rows synced.

---

## 6. The composer is a plain-text editor (v2.346.0)

> *"Any way to make that editor a regular text editor rather than a HTML
> editor? Also can you add spaces between the paragraphs as a standard?"*

`#compose-body` holds PLAIN TEXT. Blank line starts a paragraph;
`**stars**` make bold, the only markup the templates use. HTML is
generated by `composeTextToHtml()` on the way out; a stored template comes
in through `composeHtmlToText()`. `#compose-html-mode` ("Edit HTML") turns
the conversion off and converts what is already in the box, so the two
views never disagree.

**Every read of the body goes through `composeBodyHtml()`** — send,
preview and save-as-template. A path reading `.value` directly would mail
raw markdown; the test counts the direct reads.

Text-mode input is HTML-escaped. This is not cosmetic: Kerry's chosen
venue is **Max & Louie's**, and a bare `&` in the old raw-HTML box was a
live way to break the message.

Round trip verified against the live body: all five variables, the bold on
the event name and the address, the sign-off line breaks and the
ampersand all survive both directions; six spaced paragraphs come out.

**Paragraph spacing is a house standard applied SERVER-side**
(`normalize_email_html()` in fetcher.py, `EMAIL_P_STYLE = "margin:0 0
1em;"`), on both the send and preview paths — so templates written before
the standard get it and the preview matches what sends. A `<p>` that
already has a style attribute is left alone.

Test: `test_compose_plaintext.js`.

---

## 7. Three live hazards found on the way, all closed

These were not features Kerry asked for. Each was found while building
what he did ask for, and each was live.

**7.1 — An unrecognised audience emailed the entire roster.**
`/api/messages/send` matched audiences with a chain of `elif` ending in
`else: filtered.append(r)`. A typo, a stale browser tab or a renamed
option would have gone to everyone. `VALID_AUDIENCES` is now checked once,
up front; an unknown value is a 400. **Any new audience must be added to
that set.**

**7.2 — The system-template seed could never deliver anything new.**
It ran only `if existing["cnt"] == 0` — true once, in 2026. A template
added to the list later would have lived in the code and nowhere else:
the backfill rule (#405) in reverse. It now inserts BY NAME each boot.

Revising **wording** then needed its own mechanism, because Kerry rewrote
the fellowship note an hour after it shipped. The seed now also UPDATEs a
row when the stored body is still verbatim one of the bodies we seeded,
tracked in `_PRIOR_SYSTEM_TEMPLATE_BODIES`. An untouched seed gets the
correction; anything edited in the UI is left alone.

> **When you change a system template's wording, APPEND the outgoing body
> to that dict — never edit the entry in place**, or the previous version
> stops being recognised as unedited and deployments carrying it are
> stranded.

Before pushing the revision I read production's stored body through the
new `scoring-msg-templates` bridge command and compared it byte-for-byte
against the registered prior — 552 chars, exact match — then confirmed
after deploy that the row had actually changed (552 → 506, same id 8, no
duplicate). "It is in the code" says nothing about the live shelf.

**7.3 — A template blank could reach a member.**
The preset carries `[MEETING SPOT]`. The send handler refuses while the
subject or body still holds a `[BRACKETED BLANK]` or a `{tag}` outside
`KNOWN_VARS`, and names what is left. It guards **every** template — the
#424 lesson (`{link_offer}` in Kerry's composer) applied at the boundary
rather than to the one template that reintroduced the hazard.

A companion guard: `/api/messages/send` refuses with a 400 naming the
chapter when a template USES `{manager_name}` or `{manager_phone}` and
that chapter has no value. This is what makes it safe to add a chapter's
manager before their number is known.

---

## 8. New bridge commands (read-only unless noted)

| Command | What it does |
|---|---|
| `scoring-msg-templates[:<name fragment>]` | The message-template shelf as production holds it — names, subjects, body size, and any unfilled `[BLANKS]`. Pass a fragment to get the full body. |
| `scoring-customer-set:<cid>\|<field>\|<value>` | **WRITE.** Sets one personal-info field through `update_customer_info` (validated; `customers` row is the source of truth). Reports before/after. |

---

## 9. Verified against production, not assumed

Listed because the habit is the point, not the individual checks:

- Michelle Delcarmen's RSVP rows carry `matched_item_id: null` — the
  diagnosis, confirmed on live data before the fix was called correct.
- Silverhorn's fellowship split (13/9/2) read from the live roster.
- The live template body matched the registered prior byte-for-byte
  BEFORE pushing the revision, and the row changed AFTER deploy.
- `chapter_managers` read back after being set.
- `customers.phone` cid 31 before/after.
- The plain-text round trip run through the real conversion functions on
  the real body, not asserted from the regexes.
- Every deploy polled on `version.js` before anything was reported done.

**CORRECTION, 2026-09-10.** One item in this section was itself wrong.
This session reported `scoring-rounds` returning `[]` for events 3306 and
3313 as evidence that closeout had not started. It filters on an
item_name SUBSTRING, and the session passed event **ids** — which match
no name and return `[]`. Silverhorn's 24 cards were imported 2026-09-08
23:10, before the check ran. The claim went to Kerry in chat and to CA in
mailbox #430 §4 and was false in both places. Fixed at the source:
`get_scoring_rounds_list` now treats a numeric value as an events.id and
raises on an unknown one (`test_scoring_rounds_lookup.py`), so the trap
cannot produce another silent false negative. A verification step that
can only fail toward "nothing here" is worse than no verification step.

One thing I could **not** reproduce, and said so rather than explaining it
away: Kerry reported the pairings view showing "Group 1..6" instead of
hole labels. Both of that day's events carry correct labels (ShadowGlen
3313: Hole 1–4; Silverhorn 3306 likewise). **Still open — needs the event
he saw it on.**

---

## 10. Carry-forwards

- **The hole-assignment layout report** (§9) — unreproduced.
- **CA mailbox #428, seven asks — NOT DONE.** Listed and acknowledged in
  an earlier session, not executed: create the LSC as an event (needs
  entry price / course cost / prize structure from Kerry); add Luke Youngs
  cid 13 to `lsc_accepted`; the empty San Antonio `lead_notify_recipients`
  entry; diagnose the follow-up notifier; the reply-rate denominator; four
  unmapped ad sets; referral tracking as a real field.
- **Twilio auto-response** and a possible automatic email reply to leads
  (Kerry's own framing: later / "probably").
- **Austin's fellowship meeting spot** — the preset works there now; only
  the venue is missing.

---

*Tests added this session: `test_pairings_roster.js`,
`test_fellowship_filter.js`, `test_compose_plaintext.js`,
`test_message_presets.py`. All passing.*
