/**
 * The "Who brought them" control — /static/js/referral_control.js.
 *
 * Kerry 2026-09-21: "How am I supposed to attribute him to Justin
 * Angelone?" This exercises the REAL shipped module, because the
 * previous thing shipped on this surface was a dashboard that rendered
 * fine and never ran its loader.
 *
 * The control is shared by three surfaces (customer Info tab, dashboard
 * modal, Leads band), so this also checks each host actually loads it
 * rather than keeping a private copy that can drift.
 */
const fs = require("fs"), path = require("path");
const FAIL = [];
const check = (l, c, d) => { console.log((c ? "  PASS  " : "  FAIL  ") + l + (c ? "" : "  " + (d || ""))); if (!c) FAIL.push(l); };

const read = f => fs.readFileSync(path.join(__dirname, f), "utf8");
const js = read("static/js/referral_control.js");
const html = read("templates/customers.html");
const dash = read("templates/dashboard.html");
const leadsHtml = read("templates/leads.html");

// The module registers document listeners at load; give it just enough
// DOM to do that without a browser.
global.window = {};
global.document = { addEventListener() {} };
require("./static/js/referral_control.js");
const T = window.TGFRef;
const R = {
    renderReferredByBlock: c => T.render(c),
    refPeopleOptions: id => T.peopleOptions(id),
    refResolveName: (t, id) => T.resolveName(t, id),
};

T.setPeople([
    { customer_id: 829, customer_name: "Ty Bubela" },
    { customer_id: 709, customer_name: "Justin Angelone" },
    { customer_id: 31, customer_name: "Robert Straiton" },
    { customer_id: 999, customer_name: "" },
]);

console.log("The block");
let out = R.renderReferredByBlock({ customer_id: 829 });
check("an unattributed customer says so plainly", out.includes("Nobody recorded yet"), out.slice(0, 200));
check("it carries the customer id for the delegated handlers", out.includes('data-refblock="829"'));
check("it offers a name picker", out.includes("data-refinput") && out.includes("data-refsave"));
check("it offers the not-a-referral list", out.includes("data-refvia") && out.includes("Facebook ad"));
check("no Clear button when there is nothing to clear", !out.includes("data-refclear"));

out = R.renderReferredByBlock({ customer_id: 829, referred_by_name: "Justin Angelone",
                                referred_by_source: "member_claim" });
check("an attributed customer shows the referrer", out.includes("Justin Angelone"), out.slice(0, 260));
check("...and HOW we know, in words", out.includes("told us"), out.slice(0, 300));
check("...and offers Clear", out.includes("data-refclear"));

out = R.renderReferredByBlock({ customer_id: 829, found_us_via: "facebook_ad" });
check("a channel answer reads as not a referral", out.includes("Not a referral") && out.includes("Facebook ad"), out.slice(0, 260));
check("the channel is preselected so it does not look unanswered", out.includes('value="facebook_ad" selected'));

check("a customer with no id renders nothing — there is nothing to key on",
      R.renderReferredByBlock({}) === "");
out = R.renderReferredByBlock({ customer_id: 1, referred_by_name: '<img src=x onerror=alert(1)>' });
check("a referrer name cannot inject markup", !out.includes("<img src=x") && out.includes("&lt;img"), out.slice(0, 200));

console.log("The picker");
const opts = R.refPeopleOptions(829);
check("it lists other customers", opts.includes("Justin Angelone") && opts.includes("Robert Straiton"));
check("it EXCLUDES the person themselves — nobody refers themselves", !opts.includes("Ty Bubela"), opts);
check("it skips nameless shell profiles", (opts.match(/<option/g) || []).length === 2, opts);

console.log("Resolving a typed name to an id (customer_id is the identity, #6)");
check("an exact name resolves", R.refResolveName("Justin Angelone", 829) === 709);
check("case and padding do not matter", R.refResolveName("  justin angelone ", 829) === 709);
check("an unknown name resolves to nothing rather than guessing",
      R.refResolveName("Somebody Else", 829) === null);
check("empty resolves to nothing", R.refResolveName("", 829) === null);
check("you cannot resolve to yourself", R.refResolveName("Ty Bubela", 829) === null);

console.log("Wiring");
check("the save handler posts to the referred-by endpoint",
      /"\/api\/customers\/" \+ cid \+ "\/referred-by"/.test(js));
check("Save sends a customer_id, never a name string",
      /referrer_customer_id: rid/.test(js));
check("Clear sends nulls for BOTH answers", /referrer_customer_id: null, found_us_via: null/.test(js));
check("the channel dropdown posts on change",
      /data-refvia/.test(js) && /found_us_via: ev\.target\.value \|\| null/.test(js));

console.log("One control, three surfaces");
check("the customer Info tab loads the shared module", /referral_control\.js/.test(html));
check("...and seeds the picker from the one canonical fetch it already does",
      /TGFRef\.setPeople\(canonList/.test(html));
check("the dashboard loads it", /referral_control\.js/.test(dash));
check("the Leads page loads it", /referral_control\.js/.test(leadsHtml));
check("no page keeps a private copy of the vocabulary",
      !/const FOUND_US_LABELS/.test(html) && !/const FOUND_US_LABELS/.test(dash)
      && !/const FOUND_US_LABELS/.test(leadsHtml));

console.log("Re-rendering after a save (no regex over our own markup)");
check("currentHtml is a function, not a scrape", typeof T.currentHtml === "function");
check("...and renders the saved answer", T.currentHtml(
      { referred_by_name: "Justin Angelone", referred_by_source: "member_claim" })
      .includes("Justin Angelone"));

console.log(FAIL.length ? `\n${FAIL.length} FAILURE(S): ${FAIL}` : "\nALL PASS");
process.exit(FAIL.length ? 1 : 0);
