/**
 * Every page that loads auth.js must call initAuth().
 *
 * CLAUDE.md: "initAuth() must be called on every page for nav link
 * visibility." Two pages had drifted off that rule by 2026-09-21. The
 * dashboard's symptom was loud — it set window.onAuthReady, nothing ever
 * called initAuth, so the callback never fired, load() never ran and the
 * page sat on "Loading…" forever (Kerry: "Stuck on perma load").
 * Participation's symptom was quiet: its data loaded, but its nav was
 * never role-gated, so an admin saw no admin links.
 *
 * This is the CLASS guard for that bug (CLAUDE.md guiding principle:
 * protect the class, not the instance). A page may satisfy the rule
 * directly or through a script it loads.
 */
const fs = require("fs"), path = require("path");
const T = path.join(__dirname, "templates"), S = path.join(__dirname, "static/js");
const FAIL = [];
const check = (l, c, d) => { console.log((c ? "  PASS  " : "  FAIL  ") + l + (c ? "" : "  " + (d || ""))); if (!c) FAIL.push(l); };

const callsInit = src => /\binitAuth\s*\(/.test(src);
const localScripts = html => [...html.matchAll(/<script[^>]*src="\/static\/js\/([^"]+)"/g)].map(m => m[1]);

console.log("Every page that loads auth.js calls initAuth()");
const offenders = [];
for (const f of fs.readdirSync(T).filter(f => f.endsWith(".html"))) {
    const html = fs.readFileSync(path.join(T, f), "utf8");
    const scripts = localScripts(html);
    if (!scripts.includes("auth.js")) continue;          // page does not use auth at all
    if (callsInit(html)) continue;                        // calls it inline
    const viaScript = scripts.some(s => {
        const p = path.join(S, s);
        return fs.existsSync(p) && callsInit(fs.readFileSync(p, "utf8"));
    });
    if (!viaScript) offenders.push(f);
}
check("no page loads auth.js without calling initAuth", offenders.length === 0, offenders.join(", "));

console.log("The dashboard loads its data without waiting on auth");
const dash = fs.readFileSync(path.join(T, "dashboard.html"), "utf8");
check("dashboard.html calls initAuth()", callsInit(dash));
// The original bug was load() reachable ONLY from the onAuthReady callback.
const gatedOnly = /window\.onAuthReady\s*=\s*function[^}]*\bload\s*\(\)/.test(dash)
    && !/^\s*load\(\);\s*$/m.test(dash);
check("load() is NOT reachable only through onAuthReady — the perma-load shape",
      !gatedOnly, "load() is gated behind the auth callback again");
check("...it is called at top level", /^\s*load\(\);\s*$/m.test(dash));

console.log("The dashboard is admin-only (Kerry 2026-09-21)");
const nav = fs.readFileSync(path.join(T, "_shell_nav.html"), "utf8");
const dashLinks = [...nav.matchAll(/<a href="\/dashboard"[^>]*>/g)].map(m => m[0]);
check("both nav entries exist (desktop + drawer)", dashLinks.length === 2, dashLinks.length);
check("both carry admin-nav so auth.js gates them",
      dashLinks.every(a => a.includes("admin-nav")), dashLinks.join(" | "));
check("both start hidden so a non-admin never sees a flash of the link",
      dashLinks.every(a => a.includes("display:none")), dashLinks.join(" | "));

const app = fs.readFileSync(path.join(__dirname, "app.py"), "utf8");
check("the page route redirects a non-admin instead of answering JSON 403",
      /@app\.route\("\/dashboard"\)\s*\ndef dashboard_page\(\):[\s\S]{0,260}?session\.get\("role"\) != "admin"[\s\S]{0,80}?redirect\("\/events"\)/.test(app));
check("the API route is admin-gated",
      /@app\.route\("\/api\/dashboard"\)\s*\n@require_role\("admin"\)/.test(app));
check("the landing redirect is role-aware — a manager is never bounced off home",
      /redirect\("\/dashboard" if session\.get\("role"\) == "admin"/.test(app));

console.log(FAIL.length ? `\n${FAIL.length} FAILURE(S): ${FAIL}` : "\nALL PASS");
process.exit(FAIL.length ? 1 : 0);
