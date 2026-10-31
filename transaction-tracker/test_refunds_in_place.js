/**
 * REFUNDS board works like Unpaid (Kerry 2026-10-30): a tapped Venmo refund
 * stays in Outstanding as "Sent · verifying…" (no separate In Flight list),
 * and a credit with no Venmo handle on file still gets a Venmo pill.
 * Run: node test_refunds_in_place.js
 */
const fs = require("fs");
let failures = 0;
function check(label, cond, detail) {
    if (cond) console.log("  PASS  " + label);
    else { console.log("  FAIL  " + label + (detail ? "  " + detail : "")); failures++; }
}
const html = fs.readFileSync("templates/tgf.html", "utf8");
const a = html.indexOf("const REFUND_VERIFYING_PILL");
const b = html.indexOf("function renderRefunds(data)");
const c = html.indexOf("// ── Data loading");
global.navigator = { userAgent: "desktop" };
global.window = {};
require("./static/js/refund-memo.js");
const el = { innerHTML: "" };
const ctx = `
const $ = () => el; let payFilter = "refunds";
const fmt = v => "$" + Number(v || 0).toFixed(2);
const escR = s => String(s == null ? "" : s);
const playerCell = (n, id, ev) => n + " | " + ev;
const ageChip = d => d + "d"; const fmtDate = d => d;
${html.slice(a, html.indexOf("\n", a))}
function _refundPollSoon() {}
${html.slice(html.indexOf("const REFUND_VERIFY_MS"), html.indexOf("\n", html.indexOf("const REFUND_VERIFY_MS")))}
${html.slice(b, c)}
renderRefunds(DATA);`;
const DATA = {
    totals: { outstanding_count: 1, outstanding_amount: 58, in_flight_count: 2, in_flight_amount: 184.02 },
    outstanding: [{ item_id: 2673, customer: "Will Wallace", customer_id: 697, event: "s9.23 THE QUARRY",
                    amount: 58, venmo_handle: null, memo: "Will Wallace - Refund for s9.23 The Quarry", age_days: 45 }],
    in_flight: [{ item_id: 3202, customer: "Mary Wade", customer_id: 23, event: "s9.28 TPC CANYONS",
                  amount: 92.01, method: "Venmo", handle: "mary-wade-10", age_days: 0,
                  initiated_at: new Date(Date.now() - 60 * 1000).toISOString().slice(0, 19).replace("T", " ") },
                { item_id: 3201, customer: "Jeff Young", customer_id: 88, event: "s9.28 TPC CANYONS",
                  amount: 92.01, method: "Venmo", handle: "jeff-young-66", age_days: 0,
                  memo: "Jeff Young - Refund for s9.28 TPC Canyons",
                  initiated_at: new Date(Date.now() - 40 * 60 * 1000).toISOString().slice(0, 19).replace("T", " ") }],
    completed: [], referrals: { owed: [], paid: [], comped: [] },
};
try { new Function("el", "DATA", ctx)(el, DATA); } catch (e) { console.log(e); failures++; }
const out = el.innerHTML;
check("no separate In Flight section", !/>In Flight</.test(out));
check("the tapped refund sits in Outstanding as Sent · verifying…",
      /Mary Wade[\s\S]*Sent · verifying/.test(out) && !/watching…/.test(out));
check("Outstanding counts all (3 items, $242.02)", /\$242\.02[\s\S]{0,200}3 items/.test(out), out.slice(0, 600));
check("after 5 minutes a tapped refund gets its Venmo button back (Kerry 10/30)",
      /href="https:\/\/venmo\.com\/jeff-young-66\?txn=pay&amount=92\.01&note=Jeff%20Young%20-%20Refund/.test(out)
      && !/Jeff Young[^<]*<\/[^>]*>[\s\S]{0,400}Sent · verifying/.test(out.slice(out.indexOf("Jeff Young"), out.indexOf("Jeff Young") + 600)));
check("no handle on file: a Venmo pill (amount + memo, pick the person in Venmo), not Refund…",
      /href="https:\/\/venmo\.com\/\?txn=pay&amount=58\.00&note=Will%20Wallace%20-%20Refund/.test(out)
      && /class="refund-venmo-pill" data-item="2673"/.test(out) && !/>Refund…</.test(out));
check("the tap flips the pill in place and polls",
      /a\.outerHTML = REFUND_VERIFYING_PILL/.test(html) && /_refundPollSoon\(\)/.test(html));
console.log("\n" + (failures ? failures + " FAILURE(S)" : "ALL PASS"));
process.exit(failures ? 1 : 0);
