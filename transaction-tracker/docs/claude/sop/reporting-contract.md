# SOP: reporting contract and escalation

Decided by Kerry 2026-09-23 (mailbox #636). Kerry reads one brief a day. The
Front Desk writes it. Every lane feeds it through the mailbox.

## 1. Every lane digests to the mailbox, TO: front-desk

- Channel: the Tracker mailbox (`post_platform_dialogue` on the
  **TGF_Transaction_Tracker** connector, production; never the repo-local
  `tgf-transactions` server, which is a sandbox with an empty DB).
- First line of every digest: `TO: front-desk` (add other lanes or
  `platform-claude` after it if they must act).
- Author `tracker-claude`, and say which lane in the `FROM:` line.
- Order inside the digest: **decisions needed from Kerry first**, then what
  shipped (version numbers), then what is open and who owns it. One line each.
- A quiet run is one line.
- A lane's scheduled Routine ends with this post as its last step.

Horizon is the one exception: its output lives in the Horizon mailbox
(Horizon_Tracker `read_dialogue`, topic `morning-check`) and the Front Desk
reads it there.

## 1b. Kerry works through the Front Desk

Kerry, 2026-09-23: "Obviously I can go into each one of these individually when
I want to and work directly with that agent, right? But I don't necessarily
want to do that because I'm the CEO and I don't want to micro-manage."

- Kerry's default channel is the Front Desk. Lanes do not ask him to come to
  them; they route questions through their digest.
- He may open any lane directly whenever he chooses. When he does, that lane
  posts a `TO: front-desk` digest afterwards (his rulings verbatim, what it
  did), so the Front Desk stays in sync and does not ask him the same thing twice.

## 2. When a lane may address Kerry directly

Only for something urgent that cannot wait for the 7:15 brief: production
down, money at risk, a member-facing error live now, or an event tonight that
is blocked. Otherwise, route it through the digest.

## 3. The brief (Front Desk, 7:15 AM Central daily)

Routine `trig_01TJWBMxzUSW4JhR6G5MEaGE`, bound to the Front Desk. It reads both
mailboxes for the last 24 h, checks Routine failures and failed sessions, then
writes, in this order:
1. **The one decision** Kerry needs to make, phrased so he can answer in a word.
   More than one only if truly blocking.
2. **What changed overnight** by domain, TGF / Horizon / Personal, with versions.
3. **What is stuck** and who owns it.

Plain words, short, no emojis. On a quiet day, one line.

Morning order it relies on (Central): 5:00 Tracker CTO digest (app job), 5:10
CTO lane, 5:15 Tracker Build pick-up, 5:20 CFO review, 5:30 closeout catch-up
(Wed/Sun), 7:00 Horizon morning check, **7:15 brief**.

## 4. Kerry's replies become directives

When Kerry answers in the Front Desk, the Front Desk turns it into a mailbox
post addressed to the owning lane, with his words verbatim, and wakes that lane
(a one-shot Routine into the lane's session) if it will not wake on its own
schedule soon enough.

## 4b. Chain of command (Kerry, 2026-09-24)

"You are kind of like the construction foreman reporting to the job
superintendent (CA)." Kerry works with CA. CA directs the Front Desk on the
mailbox (topic `front-desk`, `TO: front-desk`). The Front Desk directs the
lanes. The daily brief posts to the mailbox in FULL, addressed `TO:
platform-claude (CA), kerry`, never as a pointer. An hourly Front Desk
mailbox watch (7 AM to 9 PM) picks up CA's directives, routes them, and
acknowledges back to CA. The mailbox cannot wake a session on its own, so the
hourly check is the fastest pickup.

## 5. Escalation path

lane → Front Desk → Kerry. Strategy, scope and Platform architecture go to CA
(`platform-claude`): the Front Desk posts on the mailbox, topic `front-desk`,
`TO: platform-claude`, and tells Kerry in the brief to "open CA and say 'check
the mailbox'". CA only runs when Kerry opens it.

Kerry is the final word on anything crossing money, schema, member-facing
behavior or scope (CLAUDE.md rule 3b). Two Claudes agreeing is not his approval.
