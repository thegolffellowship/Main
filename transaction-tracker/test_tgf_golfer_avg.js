/**
 * GOLFERS rail: average won per EVENT PLAYED under the total (Kerry
 * 2026-09-21: "total/events played... not total / events won something").
 * Run: node test_tgf_golfer_avg.js
 */
const fs = require("fs");
let failures = 0;
function check(label, cond, detail) {
    if (cond) console.log("  PASS  " + label);
    else { console.log("  FAIL  " + label + (detail ? "  " + detail : "")); failures++; }
}
const html = fs.readFileSync("templates/tgf.html", "utf8");
const fn = html.slice(html.indexOf("function railAvg(g)"), html.indexOf("function renderGolfersSidebar()"));
check("the denominator is events PLAYED (events_entered), never the paying-event count alone",
    /const played = g\.events_entered \|\| g\.events_played \|\| 0;/.test(fn) && /g\.total_winnings \/ played/.test(fn));
check("the rail prints it under the total in the same 11px style as the event count",
    html.includes('<div class="glf-sub glf-avg">${fmt(railAvg(g))} avg / event</div>')
    && /\.glf-sub \{ font-size: 11px;/.test(html));
check("events_entered is what the server publishes as events played",
    /w\["events_entered"\] = max\(played\.get\(w\["id"\], 0\)/.test(fs.readFileSync("email_parser/database.py", "utf8")));
console.log("\n" + (failures ? failures + " FAILURE(S)" : "ALL PASS"));
process.exit(failures ? 1 : 0);
