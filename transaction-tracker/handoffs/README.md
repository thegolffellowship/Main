# handoffs/ — design-claude review bundles (MCP-readable)

This directory holds **flattened review bundles** from design-claude (CD) —
self-contained HTML canvases that platform-claude pulls via
`get_tracker_source` for the visual pass, and that tracker-claude implements
from.

**MCP read access (#212):** `handoffs/` is on the `get_tracker_source`
read-only whitelist. Pass `path='handoffs/'` for a directory listing (list
mode, #220) or a byte-exact filename to read a bundle.

**Deploy-included content (#222):** `get_tracker_source` serves the **deployed**
repo, not anyone's local working tree. A CD canvas is only MCP-readable after
a deploy carries the file into this directory. A CD save in the Claude Design
project does **not** reach this repo on its own.

**Delivery protocol.** CD authors canvases in the Claude Design project
(project root, e.g. `TGF Match Play.dc.html` + shared child
`MatchScorecard.dc.html`). To land a bundle here it must be delivered to
tracker-claude by one of:
- the mailbox **design-handoff** protocol (topic `design-handoff`, file content
  in the post body, split into parts for large files — see CLAUDE.md §Workflow
  rule 4), or
- Kerry placing the file directly into this directory,

then tracker-claude commits + deploys it.

**Naming convention (#220):** lowercase-hyphen slug, no spaces, no em-dashes
(e.g. `match-play-ca-review-v2.html`), and post the byte-exact filename to the
mailbox so retrieval never has to guess.
