/**
 * The `○ = plus stroke` mark, and the NET row that went with it.
 *
 * Kerry, 2026-09-15, on Pat Youngs' Quarry Front card: "We just
 * determined this isn't how we do Net Points with pluses on holes." The
 * card drew a `○` on holes 3, 4 and 8 and rendered NET 4 over a GROSS 3,
 * because both renderers computed the net cell client-side as
 * `strokes - strokes_received` and a give-back is negative.
 *
 * Under the rule a plus comes off the ROUND, so no hole carries a
 * give-back, there is nothing to mark, and the legend entry goes with it.
 * The server publishes `game_strokes_received` / `game_stableford_net`
 * beside the true WHS values (which `verify_scoring_round` still needs
 * for GG parity), and the card renders the GAME view.
 *
 * Run: node test_plus_handicap_render.js
 */
const fs = require("fs");
let failures = 0;
function check(label, cond, detail) {
    if (cond) console.log("  PASS  " + label);
    else { console.log("  FAIL  " + label + (detail ? "  " + detail : "")); failures++; }
}

const files = {
    "scorecard-render.js": fs.readFileSync("static/js/scorecard-render.js", "utf8"),
    "points-render.js": fs.readFileSync("static/js/points-render.js", "utf8"),
};

for (const [name, src] of Object.entries(files)) {
    console.log("\n" + name);
    check("reads the GAME strokes-received the server publishes",
        /game_strokes_received/.test(src));
    check("the net cell no longer subtracts a raw strokes_received",
        !/strokes\s*-\s*\(h\.strokes_received\s*\|\|\s*0\)/.test(src),
        "the give-back is back on the hole");
    check("net POINTS come from the game view",
        /game_stableford_net/.test(src));
    check("only strokes RECEIVED are marked — no give-back circle",
        !/"●"\s*:\s*"○"/.test(src) && !/○/.test(src.split("legend")[0]) || !/○/.test(src),
        "the ○ mark survives");
    check("the ○ legend entry is gone with it",
        !/= plus stroke/.test(src), "the legend still promises a mark");
    check("the round adjustment is stated on the card",
        /plus_points_adjust/.test(src) && /plus_strokes_adjust/.test(src));
    check("…naming that it applies to the ROUND, not a hole",
        /applied to the ROUND, not to any hole/.test(src));
    check("…and showing the totals it lands on",
        /game_net_after_plus/.test(src) && /game_stableford_net_after_plus/.test(src));
    check("a non-plus card renders no adjustment line",
        /\(plusPts \|\| plusStr\)/.test(src),
        "the line is unconditional — every card would carry it");
    check("the true WHS value is still the fallback for an old payload",
        /:\s*\(h\.strokes_received\s*\|\|\s*0\)/.test(src));
}

console.log("\nThe server publishes what the renderers read");
const py = fs.readFileSync("email_parser/database.py", "utf8");
const fn = py.slice(py.indexOf("def get_scorecard(scoring_round_id"));
const body = fn.slice(0, fn.indexOf("\ndef ", 1));
for (const key of ["game_strokes_received", "game_stableford_net",
                   "game_net_vs_par", "strokes_given_back",
                   "plus_points_adjust", "plus_strokes_adjust",
                   "game_net_after_plus", "game_stableford_net_after_plus"]) {
    check(`get_scorecard publishes ${key}`, body.includes(key));
}
check("…and keeps the TRUE net_vs_par, which GG parity compares against",
    /row = dict\(h\) \| d\b/.test(body),
    "verify_scoring_round would fail every plus player's round");

console.log("\n" + (failures ? failures + " FAILURE(S)" : "ALL PASS"));
process.exit(failures ? 1 : 0);
