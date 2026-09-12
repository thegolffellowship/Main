"""Team-board pairings keep plain 'First Last' seats (v2.371.13)."""
import os, sys
os.environ.setdefault("DATABASE_PATH", ":memory:")
from email_parser import database as db
tables = [[["1", "STRAITON, Robert + YOUNGS, Luke + Hightower, Geoffery + Zac Hammond TGF Austin, Guest", "64", "$128"],
           ["2", "MCDONNELL, Kaleb + Hall, Taylor + JENKINS, Julius + BARTZ, Joshua TGF Austin, Guest,", "67", ""],
           ["3", "CLOER, Neal + CANNON, Chris + Compton, Kyle + SHARP, Matt TGF Austin, Guest", "68", ""],
           ["4", "WADE, John + Arevalo, Guilermo + WILLIAMS, Yolanda + MAZANEC, Luke TGF Austin, Guest,", "72", ""],
           ["", "Total purse: $128", "", ""]]]
g = db._parse_teamnet_groups(tables)
ok = len(g) == 4 and g[0][3] == "Zac Hammond" and g[0][0] == "STRAITON, Robert" and all(len(x) == 4 for x in g)
print("  PASS  four groups, plain-name seat kept" if ok else f"  FAIL  {g}")
bad = db._parse_teamnet_groups([[["1", "SMITH, A + 12345 + JONES, B", "", ""]]])
ok2 = bad == []
print("  PASS  junk seat still drops the group" if ok2 else f"  FAIL  {bad}")
print("ALL PASSED" if ok and ok2 else "FAILED"); sys.exit(0 if ok and ok2 else 1)
