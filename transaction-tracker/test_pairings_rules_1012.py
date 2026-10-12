"""Kerry's three pairing rules of 2026-10-12, on s9.27 The Quarry (event 3307).

Kerry, verbatim: "New rule for pairings. I don't want any first year players
riding on their own in initial pairings unless it can't be avoided. For
instance. Michele McCormick is shown on her own. I don't want that. Also, I
just removed and re-seated after removing Chris Espinosa triggered that.
However, that reduced us to 20 players. So the reseat should trigger a
reduction in groups from 6 to 5 groups, reseating according to pairings
rules/standards. Another thing I observe is that 2nd time guest, Hector
Hinojosa is being placed with Michelle DelCarmen who is not an ambassador. I
would like all guests to always be placed with an ambassador, unless they are
the guest of one of our members, or requests someone specificially."

The fixture is the 10/13 field as production had it on 10/12: 20 players,
tees, captain / Ambassador / solo_back_ok chips, 1Y (new member this year, no
earlier handicap round), Hector Hinojosa a guest whose request (Dan South) is
not on the roster, the Anthis / Palacios request, and the sheet Kerry saw
(six groups after Chris Espinosa came off).

Run: python3 test_pairings_rules_1012.py
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = tempfile.mktemp(suffix=".db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.ERROR)
from email_parser import database as db                          # noqa: E402
from email_parser.pairings_audit import event_pairing_audit       # noqa: E402
DB = os.environ["DATABASE_PATH"]
db.init_db(DB)
F = []
K = db._pair_key_name


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)


# ── units ─────────────────────────────────────────────────────────────
print("units: _group_seat_misses")
req = {frozenset((K("Ann A"), K("Bob B")))}
check("request pair + a 1Y in a threesome: the 1Y must ride alone",
      db._group_seat_misses(["Ann A", "Bob B", "New N"], req, set(), set(), {K("New N")}) == (1, 0))
check("no request: someone else can take the solo seat",
      db._group_seat_misses(["Ann A", "Bob B", "New N"], set(), set(), set(), {K("New N")}) == (0, 0))
check("a foursome has no solo seat",
      db._group_seat_misses(["Ann A", "Bob B", "New N", "Cy C"], req, set(), set(), {K("New N")}) == (0, 0))
amb = {K("Amb X")}
req2 = {frozenset((K("Amb X"), K("Pal P")))}
check("guest whose only Ambassador rides with a requested partner: miss",
      db._group_seat_misses(["Pal P", "Amb X", "Del D", "Gue G"], req2, amb, {K("Gue G")}, set()) == (0, 1))
check("guest with a free Ambassador: no miss",
      db._group_seat_misses(["Pal P", "Amb X", "Del D", "Gue G"], set(), amb, {K("Gue G")}, set()) == (0, 0))
print("units: the seater keeps a 1Y out of the solo seat")
seat = db._arrange_group_seats(["Cap C", "Mem M", "New N"], set(), set(),
                               {"Cap C": "<50", "Mem M": "<50", "New N": "Forward"},
                               captains={"Cap C"}, no_solo={"New N"})
check("1Y is not in seat 3 of a threesome", seat[2] != "New N", seat)

print("units: 1st Timer / First Year rules outrank count rules (Kerry 10/12)")
seat2 = db._arrange_group_seats(["Str S", "New N", "New M"], set(), set(),
                                {"Str S": "<50", "New N": "<50", "New M": "<50"},
                                no_solo={"New N", "New M"}, solo_streak={K("Str S"): 2})
check("a 3rd solo cart in a row (count rule) yields to a First Year player riding alone",
      seat2[2] == "Str S", seat2)
seat3 = db._arrange_group_seats(["Ft F", "Amb A", "Str S"], set(), set(),
                                {"Ft F": "<50", "Amb A": "<50", "Str S": "<50"},
                                ambassadors={"Amb A"}, first_timers={"Ft F"},
                                solo_streak={K("Str S"): 2})
check("a 1st Timer rides with the Ambassador even when that leaves a 3rd solo in a row",
      sorted(seat3[:2]) == ["Amb A", "Ft F"], seat3)
seat4 = db._arrange_group_seats(["Req A", "Req B", "New N"], set(),
                                {frozenset((K("Req A"), K("Req B")))},
                                {"Req A": "<50", "Req B": "<50", "New N": "<50"},
                                no_solo={"New N"})
check("a request still outranks the First Year rule (unchanged until Kerry says)",
      sorted(seat4[:2]) == ["Req A", "Req B"], seat4)

# ── the 10/13 field ───────────────────────────────────────────────────
P = [  # name, tee, captain, ambassador, solo_back_ok, new_1y, guest, request
 ("Gus Vasquez", "50-64", 1, 1, 0, 0, 0, None), ("Michael Murphy", "65+", 0, 0, 0, 0, 0, None),
 ("Rob Burlingame", "<50", 0, 0, 0, 1, 0, None), ("Justin Angelone", "<50", 0, 0, 0, 1, 0, None),
 ("Richard Palacios", "50-64", 0, 0, 0, 0, 0, "Larry Anthis"), ("Larry Anthis", "50-64", 0, 1, 0, 0, 0, "Richard"),
 ("Michelle DelCarmen", "Forward", 0, 0, 0, 0, 0, None), ("Hector Hinojosa", "65+", 0, 0, 0, 0, 1, "Dan South"),
 ("Brian Thompson", "<50", 0, 0, 0, 0, 0, None), ("Wade Lewis", "<50", 0, 0, 0, 1, 0, None),
 ("Scott Marroquin", "50-64", 0, 1, 0, 0, 0, None), ("Kerry Niester", "<50", 1, 1, 1, 0, 0, None),
 ("Jesse Saldana", "<50", 0, 0, 0, 1, 0, None), ("Reggie Johnson", "65+", 0, 0, 0, 1, 0, None),
 ("Adam Baker", "<50", 1, 0, 1, 0, 0, None), ("Dan Stich", "50-64", 0, 0, 0, 0, 0, None),
 ("Michele McCormick", "Forward", 0, 0, 0, 1, 0, None), ("Jeff Rideout", "50-64", 0, 0, 0, 0, 0, None),
 ("Steven Hunt", "50-64", 0, 0, 0, 1, 0, None), ("Luke Mazanec", "<50", 0, 1, 1, 0, 0, None)]
NEW = {n for n, *_r in P if _r[4]}
PAIRS = {("Richard Palacios", "Larry Anthis"): 19, ("Jeff Rideout", "Luke Mazanec"): 2,
         ("Adam Baker", "Dan Stich"): 1, ("Richard Palacios", "Michelle DelCarmen"): 1}
# The sheet Kerry saw on 10/12 (Espinosa already off): 4, 4, 3, 3, 3, 3.
SHEET = [("1A", ["Gus Vasquez", "Michael Murphy", "Rob Burlingame", "Justin Angelone"]),
         ("1B", ["Richard Palacios", "Larry Anthis", "Michelle DelCarmen", "Hector Hinojosa"]),
         ("2A", ["Brian Thompson", "Wade Lewis", "Scott Marroquin"]),
         ("2B", ["Kerry Niester", "Jesse Saldana", "Reggie Johnson"]),
         ("3A", ["Adam Baker", "Dan Stich", "Michele McCormick"]),
         ("3B", ["Jeff Rideout", "Steven Hunt", "Luke Mazanec"])]
EV = 3307


def build(ev_id, date="2026-12-15"):
    with db._connect(DB) as c:
        c.execute("INSERT INTO events (id,item_name,event_date,chapter,status,format,start_time,start_type,course) "
                  "VALUES (?,?,?,?,?,?,?,?,?)", (ev_id, f"s9.27 The Quarry {ev_id}", date, "San Antonio",
                                                  "active", "9 Holes", "4:30 PM", "Shotgun", "The Quarry"))
        c.commit()


with db._connect(DB) as c:
    c.execute("INSERT INTO events (id,item_name,event_date,chapter,status) VALUES "
              "(3000,'s9.1 Earlier','2026-03-01','San Antonio','active')")
    for i, (n, tee, cap, amb_, sok, new, guest, rq) in enumerate(P):
        cid = 900 + i
        fn, ln = n.split(" ", 1)
        c.execute("INSERT INTO customers (customer_id,first_name,last_name,current_player_status,"
                  "group_captain,ambassador,solo_back_ok) VALUES (?,?,?,?,?,?,?)",
                  (cid, fn, ln, "active_guest" if guest else "active_member", cap, amb_, sok))
        # an earlier order, so nobody reads as a 1st Timer (Hinojosa is a 2nd-time guest)
        c.execute("INSERT INTO items (customer,customer_id,item_name,holes,tee_choice,transaction_status,"
                  "order_date,order_id,email_uid,merchant,user_status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (n, cid, "s9.1 Earlier", "9", tee, "active", "2026-03-01", f"E{cid}", f"manual-e{cid}",
                   "GoDaddy", "GUEST" if guest else "MEMBER"))
        if new:   # 1Y: joined as a NEW member this year, no handicap round before it
            c.execute("INSERT INTO customer_memberships (customer_id,started_at,expires_at,source) "
                      "VALUES (?,?,?,'manual')", (cid, "2026-02-01", "2027-02-01"))
        elif not guest:
            c.execute("INSERT INTO customer_memberships (customer_id,started_at,expires_at,source) "
                      "VALUES (?,?,?,'manual')", (cid, "2019-02-01", "2027-02-01"))
    db._ensure_pairing_tables(c)
    k = 0
    for (a, b), cnt in PAIRS.items():
        for _ in range(cnt):
            k += 1
            c.execute("INSERT INTO pairing_history (player_a,player_b,event_id,event_date,rode,source) "
                      "VALUES (?,?,?,?,1,'gg_teesheet')", (a, b, 20000 + k, "2026-06-01"))
    c.commit()


def register(ev_id, names):
    with db._connect(DB) as c:
        for i, (n, tee, cap, amb_, sok, new, guest, rq) in enumerate(P):
            if n not in names:
                continue
            cid = 900 + i
            c.execute("INSERT INTO items (customer,customer_id,item_name,event_id,holes,tee_choice,"
                      "transaction_status,order_date,order_id,email_uid,merchant,user_status,partner_request) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (n, cid, f"s9.27 The Quarry {ev_id}", ev_id, "9", tee, "active", "2026-10-10",
                       f"R{ev_id}{cid}", f"manual-{ev_id}-{cid}", "GoDaddy", "GUEST" if guest else "MEMBER", rq))
        c.commit()


ALL = [p[0] for p in P]
build(EV)
register(EV, ALL)
ROLE = {n: r for n, *r in P}


def gen(ev_id):
    res = db.generate_event_pairings(ev_id, mode="random", protect_partner_requests=True, db_path=DB)
    return res["9"], res.get("mp_notes") or []


def carts(g):
    ps = sorted(g["players"], key=lambda p: p["cart_pos"])
    names = [p["name"] for p in ps]
    return [names[i:i + 2] for i in range(0, len(names), 2)]


def ambs(n):
    return ROLE[n][2] == 1


print("generator, the 10/13 field (20 players)")
groups, notes = gen(EV)
check("five groups for twenty players", len(groups) == 5, [len(g["players"]) for g in groups])
check("everyone seated once", sorted(p["name"] for g in groups for p in g["players"]) == sorted(ALL))
alone = [c[0] for g in groups for c in carts(g) if len(c) == 1]
check("nobody rides alone in five foursomes", not alone, alone)
hector = next(c for g in groups for c in carts(g) if "Hector Hinojosa" in c)
check("Hector Hinojosa rides in an Ambassador's cart",
      any(ambs(n) for n in hector if n != "Hector Hinojosa"), hector)
pal = next(c for g in groups for c in carts(g) if "Richard Palacios" in c)
check("Palacios + Anthis still share a cart (rule 5)", "Larry Anthis" in pal, pal)

print("generator, nineteen players (threesomes exist)")
for drop in ("Michael Murphy", "Dan Stich", "Brian Thompson", "Jeff Rideout"):
    ev2 = 4000 + ALL.index(drop)
    build(ev2)
    names = [n for n in ALL if n != drop]
    register(ev2, names)
    g2, _n = gen(ev2)
    solo = [c[0] for g in g2 for c in carts(g) if len(c) == 1]
    check(f"without {drop}: no first year player rides alone", not (set(solo) & NEW), solo)
    h = next(c for g in g2 for c in carts(g) if "Hector Hinojosa" in c)
    check(f"without {drop}: Hector rides with an Ambassador",
          any(ambs(n) for n in h if n != "Hector Hinojosa"), h)

print("composition: a First Year player is not left alone to save repeat counts")
# Seven players -> a foursome and a threesome. Ann + Bob requested each other.
# Nina (1Y) has played Cal, Dee, Eli and Fay twice each. The cheapest sheet by
# counts alone is Ann/Bob/Nina with Nina riding alone; the rule outranks that.
ev9 = 4700
build(ev9)
SEV = [("Ann Ames", "Bob Bell"), ("Bob Bell", "Ann Ames"), ("Nina New", None), ("Cal Cole", None),
       ("Dee Dunn", None), ("Eli Eads", None), ("Fay Fox", None)]
with db._connect(DB) as c:
    for i, (n, rq) in enumerate(SEV):
        cid = 1900 + i
        fn, ln = n.split(" ", 1)
        c.execute("INSERT INTO customers (customer_id,first_name,last_name,current_player_status,ambassador) "
                  "VALUES (?,?,?,'active_member',1)", (cid, fn, ln))
        c.execute("INSERT INTO items (customer,customer_id,item_name,holes,tee_choice,transaction_status,"
                  "order_date,order_id,email_uid,merchant,user_status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (n, cid, "s9.1 Earlier", "9", "50-64", "active", "2026-03-01", f"E{cid}", f"manual-e{cid}",
                   "GoDaddy", "MEMBER"))
        c.execute("INSERT INTO customer_memberships (customer_id,started_at,expires_at,source) "
                  "VALUES (?,?,?,'manual')", (cid, "2026-02-01" if n == "Nina New" else "2019-02-01", "2027-02-01"))
        c.execute("INSERT INTO items (customer,customer_id,item_name,event_id,holes,tee_choice,"
                  "transaction_status,order_date,order_id,email_uid,merchant,user_status,partner_request) "
                  "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (n, cid, f"s9.27 The Quarry {ev9}", ev9, "9", "50-64", "active", "2026-10-10",
                   f"R{ev9}{cid}", f"manual-{ev9}-{cid}", "GoDaddy", "MEMBER", rq))
    k = 0
    for other in ("Cal Cole", "Dee Dunn", "Eli Eads", "Fay Fox"):
        for _ in range(2):
            k += 1
            c.execute("INSERT INTO pairing_history (player_a,player_b,event_id,event_date,rode,source) "
                      "VALUES (?,?,?,?,0,'gg_teesheet')", ("Nina New", other, 60000 + k, "2026-06-01"))
    c.commit()
g9, _n = gen(ev9)
solo9 = [c[0] for g in g9 for c in carts(g) if len(c) == 1]
check("Nina (1Y) does not ride alone, though it costs repeat counts", "Nina New" not in solo9,
      [[p["name"] for p in g["players"]] for g in g9])
c9 = next(c for g in g9 for c in carts(g) if "Ann Ames" in c)
check("Ann + Bob still ride together", "Bob Bell" in c9, c9)

print("guest exemptions")
ev3 = 4100
build(ev3)
register(ev3, ALL)
with db._connect(DB) as c:   # Hinojosa now asks for someone who IS playing
    c.execute("UPDATE items SET partner_request = 'Dan Stich' WHERE event_id = ? AND customer = 'Hector Hinojosa'",
              (ev3,))
    c.commit()
g3, _n = gen(ev3)
h3 = next(c for g in g3 for c in carts(g) if "Hector Hinojosa" in c)
check("a guest whose request resolves rides with that player", "Dan Stich" in h3, h3)

print("reseat after a removal: 21 -> 20 players drops a group")
ev4 = 4200
build(ev4)
register(ev4, ALL)
sheet = []
for gi, (label, names) in enumerate(SHEET):
    if label == "2A":
        names = names + ["Chris Espinosa"]          # Espinosa was here before he came off
    sheet.append({"group_num": gi + 1, "slot_label": label,
                  "players": [{"name": n, "cart_pos": i + 1} for i, n in enumerate(names)]})
db.save_event_pairings(ev4, {"9": sheet}, db_path=DB)
dry = db.remove_player_from_pairings(ev4, "Chris Espinosa", dry_run=True, reseat=True, db_path=DB)
check("dry run reports the regroup", dry["regrouped"] and dry["regrouped"][0]["applied"]
      and dry["regrouped"][0]["needed"] == 5, dry.get("regrouped"))
check("dry run writes nothing", len(db.get_event_pairings(ev4, db_path=DB)["9"]) == 6)
res = db.remove_player_from_pairings(ev4, "Chris Espinosa", reseat=True, db_path=DB)
after = db.get_event_pairings(ev4, db_path=DB)["9"]
check("five groups after the removal", len(after) == 5, [len(g["players"]) for g in after])
seated = sorted(p["name"] for g in after for p in g["players"])
check("the twenty are all seated once", seated == sorted(ALL), seated)
kept = {tuple(p["name"] for p in sorted(g["players"], key=lambda p: p["cart_pos"])) for g in after}
check("the full foursome 1A is kept seat for seat",
      ("Gus Vasquez", "Michael Murphy", "Rob Burlingame", "Justin Angelone") in kept, kept)
alone4 = [c[0] for g in after for c in carts(g) if len(c) == 1]
check("nobody rides alone after the regroup", not alone4, alone4)
h4 = next(c for g in after for c in carts(g) if "Hector Hinojosa" in c)
check("1B (Hinojosa riding with DelCarmen) is dealt again: he rides with an Ambassador",
      any(ambs(n) for n in h4 if n != "Hector Hinojosa"), h4)
check("1B as saved is gone", ("Richard Palacios", "Larry Anthis", "Michelle DelCarmen", "Hector Hinojosa") not in kept)

print("reseat that must NOT regroup")
ev5 = 4300
build(ev5)
register(ev5, ALL)
db.save_event_pairings(ev5, {"9": [dict(g, players=[dict(p) for p in g["players"]]) for g in sheet]},
                       db_path=DB)
db.remove_player_from_pairings(ev5, "Chris Espinosa", reseat=False, db_path=DB)
check("event under way (reseat=False): six groups, seat left open",
      len(db.get_event_pairings(ev5, db_path=DB)["9"]) == 6)
ev6 = 4400
build(ev6, date="2026-09-01")                      # a past event
register(ev6, ALL)
db.save_event_pairings(ev6, {"9": [dict(g, players=[dict(p) for p in g["players"]]) for g in sheet]},
                       db_path=DB)
db.remove_player_from_pairings(ev6, "Chris Espinosa", db_path=DB)
check("past event: the clock says started, six groups kept",
      len(db.get_event_pairings(ev6, db_path=DB)["9"]) == 6)
ev7 = 4500
build(ev7)
register(ev7, [n for n in ALL if n != "Steven Hunt"])   # Hunt seated but off the roster
db.save_event_pairings(ev7, {"9": [dict(g, players=[dict(p) for p in g["players"]]) for g in sheet]},
                       db_path=DB)
r7 = db.remove_player_from_pairings(ev7, "Chris Espinosa", reseat=True, db_path=DB)
check("roster and sheet differ: groups closed up, not re-dealt",
      len(db.get_event_pairings(ev7, db_path=DB)["9"]) == 6
      and not r7["regrouped"][0]["applied"] and "off the roster" in (r7["regrouped"][0]["reason"] or ""),
      r7.get("regrouped"))

print("audit reads the new rules on the sheet Kerry saw")
ev8 = 4600
build(ev8)
register(ev8, ALL)
db.save_event_pairings(ev8, {"9": [{"group_num": i + 1, "slot_label": lab,
                                    "players": [{"name": n, "cart_pos": j + 1} for j, n in enumerate(ns)]}
                                   for i, (lab, ns) in enumerate(SHEET)]}, db_path=DB)
a = event_pairing_audit(ev8, db_path=DB)
rules = {(f["rule"], f["detail"].split(" (")[0].split(" rides")[0]) for f in a["flags"]}
check("audit: McCormick (1Y) alone is a hard flag", ("first year player alone", "Michele McCormick") in rules,
      a["flags"])
check("audit: Reggie Johnson (1Y) alone is a hard flag", ("first year player alone", "Reggie Johnson") in rules)
check("audit: Hinojosa without an Ambassador cart is a hard flag",
      ("guest + Ambassador cart", "Hector Hinojosa") in rules)

print()
print("ALL PASS" if not F else f"{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
