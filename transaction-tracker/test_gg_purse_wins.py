"""Checks for the GG-purse-wins extension (Kerry-ratified 2026-08-31):
the section-aware board parser that lets import_gg_game_results capture
Ind Net / Ind Gross flighted boards (one table, single-cell flight label
rows) alongside the unsectioned CTP / Team Net boards it always read.

Run: python3 test_gg_purse_wins.py
"""
import sys

sys.path.insert(0, ".")
from email_parser.database import (_game_winners_from_table,  # noqa: E402
                                   _split_board_sections)

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


HEAD = ["Pos.", "Player", "Playing Handicap", "Total Gross", "To Par Net",
        "Total Net", "Purse"]

FLIGHTED = [
    ["LOW Flight"],
    HEAD,
    ["T1", "STRAITON, Robert TGF Austin", "1", "70", "-2", "69 (37/32)", "$78.80"],
    ["T1", "YOUNGS, Luke TGF Austin", "4", "73", "-2", "69 (37/32)", "$78.80"],
    ["3", "NIESTER, Kerry TGF San Antonio", "2", "72", "-1", "70 (35/35)", "$39.40"],
    ["4", "BAKER, Adam TGF San Antonio", "10", "83", "+2", "73 (41/32)", "$0.00"],
    ["\xa0"],
    ["HIGH Flight"],
    HEAD,
    ["1", "McCORMICK, Sam TGF Austin", "21", "90", "-2", "69 (41/28)", "$98.50"],
    ["2", "STICH, Dan TGF San Antonio", "14", "84", "-1", "70 (38/32)", "$59.10"],
    ["Total Purse Allocated: $394.00"],
]

UNSECTIONED = [
    ["Pos.", "Player", "Purse"],
    ["1", "HOGUE, Jay TGF Austin", "$37.33"],
    ["2", "WADE, John TGF Austin", "$0.00"],
]

NO_PURSE_FLIGHTED = [
    ["FLIGHT 1 | HDCP < 6"],
    ["Pos.", "Player", "Purse"],
    ["1", "STRAITON, Robert TGF Austin", "$0.00"],
    ["2", "NIESTER, Kerry TGF San Antonio", "$0.00"],
    ["FLIGHT 2 | HDCP 6 - 12"],
    ["Pos.", "Player", "Purse"],
    ["T1", "HOGUE, Jay TGF Austin", "$0.00"],
    ["T1", "SHARP, Matt TGF Austin", "$0.00"],
]


def main():
    secs = _split_board_sections(FLIGHTED)
    check("flighted board splits into two labeled sections",
          [s[0] for s in secs] == ["LOW Flight", "HIGH Flight"]
          and [len(s[1]) for s in secs] == [5, 3], str([(s[0], len(s[1])) for s in secs]))

    w = _game_winners_from_table(FLIGHTED)
    check("purse winners captured per section with flight label",
          [(x["player"], x["purse"], x["section"]) for x in w] == [
              ("STRAITON, Robert", 78.80, "LOW Flight"),
              ("YOUNGS, Luke", 78.80, "LOW Flight"),
              ("NIESTER, Kerry", 39.40, "LOW Flight"),
              ("McCORMICK, Sam", 98.50, "HIGH Flight"),
              ("STICH, Dan", 59.10, "HIGH Flight")],
          str([(x["player"], x["purse"], x["section"]) for x in w]))
    check("chapter stripped from names, position kept",
          w[0]["chapter"] == "Austin" and w[0]["position"] == "T1"
          and w[0]["is_team"] == 0, str(w[0]))

    u = _game_winners_from_table(UNSECTIONED)
    check("unsectioned board parses exactly as before (section None)",
          [(x["player"], x["purse"], x["section"]) for x in u]
          == [("HOGUE, Jay", 37.33, None)], str(u))
    check("unsectioned split is identity",
          _split_board_sections(UNSECTIONED) == [(None, UNSECTIONED)], "")

    n = _game_winners_from_table(NO_PURSE_FLIGHTED)
    check("no-purse board falls back to position-1 rows PER SECTION",
          sorted(x["player"] for x in n)
          == ["HOGUE, Jay", "SHARP, Matt", "STRAITON, Robert"], str(n))

    if FAILURES:
        print(f"\n{len(FAILURES)} FAILURE(S)")
        sys.exit(1)
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
