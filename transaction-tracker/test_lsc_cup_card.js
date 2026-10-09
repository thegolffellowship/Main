// The Cup's opened match card on the City Match Play standards (Kerry
// 2026-10-09: "These scorecards on match expansion really need to be screen
// wide for mobile. Also, are we following all of our standards we already
// worked thru on City MATCH PLAY displays?"). lscCupGrid renders the mp-sc
// grid with one row per player: a four-ball card shows both partners.
const fs = require("fs"), path = require("path");
const src = fs.readFileSync(path.join(__dirname, "templates/contests.html"), "utf8");
let fails = 0;
const check = (name, ok, info) => { console.log(`  ${ok ? "PASS" : "FAIL"}  ${name}`); if (!ok) { fails++; if (info !== undefined) console.log("      ", info); } };
const grab = (name) => { const i = src.indexOf(`function ${name}(`); let d = 0, j = src.indexOf("{", i);
    for (let k = j; k < src.length; k++) { if (src[k] === "{") d++; else if (src[k] === "}") { d--; if (!d) return src.slice(i, k + 1); } } };
const escapeHtml = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;");
eval(grab("mpMono")); eval(grab("mpFirstLast")); eval(grab("lscCupGrid"));
// four-ball: Austin 1 & 2 v SA 3 & 4. Hole 1 SA wins with 3's 4; hole 2
// Austin wins with 2's net 3 (4 less a pop) while 1 picked up at 7.
const m = { format: "fourball", closed_at_order: null,
  players: [{ customer_ids: [1, 2], lines: ["Luke YOUNGS", "Chris CANNON"] },
            { customer_ids: [3, 4], lines: ["Pat YOUNGS", "Jeff YOUNG"] }],
  holes: [{ hole: 1, order: 1, winner: 2 }, { hole: 2, order: 2, winner: 1 }, { hole: 3, order: 3, winner: null }],
  hole_pars: { "1": 5, "2": 4, "3": 3 },
  strokes: { "1": {}, "2": { "2": 1 }, "3": {}, "4": { "3": 1 } },
  scores: { "1": { "1": 5, "2": 7 }, "2": { "1": 6, "2": 4 }, "3": { "1": 4, "2": 4 }, "4": { "1": 5, "2": 5 } },
  picked_up: { "1": [2] } };
const html = lscCupGrid(m, { live: true, liveLead: { side: "A", margin: "1 UP", thru: 2 } });
const rows = html.match(/<tr class="mp-sc-strokes">[\s\S]*?<\/tr>/g) || [];
check("one row per player on a four-ball card", rows.length === 4, rows.length);
check("rows carry each player's initials in his side's chip",
      /monochip a">LY</.test(rows[0]) && /monochip a">CC</.test(rows[1]) && /monochip b">PY</.test(rows[2]) && /monochip b">JY</.test(rows[3]));
check("the hole winner's counting ball is circled in its side's colour, nobody else's",
      /won-b">4</.test(rows[2]) && /won-a">4</.test(rows[1]) && !/won-/.test(rows[0]) && !/won-/.test(rows[3]));
check("a pop dot sits in the side's colour on the hole it falls",
      /mp-sc-pop a/.test(rows[1]) && /mp-sc-pop b/.test(rows[3]));
check("Hole, Par and Tot as on the City Match Play card",
      /mp-sc-hole/.test(html) && /mp-sc-par/.test(html) && /<th class="mp-sc-tot">12<\/th>/.test(rows[0]));
check("Strokes off low lists every player", (html.match(/mp-sc-sb-item/g) || []).length === 4);
check("the live margin sits under the card", /LIVE · Austin 1 UP · thru 2/.test(html));
check("no caption on a real card", !/mp-sc-caption/.test(html));
const chap = lscCupGrid({ ...m, format: "chapman" }, { live: false });
check("Foursomes is one ball: one row per pair",
      (chap.match(/<tr class="mp-sc-strokes">/g) || []).length === 2 && /LY·CC/.test(chap));
check("the Cup card is used for every match state (before and during play)",
      /cardHtml: lscCupGrid\(m, o\)/.test(src) && /const grid = opts\.cardHtml \|\| mpScorecardGridHtml\(gen, o\)/.test(src));
check("an opened card runs screen wide on a phone",
      /@media \(max-width: 560px\) \{\s*#lsc-board \.mp-match-card:has\(> \.mp-card-head\.open\) \{\s*margin-left: calc\(50% - 50vw\); margin-right: calc\(50% - 50vw\);/.test(src));
console.log(fails ? `\nFAILED (${fails})` : "\nALL PASS");
process.exit(fails ? 1 : 0);
