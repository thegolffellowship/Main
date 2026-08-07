> **Repo copy of the next-session prompt.** OneDrive name:
> `TGF_Tracker_Session_Prompt_EventSpecific.md` (OneDrive → `7_Web & App Development\`).
> Context: `handoff-2026-08-07-event-specific-entry-refunds.md` (= `TGF_Tracker_EventCreator_Context_v1_1.md`).

# SESSION PROMPT — EVENT-SPECIFIC ENTRY, REFUNDS & GAME OPTIONS

You are helping Kerry Niester make the TGF Tracker handle **multi-day events** in the two
places it still can't: **Add Player** and **Credit/Partial Refund**. The 2026 TGF
CHAMPIONSHIP plays **2026-08-15/16** with a Friday **08-14** practice round, and it is the
first TGF event sold as day-combination packages. Display was fixed 2026-08-07; entry and
refund were not.

---

## CONTEXT FILE
`TGF_Tracker_EventCreator_Context_v1_1.md`
**Read it before doing anything else.** It carries the 14 live package prices, the ratified
side-games bundle split, Jeff Young's already-derived refund numbers, and the traps.

---

## REPO / BRANCH
- `thegolffellowship/Main` → `transaction-tracker/`
- Develop on `claude/tgf-tracker-champ-points-g62t9l`
- **Push BOTH refs every time**: `git push origin HEAD:main` AND
  `git push origin claude/tgf-tracker-champ-points-g62t9l`. Railway deploys `main`; the stop
  hook watches the branch. Pushing one and not the other silently lags (happened last session).

---

## THIS SESSION HAS NETWORK ACCESS — USE IT
The cloud environment "The Golf Fellowship" now allows `*.up.railway.app`. Unlike the last
session you can reach `https://tgf-tracker.up.railway.app` directly. **Verify your own
deploys** — read `/static/js/version.js` and confirm `TGF_VERSION` matches what you pushed
before telling Kerry it is live. Do not make him check.

MCP (`mcp__TGF_Transaction_Tracker__*`) also works but **flaps** — it dropped and reconnected
repeatedly last session. Direct HTTPS is now the fallback; use whichever is up.

---

## WHAT THIS SESSION NEEDS TO ACCOMPLISH

**Step 0 — One answer from Kerry before building anything**

**Is the GAMES axis (YES/SAT/SUN/NO) a replacement for NET/GROSS/NONE, or a second,
day-shaped axis alongside it?** A Saturday-only buyer is still in Saturday's net AND gross
games, which suggests these are orthogonal questions, not one question. Design nothing until
Kerry answers — the wrong call here bakes a bad schema into the money path.

*(The guest practice-round pricing question from the previous session is CLOSED — $120
everywhere, tracker and website both updated and verified. Do not reopen it.)*

**Step 0b — 2-minute cleanup, no ruling needed**
The store's guest ALL 3 DAYS variants still carry the option label
*"...(Fri Practice + Sat/Sun Champ) = **$450**"* while charging $460/$560. A guest reads the
label, does `450 + 100`, expects `$550`, gets billed `$560`. Remind Kerry to fix the option
text to `= $460` — it is a website edit, not a code change.

**Step 1 — Add Player package dropdown** (context carry-forward #1, task #34)
On a package-config event, offer a Package picker that sets holes + side_games + price in one
choice. This is what would have prevented Robert Straiton being comped in as 18 holes when he
is a both-days player. (Straiton himself is fixed — 36 holes, pinned to *Both Days + Side
Games - Member*. The modal that produced the error is not.)

While here, consider adding an **`assign_event_package` MCP tool** — pinning a package is
currently UI-only, which is why the previous session could not land Straiton's badge itself.

**Step 2 — Event-specific Credit/Partial Refund** (carry-forward #2)
Per-day refund components driven by the event's package ladder rather than the hardcoded
`gross_games`/`net_games` set. First real case: **Jeff Young (item 2507)** dropping the Friday
practice round — **$105**, Full Weekend → Both Days + Side Games, displayed holes 54 → 36, side
games untouched.
**Gotcha already found:** `app.py:7032` validates `new_holes` against `("9","18")` only. It
will reject 36/54. Widen it as part of this step.

**Step 3 — GAMES options** (carry-forward #3) — ONLY after Step 0 is answered
YES / SAT / SUN / NO for this event. **Bigger than Steps 1–2 and it touches the money path**
(pot sizing, `_champ_roster_bundles`, payouts) — not display-only like the hole tabs. Scope it
with CA; do not half-ship it before 08-15.

---

## CRITICAL NOTES FOR THIS SESSION

- **Never guess a package price.** Kerry's entry through the UI IS the rule-3b ratification.
- **Rule 3b applies to Steps 2 and 3** — money path. Get an explicit Kerry ratification before
  shipping, not after.
- **Do not backfill `items.holes` from packages.** Hole display is derived (`rowHoles()`); the
  boot heal owns that column. 36/54 typed by hand DO survive now (`_is_multi_day_holes`).
- **MCP writes are guarded (v2.208.0).** Six destructive tools need `confirm=true` after a
  preview, and every write lands in `agent_action_log`. Any new destructive tool must follow
  the same shape.
- **There is still no `assign_event_package` MCP tool.** If you need to pin a package
  programmatically, build the tool properly — do NOT poke `event_package_configs` through the
  `scoring-setting-set` bridge. That was tried and silently no-op'd; a malformed write there
  would wipe 14 Kerry-entered prices.
- **⚠ The `tgf-pricing` skill file is CORRUPTED.** Its tables have dollar figures replaced by
  stray words ("round,", "an", "vs", "Guest", "championship", "price"). Example: New Member
  reads `$44 | round, | $50` where the middle cell should be `$6`. Kerry uses this document
  for **Texas sales-tax filing**. Repairing it against
  `TGF_Pricing___Services_Master_Document_v2_0.md` should be raised with Kerry early — it is
  a bigger problem than anything in this prompt.

---

## OPEN ITEMS CARRIED IN (not this session's focus)
Task #15 FLIGHTS mechanism · #18/#19 mobile waves 2 & 3 · #22 LSC decline cascade ·
#23 out-of-town availability · #30 inbound-Venmo triage · #31 course-chapter tagging

---

## START THIS SESSION BY SAYING:

"I've read the context file. Guest pricing is closed ($120 everywhere, verified live) and
Straiton is pinned, so the open work is Add Player, per-day refunds, and the GAMES axis.

One thing I need from you before I design anything: **is YES/SAT/SUN/NO replacing
NET/GROSS/NONE, or sitting alongside it?** A Saturday-only player is still in Saturday's net
*and* gross games, so I suspect those are two different questions and I don't want to collapse
them into one field wrongly — that would bake a bad assumption into the pot math.

Also a 2-minute one for you: the store's guest ALL 3 DAYS label still says '= $450' while
charging $460/$560, so a guest expects $550 and gets billed $560.

While you answer, I'll start on the Add Player package dropdown — contained, and it's the one
that would have caught Straiton."
