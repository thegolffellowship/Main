/**
 * The pairings roster must be the SAME roster the Players tab shows, and
 * an open seat must be fillable from it (Kerry 2026-09-08: "If someone
 * is not in pairings, it needs to show. Like Michelle DelCarmen. For the
 * open spots, I need to be able to click and select from a list of those
 * players.").
 *
 * Two defects are pinned here:
 *
 *  1. /api/events/<id>/pairings builds event_players from the `items`
 *     table, so a player who only ever RSVP'd in Golf Genius — no order
 *     row — never reached the Unassigned panel. The Players tab already
 *     derives those synthetic gg_rsvp rows; renderPairingsPanel now
 *     receives them and getUnassigned merges them in.
 *  2. getUnassigned compared lowercased name STRINGS, against the
 *     CLAUDE.md identity rule and against the stale-roster banner three
 *     lines above it that keys people with pairPersonKey(). A seated
 *     "Mike Marques" would have been listed as unassigned next to the
 *     roster's "Michael Marques".
 *
 * Run: node test_pairings_roster.js
 */
const fs = require("fs");
const html = fs.readFileSync("templates/events.html", "utf8");

let failures = 0;
function check(label, cond, detail) {
    if (cond) { console.log("  PASS  " + label); }
    else { console.log("  FAIL  " + label + (detail ? "  " + detail : "")); failures++; }
}

console.log("\nRoster completeness");

check("renderPairingsPanel accepts the extra roster rows",
    /function renderPairingsPanel\(ev, registrants, rosterExtra\)/.test(html));

check("desktop call site passes its synthetic GG RSVP rows",
    /renderPairingsPanel\(ev, registrants, ggRsvpRows\)/.test(html));

check("mobile call site passes its synthetic GG RSVP rows",
    /renderPairingsPanel\(ev, registrants, mGgRows\)/.test(html));

check("getUnassigned merges event_players with rosterExtra",
    /const roster = \[\.\.\.\(state\.event_players \|\| \[\]\), \.\.\.\(state\.rosterExtra \|\| \[\]\)\]/.test(html));

check("RSVP-only entries are flagged so the manager knows why they are there",
    /rsvp_only: true/.test(html) && /pairing-rsvp-badge/.test(html));

console.log("\nIdentity matching");

// The whole point: no raw lowercased-name comparison left in getUnassigned.
const fn = html.slice(html.indexOf("function getUnassigned(state)"));
const body = fn.slice(0, fn.indexOf("\n    }\n"));
check("getUnassigned keys seated players with pairPersonKey",
    /seated\.add\(pairPersonKey\(p\.name\)\)/.test(body));
check("getUnassigned keys roster players with pairPersonKey",
    /const k = pairPersonKey\(p\.name\)/.test(body));
check("no lowercased-string identity compare survives",
    !/toLowerCase\(\)/.test(body), "found a raw string compare in getUnassigned");
check("duplicates across the two roster sources collapse",
    /seen\.has\(k\)/.test(body));

console.log("\nOpen-seat picker");

check("picker helper exists",
    /function openPairingPicker\(anchor, players, holes, onPick\)/.test(html));

check("an empty seat with nothing selected opens the picker",
    /if \(!state\.selection\) \{[\s\S]{0,400}openPairingPicker\(slot, getUnassigned\(state\), holes,/.test(html));

check("picking a player seats them in that exact seat",
    /_movePlayer\(state, \{unassigned: true, name: pick\.name\},\s*\n\s*holes, groupNum, cartPos\);/.test(html));

// Scoped to the empty-seat listener only — the player-row listener keeps
// its own guard, since clicking an occupied seat with no mode is a no-op.
const seatFn = html.slice(html.indexOf("container.querySelectorAll('.pairing-empty-slot')"));
const seatBody = seatFn.slice(0, seatFn.indexOf("\n        });\n"));
check("the seat click no longer bails out when no mode is active",
    !/if \(!state\.swapMode \|\| state\.swapMode === 'group'\) return;/.test(seatBody)
    && /if \(state\.swapMode === 'group'\) return;/.test(seatBody));

check("picker closes on outside click, scroll, resize and Escape",
    /document\.addEventListener\('click', closePairingPicker, \{once: true\}\)/.test(html)
    && /window\.addEventListener\('scroll', closePairingPicker, true\)/.test(html)
    && /window\.addEventListener\('resize', closePairingPicker\)/.test(html)
    && /if \(e\.key === 'Escape'\) closePairingPicker\(\)/.test(html));

console.log("\nActions menu escapes the table's paint order");

check("open menus are lifted into a measured fixed layer",
    /\.ev-actions-menu\.menu-floating \{[\s\S]{0,200}position: fixed;[\s\S]{0,120}z-index: 9000;/.test(html));
check("every actions menu goes through the shared open/close pair",
    /function evOpenActionsMenu\(btn\)/.test(html)
    && /function evCloseActionsMenus\(\)/.test(html)
    && /else evOpenActionsMenu\(btn\);/.test(html));
check("a fixed menu is closed by scrolling rather than left stranded",
    /if \(document\.querySelector\('\.ev-actions-menu\.menu-floating'\)\) evCloseActionsMenus\(\)/.test(html));

console.log("\nRSVP-only players are first-class (v2.410.0)");
// The server now folds GG RSVPs into event_players with rsvp_only:true;
// the page must SAY so wherever a roster name is offered.
check("isRsvpOnlyPlayer answers by identity (pairPersonKey), over both roster sources",
    /function isRsvpOnlyPlayer\(state, name\)[\s\S]{0,400}pairPersonKey\(p\.name\) === k/.test(html)
    && /const roster = \[\.\.\.\(state\.event_players \|\| \[\]\), \.\.\.\(state\.rosterExtra \|\| \[\]\)\];[\s\S]{0,80}return roster\.some\(p => p\.rsvp_only/.test(html));
check("a seated RSVP-only player keeps the badge on the card",
    /isRsvpOnlyPlayer\(state, player\.name\)\) \{\s*html \+= '<span class="pairing-rsvp-badge"/.test(html));
check("rosterOptionHtml marks an RSVP entry in TEXT, not only in colour",
    /function rosterOptionHtml\(state, name, suffix\)[\s\S]{0,500}\\u00b7 RSVP/.test(html));
const selects = ["request-match-select", "data-request-add-requester", "data-request-add-partner"];
check("every request dropdown renders its names through rosterOptionHtml (" + (html.match(/rosterOptionHtml\(state, n/g) || []).length + " uses)",
    (html.match(/rosterOptionHtml\(state, n/g) || []).length >= 4);
check("no request dropdown still builds a bare <option> from a roster name",
    !/(rosterNames|canAdd|allPlayerNames)\.map\(n => `<option value="\$\{escapeHtml\(n\)\}">/.test(html));

console.log("\nName lists order by LAST name (v2.411.0)");
check("byLastName keys through lastNameSortKey",
    /function byLastName\(a, b\)[\s\S]{0,300}lastNameSortKey\(an\)\.localeCompare\(lastNameSortKey\(bn\)\)/.test(html));
check("no roster name list still sorts by plain localeCompare",
    !/(rosterNames|allPlayerNames)[\s\S]{0,200}\.sort\(\(a, b\) => a\.localeCompare\(b\)\)/.test(html));
check("request dropdowns, candidates, and the unassigned list all use it (" + (html.match(/sort\(byLastName\)/g) || []).length + " uses)",
    (html.match(/sort\(byLastName\)/g) || []).length >= 4);
check("getUnassigned returns last-name order (feeds the picker and the panel)",
    /return out\.sort\(byLastName\);\s*\}/.test(html));

console.log("");
if (failures) { console.log(failures + " FAILURE(S)"); process.exit(1); }
console.log("All pairings-roster assertions passed.");
