// The Events FINANCIAL panel shows the same bottom line as
// get_event_financial_summary (Kerry via CoS #1048: "does each event's
// FINANCIAL page read the same math?"). Run: node test_financial_panel_parity.js
const fs = require("fs");
const src = fs.readFileSync(__dirname + "/templates/events.html", "utf8");
const i = src.indexOf("function renderFinancialPanelServer(");
let depth = 0, j = src.indexOf("{", i);
for (let k = j; k < src.length; k++) {
  if (src[k] === "{") depth++;
  else if (src[k] === "}") { depth--; if (depth === 0) { j = k + 1; break; } }
}
const fnSrc = src.slice(i, j);
let F = 0;
const check = (l, c, d) => { console.log(`  ${c ? "PASS" : "FAIL"}  ${l}` + (c ? "" : `  ${d || ""}`)); if (!c) F++; };
const computeGamePotTotals = () => ({ hio: 25, included: 150, net: 255, gross: 169 });
const _renderPayoutsBudgetSection = () => "";
const escapeHtml = s => String(s);
const fn = new Function("computeGamePotTotals", "_renderPayoutsBudgetSection", "escapeHtml",
  fnSrc + "; return renderFinancialPanelServer;")(computeGamePotTotals, _renderPayoutsBudgetSection, escapeHtml);
const data = {  // 3304 as production serves it (v2.522.41, both v1.1 dials on)
  revenue: { godaddy: 1857, external_payments: 11, credit_transfers_in: 284, add_on_payments: 0, total: 2209.66 },
  contra_revenue: { credit_transfers_out: 0, refunds: 50, total: 50 },
  net_revenue: 2159.66, projected_profit: 150.89, allocation_coverage_pct: 100, accounting_verified: true,
  expenses: { course_fees: 1353.12, course_fees_by_holes: [], prize_fund: 539.98, processing_fees: 66.49,
              hio_contribution: 25, fellowship_meals: 24.18, total: 2008.77 },
  standard_v11: { pots: { live: true, tgf_mvp_adjust: 34 } },
  player_counts: { paid: 24, comp: 1, rsvp: 0, wd: 0, total_active: 25 },
};
let html = "";
try { html = fn(data, { item_name: "s9.25 Canyon Springs", id: 3304 }, []); } catch (e) { html = "ERR " + e.message; }
check("bottom line = the server's $150.89 (not a client re-sum)", html.includes("$150.89") && !html.includes("$200.07"), html.slice(0, 300));
check("total expenses = the server's $2,008.77", html.includes("$2008.77"));
check("HIO contribution and fellowship meal lines shown", html.includes("Hole-In-One Pot contribution") && html.includes("$24.18"));
check("TGF MVP share line shown", html.includes("TGF MVP share"));
const noPay = JSON.parse(JSON.stringify(data)); noPay.expenses.prize_fund = 0;
let h2 = fn(noPay, { item_name: "x", id: 1 }, []);
check("no recorded payouts: falls back to the client matrix sum (unchanged behaviour)",
      h2.includes(`$${(2159.66 - (1353.12 + 599 + 66.49)).toFixed(2)}`));
console.log(F ? `\n${F} FAILURE(S)` : "\nALL PASS");
process.exit(F ? 1 : 0);
