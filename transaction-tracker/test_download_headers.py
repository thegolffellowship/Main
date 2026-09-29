"""Download headers survive any event name (Kerry 2026-09-29: "I just got an
Internal Server Error when I tried to download the PDF for the Scorecards").

The scorecards / print-pack file names carry an em dash; header values must
be latin-1, and a2wsgi raised UnicodeEncodeError writing them — a 500. Every
Content-Disposition now comes from email_parser.http_headers.content_disposition.

Run: python3 test_download_headers.py
"""
import os, re, sys, tempfile, contextlib, io, logging
os.environ.setdefault("SECRET_KEY", "test")
os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(prefix="tgf-dl-"), "t.db")
logging.disable(logging.WARNING)
F = []
def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c: F.append(l)

from email_parser.http_headers import content_disposition, ascii_filename

NAME = "s9.25 Canyon Springs — scorecards — Café.pdf"
v = content_disposition(NAME, inline=True)
check("the header value is latin-1 (what a2wsgi writes)", bool(v.encode("latin-1")), v)
check("an ASCII fallback: dashes become -, accents fold", 'filename="s9.25 Canyon Springs - scorecards - Cafe.pdf"' in v, v)
check("the exact name rides in filename* (RFC 5987)", "filename*=UTF-8''s9.25%20Canyon%20Springs%20%E2%80%94" in v, v)
check("a plain ASCII name gets no filename*", content_disposition("a.csv") == 'attachment; filename="a.csv"')
check("quotes and line breaks cannot break out of the header", '"' not in ascii_filename('x"\r\ny'))

print("\n== the real routes, with a name holding an em dash and an accent ==")
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import app as A
import email_parser.scorecards as SC, email_parser.print_pack as PP
SC.build_scorecards_pdf = lambda *a, **k: {"pdf": b"%PDF-1.4", "filename": NAME}
A.build_print_pack_for_event = lambda *a, **k: {"pdf": b"%PDF-1.4", "filename": "s9.25 — print pack — é.pdf"}
c = A.app.test_client()
with c.session_transaction() as s:
    s["role"] = "admin"; s["authenticated"] = True
for path in ("/events/1/scorecards.pdf", "/events/1/print-pack.pdf"):
    r = c.get(path)
    ok = True
    try:
        for k, val in r.headers.items():
            val.encode("latin-1")
    except UnicodeEncodeError as e:
        ok = False
    check(f"{path}: 200 and every header latin-1", r.status_code == 200 and ok, (r.status_code, r.headers.get("Content-Disposition")))

print("\n== the class: nothing builds Content-Disposition by hand ==")
src = open("app.py", encoding="utf-8").read()
hand = [m.group(0) for m in re.finditer(r'"Content-Disposition":\s*f?["\']', src)]
check("every Content-Disposition in app.py goes through content_disposition()", not hand, hand)

print("\nALL PASSED" if not F else f"\n{len(F)} FAILED: {F}")
sys.exit(1 if F else 0)
