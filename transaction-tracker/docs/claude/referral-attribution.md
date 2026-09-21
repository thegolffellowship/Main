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
