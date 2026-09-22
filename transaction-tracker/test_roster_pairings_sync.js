/**
 * Roster → pairings is AUTOMATIC and the transfer modal carries the price
 * check (Kerry 2026-09-22). Run: node test_roster_pairings_sync.js
 */
const fs = require("fs");
let failures = 0;
function check(label, cond, detail) {
    if (cond) console.log("  PASS  " + label);
    else { console.log("  FAIL  " + label + (detail ? "  " + detail : "")); failures++; }
}
const html = fs.readFileSync("templates/events.html", "utf8");
const sync = html.slice(html.indexOf("async function offerPairingRemoval("), html.indexOf('/** Format "First Last"'));
check("no yes/no popup: the sync never calls confirm() and never posts a second removal",
      !/confirm\(/.test(sync) && !/pairings\/remove-player/.test(sync));
check("it reports what the server did from the API's `pairings` answer", /info\.removed/.test(sync) && /info\.reseated/.test(sync));
check("…and redraws the PAIRINGS panel in place when it is open",
      /pairingsOpenForEvent\[ev\.id\]/.test(sync) && /detailContainerFor\(ev\.id\)/.test(sync) && /rerenderDetail\(container, ev\)/.test(sync));
check("every money path hands the API answer to the sync (credit / refund / transfer / WD)",
      /offerPairingRemoval\(_pairCtx\.ev, _pairCtx\.name, _pairInfo\)/.test(html) && /offerPairingRemoval\(_pairCtx\.ev, _pairCtx\.name, _wdData\.pairings\)/.test(html));
const submit = html.slice(html.indexOf("async function submitEvCredit("), html.indexOf("async function reverseEvCredit("));
check("the transfer sends the excess choice and opens Venmo in the click when 'Venmo back' is chosen",
      /excess_action, excess_venmo, apply_credit_ids/.test(submit) && /window\.open\(venmoPayHref\(handle, _net\.excess, memo\), "_blank"\)/.test(submit));
check("a SHORT transfer opens the prepared balance-due email for the NEW row",
      /openVenmoEmailModal\(_newItem\.id\)/.test(submit) && /Number\(_pc\.amount_owed\) > 0\.005/.test(submit));
check("picking a target event prices the move (transfer-preview) and a stale answer is ignored",
      /transfer-preview\?target=/.test(html) && /seq !== _evTransferPreviewSeq/.test(html)
      && html.includes('select.addEventListener("change", loadTransferPreview)'));
check("the preview offers keep-as-credit / Venmo-back on an excess and says the email is coming on a shortfall",
      /name="ev-transfer-excess" value="keep"/.test(html) && /name="ev-transfer-excess" value="venmo"/.test(html) && /balance-due Venmo email opens/.test(html));
check("the page defines a toast of its own (FLIGHTS handlers already called one)", /window\.showToast = function/.test(html));
console.log("\n" + (failures ? failures + " FAILURE(S)" : "ALL PASS"));
process.exit(failures ? 1 : 0);
