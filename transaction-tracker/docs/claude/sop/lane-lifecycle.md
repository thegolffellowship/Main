# SOP: lane lifecycle

A **lane** is one Claude Code session with one job. There are two kinds:
**standing lanes**, which never close (Tracker Build, CTO, CFO, Events &
Closeout, Marketing, Horizon, Personal & Church), and **project lanes**, which
open for one piece of work and close when it ships.

## 1. When to open a lane

Open one when any of these is true:
- Kerry says "spin this off" or "give this its own session".
- A thread in a lane has become its own piece of work, with its own rulings,
  branch and follow-ups, and would crowd the lane it started in.
- The work needs a schedule of its own (a loop), and no standing lane owns it.

Do NOT open one for a task a standing lane already owns. Route it on the
mailbox instead. Before opening, check the registry §1 for a lane that already
covers it. Two lanes on the same job is how the 9/23 sprawl started.

Who opens it: the Front Desk, or a lane using the `spin-off` skill
(`.claude/skills/spin-off/SKILL.md`, CLAUDE.md rule 5). Either way the Front Desk
records it in the registry the same day.

## 2. The opening prompt

The new session has none of the parent's memory, so the prompt is the whole
contract. It holds:
1. **Goal**, in one paragraph, with Kerry's words verbatim.
2. **READ FIRST**: the mailbox since a named id, CLAUDE.md rules 3b/3c/3d/4/5,
   the named docs and any `docs/claude/handoff-*.md` that touches the work.
3. **Rulings** already made, verbatim, with mailbox ids.
4. **Files** by repo path and the branch to work on.
5. **Reporting**: its digests go to the mailbox `TO: front-desk`
   (see reporting-contract.md).
6. **First act**: read, confirm tools, post an ack on the mailbox, before any
   reply or build.

Long prompts live in the repo as `docs/claude/session-prompt-<date>-<lane>.md`.

## 3. Hand-off

When a lane passes work to another, or to a successor session, it writes
`docs/claude/handoff-<date>-<lane>.md`: what shipped (versions), Kerry's rulings
verbatim, what is open and who owns it, any Routine that fires into the lane.
It posts a digest naming the successor. A Routine bound to the old session is
moved to the successor (deleted and recreated from inside the successor,
since a Routine's prompt can only be changed from the session it fires into).

## 4. Closing a lane

A project lane closes when its work is on main and nothing it owns is open. It:
1. writes its handoff doc and final digest (`LANE CLOSED`, `TO: front-desk`);
2. says which Routines fire into it, so the Front Desk can delete or move them;
3. stops.

The Front Desk then marks it closed in the registry and asks Kerry, in the
brief, whether to archive it. **Archiving needs Kerry's go-ahead each time.**
Archiving keeps the transcript and `unarchive_session` restores it. Branches
are never deleted by archiving.

## 5. Registry updates (Front Desk, same day)

| Event | Registry change |
|---|---|
| Lane opened | Add to §1 with ID, role, parent, date |
| Routine created, moved, or retimed | Update §5 Routines |
| Lane closed | Mark closed in §1 and list it for archive |
| Kerry approves archive | Move the row to §2 |
| Routine deleted | Record its prompt verbatim in §3 so it can be recreated |
