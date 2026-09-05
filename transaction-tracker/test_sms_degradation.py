#!/usr/bin/env python3
"""Mailbox #424/#425: every preset, every combination of ABSENT data.

The P7 defect only existed when data was missing, which is the NORMAL
state for a half-built field. The existing suites test the happy path, so
they could not have caught it.

The acceptance criterion is CA's, and it is stricter than "no braces":
a human reading any degraded render must not be able to tell that a
block was removed. So this asserts no placeholder AND no doubled space,
no orphaned comma, no comma before a full stop, no sentence-final
connective, and no event reference with no event behind it.
"""
import itertools
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DATABASE_PATH", ":memory:")

from email_parser import leads  # noqa: E402

FAILURES = []


def check(label, cond, detail=""):
    if cond:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}  {detail!r}")
        FAILURES.append(label)


FULL_EVENT = {
    "item_name": "s9.22 Silverhorn", "event_date": "2026-09-08",
    "course": "Silverhorn Golf Club of Texas", "chapter": "San Antonio",
    "course_cost": 48.71, "tgf_markup": 8.0, "side_game_fee": 7.0,
    "transaction_fee_pct": 3.5, "start_time": "17:30",
    "start_type": "Shotgun", "range_balls_included": 1,
    "registration_url": "https://tgf.example/s922",
}

LEAD = {
    "id": 1, "first_name": "John", "last_name": "Doe",
    "chapter": "San Antonio",
    "payload": {"can_you_play_tuesdays_or_saturdays":
                "yes_-_i_can_play_tuesdays",
                "which_is_most_important_to_you":
                "golf_-_explore_a_variety_of_courses_and_play_as_much_as_possible",
                "would_you_like_to_stay_in_the_loop_with_tgf_and_receive"
                "_event_invitations": "yes_for_san_antonio"},
}

# Every field whose absence CA named, plus the ones the presets touch.
STRIPPABLE = ["registration_url", "course_cost", "start_time",
              "range_balls_included", "course", "event_date"]


def variants():
    """The full power set of missing data, plus 'no event at all'."""
    for n in range(len(STRIPPABLE) + 1):
        for combo in itertools.combinations(STRIPPABLE, n):
            ev = dict(FULL_EVENT)
            for f in combo:
                ev[f] = None
            yield (", ".join(combo) or "nothing missing"), ev
    yield "no event at all", {}


def main():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    p = tmp.name
    presets = leads.DEFAULT_SMS_PRESETS
    owners = leads.DEFAULT_TOUCH_OWNERS
    keys = list(leads.SMS_PRESET_ORDER)

    print(f"{len(keys)} presets x {2 ** len(STRIPPABLE) + 1} data states, "
          "with and without the offer line")
    checked = 0
    broken: dict = {}
    for why, ev in variants():
        rows = {"any": {"San Antonio": ev}, "tue": {"San Antonio": ev},
                "sat": {"San Antonio": ev}}
        v = leads.sms_vars_for(LEAD, owners, {}, rows, "tue")
        for key in keys:
            for closer in (False, True):
                txt = leads.render_sms(presets, key, LEAD, v,
                                       slot="tue", closer=closer)
                checked += 1
                # The one thing that must NEVER happen.
                if "{" in txt or "}" in txt:
                    broken.setdefault("placeholder", []).append((key, why))
                # And the grammar CA flagged as worse than a brace.
                if "  " in txt:
                    broken.setdefault("doubled space", []).append((key, why))
                if ",." in txt or ", ." in txt:
                    broken.setdefault("comma before stop", []).append((key, why))
                if ",," in txt or ", ," in txt:
                    broken.setdefault("doubled comma", []).append((key, why))
                for line in txt.split("\n"):
                    if line.rstrip().endswith((" and", " or", " for",
                                               " with", " at", " to", ",")):
                        broken.setdefault("unfinished sentence",
                                          []).append((key, why))
                if not txt.strip():
                    broken.setdefault("empty message", []).append((key, why))

    check(f"{checked} renders carry no unresolved placeholder",
          "placeholder" not in broken, broken.get("placeholder", [])[:4])
    check("none has a doubled space",
          "doubled space" not in broken, broken.get("doubled space", [])[:4])
    check("none has a comma sitting before a full stop",
          "comma before stop" not in broken,
          broken.get("comma before stop", [])[:4])
    check("none has a doubled comma",
          "doubled comma" not in broken, broken.get("doubled comma", [])[:4])
    check("none ends a sentence on a connective",
          "unfinished sentence" not in broken,
          broken.get("unfinished sentence", [])[:4])
    check("none renders empty", "empty message" not in broken,
          broken.get("empty message", [])[:4])

    # The specific live defect, pinned by name.
    print("The exact P7 defect Kerry caught")
    ev = dict(FULL_EVENT, registration_url=None)
    rows = {"any": {"San Antonio": ev}, "tue": {"San Antonio": ev}, "sat": {}}
    v = leads.sms_vars_for(LEAD, owners, {}, rows, "tue")
    t7 = leads.render_sms(presets, "p7", LEAD, v, slot="tue")
    check("P7 with no registration URL shows no {link_offer}",
          "{" not in t7, t7)
    check("it drops the whole link clause, not just the token",
          "Here's the link" not in t7, t7)
    check("and still ends like a message a person wrote",
          t7.rstrip().endswith("Ready to give it a shot?"), t7)
    check("the deadline sentence survives, because that data DOES exist",
          "Sign ups close Sunday evening" in t7, t7)

    print("An event we know nothing about is REFUSED, not sent")
    v0 = leads.sms_vars_for(LEAD, owners, {}, {"any": {}, "tue": {}, "sat": {}},
                            "tue")
    t0 = leads.render_sms(presets, "p7", LEAD, v0, slot="tue")
    check("no brace survives even with no event at all", "{" not in t0, t0)
    check("but it is FLAGGED as unsendable rather than quietly served",
          "empty_event" in leads.sms_issues_for(presets, "p7", t0, v0),
          (t0, leads.sms_issues_for(presets, "p7", t0, v0)))
    check("the text-only backstop catches it too, for callers with no vars",
          "empty_event" in leads.sms_render_issues(t0),
          (t0, leads.sms_render_issues(t0)))
    t6 = leads.render_sms(presets, "p6", LEAD, v0, slot="tue")
    check("a preset that names no event is still clean and sendable",
          leads.sms_issues_for(presets, "p6", t6, v0) == [], t6)

    print("With a real event, nothing is flagged")
    rowsf = {"any": {"San Antonio": FULL_EVENT},
             "tue": {"San Antonio": FULL_EVENT}, "sat": {}}
    vf = leads.sms_vars_for(LEAD, owners, {}, rowsf, "tue")
    for k in keys:
        tf = leads.render_sms(presets, k, LEAD, vf, slot="tue")
        if leads.sms_issues_for(presets, k, tf, vf):
            check(f"{k} is clean with full data", False,
                  (tf, leads.sms_issues_for(presets, k, tf, vf)))
            break
    else:
        check("every preset is clean and sendable with full data", True)

    print("Every fragment is registered, so none can be forgotten again")
    import re
    declared = set(leads.SMS_FRAGMENT_REQUIRES)
    used = set()
    for k, pre in presets.items():
        for field in ("text", "no_games", "tue", "sat", "both"):
            used |= set(re.findall(r"\{([a-z_0-9]+)\}", pre.get(field) or ""))
    var_names = set(leads.sms_vars_for(LEAD, owners, {}, rows, "tue"))
    unaccounted = used - declared - var_names
    check("no preset references a token that is neither a var nor a "
          "registered fragment", not unaccounted, sorted(unaccounted))

    os.unlink(p)
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILURE(S): {FAILURES}")
        raise SystemExit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
