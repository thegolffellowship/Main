"""Continuous off-site replication (Litestream -> Cloudflare R2): status for the
health digest, and the restore the drill uses (CA #834, hard gate (a) of #731).

Litestream itself runs beside the app (scripts/start.sh). This module only
READS its state and RESTORES from it; it never writes to the live database,
and never prints or returns a key, secret or endpoint.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

ENV_REQUIRED = ("LITESTREAM_ACCESS_KEY_ID", "LITESTREAM_SECRET_ACCESS_KEY",
                "LITESTREAM_R2_ENDPOINT", "LITESTREAM_R2_BUCKET")
LAG_ALERT_S = 300            # a replica more than 5 minutes behind is a finding
_CACHE: dict = {"at": 0.0, "val": None}


def _live(db_path=None) -> Path:
    from .database import DB_PATH
    return Path(str(db_path or DB_PATH))


def missing_env() -> list:
    """Names (never values) of the required variables that are not set."""
    return [k for k in ENV_REQUIRED if not os.environ.get(k)]


def configured() -> bool:
    return not missing_env()


def config_path() -> Path:
    return Path(__file__).resolve().parent.parent / "litestream.yml"


def binary(db_path=None) -> str | None:
    env = os.environ.get("LITESTREAM_BIN")
    if env and os.access(env, os.X_OK):
        return env
    cand = _live(db_path).parent / "bin" / "litestream"
    if os.access(cand, os.X_OK):
        return str(cand)
    return shutil.which("litestream")


def _cmd_env(db_path=None) -> dict:
    live = _live(db_path)
    env = dict(os.environ)
    env["DATABASE_PATH"] = str(live)
    env["GG_ARCHIVE_PATH"] = str(live.parent / "transactions_gg_archive.db")
    return env


def running() -> bool:
    """Is a `litestream replicate` process alive in this container?"""
    try:
        for p in Path("/proc").iterdir():
            if not p.name.isdigit():
                continue
            try:
                argv = (p / "cmdline").read_bytes().decode("utf-8", "replace").split("\0")
            except OSError:
                continue
            # the process itself must BE `litestream replicate` — a shell whose
            # command text merely mentions it must not count as healthy
            if len(argv) > 1 and os.path.basename(argv[0]) == "litestream" and argv[1] == "replicate":
                return True
    except OSError:
        pass
    return False


def _parse_lag(text: str) -> float | None:
    """'-8ms', '3s', '1m2s', '2h' -> seconds (negative clamped to 0)."""
    t = (text or "").strip()
    if not t or t in ("-", "n/a"):
        return None
    total, found = 0.0, False
    for num, unit in re.findall(r"(-?\d+(?:\.\d+)?)(ms|us|µs|h|m|s)", t):
        found = True
        n = float(num)
        total += n * {"h": 3600, "m": 60, "s": 1, "ms": 0.001, "us": 1e-6, "µs": 1e-6}[unit]
    return max(0.0, total) if found else None


def parse_generations(text: str) -> list:
    """`litestream generations` output -> [{name, generation, lag_s, start, end}]."""
    rows = []
    for line in (text or "").splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 5:
            rows.append({"name": parts[0], "generation": parts[1],
                         "lag_s": _parse_lag(parts[2]), "start": parts[3], "end": parts[4]})
    return rows


def _generations(b: str, path: Path, timeout: float, db_path=None) -> dict:
    """One database's replica state from `litestream generations`."""
    r = subprocess.run([b, "generations", "-config", str(config_path()), str(path)],
                       capture_output=True, text=True, timeout=timeout, env=_cmd_env(db_path))
    if r.returncode != 0:
        return {"generations": 0, "lag_s": None, "latest_end": None,
                "error": (r.stderr or r.stdout or "generations failed").strip().splitlines()[-1][:200]}
    rows = parse_generations(r.stdout)
    if not rows:
        return {"generations": 0, "lag_s": None, "latest_end": None, "error": None}
    last = sorted(rows, key=lambda x: x["end"])[-1]
    return {"generations": len(rows), "lag_s": last["lag_s"], "latest_end": last["end"], "error": None}


def status(db_path=None, cache_s: float = 120.0, timeout: float = 25.0) -> dict:
    """What the digest shows. Cached briefly: the lag read is a call to R2.
    The top-level lag/generations are the MAIN database; ``archive`` is the
    GG archive file (replicated too, but written rarely)."""
    now = time.time()
    if _CACHE["val"] is not None and now - _CACHE["at"] < cache_s:
        return _CACHE["val"]
    out = {"configured": configured(), "missing": missing_env(), "binary": None,
           "running": False, "lag_s": None, "generations": 0, "latest_end": None,
           "error": None, "archive": None,
           "checked_at": datetime.utcnow().isoformat(timespec="seconds")}
    try:
        b = binary(db_path)
        out["binary"] = bool(b)
        out["running"] = running()
        if out["configured"] and b:
            out.update(_generations(b, _live(db_path), timeout, db_path))
            arc = _live(db_path).parent / "transactions_gg_archive.db"
            if arc.is_file():
                out["archive"] = _generations(b, arc, timeout, db_path)
    except subprocess.TimeoutExpired:
        out["error"] = f"generations timed out after {int(timeout)} s"
    except Exception as e:  # noqa: BLE001 — a status read must never raise
        out["error"] = f"{type(e).__name__}: {e}"[:200]
    _CACHE.update(at=now, val=out)
    return out


def restore_to(out_path, db_path=None, timeout: float = 280.0) -> dict:
    """Restore the main database from the replica into ``out_path`` (a path
    that must NOT exist yet). Read-only against the bucket and the live file."""
    b = binary(db_path)
    if not configured():
        return {"ok": False, "error": "replication is not configured: missing " + ", ".join(missing_env())}
    if not b:
        return {"ok": False, "error": "no litestream binary on this server"}
    out_path = Path(str(out_path))
    t0 = time.perf_counter()
    try:
        r = subprocess.run([b, "restore", "-config", str(config_path()), "-o", str(out_path), str(_live(db_path))],
                           capture_output=True, text=True, timeout=timeout, env=_cmd_env(db_path))
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"litestream restore timed out after {int(timeout)} s"}
    ms = int((time.perf_counter() - t0) * 1000)
    if r.returncode != 0 or not out_path.is_file():
        msg = (r.stderr or r.stdout or "restore failed").strip().splitlines()
        return {"ok": False, "error": (msg[-1] if msg else "restore failed")[:300], "ms": ms}
    gen = None
    m = re.search(r"generation=(\w+)", (r.stderr or "") + (r.stdout or ""))
    if m:
        gen = m.group(1)
    return {"ok": True, "ms": ms, "generation": gen, "bytes": out_path.stat().st_size}
