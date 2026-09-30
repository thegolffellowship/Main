"""Recap drafts by email are STAFF-only and paste-ready (v2.488.0).

Kerry 2026-09-23: "Automatically send Austin Recap drafts to Robert
Straiton" / "Copy me on the email you send to Robert."
Run: python test_recap_mail.py
"""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from email_parser import database as db  # noqa: E402
from email_parser import recap_mail as rm  # noqa: E402

F = []
def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}" + ("" if cond else f"  {detail}"))
    if not cond:
        F.append(label)

MD = """# drafts

## SAN ANTONIO — s9.99 Test (SENT)

**Subject:** TGF Results | SA thing

Good Afternoon, %first_name%!

## AUSTIN — a9.99 Test Links (DRAFT)

**Subject:** TGF Results | SMITH Wins

Good Afternoon, %first_name%!

Pat **SMITH** won at [Test Links](https://example.com/r). [[Lou SCHNEIDER|85]] was second and **Kyle COMPTON** third.

FALL POINTS RACE.
Pat leads. [CURRENT STANDINGS](https://tgf-tracker.up.railway.app/contests#race=fall_austin)

***
{green}**HOLE-IN-ONE Pot stands at $3,476** after Tuesday.{/green}

UP NEXT.
- **Tue, Oct 6** | [__ time __] | **[__ course __]**
- Sat, Oct 10 | LONE STAR CUP | Qualifiers Only

See you Next Tuesday!

Robert Straiton
The Golf Fellowship — Austin

---

## Draft notes (not for sending)
secret notes
"""

tmp = tempfile.mktemp(suffix=".db"); db.init_db(tmp)
name = "zz-test-recap-mail.md"
path = rm.RECAPS_DIR / name
path.write_text(MD, encoding="utf-8")
try:
    print("Rendering")
    head, body = rm.extract_section(MD, "AUSTIN")
    subj, html = rm.render_recap_html(rm._signature_breaks(body))
    html = html.replace(" ", "<br>")
    check("section heading found", head.startswith("AUSTIN"), head)
    check("member subject pulled out of the body", subj == "TGF Results | SMITH Wins" and "Subject:" not in html, subj)
    check("bold survives", "<strong>SMITH</strong>" in html)
    check("links are real anchors", '<a href="https://example.com/r"><strong>Test Links</strong></a>' in html)
    check("section heads carry a rule", "<hr" in html and "<strong>UP NEXT.</strong>" in html)
    check("bullets are a list", html.count("<li>") == 2)
    check("blanks are highlighted", "background:#fff59d" in html)
    check("signature keeps its line breaks", "Robert Straiton<br>The Golf Fellowship" in html, html[-160:])
    # Kerry's s9.25 send (2026-09-30): "Including all formatting and spacing."
    check("an empty paragraph separates blocks", '<p style="margin:0">&nbsp;</p>' in html)
    check("a section head is ruled above and spaced below",
          '<hr />\n<p style="margin:0"><strong>FALL POINTS RACE.</strong></p>\n<p style="margin:0">&nbsp;</p>' in html, html)
    check("no spacer before a rule", "&nbsp;</p>\n<hr />" not in html, html)
    check("*** is a rule with no head, green renders",
          '<hr />\n<p style="margin:0"><span style="color:#27ae60;"><strong>HOLE-IN-ONE Pot stands at $3,476</strong> after Tuesday.</span></p>' in html, html)
    check("the sign-off and signature are spaced like the send",
          'See you Next Tuesday!</p>\n<p style="margin:0">&nbsp;</p>\n<p style="margin:0">Robert Straiton<br>' in html, html[-300:])
    # Kerry 2026-09-30: "Yes, add Spotlight links starting next week"
    check("[[Name|cid]] links the player's Spotlight page, bold",
          '<a href="https://tgf-tracker.up.railway.app/member/spotlight?player=85"><strong>Lou SCHNEIDER</strong></a>' in html, html[:600])
    check("draft notes never render", "secret notes" not in html and "SA thing" not in html)

    print("\nRecipients")
    to, cc = rm.recipients_for("austin")
    check("Austin goes to Robert, Kerry copied", to == ["Robert@thegolffellowship.com"] and cc == ["kerry@thegolffellowship.com"], (to, cc))
    to, cc = rm.recipients_for("san_antonio")
    check("SA goes to Kerry with no duplicate cc", to == ["kerry@thegolffellowship.com"] and cc == [], (to, cc))
    check("a member address is refused", rm.staff_only(["pat@gmail.com", "x@thegolffellowship.com"]) == ["pat@gmail.com"])

    print("\nThe send path")
    r = rm.send_recap_draft(name, "AUSTIN", dry_run=True, db_path=tmp)
    check("dry run renders and sends nothing", r.get("status") == "dry_run" and "html" in r, r.get("error"))
    check("the cover says to paste from the email, not Word",
          "Copy the recap from this email" in (r.get("html") or ""), (r.get("html") or "")[:300])
    check("a bold member name with no Spotlight link is reported",
          r.get("unlinked_names") == ["Kyle COMPTON"], r.get("unlinked_names"))
    check("dry run lists the blanks", r.get("blanks") == ["__ course __", "__ time __"], r.get("blanks"))
    r = rm.send_recap_draft(name, "AUSTIN", to="pat@gmail.com", dry_run=False, db_path=tmp)
    check("a member recipient is refused before any send", "staff only" in (r.get("error") or ""), r)
    r = rm.send_recap_draft("../../../app.py", "AUSTIN", db_path=tmp)
    check("files outside docs/claude/recaps are refused", "recaps" in (r.get("error") or ""), r)
    r = rm.send_recap_draft(name, "HOUSTON", db_path=tmp)
    check("a missing section is refused", "not found" in (r.get("error") or ""), r)
finally:
    path.unlink()

src = open(os.path.join(os.path.dirname(__file__), "mcp_server.py"), encoding="utf-8").read()
check("the bridge exists and dry-runs unless apply", 'cmd == "scoring-recap-draft-email"' in src and 'dry_run="apply" not in _flags' in src)
print("\nALL PASS" if not F else f"\nFAILED: {F}")
sys.exit(1 if F else 0)
