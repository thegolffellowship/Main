// Tests for the Lead Center triage filters (Kerry 2026-09-01, MULTI-SELECT
// 2026-09-03). Extracts the page's OWN triageOf() out of templates/leads.html
// so the test cannot drift from the shipped classifier, then exercises the
// filter predicate: picks inside a group OR together, groups AND with each
// other. The load-bearing case is Kerry's: Availability Sat + Both must mean
// everyone who can play Saturdays.
//
// Run: node test_lead_triage_filters.js   (from transaction-tracker/)

const fs = require('fs');
const src = fs.readFileSync('templates/leads.html', 'utf8');
// pull the REAL triageOf out of the template so the test can't drift
const m = src.match(/function triageOf\(l\) \{[\s\S]*?\n    \}/);
if (!m) { console.error("could not extract triageOf"); process.exit(1); }
eval(m[0]);

const AV = { both: "yes_-_i_can_play_both_tuesdays_or_saturdays",
             tue: "yes_-_i_can_play_tuesdays",
             sat: "yes_-_i_can_play_saturdays",
             none: "neither_-_but_i'm_still_interested" };
const IM = { all: "all_of_it!_-_enjoy_a_well-rounded_experience", golf: "golf_-_explore_a_variety",
             competition: "competition_-_test_yourself", community: "community_-_connect_with_fellow_golfers" };
const IV = { both: "yes_for_both", sa: "yes_for_san_antonio", austin: "yes_for_austin", none: "no" };

const lead = (n, av, im, iv) => ({ name: n, payload: {
  ...(av ? { can_you_play_tuesdays_or_saturdays: AV[av] } : {}),
  ...(im ? { which_is_most_important_to_you: IM[im] } : {}),
  ...(iv ? { would_you_like_to_stay_in_the_loop_with_tgf_and_receive_event_invitations: IV[iv] } : {}) } });

const LEADS = [
  lead("BothAll",   "both", "all",         "both"),
  lead("BothGolf",  "both", "golf",        "sa"),
  lead("SatGolf",   "sat",  "golf",        "austin"),
  lead("SatComm",   "sat",  "community",   "both"),
  lead("TueComp",   "tue",  "competition", "sa"),
  lead("TueAll",    "tue",  "all",         "both"),
  lead("NoneAll",   "none", "all",         "none"),
  lead("Blank",     null,   null,          null),
];

let fAvail = new Set(), fWant = new Set(), fLoop = new Set();
const triActive = () => fAvail.size + fWant.size + fLoop.size;
const visible = () => LEADS.filter(l => {
  if (triActive()) {
    const t = triageOf(l);
    if (fAvail.size && !fAvail.has(t.avail)) return false;
    if (fWant.size && !fWant.has(t.want)) return false;
    if (fLoop.size && !fLoop.has(t.loop)) return false;
  }
  return true;
}).map(l => l.name);

let fails = 0;
const check = (label, got, want) => {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}${ok ? "" : `\n        got  ${JSON.stringify(got)}\n        want ${JSON.stringify(want)}`}`);
  if (!ok) fails++;
};
const reset = () => { fAvail = new Set(); fWant = new Set(); fLoop = new Set(); };

check("no filters = everyone", visible(), LEADS.map(l => l.name));

// KERRY'S CASE: Availability Sat + Both = everyone who can play Saturdays
reset(); fAvail.add("sat"); fAvail.add("both");
check("KERRY'S CASE: Sat + Both = all Saturday-available", visible(),
      ["BothAll", "BothGolf", "SatGolf", "SatComm"]);

reset(); fAvail.add("sat");
check("single pick still works (Sat only)", visible(), ["SatGolf", "SatComm"]);

reset(); fAvail.add("sat"); fAvail.add("both"); fAvail.delete("both");
check("tapping a pick off removes just that one", visible(), ["SatGolf", "SatComm"]);

reset(); fAvail.add("tue"); fAvail.add("both");
check("Tue + Both = all Tuesday-available", visible(),
      ["BothAll", "BothGolf", "TueComp", "TueAll"]);

// OR within a group, AND across groups
reset(); fAvail.add("sat"); fAvail.add("both"); fWant.add("golf");
check("Saturday-available AND Golf", visible(), ["BothGolf", "SatGolf"]);

reset(); fWant.add("golf"); fWant.add("competition");
check("Importance Golf + Competition", visible(), ["BothGolf", "SatGolf", "TueComp"]);

reset(); fLoop.add("both"); fLoop.add("sa");
check("Invites Both + SA", visible(), ["BothAll", "BothGolf", "SatComm", "TueComp", "TueAll"]);

reset(); fAvail.add("both"); fAvail.add("sat"); fWant.add("all"); fWant.add("community"); fLoop.add("both");
check("all three groups multi-selected", visible(), ["BothAll", "SatComm"]);

reset(); ["both","tue","sat","none"].forEach(v => fAvail.add(v));
check("every option selected = every lead WITH an answer (blank excluded)", visible(),
      ["BothAll","BothGolf","SatGolf","SatComm","TueComp","TueAll","NoneAll"]);

reset();
check("clear returns everyone", visible(), LEADS.map(l => l.name));

console.log(fails ? `\n${fails} FAILURE(S)` : "\nALL PASS");
process.exit(fails ? 1 : 0);
