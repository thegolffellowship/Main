# Who brought this player — referral attribution (BUILT, v2.473.0, 2026-09-21)

Kerry, on Ty Bubela: *"How can I add a customer/transaction as a sub-lead
from a lead player? Ty Bubela signed up on his own, but he is a referral
from lead member convert Justin Angelone. And how could we have something
automated for 1st Timers to guess at it and have confirmation for tagging
correctly. Could be a referral, could be someone that found via another
means, but would be good to track."*

This is the #413/#416 referral model, deferred twice, now with a concrete
case. **BUILT the same day.** Kerry, standing on Ty's customer page: *"When I
click Ty Bubela under Leads to attribute it just goes to customer. How am
I supposed to attribute him to Justin Angelone?"* — the third time he
asked for this, so the proposal below was taken as ratified and shipped.
The one deviation from §3 is recorded there.

## 1. What exists today

| Fact | Where it lives | Who writes it |
|---|---|---|
| Who brought them | `customers.referred_by_customer_id` + `referred_at` | `set_referred_by()`, called from ONE place: assigning a guest off a member's purchase |
| Referral FEE owed/paid | `referral_fees` (coupon \| receipt \| manual) | coupon scan, receipt scan, `scoring-referral-add` |
| Channel they arrived through | `customers.acquisition_source` | parser (`godaddy`, etc.) |
| Who they asked to play with | `items.partner_request` | order form |
| Referrer named on a manual lead | `leads.payload._referred_by` (TEXT) | Add Lead form |

**The collision.** `referred_by_customer_id` today means *"I paid for this
person's spot."* Kerry means *"this person brought them to TGF."* Justin
did not pay for Ty, so writing it today would be a false sentence. That is
why `add_lead` deliberately parks its Referred-by in `payload` as text
(leads.py ~2409) instead of on the customer.

Consequence: **there is no way, in any surface, to record that Justin
brought Ty.** Ty's `referred_by_customer_id` is NULL and there is no
control that would set it.

## 2. BUILT — widened, with the provenance beside it

One fact, one field. `referred_by_customer_id` becomes *who brought this
player*, and a new sibling column says **how we know**:

```
customers.referred_by_source  TEXT   -- bought_spot | coupon | partner_request
                                     -- | lead_form | member_claim | kerry
customers.referred_by_note    TEXT   -- free text, Kerry's words
```

- The paid-spot case keeps working; it just stamps `bought_spot`.
- `referral_fees` is untouched. **Recording a relationship still never
  mints a liability** — the ratified rule from 2026-07-30 holds.
- `acquisition_source` is untouched. Channel and person are independent
  facts; a transaction can be both (Kerry, 2026-07-30).
- `leads.payload._referred_by` gets resolved to a customer_id on
  conversion and stops being a dead-end string.

Also needed, because "not a referral" is a real answer Kerry named:

```
customers.found_us_via  TEXT  -- referral | facebook_ad | instagram | search
                              -- | drove_by | event_flyer | other | unknown
```

### Where it actually lives (deviation from the earlier ratification)

Kerry ratified "the Leads page band" on 2026-09-21 — *before* the
dashboard existed. Once it did, he clicked a first timer from the
dashboard card and landed on the **customer page**, which is where he
expected to answer. That is also the right place on the merits: Ty is a
CUSTOMER, not a lead (he signed up directly and has no lead row), so his
record is where the fact belongs.

So the split is:
- **The dashboard card is the QUEUE** — "First timers to attribute", 24
  of them, newest first. It counts and links; nothing is worked there
  (the router rule).
- **The customer's Info tab OWNS the answer** — a "Who brought them"
  block with a name picker over the canonical customer list, a
  not-a-referral dropdown, and Clear. Three answers, exactly the three
  Kerry named.

`POST /api/customers/<id>/referred-by` takes `{referrer_customer_id,
source?, note?}` or `{found_us_via}` or `{referrer_customer_id: null}`.
Guards: `test_referred_by.py` (the data rule, 19 checks) and
`test_referred_by_ui.js` (the page's real renderer, picker and wiring, 25
checks — written because the previous thing shipped on this surface was a
dashboard that rendered fine and never ran its loader).

## 3. Proposal — the 1st Timer guesser

Trigger: a registration whose `user_status` is `1st TIMER`, or any
customer's first purchase. Produce ONE ranked candidate list; write
nothing.

| # | Signal | Strength |
|---|---|---|
| 1 | Guest item on another customer's order | certain — already auto-derived |
| 2 | `coupon_code` = `tgf-referral-<name>` | certain — already parsed |
| 3 | The first timer's `partner_request` names a member | strong |
| 4 | A member's `partner_request` on the same event names the first timer | strong |
| 5 | Lead record's `_referred_by`, or the survey's "How did you find out about TGF?" | strong |
| 6 | Shared surname + address/zip with an existing customer (family) | strong — would have caught Duncan Fieber as Scott's son |
| 7 | Same event, same zip / same fellowship group | weak — offers a pick list, never auto-fills |

**Confirmation, never auto-write.** A card per unattributed first timer
with three possible answers, matching Kerry's own framing:

1. a **person** (tap the guessed name, or search),
2. a **channel** (found us another way → `found_us_via`),
3. **unknown** (parked, re-offered next time, never nagged twice).

Kerry's words, so the UI cannot silently guess wrong: *"Could be a
referral, could be someone that found via another means, but would be good
to track."*

**Where the card lives — RATIFIED (Kerry, 2026-09-21): the Leads page**,
as an `UNATTRIBUTED FIRST TIMERS` band under the funnel stages (v2.371.0
gave that page the stage model already). *"Leads page band seems the
best."*

### The landing-page question Kerry raised alongside it

*"perhaps a cue on the landing page (Currently EVENTS)...or maybe I
should be landing on a DASHBOARD page that summarizes anything current
that I can go to with a click. Could be this week's events that I could
click to work...new players that need to be denoted like Ty Bubela for
potential lead development...perhaps checklists, etc."*

Not ratified. The counsel on the record, so the next session does not
re-derive it:

- **TGF already has three "what needs me" surfaces**: the COO dashboard's
  `action_items`, the CA Queue (`/admin/ca-queue`), and the daily digest
  email. A fourth makes the problem worse unless it absorbs or replaces
  one. This is the same accretion Kerry's own UX directive
  (`ux-directive-work-surfaces.md`) was written about.
- **A dashboard earns its place only as a ROUTER, never a workspace.**
  Every card is a count and a link to the surface that owns the work.
  Nothing is worked on it. The moment you can act on a card, it competes
  with the page it links to and they drift.
- **A card with nothing in it does not render.** A dashboard that always
  shows twelve cards becomes wallpaper by the second week; one that shows
  three today and six tomorrow keeps being read.
- The feeds all already compute: this week's events, unattributed first
  timers, follow-ups due, unpaid payouts, the expense queue, renewals
  due, CA Queue rows. Nothing new needs deriving — this is assembly.
- Strategic fit is good: a page that says *who needs you today* is the
  people-manager model made visible, and it is the thing a future chapter
  leader lands on.

## 4. What it unlocks

- Member-sourced growth becomes a number next to ad-sourced growth. Today
  the Lead Center's ORGANIC view is a shrug; this names the member.
- The referral FEE program gets a candidate feed instead of waiting for a
  coupon nobody redeemed (`#413`: the word-of-mouth referral Kerry knows
  about but never saw a coupon for).
- Ambassadors: `customers.ambassador` exists and is unused. Who brings
  people is the input that column was waiting for.

## 5. Pending, not lost

**Ty Bubela (cid 829) ← Justin Angelone (cid 709)** — Kerry,
2026-09-21. No longer held: §2 shipped, and the record now says
`member_claim`, which is true (Kerry told us) where `bought_spot` would
not have been.

## §6 — Residual ROI: what the Billeaud precedent actually was (2026-09-21)

Kerry: *"I tied Justin Angelone to Ty, but shouldn't Ty automatically
add to the campaign Justin comes from as a sub-lead residual ROI? I
thought we crossed that bridge in another situation with Logan Billeaud
bringing his father."*

**Checked, and the bridge we crossed was a narrower one.** Production,
2026-09-21:

| | source | campaign_id |
|---|---|---|
| Logan Billeaud (791) | `hubspot` | **1 — Fall 2026 Leads** |
| Rick Billeaud (795) | `referral` | **NULL** |
| Zac Hammond (819) | `organic` | NULL |
| Geoff Hightower (818) | `organic` | NULL |

What was built for Logan and Rick was *recording the relationship*:
`add_manual_lead(source="referral", referred_by=…)`, with the referrer
parked as TEXT in `payload["_referred_by"]` precisely because the
referral model was not ratified. Rick's campaign_id is NULL. **Logan's
campaign has never been credited with Rick.** No residual ROI exists
anywhere in `campaigns.py`; the word "residual" in that file is about
allocation dates, not referrals.

So this is a new rule, not an existing one, and it is a rule-3b change:
it alters what Return on Ad Spend means.

### What shipped now (the safe half)

Attributing someone mints them a lead: `source='referral'`,
`campaign_id=NULL` — Rick's shape exactly. They become trackable in the
Lead Center and land in the ORGANIC bucket, which is where Kerry put
Hammond and Hightower on 2026-09-10 so they could not inflate ROAS.
Nothing about ad spend changed.

### What needs Kerry's ruling (NOT built)

Crediting Justin's campaign with Ty means setting a referred person's
`campaign_id` to their referrer's, or carrying a second field the ROI
math reads. Either way ROAS moves, so the mechanics need answering
first:

1. **Gate.** Kerry: *"A referral only comes when the person buys a
   membership."* So the credit switches on at membership purchase, not
   at signup. Ty is a first timer today; the credit would be $0 until he
   joins. Agreed — but it means the feature is dormant on arrival.
2. **Shown how?** Merging referral margin into the campaign's number
   silently changes a figure Kerry has been reading all season. The
   recommendation is a SEPARATE line — "direct" and "+ referred" — so
   the ROAS he has been tracking stays comparable to itself and the
   residual is visible rather than baked in.
3. **How deep?** If Ty later brings someone, does that third person also
   credit campaign 1? Recommendation: ONE hop. Second-order credit is
   defensible; infinite chains make every campaign eventually responsible
   for all of TGF.
4. **How long?** A campaign that ran in March collecting margin from a
   referral in November is arguably true and arguably meaningless.
   Recommendation: no time limit on the credit, but the residual line
   carries the date so an old campaign's tail is legible.
5. **Whose margin?** All of Ty's spend, or only his membership? The
   membership is what triggers it; counting everything he ever spends is
   the honest measure of what the ad bought.

Until those are answered, `ensure_referral_lead` deliberately writes
`campaign_id=NULL`, and Ty stays in ORGANIC.

## §7 — RATIFIED 2026-09-21: residual ROI, and membership as the fee trigger

Kerry, on the §6 questions: *"Build it with the separate '+ referred'
line."* And: *"ROAS to me, includes the people that Leads
referred/brought/became members and anything they purchase in the
future. Perhaps there's a toggle to show the pure lead ROAS vs all lead
referrals included in there, but they're ultimately generated from that
Campaign where the Lead originated."*

That reasoning is sound. The ad bought the lead; the lead brought the
member; the member's spend traces back to the ad. Two things keep it
from turning into a number nobody trusts:

**DIRECT never moves.** `roi` is computed exactly as before, from the
campaign's own leads. The residual is `roi_referred`, a separate block
carrying its own margin plus the combined total. The Leads stats panel
defaults to Direct and toggles to "+ Referred". Nothing is folded in
silently, so the ROAS Kerry has read all season stays comparable to
itself.

**The rules, all his:**
1. Membership is the gate. A referral who has not joined contributes
   nothing. Once they join, ALL their value counts — "anything they
   purchase in the future."
2. One hop. A referral of a referral does not credit the campaign again.
3. Never double-counted. Anyone already in the campaign's lead set is
   dropped from the residual; they are direct value.

**One caveat worth stating**, since it affects how the toggled number
should be read: the residual only grows. An older campaign has had more
time to accumulate referrals than a recent one, so "+ Referred" is not a
like-for-like comparison across campaigns of different ages. Compare
campaigns on Direct; use "+ Referred" to see what a campaign ultimately
generated.

### The fee trigger (amends the 2026-07-30 rule)

Kerry: *"Should tie to referrals as well, if they become/became a
member, which in this case with Guillermo Arevalo, is true. He was
Robert's referral and became a member so it needs to trigger a referral
fee payment."*

The 2026-07-30 rule — a relationship must never mint a liability — is
**narrowed, not repealed**. Naming who referred someone still owes
nobody anything. What creates the fee is the relationship PLUS a
membership purchase, which is the event Kerry actually pays for.

`sync_referral_fees` gains a third scan: an attributed referral with a
membership raises an OWED row, `source='membership'`, at the configured
fee. It is idempotent, and **any existing row for the pair suppresses
it** — so the 2026-07-28 coupon rule still wins outright and a redeemed
coupon is never topped up with cash.

Guard: `test_referral_fee_membership.py` (16 checks), including that the
relationship alone still mints nothing.
