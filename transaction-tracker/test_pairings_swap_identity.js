/**
 * A swap moves the PERSON, not three of their fields.
 *
 * Kerry 2026-09-18 (s18.11 Cedar Creek): "Looks like pairings switched
 * Jeff Rideout and Justin Angelone's tees when I swapped their cart
 * assignments."
 *
 * _swapPlayers / _swapCartPairs moved name, tee and index between seats
 * and left customer_id on the seat. Save stored "Jeff Rideout" with
 * Angelone's id; the server resolves tee and locked index by id and
 * answered for the other man. Now every field but cart_pos travels.
 *
 * Run: node test_pairings_swap_identity.js
 */
const fs = require("fs");
let failures = 0;
function check(label, cond, detail) {
    if (cond) console.log("  PASS  " + label);
    else { console.log("  FAIL  " + label + (detail ? "  " + detail : "")); failures++; }
}
const html = fs.readFileSync("templates/events.html", "utf8");
const fnSrc = html.slice(html.indexOf("function _swapSeatPayloads(pA, pB)"), html.indexOf("function _swapPlayers("));
check("the helper exists and spares only cart_pos", /keys\.delete\('cart_pos'\)/.test(fnSrc));
// Behavioural: run the helper on two seats.
const fn = new Function(fnSrc + "; return _swapSeatPayloads;")();
const a = {name: "Jeff Rideout", customer_id: 6, tee_choice: "50-64", handicap_index: 13.6, cart_pos: 2, is_new: false};
const b = {name: "Justin Angelone", customer_id: 900, tee_choice: "<50", handicap_index: 7.4, cart_pos: 3, is_new: true};
fn(a, b);
check("names swap", a.name === "Justin Angelone" && b.name === "Jeff Rideout");
check("customer_id travels with the name", a.customer_id === 900 && b.customer_id === 6, JSON.stringify([a, b]));
check("tee travels with the name", a.tee_choice === "<50" && b.tee_choice === "50-64");
check("every other field travels too (badges)", a.is_new === true && b.is_new === false);
check("the seats stay put", a.cart_pos === 2 && b.cart_pos === 3);
check("_swapPlayers uses it", /_swapSeatPayloads\(pA, pB\)/.test(html.slice(html.indexOf("function _swapPlayers("), html.indexOf("function _swapCartPairs("))));
check("_swapCartPairs uses it", /_swapSeatPayloads\(pairsA\[i\], pairsB\[i\]\)/.test(html));
check("no hand-picked three-field swap survives", !/\[pA\.tee_choice, pB\.tee_choice\]/.test(html) && !/pairsA\[i\]\.tee_choice, pairsB\[i\]\.tee_choice/.test(html));
check("a player seated from Unassigned carries the roster entry whole (customer_id included)",
    /player = Object\.assign\(\{\}, found\);/.test(html));
console.log("\n" + (failures ? failures + " FAILURE(S)" : "ALL PASS"));
process.exit(failures ? 1 : 0);
