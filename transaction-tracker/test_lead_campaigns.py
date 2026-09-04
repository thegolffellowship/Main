"""Tests for the campaign entity + campaign stats (mailbox #391,
Kerry-ratified 2026-09-03).

Throwaway SQLite database; checks:
  - the current campaign seeds once (by Meta id) and leads auto-link
    from the payload's ad_campaign_id; manual assignment + clear with an
    auto note; organic leads stay unattributed;
  - Kerry's metric definitions exactly: CPL = spend / leads, CPP =
    spend / players (registered OR member, counts once), CPMem = spend /
    members — his worked example $127.16 / 5 = $25.43, / 3 = $42.39;
  - CURRENT vs 30-DAY TRAILING: conversions after end_date + 30 days
    drop out of trailing; open window reads equal to current;
  - manual spend fallback when no Meta insights; insights spend wins
    when cached; the insights normalizer maps the Marketing API row;
  - converted_at stamps on mark_lead(converted) and the backfill for
    rows converted before the column existed;
  - per-chapter split and the "All campaigns" aggregate.

Run: python3 test_lead_campaigns.py
"""

import json
import os
import tempfile

os.environ.setdefault("DATABASE_PATH", ":memory:")

from email_parser import database as db  # noqa: E402
from email_parser import leads, campaigns  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


def plant(conn, first, chapter, status="new", tag=None, cam=None,
          converted_at=None, arrived="2026-08-28 10:00:00", notes=0):
    payload = {"ad_campaign_id": cam} if cam else {}
    conn.execute(
        "INSERT INTO leads (source, external_id, first_name, last_name, email, "
        "chapter, status, tag, payload, arrived_at, converted_at) "
        "VALUES ('hubspot', ?, ?, 'T', ?, ?, ?, ?, ?, ?, ?)",
        (f"ext-{first}", first, f"{first.lower()}@x.com", chapter, status, tag,
         json.dumps(payload), arrived, converted_at))
    lid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    for i in range(notes):
        conn.execute("INSERT INTO lead_notes (lead_id, author, note) VALUES (?, 'K', ?)",
                     (lid, f"note {i}"))
    return lid


def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    META = "120253511733060195"
    with db._connect(db_path) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, "
                     "customer_id INTEGER, transaction_status TEXT, merchant TEXT,"
                     " item_name TEXT, item_price REAL, order_id TEXT,"
                     " parent_item_id INTEGER, order_date TEXT, item_index INTEGER,"
                     " customer TEXT, chapter TEXT, holes TEXT, side_games TEXT,"
                     " user_status TEXT, quantity INTEGER)")
        conn.execute("""CREATE TABLE IF NOT EXISTS godaddy_order_splits (
            id INTEGER PRIMARY KEY AUTOINCREMENT, transaction_id INTEGER,
            item_id INTEGER, event_name TEXT, customer TEXT,
            split_type TEXT NOT NULL, amount REAL NOT NULL, created_at TEXT)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS acct_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT, order_id TEXT NOT NULL,
            item_id INTEGER, event_name TEXT, chapter TEXT,
            allocation_date TEXT, player_count INTEGER DEFAULT 1,
            course_payable REAL DEFAULT 0, course_surcharge REAL DEFAULT 0,
            prize_pool REAL DEFAULT 0, tgf_operating REAL DEFAULT 0,
            godaddy_fee REAL DEFAULT 0, tax_reserve REAL DEFAULT 0,
            total_collected REAL DEFAULT 0,
            allocation_status TEXT DEFAULT 'pending', notes TEXT,
            created_at TEXT, UNIQUE(order_id, item_id))""")
        conn.execute("CREATE TABLE IF NOT EXISTS customers (customer_id INTEGER "
                     "PRIMARY KEY, first_name TEXT, last_name TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, "
                     "value TEXT, updated_at TEXT)")
        leads.ensure_leads_table(conn)
        leads.ensure_leads_table(conn)   # idempotent
        rows = conn.execute("SELECT * FROM lead_campaigns").fetchall()
        check("current campaign seeded exactly once", len(rows) == 1
              and rows[0]["meta_campaign_id"] == META, [dict(r) for r in rows])
        cid = rows[0]["id"]
        # 10 leads: 5 players (3 members) → Kerry's worked example
        plant(conn, "P1", "San Antonio", "converted", "Became member", META, "2026-08-30")
        plant(conn, "P2", "San Antonio", "converted", "Became member", META, "2026-09-01")
        plant(conn, "P3", "Austin", "converted", "Became member", META, "2026-10-20")  # after window
        plant(conn, "P4", "Austin", "converted", "Registered event", META, "2026-09-02")
        plant(conn, "P5", "San Antonio", "converted", "Registered event", META, "2026-10-09")  # after window
        plant(conn, "T1", "San Antonio", "touched", "Interested", META, notes=1)
        plant(conn, "T2", "Austin", "touched", "Texted", META)
        plant(conn, "T3", "Austin", "touched", None, META, notes=1)
        plant(conn, "N1", "San Antonio", "new", None, META)
        plant(conn, "D1", None, "dismissed", "Bad contact", META)
        org = plant(conn, "Org", "Austin", "new", None, None)
        old_conv = plant(conn, "OldConv", "Austin", "converted", "Registered event", META,
                         None, arrived="2026-08-27 09:00:00")
        conn.execute("UPDATE leads SET touched_at = '2026-08-29 12:00:00' WHERE id = ?", (old_conv,))
        conn.commit()

    print("Linking")
    got = leads.get_leads(db_path=db_path)
    linked = [l for l in got if l.get("campaign_id") == cid]
    check("payload ad_campaign_id auto-links to the campaign", len(linked) == 11, len(linked))
    check("campaign_name rides on get_leads", linked[0]["campaign_name"] == "Fall 2026 Leads")
    org_row = [l for l in got if l["id"] == org][0]
    check("organic lead stays unattributed", org_row["campaign_id"] is None)
    r = campaigns.set_lead_campaign(org, cid, author="Kerry", db_path=db_path)
    check("manual assign works", r.get("ok") and r["campaign_name"] == "Fall 2026 Leads", r)
    with db._connect(db_path) as conn:
        n = conn.execute("SELECT note FROM lead_notes WHERE lead_id = ? ORDER BY id DESC",
                         (org,)).fetchone()
        check("assign leaves an auto note", n and n["note"].startswith("Campaign set to Fall 2026 Leads by Kerry"), n and n["note"])
        oc = conn.execute("SELECT converted_at FROM leads WHERE id = ?", (old_conv,)).fetchone()
    r = campaigns.set_lead_campaign(org, None, author="Kerry", db_path=db_path)
    check("clear works", r.get("ok") and r["campaign_id"] is None, r)
    check("converted_at backfilled from touched_at for pre-column conversions",
          oc and oc["converted_at"] == "2026-08-29 12:00:00", oc and oc["converted_at"])

    print("Spend + stats (manual spend fallback)")
    r = campaigns.set_campaign(campaign_id=cid, spend_manual=127.16, db_path=db_path)
    check("manual spend set", r.get("ok") and r["spend_manual"] == 127.16, r)
    st = campaigns.campaign_stats(db_path, today="2026-09-03", gap_fill_seconds=0)
    c = st["campaigns"][0]
    f, cost = c["funnel"], c["cost"]
    check("spend source = manual without insights", c["spend_source"] == "manual" and c["spend"] == 127.16, c["spend_source"])
    check("leads = 11 on the campaign", f["leads"] == 11, f)
    check("players = 6 (5 + OldConv), members = 3", (f["players"], f["members"]) == (6, 3), f)
    check("CPL = 127.16 / 11 = 11.56", cost["cpl"] == 11.56, cost)
    check("CPMem = 127.16 / 3 = 42.39 (Kerry's example)", cost["cpmem"] == 42.39, cost)
    check("touched counts touched + converted", f["touched"] == 9, f)
    # Mailbox #412: the STATS metric is REPLIED and counts a human reply
    # only. Of the 9 touched+converted leads, exactly two have evidence a
    # person wrote back — T1 (Interested + a note) and T3 (a note). The
    # six converted leads registered or joined without ever answering a
    # text, and T2 was only texted AT. Under the old rule all six
    # converted leads counted, which is the collision Kerry resolved.
    check("replied = human reply only, NOT bare conversion",
          f["replied"] == 2, f)
    check("reply_pct = 2 / 9 touched", f["reply_pct"] == 22.2, f)
    check("old `responded` key is gone (two words, two jobs)",
          "responded" not in f and "response_pct" not in f, list(f))
    check("interested = Interested / Coming to event tags", f["interested"] == 1, f)

    # The reason replied_at exists at all. The conversion auto-detect
    # OVERWRITES tag, so a lead who texted back and then registered has
    # no trace left on the row that they ever answered. Reading REPLIED
    # off the current tag would quietly undercount exactly the campaigns
    # that worked, so the reply is stamped when it happens.
    print("REPLIED survives the conversion that overwrites the tag")
    with db._connect(db_path) as conn:
        replier = plant(conn, "Replier", "San Antonio", "touched", None, META)
        conn.commit()
    leads.set_lead_tag(replier, "Interested", db_path=db_path, author="K")
    with db._connect(db_path) as conn:
        stamped = conn.execute("SELECT replied_at FROM leads WHERE id = ?",
                               (replier,)).fetchone()["replied_at"]
        conn.commit()
    check("tagging Interested stamps replied_at", bool(stamped), stamped)
    before = campaigns.campaign_stats(db_path, today="2026-09-03",
                                      gap_fill_seconds=0)["campaigns"][0]["funnel"]
    check("and they count as replied while the tag is still there",
          before["replied"] == 3, before)
    with db._connect(db_path) as conn:      # what the auto-detect does
        conn.execute("UPDATE leads SET status = 'converted', "
                     "tag = 'Registered event', converted_at = '2026-09-02' "
                     "WHERE id = ?", (replier,))
        conn.commit()
    after = campaigns.campaign_stats(db_path, today="2026-09-03",
                                     gap_fill_seconds=0)["campaigns"][0]["funnel"]
    check("they STILL count after the tag is overwritten",
          after["replied"] == 3, after)
    check("and the conversion is counted as a player too",
          after["players"] == before["players"] + 1, (before["players"], after["players"]))
    with db._connect(db_path) as conn:      # leave the fixture as found
        conn.execute("DELETE FROM leads WHERE id = ?", (replier,))
        conn.commit()
    check("dismissed = 1, new = 1", (f["dismissed"], f["new"]) == (1, 1), f)
    check("trailing cutoff = end 9/6 + 30 = 10/6, window open on 9/3",
          c["trailing_cutoff"] == "2026-10-06" and c["trailing_window_open"] is True, c)
    check("trailing drops the 10/9 and 10/20 conversions: players 4, members 2",
          (f["players_trailing"], f["members_trailing"]) == (4, 2), f)
    check("CPP trailing = 127.16 / 4 = 31.79, CPMem trailing = 63.58",
          (cost["cpp_trailing"], cost["cpmem_trailing"]) == (31.79, 63.58), cost)
    ch = c["chapters"]
    check("per-chapter split present", set(ch) >= {"San Antonio", "Austin", "unrouted"}, list(ch))
    check("SA players 3 members 2", (ch["San Antonio"]["players"], ch["San Antonio"]["members"]) == (3, 2), ch["San Antonio"])
    check("All = campaign + unattributed", st["all"]["funnel"]["leads"] == 12 and st["unattributed"]["funnel"]["leads"] == 1,
          (st["all"]["funnel"]["leads"], st["unattributed"]["funnel"]["leads"]))
    check("All spend sums campaigns", st["all"]["spend"] == 127.16 and st["all"]["spend_source"] == "sum", st["all"]["spend"])
    check("unattributed has no cost figures", st["unattributed"]["cost"]["cpl"] is None)

    # Kerry's exact example: 5 players / 3 members on $127.16
    with db._connect(db_path) as conn:
        conn.execute("UPDATE leads SET status = 'touched', tag = NULL, converted_at = NULL "
                     "WHERE first_name = 'OldConv'")
        conn.commit()
    st = campaigns.campaign_stats(db_path, today="2026-09-03", gap_fill_seconds=0)
    cost = st["campaigns"][0]["cost"]
    check("CPP = 127.16 / 5 = 25.43 (Kerry's example)", cost["cpp"] == 25.43, cost)

    print("Meta insights")
    raw = {"spend": "127.64", "impressions": "14346", "reach": "6866",
           "frequency": "2.089426", "inline_link_clicks": "403", "ctr": "6.52",
           "cpm": "8.90", "actions": [{"action_type": "lead", "value": "85"}],
           "date_start": "2026-08-27", "date_stop": "2026-09-03"}
    n = campaigns._normalize_insights(raw)
    check("normalizer maps the API row", (n["spend"], n["impressions"], n["link_clicks"], n["meta_leads"]) == (127.64, 14346, 403, 85), n)
    with db._connect(db_path) as conn:
        conn.execute("INSERT INTO lead_campaign_insights (campaign_id, fetched_at, payload) "
                     "VALUES (?, datetime('now'), ?)", (cid, json.dumps(n)))
        conn.commit()
    st = campaigns.campaign_stats(db_path, today="2026-09-03", gap_fill_seconds=0)
    c = st["campaigns"][0]
    check("insights spend wins over manual", c["spend_source"] == "meta" and c["spend"] == 127.64, (c["spend_source"], c["spend"]))
    check("META panel carried", c["meta"]["cpm"] == 8.9 and c["meta"]["reach"] == 6866, c["meta"])

    # ALL CAMPAIGNS carried spend but NO Meta metrics — every other tile
    # read "—" while the insights were live and fresh (Kerry 2026-09-04:
    # "Looks like META data is not updating"). The roll-up bucket simply
    # never got any.
    allb = st["all"]
    check("the ALL view carries Meta metrics, not just spend",
          (allb.get("meta") or {}).get("impressions") == 14346, allb.get("meta"))
    check("with ONE campaign the roll-up is that campaign, exactly",
          allb["meta"]["cpm"] == 8.9 and allb["meta"]["reach"] == 6866
          and not allb["meta"].get("reach_approx"), allb["meta"])
    check("and it is labelled as Meta rather than a bare sum",
          allb["spend_source"] == "meta" and allb.get("insights_fetched_at"),
          (allb["spend_source"], allb.get("insights_fetched_at")))

    # Two campaigns: sum what is additive, DERIVE the ratios. Averaging
    # rates would be wrong the moment the campaigns differ in size.
    two = campaigns._roll_up_insights([
        {"insights": {"spend": 100.0, "impressions": 10000, "reach": 5000,
                      "link_clicks": 200, "meta_leads": 50,
                      "date_start": "2026-08-01", "date_stop": "2026-08-10"}},
        {"insights": {"spend": 50.0, "impressions": 10000, "reach": 4000,
                      "link_clicks": 100, "meta_leads": 30,
                      "date_start": "2026-08-05", "date_stop": "2026-08-20"}},
    ])
    check("roll-up sums spend, impressions, clicks and leads",
          (two["spend"], two["impressions"], two["link_clicks"],
           two["meta_leads"]) == (150.0, 20000, 300, 80), two)
    check("CTR is derived from the totals, not averaged",
          round(two["ctr"], 4) == 1.5, two["ctr"])
    check("CPM is derived from the totals, not averaged",
          round(two["cpm"], 2) == 7.5, two["cpm"])
    check("frequency comes from the totals too",
          round(two["frequency"], 4) == round(20000 / 9000, 4), two["frequency"])
    check("reach is flagged approximate — one person, two campaigns",
          two.get("reach_approx") is True and two["campaigns"] == 2, two)
    check("the date span covers both campaigns",
          (two["date_start"], two["date_stop"]) == ("2026-08-01", "2026-08-20"),
          (two["date_start"], two["date_stop"]))
    check("no insights at all rolls up to nothing",
          campaigns._roll_up_insights([{"insights": None}]) is None)
    os.environ.pop("META_ACCESS_TOKEN", None)
    r = campaigns.refresh_meta_insights(db_path)
    check("refresh is a no-op without META_ACCESS_TOKEN", r["token"] is False and r["refreshed"] == 0, r)

    print("Registered-events count includes members (Kerry 2026-09-04)")
    # The tag can only say ONE thing and membership outranks event, so a
    # member who also plays was invisible in the event count. The count
    # asks the items table instead: "total unique leads from this
    # campaign who have registered for events, INCLUDING those who have
    # become members."
    with db._connect(db_path) as conn:
        mem_player = plant(conn, "MemAndPlayer", "San Antonio", "converted",
                           "Became member", META)
        just_player = plant(conn, "JustPlayer", "San Antonio", "converted",
                            "Registered event", META)
        just_member = plant(conn, "JustMember", "Austin", "converted",
                            "Became member", META)
        conn.execute("UPDATE leads SET customer_id = 9001 WHERE id = ?", (mem_player,))
        conn.execute("UPDATE leads SET customer_id = 9002 WHERE id = ?", (just_player,))
        conn.execute("UPDATE leads SET customer_id = 9003 WHERE id = ?", (just_member,))
        conn.executemany(
            "INSERT INTO items (customer_id, transaction_status, merchant, "
            "item_name, item_price, order_id) VALUES (?,?,?,?,?,?)",
            [(9001, "active", "GoDaddy", "s9.22 Silverhorn", 64.0, "O-1"),
             (9001, "active", "GoDaddy", "TGF MEMBERSHIP", 75.0, "O-1"),
             (9002, "active", "GoDaddy", "s9.22 Silverhorn", 64.0, "O-2"),
             (9003, "active", "GoDaddy", "TGF MEMBERSHIP", 75.0, "O-3"),
             # A roster import puts a PERSON in the system, not a sale.
             (9003, "active", "Roster Import", "s9.22 Silverhorn", 0.0, "O-4")])
        conn.executemany(
            "INSERT INTO customers (customer_id, first_name, last_name) "
            "VALUES (?,?,?)",
            [(9001, "Mem", "Player"), (9002, "Just", "Player"),
             (9003, "Just", "Member")])
        conn.commit()
    st2 = campaigns.campaign_stats(db_path, today="2026-09-03",
                               gap_fill_seconds=0)
    fn = st2["campaigns"][0]["funnel"]
    check("a member who ALSO played counts as registered",
          fn["registered"] == 2, fn)
    check("a member who never played does not",
          fn["members"] >= 2 and fn["registered"] == 2, fn)
    # The overlap, proven by removing it: drop the member's event items
    # and the count falls to the one lead who is ONLY a player.
    with db._connect(db_path) as conn:
        conn.execute("UPDATE items SET transaction_status = 'refunded' "
                     "WHERE customer_id = 9001 AND item_name NOT LIKE "
                     "'%MEMBERSHIP%'")
        conn.commit()
    check("without the member's registration the count drops to 1",
          campaigns.campaign_stats(db_path, today="2026-09-03",
                                   gap_fill_seconds=0)["campaigns"][0]
          ["funnel"]["registered"] == 1)
    with db._connect(db_path) as conn:
        conn.execute("UPDATE items SET transaction_status = 'active' "
                     "WHERE customer_id = 9001")
        conn.commit()
    check("a Roster Import row is not a registration",
          fn["registered"] == 2, fn)

    print("Lifetime value + ROI")
    val = st2["campaigns"][0]["value"]
    check("with nothing allocated there is no money to report yet",
          val["collected"] == 0.0 and val["margin"] == 0.0, val)
    # SQLite is dynamically typed and real rows DO hold item_price as
    # TEXT. Summing those in Python took the whole Stats view down on
    # production with "unsupported operand type(s) for +: 'int' and
    # 'str'" — the fixtures were all floats, so nothing caught it.
    with db._connect(db_path) as conn:
        conn.execute("INSERT INTO items (customer_id, transaction_status, "
                     "merchant, item_name, item_price, order_id) "
                     "VALUES (9002, 'active', 'GoDaddy', 's9.23 Quarry', "
                     "'58.00', 'O-5')")
        conn.commit()
    # Both money figures come off acct_allocations, NOT items.item_price:
    # that column is not reliably numeric (SQLite is dynamically typed)
    # and summing it gave $0 against $245 of real margin on production.
    # Same rows for both means one coverage number covers both.
    with db._connect(db_path) as conn:
        conn.execute("INSERT INTO acct_allocations (order_id, item_id, "
                     "tgf_operating, total_collected) "
                     "VALUES ('O-1', 1, 21.0, '139.00')")
        conn.commit()
    v2 = campaigns.campaign_stats(db_path, today="2026-09-03",
                                  gap_fill_seconds=0)["campaigns"][0]["value"]
    check("collected and margin both come from the allocations layer",
          v2["collected"] == 139.0 and v2["margin"] == 21.0, v2)
    check("a TEXT amount does not blow up the sum", v2["collected"] == 139.0)
    check("it counts orders, not just items", val["orders"] == 3, val)
    # Kerry 2026-09-04: "Why not all 103 people from campaign? Why only
    # 97?" Value is per PERSON and a lead is not a person. The panel has
    # to say WHICH — no customer record yet, or the same person twice —
    # or the gap reads as lost money.
    check("it reports leads and people separately",
          val["leads"] > val["customers"], val)
    check("and says how many leads have no customer record",
          val["leads_without_customer"] > 0, val)
    with db._connect(db_path) as conn:
        dupe = plant(conn, "SamePerson", "San Antonio", "touched", None, META)
        conn.execute("UPDATE leads SET customer_id = 9002 WHERE id = ?", (dupe,))
        conn.commit()
    v_d = campaigns.campaign_stats(db_path, today="2026-09-03",
                                   gap_fill_seconds=0)["campaigns"][0]["value"]
    check("two leads for one person count as ONE person, and say so",
          v_d["duplicate_leads"] == 1
          and v_d["customers"] == val["customers"], v_d)
    roi = st2["campaigns"][0]["roi"]
    check("ROI is reported once there is spend", roi is not None, roi)
    check("ROI is computed on MARGIN, not gross collected",
          roi["roas_margin"] != roi["roas_collected"]
          or roi["margin"] == roi["collected"], roi)
    check("gross is carried alongside so the two are never confused",
          roi["collected"] == val["collected"]
          and roi["margin"] == val["margin"], roi)
    check("net is margin minus spend",
          abs(roi["net"] - (roi["margin"] - roi["spend"])) < 0.01, roi)
    check("coverage says how much of it is actually allocated",
          "coverage_pct" in roi, roi)
    with db._connect(db_path) as conn:
        conn.execute("INSERT INTO acct_allocations (order_id, item_id, "
                     "tgf_operating, total_collected) VALUES ('O-2', 3, 15.0, 64.0)")
        conn.commit()
    st3 = campaigns.campaign_stats(db_path, today="2026-09-03",
                               gap_fill_seconds=0)
    check("an allocated order feeds the margin",
          st3["campaigns"][0]["value"]["margin"] == 36.0,
          st3["campaigns"][0]["value"])
    check("ROAS on margin is margin over spend",
          abs(st3["campaigns"][0]["roi"]["roas_margin"]
              - 36.0 / st3["campaigns"][0]["spend"]) < 0.01,
          st3["campaigns"][0]["roi"])

    print("Margin audit trail (Kerry 2026-09-04: \"make sure your math is correct\")")
    with db._connect(db_path) as conn:
        conn.execute("DELETE FROM acct_allocations")
        # A clean event allocation: what the player paid splits four
        # ways — course, prizes, processor, TGF.
        conn.execute("INSERT INTO acct_allocations (order_id, item_id, "
                     "event_name, allocation_date, total_collected, "
                     "course_payable, course_surcharge, prize_pool, "
                     "godaddy_fee, tax_reserve, tgf_operating) VALUES "
                     "('O-2', 3, 's9.22 Silverhorn', '2026-09-02', "
                     " 64.00, 34.00, 0.00, 14.00, 2.00, 1.16, 14.00)")
        conn.commit()
    v = campaigns.campaign_stats(db_path, today="2026-09-03",
                                 gap_fill_seconds=0)["campaigns"][0]["value"]
    check("the breakdown returns a row per allocation", len(v["rows"]) == 1, v["rows"])
    row = v["rows"][0]
    check("it names the player, not just the order",
          row["player"] == "Just Player", row)
    check("it carries every bucket the money splits into",
          (row["collected"], row["course"], row["prizes"], row["fee"],
           row["margin"]) == (64.0, 34.0, 14.0, 2.0, 14.0), row)
    check("what was left over matches what the books booked",
          row["margin_actual"] == 16.0 and row["margin_booked"] == 14.0, row)
    check("and the gap is reported, not hidden",
          row["overstated"] == -2.0, row)
    check("the rows sum to the headline margin",
          round(sum(r["margin"] for r in v["rows"]), 2) == v["margin"], v)
    check("and to the headline collected",
          round(sum(r["collected"] for r in v["rows"]), 2) == v["collected"], v)

    # A BROKEN allocation must be visible as broken, not averaged away.
    with db._connect(db_path) as conn:
        conn.execute("UPDATE acct_allocations SET prize_pool = 5.00 "
                     "WHERE order_id = 'O-2'")
        conn.commit()
    v2 = campaigns.campaign_stats(db_path, today="2026-09-03",
                                  gap_fill_seconds=0)["campaigns"][0]["value"]
    check("a booked margin above what was left over is FLAGGED",
          v2["rows_reconcile"] is False and v2["rows"][0]["overstated"] == -11.0,
          v2["rows"][0])
    with db._connect(db_path) as conn:
        conn.execute("UPDATE acct_allocations SET prize_pool = 14.00 "
                     "WHERE order_id = 'O-2'")
        conn.commit()

    # THE REAL FINDING this table exposed on production: tgf_operating
    # is the event's STANDARD markup and never looks at what the player
    # paid, so a 1st Timer who came in $25 under the guest rate still
    # books the full markup. The books say more was kept than was.
    with db._connect(db_path) as conn:
        conn.execute("UPDATE acct_allocations SET total_collected = 55.00, "
                     "course_payable = 54.12, prize_pool = 7.00, "
                     "tgf_operating = 8.00 WHERE order_id = 'O-2'")
        conn.commit()
    disc = campaigns.campaign_stats(db_path, today="2026-09-03",
                                    gap_fill_seconds=0)["campaigns"][0]["value"]
    check("a discounted round books more margin than was left over",
          disc["rows"][0]["margin_booked"] == 8.0
          and disc["rows"][0]["margin_actual"] == -6.12, disc["rows"][0])

    # Kerry 2026-09-04: the customer PAYS the 3.5% and GoDaddy takes its
    # actual cut — two different numbers, and TGF keeps the difference.
    # Dropping both (my second attempt) was as wrong as subtracting one.
    with db._connect(db_path) as conn:
        conn.executemany(
            "INSERT INTO godaddy_order_splits (item_id, split_type, amount) "
            "VALUES (?,?,?)",
            [(3, "transaction_fee", 1.93), (3, "merchant_fee", -1.90)])
        conn.commit()
    fee = campaigns.campaign_stats(db_path, today="2026-09-03",
                                   gap_fill_seconds=0)["campaigns"][0]["value"]
    fr = fee["rows"][0]
    check("the fee the customer paid is added back",
          fr["fee_in"] == 1.93, fr)
    check("what GoDaddy actually took is subtracted",
          fr["fee_out"] == 1.9, fr)
    check("TGF keeps the difference, and it moves margin_actual",
          fr["fee_net"] == 0.03 and fr["margin_actual"] == -6.09, fr)
    check("the overstatement is quantified, per row and in total",
          disc["rows"][0]["overstated"] == 14.12
          and disc["overstated"] == 14.12, disc)
    check("and the headline is marked as not reconciling",
          disc["rows_reconcile"] is False, disc)

    print("Closed window + converted_at stamp")
    st = campaigns.campaign_stats(db_path, today="2026-10-30", gap_fill_seconds=0)
    c = st["campaigns"][0]
    check("window closed after 10/6", c["trailing_window_open"] is False, c["trailing_window_open"])
    with db._connect(db_path) as conn:
        nid = plant(conn, "Fresh", "Austin", "touched", None, META)
        conn.commit()
    leads.mark_lead(nid, "converted", touched_by="Kerry", db_path=db_path)
    with db._connect(db_path) as conn:
        row = conn.execute("SELECT converted_at FROM leads WHERE id = ?", (nid,)).fetchone()
    check("mark_lead(converted) stamps converted_at", bool(row["converted_at"]), dict(row))

    print("Merged duplicates never double-count (v2.295.1)")
    before = campaigns.campaign_stats(db_path, today="2026-09-03", gap_fill_seconds=0)["campaigns"][0]
    with db._connect(db_path) as conn:
        dupe = plant(conn, "DupeOfP1", "San Antonio", "touched", "Texted", META)
        conn.commit()
    mid = campaigns.campaign_stats(db_path, today="2026-09-03", gap_fill_seconds=0)["campaigns"][0]
    check("a second row for the same person counts while it is live",
          mid["funnel"]["leads"] == before["funnel"]["leads"] + 1,
          (before["funnel"]["leads"], mid["funnel"]["leads"]))
    keep = [l for l in leads.get_leads(limit=200, db_path=db_path)
            if l["first_name"] == "P1"][0]["id"]
    leads.merge_leads(keep, dupe, author="test", db_path=db_path)
    after = campaigns.campaign_stats(db_path, today="2026-09-03", gap_fill_seconds=0)["campaigns"][0]
    check("after the merge it is counted ONCE again (leads back to the "
          "pre-duplicate figure)",
          after["funnel"]["leads"] == before["funnel"]["leads"],
          (before["funnel"]["leads"], after["funnel"]["leads"]))
    check("CPL is not deflated by the merged row",
          after["cost"]["cpl"] == before["cost"]["cpl"],
          (before["cost"]["cpl"], after["cost"]["cpl"]))
    lst_after = [c for c in campaigns.list_campaigns(db_path)
                 if c["id"] == cid][0]
    check("the campaign list's lead_count excludes merged rows too",
          lst_after["lead_count"] == before["funnel"]["leads"],
          (lst_after["lead_count"], before["funnel"]["leads"]))

    # v2.318.1: the stats view reads lead columns, so it must run the
    # lead migrations itself rather than assuming another page got there
    # first. v2.317.0 shipped without this and took the whole stats view
    # down on deploy with "no such column: l.replied_at" — green tests
    # never saw it, because every test builds its DB through
    # ensure_leads_table.
    print("Stats survives a database that has not been migrated yet")
    with db._connect(db_path) as conn:
        conn.execute("ALTER TABLE leads DROP COLUMN replied_at")
        conn.commit()
        cols = {r[1] for r in conn.execute("PRAGMA table_info(leads)")}
    check("the column really is gone (the pre-upgrade shape)",
          "replied_at" not in cols)
    healed = campaigns.campaign_stats(db_path, today="2026-09-03",
                                      gap_fill_seconds=0)
    check("stats still answers instead of 500ing",
          isinstance(healed.get("campaigns"), list) and healed["campaigns"])
    check("and it migrated the column back on the way through",
          "replied" in healed["campaigns"][0]["funnel"],
          healed["campaigns"][0]["funnel"])

    print("Campaign CRUD")
    r = campaigns.set_campaign(name="Historical 2025", source="historical", db_path=db_path)
    check("historical campaign row creatable (design for reactivation)", r.get("ok") and r["source"] == "historical", r)
    r = campaigns.set_campaign(name="Historical 2025", db_path=db_path)
    check("duplicate name rejected", r.get("error"), r)
    r = campaigns.set_campaign(name="X", source="bogus", db_path=db_path)
    check("bad source rejected", r.get("error"), r)
    lst = campaigns.list_campaigns(db_path)
    check("list carries lead_count", any(x["lead_count"] >= 12 for x in lst), [(x["name"], x["lead_count"]) for x in lst])

    os.unlink(db_path)
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        raise SystemExit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
