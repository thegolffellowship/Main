/**
 * Dashboard page render (Kerry 2026-09-21).
 *
 * The page is a ROUTER: counts and links, no work. These guard the two
 * rules that make it stay useful — a card with nothing in it never
 * renders, and a feed that failed is SAID so rather than silently
 * missing (a dashboard that quietly drops a card is worse than no card).
 */
const fs = require("fs"), path = require("path");
const FAIL = [];
const check = (l, c, d) => { console.log((c ? "  PASS  " : "  FAIL  ") + l + (c ? "" : "  " + (d || ""))); if (!c) FAIL.push(l); };

const html = fs.readFileSync(path.join(__dirname, "templates/dashboard.html"), "utf8");
let js = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)]
    .map(m => m[1]).sort((a, b) => b.length - a.length)[0]
    .replace(/\{%[\s\S]*?%\}/g, "").replace(/\{\{[\s\S]*?\}\}/g, "null");

const store = {};
const el = id => (store[id] = store[id] || { id, innerHTML: "", textContent: "", style: {} });
global.document = { getElementById: el, addEventListener() {} };
global.window = {}; global.fetch = () => Promise.resolve({ ok: true, json: () => ({}) });
eval(js);
const render = global.window.__dbRender;
check("the page exposes its real renderer to the guard", typeof render === "function");

console.log("Cards");
render({ as_of: "2026-09-21", cards: [
  { key: "events_week", title: "Events this week", count: 2, href: "/events", detail: "tee sheets to work", tone: "do",
    items: [{ label: "s9.24 Brackenridge", meta: "tomorrow · 14 in", href: "/events?event=3309" },
            { label: "a9.24 Teravista", meta: "in 1d · 9 in", href: "/events?event=3315" }] },
  { key: "attribute", title: "First timers to attribute", count: 1, href: "/admin/leads", detail: "who brought them?", tone: "watch",
    items: [{ label: "Ty Bubela", meta: "first played 3d ago", href: "/customers?cid=829" }] },
], skipped: [], total: 3 });
let out = store["db-body"].innerHTML;
check("a card renders its count, title and detail",
      out.includes(">2<") && out.includes("Events this week") && out.includes("tee sheets to work"), out.slice(0, 200));
check("the card links to the surface that OWNS the work", out.includes('href="/events"'));
check("peek rows link to their own row", out.includes('href="/events?event=3309"'));
check("the tone drives the rail colour class", out.includes("db-card do") && out.includes("db-card watch"));
check("Ty Bubela reaches the page", out.includes("Ty Bubela"));
check("the as-of date shows", store["db-asof"].textContent === "2026-09-21");

console.log("The two rules");
render({ as_of: "2026-09-21", cards: [], skipped: [], total: 0 });
check("no cards is a RESULT, not an empty state",
      store["db-body"].innerHTML.includes("Nothing needs you right now"), store["db-body"].innerHTML);
check("...and no grid is drawn", !store["db-body"].innerHTML.includes("db-grid"));

render({ as_of: "2026-09-21", cards: [{ key: "k", title: "T", count: 1, href: "/x", tone: "do", items: [] }],
         skipped: [{ feed: "renewals", error: "no such table" }], total: 1 });
check("a feed that failed is NAMED, never silently missing",
      store["db-skip"].style.display === "" && store["db-skip"].textContent.includes("renewals"),
      JSON.stringify(store["db-skip"]));
render({ as_of: "2026-09-21", cards: [{ key: "k", title: "T", count: 1, href: "/x", tone: "do", items: [] }], skipped: [], total: 1 });
check("...and the warning clears when the feeds are healthy", store["db-skip"].style.display === "none");

console.log("Peek is a peek");
const many = Array.from({ length: 9 }, (_, i) => ({ label: "P" + i, meta: "m", href: "/p" + i }));
render({ as_of: "x", cards: [{ key: "k", title: "T", count: 9, href: "/all", tone: "do", items: many }], skipped: [] });
out = store["db-body"].innerHTML;
check("at most five rows are peeked", (out.match(/<li>/g) || []).length === 5, (out.match(/<li>/g) || []).length);
check("the rest are a +N more link to the owning page", out.includes("+4 more") && out.includes('href="/all"'));

console.log("Escaping");
render({ as_of: "x", cards: [{ key: "k", title: '<img src=x onerror=alert(1)>', count: 1, href: "/x", tone: "do",
                               items: [{ label: "<script>bad()</script>", meta: "", href: "/y" }] }], skipped: [] });
out = store["db-body"].innerHTML;
check("a card title cannot inject markup", !out.includes("<img src=x") && out.includes("&lt;img"), out.slice(0, 160));
check("nor can a row label", !out.includes("<script>bad"), out.slice(0, 200));

console.log(FAIL.length ? `\n${FAIL.length} FAILURE(S): ${FAIL}` : "\nALL PASS");
process.exit(FAIL.length ? 1 : 0);
