/**
 * The FLIGHTS tab's cut control, drag-to-move and auto-save, and the
 * PAIRINGS auto-save (Kerry 2026-09-22, mailbox #599):
 *
 *   "I prefer toggles that are shared toggles rather than separate
 *    buttons. Similar to the ROSTER | PAIRINGS | GAMES | FLIGHTS…
 *    Shorten these to EVEN | HCP with hover text that provides the
 *    broader explanation of what the toggle is. Add the ability to click
 *    and drag names to the other flight. When/if that is done, than it
 *    becomes a CUSTOM flight… Add an Auto-Save feature for any changes
 *    to both FLIGHTS and PAIRINGS tabs. Don't make me click SAVE each
 *    time. But the Auto-Save needs to work in the background and fast
 *    and can't impede/slow down my work."
 *
 * Regex guards on the page source, plus the segmented control rendered
 * headless for its three states.
 *
 * Run: node test_flights_custom_ui.js
 */
const fs = require("fs");
const html = fs.readFileSync("templates/events.html", "utf8");

let failures = 0;
function check(label, cond, detail) {
    if (cond) { console.log("  PASS  " + label); }
    else { console.log("  FAIL  " + label + (detail ? "  " + detail : "")); failures++; }
}

console.log("\n== EVEN | HCP: one shared control, not two buttons ==");
check("the control is one segmented group in the tab style (fb-seg-group), not free-standing pills",
      /class="fb-seg-group" role="group"/.test(html));
check("the segments read EVEN and HCP, nothing longer",
      /\[\["equal_size", "EVEN"\], \["fixed_bands", "HCP"\]\]/.test(html));
check("the old EVEN SPLIT / HCP BANDS pill labels are gone", !/"EVEN SPLIT"|"HCP BANDS"/.test(html));
check("hover text explains the even split in words (down the middle, edge = next flight's lowest index)",
      /equal_size: "EVEN — even split: the field is cut down the middle[^"]*next flight's lowest index/.test(html));
check("hover text explains the HCP bands with the ratified ladder (<12.0 / 12.0+, 6.0, 18.0, 12.0 goes up)",
      /fixed_bands: "HCP — handicap bands[^"]*<12\.0 \/ 12\.0\+[^"]*6\.0[^"]*18\.0[^"]*12\.0 goes up/.test(html));
check("the default segment carries a dot and says so on hover",
      /isDefault \? "<span[^>]*>&thinsp;&bull;<\/span>" : ""/.test(html) && /title \+= " \(default for this game\)"/.test(html));
check("a CUSTOM segment appears only once a move exists",
      /if \(mode === "custom"\) segs\.push\(\["custom", "CUSTOM"\]\)/.test(html));
check("clicking the cut you already have is a no-op (no round trip)",
      /if \(cur\.mode === mode\) return;\s*\/\/ already that cut/.test(html));
check("re-cutting from CUSTOM says the moves are cleared and saved",
      /moves_cleared\) showToast\(`Re-cut by \$\{mode === "equal_size" \? "EVEN" : "HCP"\} — the custom moves are cleared\. Saved\.`/.test(html));

console.log("\n== drag a name to another flight → CUSTOM ==");
check("member rows are draggable on a LIVE board when the game has more than one flight and the player has a customer_id",
      /const canDrag = fbLive && m\.customer_id !== null && m\.customer_id !== undefined;/.test(html)
      && /const fbLive = board\.state === "live" && canSeeFlights\(\) && \(sel\.flight_count \|\| 0\) > 1;/.test(html));
check("the row carries the game, the customer_id and the flight it sits in",
      /draggable="true" data-fb-game="\$\{g\.game\}" data-fb-cid="\$\{m\.customer_id\}" data-fb-flight="\$\{f\.flight_no\}"/.test(html));
check("every flight box is a drop target for its own game only",
      /class="fb-flight" data-fb-game="\$\{g\.game\}" data-fb-flight="\$\{f\.flight_no\}"/.test(html)
      && /if \(!fbDrag \|\| box\.dataset\.fbGame !== fbDrag\.game \|\| Number\(box\.dataset\.fbFlight\) === fbDrag\.flight\) return;/.test(html));
check("the drop POSTs flights/move with {game, customer_id, flight_no} — the drop IS the save",
      /fbPost\("move", \{ game: src\.game, customer_id: src\.cid, flight_no: to \}, "Could not move the player"\)/.test(html)
      && /fetch\(`\/api\/events\/\$\{ev\.id\}\/flights\/\$\{action\}`/.test(html));
check("the response is the board — no second round trip", /flightsBoards\[ev\.id\] = data;/.test(html));
check("a moved player is flagged MOVED with where he came from on hover",
      />MOVED<\/span>/.test(html) && /Moved by hand from Flight \$\{mv\.from_flight\}/.test(html));
check("the Selection line says CUSTOM and carries the words (custom_note)",
      /sel\.mode === "custom" \? "<strong style=\\"color:#7c2d12;\\">CUSTOM<\/strong> on the "/.test(html)
      && /escapeHtml\(sel\.custom_note\)/.test(html));
check("the hint tells him a drop saves", /Drag a name to another flight to make it custom; the drop saves\./.test(html));
check("drop rails are styled (target / over)", /\.fb-flight\.fb-drop-target \{ outline: 2px dashed/.test(html) && /\.fb-flight\.fb-drop-over \{ outline: 2px solid/.test(html));

console.log("\n== PAIRINGS auto-save: background, fast, never in the way ==");
check("every pairings change arms the background save from the rerender (one hook, every path)",
      /const ps = pairingsData\[ev\.id\];\s*if \(ps && ps\.loaded && ps\.isDirty\) schedulePairingsAutosave\(container, ev, ps\);/.test(html));
check("it debounces ~1.2 s after the LAST change", /const PAIR_AUTOSAVE_MS = 1200;/.test(html) && /clearTimeout\(pairAutosaveTimers\[ev\.id\]\);\s*pairAutosaveTimers\[ev\.id\] = setTimeout/.test(html));
check("it never fires mid-drag or mid-swap — it waits for the hand to settle",
      /if \(state\.selection \|\| document\.querySelector\('\.pair-dragging'\)\) \{\s*pairAutosaveTimers\[ev\.id\] = setTimeout\(\(\) => runPairingsAutosave\(container, ev, state, attempt\), 600\);/.test(html));
check("a change made while the save is in flight keeps the sheet dirty (saves again)",
      /state\.isDirty = state\.histIdx !== idxAtSend;/.test(html));
check("undo/redo are untouched: the save just moves the saved position", /state\.savedIdx = idxAtSend;/.test(html)
      && /state\.isDirty = state\.histIdx !== state\.savedIdx;/.test(html));
check("one retry after 2 s, then the Save button is the fallback with the error in the stamp",
      /if \(attempt < 2\) \{\s*pairAutosaveTimers\[ev\.id\] = setTimeout\(\(\) => runPairingsAutosave\(container, ev, state, attempt \+ 1\), 2000\);/.test(html)
      && /Auto-save failed \(\$\{state\.autosaveError\}\) — click Save/.test(html));
check("the toolbar shows a 'Saved h:mm' stamp and the Save button stays as the manual flush",
      /class="pair-save-stamp\$\{state\.autosaveError \? ' is-error' : ''\}" data-ev-id="\$\{ev\.id\}"/.test(html)
      && /return t \? `Saved \$\{t\.getHours\(\) % 12 \|\| 12\}:\$\{String\(t\.getMinutes\(\)\)\.padStart\(2, '0'\)\}` : 'Saved';/.test(html)
      && /data-pairings-action="save" style="background:var\(--green\);color:#fff;" title="Save now \(auto-save is on; this flushes it\)"/.test(html));
check("the manual Save cancels the pending background save (the flush wins)",
      /clearTimeout\(pairAutosaveTimers\[ev\.id\]\);\s*\/\/ the manual flush wins/.test(html));
check("after a clean background save the sheet rerenders (printables appear) unless a drag has started",
      /if \(document\.querySelector\('\.pair-dragging'\)\) paintPairingsSaveStamp\(ev, state\);\s*else rerenderDetail\(container, ev\);/.test(html));

console.log("\n== the control rendered headless ==");
const start = html.indexOf("    const FB_MODE_TEXT = {");
const end = html.indexOf("    function fbPlacesText(flight) {");
const code = 'const escapeHtml = s => String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/"/g,"&quot;");\n'
    + 'let canSeeFlights = () => true;\n' + html.slice(start, end) + '\nglobalThis.fbModeToggle = fbModeToggle;';
eval(code);
const live = { state: "live" };
let out = fbModeToggle(live, { game: "skins", selection: { mode: "fixed_bands", mode_default: "fixed_bands" } });
check("Skins by default: EVEN | HCP, HCP active with the default dot, no CUSTOM segment",
      /data-flights-mode="equal_size"[^>]*aria-pressed="false"/.test(out) && /class="fb-seg active" data-flights-mode="fixed_bands"/.test(out)
      && /HCP<span[^>]*>&thinsp;&bull;<\/span>/.test(out) && !/CUSTOM/.test(out), out);
check("...the hover text is the explanation, with '(default for this game)' on the default",
      /title="HCP — handicap bands[^"]*\(default for this game\)"/.test(out), out);
out = fbModeToggle(live, { game: "skins", selection: { mode: "custom", base_mode: "fixed_bands", mode_default: "fixed_bands",
      moves: [{ name: "Scott Marroquin", index_text: "12.4", from_flight: 2, to_flight: 1 }] } });
check("after a drag: a third CUSTOM segment, active, disabled (it is a state, not a choice), naming the move on hover",
      /class="fb-seg active" data-flights-mode="custom"[^>]*disabled[^>]*title="CUSTOM — flights moved by hand[^"]*Scott Marroquin \(12\.4\) Flight 2 → 1\."/.test(out), out);
check("...EVEN and HCP stay clickable and say what the base cut is now",
      /data-flights-mode="equal_size"[^>]*title="[^"]*Base cut now: HCP\./.test(out) && !/data-flights-mode="fixed_bands" disabled/.test(out), out);
out = fbModeToggle({ state: "frozen" }, { game: "skins", selection: { mode: "fixed_bands", mode_default: "fixed_bands" } });
check("frozen: every segment disabled and the hover says unfreeze to change",
      (out.match(/disabled/g) || []).length === 2 && /unfreeze to change/.test(out), out);

console.log();
if (failures) { console.log(`FAILED (${failures})`); process.exit(1); }
console.log("ALL PASSED");
