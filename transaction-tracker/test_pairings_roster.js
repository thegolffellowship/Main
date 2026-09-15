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

console.log("\nDropdowns read Last, First (v2.412.0)");
check("rosterOptionHtml displays through displayName but keeps the raw name as the value",
    /function rosterOptionHtml\(state, name, suffix\)[\s\S]{0,400}<option value="\$\{escapeHtml\(name\)\}"[\s\S]{0,200}\$\{escapeHtml\(displayName\(name\)\)\}/.test(html));
// Behavioural: slice the real helpers and render one option.
(() => {
    const grab = (n) => { const i = html.indexOf('function ' + n + '('); let d = 0, j = html.indexOf('{', i);
        for (let k = j; k < html.length; k++) { if (html[k] === '{') d++; else if (html[k] === '}') { d--; if (!d) return html.slice(i, k + 1); } } };
    const escapeHtml = (t) => String(t).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const pairPersonKey = (n) => String(n || '').toLowerCase().trim();
    const isRsvpOnlyPlayer = (state, name) => (state.event_players || []).some(p => p.rsvp_only && pairPersonKey(p.name) === pairPersonKey(name));
    eval(grab('isElevatedStatus') + grab('displayName') + grab('rosterOptionHtml'));
    const st = { event_players: [{ name: 'Jeff Young', rsvp_only: true }, { name: 'Victor Arias III', rsvp_only: false }] };
    const a = rosterOptionHtml(st, 'Jeff Young'), b = rosterOptionHtml(st, 'Victor Arias III');
    check("an RSVP entry renders 'Young, Jeff · RSVP' with value 'Jeff Young'",
        /value="Jeff Young"[^>]*>Young, Jeff \u00b7 RSVP<\/option>/.test(a), a);
    check("a suffixed name renders 'Arias, Victor III'",
        /value="Victor Arias III">Arias, Victor III<\/option>/.test(b), b);
})();

console.log("\nPicker + Unassigned read Last, First; foursomes wrap to the window (v2.413.0)");
check("open-seat picker entries display through displayName",
    /class="pairing-pick-item"[\s\S]{0,120}\$\{escapeHtml\(displayName\(p\.name\)\)\}/.test(html));
check("Unassigned panel names display through displayName, raw name kept on data-unassigned-name",
    /data-unassigned-name="\$\{escapeHtml\(player\.name\)\}"[\s\S]{0,500}\$\{escapeHtml\(displayName\(player\.name\)\)\}/.test(html));
check("seated cards still read First Last",
    /data-cart-pos="\$\{player\.cart_pos\}">`;[\s\S]{0,400}\$\{escapeHtml\(player\.name \|\| '\u2014'\)\}/.test(html));
check("detail panel is capped at the wrapper's visible width and sticks left",
    /\.event-detail-content \{[^}]*max-width: var\(--ev-detail-w, 100%\);[^}]*position: sticky; left: 0;/.test(html));
check("a ResizeObserver on the table wrapper publishes --ev-detail-w",
    /querySelector\('\.events-table-wrapper'\)[\s\S]{0,300}setProperty\('--ev-detail-w', wrap\.clientWidth \+ 'px'\)[\s\S]{0,120}new ResizeObserver\(set\)\.observe\(wrap\)/.test(html));

console.log("\nBullpen X (v2.413.0)");
check("every seated row carries an unseat button keyed by holes/group/cart",
    /class="pairing-unseat" data-unseat data-ev-id="\$\{ev\.id\}" data-holes="\$\{holes\}" data-group-num="\$\{grp\.group_num\}" data-cart-pos="\$\{player\.cart_pos\}"/.test(html));
check("the handler splices the player out, dirties the sheet and records history",
    /\[data-unseat\]'\)\.forEach\(btn =>[\s\S]{0,900}grp\.players\.splice\(idx, 1\);[\s\S]{0,120}state\.isDirty = true;[\s\S]{0,160}commitPairHistory\(state\);/.test(html));
check("the X cannot start a drag of the row",
    /btn\.addEventListener\('dragstart', e => \{ e\.preventDefault\(\); e\.stopPropagation\(\); \}\)/.test(html));
check("the X is red and quiet until hovered",
    /\.pairing-unseat \{[^}]*color: #b91c1c;[^}]*opacity: 0\.35;/.test(html)
    && /\.pairing-player-row:hover \.pairing-unseat \{ opacity: 0\.85; \}/.test(html));

console.log("\nPoints column checkbox (v2.414.0)");
check("a Points checkbox is offered when the race has points",
    /data-pairings-points="\$\{ev\.id\}" \$\{state\.showPointsCol \? 'checked' : ''\}/.test(html)
    && /if \(state\.standingsPoints && Object\.keys\(state\.standingsPoints\)\.length > 0\) \{\s*html \+= `<label class="pairings-toggle-label"/.test(html));
check("unchecked hides the column but keeps the bands",
    /const showPoints = havePoints && state\.showPointsCol !== false;/.test(html)
    && /\|\| havePoints;/.test(html));
check("the choice is remembered per browser and re-renders",
    /state\.showPointsCol = pointsChk\.checked;\s*pairingsPointsPref\(pointsChk\.checked\);\s*rerenderDetail\(container, ev\);/.test(html)
    && /localStorage\.getItem\('tgf_pairings_points_col'\)/.test(html));
check("default is ON when nothing is stored",
    /return raw === null \? true : raw === '1';/.test(html));

console.log("\nRoles on the sheet (v2.416.0)");
check("badges read the roster row by identity",
    /function rosterFlags\(state, name\)[\s\S]{0,200}pairPersonKey\(p\.name\) === k/.test(html));
check("C / A / 1Y badges follow the seated name and the unassigned name",
    /<span class="pairing-player-name">\$\{escapeHtml\(player\.name \|\| '\u2014'\)\}<\/span>`;\s*if \(player\.name\) html \+= roleBadgesHtml\(state, player\.name\);/.test(html)
    && /displayName\(player\.name\)\)\}<\/span>`;\s*if \(player\.name\) html \+= roleBadgesHtml\(state, player\.name\);/.test(html));
check("badges are single letters: C, A, and a green 1Y",
    />C<\/span>'/.test(html) && />A<\/span>'/.test(html) && />1Y<\/span>'/.test(html)
    && /\.pairing-role-badge\.role-new \{ background: var\(--buyin-green/.test(html));
check("no wheel mark — seats 1 and 3 drive by definition", !/driverMarkHtml|pairing-driver/.test(html));
check("names never wrap on the sheet",
    /\.pairing-player-name \{[^}]*white-space: nowrap; overflow: hidden; text-overflow: ellipsis;/.test(html)
    && /minmax\(340px, 1fr\)/.test(html));
// ── History row under each name (Kerry 2026-09-15, after the s9.23
//    count report: "I had no idea about the Group 5 repeats ... provide
//    this info as a row underneath each name in a foursome that also has
//    a check box to show Pairing History Count (History)").
check("a History checkbox sits with the other pairing toggles",
    /data-pairings-history=\"\$\{ev\.id\}\"/.test(html) && />\s*History\s*</.test(html));
check("it re-renders and is remembered per browser",
    /const histChk = [\s\S]{0,320}pairingsHistoryPref\(histChk\.checked\);[\s\S]{0,80}rerenderDetail/.test(html)
    && /localStorage\.getItem\('tgf_pairings_history_row'\)/.test(html));
check("default ON — a repeat should be impossible to miss",
    /function pairingsHistoryPref\(v\) \{[\s\S]{0,240}raw === null \? true : raw === '1'/.test(html));
check("the count key is the server's _pair_key_name twin, not pairPersonKey",
    /function pairCountKey\(name\) \{\s*return String\(name \|\| ''\)\.trim\(\)\.replace\(\/\\s\+\/g, ' '\)\.toLowerCase\(\);/.test(html)
    && /function pairPlayedTotal\(state, a, b\) \{\s*const ka = pairCountKey\(a\), kb = pairCountKey\(b\);/.test(html));
check("tonight is the +1 on top of the server's prior counts",
    /\(Number\(\(state\.pairCounts \|\| \{\}\)\[key\]\) \|\| 0\) \+ 1/.test(html));
check("the roster's prior counts land in state from the GET and from Generate",
    (html.match(/state\.pairCounts = data\.pair_counts \|\| \{\}/g) || []).length >= 1
    && /if \(data\.pair_counts\) state\.pairCounts = data\.pair_counts;/.test(html));
check("the line lists the OTHER seats in cart order, surname + count",
    /function pairHistoryRowHtml\(state, grp, player\)[\s\S]{0,420}p\.name !== player\.name[\s\S]{0,200}cart_pos/.test(html));
check("2+ is amber, 4+ is red",
    /n >= 4 \? ' ph-hot' : \(n >= 2 \? ' ph-rep' : ''\)/.test(html)
    && /\.ph-rep \{ color: #b45309/.test(html) && /\.ph-hot \{ color: #b91c1c/.test(html));
check("the line wraps to its own row without breaking the rest of the row",
    /\.pairing-player-row\.has-hist \{ flex-wrap: wrap;/.test(html)
    && /\.pairing-hist-row \{\s*flex: 0 0 100%;/.test(html));
check("…and it never wraps itself — clipped like the name",
    /\.pairing-hist-row \{[^}]*white-space: nowrap; overflow: hidden; text-overflow: ellipsis;/.test(html));
check("the line renders LAST so the X stays on line one",
    /pairing-unseat[\s\S]{0,900}html \+= histHtml;\s*html \+= '<\/div>';/.test(html)
    && html.indexOf("html += histHtml;") > html.indexOf('class="pairing-unseat"'));
check("a group carrying a repeat is chipped on its header",
    /function groupRepeatMax\(state, grp\)/.test(html)
    && /if \(rep\.max >= 2\)/.test(html)
    && /\$\{escapeHtml\(grp\.slot_label\)\}\$\{paceChip\}\$\{repeatChip\}/.test(html));
check("the chip only shows while History is on", /if \(state\.showHistoryRow\) \{\s*const rep = groupRepeatMax/.test(html));

// ── The sheet is linked to the PERSON (Kerry 2026-09-15: "It needs to
//    be directly linked in PAIRINGS to the ROSTER and Customer ID so it
//    changes immediately if customer profile is changed").
check("the roster row is found by customer_id first, name only as fallback",
    /function rosterEntry\(state, name, cid\) \{[\s\S]{0,320}Number\(x\.customer_id\) === Number\(cid\)/.test(html));
check("the seated card passes the sheet's customer_id to that lookup",
    /rosterEntry\(state, player\.name, player\.customer_id\)/.test(html));

// ── The counts have to actually ARRIVE (Kerry 2026-09-15: "This looks
//    good, but actual counts aren't showing"). The GET called
//    db.get_connection(), but `db` is not a bound name in app.py — the
//    NameError went straight into a non-fatal except and every pair
//    silently read 1. No module-qualified `db.` call may exist there.
const appPy = fs.readFileSync("app.py", "utf8");
check("app.py never calls a `db.` module that it does not import",
    /^\s*(import email_parser\.database as db|from email_parser import database as db)\b/m.test(appPy)
    || !/(^|[^_.\w])db\.[a-z_]+\(/m.test(appPy),
    (appPy.match(/(^|[^_.\w])db\.[a-z_]+\(/) || [""])[0]);
check("the pairings GET ships the roster's counts through a real import",
    /from email_parser\.database import roster_pair_counts[\s\S]{0,200}pair_counts = roster_pair_counts\(/.test(appPy)
    && /"pair_counts": pair_counts,/.test(appPy));

// ── Requested pairs are exempt from the repeat flag (Kerry 2026-09-15:
//    "Yes, any requests should be exempted from the repeat flag").
check("a requested pair is built from the request list, both orders",
    /function requestedPairSet\(state\)[\s\S]{0,420}r\.partner[\s\S]{0,240}a < b \? `\$\{a\}\|\$\{b\}` : `\$\{b\}\|\$\{a\}`/.test(html));
check("a suppressed request does not count as a request",
    /if \(!r \|\| !r\.partner \|\| r\.suppressed\) return;/.test(html));
check("a requested pair is never coloured as a repeat",
    /const cls = req \? ' ph-req' : \(n >= 4 \? ' ph-hot' : \(n >= 2 \? ' ph-rep' : ''\)\);/.test(html)
    && /\.ph-req \{ color: var\(--muted\)/.test(html));
check("…and never drives the group's repeat chip",
    /if \(pairIsRequested\(state, names\[i\], names\[j\]\)\) continue;/.test(html));
check("the count itself still shows for a requested pair",
    /\$\{n\}\$\{req \? '&#x2691;' : ''\}/.test(html));
check("the request cache is dropped when the request list is replaced",
    /state\.requests = data\.partner_requests \|\| \[\];\s*state\._reqPairs = null;/.test(html));

// ── Legend carries the role marks (Kerry 2026-09-15: "Add the new
//    symbols for Captain, Ambassador and 1Y to the legend above").
check("the legend shows C, A and 1Y in the card's own badge markup",
    /\['role-capt', 'C', 'GROUP CAPTAIN'\][\s\S]{0,160}\['role-new', '1Y', 'FIRST-YEAR MEMBER'\]/.test(html)
    && /<span class="pairing-role-badge \$\{cls\}">\$\{mark\}<\/span>/.test(html));
check("the role marks show even when the standings bands do not",
    /const bandLegend = !showBands \? '' :/.test(html)
    && /if \(bandLegend \|\| roleLegend\) \{/.test(html));

// ── A LATE SIGNUP REACHES THE BULLPEN (Kerry 2026-09-15: "Just had a
//    late signup... Justin Guerrero. He's not showing up as in the
//    bullpen though."). The panel read the roster once, on first open,
//    and nothing re-read it — the stale-player banner was armed only the
//    other way round (seated, no longer on the roster).
check("there is a roster-only refresh that never touches the groups",
    /async function refreshPairingsRoster\(evId\)[\s\S]{0,900}state\.event_players = data\.event_players \|\| \[\];/.test(html)
    && !/function refreshPairingsRoster[\s\S]{0,900}state\.groups_9 =/.test(html));
check("it rebuilds the lookups that hang off the roster",
    /refreshPairingsRoster[\s\S]{0,900}state\._paceMap = null;[\s\S]{0,300}state\._reqPairs = null;[\s\S]{0,300}state\.pairCounts = data\.pair_counts/.test(html));
check("re-opening the PAIRINGS tab re-reads the roster; first open still loads the sheet",
    /if \(!getPairingsState\(ev\.id\)\.loaded\) \{\s*await loadPairings\(ev\.id\);\s*\} else \{\s*await refreshPairingsRoster\(ev\.id\);/.test(html));
check("the bullpen no longer disappears when everyone is seated",
    /Everyone on the roster is seated/.test(html)
    && !/const unassigned = getUnassigned\(state\);\s*if \(!unassigned\.length\) return '';/.test(html));
check("a Re-check roster control sits on the panel, in both states",
    (html.match(/\$\{refreshBtn\}/g) || []).length >= 2
    && /class="pairings-roster-refresh"/.test(html));
check("the control names who arrived rather than silently redrawing",
    /pairings-roster-refresh[\s\S]{0,900}New on the roster: /.test(html));

const cust = fs.readFileSync("templates/customers.html", "utf8");
check("Customers page offers AMB / CAPT / BACK chips beside pace, both layouts",
    (cust.match(/renderRoleChips\(c\)/g) || []).length >= 2
    && /fetch\(`\/api\/customers\/\$\{cid\}\/roles`/.test(cust));

console.log("");
if (failures) { console.log(failures + " FAILURE(S)"); process.exit(1); }
console.log("All pairings-roster assertions passed.");
