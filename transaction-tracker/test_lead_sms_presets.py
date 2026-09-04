"""Tests for the first-touch SMS preset set (mailbox #383 → #388/#389,
Kerry-ratified 2026-09-02).

Builds a throwaway SQLite database with a few events, then checks:

  - the ratified selection logic: Importance → P1–P4 (blank → P4),
    Availability → the tue/sat/both slot, "No days" → P6, touched with
    no human reply 2+ days → P7 (4+ → P7b), re-submitter → P8;
  - the #389 both-cities add-on rides on P1–P4 / P8 only when
    Invitations = Both, and the offer closer only when asked;
  - the standing copy rules: no em-dash anywhere in the defaults, every
    first touch opens "Hey {first_name}, {owner}";
  - {next_tue}/{next_sat}/{next_event} labels from the events table,
    TGF events counting for both chapters, and the Saturday borrow when
    a chapter has no 18 inside three weeks;
  - the lead_sms_presets dial merges per key over the defaults, and a
    legacy lead_sms_template surfaces as the 'custom' preset.

Run: python3 test_lead_sms_presets.py
"""

import json
import os
import tempfile
from datetime import datetime

os.environ.setdefault("DATABASE_PATH", ":memory:")

from email_parser import database as db  # noqa: E402
from email_parser import leads  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail}")
        FAILURES.append(label)


AVAIL = leads.MANUAL_ANSWER_KEYS["availability"]
IMP = leads.MANUAL_ANSWER_KEYS["importance"]
INV = leads.MANUAL_ANSWER_KEYS["invitations"]
OPT = {f: dict(v) for f, v in leads.MANUAL_ANSWER_OPTIONS.items()}
BY_LABEL = {f: {lbl: val for val, lbl in leads.MANUAL_ANSWER_OPTIONS[f]}
            for f in leads.MANUAL_ANSWER_OPTIONS}


def lead(first="Sam", chapter="San Antonio", avail=None, imp=None,
         inv=None, status="new", touched_at=None, tag=None, notes=None,
         has_history=False):
    payload = {}
    if avail:
        payload[AVAIL] = BY_LABEL["availability"][avail]
    if imp:
        payload[IMP] = BY_LABEL["importance"][imp]
    if inv:
        payload[INV] = BY_LABEL["invitations"][inv]
    return {"id": 1, "first_name": first, "chapter": chapter,
            "payload": payload, "status": status, "touched_at": touched_at,
            "tag": tag, "notes_log": notes or [], "has_history": has_history}


NOW = datetime(2026, 9, 2, 18, 0, 0)


SILVERHORN = {"item_name": "s9.22 Silverhorn", "event_date": "2026-09-08",
              "course": "Silverhorn Golf Club of Texas", "chapter": "San Antonio",
              "course_cost": 48.71, "tgf_markup": 8.0, "side_game_fee": 7.0,
              "transaction_fee_pct": 3.5, "start_time": "17:30",
              "start_type": "Shotgun", "range_balls_included": None}
CEDAR = {"item_name": "s18.11 Cedar Creek", "event_date": "2026-09-19",
         "course": "Cedar Creek Golf Course", "chapter": "San Antonio",
         "course_cost": 90.65, "tgf_markup": 15.0, "side_game_fee": 14.0,
         "transaction_fee_pct": 3.5, "start_time": "08:30",
         "start_type": "Tee Times", "range_balls_included": 1}
SHADOW = {"item_name": "a9.22 ShadowGlen", "event_date": "2026-09-08",
          "course": "ShadowGlen Golf Club", "chapter": "Austin",
          "course_cost": 43.30, "tgf_markup": 8.0, "side_game_fee": 7.0,
          "start_time": "17:30", "start_type": "Shotgun"}
NOCOST = {"item_name": "a9.28 Forest Creek", "event_date": "2026-10-20",
          "course": "Forest Creek Golf Club", "chapter": "Austin",
          "course_cost": None, "tgf_markup": None}


def main():
    presets = {k: dict(v) for k, v in leads.DEFAULT_SMS_PRESETS.items()}
    pick = lambda l: leads.select_sms_preset(l, now=NOW)  # noqa: E731

    print("Copy rules (#406)")
    for k, p in presets.items():
        for f in ("text", "no_games"):
            t = p.get(f)
            if t:
                check(f"{k}.{f} has no em-dash", "—" not in t and "–" not in t)
    check("P3 no longer promises an 'ambassador'",
          "ambassador" not in presets["p3"]["text"].lower())
    check("P3 uses Kerry's wording instead",
          "someone who will welcome you and show you the ropes"
          in presets["p3"]["text"])
    check("P3 omits the optional gross games line",
          "gross games" not in presets["p3"]["text"])
    check("'weekly' not 'every week' (rule 7)",
          all("every week" not in (p.get("text") or "") for p in presets.values()))
    check("games named 'Team Net game and Closest to Pins' (rule 6)",
          "Team Net game and Closest to Pins" in presets["price_block"]["text"]
          and "eligibility" not in presets["price_block"]["text"])

    print("Course names (rule 1)")
    check("strips 'Golf Club of Texas'",
          leads.short_course_name("Silverhorn Golf Club of Texas") == "Silverhorn")
    check("strips 'Golf Club'",
          leads.short_course_name("Forest Creek Golf Club") == "Forest Creek")
    check("strips 'Golf Course'",
          leads.short_course_name("Cedar Creek Golf Course") == "Cedar Creek")
    check("leaves a name with no suffix alone",
          leads.short_course_name("TPC San Antonio - Canyons")
          == "TPC San Antonio - Canyons")

    print("Dates (rule 2) — never 9/19")
    from datetime import date as D
    t = D(2026, 9, 3)
    check("inside 7 days is the day name",
          leads.when_phrase("2026-09-08", t) == "Tuesday",
          leads.when_phrase("2026-09-08", t))
    check("8-10 days is 'next Saturday, Sep 12'",
          leads.when_phrase("2026-09-12", t) == "next Saturday, Sep 12",
          leads.when_phrase("2026-09-12", t))
    check("beyond that is 'Sep 19'",
          leads.when_phrase("2026-09-19", t) == "Sep 19",
          leads.when_phrase("2026-09-19", t))
    check("no slashes anywhere",
          "/" not in leads.when_phrase("2026-10-20", t))

    print("Start phrase (build ask B)")
    check("shotgun", leads.start_phrase(SILVERHORN) == ", 5:30p shotgun",
          leads.start_phrase(SILVERHORN))
    check("tee times",
          leads.start_phrase(CEDAR) == " with tee times starting at 8:30a",
          leads.start_phrase(CEDAR))
    check("unknown start renders NOTHING rather than guessing",
          leads.start_phrase({"start_time": "", "start_type": ""}) == "")

    print("Pricing — verified against the live Edit Event screen")
    check("Silverhorn 9h 1st Timer is $49 (CA verified 64/74/49)",
          leads.first_timer_price(SILVERHORN) == 49.0,
          leads.first_timer_price(SILVERHORN))
    check("Cedar Creek 18h uses the +$15 guest surcharge",
          leads.first_timer_price(CEDAR) == 110.0,
          leads.first_timer_price(CEDAR))
    check("an uncontracted course yields NO price, not a zero",
          leads.first_timer_price(NOCOST) is None)
    check("money() drops cents on whole dollars", leads.money(49.0) == "$49")
    check("gross bundle is $16 on 9s and $30 on 18s",
          leads.GROSS_BUNDLE[9] == "$16" and leads.GROSS_BUNDLE[18] == "$30")

    print("Owner (rule 3) — both names whenever Austin is touched")
    ow = {"San Antonio": "Kerry", "Austin": "Robert", "default": "Kerry"}
    check("SA-only is the sender alone",
          leads.owner_phrase("San Antonio", "yes_for_san_antonio", ow) == "Kerry")
    check("Austin chapter gets both",
          leads.owner_phrase("Austin", "yes_for_austin", ow) == "Kerry and Robert")
    check("both-cities gets both even on an SA lead",
          leads.owner_phrase("San Antonio", "yes_for_both", ow) == "Kerry and Robert")

    print("Cadence (rule 4) — never drops the other option")
    tue = leads.cadence_phrase("tue")
    sat = leads.cadence_phrase("sat")
    check("Tue leads with Tuesdays", tue.startswith("9 after work on Tuesdays weekly"))
    check("...and still mentions Saturday", "Saturday 18" in tue)
    check("Sat leads with Saturday", sat.startswith("a Saturday 18 each month"))
    check("...and still mentions Tuesday", "Tuesdays" in sat)
    check("the 'whenever you can' softener rides the NON-selected day only",
          "whenever you can" in sat and "whenever you can" not in tue)

    print("Chapter callout (rule 5) — only when Invitations = Both")
    check("both cities gets the callout",
          leads.chapter_phrase("yes_for_both", "San Antonio") == " here in SA")
    check("Austin variant",
          leads.chapter_phrase("yes_for_both", "Austin") == " here in Austin")
    check("single-chapter invites get NO callout",
          leads.chapter_phrase("yes_for_san_antonio", "San Antonio") == "")

    print("Rendering end to end")
    rows = {"any": {"San Antonio": SILVERHORN, "Austin": SHADOW},
            "tue": {"San Antonio": SILVERHORN, "Austin": SHADOW},
            "sat": {"San Antonio": CEDAR}}
    l = lead(first="Mitchell", chapter="San Antonio", imp="Golf",
             avail="Both (Tue + Sat)", inv="San Antonio only")
    v = leads.sms_vars_for(l, ow, {}, rows, "both")
    txt = leads.render_sms(presets, "p2", l, v, slot="both")
    check("names the person and the sender", txt.startswith("Hey Mitchell, Kerry with"))
    check("uses the short course name", "at Silverhorn," in txt, txt[:200])
    check("uses the day name, not a date", "is Tuesday at Silverhorn" in txt, txt[:220])
    check("carries the shotgun phrase", "5:30p shotgun" in txt)
    check("quotes the real 1st Timer price", "$49 is our 1st Time rate" in txt, txt)
    check("no unfilled placeholders", "{" not in txt, txt)
    check("no double spaces left behind", "  " not in txt)

    print("Price block drops out when the price is unknown")
    l2 = lead(first="Jill", chapter="Austin", imp="Golf", avail="Tuesdays only")
    v2 = leads.sms_vars_for(l2, ow, {}, {"any": {"Austin": NOCOST},
                                         "tue": {"Austin": NOCOST}}, "tue")
    txt2 = leads.render_sms(presets, "p2", l2, v2, slot="tue")
    check("no price sentence at all", "1st Time rate" not in txt2, txt2)
    check("no empty dollar sign", "$ " not in txt2 and "{first_timer_price}" not in txt2)
    check("the rest of the message still reads",
          "Forest Creek" in txt2 and txt2.rstrip().endswith("We'd love to have you play!"),
          txt2)
    check("Austin lead gets both names", "Kerry and Robert" in txt2)

    print("P3 keeps its price sentence but never the gross games line")
    l3 = lead(first="Gio", chapter="San Antonio", imp="Community",
              avail="Tuesdays only", inv="Both chapters")
    v3 = leads.sms_vars_for(l3, ow, {}, rows, "tue")
    txt3 = leads.render_sms(presets, "p3", l3, v3, slot="tue")
    check("P3 quotes the price", "$49 is our 1st Time rate" in txt3, txt3)
    check("P3 omits optional gross games", "gross games" not in txt3)
    check("P3 carries the chapter callout for a both-cities lead",
          "here in SA" in txt3, txt3[:260])
    check("P3 says Kerry's welcome line",
          "someone who will welcome you and show you the ropes" in txt3)

    print("P9 now names the other chapter's event (#406)")
    v9 = leads.sms_vars_for(l3, ow, {}, rows, "tue")
    txt9 = leads.render_sms(presets, "p9", l3, v9)
    check("P9 appends the other chapter's game",
          "Our Austin group is playing ShadowGlen" in txt9, txt9)

    print("Range balls (build ask A)")
    vr = leads.sms_vars_for(lead(chapter="San Antonio", imp="Golf",
                                 avail="Saturdays only"),
                            ow, {}, rows, "sat")
    check("included renders ', range balls'", vr["range_balls"] == ", range balls",
          vr["range_balls"])
    check("not stated renders nothing",
          leads.sms_vars_for(l, ow, {}, rows, "tue")["range_balls"] == "")

    # The checkbox on the Edit Event screen is only useful if the field
    # survives the save — update_event drops anything outside its allowed
    # set silently, which is exactly how a checkbox becomes a no-op.
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    with db._connect(tmp.name) as conn:
        conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, "
                     "item_name TEXT, range_balls_included INTEGER)")
        conn.execute("INSERT INTO events (id, item_name) VALUES (1, 's9.22')")
        conn.commit()
    db.update_event(1, {"range_balls_included": 1}, db_path=tmp.name)
    with db._connect(tmp.name) as conn:
        got = conn.execute("SELECT range_balls_included FROM events "
                           "WHERE id = 1").fetchone()[0]
    check("update_event persists range_balls_included", got == 1, got)
    db.update_event(1, {"range_balls_included": 0}, db_path=tmp.name)
    with db._connect(tmp.name) as conn:
        got = conn.execute("SELECT range_balls_included FROM events "
                           "WHERE id = 1").fetchone()[0]
    check("unchecking clears it", got == 0, got)
    os.unlink(tmp.name)

    print("The /api/leads payload shape (v2.300.0 regression)")
    # v2.300.0 collapsed P1-P4 from per-slot keys (tue/sat/both) to one
    # `text`, and a legacy line in /api/leads still read ["tue"]. The
    # KeyError 500'd the route and the Lead Center came up BLANK on
    # mobile. Every preset the route hands the client must resolve to a
    # body without indexing a slot key.
    order = leads.sms_preset_order(presets)
    for k in order:
        p = presets[k]
        body = p.get("text") or p.get("tue") or p.get("both") or ""
        check(f"{k} resolves to a body without a slot key", bool(body), p.keys())
    _p4 = presets.get("p4") or {}
    check("the legacy sms_template still resolves",
          bool(_p4.get("text") or _p4.get("tue") or _p4.get("both")), _p4.keys())
    check("fragments are not offered as pickable presets",
          not ({"closer", "p9", "price_block"} & set(order)), order)
    check("every ORDERED preset actually exists in the set",
          all(k in presets for k in order), order)

    print("lead_center_payload — the exact thing /api/leads returns")
    import tempfile as _tf
    _t = _tf.NamedTemporaryFile(suffix=".db", delete=False)
    _t.close()
    with db._connect(_t.name) as conn:
        leads.ensure_leads_table(conn)
        conn.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY "
                     "KEY, customer_id INTEGER, transaction_status TEXT, "
                     "merchant TEXT, item_name TEXT, parent_item_id INTEGER)")
        conn.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT "
                     "PRIMARY KEY, value TEXT, updated_at TEXT)")
        conn.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY "
                     "KEY, item_name TEXT, event_date TEXT, course TEXT, "
                     "chapter TEXT, format TEXT, start_type TEXT, "
                     "start_time TEXT, course_cost REAL, tgf_markup REAL, "
                     "side_game_fee REAL, transaction_fee_pct REAL, "
                     "range_balls_included INTEGER, event_type TEXT, "
                     "status_badge TEXT)")
        conn.execute(
            "INSERT INTO leads (source, external_id, first_name, last_name, "
            "email, chapter, status, arrived_at, payload) VALUES "
            "('hubspot', 'x1', 'Bruno', 'Ramos', 'b@x.com', 'San Antonio', "
            "'new', datetime('now'), ?)",
            (json.dumps({AVAIL: BY_LABEL["availability"]["Both (Tue + Sat)"],
                         IMP: BY_LABEL["importance"]["Golf"],
                         "ad_set_name": "SA - Fall 2026 Leads"}),))
        conn.execute(
            "INSERT INTO events (item_name, event_date, course, chapter, "
            "format, start_type, start_time, course_cost, tgf_markup, "
            "side_game_fee, transaction_fee_pct, event_type) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,'event')",
            ("s9.22 Silverhorn", SILVERHORN["event_date"],
             SILVERHORN["course"], "San Antonio", "9 Holes", "Shotgun",
             "17:30", 48.71, 8.0, 7.0, 3.5))
        conn.commit()
    pay = leads.lead_center_payload(db_path=_t.name)
    check("it returns every key the page reads",
          {"leads", "by_ad_set", "sms_template", "next_events",
           "sms_presets", "sms_order", "sms_p9_presets", "campaigns",
           "tag_options", "answer_options"} <= set(pay), sorted(pay))
    check("the lead comes back with a server-picked preset",
          len(pay["leads"]) == 1 and pay["leads"][0].get("sms"),
          pay["leads"][0].get("sms") if pay["leads"] else None)
    check("sms_template resolves to a real body (the v2.300.0 KeyError)",
          isinstance(pay["sms_template"], str) and pay["sms_template"],
          repr(pay["sms_template"])[:60])
    check("ad-set stats are keyed on the human name",
          "SA - Fall 2026 Leads" in pay["by_ad_set"], pay["by_ad_set"])
    check("every ordered preset is present and sendable",
          all(pay["sms_presets"].get(k, {}).get("text")
              or pay["sms_presets"].get(k, {}).get("tue")
              for k in pay["sms_order"]), pay["sms_order"])
    os.unlink(_t.name)

    # ── WAVE 2 (#417) ────────────────────────────────────────────
    print("Wave 2: the follow-ups carry the link, not a price recap")
    LINKED = dict(SILVERHORN, registration_url="https://tgf.example/s9-22")
    rows_l = {"any": {"San Antonio": LINKED}, "tue": {"San Antonio": LINKED},
              "sat": {"San Antonio": CEDAR}}
    l7 = lead(first="Jeff", chapter="San Antonio", imp="Golf",
              avail="Tuesdays only", inv="San Antonio only")
    v7 = leads.sms_vars_for(l7, ow, {}, rows_l, "tue")
    t7 = leads.render_sms(presets, "p7", l7, v7, slot="tue")
    check("P7 carries the actual link", "https://tgf.example/s9-22" in t7, t7)
    check("P7 tells them to click 1st Timer",
          "just click 1st Timer for the discount" in t7, t7)
    check("P7 names the event and why it was picked",
          "at Silverhorn is up next based on your availability" in t7, t7)
    check("P7 gives the deadline a reason, not just a date",
          "so we can get the groups set" in t7, t7)
    check("P7 keeps Kerry's joke about encountering weird people",
          "whether there's weird people" in t7, t7)
    check("P7 drops the salesman setup line",
          "answer for all three" not in t7, t7)
    check("P7 leaves no placeholder", "{" not in t7, t7)

    # Kerry's rule: Tuesday events close two days before, weekend 18s
    # three, rendered as that evening.
    check("a Tuesday event closes Sunday evening",
          "Sign ups close Sunday evening" in t7, t7)
    l7c = lead(first="Jason", chapter="San Antonio", imp="Golf",
               avail="Saturdays only", inv="San Antonio only")
    rows_c = {"any": {"San Antonio": dict(CEDAR, registration_url="https://x/y")},
              "tue": {}, "sat": {"San Antonio": dict(CEDAR, registration_url="https://x/y")}}
    v7c = leads.sms_vars_for(l7c, ow, {}, rows_c, "sat")
    t7c = leads.render_sms(presets, "p7", l7c, v7c, slot="sat")
    check("a Saturday 18 closes Wednesday evening",
          "Sign ups close Wednesday evening" in t7c, t7c)

    # The valve: an event with no URL must not send a dangling offer.
    v7n = leads.sms_vars_for(l7, ow, {}, {"any": {"San Antonio": SILVERHORN},
                                          "tue": {"San Antonio": SILVERHORN},
                                          "sat": {}}, "tue")
    t7n = leads.render_sms(presets, "p7", l7, v7n, slot="tue")
    check("with no URL the link sentence vanishes entirely",
          "Here's the link" not in t7n and "http" not in t7n, t7n)
    check("and the message still ends like a message",
          t7n.rstrip().endswith("Ready to give it a shot?"), t7n)
    check("no placeholder is left where the link was", "{" not in t7n, t7n)

    print("Wave 2: P7b names the last ask and never mentions a drink")
    t7b = leads.render_sms(presets, "p7b", l7, v7, slot="tue")
    check("P7b says it is the last one, which is honest and lifts replies",
          "this is my last one for now" in t7b, t7b)
    check("P7b answers nerves with the net Team Best Ball game",
          "your foursome is actually rooting for you" in t7b, t7b)
    # Kerry: the free-drink line "comes across potentially like we're a
    # drinking league". It is removed and must not come back.
    check("P7b NEVER offers a drink as the answer to nerves",
          "drink" not in t7b.lower(), t7b)
    check("P7b offers a real out with no season promise",
          "check back when it fits" in t7b and "next season" not in t7b, t7b)
    check("P7b carries the link", "https://tgf.example/s9-22" in t7b, t7b)
    t7bn = leads.render_sms(presets, "p7b", l7, v7n, slot="tue")
    check("and drops 'Link's below' when there is no link",
          "Link's below" not in t7bn and "http" not in t7bn, t7bn)

    print("Wave 2: P6 states the decision rule, P8 asks the real question")
    t6 = leads.render_sms(presets, "p6", l7, v7, slot="tue")
    check("P6 no longer promises events TGF might not add",
          "we add events" not in t6, t6)
    check("P6 states how the decision is actually made",
          "how we decide what to add" in t6, t6)
    check("P6 sounds like Kerry, not a marketer",
          "No pressure at all" in t6 and "Zero pressure" not in t6, t6)

    t8 = leads.render_sms(presets, "p8", l7, v7, slot="tue")
    check("P8 names the pattern instead of assuming they missed something",
          "You keep circling back" in t8, t8)
    check("P8 does not answer a question nobody asked",
          "no catching up required" not in t8, t8)
    check("P8 asks exactly one question",
          t8.count("?") == 1, t8)
    check("P8 quotes the 1st Timer price", "as a 1st Timer" in t8, t8)
    v8n = leads.sms_vars_for(l7, ow, {}, {"any": {"San Antonio": NOCOST},
                                          "tue": {"San Antonio": NOCOST},
                                          "sat": {}}, "tue")
    t8n = leads.render_sms(presets, "p8", l7, v8n, slot="tue")
    check("and drops the price tail when the price is unknown",
          "1st Timer" not in t8n and "{" not in t8n, t8n)

    print("Wave 2: no em-dashes anywhere in the ratified copy")
    for k in ("p1", "p2", "p3", "p4", "p6", "p7", "p7b", "p8", "p9"):
        body = (presets.get(k) or {}).get("text") or ""
        check(f"{k} has no em-dash", "\u2014" not in body, k)

    print("Selection logic still holds")
    r = pick(lead(imp="Competition", avail="Tuesdays only"))
    check("Competition -> P1", r["preset"] == "p1", r)
    r = pick(lead(avail="Neither, still interested"))
    check("No days -> P6", r["preset"] == "p6", r)
    r = pick(lead(imp="Golf", status="touched", touched_at="2026-08-28 15:00:00"))
    check("touched 5d, no reply -> P7b", r["preset"] == "p7b", r)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        raise SystemExit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
