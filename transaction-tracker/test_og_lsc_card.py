"""The Lone Star Cup's link-preview card (Kerry 2026-10-09: "Need to change the
link image view to show new logo and remove the qualifiers text. Make it
square. Keep the golf fellowship band over top").

Pins: /member/lonestarcup serves the square card with its size stated and no
"Qualifiers"; other pages keep their cards.

Run: python3 test_og_lsc_card.py
"""
import os, sys, re, tempfile, logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(prefix="tgf-og-"), "t.db")
os.environ.setdefault("SECRET_KEY", "test")
logging.disable(logging.ERROR)
from PIL import Image                                             # noqa: E402
import app as appmod                                              # noqa: E402
F = []


def check(l, c, d=""):
    print(f"  {'PASS' if c else 'FAIL'}  {l}" + ("" if c else f"  {d}"))
    if not c:
        F.append(l)


def meta(html, prop):
    m = re.search(r'<meta (?:property|name)="%s" content="([^"]*)"' % re.escape(prop), html)
    return m.group(1) if m else None


c = appmod.app.test_client()
h = c.get("/member/lonestarcup").get_data(as_text=True)
print("the Cup landing's card")
check("square image", (meta(h, "og:image") or "").endswith("/static/og-lone-star-cup-sq.png?v=2533"), meta(h, "og:image"))
check("size stated 1200x1200", meta(h, "og:image:width") == "1200" and meta(h, "og:image:height") == "1200")
check("square stays a summary card", meta(h, "twitter:card") == "summary", meta(h, "twitter:card"))
check("no Qualifiers in the title or text", "Qualifiers" not in (meta(h, "og:title") or "") + (meta(h, "og:description") or "")
      and meta(h, "og:title") == "The Lone Star Cup", meta(h, "og:title"))
im = Image.open("static/og-lone-star-cup-sq.png")
check("the file is 1200x1200", im.size == (1200, 1200), im.size)
r, g, b = im.convert("RGB").getpixel((10, 10))
check("the TGF orange band is on top", abs(r - 232) < 6 and abs(g - 124) < 6 and abs(b - 62) < 6, (r, g, b))

print("other pages keep theirs")
mp = c.get("/member/matchplay/austin").get_data(as_text=True)
check("Match Play stays wide", "og-match-play.png" in (meta(mp, "og:image") or "") and meta(mp, "twitter:card") == "summary_large_image"
      and meta(mp, "og:image:width") is None, (meta(mp, "og:image"), meta(mp, "twitter:card")))

print("\n" + ("ALL PASS" if not F else f"{len(F)} FAILURE(S): " + "; ".join(F)))
sys.exit(1 if F else 0)
