"""Parity tests: season_payouts engine vs the worked matrices in
TGF_Season_Contest_Payouts_v1_0.md (Kerry-ratified 2026-07-06)."""

from email_parser.season_payouts import (
    city_net_payouts, fellowship_cup_payouts, players_cup_payouts)


def test_city_net_san_antonio_n18():
    # SA N=18 -> %paid 28.4% -> 5 places, pot $720:
    # $252.00 / $180.00 / $129.60 / $86.40 / $72.00
    p = city_net_payouts(18)
    assert p["pot_cents"] == 72000
    assert p["amounts_cents"] == [25200, 18000, 12960, 8640, 7200]
    assert sum(p["amounts_cents"]) == p["pot_cents"]


def test_city_net_austin_n9():
    # Austin N=9 -> %paid 30.2% -> 3 places, pot $360: $162 / $108 / $90
    p = city_net_payouts(9)
    assert p["pot_cents"] == 36000
    assert p["amounts_cents"] == [16200, 10800, 9000]
    assert sum(p["amounts_cents"]) == p["pot_cents"]


def test_fellowship_cup_n27():
    # N=27, pot $1,080 -> %paid 14.56% -> 4 places:
    # $486.00 / $270.00 / $189.00 / $135.00
    p = fellowship_cup_payouts(27)
    assert p["pot_cents"] == 108000
    assert p["amounts_cents"] == [48600, 27000, 18900, 13500]
    assert sum(p["amounts_cents"]) == p["pot_cents"]


def test_fellowship_cup_first_flat_45_until_cap():
    # 1st = 45% flat through N=56 (pot $2,240 -> 1st $1,008) ...
    p56 = fellowship_cup_payouts(56)
    assert p56["amounts_cents"][0] == 100800
    # ... past the threshold, +$8 of every new $40 buy-in (20% marginal)
    p57 = fellowship_cup_payouts(57)
    assert p57["amounts_cents"][0] == 100800 + 800
    # 1st never decreases as N grows (universal rule 5)
    prev = 0
    for n in range(3, 120):
        first = fellowship_cup_payouts(n)["amounts_cents"][0]
        assert first >= prev, f"1st dipped at N={n}"
        prev = first


def test_fellowship_cup_pot_always_fully_paid():
    for n in range(3, 120):
        p = fellowship_cup_payouts(n)
        assert sum(p["amounts_cents"]) == p["pot_cents"], f"leak at N={n}"


def test_city_net_pot_always_fully_paid_and_descending():
    for n in range(2, 80):
        p = city_net_payouts(n)
        assert sum(p["amounts_cents"]) == p["pot_cents"], f"leak at N={n}"
        a = p["amounts_cents"]
        assert all(a[i] >= a[i + 1] for i in range(len(a) - 1)), \
            f"ladder not descending at N={n}"


def test_players_cup_n16():
    # N=16, pot $640: Champion $64.00; $144.00/flight -> $96.48 / $47.52
    p = players_cup_payouts(16)
    assert p["pot_cents"] == 64000
    assert p["champion_cents"] == 6400
    assert p["flight_pot_cents"] == 14400
    assert p["flight_first_cents"] == 9648
    assert p["flight_second_cents"] == 4752


def test_zero_and_negative_n():
    assert city_net_payouts(0) is None
    assert fellowship_cup_payouts(0) is None
    assert players_cup_payouts(-1) is None


if __name__ == "__main__":
    import sys
    mod = sys.modules["__main__"]
    fails = 0
    for name in sorted(dir(mod)):
        if name.startswith("test_"):
            try:
                getattr(mod, name)()
                print(f"PASS {name}")
            except AssertionError as e:
                fails += 1
                print(f"FAIL {name}: {e}")
    sys.exit(1 if fails else 0)
