// Guard: the Customers page's year filter counts a customer CREATED in
// the target year as activity (Kerry 2026-09-15: a Facebook lead — Joe
// Mejia, customer 729, zero purchases — was invisible under the default
// "This Year" filter even though the lead pipe had created his row).
const fs = require("fs");
const html = fs.readFileSync("templates/customers.html", "utf8");
const py = fs.readFileSync("email_parser/database.py", "utf8");
let f = 0; const ck = (l, c) => { console.log((c ? "  PASS  " : "  FAIL  ") + l); if (!c) f++; };
ck("created_at in the target year counts as activity",
   /\(c\.created_at \|\| ""\)\.startsWith\(targetYear\)\s*\|\| \(c\.items \|\| \[\]\)\.some/.test(html));
ck("the customers list query ships created_at + acquisition_source",
   /c\.created_at, c\.acquisition_source,\s*c\.updated_at,/.test(py));
console.log(f ? `${f} FAILED` : "ALL PASSED"); process.exit(f ? 1 : 0);
