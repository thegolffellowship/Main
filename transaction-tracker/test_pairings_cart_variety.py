"""R-G cart variety (Pairings Spec v1.2 §11, Kerry 2026-09-30, #1038): two
players who have shared a cart before ride in different carts when they land
in one group again. Soft: the lowest seat term, it only breaks ties."""
import tempfile
from email_parser import database as db

K = db._pair_key_name


def _seat(names, rode=(), tees=None, partner=()):
    return db._arrange_group_seats(list(names), set(), {frozenset(map(K, p)) for p in partner},
                                   tees or {}, rode_before={frozenset(map(K, p)) for p in rode})


def _carts(order):
    return {frozenset(order[:2]), frozenset(order[2:])}


def test_repeat_cart_pair_is_split():
    out = _seat(["Ann A", "Bob B", "Cy C", "Di D"], rode=[("Ann A", "Bob B")])
    assert frozenset(("Ann A", "Bob B")) not in _carts(out)


def test_without_history_seat_order_is_unchanged():
    names = ["Ann A", "Bob B", "Cy C", "Di D"]
    assert _seat(names) == db._arrange_group_seats(names, set(), set(), {})


def test_tee_match_outranks_cart_variety():
    tees = {"Ann A": "Blue", "Bob B": "Blue", "Cy C": "White", "Di D": "White"}
    out = _seat(["Ann A", "Cy C", "Bob B", "Di D"], rode=[("Ann A", "Bob B")], tees=tees)
    assert frozenset(("Ann A", "Bob B")) in _carts(out)   # same tee wins; R-G only a tie-break


def test_partner_request_outranks_cart_variety():
    out = _seat(["Ann A", "Cy C", "Bob B", "Di D"], rode=[("Ann A", "Bob B")], partner=[("Ann A", "Bob B")])
    assert frozenset(("Ann A", "Bob B")) in _carts(out)


def test_rode_counts_rules():
    tmp = tempfile.mktemp(suffix=".db")
    db.init_db(tmp)
    with db._connect(tmp) as c:
        db._ensure_pairing_tables(c)
        c.execute("INSERT INTO events (id, item_name, event_date) VALUES (1, 'a', '2025-05-01')")
        c.execute("INSERT INTO events (id, item_name, event_date) VALUES (2, 'b', '2026-09-01')")
        c.execute("INSERT INTO events (id, item_name, event_date) VALUES (3, 'c', '2099-01-01')")
        rows = [("Ann A", "Bob B", 1, "2025-05-01", 1, "gg_teesheet"),   # last year counts
                ("Ann A", "Bob B", 2, "2026-09-01", 1, "entry"),         # entry seats count
                ("Ann A", "Cy C", 2, "2026-09-01", 0, "gg_teesheet"),    # same group, other cart
                ("Cy C", "Di D", 2, "2026-09-01", 1, "app"),             # app plan: never
                ("Di D", "Ann A", 3, "2099-01-01", 1, "gg_teesheet")]    # not played yet
        for a, b, e, d, rode, src in rows:
            c.execute("INSERT INTO pairing_history (player_a, player_b, event_id, event_date, rode, source) "
                      "VALUES (?,?,?,?,?,?)", (a, b, e, d, rode, src))
        c.commit()
        got = db._rode_counts_from_conn(c)
        assert got == {("ann a", "bob b"): 2}
        assert db._rode_counts_from_conn(c, exclude_event_id=2) == {("ann a", "bob b"): 1}
        assert db.roster_rode_counts(c, 99, ["Ann A", "Bob B", "Di D"]) == {"ann a|bob b": 2}
