"""Lone Star Cup RECAP drafts (Kerry 10/9: "Would be nice to auto-generate an
end of day Saturday recap for what happened and where the cup stands after
team sessions. Then a final recap").

The fixture is a REAL board from the Cup engine (lsc_cup.compute_board) on
a 28-player, 28-match, 18-hole weekend, every match scripted hole by hole.
FIXTURE NAMES AND RESULTS ARE INVENTED for the test, not the real Cup.

Checks: a finished Saturday writes the session scores, every match on one
line in match order, the standouts the cards show and the Cup math (SA needs
14 to retain, Austin 14½ to win, from the real totals); an unfinished
Saturday / part-drawn session / mock-scored board is refused; a finished
Sunday names the result, the singles, the clinch ONLY when finish times are
in the data, and perfect weekends; no "$" anywhere; the send is a staff-only
draft, once per kind, force re-runs; the auto job keeps to the Cup's dates
and its setting.

Run: python3 test_lsc_recap.py
"""
import copy
import os
import sys
import tempfile
from datetime import date

os.environ.setdefault("DATABASE_PATH", ":memory:")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from email_parser import lsc_cup as lc          # noqa: E402
from email_parser import lsc_recap as lr        # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + label
          + ("" if cond else "  " + str(detail)[:1500]))
    if not cond:
        FAILURES.append(label)


COURSE = [{"hole": h, "par": 4, "stroke_index": h} for h in range(1, 19)]
AUS = list(range(101, 115))
SA = list(range(201, 215))
# Display lines as the board carries them (members' LAST name in caps).
# Collisions on purpose: two WADEs (one each side), two JONES (Walt Jones a
# guest, plain), so the short names must fall back to the full name.
DISPLAY = {
    101: "Al ADAMS", 102: "Ben BROOKS", 103: "Cal CARTER", 104: "Dan DAVIS",
    105: "Eli EVANS", 106: "Fred FOSTER", 107: "Gus GRANT", 108: "Hal HUGHES",
    109: "Ike IRWIN", 110: "Jay JONES", 111: "Ken KING", 112: "Lou LANE",
    113: "Mary WADE", 114: "Walt Jones",
    201: "Ned NASH", 202: "Oscar OWENS", 203: "Pat PRICE", 204: "Quinn QUAID",
    205: "Rob REED", 206: "Sam SHAW", 207: "Ty TATE", 208: "Uri UPTON",
    209: "Vic VANCE", 210: "Will WEBB", 211: "Xavi XU", 212: "Yuri YOUNG",
    213: "Zack ZANE", 214: "Sam WADE",
}
NAMES = {c: d.title() if d.isupper() else " ".join(w.capitalize() for w in d.split())
         for c, d in DISPLAY.items()}

H = "H" * 18


def pat(head: str) -> str:
    """An 18-hole script: the given holes, then halves."""
    return (head + H)[:18]


# Saturday AM FOURBALL: Austin 3½ - SA 3½
AM = [pat("AAA"),             # M1  Austin 3&2
      pat("SSSAAAAA"),        # M2  Austin from 3 down through 3 -> 2&1 (comeback)
      pat("AS"),              # M3  halved over 18
      pat("SSSSSS"),          # M4  SA 6&5 (biggest margin)
      "H" * 17 + "S",         # M5  SA 1 UP on 18
      pat("AA"),              # M6  Austin 2&1
      pat("SSSS")]            # M7  SA 4&3
# Saturday PM FOURSOMES: SA sweeps 7-0
PM = [pat("SSS"), pat("SS"), "H" * 17 + "S", pat("SSSS"), pat("SSASS"),
      pat("S"), pat("SSSSS")]


def sunday(variant: str) -> list[str]:
    """14 singles. 'defend': Austin 9½ - SA 4½ -> SA 15, AUS 13.
    'tie': Austin 10½ - SA 3½ -> 14-14, SA retains. 'take': Austin 11½ -
    SA 2½ -> AUS 15, SA 13."""
    out = []
    for i in range(14):
        if variant == "defend":
            if i in (0, 4, 6, 13):
                out.append(pat("SSS"))
            elif i == 2:
                out.append(H)
            elif i == 1:
                out.append(pat("SSAAAA"))     # Austin from 2 down -> 2&1
            else:
                out.append(pat("AAA"))
        elif variant == "tie":
            out.append(pat("SSS") if i in (4, 6, 13) else H if i == 2 else pat("AAA"))
        else:  # take
            out.append(pat("SSS") if i in (4, 6) else H if i == 2 else pat("AAA"))
    return out


def dial(n_pm: int = 7):
    am_m = [{"id": f"SAT-AM-{i + 1}", "tee_time": "8:30",
             "austin": AUS[2 * i:2 * i + 2], "sa": SA[2 * i:2 * i + 2]} for i in range(7)]
    # Foursomes: SA pairs rotated one place
    sa_pairs = [SA[2 * i:2 * i + 2] for i in range(7)]
    sa_pairs = sa_pairs[1:] + sa_pairs[:1]
    pm_m = [{"id": f"SAT-PM-{i + 1}", "tee_time": "1:30",
             "austin": AUS[2 * i:2 * i + 2], "sa": sa_pairs[i]} for i in range(n_pm)]
    sun_m = [{"id": f"SUN-{i + 1}", "tee_time": ["8:30", "8:40", "8:50", "9:00", "9:10",
                                                 "9:20", "9:30"][i // 2],
              "austin": [AUS[i]], "sa": [SA[i]]} for i in range(14)]
    return {"event_id": 3329, "defending_champion": "sa", "sessions": [
        {"id": "sat-am", "label": "FOURBALL", "date": "2026-10-10", "format": "fourball",
         "n_holes": 18, "n_matches": 7, "se_round": 1, "matches": am_m},
        {"id": "sat-pm", "label": "FOURSOMES", "date": "2026-10-10", "format": "chapman",
         "n_holes": 18, "n_matches": 7, "se_round": 2, "matches": pm_m},
        {"id": "sun", "label": "SINGLES", "date": "2026-10-11", "format": "singles",
         "n_holes": 18, "n_matches": 14, "se_round": 3, "matches": sun_m}]}


def scores_for(matches, scripts, upto=18):
    sc = {}
    for m, s in zip(matches, scripts):
        for k, side in (("austin", "A"), ("sa", "S")):
            for c in m[k]:
                sc[c] = {h + 1: (4 if (s[h] == side or s[h] == "H") else 5)
                         for h in range(min(upto, 18))}
    return sc


def board(sunday_variant=None, pm_upto=18, n_pm=7, stamps=None, source="entry"):
    d = dial(n_pm)
    sd = {}
    for sess, scripts, upto in ((d["sessions"][0], AM, 18), (d["sessions"][1], PM, pm_upto)):
        sd[sess["id"]] = {"course": COURSE,
                          "phs": {c: 0 for m in sess["matches"] for k in ("austin", "sa") for c in m[k]},
                          "scores": scores_for(sess["matches"], scripts, upto)}
    if sunday_variant:
        sess = d["sessions"][2]
        sd["sun"] = {"course": COURSE, "phs": {c: 0 for c in AUS + SA},
                     "scores": scores_for(sess["matches"], sunday(sunday_variant))}
    b = lc.compute_board(d, sd, NAMES, {"buyers": set(), "index": {}})
    b["configured"] = True
    b["source"] = source
    b["entry_sessions"] = sorted(sd)
    for s in b["sessions"]:
        for m in s["matches"]:
            for p in m["players"]:
                p["lines"] = [DISPLAY[c] for c in p["customer_ids"]]
            if stamps and m["match_id"] in stamps:
                m["decided_at"] = stamps[m["match_id"]]
    return b


CTX = {"course": "The Hideout Golf Club & Resort"}


def no_dollars(r):
    return all("$" not in (r.get(k) or "") for k in ("markup", "text", "html", "subject"))


print("Saturday, finished")
b_sat = board()
r = lr.build_recap("saturday", board=b_sat, context=CTX)
t = r.get("text") or ""
print("\n----- SATURDAY (plain text) -----\n" + t + "-----\n")
check("guard passes when both Saturday sessions are final", r["ok"], r.get("reason"))
check("Saturday covers the two Saturday sessions by date", r["sessions"] == ["sat-am", "sat-pm"], r["sessions"])
check("subject: SA leads 10½–3½", r["subject"] == "TGF Results | SAN ANTONIO Leads the Lone Star Cup 10½–3½", r["subject"])
check("Fourball session score", "FOURBALL.\n\nAustin 3½ – San Antonio 3½." in t, t[:900])
check("Foursomes session score", "FOURSOMES.\n\nAustin 0 – San Antonio 7." in t)
check("Match 1 line: winners, tag, losers, margin",
      "- Match 1: ADAMS & BROOKS (AUS) def. NASH & OWENS 3&2" in t, t)
check("a halved match reads halved", "- Match 3: EVANS & FOSTER (AUS) halved with REED & SHAW (SA)" in t)
check("a 1 UP finish carries its margin", "- Match 5: Sam WADE & Ned NASH" not in t and "- Match 5:" in t and " 1 UP" in t.split("- Match 5:")[1].split("\n")[0])
check("a shared surname prints the full name (WADE, Jones); the guest stays plain",
      "def. Mary WADE & Walt Jones 4&3" in t and "ZANE & Sam WADE (SA)" in t
      and "IRWIN & Jay JONES" in t, t)
MATCH_RE = __import__("re").compile(r"^- Match (\d+):")
lines = [l for l in t.splitlines() if MATCH_RE.match(l)]
check("every Saturday match on one line, in match order 1-14",
      [int(MATCH_RE.match(l).group(1)) for l in lines] == list(range(1, 15)), lines)
check("biggest margin is Match 4, SA 6&5",
      "- The biggest margin: TATE & UPTON (SA) closed out GRANT & HUGHES 6&5 in Match 4." in t, t)
check("comeback from the cards (3 down through 3, won 2&1)",
      "Comeback in Match 2: CARTER & DAVIS (AUS) were 3 down through 3 and won 2&1." in t, t)
check("matches that went 18 are counted and listed",
      "Four matches went all 18 holes: Matches 3, 5, 10 and 13." in t, t)
check("the Foursomes sweep is called", "San Antonio swept the Foursomes, 7–0." in t)
check("where the Cup stands: leader + points left",
      "After Saturday San Antonio leads Austin 10½ to 3½. 14 points are left in Sunday's singles." in t, t)
check("SA needs 3½ to retain (14 of 28), Austin 11 to win (14½)",
      "San Antonio, the defending champion, needs 3½ to retain the Cup (14 of 28 keeps it); "
      "Austin needs 11 to win it (14½)." in t, t)
check("UP NEXT reads Sunday from the dial", "Sun, Oct 11 | first tee time 8:30 | SINGLES | 14 matches, 14 points" in t, t)
check("fellowship is a blank for Kerry, not a guess", lr.FELLOWSHIP_BLANK in t)
check("greeting carries the merge tag", "Good Evening, %first_name%!" in t)
check("signature", t.rstrip().endswith("Kerry Niester\nThe Golf Fellowship\n210.838.3948"), t[-120:])
check("every name is a Spotlight link in the HTML",
      'member/spotlight?player=101"><strong>ADAMS</strong></a>' in r["html"], r["html"][:400])
check("HTML: ruled CAPS heads (Kerry's sent layout)", "<hr />" in r["html"] and "<strong>WHERE THE CUP STANDS.</strong>" in r["html"])
check("HTML went through normalize_email_html (bullets styled)", "<ul>" in r["html"])
check("no dollar sign anywhere (Saturday)", no_dollars(r))
check("no skins anywhere", "skin" not in (r["markup"] or "").lower())

print("\nSaturday, refused")
r = lr.build_recap("saturday", board=board(pm_upto=10), context=CTX)
check("an unfinished Foursomes is refused", not r["ok"] and "sat-pm SAT-PM-3 is live (thru 10)" in (r["reason"] or ""), r.get("reason"))
check("a refusal carries no text", "text" not in r)
r = lr.build_recap("saturday", board=board(n_pm=6), context=CTX)
check("a part-drawn session is refused", not r["ok"] and "only 6 of 7 matches drawn" in (r["reason"] or ""), r.get("reason"))
r = lr.build_recap("saturday", board=board(source="mock"), context=CTX)
check("a mock-scored board is refused", not r["ok"] and "source mock" in (r["reason"] or ""), r.get("reason"))
r = lr.build_recap("final", board=b_sat, context=CTX)
check("final is refused while Sunday hasn't started", not r["ok"] and "sun SUN-1 is upcoming" in (r["reason"] or ""), r.get("reason"))
r = lr.build_recap("sunday", board=b_sat)
check("an unknown kind is refused", not r["ok"])
r = lr.build_recap("saturday", board={"configured": False})
check("no dial is refused", not r["ok"] and "not configured" in r["reason"])

print("\nFinal, SA defends 15-13, no finish times")
b_fin = board("defend")
check("engine: SA 15, Austin 13, status won by SA",
      b_fin["teams"]["sa"]["points"] == 15 and b_fin["teams"]["austin"]["points"] == 13
      and b_fin["cup"]["status"] == "won" and b_fin["cup"]["winner"] == "sa", b_fin["cup"])
r = lr.build_recap("final", board=b_fin, context=CTX)
t = r.get("text") or ""
print("\n----- FINAL (plain text) -----\n" + t + "-----\n")
check("guard passes when every session is final", r["ok"], r.get("reason"))
check("subject: SA defends", r["subject"] == "TGF Results | SAN ANTONIO Defends the Lone Star Cup, 15–13", r["subject"])
check("lede names the result and course",
      "San Antonio defends the Lone Star Cup at The Hideout Golf Club & Resort, 15 to 13." in t, t[:400])
check("session scores + total",
      "- FOURBALL: Austin 3½ – San Antonio 3½" in t and "- FOURSOMES: Austin 0 – San Antonio 7" in t
      and "- SINGLES: Austin 9½ – San Antonio 4½" in t and "- TOTAL: Austin 13 – San Antonio 15" in t, t)
sun_lines = [l for l in t.splitlines() if MATCH_RE.match(l)]
check("Sunday singles 15-28, one line each, in order",
      [int(MATCH_RE.match(l).group(1)) for l in sun_lines] == list(range(15, 29)), sun_lines)
check("a many-way tie for the biggest margin is one compact line",
      "- The biggest margin, 3&2, came in 12 matches: Matches 15, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27 and 28." in t, t)
check("Saturday's facts stay out of the Sunday standouts", "Match 4" not in t.split("THE STANDOUTS.")[1])
check("singles line", "- Match 15: NASH (SA) def. ADAMS 3&2" in t, t)
check("no clinch line without finish times", "clinch" not in t.lower())
check("Sunday comeback from the cards", "Comeback in Match 16: BROOKS (AUS) was 2 down through 2 and won 2&1." in t, t)
check("perfect weekends: the 3-0 players, from the records",
      "PERFECT WEEKENDS.\n\n- Sam WADE (SA) and Ty TATE (SA) won all three matches." in t, t)
recs = lr.records(b_fin)
check("records: 207 is 3-0", recs[207]["w"] == 3 and recs[207]["played"] == 3, recs.get(207))
check("unbeaten with a halve: Rob REED 2-0-1", "Rob REED (SA, 2-0-1)" in t, t)
check("no dollar sign anywhere (final)", no_dollars(r))
check("the player count is the board's", "Thank you to all 28 players" in t)

print("\nFinal, with finish times: the clincher")
# SA needs 3½ on Sunday to reach 14 (defending: half keeps it). SA's Sunday
# points in finishing order: SUN-5 (1) 11½, SUN-1 (1) 12½, SUN-3 halve 13,
# SUN-7 (1) 14 -> the clinch is SUN-7 = Match 21, Ty TATE.
stamps = {f"SUN-{i + 1}": f"2026-10-11 11:{i:02d}:00" for i in range(14)}
stamps.update({"SUN-5": "2026-10-11 10:50:00", "SUN-1": "2026-10-11 11:05:00",
               "SUN-3": "2026-10-11 11:20:00", "SUN-7": "2026-10-11 11:40:00",
               "SUN-14": "2026-10-11 12:30:00"})
b_cl = board("defend", stamps=stamps)
cl = lr.clinch(b_cl)
check("clinch = Match 21 at 14", cl and cl["number"] == 21 and cl["points"] == 14, cl and {k: cl[k] for k in ("number", "points", "at")})
r = lr.build_recap("final", board=b_cl, context=CTX)
check("the clincher is written", "The clincher: Match 21, Ty TATE (SA) won 3&2, the point that took San Antonio to 14 to retain the Cup." in r["text"], r["text"])
partial = dict(stamps)
partial.pop("SUN-9")
check("one Sunday match without a time -> no clinch", lr.clinch(board("defend", stamps=partial)) is None)

print("\nFinal, tie (SA retains) and Austin takes it")
b_tie = board("tie")
r = lr.build_recap("final", board=b_tie, context=CTX)
check("14-14 reads retained", b_tie["cup"]["status"] == "retained" and
      r["subject"] == "TGF Results | SAN ANTONIO Retains the Lone Star Cup" and
      "The weekend finished level, 14 to 14, and the defending champion keeps the Cup on a tie." in r["text"], (b_tie["cup"], r.get("subject")))
b_take = board("take")
r = lr.build_recap("final", board=b_take, context=CTX)
check("Austin 15-13 takes it from SA", r["subject"] == "TGF Results | AUSTIN Takes the Lone Star Cup, 15–13"
      and "Austin takes the Lone Star Cup from San Antonio" in r["text"], r.get("subject"))
st = {f"SUN-{i + 1}": f"2026-10-11 10:{i:02d}:00" for i in range(14)}
cl = lr.clinch(board("take", stamps=st))
# Austin needs 14½: 3½ after Saturday + Sunday points in order SUN-1.. (S wins 5,7; halve 3)
# SUN-1 4½, SUN-2 5½, SUN-3 6, SUN-4 7, SUN-6 8, SUN-8 9, ... SUN-14 = 14½? count:
# wins at 1,2,4,6,8,9,10,11,12,13,14 (11) + halve 3 -> after SUN-13: 3½+10+½ = 14, SUN-14 -> 15
check("challenger clinches past half (14½), at SUN-14 = Match 28", cl and cl["number"] == 28 and cl["points"] == 15, cl and cl.get("number"))
check("no dollars in any variant", all(no_dollars(lr.build_recap("final", board=x, context=CTX))
                                       for x in (b_tie, b_take, b_cl)))

print("\nDelivery: a staff-only draft, once per kind")
from email_parser import database as db      # noqa: E402
from email_parser import fetcher             # noqa: E402

tmp = os.path.join(tempfile.mkdtemp(prefix="tgf-lscrecap-"), "t.db")
db.init_db(tmp)
calls = []
orig_send = fetcher.send_mail_graph
fetcher.send_mail_graph = lambda **kw: calls.append(kw) or True
for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "EMAIL_ADDRESS"):
    os.environ[k] = "test"
try:
    r = lr.send_recap("saturday", db_path=tmp, board=b_sat)
    check("dry run: text + guard, nothing sent", r["status"] == "dry_run" and r["ok"] and r["text"] and not calls, r.get("status"))
    check("default recipient is Kerry only", r["to"] == ["kerry@thegolffellowship.com"], r["to"])
    r = lr.send_recap("final", send=True, db_path=tmp, board=b_sat)
    check("a refused guard never sends", r["status"] == "refused" and not calls, r)
    r = lr.send_recap("final", send=True, force=True, db_path=tmp, board=b_sat)
    check("force does not bypass the guard", r["status"] == "refused" and not calls, r)
    r = lr.send_recap("saturday", send=True, db_path=tmp, board=b_sat)
    check("send mails the draft", r["status"] == "sent" and len(calls) == 1, r)
    check("to Kerry, draft subject, recap in the body",
          calls and calls[0]["to_address"] == "kerry@thegolffellowship.com"
          and calls[0]["subject"] == "Lone Star Cup recap draft — Saturday"
          and "WHERE THE CUP STANDS." in calls[0]["html_body"], calls and calls[0]["subject"])
    check("the email carries no dollar sign", calls and "$" not in calls[0]["html_body"])
    st_ = lr.sent_state(3329, "saturday", db_path=tmp)
    check("recorded in lsc_recap_sent", st_ and st_["status"] == "sent" and st_["attempts"] == 1, st_)
    r = lr.send_recap("saturday", send=True, db_path=tmp, board=b_sat)
    check("never re-sends", r["status"] == "skipped_already_sent" and len(calls) == 1, r.get("status"))
    r = lr.send_recap("saturday", send=True, force=True, db_path=tmp, board=b_sat)
    check("force re-runs it", r["status"] == "sent" and len(calls) == 2, r.get("status"))
    db.set_app_setting("lsc_recap_to", "pat@gmail.com", db_path=tmp)
    r = lr.send_recap("saturday", send=True, force=True, db_path=tmp, board=b_sat)
    check("a member address is refused before any send", r["status"] == "refused"
          and "staff only" in (r.get("reason") or "") and len(calls) == 2, r)
    db.set_app_setting("lsc_recap_to", "", db_path=tmp)

    print("\nThe auto job")
    tmp2 = os.path.join(tempfile.mkdtemp(prefix="tgf-lscrecap2-"), "t.db")
    db.init_db(tmp2)
    n0 = len(calls)
    check("window = the Cup's dates through the day after", lr.cup_window(b_sat) == (date(2026, 10, 10), date(2026, 10, 12)))
    r = lr.lsc_recap_auto_check(db_path=tmp2, today=date(2026, 10, 9), board=b_sat)
    check("outside the dates: nothing", "outside" in (r.get("skipped") or "") and len(calls) == n0, r)
    db.set_app_setting("lsc_recap_auto", "0", db_path=tmp2)
    r = lr.lsc_recap_auto_check(db_path=tmp2, today=date(2026, 10, 10), board=b_sat)
    check("setting off: nothing", "off" in (r.get("skipped") or "") and len(calls) == n0, r)
    db.set_app_setting("lsc_recap_auto", "", db_path=tmp2)
    check("the setting defaults ON", lr.auto_enabled(db_path=tmp2))
    r = lr.lsc_recap_auto_check(db_path=tmp2, today=date(2026, 10, 10), board=board(pm_upto=10))
    check("Saturday not final: nothing", r.get("skipped") == "nothing final yet" and len(calls) == n0, r)
    r = lr.lsc_recap_auto_check(db_path=tmp2, today=date(2026, 10, 10), board=b_sat)
    check("Saturday final: the Saturday draft goes once", r.get("kind") == "saturday" and r.get("status") == "sent"
          and len(calls) == n0 + 1, r)
    r = lr.lsc_recap_auto_check(db_path=tmp2, today=date(2026, 10, 10), board=b_sat)
    check("next tick: already sent, no mail", "already" in (r.get("status") or "") and len(calls) == n0 + 1, r)
    r = lr.lsc_recap_auto_check(db_path=tmp2, today=date(2026, 10, 11), board=b_fin)
    check("whole Cup final: the final draft goes once", r.get("kind") == "final" and r.get("status") == "sent"
          and len(calls) == n0 + 2, r)
    r = lr.lsc_recap_auto_check(db_path=tmp2, today=date(2026, 10, 12), board=b_fin)
    check("and never again", "already" in (r.get("status") or "") and len(calls) == n0 + 2, r)
    tmp3 = os.path.join(tempfile.mkdtemp(prefix="tgf-lscrecap3-"), "t.db")
    db.init_db(tmp3)
    fetcher.send_mail_graph = lambda **kw: calls.append(kw) and False
    for i in range(5):
        lr.lsc_recap_auto_check(db_path=tmp3, today=date(2026, 10, 10), board=b_sat)
    check("a failing send retries at most 3 times", lr.sent_state(3329, "saturday", db_path=tmp3)["attempts"] == 3
          and len(calls) == n0 + 5, lr.sent_state(3329, "saturday", db_path=tmp3))
finally:
    fetcher.send_mail_graph = orig_send

print("\nWiring")
here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, "mcp_server.py"), encoding="utf-8").read()
check("bridge scoring-lsc-recap is dispatched", 'cmd == "scoring-lsc-recap"' in src)
app_src = open(os.path.join(here, "app.py"), encoding="utf-8").read()
check("scheduler job lsc_recap_auto registered every 10 minutes",
      'id="lsc_recap_auto"' in app_src and "lsc_recap_auto_check" in app_src and 'minute="*/10"' in app_src)
check("the board carries each session's n_matches", all("n_matches" in s for s in b_sat["sessions"]))

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILURE(S):")
    for f in FAILURES:
        print("  - " + f)
    sys.exit(1)
print("ALL PASS")
