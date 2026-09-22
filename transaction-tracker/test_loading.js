/**
 * LOADING… — the page-wide in-flight indicator (Kerry 2026-09-22: "We
 * need some type of 'LOADING...' visual for our pages.").
 *
 * The contract: loading.js wraps window.fetch, counts what is in flight,
 * shows a top bar after a short delay (no flicker on fast pages) and a
 * "Loading…" label after a longer one, hides when the count returns to
 * zero — and the shell include loads it FIRST, without defer, so no
 * page script can fetch before it is wrapped. Run under a tiny DOM stub
 * so the REAL file is exercised, not a restatement of it.
 *
 * Run: node test_loading.js
 */
const fs = require("fs"), path = require("path"), vm = require("vm");
const read = f => fs.readFileSync(path.join(__dirname, f), "utf8");
let fails = 0;
const ck = (l, c, d = "") => { console.log((c ? "  PASS  " : "  FAIL  ") + l + (c ? "" : "  " + d)); if (!c) fails++; };

console.log("== the shell loads it first ==");
const tpl = read("templates/_shell_nav.html");
const i = tpl.indexOf('<script src="/static/js/loading.js"></script>');
ck("the shell include loads /static/js/loading.js", i >= 0);
ck("...before any markup or other script (first tag after the header comment)", i >= 0 && !/<(script|header|nav|div)\b/.test(tpl.slice(0, i)));
ck("...and NOT deferred (fetch must be wrapped before page scripts run)", !/loading\.js"[^>]*defer/.test(tpl));

console.log("== the events page does not refresh a hidden tab ==");
const ev = read("templates/events.html");
const ar = ev.indexOf("Auto-refresh every 30s");
ck("the 30 s auto-refresh returns at once when document.hidden (no 2.6 MB pull for a tab nobody is looking at)",
   ar >= 0 && /setInterval\(async \(\) => \{\s*if \(document\.hidden\) return;/.test(ev.slice(ar, ar + 800)));

console.log("== the script under a DOM stub ==");
const src = read("static/js/loading.js");
ck("no 768/769 breakpoint (the ONE mobile breakpoint is 560)", !/76[89]px/.test(src));
function makeWorld() {
    const timers = [];
    const els = [];
    const mk = tag => ({ tag, id: "", classes: new Set(), textContent: "", attrs: {},
        classList: { add(c) { this._e.classes.add(c); }, remove(c) { this._e.classes.delete(c); }, contains(c) { return this._e.classes.has(c); } },
        setAttribute(k, v) { this.attrs[k] = v; }, appendChild() {} });
    const create = tag => { const e = mk(tag); e.classList._e = e; els.push(e); return e; };
    let resolveFetch = null, rejectFetch = null;
    const world = {
        document: { readyState: "complete", head: { appendChild() {} }, body: { appendChild() {} },
                    createElement: create, addEventListener() {} },
        window: { fetch: () => new Promise((res, rej) => { resolveFetch = res; rejectFetch = rej; }) },
        setTimeout: (fn, ms) => { timers.push({ fn, ms, id: timers.length + 1 }); return timers.length; },
        clearTimeout: id => { const t = timers.find(t => t.id === id); if (t) t.dead = true; },
        console,
    };
    world.window.document = world.document; world.self = world.window;
    vm.createContext(world);
    vm.runInContext(src, world);
    const fire = ms => timers.filter(t => !t.dead && !t.fired && t.ms === ms).forEach(t => { t.fired = true; t.fn(); });
    const bar = () => els.find(e => e.id === "tgf-loading-bar"), label = () => els.find(e => e.id === "tgf-loading-label");
    return { world, fire, bar, label, resolve: () => resolveFetch && resolveFetch({ ok: true }), reject: () => rejectFetch && rejectFetch(new Error("x")) };
}
let W = makeWorld();
ck("window.fetch is wrapped and window.tgfLoading exposed", typeof W.world.window.fetch === "function" && W.world.window.tgfLoading && typeof W.world.window.tgfLoading.start === "function");
ck("the bar and label exist in the DOM, hidden", W.bar() && W.label() && !W.bar().classList.contains("on") && !W.label().classList.contains("on"));
const p = W.world.window.fetch("/api/items");
ck("a fetch in flight counts as one", W.world.window.tgfLoading.inflight() === 1);
ck("nothing shows immediately (no flicker on a fast answer)", !W.bar().classList.contains("on"));
W.fire(150);
ck("after 150 ms the top bar is on", W.bar().classList.contains("on"));
ck("...the label is not yet", !W.label().classList.contains("on"));
W.fire(800);
ck("after 800 ms the Loading… label is on too", W.label().classList.contains("on") && W.label().textContent === "Loading…");
W.resolve();
(async () => {
    await p;
    ck("the fetch resolves through the wrapper with its response", true);
    ck("the count returns to zero", W.world.window.tgfLoading.inflight() === 0);
    W.fire(120);
    ck("...and after the hide delay both bar and label are off", !W.bar().classList.contains("on") && !W.label().classList.contains("on"));

    // a failing fetch also ends the count
    W = makeWorld();
    const q = W.world.window.fetch("/x").catch(() => "caught");
    W.reject();
    const r = await q;
    ck("a rejected fetch still decrements (and the rejection reaches the caller)", r === "caught" && W.world.window.tgfLoading.inflight() === 0);

    // two overlapping fetches: one bar, off only when both are done
    W = makeWorld();
    const a = W.world.window.fetch("/a"); W.world.window.tgfLoading.start();
    W.fire(150);
    ck("overlapping work: still on while any is in flight", W.bar().classList.contains("on") && W.world.window.tgfLoading.inflight() === 2);
    W.resolve(); await a;
    ck("...one finishing leaves the count at 1", W.world.window.tgfLoading.inflight() === 1);
    W.world.window.tgfLoading.end();
    ck("...manual end() balances to 0", W.world.window.tgfLoading.inflight() === 0);
    ck(".tgf-loading placeholder class is defined (pulsing Loading… text for a panel)", src.includes(".tgf-loading{") && src.includes("Loading\\\\2026"));

    console.log();
    if (fails) { console.log("FAILED (" + fails + ")"); process.exit(1); }
    console.log("ALL PASS");
})();
