// The phone has every manager ability the desktop has (Kerry 2026-09-28,
// #920). Guards the two gaps closed that night: the mobile roster card's
// HCP field sets a starting handicap with the SAME control as the desktop
// cell, and PAIRINGS' print row links to the scorecards page (#919).
// Run: node test_mobile_manager_parity.js
const fs = require("fs");
const s = fs.readFileSync(__dirname + "/templates/events.html", "utf8");
let fail = 0;
const check = (label, ok) => { console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}`); if (!ok) fail++; };
const helper = s.slice(s.indexOf("function _mobileHcpField("), s.indexOf("function hcpEntryFor("));
check("a mobile HCP helper exists", helper.length > 50);
check("it renders the desktop's .btn-set-hcp control", /class="btn-set-hcp"/.test(helper));
check("a STARTING placeholder is editable (data-current)", /data-current/.test(helper));
check("both mobile field lists use it",
      (s.match(/\["HCP", _mobileHcpField\(r, ev, showHcp18Only\)\]/g) || []).length === 2);
check("mobile fields can carry HTML (the button) while text stays escaped",
      /v\.html\) \? v\.html : escapeHtml\(v\)/.test(s));
check("one handler serves both: .btn-set-hcp posts to the starting-handicap endpoint",
      /querySelectorAll\("\.btn-set-hcp"\)[\s\S]{0,4000}\/api\/customers\/\$\{cid\}\/starting-handicap/.test(s));
// REPORTS tab (Kerry 2026-09-29: "move the print reports stuff to it's own
// tab on the toggle bar. After Flights") — desktop AND phone.
const rp = s.slice(s.indexOf("function renderReportsPanel(ev)"), s.indexOf("function renderFlightsPanel(ev)"));
for (const r of ["starter-sheet", "cart-signs", "scorecards", "divisions-flights", "proximity-markers"])
    check(`REPORTS panel opens ${r}`, rp.includes(`open("${r}"`));
check("REPORTS panel has Send Pack", /sendPrintPack\(\$\{ev\.id\}, this\)/.test(rp));
check("REPORTS badge sits right after FLIGHTS on desktop and phone",
      (s.match(/FLIGHTS<\/span>`;\s*\}\s*(?:\/\/[^\n]*\n\s*)*(?:html|badgesHtml) \+= `<span class="game-stat-badge \$\{(?:reportsView|mobileReportsView)/g) || []).length === 2);
check("the phone renders the REPORTS panel", /mobileReportsView\) \{\s*detailHtml = badgesHtml \+ renderReportsPanel\(ev\)/.test(s));
check("print buttons are gone from the PAIRINGS row (pairing tools stay)",
      !/renderPairingsPanel[\s\S]*starter-sheet','_blank'/.test(s.slice(s.indexOf("function renderPairingsPanel"), s.indexOf("// ── SCORE ENTRY panel")))
      && /data-pairings-action="generate"/.test(s) && /pairings-blinds-btn/.test(s));
// GG Sheet is gone (Kerry 10/9: "I never used that GG Sheet thing anyway.
// That can be removed."); events are paired in the Tracker.
check("no GG Sheet pull on PAIRINGS", !/gg-import|GG Sheet/.test(s));
check("?view=reports opens the REPORTS tab", /params\.get\("view"\) === "reports"[\s\S]{0,120}applyDetailView\(byId\.id, "6"\)/.test(s));
// Back from a print view (?event=<id>&view=pairings) must LOAD the pairings,
// not just open the tab (Kerry 2026-09-29: "stuck loading").
const deep = s.slice(s.indexOf('const evParam = params.get("event");'), s.indexOf("// Plain refresh with a row open"));
check("the ?view=pairings deep link loads the pairings it opens",
      /_wantPairings/.test(deep) && /loadPairings\(byId\.id\)/.test(deep) && /rerenderDetail\(c, ev2\)/.test(deep));
// Kerry 10/9: "Can't see all the toggles in mobile view" -- the event's tabs
// wrap into rows of four on a phone
check("the phone's event tabs wrap into rows so every tab shows",
      /'<span class="view-toggle-group ev-tabs">'/.test(s)
      && /\.view-toggle-group\.ev-tabs \{ display: grid; grid-template-columns: repeat\(4, 1fr\)/.test(s));
console.log(fail ? `\n${fail} failure(s)` : "\nALL PASS");
process.exit(fail ? 1 : 0);
