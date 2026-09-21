/**
 * A remembered PAIRINGS tab comes back on a phone too.
 *
 * Kerry 2026-09-18 (iPhone): "Had generated pairings, tweaked, saved,
 * then added blinds, then clicked Starter Sheet, then clicked back. Now
 * it's stuck on LOADING."
 *
 * iOS reloads the tab on return. The restore-on-load path re-opened the
 * event on PAIRINGS, loaded the sheet, then repainted the DESKTOP
 * container by id. The phone's container has a different id, so nothing
 * repainted and the panel sat on "Loading…" with the data already in
 * hand. Every after-the-fact repaint now resolves the container through
 * one helper that knows both layouts.
 *
 * Run: node test_events_restore_mobile.js
 */
const fs = require("fs");
let failures = 0;
function check(label, cond, detail) {
    if (cond) console.log("  PASS  " + label);
    else { console.log("  FAIL  " + label + (detail ? "  " + detail : "")); failures++; }
}
const html = fs.readFileSync("templates/events.html", "utf8");
const helper = html.slice(html.indexOf("function detailContainerFor(evId)"), html.indexOf("function rerenderDetail("));
check("the helper exists", helper.length > 0);
check("…and tries the desktop container", /detail-content-\$\{evId\}/.test(helper));
check("…then the mobile one", /ev-mobile-detail-\$\{evId\}/.test(helper));
check("both ids are the ones the two layouts actually render",
    html.includes('id="ev-mobile-detail-${ev.id}"') && html.includes('id="detail-content-${ev.id}"'));
const restore = html.slice(html.indexOf("const mem = readEventOpen();"), html.indexOf("const mem = readEventOpen();") + 900);
check("the restore-on-load path repaints through the helper",
    /const c = detailContainerFor\(mem\.id\);/.test(restore) && /rerenderDetail\(c, ev2\)/.test(restore),
    "restore still looks up the desktop container only");
check("no after-the-fact repaint looks up the desktop container by id and stops there",
    (html.match(/getElementById\(`detail-content-\$\{(ev\.id|mem\.id)\}`\)/g) || []).length === 0);
check("rerenderDetail still routes a mobile container to the mobile renderer",
    /if \(isMobileContainer\(container\)\) \{\s*\/\/[^\n]*\n\s*renderEventsMobile\(/.test(html));
console.log("\n" + (failures ? failures + " FAILURE(S)" : "ALL PASS"));
process.exit(failures ? 1 : 0);
