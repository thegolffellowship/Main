---
name: spin-off
description: Spin a tangent or a distinct area of work out of the current session into its own dedicated Claude Code session, with a self-contained hand-off that forces the new session to load context from the Tracker mailbox and the relevant docs BEFORE it does anything. Invoke when Kerry says "spin this off", "spin-off", "give this its own session", "this needs a dedicated session", or when a thread has clearly outgrown the lane it started in.
---

# Spin-off directive (Kerry, 2026-09-10)

Kerry: "too often I'm in a continuous stream of thought that goes all
over the place." A spin-off moves one line of work into its own session
so the parent lane stays on its subject and the new lane starts with
the whole picture. A new session has NONE of the parent's memory — the
opening prompt is the entire contract, and the first thing the new
session does is READ, not build.

## What the parent session must do (in this order)

1. **Name it.** Title = the area of work in ≤6 words (matches the
   session list convention: "Lead Edits + Brevo Sync", "Event
   closeout: Silverhorn & ShadowGlen"). Branch = `claude/<slug>-<6
   random chars>` unless the work is docs-only on main.
2. **Write the hand-off block** (template below). Everything the new
   session needs by REPO PATH or MAILBOX ID — never "as discussed".
   Rulings Kerry already made go in verbatim with the date; a spin-off
   must never re-litigate them.
3. **Create the session** with `create_session` (same environment;
   `title`, `prompt` = the hand-off block, `outcome_branch` when there
   is one). If the work should start later or recur, create a Routine
   with `create_new_session_on_fire=true` instead, same prompt.
4. **Post a mailbox note** (`post_platform_dialogue`, author
   tracker-claude, topic `session-digest`): one paragraph — spin-off
   title, branch, scope, what stays with the parent — so lanes don't
   collide and CA knows a new lane exists.
5. **Tell Kerry** the title and what the parent keeps.

## What the spin-off session must do before its first real response

The hand-off block instructs it; the skill exists so the instruction
is never forgotten:

1. `read_platform_dialogue` since the id named in the hand-off (and
   again before EVERY reply — CLAUDE.md rule 4).
2. Read `transaction-tracker/CLAUDE.md` and every doc the hand-off
   names, plus any `docs/claude/handoff-*.md` whose title touches the
   area of work.
3. Confirm the tools it needs are present (Tracker MCP via
   `probe_golf_genius`, Brevo, HubSpot, M365 as relevant). A freshly
   created session can start WITHOUT connectors — say so immediately
   rather than building blind.
4. Post an acknowledgement to the mailbox: "lane open — read #A–#B,
   docs X/Y/Z, starting with step 1". Then work.
5. On close: handoff doc under `docs/claude/handoff-<date>-<slug>.md`,
   session prompt if a successor is expected, CLAUDE.md index line,
   digest to the mailbox — the session-documentation routine.

## Hand-off block template (paste as the new session's prompt)

```
SPIN-OFF from "<parent session title>" — <date>. Kerry directed this
area of work into its own session.

GOAL: <one sentence: what done looks like>

READ FIRST, BEFORE ANY REPLY:
1. Tracker mailbox: read_platform_dialogue since_id=<N>; posts #<a>,
   #<b> are the ones that matter. Re-read before every response.
2. transaction-tracker/CLAUDE.md (rules 3b/3c/3d/4 govern you).
3. <repo paths of the docs/handoffs/templates that carry the context>
4. Confirm your tools: <which connectors/bridges you need>. If any is
   missing, say so first.

RULINGS ALREADY MADE (verbatim, do not reopen):
- <date> Kerry: "<quote>"
- ...

STATE OF THE CODE: <what exists, by path; what is live; what is not
built>

SCOPE: <in> / NOT IN SCOPE: <out — stays with the parent or another
lane>

STEPS: 1) ... 2) ... 3) ...

CONVENTIONS: push to main as standard; bump version.js + changelog +
docs per CLAUDE.md; merge main into your branch BEFORE bumping
version.js; post a mailbox ack when you open and a digest when you
close; never send/pay/delete without Kerry's approval.

START BY SAYING: "<the orienting first line, ending in the first
question for Kerry if there is one>"
```

## Why the read-first step is mandatory

Two lanes in September 2026 built on stale or wrong context because
they trusted their opening prompt over the mailbox (see #452: a
start-here prompt pointed at work that was already finished). The
mailbox and the handoff docs are the shared memory; a spin-off that
skips them inherits nothing and re-derives everything.
