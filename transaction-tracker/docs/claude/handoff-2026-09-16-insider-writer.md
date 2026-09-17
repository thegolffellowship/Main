# Insider Writer — lane handoff (2026-09-16)

Branch `claude/insider-writer-0e4788`. Spun off from the closeout lane
(mailbox #538); ack #539. **v2.463.0 is ON MAIN (2026-09-17, Kerry: "Go with
your order. Push to main.")**; the angle order below is ratified and set on
the dial. Routines: Wednesday ~8:30 AM CDT (draft → get Kerry to SEND) and
Friday ~1:30 PM CDT (scorecard by group), both firing into this session.
v2.462.6 (`scoring-brevo-campaign-split`) shipped the same day; mailbox #541–#543
carry Insider #3's +8h / +24h reads and the audience split (~70% of recipients
have never bought). Companion rules:
`docs/claude/event-recaps.md` ("THE WRITER" block + the Insider #3
lessons); voice memory: `docs/claude/templates/insider-voice-examples.md`.

Kerry's brief, verbatim (2026-09-16): *"I'm thinking you don't auto post to
Brevo each week, but instead send me an email of what you suggest, that I
can edit and approve. I want it to be creative though. I don't necessarily
want the same format each time with the '3 things.' I think we need to be
more diverse about it. We need to explore more of The Golf Fellowship and
what it provides. So many avenues for potential."* and *"yes, I am
comfortable, ultimately, allowing an AI-written draft with options to choose
from. I would ultimately work back and forth with it to hone the message
that can be committed to memory."*

---

## 1. What exists now

`email_parser/insider_writer.py` (new) + `email_parser/insider.py` (extended)
+ three bridges in `mcp_server.py`. The Wednesday 13:00 UTC job is
unchanged in shape; in `review` mode (the dial since 1:19 PM CDT today) it
now runs the writer:

```
gather_week()  →  pick_angle()  →  writer_facts()  →  write_insider()  ─ok─→  compose_from_writer()
                                                            │ WriterError / lint hit
                                                            └────────────→  compose()   (deterministic fallback)
                →  render(story=…)  →  lint()  →  send_review_preview()   (email to Kerry + mailbox #insider-review)
```

Nothing in this path touches Brevo. Brevo gets a DRAFT only through
`approve_insider()` = `scoring-insider-approve:<subject>|<html>`, from the
text Kerry approves, and Kerry sends.

### The angle rotation (data, not code)

| key | title | needs this week | pins band |
|---|---|---|---|
| `tuesday-story` | A Tuesday story | — | — |
| `first-timer` | A first-timer's night, start to finish | a first-timer on a card | — |
| `fellowship` | The fellowship afterward | — | — |
| `handicap-fair` | How the handicap makes a 20 and a scratch equal | — | skill |
| `saturday-18s` | The Saturday 18s and road trips | a Saturday 18 on the calendar | — |
| `season-contests` | The season contests, explained plainly | — | — |
| `hio-pot` | The Hole-In-One pot | — | hio |
| `twenty-seasons` | Twenty seasons of TGF | — | — |
| `course-of-week` | A course of the week | — | — |
| `member-words` | A member's own words | a quote on `insider_member_quote` | — |

Dials (all `scoring-setting-set:<key>|<value>`): `insider_angles` (comma
list = the ORDER; unknown keys dropped), `insider_angle_force` (one key for
the next run, consumed by the scheduled run), `insider_writer` (`off` =
composer only), `insider_model` (default `claude-sonnet-4-5`, the parser's
proven route; env `INSIDER_MODEL` also honoured), `insider_member_quote`
(`{"name":"Adam B.","quote":"…"}`), `insider_facts_history` (replaces the
twenty-seasons facts). History lives in `insider_angle_history` (JSON), written
ONLY by the scheduled run (`record=True`), so dry runs and samples never
advance the rotation. `scoring-insider-angles` shows all of it.

**RATIFIED 2026-09-17 — the dial holds Kerry's order: `first-timer, fellowship,
handicap-fair, tuesday-story, saturday-18s, hio-pot, season-contests,
course-of-week, twenty-seasons, member-words`.** Next Wednesday (2026-09-23)
runs `first-timer` if the week has one, else `fellowship`.

### The call

One `messages.create` a week (`_client_create`, the only SDK touch; mocked
in tests). System prompt = `PUBLIC_RULES` (the #381 guardrails + the Insider
lessons, and they WIN over the member-recap style) + the voice-examples
file + `event-recaps.md` in full (voice and Kerry's corrections). User turn
= the angle brief + the fact sheet as JSON + the output schema. The fact
sheet already carries every name as first + initial, the URL allow-list,
the surnames that must not appear, the recent headlines, the pot as a
string, the handicap spread, next Tuesday per chapter, the Saturday 18s,
the season-contest mechanics without dollar figures, the history facts.

Failure classes: SDK auth / credit → `maybe_alert_anthropic_billing` +
fallback; non-JSON → one retry ("return ONLY the JSON object") → fallback;
validation problems → one retry with the problems listed → fallback; lint
hit after render → fallback. The review email's banner says which.

### Review → approve loop

1. Wednesday 8:00: Kerry gets `REVIEW: TGF Insider | <headline>` — orange
   banner (angle, why, three headline options, writer/fallback, lint) over
   the rendered Insider. Mailbox `insider-review` carries the digest.
2. Kerry replies in chat with edits (or picks a headline / mixes options).
3. The lane folds each edit into `event-recaps.md` as a numbered lesson AND,
   when it is a sentence he wrote, into `insider-voice-examples.md`. That is
   the "committed to memory" mechanism: the next call reads both.
4. The lane renders his final text (a dry run with the edits applied, or his
   HTML), then `scoring-insider-approve:<subject>|<html>` → lint → Brevo
   DRAFT → link emailed → `insider-approved` in `message_log` (so the
   headline rotation sees the title he actually used).
5. Kerry sends from Brevo.

`scoring-brevo-draft:samples|first-timer,fellowship,handicap-fair` puts
three angles in ONE review email — Kerry's "options to choose from".

## 2. What was verified

- `test_insider_writer.py` — 60 checks, all green: catalogue + dial
  ordering, history-based pick, force + consume, skips for missing facts,
  fact sheet in public form with the forbidden-surname set, prompt
  contents, JSON fences, surname leak → retry → fallback, off-list link
  unwrapped and `<script>` stripped, banned words / stray dollars / the pot
  allowed / recent headline refused / 'alone', 2- and 4-beat renders lint
  clean with the merge tags intact, angle-pinned bands, the
  `AuthenticationError` → billing alert → fallback path, `writer=False`,
  the scheduled-run recording, review email + mailbox digest, samples
  email with three banners, approve (prefix, lint, Brevo draft, ping, log)
  and its refusals.
- `test_insider.py` + `test_insider_headline.py` unchanged and green.
- `python -c "import ast"` on the three edited modules.

## 3. What was NOT run, and why

- **No live Claude call from this sandbox** — the session has no
  `ANTHROPIC_API_KEY` (only the proxy URL; a probe returned 401). The
  three-angle sample on this week's facts (s9.23 Quarry / a9.23 Avery
  Ranch) therefore runs on production: after the merge to `main` deploys,
  `probe_golf_genius extract="scoring-brevo-draft:samples|first-timer,handicap-fair,fellowship"`
  emails Kerry one message with the three drafts and posts the mailbox
  digest. Whoever runs it: read the mailbox post back and check the
  banners say "Written by the Insider writer", not "fell back".
- **Insider #3 is already SENT** (Brevo campaign 19, 1:16 PM CDT today,
  Kerry's edit of the 8:00 deterministic draft). The sample is for his
  evaluation of the writer, not for this week's send.
- **The angle order is not ratified.** Proposed in the digest; the dial is
  the ratification surface.

## 4. Traps for the next session

- `record=True` only from the scheduled job. A `review` bridge call is a
  preview and must not advance the rotation or consume the force dial.
- The writer never sees a surname: `writer_facts()` converts, and
  `validate()` refuses any surname from `forbidden_surnames`. If a new fact
  source is added (standings leaders, winners), convert it there.
- `render(story=…)` swaps the template's fixed three-beat block for N
  beats by regex on the exact `{{BEAT_n_*}}` lines; if the template's
  story box is restyled, keep the `<p style="…"><strong>{{BEAT_1_LEAD}}</strong> {{BEAT_1_BODY}}</p>`
  shape or update `_BEAT_BLOCK_RE`.
- The only dollar figures that survive `validate()`/`lint()` are the pot
  (exactly as `hio_pot` prints it) and the template's own `$25` offer; the
  writer is told not to restate the offer.
- `approve_insider` re-lints Kerry's HTML. Brevo's editor rewrites merge
  fields into `rte-personalized-node` spans — pass the lane's HTML with the
  raw `{{ contact.FIRSTNAME }}` tags, not a paste from Brevo's source view.
- The default model is the parser's `claude-sonnet-4-5` route on purpose:
  a weekly job whose failure is silent (fallback) should run on the model
  the account has already proven. Move it with `insider_model` once a
  newer Sonnet is confirmed on this key.

## 5. Open for Kerry

1. The angle ORDER (and any cuts/adds). Reply with the list or set
   `insider_angles`.
2. Which sample he wants first — the three are chosen for contrast (a
   person, a mechanic, a feeling).
3. A member quote for `member-words` when he has one (verbatim, first +
   initial).
4. Whether the history facts (`HISTORY_FACTS`) are right; replace via
   `insider_facts_history`.
