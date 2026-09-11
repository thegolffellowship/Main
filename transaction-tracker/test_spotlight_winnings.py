"""Winnings by Game on the Player Spotlight (Kerry ratified 2026-09-11).

Option A: bundle-first rows (NET / GROSS / Included / Season Contests)
that expand to per-game rows, scoped by a page-level SEASON-per-year |
ALL-TIME toggle. Bundle membership is rules-as-data (app_settings
`spotlight_winnings_bundles`, seeded by SEED_WINNINGS_BUNDLES).

Covers the pure aggregation `_winnings_by_game`:
  - production category spellings map to the ratified bundles
    (rows use `ctp`; label maps also carry `closest_to_pin` — both
    must land in Included, merged as ONE game row);
  - an unknown category lands in the catch_all bundle, never vanishes;
  - per-year scoping + all_time, years discovered from the data;
  - every bundle renders even at $0 (Kerry: a zero GROSS row
    advertises the games you're not in);
  - buy-in counters resolve per scope;
  - bundle totals sum exactly to the payout total (page self-audits
    against the Won tile).

Run: python3 test_spotlight_winnings.py
"""

import os

os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


PAYOUTS = [
    # 2026 event games — production spellings + real description shapes
    # from the 2026-09-11 audit (s9.22, s18.10)
    {"category": "team_net", "amount": 12.0, "event_date": "2026-09-08",
     "event_name": "s9.22 Silverhorn",
     "description": "TEAM Net 1st (T) (team split)"},
    # two CTP spellings, SAME event — one game row, bits accumulate
    {"category": "ctp", "amount": 24.0, "event_date": "2026-09-08",
     "event_name": "s9.22 Silverhorn",
     "description": "CTP Closest to Pin #13"},
    {"category": "closest_to_pin", "amount": 19.0,
     "event_date": "2026-09-08", "event_name": "s9.22 Silverhorn",
     "description": "CTP Closest to Pin #16"},
    {"category": "skins", "amount": 39.0, "event_date": "2026-09-08",
     "event_name": "s9.22 Silverhorn",
     "description": "Skins Par on 17 (GG $)"},
    {"category": "skins", "amount": 15.6, "event_date": "2026-08-29",
     "event_name": "s18.10 FALL KICKOFF | Landa Park",
     "description": "Skins HIGH Flight ×2 holes 2, 18"},
    {"category": "individual_net", "amount": 67.5,
     "event_date": "2026-09-08", "event_name": "s9.22 Silverhorn",
     "description": "Ind Net LOW Flight 1st (T) (GG $)"},
    {"category": "individual_gross", "amount": 36.0,
     "event_date": "2026-08-29",
     "event_name": "s18.10 FALL KICKOFF | Landa Park",
     "description": "Ind Gross FLIGHT 3 | HDCP 12+ 1st (GG $)"},
    {"category": "mvp", "amount": 30.0, "event_date": "2026-09-08",
     "event_name": "s9.22 Silverhorn", "description": "City MVP"},
    {"category": "tgf_mvp", "amount": 50.0, "event_date": "2026-09-08",
     "event_name": "s9.22 Silverhorn",
     "description": "TGF MVP (combined same-day pot)"},
    # season rows store display-string categories
    {"category": "City Net", "amount": 200.0, "event_date": "2026-08-01",
     "event_name": "SAN ANTONIO Net 2026",
     "description": "SAN ANTONIO Net 2026 final standings — 2 place"},
    {"category": "Match Play", "amount": 100.0, "event_date": "2026-08-01",
     "event_name": "SAN ANTONIO MATCH PLAY 2026"},
    {"category": "monthly_points", "amount": 70.0,
     "event_date": "2026-06-30", "event_name": "JUNE Points 2026"},
    # a category nobody declared — must land in the catch_all bundle
    {"category": "mystery_game", "amount": 5.0, "event_date": "2026-05-01"},
    # a prior-year row (synthetic) — drives the per-year scoping
    {"category": "skins", "amount": 10.0, "event_date": "2025-06-01"},
]

BUYINS = {
    "all_time": {"net": 9, "gross": 7, "events": 15, "contests": 3},
    "years": {"2026": {"net": 8, "gross": 6, "events": 14, "contests": 3},
              "2025": {"net": 1, "gross": 1, "events": 1, "contests": 0}},
}

out = db._winnings_by_game(PAYOUTS, db.SEED_WINNINGS_BUNDLES, 2026, BUYINS)

check("years discovered from data, newest first",
      out["years"] == ["2026", "2025"], repr(out["years"]))
check("current_year rides along", out["current_year"] == 2026)

y26 = {b["key"]: b for b in out["by_year"]["2026"]}
y25 = {b["key"]: b for b in out["by_year"]["2025"]}
allt = {b["key"]: b for b in out["all_time"]}

check("all four bundles present even when empty",
      set(y25) == {"net", "gross", "included", "season"}, repr(set(y25)))
check("2025 NET bundle shows $0 (zero rows still render)",
      y25["net"]["total"] == 0 and y25["net"]["games"] == [])

check("NET 2026 = Ind Net + City MVP + TGF MVP",
      y26["net"]["total"] == 147.5, y26["net"]["total"])
check("GROSS 2026 = Skins + Ind Gross",
      y26["gross"]["total"] == 90.6, y26["gross"]["total"])
inc = y26["included"]
check("Included 2026 = Team Net + both CTP spellings",
      inc["total"] == 55.0, inc["total"])
ctp_rows = [g for g in inc["games"] if g["label"] == "Closest to Pin"]
check("ctp + closest_to_pin merge into ONE game row",
      len(ctp_rows) == 1 and ctp_rows[0]["count"] == 2
      and ctp_rows[0]["total"] == 43.0,
      repr(inc["games"]))
sea = y26["season"]
check("Season Contests 2026 collects display-string categories",
      sea["total"] == 375.0, sea["total"])
check("unknown category lands in catch_all, not dropped",
      any(g["category"] == "mystery_game" for g in sea["games"]),
      repr([g["category"] for g in sea["games"]]))
check("City Net shows its member-facing label",
      any(g["label"] == "City Points Race" for g in sea["games"]))

check("2025 skins scoped to 2025",
      y25["gross"]["total"] == 10.0 and allt["gross"]["total"] == 100.6,
      (y25["gross"]["total"], allt["gross"]["total"]))

total_payouts = round(sum(p["amount"] for p in PAYOUTS), 2)
check("all_time bundle totals sum exactly to the payout total",
      round(sum(b["total"] for b in out["all_time"]), 2) == total_payouts,
      (round(sum(b["total"] for b in out["all_time"]), 2), total_payouts))
per_year_sum = round(sum(b["total"] for y in out["years"]
                         for b in out["by_year"][y]), 2)
check("per-year totals partition the all-time total",
      per_year_sum == total_payouts, (per_year_sum, total_payouts))

check("buy-ins resolve per scope (2026 NET)",
      y26["net"]["buyins"] == 8, y26["net"]["buyins"])
check("buy-ins resolve per scope (all-time events)",
      allt["included"]["buyins"] == 15, allt["included"]["buyins"])
check("buyin noun rides on the bundle",
      y26["included"]["buyin_noun"] == "event")

# games sorted biggest first inside a bundle
g_order = [g["total"] for g in y26["net"]["games"]]
check("games sorted by total desc", g_order == sorted(g_order, reverse=True),
      g_order)

# no buy-in counts supplied -> buyins stays None (payload shows nothing)
out2 = db._winnings_by_game(PAYOUTS, db.SEED_WINNINGS_BUNDLES, 2026, None)
check("missing buy-in counts degrade to None, not 0",
      all(b["buyins"] is None for b in out2["all_time"]))

# empty payouts: current year still present so the toggle renders
out3 = db._winnings_by_game([], db.SEED_WINNINGS_BUNDLES, 2026, None)
check("no payouts still yields the current season at $0",
      out3["years"] == ["2026"]
      and all(b["total"] == 0 for b in out3["by_year"]["2026"]))

# ── per-event drill-down (Kerry 2026-09-11 follow-up): each game row
#    carries the events it was won in, with flight/place + amount ──
ctp_g = ctp_rows[0]
check("CTP: two rows in one event fold to ONE event line",
      len(ctp_g["events"]) == 1 and ctp_g["events"][0]["total"] == 43.0,
      repr(ctp_g["events"]))
check("CTP event line accumulates both holes",
      ctp_g["events"][0]["detail"] == "Hole 13 · Hole 16",
      repr(ctp_g["events"][0]["detail"]))
ind_net = next(g for g in y26["net"]["games"] if g["label"] == "Individual Net")
check("Ind Net event carries tied place + flight",
      ind_net["events"][0]["detail"] == "T1st Place · Low Flight",
      repr(ind_net["events"][0]["detail"]))
ind_gr = next(g for g in y26["gross"]["games"]
              if g["label"] == "Individual Gross")
check("Ind Gross event carries place + numeric flight",
      ind_gr["events"][0]["detail"] == "1st Place · Flight 3",
      repr(ind_gr["events"][0]["detail"]))
sk = next(g for g in y26["gross"]["games"] if g["label"] == "Skins")
check("Skins events sorted newest first",
      [e["event_date"] for e in sk["events"]] == ["2026-09-08", "2026-08-29"],
      repr([e["event_date"] for e in sk["events"]]))
check("Skins flighted event carries holes + flight",
      sk["events"][1]["detail"] == "Holes 2 & 18 · High Flight",
      repr(sk["events"][1]["detail"]))
cn = next(g for g in sea["games"] if g["label"] == "City Points Race")
check("Season standings row carries the standings place",
      cn["events"][0]["detail"] == "2nd Place | Season Standings",
      repr(cn["events"][0]["detail"]))
check("event names ride on the drill-down lines",
      sk["events"][0]["event_name"] == "s9.22 Silverhorn")
check("a row with no description still yields an event line",
      next(g for g in sea["games"] if g["category"] == "mystery_game")
      ["events"][0]["detail"] == "")

# dial fallback: malformed JSON must fall back to the seed, not blank
check("seed bundles well-formed",
      db.get_winnings_bundles.__doc__ is not None
      and all(b.get("key") and isinstance(b.get("categories"), list)
              for b in db.SEED_WINNINGS_BUNDLES))

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
    raise SystemExit(1)
print("ALL PASS")
