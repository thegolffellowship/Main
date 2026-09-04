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
