"""EVENT PHOTOS (Kerry 2026-10-29, Event Ops #2460-J: "it would be nice for me
to be able to post photos of champions this Saturday, and possibly photos on
regular event nights too. Need a workflow for that that's super simple").

The workflow: on Live Scoring a manager or admin taps **Add photo**, the
phone camera opens, an optional caption and an optional player tag
(customer_id, the champion) go with it, and it uploads. Nothing else.

Storage is files beside the database, like player_photos/ and se_photos/,
so there is no table and no migration:

    event_photos/<event_id>/<photo_id>.jpg   the picture (JPEG, <= 1600 px)
    event_photos/<event_id>/index.json       [{id, caption, customer_id,
                                               by, at, bytes, promoted_at}]

The server re-encodes with Pillow when it is installed (it arrives with
pdfplumber / weasyprint): EXIF rotation applied, long side <= 1600 px, JPEG
q82, metadata (GPS) dropped. Without Pillow it keeps a JPEG the phone has
already shrunk (the page resizes before upload, as Check the card does).

Readers: `event_photos(event_id)` (the list), `photo_file(...)` (one file for
the public route `/member/event-photo/<event_id>/<photo_id>.jpg`). The results
email and the recap writer read the list ONLY while dial
`event_photos_in_email` is on (default OFF). The Add photo button shows while
dial `event_photos_capture` is not "off" (staff only either way).

A champion-tagged photo becomes that player's Spotlight headshot only on an
explicit manager action (`promote_to_spotlight`, the Spotlight button), never
automatically; the old volume headshot, if any, is kept under
player_photos/replaced/ first, so nothing is lost.
"""
from __future__ import annotations

import io
import json
import logging
import os
import re
import secrets
import tempfile
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

STORE = "event_photos"
CAPTURE_DIAL = "event_photos_capture"      # on unless "off" (staff-only button)
EMAIL_DIAL = "event_photos_in_email"       # off unless "on"
MAX_UPLOAD = 20 * 1024 * 1024              # a raw phone photo
MAX_KEEP_NO_PIL = 4 * 1024 * 1024          # without Pillow: an already-shrunk JPEG
LONG_SIDE = 1600
CAPTION_MAX = 200
_ID = re.compile(r"^p\d{14}-[0-9a-f]{6}$")


def _setting(key, db_path=None) -> str:
    from email_parser import database as db
    try:
        return (db.get_app_setting(key, db_path=db_path) or "").strip().lower()
    except Exception:
        return ""


def capture_on(db_path=None) -> bool:
    return _setting(CAPTURE_DIAL, db_path) not in ("off", "0", "false", "no")


def in_email_on(db_path=None) -> bool:
    return _setting(EMAIL_DIAL, db_path) == "on"


def store_dir(db_path=None) -> Path:
    from email_parser.database import DB_PATH
    return Path(str(db_path or DB_PATH)).parent / STORE


def _event_dir(event_id: int, db_path=None) -> Path:
    return store_dir(db_path) / str(int(event_id))


def _read_index(event_id: int, db_path=None) -> list:
    p = _event_dir(event_id, db_path) / "index.json"
    try:
        rows = json.loads(p.read_text(encoding="utf-8"))
        return rows if isinstance(rows, list) else []
    except (OSError, ValueError):
        return []


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".part")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def _write_index(event_id: int, rows: list, db_path=None) -> None:
    _write_atomic(_event_dir(event_id, db_path) / "index.json",
                  json.dumps(rows, indent=1, sort_keys=True).encode("utf-8"))


def _pil():
    try:
        from PIL import Image, ImageOps
        return Image, ImageOps
    except Exception:
        return None, None


def normalize_jpeg(data: bytes, long_side: int = LONG_SIDE, square: int | None = None,
                   quality: int = 82) -> tuple[bytes | None, str | None]:
    """(jpeg bytes, error). Pillow: rotate by EXIF, shrink, re-encode without
    metadata; `square` centre-crops to a square of that size. No Pillow: a
    JPEG is kept as it came (the page already shrank it); a square is refused."""
    if not data:
        return None, "no photo"
    if len(data) > MAX_UPLOAD:
        return None, f"photo is {len(data)} bytes; the limit is {MAX_UPLOAD}"
    Image, ImageOps = _pil()
    if Image is None:
        if data[:3] != b"\xff\xd8\xff":
            return None, "not a JPEG (and the server cannot convert images)"
        if square:
            return None, "the server cannot crop images (Pillow is not installed)"
        if len(data) > MAX_KEEP_NO_PIL:
            return None, f"photo is {len(data)} bytes; without Pillow the limit is {MAX_KEEP_NO_PIL}"
        return data, None
    try:
        im = Image.open(io.BytesIO(data))
        im = ImageOps.exif_transpose(im)
        im = im.convert("RGB")
        if square:
            w, h = im.size
            s = min(w, h)
            # a portrait keeps the top of the frame (faces), a landscape the middle
            top = 0 if h > w else (h - s) // 2
            left = (w - s) // 2
            im = im.crop((left, top, left + s, top + s)).resize((square, square))
        else:
            im.thumbnail((long_side, long_side))
        out = io.BytesIO()
        im.save(out, "JPEG", quality=quality, optimize=True, progressive=True)
        return out.getvalue(), None
    except Exception as exc:
        return None, f"could not read the image: {type(exc).__name__}"


def _valid_customer(cid, db_path=None) -> bool:
    from email_parser.database import get_connection
    conn = get_connection(db_path)
    try:
        return bool(conn.execute("SELECT 1 FROM customers WHERE customer_id = ?",
                                 (int(cid),)).fetchone())
    finally:
        conn.close()


def _valid_event(event_id, db_path=None) -> bool:
    from email_parser.database import get_connection
    conn = get_connection(db_path)
    try:
        return bool(conn.execute("SELECT 1 FROM events WHERE id = ?", (int(event_id),)).fetchone())
    finally:
        conn.close()


def save_photo(event_id: int, data: bytes, caption: str = "", customer_id=None,
               by: str = "", db_path=None, now: datetime | None = None) -> dict:
    """Store one photo for an event. Returns {ok, photo} or {error}."""
    try:
        event_id = int(event_id)
    except (TypeError, ValueError):
        return {"error": "event_id must be a number"}
    if not _valid_event(event_id, db_path):
        return {"error": f"no event {event_id}"}
    cid = None
    if customer_id not in (None, "", 0, "0"):
        try:
            cid = int(customer_id)
        except (TypeError, ValueError):
            return {"error": "customer_id must be a number"}
        if not _valid_customer(cid, db_path):
            return {"error": f"no customer {cid}"}
    jpg, err = normalize_jpeg(data)
    if err:
        return {"error": err}
    from email_parser.timezone_utils import now_central
    now = now or now_central()
    pid = f"p{now.strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3)}"
    _write_atomic(_event_dir(event_id, db_path) / f"{pid}.jpg", jpg)
    row = {"id": pid, "caption": (caption or "").strip()[:CAPTION_MAX], "customer_id": cid,
           "by": (by or "")[:60], "at": now.strftime("%Y-%m-%d %H:%M"), "bytes": len(jpg),
           "promoted_at": None}
    rows = _read_index(event_id, db_path)
    rows.append(row)
    _write_index(event_id, rows, db_path)
    return {"ok": True, "photo": public_row(event_id, row)}


def public_row(event_id: int, row: dict) -> dict:
    """What a public reader gets: id, caption, the tagged customer_id (an id,
    not a name), and the URL. Who uploaded it stays staff-side."""
    return {"id": row["id"], "caption": row.get("caption") or "",
            "customer_id": row.get("customer_id"), "at": row.get("at"),
            "url": f"/member/event-photo/{int(event_id)}/{row['id']}.jpg",
            "promoted": bool(row.get("promoted_at"))}


def event_photos(event_id: int, db_path=None, staff: bool = False) -> list:
    """THE READER: the event's photos, oldest first, only those whose file is
    there. `staff` adds who uploaded and when it was promoted."""
    try:
        event_id = int(event_id)
    except (TypeError, ValueError):
        return []
    d = _event_dir(event_id, db_path)
    out = []
    for r in _read_index(event_id, db_path):
        if not _ID.match(str(r.get("id") or "")) or not (d / f"{r['id']}.jpg").is_file():
            continue
        row = public_row(event_id, r)
        if staff:
            row.update(by=r.get("by"), promoted_at=r.get("promoted_at"), bytes=r.get("bytes"))
        out.append(row)
    return out


def photo_file(event_id, photo_id: str, db_path=None) -> Path | None:
    if not re.fullmatch(r"\d+", str(event_id or "")) or not _ID.match(photo_id or ""):
        return None
    p = _event_dir(int(event_id), db_path) / f"{photo_id}.jpg"
    return p if p.is_file() else None


def promote_to_spotlight(event_id: int, photo_id: str, by: str = "", db_path=None) -> dict:
    """A manager's explicit action: the champion-tagged photo becomes that
    player's Spotlight headshot through player_photos.save_photo (a 400 px
    square). The volume headshot it replaces is kept first."""
    from email_parser import player_photos as pp
    rows = _read_index(event_id, db_path)
    row = next((r for r in rows if r.get("id") == photo_id), None)
    src = photo_file(event_id, photo_id, db_path)
    if not row or not src:
        return {"error": "no such photo"}
    cid = row.get("customer_id")
    if not cid:
        return {"error": "tag the player first: only a photo tagged with a player can go to the Spotlight"}
    data, err = normalize_jpeg(src.read_bytes(), square=400, quality=85)
    if err:
        return {"error": err}
    old = pp.photo_dir(db_path) / f"h-{int(cid)}.jpg"
    kept = None
    if old.is_file():
        stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        dest = pp.photo_dir(db_path) / "replaced" / f"h-{int(cid)}-{stamp}.jpg"
        _write_atomic(dest, old.read_bytes())
        kept = dest.name
    res = pp.save_photo("headshot", [int(cid)], data, db_path=db_path)
    if res.get("error"):
        return res
    from email_parser.timezone_utils import now_central
    row["promoted_at"] = now_central().strftime("%Y-%m-%d %H:%M")
    row["promoted_by"] = (by or "")[:60]
    _write_index(event_id, rows, db_path)
    return {"ok": True, "customer_id": int(cid), "saved": res.get("saved"), "previous_kept": kept}


def set_tag(event_id: int, photo_id: str, caption=None, customer_id="keep", db_path=None) -> dict:
    """Edit a photo's caption or player tag (manager)."""
    rows = _read_index(event_id, db_path)
    row = next((r for r in rows if r.get("id") == photo_id), None)
    if not row:
        return {"error": "no such photo"}
    if caption is not None:
        row["caption"] = str(caption).strip()[:CAPTION_MAX]
    if customer_id != "keep":
        if customer_id in (None, "", 0, "0"):
            row["customer_id"] = None
        else:
            try:
                cid = int(customer_id)
            except (TypeError, ValueError):
                return {"error": "customer_id must be a number"}
            if not _valid_customer(cid, db_path):
                return {"error": f"no customer {cid}"}
            row["customer_id"] = cid
    _write_index(event_id, rows, db_path)
    return {"ok": True, "photo": public_row(event_id, row)}


# ── the emails (dial event_photos_in_email, default off) ──────────────────
def email_photos(event_id: int, db_path=None, limit: int = 4) -> list:
    """The photos an email may carry: [] unless the dial is on."""
    if not in_email_on(db_path):
        return []
    return event_photos(event_id, db_path=db_path)[-limit:]


def email_card_html(event_id: int, base: str, db_path=None) -> str:
    """The results email's PHOTOS card, or "" (dial off / no photos)."""
    import html as _h
    rows = email_photos(event_id, db_path=db_path)
    if not rows:
        return ""
    cells = []
    for r in rows:
        cap = _h.escape(r["caption"]) if r["caption"] else ""
        cells.append(
            f'<div style="padding:8px 0;border-top:1px solid #E5E7EB;">'
            f'<img src="{_h.escape(base + r["url"])}" alt="{cap or "Event photo"}" width="520" '
            f'style="display:block;width:100%;max-width:520px;height:auto;border-radius:8px;">'
            + (f'<div style="font-size:13px;color:#4B5563;padding-top:6px;">{cap}</div>' if cap else "")
            + "</div>")
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            f'style="margin:0 0 18px;"><tr><td style="border:1px solid #E5E7EB;border-radius:12px;'
            f'padding:14px 16px;"><div style="font:bold 11px Arial,sans-serif;letter-spacing:2px;'
            f'color:#E87C3E;padding-bottom:6px;">PHOTOS</div>{"".join(cells)}</td></tr></table>')


def recap_facts(event_id: int, db_path=None) -> list:
    """For the recap writer: captions and tags only (dial off -> [])."""
    return [{"caption": r["caption"], "customer_id": r["customer_id"]}
            for r in email_photos(event_id, db_path=db_path)]
