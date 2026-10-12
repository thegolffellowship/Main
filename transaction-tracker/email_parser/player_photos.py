"""PLAYER PHOTOS (Kerry 2026-10-10: "I'd like to start capturing player
photos ... could we somehow start associating headshots with LSC results?
Teams could be these duo shots." Mockups approved the same night: "I love
all of those applications. Let's do them.")

A photo is a finished JPEG file beside the database (`player_photos/`),
named by customer_id, so there is no table and no migration:

    h-<customer_id>.jpg        a square headshot
    t-<low id>-<high id>.jpg   a two-person team shot (ids sorted)

Cropping and touch-up happen before upload (the server has no image
library); this module only checks the bytes are a JPEG of sane size and
that every customer_id is a real customer. The index (`photo_index`) is
ids and a version stamp only, no names, so the public read is PII-free.
The proper photos table and upload page come after the Cup (#1577).

SEED: the first set (the Lone Star Cup 2026 players, Kerry 10/10) ships in
the repo at data/player_photos/, same names, already cropped and graded,
so it is on the site from the deploy without 42 uploads. A photo written
to the volume replaces the seed one for that person or pair.
"""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

MAX_BYTES = 600 * 1024
KINDS = ("headshot", "team")
_NAME = re.compile(r"^(h-(\d+)|t-(\d+)-(\d+))\.jpg$")


SEED_DIR = Path(__file__).resolve().parent.parent / "data" / "player_photos"

# CHAMPION PHOTOS (Kerry 2026-10-12: "something definitely on the leaderboard
# results" for Gus Vasquez with the Bruce Friesenhahn Fellowship Cup). A
# finished JPEG that ships in the repo (data/champion_photos/), keyed
# "<race>-<season>", so it is read-only at runtime: no upload path, no table,
# and git is its backup. `customer_ids` is who is in it: the board shows it
# only while the champion(s) on the plaque are exactly those people.
CHAMPION_DIR = Path(__file__).resolve().parent.parent / "data" / "champion_photos"
CHAMPION_PHOTOS = {
    "fellowship_cup-2026": {
        "file": "fellowship-cup-2026.jpg",
        "customer_ids": [42],
        "cup": "The Bruce Friesenhahn Fellowship Cup",
        "caption": "Gus Vasquez with The Bruce Friesenhahn Fellowship Cup, 2026",
    },
    "players_cup-2026": {
        "file": "players-cup-2026.jpg",
        "customer_ids": [31],
        "cup": "The Players Cup",
        "caption": "Robert Straiton with The Players Cup, 2026",
    },
    # PAST CHAMPIONS (Kerry 2026-10-12, captioning each photo): same rule, an older
    # year. Shown on the Past Champions strip of the cup boards and under the
    # champion titles on that player's Spotlight.
    "fellowship_cup-2023": {
        "file": "fellowship-cup-2023.jpg",
        "customer_ids": [497],
        "cup": "The Fellowship Cup",
        "caption": "Paul Day with The Fellowship Cup, 2023",
    },
    "fellowship_cup-2024": {
        "file": "fellowship-cup-2024.jpg",
        "customer_ids": [299],
        "cup": "The Fellowship Cup",
        "caption": "Mark Freund with The Fellowship Cup, 2024",
    },
    "fellowship_cup-2025": {
        "file": "fellowship-cup-2025.jpg",
        "customer_ids": [289],
        "cup": "The Fellowship Cup",
        "caption": "Jay Horton with The Fellowship Cup, 2025",
    },
    "players_cup-2023": {
        "file": "players-cup-2023.jpg",
        "customer_ids": [289],
        "cup": "The Players Cup",
        "caption": "Jay Horton with The Players Cup, 2023, the first year it was awarded",
    },
    "players_cup-2024": {
        "file": "players-cup-2024.jpg",
        "customer_ids": [31],
        "cup": "The Players Cup",
        "caption": "Robert Straiton with The Players Cup, 2024 TGF Championship at The Bandit",
    },
}


def photo_dir(db_path=None) -> Path:
    from email_parser.database import DB_PATH
    return Path(str(db_path or DB_PATH)).parent / "player_photos"


def team_key(cids) -> str:
    ids = sorted(int(c) for c in cids)
    return "-".join(str(c) for c in ids)


def _file_name(kind: str, cids) -> str:
    if kind == "headshot":
        return f"h-{int(cids[0])}.jpg"
    return f"t-{team_key(cids)}.jpg"


def _check(kind: str, cids, db_path=None) -> str | None:
    if kind not in KINDS:
        return "kind must be headshot or team"
    try:
        ids = [int(c) for c in cids]
    except (TypeError, ValueError):
        return "customer ids must be numbers"
    if kind == "headshot" and len(ids) != 1:
        return "a headshot names one customer_id"
    if kind == "team" and (len(ids) != 2 or ids[0] == ids[1]):
        return "a team shot names two different customer_ids"
    from email_parser.database import get_connection
    conn = get_connection(db_path)
    try:
        found = {r[0] for r in conn.execute(
            "SELECT customer_id FROM customers WHERE customer_id IN (%s)"
            % ",".join("?" * len(ids)), ids)}
    finally:
        conn.close()
    missing = [c for c in ids if c not in found]
    return f"no customer {missing}" if missing else None


def save_photo(kind: str, cids, data: bytes, db_path=None) -> dict:
    """Write one finished JPEG. Replaces an earlier photo of the same
    person or pair (written to a temp file first, then renamed)."""
    err = _check(kind, cids, db_path)
    if err:
        return {"error": err}
    if not data or data[:3] != b"\xff\xd8\xff":
        return {"error": "not a JPEG"}
    if len(data) > MAX_BYTES:
        return {"error": f"photo is {len(data)} bytes; the limit is {MAX_BYTES}"}
    d = photo_dir(db_path)
    d.mkdir(parents=True, exist_ok=True)
    name = _file_name(kind, cids)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".part")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.replace(tmp, d / name)
    return {"saved": name, "bytes": len(data), "version": int((d / name).stat().st_mtime)}


def remove_photo(kind: str, cids, db_path=None) -> dict:
    if kind not in KINDS:
        return {"error": "kind must be headshot or team"}
    p = photo_dir(db_path) / _file_name(kind, cids)
    if not p.exists():
        return {"removed": False, "why": "no such photo"}
    p.unlink()
    return {"removed": p.name}


def photo_index(db_path=None) -> dict:
    """{"h": {"<cid>": version}, "t": {"<a>-<b>": version}, "c": {"<race>-<season>":
    {v, ids, cup, caption}}}: who has a photo, and a stamp that changes when it
    is replaced (cache busting). "c" is the champion photos: the people are
    ids, and the caption is the public champion's name already on the board."""
    out = {"h": {}, "t": {}, "c": {}}
    # the seed first, then the volume, so an upload replaces a seed photo
    for d in (SEED_DIR, photo_dir(db_path)):
        if not d.is_dir():
            continue
        for p in d.iterdir():
            m = _NAME.match(p.name)
            if not m:
                continue
            v = int(p.stat().st_mtime)
            if m.group(2):
                out["h"][m.group(2)] = v
            else:
                out["t"][f"{m.group(3)}-{m.group(4)}"] = v
    for key, c in CHAMPION_PHOTOS.items():
        f = CHAMPION_DIR / c["file"]
        if f.is_file():
            out["c"][key] = {"v": int(f.stat().st_mtime), "ids": list(c["customer_ids"]),
                             "cup": c["cup"], "caption": c["caption"]}
    return out


def photo_file(kind: str, key: str, db_path=None) -> Path | None:
    """The file for a public read, or None. `key` is a customer_id for a
    headshot or "<a>-<b>" for a team; anything else is refused."""
    if kind == "h" and re.fullmatch(r"\d+", key or ""):
        name = f"h-{int(key)}.jpg"
    elif kind == "t" and re.fullmatch(r"\d+-\d+", key or ""):
        name = f"t-{team_key(key.split('-'))}.jpg"
    elif kind == "c":
        c = CHAMPION_PHOTOS.get(key or "")
        p = CHAMPION_DIR / c["file"] if c else None
        return p if p and p.is_file() else None
    else:
        return None
    for d in (photo_dir(db_path), SEED_DIR):      # an upload wins over the seed
        p = d / name
        if p.is_file():
            return p
    return None
