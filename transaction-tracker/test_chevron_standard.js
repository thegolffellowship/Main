/**
 * One expand arrow, everywhere: the house `.tgf-exp` glyph (▶, orange,
 * rotates 90° when open). Kerry 2026-09-15: "Standard chevron is
 * supposed to be orange." `/me` and Money Flow each had a grey glyph of
 * their own — carried as "two off-standard chevrons" since then.
 *
 * Run: node test_chevron_standard.js
 */
const fs = require("fs");
let failures = 0;
function check(label, cond, detail) {
    if (cond) console.log("  PASS  " + label);
    else { console.log("  FAIL  " + label + (detail ? "  " + detail : "")); failures++; }
}
const css = fs.readFileSync("static/css/dashboard.css", "utf8");
const std = css.slice(css.indexOf(".tgf-exp {"), css.indexOf(".tgf-exp {") + 400);
check("the house arrow is orange and 0.75rem", /var\(--primary, #E87C3E\)/.test(std) && /font-size: 0\.75rem/.test(std));

const mf = fs.readFileSync("templates/moneyflow.html", "utf8");
check("Money Flow uses the house class and glyph", /class="chev tgf-exp"/.test(mf) && /&#9654;/.test(mf));
check("…and no longer paints its own grey colour or size",
    !/\.mf-line \.chev \{[^}]*color/.test(mf) && !/\.mf-line \.chev \{[^}]*font-size/.test(mf));
check("…and rotates when open", /\.mf-line\.open \.chev \{ transform:rotate\(90deg\); \}/.test(mf));

const me = fs.readFileSync("templates/me.html", "utf8");
check("/me takes the house values (it does not load dashboard.css)",
    /\.chev \{[^}]*color:#E87C3E[^}]*font-size:0\.75rem/.test(me) && /\.chev\.open \{ transform: rotate\(90deg\); \}/.test(me));
check("/me uses the house glyph", /class="chev">&#9654;</.test(me));
check("/me rotates by class instead of swapping glyphs",
    !/innerHTML = "&#9656;"/.test(me) && !/innerHTML = "&#9662;"/.test(me) && /classList\.add\("open"\)/.test(me));
for (const [name, src] of [["moneyflow.html", mf], ["me.html", me]]) {
    check(`${name} carries none of the old glyphs`, !/&#9656;|&#9662;/.test(src));
}
console.log("\n" + (failures ? failures + " FAILURE(S)" : "ALL PASS"));
process.exit(failures ? 1 : 0);
