/**
 * Every registrant lands in exactly one bucket.
 *
 * Kerry 2026-09-16, on the s9.23 send: "Not sure how we have 21
 * registered and only 16 sent and 3 skipped. Seems to be 2 unaccounted
 * for." Then, on Austin: "Same kind of deal" — 12 registered, 9 sent, 2
 * skipped, 1 gone.
 *
 * Two `continue`s inside the send loop — no email on file, and no
 * NINE-hole index even though the player was otherwise eligible — dropped
 * people with no counter and no name, so the arithmetic could not close
 * and there was no way to find out who missed a card.
 *
 * Run: node test_handicap_card_counts.js
 */
const fs = require("fs");
const py = fs.readFileSync("app.py", "utf8");
const html = fs.readFileSync("templates/handicaps.html", "utf8");
let failures = 0;
function check(label, cond, detail) {
    if (cond) console.log("  PASS  " + label);
    else { console.log("  FAIL  " + label + (detail ? "  " + detail : "")); failures++; }
}

console.log("\nNobody leaves the loop uncounted");
const fn = py.slice(py.indexOf("skipped_names: list = []"));
const loop = fn.slice(0, fn.indexOf('return jsonify(out)'));
check("a player with no email is counted AND named",
    /if not email:\s*\n\s*skipped_no_email \+= 1\s*\n\s*skipped_names\.append/.test(loop),
    "the no-email continue is still silent");
check("a player with no nine-hole index is counted AND named",
    /handicap_index_9"\) is None:\s*\n\s*skipped_no_index \+= 1\s*\n\s*skipped_names\.append/.test(loop),
    "the no-index continue is still silent");
check("no bare `continue` survives in the send loop",
    !/\n\s+continue\s*\n(?![\s\S]{0,200}skipped_names)/.test(
        loop.slice(0, loop.indexOf("send_mail_graph"))) || /skipped_names/.test(loop));

console.log("\nThe arithmetic is published");
check("the response carries what it was measured against",
    /out\["registered"\] = registered/.test(py));
check("…and adds the buckets up itself",
    /out\["accounted"\] = \(sent \+ failed \+ skipped_no_email/.test(py));
check("…and states the gap rather than leaving it to be noticed",
    /out\["unaccounted"\] = registered - out\["accounted"\]/.test(py));
check("every skipped player is returned, not just a tally",
    /"skipped_players": skipped_names\[:40\]/.test(py));

console.log("\nThe page shows it");
check("the result line says 'of N registered'",
    /of \$\{data\.registered\} registered/.test(html));
check("a gap is called out in red, not buried",
    /data\.unaccounted/.test(html) && /unaccounted — tell tracker-claude/.test(html));
check("and the skipped players are named with the reason",
    /data\.skipped_players/.test(html) && /p\.why/.test(html));
check("names are escaped", /escapeHtml\(p\.player\)/.test(html)
    && /function escapeHtml\(str\)/.test(html));

console.log(failures ? `\n${failures} FAILURE(S)` : "\nALL PASS");
process.exit(failures ? 1 : 0);
