/**
 * The ladies' tee gets the outline, and the men's Red does not —
 * and the word for it is "Women" on every legend.
 *
 * Kerry, 2026-09-16, on the s9.23 board: "Open circles should be for
 * ladies tees, not men... Mike is showing as that open circle and the
 * ladies should be the open circle. So need to flip those."
 *
 * Root cause: the legend was built in tee ORDER, re-sorted so the
 * ladies' tee falls last, and only THEN zipped against the still-
 * unsorted label list. After the sort the sequences no longer line up,
 * so every entry from the moved element onward paired with the wrong
 * label. On a card carrying both "3 - Red Tee" and "3 - Red (L) Tee"
 * that is an exact swap.
 *
 * Run: node test_tee_legend_pairing.js
 */
const fs = require("fs");
let failures = 0;
function check(label, cond, detail) {
    if (cond) console.log("  PASS  " + label);
    else { console.log("  FAIL  " + label + (detail ? "  " + detail : "")); failures++; }
}

const py = fs.readFileSync("email_parser/database.py", "utf8");
const i = py.indexOf("_lbl_of[r[\"tee_name\"]] = (label,");
const blk = py.slice(i, i + 3000);

console.log("\nThe pairing is made BEFORE the display sort");
const zipAt = blk.indexOf("_leg_by_label[lbl] = t");
const sortAt = blk.indexOf('tee_legend.sort(key=lambda t: 1 if t["ladies"] else 0)');
check("both the zip and the ladies-last sort are still present",
    zipAt > -1 && sortAt > -1);
check("the label pairing happens BEFORE the sort reorders the list",
    zipAt > -1 && sortAt > -1 && zipAt < sortAt,
    "the sort runs first again — labels pair with the wrong tee");

console.log("\nONE word for the women's tee, on both legends");
// Kerry 2026-09-16: "S1. Women's" and "We need to sync up the two legends
// somehow to maintain consistency". The LEADERBOARD's played-tee legend
// and the STARTER SHEET's band legend are built by different code; both
// must take the word from TEE_LEGEND_WOMEN_WORD and compose
// band_label + tee_name, so neither can drift to "Ladies" on its own.
const pyCode = py.replace(/"""[\s\S]*?"""/g, "").replace(/#[^\n]*/g, "");
check("the word is defined once", /TEE_LEGEND_WOMEN_WORD = "Women"/.test(pyCode));
check("the BOARD legend takes band_label from the constant",
    /"band_label": TEE_LEGEND_WOMEN_WORD if ladies else None/.test(pyCode));
check("the BAND (starter sheet) legend takes it from the same constant",
    /band, TEE_LEGEND_WOMEN_WORD if \(ladies or band == "Forward"\)/.test(pyCode));
check("no legend builder spells 'Ladies' on its own",
    !/Ladies - /.test(pyCode) && !/"Ladies"/.test(pyCode));
const j = py.indexOf("def _tee_legend_display_name");
const fn = py.slice(j, py.indexOf("\ndef ", j + 1)).replace(/"""[\s\S]*?"""/, "");
check("the tee NAME never carries who plays it", /return _tee_name_plural\(name\)/.test(fn)
    && !/ladies and/.test(fn));
const html = fs.readFileSync("templates/contests.html", "utf8");
const lg = html.slice(html.indexOf("function evlbTeeLegend"), html.indexOf("function evlbTeeDot"));
check("the board legend renders band_label THEN tee_name, like the starter sheet",
    /\[t\.band_label \|\| t\.band \|\| "", t\.tee_name \|\| ""\]\.filter\(Boolean\)\.join\(" "\)/.test(lg));
const ss = fs.readFileSync("templates/starter_sheet.html", "utf8");
check("the starter sheet renders band_label then tee_name",
    ss.indexOf("{{ t.band_label or t.band }}") > -1
    && ss.indexOf("{{ t.band_label or t.band }}") < ss.indexOf("{{ t.tee_name }}"));
// The BAND legend's spelling is RATIFIED (Kerry 2026-09-15): "Red Tees",
// the band says who plays it, the colour must NOT repeat it.
const b = py.indexOf("def _tee_name_plural");
const bfCode = py.slice(b, py.indexOf("\ndef ", b + 1)).replace(/"""[\s\S]*?"""/, "");
check("the tee name keeps its ratified 'Red Tees' spelling",
    /return f"\{n\} Tees" if n else n/.test(bfCode));

console.log("\nThe outline still means ladies, and only ladies");
const k = py.indexOf('"ring": ladies');
check("ring is set from the ladies flag, nothing else", k > -1);
check("ladies is detected from the tee name's (L) marker",
    /ladies = bool\(re\.search\(r"\\\(\(\?:l\|lady\|ladies\)\\\)"/.test(py));

console.log("\n" + (failures ? failures + " FAILURE(S)" : "ALL PASS"));
process.exit(failures ? 1 : 0);
