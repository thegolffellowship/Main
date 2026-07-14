"""Proof that the Match Play engine seed reproduces the ratified matrix.

Expected values are transcribed column-by-column from
OneDrive/01_STANDARDS/Prizes/"Prizes-Match Play Matrix.xlsx" (July 6 final).
Run: python3 test_match_play.py
"""

from email_parser.match_play import (
    SEED_MATCH_PLAY_CONFIG,
    allocate_cents,
    cross_pool_semi_order,
    ladder_payout_rows,
    seed_bracket,
    seed_order,
    structure_for_n,
)

# N: (pools, knockout, wildcards, pot, bonus_each, bonus_total, adjusted,
#     ladder dollar amounts)
XLSX = {
    4:  (1, 2, 0, 160, 25, 25, 135, [97, 38]),
    5:  (1, 2, 0, 200, 20, 20, 180, [120, 60]),
    6:  (2, 4, 0, 240, 20, 40, 200, [125, 45, 30]),
    7:  (2, 4, 0, 280, 20, 40, 240, [132, 60, 48]),
    8:  (2, 4, 0, 320, 20, 40, 280, [140, 84, 56]),
    9:  (2, 4, 0, 360, 20, 40, 320, [160, 96, 64]),
    10: (2, 4, 0, 400, 20, 40, 360, [180, 108, 72]),
    11: (3, 8, 2, 440, 20, 60, 380, [190, 95, 57, 38]),
    12: (3, 8, 2, 480, 20, 60, 420, [210, 105, 63, 42]),
    13: (3, 8, 2, 520, 20, 60, 460, [230, 115, 69, 46]),
    14: (3, 8, 2, 560, 20, 60, 500, [250, 125, 75, 50]),
    15: (3, 8, 2, 600, 20, 60, 540, [270, 135, 81, 54]),
    16: (4, 8, 0, 640, 20, 80, 560, [280, 140, 84, 56]),
    17: (4, 8, 0, 680, 20, 80, 600, [300, 150, 90, 60]),
    18: (4, 8, 0, 720, 20, 80, 640, [320, 160, 96, 64]),
    19: (4, 8, 0, 760, 20, 80, 680, [340, 170, 102, 68]),
    20: (5, 12, 2, 800, 20, 100, 700, [350, 175, 105, 70]),
    21: (5, 12, 2, 840, 20, 100, 740, [370, 185, 111, 74]),
    22: (5, 12, 2, 880, 20, 100, 780, [390, 195, 117, 78]),
    23: (5, 12, 2, 920, 20, 100, 820, [410, 205, 123, 82]),
    24: (6, 16, 4, 960, 20, 120, 840, [420, 210, 126, 84]),
    25: (6, 16, 4, 1000, 20, 120, 880, [440, 220, 132, 88]),
    26: (6, 16, 4, 1040, 20, 120, 920, [460, 230, 138, 92]),
    27: (6, 16, 4, 1080, 20, 120, 960, [480, 240, 144, 96]),
    28: (7, 16, 2, 1120, 20, 140, 980, [490, 245, 147, 98]),
    29: (7, 16, 2, 1160, 20, 140, 1020, [510, 255, 153, 102]),
    30: (7, 16, 2, 1200, 20, 140, 1060, [530, 265, 159, 106]),
    31: (7, 16, 2, 1240, 20, 140, 1100, [550, 275, 165, 110]),
    32: (8, 16, 0, 1280, 20, 160, 1120, [560, 280, 168, 112]),
}


def test_matrix_parity():
    cfg = SEED_MATCH_PLAY_CONFIG
    for n, (pools, ko, wc, pot, be, bt, adj, amounts) in XLSX.items():
        s = structure_for_n(cfg, n)
        assert s["pools"] == pools, (n, "pools", s["pools"])
        assert s["knockout"] == ko, (n, "knockout", s["knockout"])
        assert s["wildcards"] == wc, (n, "wildcards", s["wildcards"])
        assert s["pot"] == pot, (n, "pot", s["pot"])
        assert s["pool_winner_bonus_each"] == be, (n, "bonus_each")
        assert s["pool_winner_bonus_total"] == bt, (n, "bonus_total")
        assert s["adjusted_pot"] == adj, (n, "adjusted", s["adjusted_pot"])
        assert s["ladder_amounts"] == [float(a) for a in amounts], (
            n, "amounts", s["ladder_amounts"])
        # exact-division: ladder always sums to the adjusted pot
        assert sum(s["ladder_amounts_cents"]) == s["adjusted_pot_cents"], n
        # pool sizes: bounded 3-5 (single-pool N=4/5 excepted), sum to N
        sizes = s["pool_sizes"]
        assert sum(sizes) == n
        if pools > 1:
            assert all(3 <= x <= 5 for x in sizes), (n, sizes)
        # advancers + wildcards fill the bracket exactly
        assert pools * s["advance_per_pool"] + wc == ko, (n, "bracket fill")
        # byes only on the 12 bracket
        assert s["byes"] == (4 if ko == 12 else 0), (n, "byes")


def test_seed_order():
    assert seed_order(8) == [1, 8, 4, 5, 2, 7, 3, 6]
    assert seed_order(16) == [1, 16, 8, 9, 4, 13, 5, 12, 2, 15, 7, 10, 3, 14, 6, 11]


def test_bracket_12_byes():
    entrants = [{"player_name": f"P{i}"} for i in range(1, 13)]
    b = seed_bracket(entrants, 12)
    assert b["template_size"] == 16
    assert b["rounds"] == ["r16", "qf", "sf", "final"]
    byes = {p["player"]["player_name"] for p in b["bye_placements"]}
    assert byes == {"P1", "P2", "P3", "P4"}, byes
    # bye seeds land at the qf slot equal to their r16 match index
    slot_of = {p["player"]["player_name"]: p["slot"] for p in b["bye_placements"]}
    assert slot_of == {"P1": 0, "P4": 2, "P2": 4, "P3": 6}
    # r16 real matches: 8v9, 5v12, 7v10, 6v11
    pairs = set()
    fr = {r["slot"]: r["player"]["player_name"] for r in b["first_round"]}
    for m in range(8):
        a, c = fr.get(m * 2), fr.get(m * 2 + 1)
        if a and c:
            pairs.add(frozenset((a, c)))
    assert pairs == {frozenset(("P8", "P9")), frozenset(("P5", "P12")),
                     frozenset(("P7", "P10")), frozenset(("P6", "P11"))}


def test_bracket_4_and_2():
    b = seed_bracket([{"player_name": f"P{i}"} for i in range(1, 5)], 4)
    assert b["rounds"] == ["sf", "final"] and not b["bye_placements"]
    b = seed_bracket([{"player_name": "A"}, {"player_name": "B"}], 2)
    assert b["rounds"] == ["final"] and len(b["first_round"]) == 2


def test_tie_split():
    s = structure_for_n(SEED_MATCH_PLAY_CONFIG, 10)  # 180/108/72
    rows = ladder_payout_rows(s, [["Champ"], ["Runner"], ["SF1", "SF2"]])
    by_name = {r["player_name"]: r for r in rows}
    assert by_name["Champ"]["amount"] == 180.0
    assert by_name["Runner"]["amount"] == 108.0
    # 3rd+4th combined = 72 + 0 (3-place ladder) → 36 each
    assert by_name["SF1"]["amount"] == 36.0 and by_name["SF2"]["amount"] == 36.0
    assert by_name["SF1"]["place_label"] == "3rd–4th (T)"

    s = structure_for_n(SEED_MATCH_PLAY_CONFIG, 20)  # 350/175/105/70
    rows = ladder_payout_rows(s, [["C"], ["R"], ["S1", "S2"]])
    by_name = {r["player_name"]: r for r in rows}
    # 3rd+4th combined = 105+70 = 175 → 87.50 each
    assert by_name["S1"]["amount"] == 87.5 and by_name["S2"]["amount"] == 87.5
    total = sum(r["amount"] for r in rows)
    assert total == s["adjusted_pot"], total


def test_cross_pool_semis():
    # Kerry 2026-07-14: 4-player knockout semis are cross-pool — each
    # pool winner vs the OTHER pool's runner-up; Stableford never seeds
    # this bracket. Seed order [A1, B1, A2, B2] through classic 4-slot
    # placement (1v4, 2v3) must land A1vB2 and B1vA2.
    a1, a2 = {"player_name": "A1"}, {"player_name": "A2"}
    b1, b2 = {"player_name": "B1"}, {"player_name": "B2"}
    order = cross_pool_semi_order([a1, a2], [b1, b2])
    assert order == [a1, b1, a2, b2]
    plan = seed_bracket(order, 4)
    fr = [e["player"]["player_name"] for e in plan["first_round"]]
    assert fr == ["A1", "B2", "B1", "A2"], fr  # match 0: A1vB2, match 1: B1vA2
    assert not plan["bye_placements"]
    assert SEED_MATCH_PLAY_CONFIG["seeding_knockout4"] == "cross_pool"
    # extra pool rows beyond the runner-up are ignored
    assert cross_pool_semi_order([a1, a2, {"player_name": "A3"}],
                                 [b1, b2]) == [a1, b1, a2, b2]
    try:
        cross_pool_semi_order([a1], [b1, b2])
        assert False, "expected ValueError for a 1-advancer pool"
    except ValueError:
        pass


def test_allocate_cents_exact():
    # odd split still sums exactly, spare cent to 1st place
    assert allocate_cents(13500, [71.5, 28.5]) == [9653, 3847]
    assert sum(allocate_cents(99999, [50, 25, 15, 10])) == 99999


if __name__ == "__main__":
    for fn in [test_matrix_parity, test_seed_order, test_bracket_12_byes,
               test_bracket_4_and_2, test_tie_split, test_cross_pool_semis,
               test_allocate_cents_exact]:
        fn()
        print(f"OK  {fn.__name__}")
    print("All Match Play engine tests passed.")
