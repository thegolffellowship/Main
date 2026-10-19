"""PACE OF PLAY, MEASURED (Kerry 2026-10-19 #2092; migration 0037).

- The measure (#2084): first save per hole from se_audit (an edit never
  moves it), client_ts when within the clock dial, play order from the start
  hole (shotgun wraps), first hole to second-to-last, catch-ups under 5 min
  spread, hole 1 saved with hole 2 moves the start, second-to-last saved with
  the last moves the end.
- Flags (shown, not counted): few_holes, long_gap, clock, entry_split
  (#2103), manager_entry; per player partial, regrouped. clean + adjusted
  count.
- Tables: rebuild is a dry run by default, idempotent on apply, customer_id
  on every player row; preview rounds are not timed; se_audit is unchanged
  (append-only); customers.pace_rating is never written (#2100).
- The manager report: names not group numbers, fastest first, hole table
  with n and reasons, method line; the send refuses while the dial is off.

Run: python3 test_pace.py
"""
import contextlib
import io
import json
import logging
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
DB = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_PATH"] = DB
for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "EMAIL_ADDRESS"):
    os.environ.pop(k, None)   # no credentials: nothing can be mailed from a test
logging.disable(logging.CRITICAL)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    from email_parser import database as db  # noqa: E402
    db.init_db(DB)
from email_parser import score_entry as se  # noqa: E402
from email_parser import pace_report as pr  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        FAILURES.append(label)


conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
NAMES = {}
for cid in range(101, 131):
    fn, ln = f"First{cid}", f"Last{cid}"
    NAMES[cid] = f"{fn} {ln}"
    conn.execute("INSERT INTO customers (customer_id, first_name, last_name, pace_rating) VALUES (?,?,?,?)",
                 (cid, fn, ln, 2))
conn.execute("INSERT INTO events (id, item_name, event_date, chapter, course) VALUES "
             "(950, 's9.27 Test Course', '2026-10-13', 'San Antonio', 'Test Course')")
conn.commit()

print("migration 0037")
mig = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
check("0037 applied by init_db", "0037_se_pace.sql" in mig, sorted(mig)[-3:])
cols = {r[1] for r in conn.execute("PRAGMA table_info(se_player_pace)")}
check("se_player_pace carries customer_id", "customer_id" in cols, cols)
check("no notice key in the migration (#2096)",
      "pace_10_round_notice_sent_at" not in open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                              "migrations", "0037_se_pace.sql")).read())

NINE = [{"hole": h, "par": 4, "stroke_index": h} for h in range(1, 10)]
rid = se.create_round(950, 9, round_date="2026-10-13", label="s9.27", course_holes=NINE)["round_id"]
T = datetime(2026, 10, 13, 21, 30, tzinfo=timezone.utc)


def iso(sec, ms=False):
    d = T + timedelta(seconds=sec)
    return d.strftime("%Y-%m-%dT%H:%M:%S") + (".123Z" if ms else "Z")


GID = {}
ops = [0]


def group(num, start, cids):
    conn.commit()
    g = se.upsert_group(rid, num, label=f"G-LABEL-{num}", start_hole=start, tee_time=f"4:{20 + num}0 PM",
                        players=[{"customer_id": c, "display_name": NAMES[c], "seat": i + 1}
                                 for i, c in enumerate(cids)])
    GID[num] = g["group_id"]
    return g["group_id"]


def save(gid, hole, cid, sec, client=None, device="phone-1", result="ok", gross=4):
    ops[0] += 1
    conn.execute("INSERT INTO se_audit (round_id, group_id, kind, customer_id, device_id, op_id, result, "
                 "detail, at) VALUES (?,?,?,?,?,?,?,?,?)",
                 (rid, gid, "write", cid, device, f"op{ops[0]}", result,
                  json.dumps({"hole": hole, "gross": gross, "customer_id": cid, "team_id": None,
                              "client_ts": client}), iso(sec)))


def card(gid, cids, times, **kw):
    for h, t in times.items():
        for c in cids:
            save(gid, h, c, t, **kw)


# G1 clean, start 1, 14 min a hole; hole 1's phone clock 60 s early (used);
# hole 3 re-saved an hour later (the first save stands); a 4th player with
# saves on holes 1-3 only (partial).
g1 = group(1, 1, [101, 102, 103, 104])
t1 = {h: (h - 1) * 840 for h in range(1, 10)}
for h, t in t1.items():
    for c in (101, 102, 103):
        save(g1, h, c, t, client=iso(t - 60, ms=True) if h == 1 else None)
for h in (1, 2, 3):
    save(g1, h, 104, t1[h])
save(g1, 3, 101, t1[9] + 3600, gross=5)
# G2: hole 1 saved 5 s before hole 2 (start moves), 12 min a hole after.
g2 = group(2, 1, [105, 106, 107])
t2 = {1: 600, 2: 605}
t2.update({h: 605 + (h - 2) * 720 for h in range(3, 10)})
card(g2, [105, 106, 107], t2)
# G3: shotgun on 5 (5..9, 1..4); holes 7-8 saved 4 s apart after a long gap.
g3 = group(3, 5, [108, 109, 110])
t3 = {5: 0, 6: 900, 7: 2690, 8: 2694, 9: 3594, 1: 4494, 2: 5394, 3: 6294, 4: 7194}
card(g3, [108, 109, 110], t3)
# G4: hole 5 took 40 minutes -> long_gap.
g4 = group(4, 1, [111, 112, 113])
t4 = {h: (h - 1) * 840 + (1560 if h >= 5 else 0) for h in range(1, 10)}
card(g4, [111, 112, 113], t4)
# G5: two players saving their own, 3 min apart on holes 2-4 -> entry_split;
# one take-over on the group.
g5 = group(5, 1, [114, 115])
t5 = {h: (h - 1) * 840 for h in range(1, 10)}
for h, t in t5.items():
    save(g5, h, 114, t, device="phone-a")
    save(g5, h, 115, t + (180 if h in (2, 3, 4) else 0), device="phone-b")
conn.execute("INSERT INTO se_audit (round_id, group_id, kind, customer_id, device_id, prev_device_id, at) "
             "VALUES (?,?,?,?,?,?,?)", (rid, g5, "takeover", 115, "phone-b", "phone-a", iso(100)))
# G6: hole 8 saved with hole 9 (clubhouse) -> the end moves back to hole 7.
# Player 120 also has 3 saves in G2 -> regrouped (kept in G6, most holes).
g6 = group(6, 1, [116, 117, 120])
t6 = {h: (h - 1) * 840 for h in range(1, 9)}
t6[9] = t6[8] + 5
card(g6, [116, 117, 120], t6)
for h in (1, 2, 3):
    save(g2, h, 120, t2[h])
# G7: one hole's phone clock 10 minutes off -> clock.
g7 = group(7, 1, [118])
for h in range(1, 10):
    t = (h - 1) * 840
    save(g7, h, 118, t, client=iso(t - 600) if h == 4 else iso(t))
# G8: a card keyed by a manager afterwards -> manager_entry.
g8 = group(8, 1, [119])
card(g8, [119], {h: 9000 + h * 840 for h in range(1, 10)}, device="manager:San Antonio")
# Noise that must be ignored: a refused write and a cleared hole.
save(g1, 2, 102, -5000, result="refused_lock")
save(g1, 4, 102, -4000, gross=None)
conn.commit()

audit_before = conn.execute("SELECT COUNT(*), MAX(id) FROM se_audit").fetchone()
pace_before = [tuple(r) for r in conn.execute("SELECT customer_id, pace_rating FROM customers ORDER BY 1")]

print("the bridge read: first saves from se_audit")
raw = se.audit_first_saves(rid)
gr = {g["group_id"]: g for g in raw["groups"]}
check("an edit later never moves the first save",
      gr[g1]["subjects"]["c:101"]["holes"]["3"]["at"] == iso(t1[3]), gr[g1]["subjects"]["c:101"]["holes"]["3"])
check("client_ts carried beside the server time",
      gr[g1]["subjects"]["c:101"]["holes"]["1"]["client_ts"] == iso(-60, ms=True))
check("a refused write is not a save", gr[g1]["subjects"]["c:102"]["holes"]["2"]["at"] == iso(t1[2]))
check("take-over count per group (#2103)", gr[g5]["takeovers"] == 1 and gr[g1]["takeovers"] == 0)

print("the measure")
rp = se.compute_round_pace(rid)
G = {g["group_id"]: g for g in rp["groups"]}
check("G1 clean, 7 holes, client_ts used (849 s/hole)",
      (G[g1]["status"], G[g1]["holes_timed"], G[g1]["seconds_per_hole"]) == ("clean", 7, 849), G[g1])
check("G2 hole 1 with hole 2: start moves, 6 holes at 12:00",
      (G[g2]["status"], G[g2]["start_moved"], G[g2]["holes_timed"], G[g2]["seconds_per_hole"])
      == ("adjusted", 1, 6, 720), G[g2])
check("G3 shotgun wraps; the mid catch-up spread (897 each); avg over 7 holes",
      G[g3]["status"] == "adjusted" and G[g3]["hole_seconds"][7] == 897 and G[g3]["hole_seconds"][8] == 897
      and G[g3]["holes_timed"] == 7 and G[g3]["seconds_per_hole"] == 899
      and G[g3]["span_holes"][0] == 5 and G[g3]["last_hole"] == 4, G[g3])
check("G4 a 40-minute hole flags long_gap", G[g4]["status"] == "flagged" and "long_gap" in G[g4]["flags"], G[g4])
check("G5 saves 3 min apart on 3 holes flags entry_split",
      G[g5]["status"] == "flagged" and "entry_split" in G[g5]["flags"] and G[g5]["takeovers"] == 1, G[g5])
check("G6 second-to-last with the last: end moves to hole 7",
      (G[g6]["status"], G[g6]["end_moved"], G[g6]["holes_timed"], G[g6]["span_holes"][-1])
      == ("adjusted", 1, 6, 7), G[g6])
check("G7 a phone clock far off flags clock", "clock" in G[g7]["flags"], G[g7])
check("G8 manager-keyed card flags manager_entry", "manager_entry" in G[g8]["flags"], G[g8])
med = int(round((840 + 849) / 2))
check("field median over counting groups only", rp["field_median_seconds"] == med, rp["field_median_seconds"])
P = {p["customer_id"]: p for p in rp["players"]}
check("every player carries the group's pace and customer_id",
      P[101]["group_seconds_per_hole"] == 849 and P[101]["rel_seconds_per_hole"] == 849 - med
      and P[101]["counts"] == 1 and P[101]["group_size"] == 4, P[101])
check("adjusted counts (#2093)", P[105]["status"] == "adjusted" and P[105]["counts"] == 1, P[105])
check("flagged is shown, not counted", P[111]["status"] == "flagged" and P[111]["counts"] == 0, P[111])
check("a player with too few span saves is partial", P[104]["flag_partial"] == 1 and P[104]["counts"] == 0, P[104])
check("a player saved in two groups is regrouped, kept in the larger",
      P[120]["flag_regrouped"] == 1 and P[120]["group_id"] == g6 and P[120]["counts"] == 0, P[120])

print("rebuild")
dry = se.rebuild_pace(rid)
n_rows = conn.execute("SELECT COUNT(*) FROM se_player_pace").fetchone()[0]
check("dry run by default writes nothing", dry["applied"] is False and n_rows == 0, dry)
a1 = se.rebuild_pace(apply=True)
a2 = se.rebuild_pace(apply=True)
rows = conn.execute("SELECT * FROM se_player_pace").fetchall()
check("apply stores one row per group and per player; re-run is idempotent",
      a1["stored"] == a2["stored"] == {"groups": 8, "players": 20}
      and len(rows) == 20, (a1, a2, len(rows)))
check("customer_id on every player row", all(r["customer_id"] for r in rows))
gp = {r["group_id"]: dict(r) for r in conn.execute("SELECT * FROM se_group_pace")}
check("group flags stored as columns", gp[g5]["flag_entry_split"] == 1 and gp[g5]["takeovers"] == 1
      and gp[g4]["flag_long_gap"] == 1 and gp[g1]["status"] == "clean")
prev = se.create_preview_round(950, [101])
if prev.get("round_id"):
    se.write_scores(prev["group_id"], "dev-x", 101, [])
    rp2 = se.compute_round_pace(prev["round_id"])
    check("a preview round is not timed", bool(rp2["excluded"]), rp2.get("excluded"))
check("se_audit untouched by the measure (append-only)",
      tuple(conn.execute("SELECT COUNT(*), MAX(id) FROM se_audit").fetchone()) == tuple(audit_before))
check("customers.pace_rating never written (#2100)",
      [tuple(r) for r in conn.execute("SELECT customer_id, pace_rating FROM customers ORDER BY 1")] == pace_before)

print("staff read + digest line")
pp = se.pace_players()
check("digest line (#2096)", pp["digest_line"] == "Pace: top player 1/10 timed rounds", pp["digest_line"])
one = se.pace_players(101)
check("one player's history, below 10 not in use",
      one["timed_rounds"] == 1 and one["counting_rounds"] == 1 and one["in_use"] is False, one)
check("no suggested 1/2/3 anywhere (#2100)", "suggested" not in json.dumps(pp) + json.dumps(one))

print("the manager report")
rep = pr.event_report(950)
rr = rep["rounds"][0]
spms = [g["seconds_per_hole"] for g in rr["groups"] if g["status"] != "flagged"]
check("groups fastest to slowest (counting first)", spms == sorted(spms) and rr["groups"][0]["seconds_per_hole"] == 720,
      [(g["seconds_per_hole"], g["status"]) for g in rr["groups"]])
check("rows lead with names", rr["groups"][0]["players"][0] == NAMES[105], rr["groups"][0]["players"])
check("total minutes with the hole count and an estimated round",
      rr["groups"][0]["total_minutes"] == 72 and rr["groups"][0]["holes_timed"] == 6
      and rr["groups"][0]["est_round"] == "1:48", rr["groups"][0])
check("flag reasons spelled out", any("players' saves far apart" in g["status_text"] for g in rr["groups"]))
ht = {h["hole"]: h for h in rr["hole_table"]}
check("every hole has an average or a reason, with n",
      all((h["avg_minutes"] is not None) != (h["why_none"] is not None) for h in rr["hole_table"]), rr["hole_table"])
check("n per hole: hole 1 only from the shotgun group; hole 2 not from G2 (its start moved)",
      ht[1]["n"] == 1 and ht[2]["n"] == 3, (ht[1], ht[2]))
# A tee-time round where every group starts on 1: holes 1 and 9 have no data,
# and the report says why instead of leaving a blank (#2092 §2b).
conn.execute("INSERT INTO events (id, item_name, event_date, chapter) VALUES "
             "(951, 'a9.27 Tee Times', '2026-10-13', 'Austin')")
conn.commit()
rid_b = se.create_round(951, 9, round_date="2026-10-13", course_holes=NINE)["round_id"]
rid_main, rid = rid, rid_b
for n, cids in ((1, [121, 122]), (2, [123, 124])):
    gb = group(n, 1, cids)
    card(gb, cids, {h: n * 600 + (h - 1) * 780 for h in range(1, 10)})
conn.commit()
rid = rid_main
hb = {h["hole"]: h for h in pr.round_report(rid_b)["hole_table"]}
check("holes with no data are explained, not blank",
      hb[1]["avg_minutes"] is None and "every group started or finished" in (hb[1]["why_none"] or "")
      and hb[9]["avg_minutes"] is None and hb[5]["n"] == 2, (hb[1], hb[9], hb[5]))
check("slowest holes marked (at most 3)", 0 < sum(h["slowest"] for h in rr["hole_table"]) <= 3)
em = pr.build_email(950)
check("HTML: names in, group labels/ids out, method line",
      NAMES[101] in em["html"] and "G-LABEL" not in em["html"] and "second-to-last" in em["html"]
      and "Group " not in em["html"], em["html"][:300])
check("send refused while dial pace_report_send is off",
      pr.send_round(950, rid)["status"] == "off")
db.set_app_setting(pr.DIAL, "on")
res = pr.send_round(950, rid)
check("dial on, no credentials: an error, nothing sent", "error" in res and not pr.already_sent(rid), res)
to, cc = pr.recipients("San Antonio")
check("recipients: the chapter manager, Kerry copied once", to and pr.KERRY in [a.lower() for a in to + cc]
      and len(to + cc) == len({a.lower() for a in to + cc}), (to, cc))
db.set_app_setting(pr.DIAL, "off")
mj = pr.morning_job(now=datetime(2026, 10, 14, 6, 41))
check("morning job rebuilds, sends nothing while off", mj["send"] == "off" and mj["rebuild"]["stored"]["players"] == 24, mj)

conn.close()
print()
print("ALL PASS" if not FAILURES else f"{len(FAILURES)} FAILURE(S): {FAILURES}")
sys.exit(1 if FAILURES else 0)
