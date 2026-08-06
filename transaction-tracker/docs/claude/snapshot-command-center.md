# Snapshot Command Center — Member Outreach Engine (spec of record)

Written 2026-08-03 for CA's optimization session (Kerry: "I want to have
a session with them to optimize it, but want them to have full access
with everything that you created and that can be created with it").
Everything here is LIVE unless marked otherwise. The operational MCP
tool is **`snapshot_command_center`** — CA can read, preview, mark, and
test-send with it directly.

## What this system is for (Kerry's intent, verbatim anchors)

1. **A regular personalized "Your TGF Snapshot" email** — "clean and
   totally about them", "look sharp, and definitely don't want to bait".
2. **Promote the TGF Championship** — "Those two weekends (TGF Champ and
   Lone Star Cup) are the most fun TGF has to offer, hands down. They're
   our top two experiences. Fun for the family too. Nice getaways."
3. **Promote the Cup races** (Fellowship Cup + Players Cup buy-ins,
   Fall City Points Race) and **Lone Star Cup qualification** — "making
   your city's Lone Star Cup team is an even lower bar. Measuring from
   that on either the Fellowship or Players Cup would be really good."
4. **Be strategic about WHO gets WHICH message** — "a list of
   identifying who is in our window to push on entry because they're
   realistically in the mix, versus those who just gets a more
   normalized spotlight email." Availability is human knowledge ("he'll
   be in Hawaii"), so nothing auto-sends: every real send is a Kerry
   click.

## The story the email tells (all numbers verified, never guessed)

- **The Points Reset is TGF's Tour Championship** (Kerry): after the
  city championships (2026-08-02 official), seeds compress to
  100 / 99.5 / 99 / … so ~30 players sit within possible range of
  winning it all.
- **Proof of concept — Mark Freund 2024** (verified off the tgf-champ24
  GG portal, season_points_v2 widget with effective_date bisection):
  when 2024 championship weekend started he was **30th of 30 on the
  seeded board — dead last, 14.5 points back**. He finished **1st by
  2.5** over Neal Cloer, passing all 29 players ahead; Pollard (the
  leader he chased) fell to T6. On raw season points he'd been 38 back —
  the reset is what made the comeback possible.
- **The 72-point weekend** (Kerry): shooting your handicap across TGF
  Championship weekend ≈ 72 points — dwarfs the 15-point seed spread.
- **The seat line is the lower bar**: each cup path's LAST Lone Star Cup
  seat has a points value; the gap to it is often ~1 point = **one net
  bogey at the TGF Championship** (Kerry's framing, now in the email).
- **Reset differentiation (Kerry ruling)**: the city NET race's reset
  carried ONLY into THE FELLOWSHIP CUP. THE PLAYERS CUP ran its OWN
  reset and flights. The email says so explicitly.

## Key dates & money (2026)

- LSC selection deadline: **Aug 14** (`lsc_selection_deadline` dial).
- 2026 TGF CHAMPIONSHIP event: **Aug 15** (events table; signup =
  registration purchase or matched YES RSVP).
- Buy-ins (tgf-pricing, Kerry-confirmed): Fellowship Cup standalone
  **$50** ($40 pool / $10 markup — new post-City-Net option), Players
  Cup **$50**, Fall City Points Race **$50** (Best 6 + Fall
  Championship; its own race — does NOT feed TGF Champ or LSC).
- Shop links: season contests →
  `https://thegolffellowship.com/shop/ols/products/season-contests`;
  championship →
  `https://thegolffellowship.com/shop/ols/products/2026-tgf-championship`.

## The targeting queue (`snapshot_target_list` / `snapshot_center_queue`)

Walks THE FELLOWSHIP CUP + THE PLAYERS CUP live boards once (LSC
chapters only) and segments every player with a tracker profile:

- **push_entry** — in the window, NOT bought into either cup. Window =
  ≤15 points back of the lead (reset seeds) OR within 15 of an LSC seat
  line (`window_points` / `seat_window`, both tunable per call).
- **defend** — in the window AND bought in (motivate, don't pitch).
- **normal** — everyone else (gets the normalized snapshot).

Every entry carries: per-path `points_back`, `gap_to_seat`,
`seat_cut_points`, `enrolled_any`, `secured_seat` (locked LSC seat),
and **`tgf_champ_signed_up`** (the second ask layer — None until a fall
championship event exists; it exists now; as of v2.204.0 this means a
registration PURCHASE only) plus **`tgf_champ_rsvp_only`** (YES RSVP /
rsvp_only row, no purchase — renders the amber "◐ RSVP · not paid"
tier in the queue, and the chase email swaps to "You're RSVP'd for the
TGF Championship. Two steps left: 1. Sign up... 2. Get in on the Cup
races" — or the one-step variant when a cup buy-in already exists). Live counts 2026-08-03:
push 41 / defend 26 / normal 70 — only 4 of the 41 push players were
championship-registered.

## The email (`build_player_snapshot_email`), block by block

1. Dark header: TGF logo left (interim G-icon; official white roundel
   pending via design-handoff), eyebrow YOUR TGF SNAPSHOT, **player
   name as the headline**, chapter · date.
2. 9-Hole Index (`xx.xN`).
3. **City Net — Final** lead-in: finish, points, reset conversion
   "carried into THE FELLOWSHIP CUP".
4. WHERE YOU STAND table: Fellowship Cup then Players Cup, "(not
   entered)" tags, Players Cup "(own reset · <flight>)" tag + footnote.
   Every race name deep-links to the member Leaderboard
   (`/member/contests#race=<tab>&player=<cid>` — tabs: tfc, gross, net,
   austin) landing centered + pulsing.
5. **Immediate CTA** (one button): BUY IN NOW (outside a cup) or SIGN
   UP FOR THE TGF CHAMPIONSHIP (in, unregistered); omitted if both
   handled.
6. Faded-orange story block: reset framing, live within-15 count,
   72-point math, Freund 2024.
7. Navy LONE STAR CUP block: per-path seat-line measurement with the
   net-bogey kicker; path names linked.
8. Faded-orange WAYS IN block (only when not in both cups): the three
   $50 options + BUY IN NOW pill.
9. "Be there for the weekend itself" (only when not championship-
   registered): the top-two-experiences pitch + signup pill.
10. SEE YOUR FULL SPOTLIGHT pill → `/member/spotlight?player=<cid>` +
    live-data footnote.

Subject: "Your TGF Snapshot — X points off the lead" / "— you're the
one they're chasing" (leader).

## Send governance (rule 3b — DO NOT weaken)

- **Test sends** (to the admin/Kerry inbox) are unrestricted — that is
  the review loop.
- **Real member sends** require an **approved mark** set in the Command
  Center; Kerry's Approve click is the per-send ratification. There is
  deliberately NO bulk send anywhere. Marks:
  approved / deferred(note, e.g. "in Hawaii until Sept") / skipped /
  sent(+timestamp+address), persisted in the `snapshot_center_marks`
  app setting.
- Future (task #23, needs Platform player logins): member self-service
  "out of town" calendar windows.

## Access surfaces

- **MCP tool `snapshot_command_center`** (CA's surface): actions
  overview / queue / targets / preview / mark / send_test / send —
  see the tool docstring.
- Admin UI: `/admin/snapshot-center` (tabs, preview modal, marks,
  gated sends) — in every admin subnav.
- HTTP: `GET /api/snapshot-center/queue`, `POST .../mark`,
  `GET .../preview?cid=`, `POST .../send` (admin PIN).
- Bridge (probe_golf_genius extract=): `scoring-snapshot-targets`,
  `scoring-snapshot-email:<cid>[|<to>][|send]`.
- Data layer: `snapshot_target_list`, `snapshot_center_queue/mark/send`,
  `build_player_snapshot_email`, `_tgf_champ_signups` in
  `email_parser/database.py`.

## Optimization levers CA can work with (the session agenda)

- **Window criteria**: `window_points` (default 15) is the ONE gate as
  of v2.205.0 — Kerry 2026-08-06: players 16+ off the lead go Normal
  even when the seat-line gap looks close, so `seat_window` no longer
  qualifies anyone by itself (kept for signature compat + display).
- **Segment copy variants**: today one builder serves all segments.
  DEFEND tier arguably needs "protect what you built" instead of the
  comeback pitch; NORMAL gets facts-not-pitch. The builder is one
  function — variants are straightforward.
- **Cadence**: when does the "regular" spotlight email fire (post-event?
  weekly? milestone-triggered: seat line crossed, rank change)?
  Scheduler exists (APScheduler); nothing is scheduled yet by design.
- **Championship-weekend sequencing**: LSC deadline Aug 14, championship
  Aug 15 — the seat-line pitch expires; sends this week hit hardest.
- **New signals**: RSVP/attendance history, winnings, handicap trend
  (all in the spotlight payload) are available to the builder.
- **Design**: design-claude pass in flight (mailbox #269-#272): full
  roundel header, hierarchy/spacing, CTA treatment.
- **Measurement**: `member_analytics` (the traffic beacon) counts
  member-page opens/clicks — deep links from the email land there.
  Per-send attribution IS built as of v2.202.0 — see below.

## Open/click tracking (v2.202.0 — Kerry: "Build the email tracking")

Every `build_chase_email(send=True)` generates a `secrets.token_urlsafe(12)`
token and instruments the outgoing HTML (`_instrument_tracking` in
`chase_email.py`):

- **Opens**: a 1x1 GIF at `GET /t/o/<token>.gif` appended before
  `</body>`. Route serves the pixel unconditionally (junk tokens
  included) with `Cache-Control: no-store`.
- **Clicks**: every `href="http(s)..."` is rewritten to
  `GET /t/c/<token>?u=<urlencoded target>`; the route records the click
  and 302s to the target. **Allowlist** (`_TRACK_REDIRECT_HOSTS` in
  app.py): tgf-tracker.up.railway.app + thegolffellowship.com(+www) —
  anything else (or a junk scheme) redirects to /member/spotlight, so
  the endpoint is never an open redirect. `mailto:` (unsubscribe) is
  never wrapped; `src=` image URLs untouched.

Storage (`email_parser/database.py`, lazily created):
- `email_sends` — token PK, `customer_id` FK (rule 6), sent_to,
  `is_test`, subject, sent_at (Central), opened_at/open_count,
  clicked_at/click_count.
- `email_send_events` — raw beacon stream (kind, url, user_agent,
  created_at UTC).

Wiring: `email_tracking_register` records the send only after Graph
accepts it; `email_tracking_record` handles both beacon kinds.
`snapshot_center_queue` joins `_email_tracking_latest` (latest REAL
send per customer) onto each row; the Command Center renders green
OPENED / orange CLICKED chips with first-timestamps + ×N counts next
to the mark chip. Test sends (no explicit to_address → recap inbox)
are `is_test=1` and excluded from the chips, so Kerry's own opens
never read as member engagement.

Honesty caveat (surfaced in the UI comment): opens are a FLOOR —
Apple Mail Privacy Protection / Gmail image proxies may prefetch the
pixel (over-count) while image-blocking clients report nothing
(under-count). Clicks are the hard signal.

## Change protocol

Copy, criteria, segment logic, and cadence changes route through Kerry
(member-facing, rule 3b). CA proposals land via the platform dialogue
mailbox (`post_platform_dialogue`, TO: tracker-claude) or a Kerry
session; tracker-claude implements.
