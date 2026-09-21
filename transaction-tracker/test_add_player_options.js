/**
 * The Add Player modal's selects follow the EVENT (Kerry 2026-09-21).
 * Run: node test_add_player_options.js
 */
const fs = require("fs");
let failures = 0;
function check(label, cond, detail) {
    if (cond) console.log("  PASS  " + label);
    else { console.log("  FAIL  " + label + (detail ? "  " + detail : "")); failures++; }
}
const html = fs.readFileSync("templates/events.html", "utf8");
check("opening the modal loads this event's options", /updateAddPlayerMode\(\);\s*apLoadOptions\(addPlayerEventId\);/.test(html));
check("…from the event-aware endpoint", html.includes("/api/events/${evId}/add-player-options"));
const rebuild = html.slice(html.indexOf("function apRebuildSelect("), html.indexOf("function apApplyOptions("));
check("a single option is preselected — an answer, not a choice", /if \(single\) sel\.value = opts\[0\]\.value;/.test(rebuild) && /single \? "" :/.test(rebuild));
check("holes, side games and tees are all rebuilt from the event",
    ["add-player-holes", "add-player-side-games", "add-player-tee"].every(id => html.includes(`apRebuildSelect("${id}"`)));
const load = html.slice(html.indexOf("async function apLoadOptions("), html.indexOf("function apEnsureOption("));
check("a failed fetch leaves the static lists standing (no blank modal)", /if \(!res\.ok\) return;/.test(load) && /catch \(err\)/.test(load));
check("a stale response for a modal that moved on is ignored", /seq !== apOptionsSeq \|\| addPlayerEventId !== evId/.test(load));
check("a package's hole count is added to the list rather than dropped", /apEnsureOption\("add-player-holes", String\(holes\)/.test(html));
check("the person's last tee prefills an empty tee field, only if the course offers that band",
    /function apPrefillFromPerson\(\)/.test(html) && /some\(o => o\.value === last\)/.test(html));
check("…on the typed name and on the manager pick", /apPrefillFromPerson\(\);\s*\}\s*renderApNameSuggest/.test(html)
    && html.includes('getElementById("add-player-manager").addEventListener("change", apPrefillFromPerson)'));
check("history prefills an empty Side Games field with the person's MOST FREQUENT choice, only when the event offers it",
    /function apNormSideGames\(v\)/.test(html) && /const typical = Object\.entries\(tally\)\.sort\(\(a, b\) => b\[1\] - a\[1\]\)\[0\];/.test(html)
    && /if \(typical && \[\.\.\.sgSel\.options\]\.some\(o => o\.value === typical\[0\]\)\) sgSel\.value = typical\[0\];/.test(html));
check("…and never overwrites a value already chosen", /if \(sgSel && !sgSel\.value\) \{/.test(html) && /if \(teeSel && !teeSel\.value\) \{/.test(html));
check("the static fallback lists are still in the HTML", html.includes('<option value="36">36 (two days)</option>') && html.includes('<option value="Forward">Forward</option>'));
console.log("\n" + (failures ? failures + " FAILURE(S)" : "ALL PASS"));
process.exit(failures ? 1 : 0);
