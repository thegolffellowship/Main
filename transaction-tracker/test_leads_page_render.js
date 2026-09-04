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
global.document = { getElementById: id => store[id] || (store[id] = el(id)),
    querySelectorAll: () => [], querySelector: () => null, addEventListener() {},
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
    eval(js + "\nglobal.__render = renderLeads; global.__setALL = v => { ALL = v; };");
    render = global.__render; setALL = global.__setALL;
    console.log("  PASS  the page script evaluates");
} catch (e) {
    console.log("  FAIL  the page script evaluates  " + e.message);
    process.exit(1);
}

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

// An 'auto' note is BOOKKEEPING, not a reply. Counting it made every
// lead the 48-hour alarm ever armed read as RESPONDED, and the v2.301.x
// backfill flipped 49 people at once on the screen Kerry uses to decide
// who still needs chasing.
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

// Empty queue must say so rather than render blank.
setALL({ ...ALL, leads: [] });
try { render(); } catch (e) { check("empty queue renders", false, e.message); }
check("an empty queue shows an empty-state, never a blank page",
      store["ld-mlist"].innerHTML.length > 0
      || store["ld-dlist"].innerHTML.length > 0);

console.log("");
if (FAILURES.length) {
    console.log(FAILURES.length + " FAILURE(S): " + FAILURES.join(", "));
    process.exit(1);
}
console.log("ALL PASS");
