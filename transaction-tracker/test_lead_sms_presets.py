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


def main():
    presets = {k: dict(v) for k, v in leads.DEFAULT_SMS_PRESETS.items()}
    pick = lambda l: leads.select_sms_preset(l, now=NOW)  # noqa: E731

    print("Copy rules")
    for k, p in presets.items():
        for f in ("tue", "sat", "both", "text"):
            t = p.get(f)
            if not t:
                continue
            check(f"{k}.{f} has no em-dash", "—" not in t and "–" not in t)
    for k in ("p1", "p2", "p3", "p4", "p6", "p8"):
        for f in ("tue", "sat", "both", "text"):
            t = presets[k].get(f)
            if t:
                check(f"{k}.{f} opens with the owner voice",
                      t.startswith("Hey {first_name}, {owner} with The Golf Fellowship."))
    for k in ("p7", "p7b"):
        check(f"{k} opens 'again'", presets[k]["text"].startswith("Hey {first_name}, {owner} again."))
    check("P1 tue uses {next_tue}", "{next_tue}" in presets["p1"]["tue"])
    check("P1 sat uses {next_sat} + Saturday 18s",
          "{next_sat}" in presets["p1"]["sat"] and "Saturday 18s" in presets["p1"]["sat"])
    check("P1 both uses {next_event} + Tuesday 9s and a Saturday 18 each month",
          "{next_event}" in presets["p1"]["both"]
          and "Tuesday 9s and a Saturday 18 each month" in presets["p1"]["both"])
    check("closer verbatim", presets["closer"]["text"] == "$25 off your first event, plus a drink on us.")
    check("P9 verbatim", presets["p9"]["text"].startswith("BTW, you marked both San Antonio and Austin."))

    print("Selection logic")
    r = pick(lead(imp="Competition", avail="Tuesdays only"))
    check("Competition + Tue → P1/tue", (r["preset"], r["slot"]) == ("p1", "tue"), r)
    r = pick(lead(imp="Golf", avail="Saturdays only"))
    check("Golf + Sat → P2/sat", (r["preset"], r["slot"]) == ("p2", "sat"), r)
    r = pick(lead(imp="Community", avail="Both (Tue + Sat)"))
    check("Community + Both → P3/both", (r["preset"], r["slot"]) == ("p3", "both"), r)
    r = pick(lead(imp="All of it", avail="Both (Tue + Sat)"))
    check("All of it + Both → P4/both", (r["preset"], r["slot"]) == ("p4", "both"), r)
    r = pick(lead())
    check("blank Importance → P4 (tue default slot)", (r["preset"], r["slot"]) == ("p4", "tue"), r)
    r = pick(lead(imp="Competition", avail="Neither, still interested"))
    check("No days → P6 regardless of importance", r["preset"] == "p6", r)
    r = pick(lead(imp="Golf", status="touched", touched_at="2026-08-31 15:00:00"))
    check("touched 2d, no reply → P7", r["preset"] == "p7", r)
    r = pick(lead(imp="Golf", status="touched", touched_at="2026-08-28 15:00:00"))
    check("touched 5d, no reply → P7b", r["preset"] == "p7b", r)
    r = pick(lead(imp="Golf", status="touched", touched_at="2026-09-01 15:00:00"))
    check("touched 1d → still the first touch (P2)", r["preset"] == "p2", r)
    r = pick(lead(imp="Golf", status="touched", touched_at="2026-08-28 15:00:00", tag="Interested"))
    check("hot tag = replied → no second touch", r["preset"] == "p2", r)
    r = pick(lead(imp="Golf", status="touched", touched_at="2026-08-28 15:00:00",
                  notes=[{"author": "K", "note": "said he'd come"}]))
    check("human note = replied → no second touch", r["preset"] == "p2", r)
    r = pick(lead(imp="Golf", status="touched", touched_at="2026-08-28 15:00:00",
                  notes=[{"author": "HS", "note": "Re-submitted the FB survey"}]))
    check("system-only notes are not a reply → P7b", r["preset"] == "p7b", r)
    r = pick(lead(imp="Golf", notes=[{"author": "HS", "note": "Re-submitted the FB survey — existing HubSpot contact since 2025-04-25"}]))
    check("re-submitter → P8", r["preset"] == "p8", r)
    r = pick(lead(imp="Golf", has_history=True))
    check("existing customer → P8", r["preset"] == "p8", r)

    print("#389 add-on + closer")
    r = pick(lead(imp="Competition", avail="Tuesdays only", inv="Both chapters"))
    check("Both cities on P1 → p9 add-on", r["addons"] == ["p9"], r)
    r = pick(lead(imp="Golf", inv="Both chapters", has_history=True))
    check("Both cities on P8 → p9 add-on", r["addons"] == ["p9"], r)
    r = pick(lead(avail="Neither, still interested", inv="Both chapters"))
    check("P6 never carries p9", r["addons"] == [], r)
    r = pick(lead(imp="Golf", inv="Both chapters", status="touched", touched_at="2026-08-28 15:00:00"))
    check("P7b never carries p9", r["addons"] == [], r)
    r = pick(lead(imp="Competition", inv="San Antonio only"))
    check("single-chapter invites → no p9", r["addons"] == [], r)

    print("Rendering")
    vars_ = leads.sms_vars_for(lead(first="Mick", chapter="Austin"),
                               leads.DEFAULT_TOUCH_OWNERS,
                               {"any": {"Austin": "Tuesday 9/8 at ShadowGlen"},
                                "tue": {"Austin": "Tuesday 9/8 at ShadowGlen"},
                                "sat": {"Austin": "Saturday 9/20 at Crystal Falls"}})
    check("Austin owner is Robert", vars_["owner"] == "Robert", vars_)
    txt = leads.render_sms(presets, "p1", {}, vars_, slot="tue", addons=["p9"], closer=True)
    check("P1 renders name + owner", txt.startswith("Hey Mick, Robert with The Golf Fellowship."), txt)
    check("P1 tue fills {next_tue}", "Next one's Tuesday 9/8 at ShadowGlen. Want a spot?" in txt, txt)
    lines = txt.split("\n")
    check("P9 rides as its own line after the closer question",
          len(lines) == 3 and lines[1].startswith("BTW, you marked both"), lines)
    check("offer line last", lines[-1] == "$25 off your first event, plus a drink on us.", lines)
    check("no unfilled placeholders", "{" not in txt, txt)
    txt2 = leads.render_sms(presets, "p1", {}, vars_, slot="tue")
    check("no add-on / closer unless asked", "\n" not in txt2, txt2)
    txt3 = leads.render_sms(presets, "p1", {}, vars_, slot="sat")
    check("sat slot fills {next_sat}", "Saturday 9/20 at Crystal Falls" in txt3, txt3)
    fb = leads.sms_vars_for(lead(first="", chapter=""), leads.DEFAULT_TOUCH_OWNERS, {})
    check("fallbacks: 'there' / Kerry / Tuesday night",
          (fb["first_name"], fb["owner"], fb["next_tue"]) == ("there", "Kerry", "Tuesday night"), fb)

    print("Next-event labels + dials (SQLite)")
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db_path = tmp.name
    with db._connect(db_path) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, "
                     "item_name TEXT, event_date TEXT, course TEXT, chapter TEXT, "
                     "event_type TEXT DEFAULT 'event')")
        conn.execute("CREATE TABLE IF NOT EXISTS app_settings (key TEXT PRIMARY KEY, "
                     "value TEXT, updated_at TEXT)")
        rows = [
            ("s9.22 SILVERHORN", "2026-09-08", "Silverhorn", "San Antonio"),
            ("a9.22 SHADOWGLEN", "2026-09-08", "ShadowGlen", "Austin"),
            ("s9.21 CANYON SPRINGS", "2026-09-01", "Canyon Springs", "San Antonio"),  # past
            ("a18.4 CRYSTAL FALLS", "2026-09-19", "Crystal Falls", "Austin"),
            ("s18.11 THE QUARRY", "2026-10-10", "The Quarry", "San Antonio"),  # > 3 weeks
            ("TGF CHAMPIONSHIP", "2026-11-14", "Cordillera", "TGF"),
        ]
        conn.executemany("INSERT INTO events (item_name, event_date, course, chapter) "
                         "VALUES (?,?,?,?)", rows)
        conn.commit()
    n = leads.next_event_labels(db_path, today="2026-09-02")
    check("SA next event = Tuesday 9/8 at Silverhorn", n["any"].get("San Antonio") == "Tuesday 9/8 at Silverhorn", n)
    check("Austin next tue = ShadowGlen", n["tue"].get("Austin") == "Tuesday 9/8 at ShadowGlen", n)
    check("past events ignored", "Canyon Springs" not in json.dumps(n), n)
    check("Austin next sat = Crystal Falls", n["sat"].get("Austin") == "Saturday 9/19 at Crystal Falls", n)
    check("SA borrows Austin's Saturday (own 18 is 5+ weeks out)",
          n["sat"].get("San Antonio") == "Saturday 9/19 at Crystal Falls (Austin)", n)
    n2 = leads.next_event_labels(db_path, today="2026-11-01")
    check("TGF event counts for both chapters",
          n2["any"].get("Austin") == "Saturday 11/14 at Cordillera"
          and n2["any"].get("San Antonio") == "Saturday 11/14 at Cordillera", n2)

    with db._connect(db_path) as conn:
        conn.execute("INSERT INTO app_settings (key, value) VALUES (?, ?)",
                     ("lead_sms_presets", json.dumps({
                         "p6": "Hey {first_name}, {owner} here. Edited P6.",
                         "p1": {"tue": "Edited P1 tue {next_tue}"},
                         "closer": {"text": "Edited closer."}})))
        conn.execute("INSERT INTO app_settings (key, value) VALUES (?, ?)",
                     ("lead_touch_owners", json.dumps({"Austin": "James"})))
        conn.execute("INSERT INTO app_settings (key, value) VALUES (?, ?)",
                     ("lead_sms_template", "Hey {first_name}, legacy text."))
        conn.commit()
    ps = leads.get_sms_presets(db_path)
    check("dial string replaces a single-text preset", ps["p6"]["text"].startswith("Hey {first_name}, {owner} here. Edited P6."), ps["p6"])
    check("dial dict merges one slot, keeps the others",
          ps["p1"]["tue"] == "Edited P1 tue {next_tue}" and ps["p1"]["sat"] == presets["p1"]["sat"], ps["p1"])
    check("closer editable", ps["closer"]["text"] == "Edited closer.", ps["closer"])
    check("legacy template rides as 'custom'", ps.get("custom", {}).get("text") == "Hey {first_name}, legacy text.", ps.get("custom"))
    check("picker order: P1..P8 then custom", leads.sms_preset_order(ps) == ["p1", "p2", "p3", "p4", "p6", "p7", "p7b", "p8", "custom"], leads.sms_preset_order(ps))
    ow = leads.get_touch_owners(db_path)
    check("owner dial overrides Austin only", ow["Austin"] == "James" and ow["San Antonio"] == "Kerry", ow)

    os.unlink(db_path)
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        raise SystemExit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
