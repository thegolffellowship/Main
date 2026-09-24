# SOP: Routines and working loops

Kerry, 2026-09-23: "When possible and it makes sense I'm wanting to create loops
of operations to keep you guys working even if I'm not."

A **Routine** is a scheduled trigger that fires a prompt into a session. A
**working loop** is a Routine that fires into a lane to take the next item from
its queue, ship it, and digest it.

## 1. Rules for every Routine

1. **The Front Desk owns the list.** Before creating one, run `list_triggers`
   so nothing is duplicated. Record every new Routine in the registry §6 the
   same day.
2. **Bind it to the lane that owns the work** (`persistent_session_id`), so the
   run has the lane's context. Use a fresh session per fire only for a job that
   needs no memory.
3. **A Routine's prompt can only be changed from the session it fires into.**
   The Front Desk can rename, retime, pause and delete from anywhere. To change
   a prompt, it sends the lane a one-shot poke with the exact new text.
4. **The prompt's last step is the digest** `TO: front-desk`
   (reporting-contract.md).
5. **Times are UTC in cron.** Central daylight time is UTC−5 until Nov 1, then
   UTC−6. Each prompt carries a note of its post-DST cron; the Front Desk moves
   them all on Nov 1.
6. **One-shot pokes** (`run_once_at`) are fine for handing a lane a message.
   They disable themselves after firing; the registry keeps their prompts.

## 2. Guardrails every working loop carries

Written into the loop's prompt, word for word:
- Never send anything to members, pay anyone, or delete anything without
  Kerry's explicit OK.
- Rule 3b: money, schema, member-facing behavior and scope decisions wait for
  Kerry. Park them in the digest; do not ship them.
- If the same item fails twice, stop, and report it in the digest. Do not try
  a third time.
- Take one item per run unless the queue says otherwise. Merges to main follow
  CLAUDE.md (merge main first, bump version.js, docs, tests pass).

## 3. How a new loop is approved

The Front Desk proposes it in the 7:15 brief (lane, schedule, what queue it
works from, what it may and may not do). It is created only after Kerry says
yes, then recorded in the registry.

## 4. Loops running today (2026-09-23)

| Routine | Lane | When (Central) |
|---|---|---|
| CTO daily response | CTO / Tracker Health | 5:10 daily |
| Tracker pick-up + fixes | Tracker Build (Improvements 3) | 5:15 daily |
| CFO Daily Financial Review | CFO | 5:20 daily |
| Event-night closeout | Event Closeout | 9 PM Tue + Sat |
| Closeout catch-up | Event Closeout | 5:30 AM Wed + Sun |
| Insider draft check-in | Insider Writer | 8:30 AM Wed |
| Insider scorecard | Insider Writer | 1:30 PM Fri |
| Horizon morning check | fresh session | 7:00 AM weekdays |
| Horizon hourly sweep | fresh session | 9:30 AM to 6:30 PM weekdays |
| Front Desk daily brief (full text to mailbox for CA) | Front Desk | 7:15 daily |
| Front Desk mailbox watch | Front Desk | hourly 7 AM to 9 PM daily |

IDs are in the registry §6.
