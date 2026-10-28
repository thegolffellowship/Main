"""WHO DID IT: every change made in the Tracker by a signed-in person is
logged (Kerry 2026-10-28: "Sounds like we need a log of clicks and who did
it so you can easily see that I was the one that removed myself").

Kerry took himself off the Fall Championship (3305) by deleting his comp
row, and nothing recorded it: agent writes were logged (`mcp-claude`), page
writes were not. Now every successful POST / PUT / PATCH / DELETE under
/api/ from a PIN session lands in ``agent_action_log``:

- agent_name   ``ui:<role>`` or ``ui:<role>:<chapter>`` (the PIN that was
  used: admin is Kerry, each chapter manager has his own PIN);
- action_type  ``<METHOD> <route>``;
- description  the path, the row it touched (customer, event, status as
  it stood BEFORE the change, so a delete still names who was removed),
  the safe body fields, IP and browser;
- related_item_id  the items row, when the path names one.

Read it with ``get_agent_action_log`` (agent_name ``ui:admin`` etc.).
Player phones (score entry), the public member beacon, sign-in and chat are
not logged here; they have their own trails.
"""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

MUTATING = ("POST", "PUT", "PATCH", "DELETE")
LOGGED_ROLES = ("admin", "manager", "view-only")
SKIP_PREFIXES = (
    "/api/score-entry/", "/api/member-metric", "/api/login", "/api/logout",
    "/api/auth", "/api/coo/chat", "/api/chat", "/api/support",
)
ITEM_PATH = re.compile(r"^/api/(?:items|events/delete-manual-player)/(\d+)(?:/|$)")
EVENT_PATH = re.compile(r"^/api/events/(\d+)(?:/|$)")
SAFE_KEYS = ("note", "action", "method", "reason", "status", "credit_amount",
             "target_event_name", "target_event", "amount", "holes", "side_games",
             "user_status", "tee_choice", "mode", "field", "value_kind")


def should_log(method: str, path: str, status: int, role: str | None) -> bool:
    return (method in MUTATING and path.startswith("/api/") and status < 400
            and (role or "") in LOGGED_ROLES
            and not any(path.startswith(p) for p in SKIP_PREFIXES))


def item_id_of(path: str) -> int | None:
    m = ITEM_PATH.match(path)
    return int(m.group(1)) if m else None


def item_snapshot(conn, item_id: int) -> str:
    r = conn.execute("SELECT customer, customer_id, item_name, item_price, "
                     "COALESCE(transaction_status, 'active') FROM items WHERE id = ?",
                     (item_id,)).fetchone()
    if not r:
        return f"item {item_id} (not found)"
    return f"item {item_id}: {r[0]} (cid {r[1]}), {r[2]}, {r[3]}, was {r[4]}"


def safe_body(raw: bytes | None) -> str:
    if not raw:
        return ""
    try:
        data = json.loads(raw)
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    kept = {k: data[k] for k in SAFE_KEYS if k in data and data[k] not in (None, "")}
    other = sorted(k for k in data if k not in kept)
    out = json.dumps(kept, default=str)[:300] if kept else ""
    if other:
        out += (" " if out else "") + "fields: " + ",".join(other)[:200]
    return out


def describe(method: str, path: str, before: str, body: str, ip: str, ua: str) -> str:
    parts = [f"{method} {path}"]
    if before:
        parts.append(before)
    if body:
        parts.append(body)
    parts.append(f"ip={ip} ua={(ua or '')[:80]}")
    return " | ".join(parts)
