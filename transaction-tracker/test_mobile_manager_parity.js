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
check("PAIRINGS print row has a Scorecards button", /\/events\/\$\{ev\.id\}\/scorecards'/.test(s));
// Back from a print view (?event=<id>&view=pairings) must LOAD the pairings,
// not just open the tab (Kerry 2026-09-29: "stuck loading").
const deep = s.slice(s.indexOf('const evParam = params.get("event");'), s.indexOf("// Plain refresh with a row open"));
check("the ?view=pairings deep link loads the pairings it opens",
      /_wantPairings/.test(deep) && /loadPairings\(byId\.id\)/.test(deep) && /rerenderDetail\(c, ev2\)/.test(deep));
console.log(fail ? `\n${fail} failure(s)` : "\nALL PASS");
process.exit(fail ? 1 : 0);
