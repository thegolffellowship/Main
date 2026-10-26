/**
 * LEADERBOARD: chapter colour bars instead of chapter badges, and one
 * house chevron everywhere (Kerry 2026-10-20, looking at Monthly on his
 * phone: "No reason for two lines on these. Let's do color bars for the
 * chapter on the left of each entry like we've done elsewhere, rather
 * than the chapter badges. Also, the chevrons don't match our standard.
 * Review all chevrons across the leaderboard and match standard.").
 *
 * The off-standard chevron was the house glyph itself: inside a Bitter
 * name cell the ▶ has no glyph in Bitter or Georgia and iPhone drew the
 * colour emoji (a boxed blue play button). The fix is in the CLASS
 * (.tgf-exp takes the system font and asks for text presentation), plus
 * U+FE0E after every leaderboard glyph, and every open state is a 90°
 * turn like the Events board — never a glyph swap to ▼.
 *
 * Run: node test_lb_chapter_bars_chevrons.js
 */
const fs = require("fs");
let failures = 0;
function check(label, cond, detail) {
    if (cond) console.log("  PASS  " + label);
    else { console.log("  FAIL  " + label + (detail ? "  " + detail : "")); failures++; }
}
const page = fs.readFileSync("templates/contests.html", "utf8");
const pr = fs.readFileSync("static/js/points-render.js", "utf8");
const css = fs.readFileSync("static/css/dashboard.css", "utf8");
const events = fs.readFileSync("templates/events.html", "utf8");

// ---- chapter bars ----
check("no chapter badge renderer is left on the leaderboard", !/prChapterBadge/.test(page.replace(/\/\/[^\n]*/g, "")));
check("the bar reuses the Events table's classes, width and tokens",
    /\.events-table tbody tr\.event-row-clickable > td:first-child \{ border-left: 8px solid #E5E7EB; \}/.test(events)
    && /#pr-table-container tbody tr\[class\*="ev-ch-"\] > td:first-child \{ border-left: 8px solid #E5E7EB; \}/.test(page)
    && /#pr-table-container tbody tr\.ev-ch-austin > td:first-child \{ border-left-color: var\(--chapter-austin, #BF5700\); \}/.test(page)
    && /#pr-table-container tbody tr\.ev-ch-sa > td:first-child \{ border-left-color: var\(--chapter-sa-alt, #8FA8B8\); \}/.test(page)
    && /tr\.ev-ch-sa > td:first-child \{ border-left-color: var\(--chapter-sa-alt, #8FA8B8\); \}/.test(events));
check("every chapter maps to a bar (rule 3d): Austin, SA, TGF, unknown, none",
    /function prChapterBarClass/.test(page) && ["ev-ch-austin", "ev-ch-sa", "ev-ch-tgf", "ev-ch-other", "ev-ch-none"].every(c => page.includes(`"${c}"`)));
check("the Points Race (cross-chapter), Fellowship Cup and Monthly rows each carry the bar",
    (page.match(/prChapterBarClass\(r\.(player_)?chapter\)/g) || []).length === 3);
check("Monthly is one line: no badge line under the name, the month-won trophy rides the name",
    page.includes('<span class="pr-nm-n">${name}${win ? \' <span class="tgf-troph" title="Month won"></span>\' : ""}</span><span class="pr-nm-chev">${chevron}</span></span><span class="pr-nm-b"></span>'));
check("Fellowship Cup: the handicap sits on the name line, not the badge line",
    page.includes('<span class="pr-nm-n">${nameCell}${cupSlimF ? "" : hcp}</span><span class="pr-nm-chev">${chevF}</span>'));

// ---- chevrons ----
const std = css.slice(css.indexOf(".tgf-exp {"), css.indexOf(".tgf-exp {") + 1200);
check("the house arrow never inherits a Bitter cell's font and asks for text, not emoji",
    /font-family: -apple-system/.test(std) && /font-variant-emoji: text;/.test(std));
check("the open state is a 90° turn on the class", /\.tgf-exp\.is-open \{ transform: rotate\(90deg\); \}/.test(css));
for (const [name, src] of [["contests.html", page], ["points-render.js", pr]]) {
    const spans = src.match(/class="[^"]*tgf-exp[^"]*"[^>]*>[^<]*/g) || [];
    const off = spans.filter(s => !/>&#9654;&#xFE0E;$/.test(s));
    check(`${name}: every house arrow is ▶ + U+FE0E (${spans.length})`, spans.length > 0 && off.length === 0, off.slice(0, 3).join(" | "));
    check(`${name}: no expand arrow swaps its glyph for ▼ (it turns instead)`,
        !/innerHTML\s*=\s*[^;\n`]{0,30}["']&#96(54|60);["']/.test(src) && !/"&#9660;"\s*:\s*"&#9654;"|"&#9654;"\s*:\s*"&#9660;"/.test(src) && !/textContent\.indexOf\("\\u25BC"\)/.test(src));
    check(`${name}: no off-standard chevron glyphs (› ▴ ▸)`, !/&rsaquo;|&#8250;|&#9652;|&#9656;|[›▸▴]/.test(src.replace(/\/\*[\s\S]*?\*\/|\/\/[^\n]*/g, "")));
}
check("points-render.js keeps no ▼ at all", !/&#9660;/.test(pr));
check("Past Champions shows the house arrow, not the browser's disclosure triangle",
    /\.past-champs > summary::-webkit-details-marker \{ display: none; \}/.test(page) && /\.past-champs > summary \{ list-style: none; \}/.test(page)
    && page.includes('<summary><span class="pc-chev tgf-exp">&#9654;&#xFE0E;</span>Past Champions'));
check("Match Play's chip and card hint use the house arrow",
    page.includes('Matches <span class="mp-mc-chev tgf-exp">&#9654;&#xFE0E;</span>')
    && page.includes(`'<span class="tgf-exp is-open">&#9654;&#xFE0E;</span> <span class="mp-hint-long">collapse card</span>`));
check("open-state readers read the class, not the glyph",
    page.includes('const open = !!chev && chev.classList.contains("is-open");'));

console.log("\n" + (failures ? failures + " FAILURE(S)" : "ALL PASS"));
process.exit(failures ? 1 : 0);
