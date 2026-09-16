/**
 * The ladies' tee gets the outline, and the men's Red does not.
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

console.log("\nThe ladies' tee is NAMED, not just ringed");
const j = py.indexOf("def _tee_legend_display_name");
const fn = py.slice(j, py.indexOf("\ndef ", j + 1));
check("the LEADERBOARD legend renders 'Ladies - <colour> Tees'",
    /Ladies - \{base\}/.test(fn), "the legend still leans on the ring alone");
check("a men's tee is unchanged", /else base/.test(fn));
check("the board legend uses it", /_tee_legend_display_name\(label, ladies\)/.test(py));
// The BAND legend's spelling is RATIFIED separately (Kerry 2026-09-15):
// its band_label already says "Women", so the colour must NOT repeat it.
const b = py.indexOf("def _tee_name_plural");
const bf = py.slice(b, py.indexOf("\ndef ", b + 1));
// Strip the docstring first: this function DOCUMENTS the split by
// naming the other spelling, and a bare substring search finds the
// explanation and calls it the defect.
const bfCode = bf.replace(/"""[\s\S]*?"""/, "");
check("the BAND legend keeps its ratified 'Red Tees' spelling",
    !/Ladies - /.test(bfCode) && /return f"\{n\} Tees" if n else n/.test(bfCode),
    "the starter sheet's ratified label was trampled");

console.log("\nThe outline still means ladies, and only ladies");
const k = py.indexOf('"ring": ladies');
check("ring is set from the ladies flag, nothing else", k > -1);
check("ladies is detected from the tee name's (L) marker",
    /ladies = bool\(re\.search\(r"\\\(\(\?:l\|lady\|ladies\)\\\)"/.test(py));

console.log("\n" + (failures ? failures + " FAILURE(S)" : "ALL PASS"));
process.exit(failures ? 1 : 0);
