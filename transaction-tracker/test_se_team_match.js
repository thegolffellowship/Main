// The scoring card's TEAM pieces read THIS group's match (Kerry 2026-10-09:
// "if I entered a hole score why isn't the team Net score for that hole
// showing?"). The server sends every match of the session in match_status;
// Match 2's card was reading Match 1 and showed "AUS – SA –".
const fs = require("fs"), path = require("path");
const src = fs.readFileSync(path.join(__dirname, "templates/score_entry.html"), "utf8");
let fails = 0;
const check = (n, ok, info) => { console.log(`  ${ok ? "PASS" : "FAIL"}  ${n}`); if (!ok) { fails++; if (info !== undefined) console.log("      ", info); } };
const grab = (name) => { const i = src.indexOf(`function ${name}(`); let d = 0, j = src.indexOf("{", i);
    for (let k = j; k < src.length; k++) { if (src[k] === "{") d++; else if (src[k] === "}") { d--; if (!d) return src.slice(i, k + 1); } } };
// the production shape: Match 1 (other players) first, this card's Match 2 second
var card = {
  players: [{customer_id: 13, seat: 1}, {customer_id: 438, seat: 2}, {customer_id: 18, seat: 3}, {customer_id: 703, seat: 4}],
  teams: [],
  match_status: [
    {cup: true, format: "fourball", match_id: "sat-am-1", sides: [[7, 294], [136, 88]], strokes: {}},
    {cup: true, format: "fourball", match_id: "sat-am-2", sides: [[13, 438], [18, 703]], strokes: {"438": {"10": 0}}},
  ],
};
const scores = {"c:13": 5, "c:438": 3, "c:18": 4, "c:703": 4};
var draft = {}, draftX = {};
const value = (key, n) => ({v: n === 10 ? scores[key] : null});
const isX = () => false;
const byId = (cid) => card.players.find((p) => p.customer_id === cid) || {};
const esc = (x) => String(x);
const first = (x) => String(x || "").split(" ")[0];
eval(grab("subjects")); eval(grab("myTeamMatch")); eval(grab("teamScoreBox")); eval(grab("teamGroups"));
check("myTeamMatch picks the match holding this card's players, not the first", (myTeamMatch() || {}).match_id === "sat-am-2", myTeamMatch());
const box = teamScoreBox(10);
check("Match 2's team score shows its own best balls (AUS 3, SA 4)", /AUS 3/.test(box) && /SA 4/.test(box), box);
const g = teamGroups();
check("the team boxes hold this card's sides", g && g[0].keys.join() === "c:13,c:438" && g[1].keys.join() === "c:18,c:703", g);
check("the eyebrow names only this card's match", /m\.cup && \(m\.sides \|\| \[\]\)\.flat\(\)\.some\(\(c\) => mine\.has\(c\)\)/.test(src));
console.log(fails ? `\nFAILED (${fails})` : "\nALL PASS");
process.exit(fails ? 1 : 0);
