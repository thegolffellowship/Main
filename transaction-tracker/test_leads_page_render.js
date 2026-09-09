/**
 * Lead Center page render (regression guard, 2026-09-04).
 *
 * v2.300.0 collapsed the P1-P4 presets from per-slot keys to a single
 * `text`, and a legacy line in /api/leads kept indexing ["tue"]. That
 * KeyError 500'd the route, and because the page wrote its error banner
 * only into the DESKTOP container — display:none under 768px — the Lead
 * Center rendered as a BLANK PAGE on the phone. Nothing in the suite
 * touched the page itself, so every test stayed green while the surface
 * Kerry works from was down.
 *
 * This runs the page's own script headless and renders real-shaped
 * leads: a backfilled one (outreach_at + a past follow_up_at), a fresh
 * untouched one, a converted member, and one whose server-side SMS pick
 * failed (sms: null) — the case the route's try/except actually
 * produces.
 *
 * Run: node test_leads_page_render.js
 */
const fs = require("fs");
const path = require("path");

const FAILURES = [];
const check = (label, cond, detail) => {
    if (cond) console.log("  PASS  " + label);
    else { console.log("  FAIL  " + label + "  " + (detail || "")); FAILURES.push(label); }
};

// ---- extract the page's inline script ------------------------------
const html = fs.readFileSync(path.join(__dirname, "templates/leads.html"), "utf8");
const blocks = [...html.matchAll(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)]
    .map(m => m[1]);
let js = blocks.sort((a, b) => b.length - a.length)[0]
    .replace(/\{%[\s\S]*?%\}/g, "")
    .replace(/\{\{[\s\S]*?\}\}/g, "null");

// ---- the smallest DOM the script needs -----------------------------
const store = {};
const el = id => ({ id, innerHTML: "", style: {}, value: "", dataset: {},
    checked: false, classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    addEventListener() {}, querySelectorAll: () => [], querySelector: () => null,
    closest: () => null, appendChild() {}, remove() {} });

// The menus the page can open, and the document listeners it installs.
// The stub used to swallow both, which is exactly why the "menu never
// closes" bug reached Kerry's phone: nothing here could see a click.
const MENUS = [];
const LISTENERS = { click: [], keydown: [] };
const CAPTURE = {};
const COPIED = [];
// A click target that answers closest() the way a browser would, from a
// declared list of the classes on it and its ancestors.
const target = (...classes) => ({
    closest: sel => sel.split(",").map(x => x.trim().replace(".", ""))
        .some(c => classes.includes(c)) ? {} : null,
});
const dispatch = (type, ev) => LISTENERS[type].forEach(fn => fn(ev));

global.document = { getElementById: id => store[id] || (store[id] = el(id)),
    querySelectorAll: sel => (sel === ".ld-menu" ? MENUS : []),
    querySelector: () => null,
    addEventListener: (type, fn, capture) => {
        (LISTENERS[type] || []).push(fn);
        CAPTURE[type] = CAPTURE[type] || [];
        CAPTURE[type].push(!!capture);
    },
    execCommand: () => (COPIED.push("execCommand"), true),
    createElement: () => el("x"), body: el("body"), documentElement: el("html") };
global.window = { location: { search: "", href: "" }, addEventListener() {},
    matchMedia: () => ({ matches: false, addEventListener() {} }) };
global.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };
global.sessionStorage = global.localStorage;
global.navigator = {};
global.fetch = () => Promise.resolve({ ok: true, status: 200, json: () => ({}) });
global.initAuth = () => {}; global.onAuthReady = () => {};
global.currentRole = "admin"; global.shellApplyRole = () => {};

let render, setALL;
try {
    eval(js + "\nglobal.__render = renderLeads; global.__setALL = v => { ALL = v; };"
            + "\nglobal.__F = { toggleSection,"
            + " setSearch: v => { searchQ = v; renderLeads(); },"
            + " setStatus: v => { statusFilter = v; renderLeads(); },"
            + " toggleMenu, closeAllMenus, copyLeadEmail, menuHead,"
            + " setStats: v => { STATS = v; renderStats(); } };");
    render = global.__render; setALL = global.__setALL;
    console.log("  PASS  the page script evaluates");
} catch (e) {
    console.log("  FAIL  the page script evaluates  " + e.message);
    process.exit(1);
}
const F = global.__F;

// ---- realistic payload ---------------------------------------------
const P = {
    p1: { label: "Competition", text: "Hey {first_name}, {owner} here. {cadence}. Next one{chapter} is {when} at {course}{start_phrase}.{price_block}" },
    p2: { label: "Golf", text: "Hey {first_name}, {owner} here. {cadence}.{price_block}" },
    p3: { label: "Community", text: "Hey {first_name}, {owner} here." },
    p4: { label: "General", text: "Hey {first_name}, {owner} here. {cadence}." },
    p6: { label: "No days", text: "Hey {first_name}." },
    p7: { label: "Nudge", text: "Hey {first_name}." },
    p7b: { label: "Nudge 2", text: "Hey {first_name}." },
    p8: { label: "Re-submitter", text: "Hey {first_name}." },
    p9: { label: "Both cities", text: "BTW you marked both.{other_chapter_event}" },
    closer: { text: "Want a spot?" },
    price_block: { text: " {first_timer_price} is our 1st Time rate.",
                   no_games: " {first_timer_price} is our 1st Time rate." },
};
const VARS = { first_name: "Bruno", owner: "Kerry", cadence: "Tuesday 9s",
    chapter: "", when: "Tuesday", course: "Silverhorn", start_phrase: ", 5:30p shotgun",
    first_timer_price: "$49", range_balls: "", gross_bundle: "$16",
    other_chapter_event: "", next_tue: "Tuesday 9/8", next_sat: "Saturday 9/19",
    next_event: "Tuesday 9/8", _price_known: true };
const base = {
    source: "hubspot", external_id: "1", city: null, notes: null,
    customer_id: 700, campaign_id: 1, campaign_name: "Fall 2026 Leads",
    merged_into: null, converted_at: null, source_label: "FORM",
    has_history: false, follow_up_notified_for: null, touched_by: null,
    payload: { can_you_play_tuesdays_or_saturdays: "yes_-_i_can_play_both_tuesdays_or_saturdays",
        which_is_most_important_to_you: "golf_-_explore_a_variety_of_courses_and_play_as_much_as_possible",
        would_you_like_to_stay_in_the_loop_with_tgf_and_receive_event_invitations: "yes_for_san_antonio",
        ad_set_name: "SA - Fall 2026 Leads" },
};
const sms = p => ({ preset: p, slot: "both", addons: [], why: "golf · both", vars: VARS });
const leads = [
    // Backfilled: the v2.301.x shape — outreach_at set, follow_up_at past.
    { ...base, id: 3, first_name: "Bruno", last_name: "Ramos", email: "b@x.com",
      phone: "+12105550000", chapter: "San Antonio", status: "touched", tag: "Texted",
      touched_at: "2026-08-28 13:42:46", arrived_at: "2026-08-27T10:00:00Z",
      days_since_arrival: 7, outreach_at: "2026-08-28 13:42:46",
      follow_up_at: "2026-08-30", sms: sms("p2"),
      notes_log: [{ author: "auto", note: "48-hour follow-up backfilled from the Texted tag (2026-08-28) — due 2026-08-30", created_at: "2026-09-04 00:55:00" }] },
    { ...base, id: 4, first_name: "Fresh", last_name: "Lead", email: "f@x.com",
      phone: null, chapter: "Austin", status: "new", tag: null, touched_at: null,
      arrived_at: "2026-09-04T10:00:00Z", days_since_arrival: 0, outreach_at: null,
      follow_up_at: null, notes_log: [], sms: sms("p1") },
    { ...base, id: 5, first_name: "Sam", last_name: "Member", email: "s@x.com",
      phone: null, chapter: "San Antonio", status: "converted", tag: "Became member",
      touched_at: "2026-08-20 10:00:00", arrived_at: "2026-08-19T10:00:00Z",
      days_since_arrival: 16, outreach_at: null, follow_up_at: null,
      notes_log: [], sms: sms("p4") },
    // The route sets sms = None when the server-side pick throws.
    { ...base, id: 6, first_name: "Nosms", last_name: "Lead", email: "n@x.com",
      phone: null, chapter: null, status: "touched", tag: "Left VM",
      touched_at: "2026-09-01 22:00:00", arrived_at: "2026-09-01T10:00:00Z",
      days_since_arrival: 3, outreach_at: "2026-09-01 22:00:00",
      follow_up_at: "2026-09-03", notes_log: [], sms: null },
];
const ALL = { leads, by_ad_set: {}, sms_template: P.p4.text, next_events: {},
    sms_presets: P, sms_order: ["p1", "p2", "p3", "p4", "p6", "p7", "p7b", "p8"],
    sms_p9_presets: ["p1", "p2", "p3", "p4", "p8"], campaigns: [],
    tag_options: ["Texted", "Left VM", "Interested", "Became member"],
    answer_options: {} };

setALL(ALL);
let threw = null;
try { render(); } catch (e) { threw = e; }
check("renderLeads() does not throw on real-shaped leads",
      !threw, threw && (threw.constructor.name + ": " + threw.message));
if (threw) process.exit(1);

const mob = store["ld-mlist"].innerHTML;
const desk = store["ld-dlist"].innerHTML;
check("the MOBILE list is populated — the surface Kerry works from",
      mob.length > 200, "bytes=" + mob.length);
check("the desktop list is populated", desk.length > 200, "bytes=" + desk.length);
for (const name of ["Bruno", "Fresh", "Sam"]) {
    check(`${name} renders in the mobile list`, mob.includes(name));
}
check("a lead whose server-side SMS pick failed still renders",
      mob.includes("Nosms"));
check("the backfilled ⏰ alarm chip renders", mob.includes("⏰"));
check("no unsubstituted placeholder leaks into a message",
      !/\{(first_name|owner|cadence|price_block|first_timer_price)\}/.test(mob),
      (mob.match(/\{[a-z_]+\}/g) || []).slice(0, 5).join(" "));
check("nor into the desktop list",
      !/\{(first_name|owner|cadence|price_block|first_timer_price)\}/.test(desk),
      (desk.match(/\{[a-z_]+\}/g) || []).slice(0, 5).join(" "));

// v2.324.0: the Email picker renders the same preset preview the Text
// picker does, so it hit the SAME trap on a lead whose server-side pick
// failed — a half-filled template with {cadence} still in it, next to a
// button offering to mail it to a stranger. No preset, no send button.
check("a lead with no usable preset is offered a plain compose link, "
      + "never a half-rendered one",
      !/ld-emsend-[md]-6\b/.test(mob + desk),
      "Nosms still shows a Send button");

// An 'auto' note is BOOKKEEPING, not a reply. Counting it made every
// lead the 48-hour alarm ever armed read as RESPONDED, and the v2.301.x
// backfill flipped 49 people at once on the screen Kerry uses to decide
// who still needs chasing.
// Kerry 2026-09-05: "The text preset choice tab doesn't collapse easily.
// It should go away once something else is clicked like when you click
// text." It used to close ONLY when another menu opened, so tapping
// Text / Call / Note left it sitting over the next card.
console.log("The preset menu dismisses like a menu");
const menu = document.getElementById("ld-smsmenu-m-1");
MENUS.push(menu);
F.toggleMenu("ld-smsmenu-m-1");
check("opening it shows it", menu.style.display === "block", menu.style.display);

dispatch("click", { target: target("ld-smspk") });
check("tapping the picker itself does NOT close it — its own handler owns that",
      menu.style.display === "block", menu.style.display);

dispatch("click", { target: target("ld-btn", "ld-menu") });
check("choosing a preset INSIDE the menu keeps it open, so the preview "
      + "can update", menu.style.display === "block", menu.style.display);

dispatch("click", { target: target("cell-link") });
check("tapping Text closes it", menu.style.display === "none", menu.style.display);

F.toggleMenu("ld-smsmenu-m-1");
dispatch("click", { target: target("ld-act") });
check("so does tapping Call or Note", menu.style.display === "none", menu.style.display);

F.toggleMenu("ld-smsmenu-m-1");
dispatch("click", { target: target("ld-dcard") });
check("so does tapping anywhere else on the page",
      menu.style.display === "none", menu.style.display);

F.toggleMenu("ld-smsmenu-m-1");
dispatch("keydown", { key: "Escape" });
check("and Escape closes it", menu.style.display === "none", menu.style.display);

F.toggleMenu("ld-smsmenu-m-1");
F.toggleMenu("ld-smsmenu-m-1");
check("tapping the picker twice toggles it shut",
      menu.style.display === "none", menu.style.display);

// Kerry 2026-09-05: "Don't collapse email and text things when I select a
// different preset within the modal." In BUBBLE phase the dismiss
// handler runs after pickSms() has replaced the menu's innerHTML, which
// detaches the clicked button — closest() then walks an orphaned node,
// finds no .ld-menu, and closes the menu the user is working in. Capture
// phase is the fix, so the phase itself is the thing worth asserting.
check("the dismiss handler is registered in CAPTURE phase, so a preset "
      + "button is still attached when it runs",
      (CAPTURE.click || []).some(c => c === true), CAPTURE.click);
MENUS.length = 0;

// Kerry asked for both of these directly.
console.log("Every menu has a title and a close button");
const head = F.menuHead("P7 · email");
check("it carries the menu's name", head.includes("P7 · email"), head);
check("and an X that closes it",
      head.includes("closeAllMenus()") && head.includes("&times;"), head);

// "Give me a copy email address button so I can copy to add to new
// contacts on my phone."
console.log("Copying a lead's email");
global.navigator.clipboard = { writeText: t => (COPIED.push(t), Promise.resolve()) };
const btn = { textContent: "Copy", classList: { toggle() {}, remove() {} } };
F.copyLeadEmail(3, btn);
check("it copies the address, not the name or the whole card",
      COPIED.length === 1 && COPIED[0] === "b@x.com", COPIED);
COPIED.length = 0;
F.copyLeadEmail(99999, btn);
check("a lead we do not have copies nothing rather than an empty string",
      COPIED.length === 0, COPIED);
check("the button reports back so a silent failure is impossible",
      btn.textContent !== "", btn.textContent);

const touchSub = () => store["ld-touch-sub"].textContent || "";
check("a lead whose only note is 'auto' is NOT counted as responded",
      /0 responded/.test(touchSub()), touchSub());
const withHuman = leads.map(l => l.id !== 3 ? l : { ...l,
    notes_log: [...l.notes_log, { author: "K", note: "he called back", created_at: "2026-09-04 01:00:00" }] });
setALL({ ...ALL, leads: withHuman });
render();
check("a human note DOES count as responded",
      /1 responded/.test(touchSub()), touchSub());
const withGG = leads.map(l => l.id !== 3 ? l : { ...l,
    notes_log: [...l.notes_log, { author: "GG", note: "RSVPd", created_at: "2026-09-04 01:00:00" }] });
setALL({ ...ALL, leads: withGG });
render();
check("a GG RSVP counts too — that is the person acting",
      /1 responded/.test(touchSub()), touchSub());
setALL(ALL); render();

// ---- sections: order + accordion (Kerry 2026-09-04) ----------------
console.log("Sections");
const barsOf = html => [...html.matchAll(/class="ld-secbar[^"]*"[^>]*data-sec="([^"]+)"/g)]
    .map(m => m[1]);
const order = barsOf(mob);
check("NEW LEADS outranks FOLLOW-UPS DUE",
      order.indexOf("NEW LEADS") >= 0
      && order.indexOf("NEW LEADS") < order.indexOf("FOLLOW-UPS DUE"), order);
check("each section appears exactly once — tier() and sectionOf() agree",
      order.length === new Set(order).size, order);
check("mobile gets section bars too, not just desktop",
      barsOf(desk).length === order.length, barsOf(desk));

const hiddenRows = h => (h.match(/class="ld-(?:drow|mcard)[^"]*"[^>]*hidden/g) || []).length;
const allRows = h => (h.match(/class="ld-(?:drow|mcard)[^"]*"/g) || []).length;
const secOf = h => [...h.matchAll(/class="ld-mcard[^"]*"\s+data-sec="([^"]+)"([^>]*)>/g)]
    .map(m => ({ sec: m[1], hidden: /hidden/.test(m[2]) }));
const LANDING = ["NEW LEADS", "FOLLOW-UPS DUE"];
check("the queue LANDS with New Leads and Follow-Ups Due open",
      secOf(mob).every(r => r.hidden === !LANDING.includes(r.sec)),
      JSON.stringify(secOf(mob)));
check("everything else lands collapsed",
      secOf(mob).some(r => r.hidden), JSON.stringify(secOf(mob)));
check("the collapsed bars still carry their counts",
      /class="n">· \d+/.test(mob), mob.slice(0, 200));

// "Then I'll collapse them if necessary" — closing one must not take
// the other with it.
F.toggleSection("NEW LEADS");
check("closing one landing section leaves the other open",
      secOf(store["ld-mlist"].innerHTML)
          .every(r => r.hidden === (r.sec !== "FOLLOW-UPS DUE")),
      JSON.stringify(secOf(store["ld-mlist"].innerHTML)));
F.toggleSection("FOLLOW-UPS DUE");
check("closing both leaves everything collapsed",
      secOf(store["ld-mlist"].innerHTML).every(r => r.hidden));

F.toggleSection("NEW LEADS");
const openMob = store["ld-mlist"].innerHTML;
const openRows = [...openMob.matchAll(/class="ld-mcard[^"]*"\s+data-sec="([^"]+)"([^>]*)>/g)]
    .map(m => ({ sec: m[1], hidden: /hidden/.test(m[2]) }));
check("only the open section's cards are visible",
      openRows.length > 0
      && openRows.every(r => r.hidden === (r.sec !== "NEW LEADS")),
      JSON.stringify(openRows));
check("the open bar shows a down chevron",
      /ld-secbar[^"]*open[^"]*"[^>]*data-sec="NEW LEADS"/.test(openMob),
      openMob.slice(0, 300));

F.toggleSection("FOLLOW-UPS DUE");
const swapped = [...store["ld-mlist"].innerHTML
    .matchAll(/class="ld-mcard[^"]*"\s+data-sec="([^"]+)"([^>]*)>/g)]
    .map(m => ({ sec: m[1], hidden: /hidden/.test(m[2]) }));
check("opening another auto-collapses the first — one at a time",
      swapped.every(r => r.hidden === (r.sec !== "FOLLOW-UPS DUE")),
      JSON.stringify(swapped));

F.toggleSection("FOLLOW-UPS DUE");
const reclosed = [...store["ld-mlist"].innerHTML
    .matchAll(/class="ld-mcard[^"]*"\s+data-sec="([^"]+)"([^>]*)>/g)]
    .map(m => /hidden/.test(m[2]));
check("clicking the open section closes it again",
      reclosed.length > 0 && reclosed.every(Boolean), reclosed);

// A search that finds people and then hides them behind collapsed bars
// is worse than no search at all.
setALL({ ...ALL, leads });
render();
F.toggleSection("NEW LEADS");            // land on a mostly-collapsed queue
F.toggleSection("NEW LEADS");
F.setSearch("bruno");
const searched = secOf(store["ld-mlist"].innerHTML);
check("a search opens every section that survived it",
      searched.length > 0 && searched.every(r => !r.hidden),
      JSON.stringify(searched));
F.setSearch("");
check("clearing the search restores the collapse state, not everything",
      secOf(store["ld-mlist"].innerHTML).some(r => r.hidden),
      JSON.stringify(secOf(store["ld-mlist"].innerHTML)));
F.setStatus("touched");
check("a status filter opens them too — the same trap",
      secOf(store["ld-mlist"].innerHTML).every(r => !r.hidden),
      JSON.stringify(secOf(store["ld-mlist"].innerHTML)));
F.setStatus("all");

// Empty queue must say so rather than render blank.
setALL({ ...ALL, leads: [] });
try { render(); } catch (e) { check("empty queue renders", false, e.message); }
check("an empty queue shows an empty-state, never a blank page",
      store["ld-mlist"].innerHTML.length > 0
      || store["ld-dlist"].innerHTML.length > 0);

// ---- Stats panel: the benchmark windows (Kerry 2026-09-09) --------
// 30/60/90/180/1y/lifetime columns must render, an open window must
// say so, and lifetime must carry no cut-off. Nothing else in the
// suite touched renderStats before this.
{
    const win = (players, members, cutoff, open) => ({ players, members, cutoff, open,
        cpp: players ? 199.62 / players : null, cpmem: members ? 199.62 / members : null });
    const funnel = { leads: 129, touched: 100, replied: 20, interested: 5, players: 6, members: 3,
        registered: 5, dismissed: 10, new: 9, players_trailing: 6, members_trailing: 3, reply_pct: 20,
        windows: {} };
    const windows = { "30": win(4, 2, "2026-10-06", true), "60": win(6, 3, "2026-11-05", true),
        "90": win(6, 3, "2026-12-05", true), "180": win(6, 3, "2027-03-05", true),
        "365": win(6, 3, "2027-09-06", true), "lifetime": win(6, 3, null, null) };
    const bucket = { id: 1, name: "Fall 2026", spend: 199.62, spend_source: "meta", end_date: "2026-09-06",
        trailing_cutoff: null, trailing_window_open: null, meta: {}, funnel, chapters: {},
        cost: { cpl: 1.55, cpp: 33.27, cpmem: 66.54, cpp_trailing: 33.27, cpmem_trailing: 66.54, windows },
        value: null, roi: null };
    try {
        F.setStats({ campaigns: [bucket], unattributed: bucket, all: bucket,
            trailing_days: null, benchmark_windows: [30, 60, 90, 180, 365], definitions: {} });
    } catch (e) { check("stats panel renders", false, e.message); }
    const sh = store["ld-stats"].innerHTML;
    check("stats panel renders the benchmark columns 30d … 1 yr … Lifetime",
          /<th[^>]*>30d/.test(sh) && /<th[^>]*>180d/.test(sh) && /<th[^>]*>1 yr/.test(sh)
          && /<th[^>]*>Lifetime/.test(sh), sh.slice(0, 400));
    check("an open window is marked open", /30d<span class="ld-dsub"> ·open<\/span>/.test(sh), sh.slice(0, 600));
    check("the 30-day CPP reads $49.91 /4", /\$49\.91<span class="ld-dsub"> \/4<\/span>/.test(sh), sh.slice(0, 900));
    check("lifetime carries no cut-off", /title="no cut-off">Lifetime/.test(sh));
    check("the window table scrolls inside its own container", /overflow-x:auto"><table class="ld-costtbl"><thead><tr><th><\/th><th>Current<\/th>/.test(sh));
}

console.log("");
if (FAILURES.length) {
    console.log(FAILURES.length + " FAILURE(S): " + FAILURES.join(", "));
    process.exit(1);
}
console.log("ALL PASS");
