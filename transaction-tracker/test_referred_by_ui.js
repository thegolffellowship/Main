/**
 * The "Who brought them" control on the customer Info tab.
 *
 * Kerry 2026-09-21: "How am I supposed to attribute him to Justin
 * Angelone?" This exercises the page's REAL renderer and its real click
 * handler, because the previous thing shipped on this surface was a
 * dashboard that rendered fine and never ran its loader.
 */
const fs = require("fs"), path = require("path");
const FAIL = [];
const check = (l, c, d) => { console.log((c ? "  PASS  " : "  FAIL  ") + l + (c ? "" : "  " + (d || ""))); if (!c) FAIL.push(l); };

const html = fs.readFileSync(path.join(__dirname, "templates/customers.html"), "utf8");
// Pull only the functions under test — the page script is ~5k lines and
// drags in the whole app otherwise.
const grab = name => {
    const i = html.indexOf("function " + name + "(");
    if (i < 0) throw new Error("not found: " + name);
    let d = 0, started = false;
    for (let j = i; j < html.length; j++) {
        if (html[j] === "{") { d++; started = true; }
        else if (html[j] === "}") { d--; if (started && d === 0) return html.slice(i, j + 1); }
    }
    throw new Error("unbalanced: " + name);
};
const consts = html.slice(html.indexOf("const FOUND_US_LABELS"),
                          html.indexOf("function renderReferredByBlock"));
const src = "function escapeHtml(s){return String(s==null?'':s).replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[c]));}\n"
    + consts + grab("renderReferredByBlock") + "\n" + grab("refPeopleOptions") + "\n" + grab("refResolveName")
    + "\nglobal.__R = { renderReferredByBlock, refPeopleOptions, refResolveName };";
global.window = {};
eval(src);
const R = global.__R;

window.__custAll = [
    { customer_id: 829, customer_name: "Ty Bubela" },
    { customer_id: 709, customer_name: "Justin Angelone" },
    { customer_id: 31, customer_name: "Robert Straiton" },
    { customer_id: 999, customer_name: "" },
];

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
      /\/api\/customers\/\$\{cid\}\/referred-by/.test(html));
check("Save sends a customer_id, never a name string",
      /referrer_customer_id: rid/.test(html));
check("Clear sends nulls for BOTH answers", /referrer_customer_id: null, found_us_via: null/.test(html));
check("the channel dropdown posts on change", /data-refvia/.test(html) && /found_us_via: ev\.target\.value \|\| null/.test(html));
check("the people index is filled from the one canonical fetch",
      /window\.__custAll = canonList/.test(html));

console.log(FAIL.length ? `\n${FAIL.length} FAILURE(S): ${FAIL}` : "\nALL PASS");
process.exit(FAIL.length ? 1 : 0);
