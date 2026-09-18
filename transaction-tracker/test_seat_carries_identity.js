/**
 * A seat on the pairings page carries the PERSON, never a name alone.
 *
 * Kerry 2026-09-18: "EVERY person gets a customer_id, no matter what
 * their role is... customer_id is king." The swap that moved three
 * fields and left the id behind was the instance; this is the class:
 * every path that constructs or moves a seat object must carry
 * customer_id.
 *
 * Run: node test_seat_carries_identity.js
 */
const fs = require("fs");
let failures = 0;
function check(label, cond, detail) {
    if (cond) console.log("  PASS  " + label);
    else { console.log("  FAIL  " + label + (detail ? "  " + detail : "")); failures++; }
}
const html = fs.readFileSync("templates/events.html", "utf8");
// Every object literal that seats a person (has name + cart_pos and is
// pushed into a players/blinds array) must name customer_id.
const pushes = [...html.matchAll(/\.(players|blinds)\.push\((\{[\s\S]*?\})\)/g)];
check("there are seat pushes to audit", pushes.length >= 2, String(pushes.length));
for (const m of pushes) {
    const lit = m[2];
    if (!/name/.test(lit)) continue;
    check(`seat push carries customer_id: ${lit.replace(/\s+/g, " ").slice(0, 70)}`, /customer_id/.test(lit));
}
check("the swaps move the whole person", /function _swapSeatPayloads\(pA, pB\)/.test(html)
    && /_swapSeatPayloads\(pA, pB\)/.test(html) && /_swapSeatPayloads\(pairsA\[i\], pairsB\[i\]\)/.test(html));
check("a player seated from Unassigned is the roster entry whole", /player = Object\.assign\(\{\}, found\);/.test(html));
check("no hand-picked field swap remains", !/\[pA\.name, pB\.name\] = \[pB\.name, pA\.name\]/.test(html));
console.log("\n" + (failures ? failures + " FAILURE(S)" : "ALL PASS"));
process.exit(failures ? 1 : 0);
