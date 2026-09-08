/**
 * FELLOWSHIP filter badge (Kerry 2026-09-08: "Can you give me a button
 * to filter/list those who've selected YES for FELLOWSHIP?").
 *
 * items.fellowship holds 'YES' / 'NO' / null. Before this the answer was
 * only visible one player at a time, behind the info icon on an expanded
 * row — there was no way to see the group.
 *
 * The badge sits with the game badges but is NOT a game: on a day-games
 * event the roster filter short-circuits to axisFilterMatch(), which
 * would have swallowed FELLOWSHIP and returned the wrong roster. Both
 * the desktop and mobile filters answer fellowship BEFORE that branch.
 *
 * Run: node test_fellowship_filter.js
 */
const fs = require("fs");
const html = fs.readFileSync("templates/events.html", "utf8");

let failures = 0;
function check(label, cond, detail) {
    if (cond) { console.log("  PASS  " + label); }
    else { console.log("  FAIL  " + label + (detail ? "  " + detail : "")); failures++; }
}

console.log("\nBadge");
check("the filter value is a named constant, not a loose string",
    /const FELLOWSHIP_FILTER = "FELLOWSHIP";/.test(html));
check("badge renders on the desktop sub-filter row",
    /html \+= fellowshipBadgeHtml\(ev, registrants, activeFilter\);/.test(html));
check("badge renders on the mobile sub-filter row",
    /badgesHtml \+= fellowshipBadgeHtml\(ev, registrants, activeFilter\);/.test(html));
check("badge hides itself when nobody answered YES",
    /const n = countFellowshipYes\(registrants\);\s*\n\s*if \(!n\) return "";/.test(html));
check("badge has its own tint so it does not read as a game type",
    /\.game-stat-badge\.fellowship-badge \{/.test(html));

console.log("\nMatching");
check("a leading Y matches, so 'Yes' from a future form still counts",
    /return \/\^\\s\*y\/i\.test\(String\(r && r\.fellowship \|\| ""\)\);/.test(html));
check("the count excludes child payment rows and inactive players",
    /!r\.parent_item_id\s*\n\s*&& !_FELLOW_INACTIVE\.includes\(r\.transaction_status\)\s*\n\s*&& isFellowshipYes\(r\)/.test(html));

console.log("\nThe axis trap");
// On a day-games event the roster filter returns axisFilterMatch() before
// reading activeFilter any further. Fellowship must be answered first or
// the badge silently produces a games-axis roster.
const deskIdx = html.indexOf("filtered = activePlayers.filter(r => {");
const desk = html.slice(deskIdx, deskIdx + 700);
check("desktop answers FELLOWSHIP before the axis branch",
    desk.indexOf("activeFilter === FELLOWSHIP_FILTER") > -1
    && desk.indexOf("activeFilter === FELLOWSHIP_FILTER") < desk.indexOf("if (ax) return axisFilterMatch"));

const mobIdx = html.indexOf("if (mAx) return axisFilterMatch");
const mob = html.slice(Math.max(0, mobIdx - 400), mobIdx + 100);
check("mobile answers FELLOWSHIP before the axis branch",
    mob.indexOf("activeFilter === FELLOWSHIP_FILTER") > -1
    && mob.indexOf("activeFilter === FELLOWSHIP_FILTER") < mob.indexOf("if (mAx) return axisFilterMatch"));

console.log("\nMessage Players");
check("Fellowship YES is an audience in the compose modal",
    /<option value="fellowship">Fellowship YES<\/option>/.test(html));
check("the compose recipient filter honours it",
    /if \(audience === "fellowship"\) return isFellowshipYes\(r\);/.test(html));
check("choosing the Fellowship template selects its audience",
    /\/fellowship\/i\.test\(tpl\.name \|\| ""\) && audSel\.value === "all"/.test(html));

// #424 shipped {link_offer} into Kerry's composer. A template blank must
// not be able to leave the building either.
check("send blocks on an unfilled [BRACKET] blank",
    /\\\[\[A-Z\]\[A-Z0-9 _\/-\]\{2,\}\\\]/.test(html));
check("send blocks on an unknown {curly} variable",
    /const KNOWN_VARS = \["player_name", "event_name", "event_date",/.test(html)
    && /if \(blanks\.length\) \{/.test(html));
check("the guard runs before any recipient is counted or confirmed",
    html.indexOf("Still to fill in before this can go out")
        < html.indexOf("if (!recipientCount) { alert(\"No recipients selected\"); return; }"));

console.log("");
if (failures) { console.log(failures + " FAILURE(S)"); process.exit(1); }
console.log("All fellowship-filter assertions passed.");
