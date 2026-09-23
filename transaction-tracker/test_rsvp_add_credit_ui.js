/**
 * Add Player → RSVP Only checks for credit and opens Apply Credit
 * (Kerry 2026-09-23). Run: node test_rsvp_add_credit_ui.js
 */
const fs = require("fs");
let failures = 0;
function check(label, cond, detail) {
    if (cond) console.log("  PASS  " + label);
    else { console.log("  FAIL  " + label + (detail ? "  " + detail : "")); failures++; }
}
const html = fs.readFileSync("templates/events.html", "utf8");
const submit = html.slice(html.indexOf("async function handleAddPlayerSubmit("), html.indexOf("async function apOfferCreditAfterRsvp("));
check("after a successful Add RSVP the page runs the credit offer for the NEW row (and only for RSVP mode)",
      /_apMode === "rsvp" && newId != null\) apOfferCreditAfterRsvp\(newId, _apName, _apEvent\)/.test(submit));
check("…after the roster redraw, with the event name captured before the modal is closed (closeAddPlayerModal nulls it)",
      submit.indexOf("const _apMode = mode, _apName = name, _apEvent = addPlayerEventName;") < submit.indexOf("closeAddPlayerModal();")
      && submit.indexOf("await refreshEventInPlace(expandedEventId);") < submit.indexOf("apOfferCreditAfterRsvp(newId"));
const offer = html.slice(html.indexOf("async function apOfferCreditAfterRsvp("), html.indexOf("// ---- Add Payment modal ----"));
check("the offer asks the same credit-info the Apply Credit modal uses and stays silent when there is none",
      /\/api\/rsvps\/\$\{itemId\}\/credit-info/.test(offer) && /if \(!info \|\| !\(info\.credits \|\| \[\]\)\.length\) return;/.test(offer));
check("…and opens the EXISTING Apply Credit modal for the RSVP row (no second credit flow)",
      /openApplyCreditModal\(itemId, null, name, eventName\)/.test(offer) && !/fetch\(.*apply-credit`/.test(offer));
check("a toast names the player and the credit total", /has \$\$\{total\} credit on file/.test(offer));
check("the Add Player modal carries a credit hint under the name, fed by /api/customers/credit-check as the name is typed",
      /id="ap-credit-hint"/.test(html) && /\/api\/customers\/credit-check\?name=/.test(html) && /apCreditHint\(isKnown \? name : ""\)/.test(html));
check("a stale hint answer is dropped (sequence guard)", /seq !== _apCreditSeq/.test(html));
console.log("\n" + (failures ? failures + " FAILURE(S)" : "ALL PASS"));
process.exit(failures ? 1 : 0);
