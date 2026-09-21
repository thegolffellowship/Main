/**
 * Mark Paid is ONE modal, and it arrives filled in.
 *
 * Kerry 2026-09-16: "Can you also make it all one modal to Mark Paid so I
 * can just click a button or select from a drop down, then auto enter
 * today's date which would most likely be the date that I'm marking it,
 * and enter the appropriate note?"
 *
 * It used to be three chained window.prompt()s — type the method, type
 * the date, type the note — for a payout whose method is one of eight,
 * whose date is today, and whose note is already written on its own rows.
 *
 * Run: node test_mark_paid_modal.js
 */
const fs = require("fs");
const html = fs.readFileSync("templates/tgf.html", "utf8");
let failures = 0;
function check(label, cond, detail) {
    if (cond) console.log("  PASS  " + label);
    else { console.log("  FAIL  " + label + (detail ? "  " + detail : "")); failures++; }
}

console.log("\nOne modal, no prompts");
check("the dialog exists and returns a promise",
    /function tgfMarkPaidDialog\(\{name, amount, eventName, note\}\)/.test(html)
    && /return new Promise\(resolve =>/.test(html));
const handler = html.slice(html.indexOf("function attachMarkPaidHandlers"));
const body = handler.slice(0, handler.indexOf("\n        }\n"));
check("the three chained prompts are gone", !/prompt\(/.test(body),
    "a window.prompt survives in the Mark Paid handler");
check("…replaced by one awaited dialog",
    /const got = await tgfMarkPaidDialog\(/.test(body));
check("cancel means cancel", /if \(!got\) return;/.test(body));

console.log("\nNothing has to be typed");
check("method is a row of buttons, Venmo first",
    /const TGF_PAY_METHODS = \[\s*\["venmo", "Venmo"\], \["applepay", "Apple Pay"\]/.test(html));
check("Apple Pay is one of them (Kerry 2026-09-16)", /\["applepay", "Apple Pay"\]/.test(html));
check("the date opens on TGF'S today, not the browser's UTC day",
    /function tgfTodayCentral\(\)[\s\S]{0,300}America\/Chicago/.test(html)
    && /value="\$\{tgfTodayCentral\(\)\}"/.test(html));
check("the note writes itself from the payout rows",
    /function paidNoteFor\(items\)/.test(html)
    && /data-note="\$\{paidNoteFor\(/.test(html));
check("…and drops the bookkeeping tails a human would not write",
    html.indexOf("(GG ") > 0 && html.indexOf("(team split)") > 0);

console.log("\nIt behaves like a dialog");
check("Escape cancels and Enter submits",
    /if \(e\.key === "Escape"\) close\(null\)/.test(html)
    && /if \(e\.key === "Enter"[\s\S]{0,60}submit\(\)/.test(html));
check("clicking the backdrop cancels",
    /wrap\.addEventListener\("click", e => \{ if \(e\.target === wrap\) close\(null\); \}\)/.test(html));
check("the key handler is removed on close, not left on document",
    /document\.removeEventListener\("keydown", onKey\)/.test(html));
check("names and notes are escaped into the markup",
    /function escapeHtml\(str\)/.test(html)
    && /\$\{escapeHtml\(name\)\}/.test(html));

console.log(failures ? `\n${failures} FAILURE(S)` : "\nALL PASS");
process.exit(failures ? 1 : 0);
