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
                     "customer_id INTEGER, transaction_status TEXT, merchant TEXT)")
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
    st = campaigns.campaign_stats(db_path, today="2026-09-03")
    c = st["campaigns"][0]
    f, cost = c["funnel"], c["cost"]
    check("spend source = manual without insights", c["spend_source"] == "manual" and c["spend"] == 127.16, c["spend_source"])
    check("leads = 11 on the campaign", f["leads"] == 11, f)
    check("players = 6 (5 + OldConv), members = 3", (f["players"], f["members"]) == (6, 3), f)
    check("CPL = 127.16 / 11 = 11.56", cost["cpl"] == 11.56, cost)
    check("CPMem = 127.16 / 3 = 42.39 (Kerry's example)", cost["cpmem"] == 42.39, cost)
    check("touched counts touched + converted", f["touched"] == 9, f)
    check("responded = hot tag / human note / converted", f["responded"] == 8, f)
    check("interested = Interested / Coming to event tags", f["interested"] == 1, f)
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
    st = campaigns.campaign_stats(db_path, today="2026-09-03")
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
    st = campaigns.campaign_stats(db_path, today="2026-09-03")
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

    print("Closed window + converted_at stamp")
    st = campaigns.campaign_stats(db_path, today="2026-10-30")
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
    before = campaigns.campaign_stats(db_path, today="2026-09-03")["campaigns"][0]
    with db._connect(db_path) as conn:
        dupe = plant(conn, "DupeOfP1", "San Antonio", "touched", "Texted", META)
        conn.commit()
    mid = campaigns.campaign_stats(db_path, today="2026-09-03")["campaigns"][0]
    check("a second row for the same person counts while it is live",
          mid["funnel"]["leads"] == before["funnel"]["leads"] + 1,
          (before["funnel"]["leads"], mid["funnel"]["leads"]))
    keep = [l for l in leads.get_leads(limit=200, db_path=db_path)
            if l["first_name"] == "P1"][0]["id"]
    leads.merge_leads(keep, dupe, author="test", db_path=db_path)
    after = campaigns.campaign_stats(db_path, today="2026-09-03")["campaigns"][0]
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
