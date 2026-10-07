"""CoS tools 3 + 4 (#1048/#1060): read one post, oldest-first catch-up with
`more`, trimmed bodies, and precedent search. The old reader keeps its shape."""
import os, tempfile
from email_parser import database as db


def _fresh():
    tmp = tempfile.mktemp(suffix=".db")
    db.init_db(tmp)
    with db._connect(tmp) as conn:
        db._ensure_platform_dialogue_table(conn)
        conn.execute("DELETE FROM platform_dialogue")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = 'platform_dialogue'")
        for i in range(1, 8):
            conn.execute("INSERT INTO platform_dialogue (author, topic, body) VALUES (?,?,?)",
                         ("kerry" if i == 3 else "tracker-claude", "front-desk" if i % 2 else "cfo",
                          f"post {i} " + ("Lone Star Cup liabilities " if i == 3 else "") + "x" * 50))
        conn.commit()
    return tmp


def test_one_post_by_id():
    tmp = _fresh()
    r = db.read_platform_dialogue_v2(post_id=3, db_path=tmp)
    assert [p["id"] for p in r["posts"]] == [3] and r["more"] is False


def test_since_id_is_oldest_first_with_more():
    tmp = _fresh()
    r = db.read_platform_dialogue_v2(3, since_id=2, db_path=tmp)
    assert [p["id"] for p in r["posts"]] == [3, 4, 5]
    assert r["more"] is True and r["next_since_id"] == 5 and r["order"] == "oldest-first"
    r2 = db.read_platform_dialogue_v2(3, since_id=r["next_since_id"], db_path=tmp)
    assert [p["id"] for p in r2["posts"]] == [6, 7] and r2["more"] is False


def test_newest_first_without_since_id():
    tmp = _fresh()
    r = db.read_platform_dialogue_v2(2, db_path=tmp)
    assert [p["id"] for p in r["posts"]] == [7, 6] and r["more"] is True


def test_max_chars_trims_and_points_to_id():
    tmp = _fresh()
    r = db.read_platform_dialogue_v2(1, post_id=4, max_chars=10, db_path=tmp)
    assert r["posts"][0]["body"].startswith("post 4 xxx") and "post_id=4" in r["posts"][0]["body"]


def test_search_text_author_case_insensitive():
    tmp = _fresh()
    r = db.read_platform_dialogue_v2(text="lone STAR cup", db_path=tmp)
    assert [p["id"] for p in r["posts"]] == [3]
    r = db.read_platform_dialogue_v2(author="KERRY", db_path=tmp)
    assert [p["id"] for p in r["posts"]] == [3]
    r = db.read_platform_dialogue_v2(topic="CFO", db_path=tmp)
    assert {p["id"] for p in r["posts"]} == {2, 4, 6}


def test_old_reader_unchanged():
    tmp = _fresh()
    rows = db.read_platform_dialogue_entries(5, "front-desk", 0, db_path=tmp)
    assert [r["id"] for r in rows] == [7, 5, 3, 1]
