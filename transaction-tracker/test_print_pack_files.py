"""Print files: the bound pack cut into one PDF per report (Kerry 2026-10-09:
"Can you have the practice round reports sent to me in separate PDF files
right now? I need to send to course for printing").

Run: python3 test_print_pack_files.py
"""
import io, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pypdf import PdfWriter, PdfReader                       # noqa: E402
from email_parser import print_pack as pp                    # noqa: E402
F = []


def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c:
        F.append(l)


w = PdfWriter()
sizes = [(200, 300), (300, 200), (300, 200), (300, 200), (300, 200), (400, 400), (400, 400)]
for wd, ht in sizes:
    w.add_blank_page(width=wd, height=ht)
buf = io.BytesIO(); w.write(buf)
built = {"pdf": buf.getvalue(),
         "parts": [{"slug": "starter-sheet", "pages": 1}, {"slug": "cart-signs", "pages": 4},
                   {"slug": "scorecards", "pages": 2}],
         "event": {"id": 3330, "item_name": "LSC PRACTICE ROUND | The Hideout", "event_date": "2026-10-09"}}
files = pp.split_print_pack(built)
names = [f for f, _ in files]
check("one file per report, in print order",
      len(files) == 3 and names[0].endswith("-StarterSheet.pdf") and names[1].endswith("-CartSigns.pdf")
      and names[2].endswith("-Scorecards.pdf"), names)
pages = [len(PdfReader(io.BytesIO(b)).pages) for _, b in files]
check("each file holds exactly its report's pages", pages == [1, 4, 2], pages)
first = PdfReader(io.BytesIO(files[2][1])).pages[0]
check("the pages are the report's own (scorecards are the 400x400 pages)",
      round(float(first.mediabox.width)) == 400, first.mediabox)
built["parts"][1]["pages"] = 3
try:
    pp.split_print_pack(built); check("a page-count mismatch is refused", False)
except ValueError:
    check("a page-count mismatch is refused", True)
src = open("mcp_server.py", encoding="utf-8").read()
check("the bridge takes |files and builds with the scorecards forced in",
      'parts[1].lower() == "files"' in src and "force_scorecards=True" in src)

app_src = open("app.py", encoding="utf-8").read()
check("the Cup prints its own per-session files (starter sheet, 3e cart signs, QR scorecards)",
      'parts[1].lower().split("=")[0] == "cup-files"' in src and "def build_cup_print_files(" in app_src
      and '"lsc_starter_sheet.html"' in app_src and 'cup_cart_signs_data(int(event_id), session_id=sid)' in app_src
      and 'build_scorecards(int(event_id), "3up", "team", qr="on", session=sid)' in app_src)

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
