/**
 * The Edit Event calculator must agree with the saved course cost.
 *
 * Kerry 2026-09-09, off the Austin upcoming list: "Pricing should be
 * based off of what is in the Pricing List in the editor. I thought when
 * I asked you to bring those numbers in that you were also populating
 * the source in the editor?"
 *
 * The list column reads events.course_cost. The editor's Pricing List
 * reads the Course Cost calculator, which was seeded ONLY from the
 * line-item breakdown JSON — and costs entered through the API / MCP
 * tools carry no breakdown. So the calculator read $0.00, the tiers were
 * built from markup + games alone, and saving from that screen wrote
 * course_cost = null. Two screens, one number, two answers.
 *
 * Run: node test_event_pricing_editor.js
 */
const fs = require("fs");
const html = fs.readFileSync("templates/events.html", "utf8");
let failures = 0;
function check(label, cond, detail) {
    if (cond) { console.log("  PASS  " + label); }
    else { console.log("  FAIL  " + label + (detail ? "  " + detail : "")); failures++; }
}

// Lift the two pure helpers out of the template and run them for real.
function lift(name) {
    const m = html.match(new RegExp("function " + name + "\\([\\s\\S]*?\\n    \\}\\n"));
    if (!m) throw new Error("could not find " + name);
    return m[0];
}
const src = lift("breakdownTotal") + lift("breakdownForEditor")
    + "\nreturn { breakdownTotal, breakdownForEditor };";
const { breakdownTotal, breakdownForEditor } = new Function(src)();

console.log("\nThe seed rule");
let s = breakdownForEditor(null, 43.3);
check("no breakdown + saved cost -> a single tax-free Green Fees line equal to the cost",
    s.synthesized && !s.mismatch && s.breakdown.green_fees.amount === 43.3 && s.breakdown.green_fees.tax_pct === 0,
    JSON.stringify(s));
check("the synthesized line totals exactly the saved cost",
    breakdownTotal(s.breakdown) === 43.3);

const real = JSON.stringify({ green_fees: { amount: 40, tax_pct: 8.25 }, cart_fees: { amount: 0, tax_pct: 8.25 } });
s = breakdownForEditor(real, 43.3);
check("a breakdown that totals the saved cost is used as-is",
    !s.synthesized && s.breakdown.green_fees.amount === 40, JSON.stringify(s));

s = breakdownForEditor(real, 54.13);
check("a breakdown that DISAGREES with the saved cost is replaced — the saved cost wins",
    s.synthesized && s.mismatch && s.breakdown.green_fees.amount === 54.13 && s.breakdownTotal === 43.3,
    JSON.stringify(s));

s = breakdownForEditor(real, null);
check("a breakdown with no saved cost is used as-is (nothing to disagree with)",
    !s.synthesized && s.breakdown.green_fees.amount === 40);

s = breakdownForEditor(null, null);
check("nothing on file -> empty calculator, no note",
    s.breakdown === null && !s.synthesized);

s = breakdownForEditor(JSON.stringify({ green_fees: { amount: 0, tax_pct: 8.25 } }), 48.71);
check("an all-zero breakdown (the wipe the bug wrote) is treated as missing",
    s.synthesized && s.breakdown.green_fees.amount === 48.71, JSON.stringify(s));

s = breakdownForEditor("{not json", 48.71);
check("unparseable breakdown JSON falls back to the saved cost, never throws",
    s.synthesized && s.breakdown.green_fees.amount === 48.71);

console.log("\nWired into the editor");
check("single-format calculator is seeded through the rule",
    /const singleSeed = breakdownForEditor\(ev\.course_cost_breakdown, ev\.course_cost\);\s*\n\s*renderCostCalculator\("edit-single-calc", "edit-single", singleSeed\.breakdown\);/.test(html));
check("combo 9-hole calculator is seeded through the rule",
    /breakdownForEditor\(ev\.course_cost_breakdown_9, ev\.course_cost_9\)/.test(html));
check("combo 18-hole calculator is seeded through the rule",
    /breakdownForEditor\(ev\.course_cost_breakdown_18, ev\.course_cost_18\)/.test(html));
check("the editor says when it is showing an imported total",
    /noteImportedCost\("edit-single-calc", singleSeed\);/.test(html)
    && /no line-item breakdown on file\. Saving keeps the total\./.test(html));
check("the old direct JSON.parse seed is gone",
    !/const singleBreakdown = ev\.course_cost_breakdown \? JSON\.parse/.test(html));

console.log("");
if (failures) { console.log(failures + " FAILED"); process.exit(1); }
console.log("all passed");
