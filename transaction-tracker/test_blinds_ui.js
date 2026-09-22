/**
 * The BLINDS button shows its cards at once (Kerry 2026-09-22: "nothing
 * showed up in the open spot until I collapsed and reopened the event").
 * Run: node test_blinds_ui.js
 */
const fs = require("fs");
let failures = 0;
function check(label, cond, detail) {
    if (cond) console.log("  PASS  " + label);
    else { console.log("  FAIL  " + label + (detail ? "  " + detail : "")); failures++; }
}
const html = fs.readFileSync("templates/events.html", "utf8");
const fn = html.slice(html.indexOf("async function drawBlinds("), html.indexOf("// ROSTER-ONLY REFRESH"));
check("drawBlinds exists", fn.length > 200);
check("after OK the sheet is patched from the apply response, not re-read (no loadPairings wait)",
      !/await loadPairings\(evId\)/.test(fn) && /\(wd\.drawn \|\| \[\]\)\.concat\(wd\.covered_by_existing \|\| \[\]\)/.test(fn));
check("each drawn seat lands on its group's blinds by holes + group + cart_pos",
      /_findGroup\(st, String\(b\.holes\), b\.group_num\)/.test(fn) && /filter\(x => x\.cart_pos !== b\.cart_pos\)/.test(fn));
check("the redraw cleared app-drawn blinds first, and the cards mirror that (GG-sourced ones stay)",
      /filter\(b => b\.source && b\.source !== 'app'\)/.test(fn));
check("the cached blind pool is dropped (counts moved)", /st\.blindPool = null/.test(fn));
check("…and the detail redraws immediately", /rerenderDetail\(container, ev\)/.test(fn));
check("the single-seat path patches the same way (the standard both share)",
      /async function blindSeat\(ctx, body\)/.test(html) && /grp\.blinds\.push\(\{cart_pos: ctx\.cartPos,/.test(html));
console.log("\n" + (failures ? failures + " FAILURE(S)" : "ALL PASS"));
process.exit(failures ? 1 : 0);
