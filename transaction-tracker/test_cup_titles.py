"""Cup champion titles on the Spotlight header (Kerry 2026-10-12).

Run: python3 test_cup_titles.py
"""
import os, sys, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(prefix="tgf-cups-"), "t.db")
os.environ.setdefault("SECRET_KEY", "test-only-not-real")
logging.disable(logging.ERROR)
from email_parser import cup_titles as ct          # noqa: E402
from email_parser import database as db            # noqa: E402
F = []


def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c:
        F.append(l)


GUS, ROBERT, JAY, MARK = 42, 31, 289, 299
cur = {"fellowship_cup": [GUS], "players_cup": [ROBERT]}
g = ct.cup_titles(GUS, 2026, cur)
check("Gus: one line, Kerry's copy of record", [t["line"] for t in g] == ["The Fellowship Cup - 2026 Champion"], str(g))
r = ct.cup_titles(ROBERT, 2026, cur)
check("Robert: 2024 from Kerry's list plus 2026 derived, 'and' joined",
      [t["line"] for t in r] == ["The Players Cup - 2024 & 2026 Champion"], str(r))
j = ct.cup_titles(JAY, 2026, cur)
check("Jay Horton: Fellowship Cup 2025, Players Cup 2023 & 2025 (first year of the Players Cup), Fellowship above Players",
      [t["line"] for t in j] == ["The Fellowship Cup - 2025 Champion", "The Players Cup - 2023 & 2025 Champion"], str(j))
check("Paul Day (497): Fellowship Cup 2023 from Kerry's photo caption",
      [t["line"] for t in ct.cup_titles(497, 2026, cur)] == ["The Fellowship Cup - 2023 Champion"])
check("Mark Freund: Fellowship Cup 2024 only", [t["line"] for t in ct.cup_titles(MARK, 2026, cur)] == ["The Fellowship Cup - 2024 Champion"])
check("a player who is nobody's champion gets nothing", ct.cup_titles(7, 2026, cur) == [] and ct.cup_titles(7, 2026, None) == [])
check("a cup that is not final (no champions) derives nothing for 2026",
      ct.cup_titles(GUS, 2026, {"fellowship_cup": None, "players_cup": []}) == [])
check("three or more years: commas then '&'", ct.title_line("players_cup", [2026, 2022, 2024]) == "The Players Cup - 2022, 2024 & 2026 Champion")
check("the same year twice reads once", ct.title_line("fellowship_cup", [2026, 2026]) == "The Fellowship Cup - 2026 Champion")
check("Gus on the Players Cup standings but not its champion gets no Players Cup line",
      all(t["cup"] != "players_cup" for t in ct.cup_titles(GUS, 2026, cur)))
check("the wrapper reads the champions off the cup payloads and never raises",
      [t["line"] for t in db._spotlight_cup_titles(GUS, {"champions": [{"customer_id": ROBERT}]},
                                                    {"champions": [{"customer_id": GUS}]})]
      == ["The Fellowship Cup - 2026 Champion"]
      and db._spotlight_cup_titles(GUS, None, None) == []
      and db._spotlight_cup_titles(GUS, {"champions": "bad"}, {}) == [])
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "spotlight.html")).read()
check("the Spotlight header renders the server's lines as the card's last row",
      "d.cup_titles" in src and "${champLines}</div>`" in src and 'class="spt-champs"' in src)
con = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "contests.html")).read()
check("the plaque's third line (the cup's name) is gone, the photo tag carries it", "tgf-champ-sub" in con and
      'sub.textContent = p.cup' not in con)
jp = {t["cup"]: [x["key"] for x in t["photos"]] for t in ct.cup_titles(JAY, 2026, cur)}
check("Jay's titles carry his registered photos in year order (Fellowship 2025; Players 2023, no 2025 photo)",
      jp == {"fellowship_cup": ["fellowship_cup-2025"], "players_cup": ["players_cup-2023"]}, str(jp))
rp = {t["cup"]: [x["key"] for x in t["photos"]] for t in ct.cup_titles(ROBERT, 2026, cur)}
check("Robert's 2026 plaque photo and his 2024 photo are both on his Players Cup title",
      rp == {"players_cup": ["players_cup-2024", "players_cup-2026"]}, str(rp))
check("a photo that does not show the player is never attached (Gus gets only his own)",
      [x["key"] for t in ct.cup_titles(GUS, 2026, cur) for x in t["photos"]] == ["fellowship_cup-2026"])
pc = ct.past_champions({497: "Paul Day", 299: "Mark Freund", 289: "Jay Horton", 31: "Robert Straiton"})
check("past_champions: newest first, names from the map, photo only when it shows exactly the champion(s)",
      [r["year"] for r in pc["players_cup"]] == [2025, 2024, 2023] and pc["players_cup"][0]["photo"] is None
      and pc["players_cup"][1]["names"] == ["Robert Straiton"] and pc["fellowship_cup"][2]["names"] == ["Paul Day"])
check("the Spotlight draws the photos under the titles and opens them in a lightbox",
      "sptChampPhotos(d.cup_titles)" in src and "spt-champ-ph" in src and "spt-champ-lb" in src)
check("both cup boards get a collapsed Past Champions strip filled from /api/cup-champions",
      "fcPastChampsLoad" in con and 'data-race="fellowship_cup" hidden' in con and 'data-race="players_cup" hidden' in con
      and "/api/cup-champions" in con and "Past Champions" in con)
print("ALL PASS" if not F else f"FAILED: {F}")
sys.exit(1 if F else 0)
