/**
 * The pairings panel must permit wrapping at the CONTAINER (Kerry
 * 2026-09-08: "fix pairings view when Requests is open — should be the
 * same as when requests is closed").
 *
 * The panel renders inside .event-detail-row > td, and dashboard.css
 * declares a global `tbody td { white-space: nowrap }` that block
 * children inherit. With Requests open, the explainer paragraph (~1,100
 * characters) could not wrap, laid out as one enormous line, grew the
 * cell, grew the groups grid with it, and stretched the auto-fit
 * columns to roughly double width — two fat groups off the right edge
 * instead of three that fit.
 *
 * These assertions pin the container-level override so a future block
 * added to the panel inherits wrapping instead of the hazard.
 *
 * Run: node test_pairings_wrap.js
 */
const fs = require("fs");

const html = fs.readFileSync("templates/events.html", "utf8");
const css = fs.readFileSync("static/css/dashboard.css", "utf8");

let failures = 0;
function check(label, cond, detail) {
    if (cond) { console.log("  PASS  " + label); }
    else { console.log("  FAIL  " + label + (detail ? "  " + detail : "")); failures++; }
}

// The hazard is real: if this global ever goes away the override below
// becomes harmless rather than wrong, but the reason should be visible.
check("dashboard.css still declares the global tbody td nowrap",
      /tbody td\s*\{[^}]*white-space:\s*nowrap/.test(css));

// The panel renders inside a table cell, which is what makes it inherit.
check("the pairings panel renders inside .event-detail-row > td",
      html.includes('class="event-detail-row') &&
      html.includes(".event-detail-row > td"));

const panelRule = html.match(/\.pairings-panel\s*\{[^}]*\}/);
check("a .pairings-panel rule exists", !!panelRule);
check("the panel itself declares white-space: normal, so every block "
      + "inside it inherits wrapping",
      !!panelRule && /white-space:\s*normal/.test(panelRule[0]),
      panelRule && panelRule[0]);

// The narrow stat columns opt back out — "50-64" must never break.
const optOut = html.match(
    /\.pairings-panel \.pairing-points[\s\S]{0,200}?white-space:\s*nowrap/);
check("the narrow stat columns opt back out of wrapping", !!optOut);
["pairing-hcp", "pairing-tee"].forEach(c =>
    check(`  ... including .${c}`,
          !!optOut && optOut[0].includes(c)));

// The requests explainer is the block that exposed this. It must not
// carry its own nowrap, and must live inside the panel.
const reqPanel = html.indexOf("Partner requests in <strong>signup order");
check("the requests explainer is present", reqPanel > 0);
const around = html.slice(Math.max(0, reqPanel - 400), reqPanel + 200);
check("the requests explainer sets no nowrap of its own",
      !/white-space:\s*nowrap/.test(around));

console.log();
if (failures) { console.log(failures + " FAILED"); process.exit(1); }
console.log("All checks passed.");
