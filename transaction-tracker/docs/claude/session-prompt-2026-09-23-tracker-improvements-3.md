# SESSION PROMPT — TGF Tracker Improvements 3

You are helping Kerry Niester continue improving the TGF Transaction Tracker
(repo `thegolffellowship/Main`, code in `transaction-tracker/`, push to
`main` per convention). This is the successor of "TGF Tracker Improvements 2"
(the Handicap Surfaces lane), which closed 2026-09-23 at v2.487.4.

## READ FIRST, BEFORE ANY REPLY
1. Tracker mailbox — use the **`TGF_Transaction_Tracker` connector**
   (production), NOT the repo-local `tgf-transactions` server (a sandbox
   copy with an empty DB). `read_platform_dialogue since_id=626`; #627–#632
   are this lane's last posts. Re-read before every reply (rule 4).
2. `transaction-tracker/CLAUDE.md` (rules 3b/3c/3d/4/5).
3. `docs/claude/handoff-2026-09-23-handicap-surfaces-2.md` — rulings §1,
   the outage §3, open items §4. Do not re-derive or reopen §1.
4. `docs/claude/handoff-2026-09-22-tracker-health.md` (the CTO lane).

## WHAT THIS SESSION DOES
Step 1 — **Own the morning brief.** The 5:15 AM Central routine must fire
into THIS session. If a Routine named "Daily 5:15 AM Central: Tracker health
pick-up + morning brief for Kerry" is not bound to this session
(`list_triggers`), create it here: cron `15 10 * * *` (UTC; move to
`15 11 * * *` after DST ends Nov 1), prompt = read the last 24 h of mailbox
(topic tracker-health + every lane digest) and `get_agent_action_log`, do
this lane's small clear fixes, route the rest, and leave Kerry a brief —
decisions first, then what was updated (with versions), then what is still
slow/broken and who owns it; one line on a quiet night.
Step 2 — Check the mailbox for the CTO lane's answer on **Spotlight cold
open / scaling** (#630) and the **GG archive move** (#627); bring Kerry the
plain-words answer when it lands.
Step 3 — Take Kerry's next requests.

## CRITICAL NOTES
- Never send, pay or delete without Kerry's explicit OK; merges are his call.
- `customers.chapter` is never overwritten from `items.chapter`.
- Merge `origin/main` before bumping `static/js/version.js`; other lanes push
  all day — renumber above origin's top on conflict. Changelog + docs per
  commit; tests with `|| exit 1`; verify the deploy by polling
  `https://tgf-tracker.up.railway.app/static/js/version.js`.
- The volume is 250 GB now; `/api/health` shows `volume.pct_used`.
- Kerry's style: plain words, short, one question at a time, no emojis.

## START THIS SESSION BY SAYING:
"Tracker Improvements 3 is open — I've read the mailbox through #<latest>
and the handoff, and the 5:15 AM brief now fires into this session. What's
next?"
