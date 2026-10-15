"""The GG Retirement lane's read-only views (CTO > GG Retirement & History
Integration, Kerry 2026-10-15, CoS #1906).

Proves: the archive manifest counts rows, distinct addresses and bytes per fetch
kind and per portal, and writes nothing; the checksum list is paged by row id,
stable, and equals sha256 of the stored bytes; the pending-names queue pages with
limit and offset without skipping or repeating a name and reports its offset; and
the registry follows Kerry's rename of the 2021-2023 Lone Star Cup sites.
"""
import hashlib
import logging
import os
import sys
import tempfile
import zlib

root = tempfile.mkdtemp(prefix="tgf-ggretire-")
tmp = os.path.join(root, "t.db")
os.environ["DATABASE_PATH"] = tmp
os.environ["PERF_SAMPLES"] = "0"
os.environ.setdefault("SECRET_KEY", "test-secret")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logging.disable(logging.CRITICAL)

from email_parser import database as db
from email_parser import gg_archive as ga
from email_parser import gg_history as gh

fails = []


def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label + ("" if cond else f"  {detail}"))
    if not cond:
        fails.append(label)


print("== url_pattern ==")
check("digits in path and query values blank, the portal name is a wildcard",
      ga.url_pattern("https://tgf-sa2024.golfgenius.com/leagues/395571/widgets/"
                     "season_points_v2?page_id=4582854&shared=false")
      == "*.golfgenius.com/leagues/#/widgets/season_points_v#?page_id=#&shared=false")
check("two portals and two league ids give the same pattern",
      ga.url_pattern("https://a.golfgenius.com/leagues/1/widgets/x?page_id=2")
      == ga.url_pattern("https://b.golfgenius.com/leagues/99/widgets/x?page_id=77"))
check("a different widget is a different pattern",
      ga.url_pattern("https://a.golfgenius.com/leagues/1/widgets/x")
      != ga.url_pattern("https://a.golfgenius.com/leagues/1/widgets/y"))
check("an empty or odd address does not raise", ga.url_pattern("") == "" and
      ga.url_pattern("not a url") == "not a url")

print("\n== manifest and checksums over a small archive ==")
db.init_db(tmp)
bodies = {}
with db._connect(tmp) as conn:
    for url, body in [
        ("https://tgf-sa2024.golfgenius.com/leagues/395571/widgets/season_points_v2?page_id=1&shared=false", "<a/>"),
        ("https://tgf-sa2024.golfgenius.com/leagues/395571/widgets/season_points_v2?page_id=2&shared=false", "<b/>"),
        ("https://tgf-sa2024.golfgenius.com/leagues/395571/widgets/season_points_v2?page_id=2&shared=false", "<b/>"),
        ("https://tgf-dfw2024.golfgenius.com/leagues/395610/widgets/tournament_results?shared=false", "<c/>"),
        ("https://cloudfront.example/x.png", "<d/>"),
    ]:
        rid = gh._archive_raw(conn, url, body)
        bodies[rid] = ga.zlib.compress(body.encode()) if hasattr(ga, "zlib") else None
    conn.commit()
with db._connect(tmp) as conn:
    t = ga.archive_table(conn)
    before = conn.execute(f"SELECT COUNT(*), SUM(LENGTH(body_gz)) FROM {t}").fetchone()
    stored = {r[0]: r[1] for r in conn.execute(f"SELECT id, body_gz FROM {t}")}

m = ga.manifest(tmp)
check("manifest counts every row", m["rows"] == 5, m["rows"])
check("manifest counts distinct addresses (one address was fetched twice)",
      m["distinct_urls"] == 4, m["distinct_urls"])
check("manifest bytes equal the stored bytes", m["bytes"] == before[1], (m["bytes"], before[1]))
kinds = {k["pattern"]: k for k in m["by_kind"]}
pts = "*.golfgenius.com/leagues/#/widgets/season_points_v#?page_id=#&shared=false"
check("the two points-page fetches of one portal group as one kind with 3 rows",
      kinds.get(pts, {}).get("rows") == 3 and kinds[pts]["distinct_urls"] == 2, kinds.get(pts))
check("kinds are listed largest first", m["by_kind"][0]["rows"] >= m["by_kind"][-1]["rows"])
ports = {p["portal"]: p for p in m["by_portal"]}
check("rows per portal, and a non-Golf-Genius host keeps its own name",
      ports["tgf-sa2024"]["rows"] == 3 and ports["tgf-dfw2024"]["rows"] == 1
      and ports["cloudfront.example"]["rows"] == 1, ports)
check("first and last row ids reported", m["min_id"] == min(stored) and m["max_id"] == max(stored))

c1 = ga.checksums(from_id=0, limit=2, db_path=tmp)
c2 = ga.checksums(from_id=c1["next_from"], limit=2, db_path=tmp)
c3 = ga.checksums(from_id=c2["next_from"], limit=2, db_path=tmp)
ids = [r[0] for r in c1["rows"] + c2["rows"] + c3["rows"]]
check("paging by next_from visits every row once, oldest first",
      ids == sorted(stored) and c1["count"] == 2 and c2["count"] == 2 and c3["count"] == 1, ids)
check("each checksum is the sha256 of the stored bytes",
      all(h == hashlib.sha256(stored[i]).hexdigest() for i, h in c1["rows"] + c2["rows"] + c3["rows"]))
check("the page digest is stable between calls",
      ga.checksums(from_id=0, limit=2, db_path=tmp)["digest"] == c1["digest"])
check("to_id caps the range", ga.checksums(from_id=0, to_id=ids[1], db_path=tmp)["count"] == 2)
check("past the end returns an empty page and keeps the cursor",
      ga.checksums(from_id=ids[-1], db_path=tmp)["count"] == 0
      and ga.checksums(from_id=ids[-1], db_path=tmp)["next_from"] == ids[-1])
with db._connect(tmp) as conn:
    after = conn.execute(f"SELECT COUNT(*), SUM(LENGTH(body_gz)) FROM {ga.archive_table(conn)}").fetchone()
check("neither call wrote anything", tuple(after) == tuple(before), (after, before))

print("\n== the pending-names queue pages without skipping or repeating ==")
with db._connect(tmp) as conn:
    gh.ensure_gg_history_tables(conn)
    conn.execute("INSERT INTO gg_history_portals (subdomain, chapter, season, kind, brand, source, status) "
                 "VALUES ('tgf-sa2021', 'San Antonio', '2021', 'season', 'TGF', 'recon', 'alive')")
    pid = conn.execute("SELECT id FROM gg_history_portals WHERE subdomain='tgf-sa2021'").fetchone()[0]
    for i in range(7):
        conn.execute("INSERT INTO gg_history_name_links (raw_name, portal_id, matched_by, reviewed) "
                     "VALUES (?, ?, 'pending', 0)", (f"NOBODY{i}, Pat", pid))
    conn.commit()
q_all = gh.review_queue(tmp, limit=100)
p1 = gh.review_queue(tmp, limit=3, offset=0)
p2 = gh.review_queue(tmp, limit=3, offset=3)
p3 = gh.review_queue(tmp, limit=3, offset=6)
names = [n["raw_name"] for p in (p1, p2, p3) for n in p["names"]]
check("seven pending names in total", q_all["pending_total"] == 7, q_all["pending_total"])
check("three pages of 3, 3, 1 cover all names once, in the same order as one big page",
      names == [n["raw_name"] for n in q_all["names"]] and len(set(names)) == 7, names)
check("the page reports its offset", (p1["offset"], p2["offset"], p3["offset"]) == (0, 3, 6))
check("each name carries its portal, season and chapter",
      all(n["subdomain"] == "tgf-sa2021" and n["season"] == "2021" and n["chapter"] == "San Antonio"
          for n in q_all["names"]))
check("an offset past the end is an empty page, not an error",
      gh.review_queue(tmp, limit=3, offset=50)["names"] == [])

print("\n== the registry follows the renamed Lone Star Cup sites ==")
subs = [row[0] for row in gh.SEED_PORTALS]
check("lonestarcup21, lonestarcup22 and lonestarcup23 are registered",
      all(s in subs for s in ("lonestarcup21", "lonestarcup22", "lonestarcup23")))
check("the old subdomains that now redirect are not",
      all(s not in subs for s in ("tgf-lonestarcup21", "tgf-lonestarcup22", "lonestarcup")))
check("every subdomain is registered once", len(subs) == len(set(subs)))

print()
if fails:
    print(f"{len(fails)} FAILED: {fails}")
    sys.exit(1)
print("all passed")
