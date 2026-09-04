/**
 * Events-table Start and Pricing columns (Kerry 2026-09-04:
 * "I need a quicker visual on that").
 *
 * The pricing cell must reproduce the Edit Event screen EXACTLY — it
 * reuses that screen's own calcPricingLine + getPlayerMarkups rather
 * than reimplementing the arithmetic, and this locks that in against
 * the real production Silverhorn row (course_cost 48.71, markup 8,
 * games 7 -> member $64 / guest $74 / 1st Timer $49, the figures CA
 * verified).
 *
 * Run: node test_event_columns.js
 */
const fs = require("fs");
const path = require("path");
const FAILURES = [];
const check = (label, cond, detail) => {
    if (cond) console.log("  PASS  " + label);
    else { console.log("  FAIL  " + label + "  " + (detail || "")); FAILURES.push(label); }
};

// Pull the functions under test straight out of the page.
const html = fs.readFileSync(path.join(__dirname, "templates/events.html"), "utf8");
const grab = (name, kind) => {
    const re = new RegExp("(?:function|const)\\s+" + name + "\\b");
    const at = html.search(re);
    if (at < 0) throw new Error("not found: " + name);
    // brace-match from the first { after the signature
    let i = html.indexOf("{", at), depth = 0, end = i;
    for (; end < html.length; end++) {
        if (html[end] === "{") depth++;
        else if (html[end] === "}") { depth--; if (!depth) { end++; break; } }
    }
    return html.slice(at, end);
};
const SRC = ["calcPricingLine", "getPlayerMarkups", "_evShortTime",
             "_evStartKind", "_evStartLeg", "evStartCell", "_evPriceTrio",
             "_evPriceTrioHtml", "evPriceCell"].map(n => grab(n)).join("\n");
// new Function keeps the extracted declarations in their own scope —
// eval at module top level collides with the consts below.
const F = new Function(SRC + "\nreturn {evStartCell, evPriceCell, _evShortTime, _evPriceTrio};")();
const evStartCell = F.evStartCell, evPriceCell = F.evPriceCell,
      _evShortTime = F._evShortTime, _evPriceTrio = F._evPriceTrio;

console.log("Time formatting");
check("17:30 -> 5:30p", _evShortTime("17:30") === "5:30p", _evShortTime("17:30"));
check("08:30 -> 8:30a", _evShortTime("08:30") === "8:30a", _evShortTime("08:30"));
check("on the hour drops :00", _evShortTime("17:00") === "5p", _evShortTime("17:00"));
check("noon is 12p", _evShortTime("12:00") === "12p", _evShortTime("12:00"));
check("midnight is 12a", _evShortTime("00:15") === "12:15a", _evShortTime("00:15"));
check("blank stays blank", _evShortTime("") === "" && _evShortTime(null) === "");

console.log("Start cell");
const SILVERHORN = { format: "9 Holes", start_time: "17:30", start_type: "Shotgun",
    course_cost: 48.71, tgf_markup: 8, side_game_fee: 7, transaction_fee_pct: 3.5 };
check("shotgun is 's'", /5:30p.*>s</.test(evStartCell(SILVERHORN)), evStartCell(SILVERHORN));
check("tee times is 'tt'",
      /8:30a.*>tt</.test(evStartCell({ start_time: "08:30", start_type: "Tee Times" })),
      evStartCell({ start_time: "08:30", start_type: "Tee Times" }));
check("no start info shows a dash", evStartCell({}) === "—", evStartCell({}));
const combo = evStartCell({ format: "9/18 Combo", start_time: "17:30",
    start_type: "Shotgun", start_time_18: "08:30", start_type_18: "Tee Times" });
check("a combo labels both legs", combo.includes(">9<") && combo.includes(">18<")
      && combo.includes("5:30p") && combo.includes("8:30a"), combo);

console.log("Pricing — against the real production Silverhorn row");
const t = _evPriceTrio(48.71, 8, 7, 3.5, "9 Holes");
check("member $64", t.member === 64, t);
check("guest $74 (+$10 on a 9)", t.guest === 74, t);
check("1st Timer $49 (guest - $25)", t.firstTimer === 49, t);
const cell = evPriceCell(SILVERHORN);
check("the cell renders all three", /\$64/.test(cell) && /\$74/.test(cell) && /\$49/.test(cell), cell);

console.log("The other formats");
const t18 = _evPriceTrio(90.65, 15, 14, 3.5, "18 Holes");
check("18-hole guest is +$15", t18.guest - t18.member === 15, t18);
check("18-hole 1st Timer is guest - $25", t18.firstTimer === t18.guest - 25, t18);
const t27 = _evPriceTrio(100, 20, 10, 3.5, "27 Holes");
check("27-hole guest is +$25", t27.guest - t27.member === 25, t27);
check("27 Holes has NO 1st Timer tier", t27.firstTimer === null, t27);
check("and the cell shows a dash there, never $0",
      /ev-p-na/.test(evPriceCell({ format: "27 Holes", course_cost: 100,
                                   tgf_markup: 20, side_game_fee: 10 })),
      evPriceCell({ format: "27 Holes", course_cost: 100, tgf_markup: 20, side_game_fee: 10 }));

console.log("Unknown cost");
// Forest Creek: uncontracted, no course cost yet. A $0 here is a number
// somebody could quote to a member.
const unknown = evPriceCell({ format: "18 Holes", course_cost: null, tgf_markup: null });
check("no course cost renders a dash, not $0",
      unknown.includes("ev-p-na") && !unknown.includes("$"), unknown);
check("markup without cost is still a dash",
      evPriceCell({ course_cost: null, tgf_markup: 15 }).includes("ev-p-na"));

console.log("Combo pricing");
const comboCell = evPriceCell({ format: "9/18 Combo", course_cost_9: 48.71,
    tgf_markup_9: 8, side_game_fee_9: 7, course_cost_18: 90.65,
    tgf_markup_18: 15, side_game_fee_18: 14, transaction_fee_pct: 3.5 });
check("a combo prices both legs separately",
      comboCell.includes(">9<") && comboCell.includes(">18<")
      && comboCell.includes("$64") && comboCell.includes("$120"), comboCell);

console.log("");
if (FAILURES.length) { console.log(FAILURES.length + " FAILURE(S): " + FAILURES.join(", ")); process.exit(1); }
console.log("ALL PASS");
