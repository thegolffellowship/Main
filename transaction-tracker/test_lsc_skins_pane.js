// Skins pane (Side Games, #1398) — since Kerry 10/9 ("Skins leaderboard
// should look just like the event leaderboard") drawn by the EVENTS
// leaderboard's own renderer (evlbStdBoard). Runs the page's own functions,
// cut from templates/contests.html (the whole evlb renderer region plus the
// Cup's adapter), on a member board (no money) and a staff board, and checks
// what each shows.
const fs = require("fs");
const src = fs.readFileSync(__dirname + "/templates/contests.html", "utf8");
function cut(name) {
    const i = src.indexOf(`    function ${name}(`);
    if (i < 0) throw new Error("missing " + name);
    let depth = 0, j = src.indexOf("{", i);
    for (let k = j; k < src.length; k++) {
        if (src[k] === "{") depth++;
        else if (src[k] === "}" && --depth === 0) return src.slice(i, k + 1);
    }
}
const lines = src.split("\n");
const a = lines.findIndex(l => l.startsWith("    const EVLB_FLIGHT_COLORS"));
const b = lines.findIndex(l => l.startsWith("    function evlbEventHtml(d) {"));
if (a < 0 || b < 0) throw new Error("evlb renderer region not found");
const escapeHtml = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
eval(lines.slice(a, b).join("\n") + "\n" + cut("lscSkinsEvlbData") + "\n" + cut("lscSkinsBoard")
     + "\n" + cut("lscSkinsPane")
     + "\nglobalThis.pane = lscSkinsPane; globalThis.data = lscSkinsEvlbData;");
let fails = 0;
const check = (l, c, d) => { console.log((c ? "  PASS  " : "  FAIL  ") + l + (c ? "" : "  " + (d || "").slice(0, 600))); if (!c) fails++; };

// Saturday PM Foursomes, team NET, one flight, 8 holes, holes 6-8 open
const totals = [{ key: "M1:austin", label: "Youngs & Cloer", team: "austin", skins: 2 },
                { key: "M2:sa", label: "Youngs & Young", team: "sa", skins: 1 }];
const holes = [{ hole: 1, status: "tied" }, { hole: 2, status: "won", winner: "M1:austin", value: 1 },
               { hole: 3, status: "tied" }, { hole: 4, status: "won", winner: "M2:sa", value: 1 },
               { hole: 5, status: "won", winner: "M1:austin", value: 1 },
               { hole: 6, status: "pending" }, { hole: 7, status: "pending" }, { hole: 8, status: "pending" }];
const par = { 1: 4, 2: 4, 3: 3, 4: 5, 5: 4, 6: 4, 7: 4, 8: 4 };
const cards = { "M1:austin": { 1: [4, 0], 2: [4, 1], 3: [3, 0], 4: [5, 0], 5: [4, 1], 6: [4, 0] },
                "M2:sa": { 1: [4, 0], 2: [5, 0], 3: [3, 0], 4: [4, 0], 5: [5, 0] } };
const fsMember = { id: "sat-pm", format: "chapman", label: "FOURSOMES",
    matches: [{ state: "live", tee_time: "1:30 PM" }, { state: "live" }, { state: "final" }],
    skins: { kind: "team", basis: "net", groups: [{ flight: null, totals, holes, par, cards,
             entrants: 2, complete: false,
             entries: { "M1:austin": { index: null, ph: 9 }, "M2:sa": { index: null, ph: 14 } } }] } };
const h = pane(fsMember);
check("title + basis line", h.includes("Foursomes team skins") && h.includes("net · one flight · live"), h);
check("drawn by the EVENT leaderboard's own table", h.includes('class="evlb-holes evlb-ovr') && h.includes('data-board="evb'), h);
check("lands hole by hole (the circles are the board)", !/evlb-ovr[^"]*no-holes/.test(h), h);
check("the PAR row", h.includes('class="evlb-parrow"'), h);
check("a row per team, named, with its side", h.includes("Youngs &amp; Cloer") && h.includes("Austin") && h.includes("San Antonio"), h);
check("a won hole is circled in the flight colour", (h.match(/class="evlb-circ"/g) || []).length === 3, h);
check("pops show on the ball that counted", h.includes('class="evlb-pops"'), h);
check("# column beside Won, counts 2 and 1",
      h.includes('title="Skins won">#</th>') && h.includes('<td class="bl br gc" style="">2</td>') && h.includes('<td class="bl br gc" style="">1</td>'), h);
check("team skins are NET: no gross column", !h.includes('title="Gross score"') && h.includes('title="Net score"'), h);
check("member view: Won column hidden and no dollars", /evlb-ovr[^"]*no-won/.test(h) && !h.includes("$"), h);
check("no Show All Players box (nobody outside the skins is on it)", !h.includes("data-ovr-all"), h);
check("Chapman note", h.includes("Chapman 60/40 allowance"), h);
const dd = data(fsMember);
check("team net total = gross less pops over the holes played",
      dd.overall_board[0].net === 24 - 2 && dd.overall_board[0].to_par_net === 22 - 24, JSON.stringify(dd.overall_board[0]));
check("member board carries no money on the rows", dd.overall_board.every(r => !r.won_total), JSON.stringify(dd.overall_board));

// staff, round complete: Won column + amounts + pot line
const staff = JSON.parse(JSON.stringify(fsMember));
Object.assign(staff.skins, { pot_cents: 57500, buyers_in_round: 23, flags: ["x flag"] });
const g0 = staff.skins.groups[0];
g0.pot_cents = 57500; g0.complete = true;
g0.holes = g0.holes.map(x => x.status === "pending" ? Object.assign({}, x, { status: "tied" }) : x);
g0.payouts = [{ key: "M1:austin", cents: 38333 }, { key: "M2:sa", cents: 19167 }];
const hs = pane(staff);
check("staff see the pot", hs.includes("pot $575.00"), hs);
check("staff see each winner's amount in Won", hs.includes("$383.33") && hs.includes("$191.67") && !/evlb-ovr[^"]*no-won/.test(hs), hs);
check("staff see flags", hs.includes("x flag"));
// staff, cards still out: the money waits like the event board's
const held = JSON.parse(JSON.stringify(staff));
held.skins.groups[0].complete = false; held.skins.groups[0].payouts = null;
const hh = pane(held);
check("staff mid-round: Won hidden until every card is in", /evlb-ovr[^"]*no-won/.test(hh) && hh.includes("Won shows once every card is in"), hh);

// Sunday singles, individual GROSS, two flights, before the first tee
const sun = { id: "sun", format: "singles", matches: [{ state: "upcoming", tee_time: "8:30 AM" }],
    skins: { kind: "individual", basis: "gross", groups: [
        { flight: 1, members: [{ name: "Pat Youngs" }, { name: "Mesa" }, { name: "Walter Hogue" }],
          holes: [{ hole: 1, status: "pending" }], par: { 1: 4 }, cards: {}, entrants: 3,
          totals: [{ key: "S1:austin:1", label: "Pat Youngs", team: "austin", skins: 0 },
                   { key: "S2:sa:2", label: "Mesa", team: "sa", skins: 0 },
                   { key: "S3:austin:3", label: "Walter Hogue", team: "austin", skins: 0 }],
          entries: { "S1:austin:1": { index: 3.2, ph: 4 } } },
        { flight: 2, members: [{ name: "Callaway" }, { name: "Rideout" }],
          holes: [{ hole: 1, status: "pending" }], par: { 1: 4 }, cards: {}, entrants: 2,
          totals: [{ key: "S1:sa:4", label: "Callaway", team: "sa", skins: 0 },
                   { key: "S2:austin:5", label: "Rideout", team: "austin", skins: 0 }] }] } };
const hn = pane(sun);
check("Sunday title + basis", hn.includes("Singles skins") && hn.includes("gross · two flights · 8:30 AM"), hn);
check("a band per flight with its size", hn.includes("Flight 1 · index under 12.0 · 3 players") && hn.includes("Flight 2 · index 12.0 and up · 2 players"), hn);
check("Sunday skins are GROSS: no net column", hn.includes('title="Gross score"') && !hn.includes('title="Net score"'), hn);
check("every flighted player listed before a ball is struck", ["Pat Youngs", "Mesa", "Walter Hogue", "Callaway", "Rideout"].every(n => hn.includes(n)), hn);
check("the frozen index rides in Idx", hn.includes('<td class="bl hc">3.2</td>'), hn);
check("no skins data -> nothing", pane({ skins: null }) === "");

// Kerry 10/9: "Stack player names in team skins" — one partner per line,
// first initial + LAST (the scoring page's match strip); Sunday unchanged
const stk = JSON.parse(JSON.stringify(fsMember));
stk.skins.groups[0].entries["M1:austin"].names = ["Luke Youngs", "Chris Cannon"];
const hk = pane(stk);
check("team name stacked: L. YOUNGS over C. CANNON",
      hk.includes('<span class="evlb-nm-stack" title="Youngs &amp; Cloer"><span>L. YOUNGS</span><span>C. CANNON</span></span>'), hk);
check("a team with no names list stacks its label's halves",
      hk.includes("<span>YOUNGS</span><span>YOUNG</span>"), hk);
check("the row keeps its plain name for sorting / lookups",
      data(stk).overall_board[0].player_name === "Youngs & Cloer", JSON.stringify(data(stk).overall_board[0]));
check("Sunday singles names are not stacked", !hn.includes("evlb-nm-stack") && hn.includes(">Pat Youngs<"), hn);
// ONE team score per hole: the board's hole cell is the counting ball only
// (compute_skins `cards` = [gross, pops] of the ball that counted)
check("one score per team per hole (hole 2: the counting 4 with its pop, circled)",
      /<td class="h"><span class="evlb-pops"[^>]*>[^<]*<\/span><span class="evlb-circ"[^>]*>4<\/span><\/td>/.test(hk), hk);

// the renderer and its wiring are the event board's, not a copy
check("lscSkinsPane draws through evlbStdBoard", cut("lscSkinsPane").includes("evlbStdBoard("));
check("the Cup render wires its boards with evlbWireBoards", /evlbWireBoards\(box\)/.test(src));
check("an event body is wired through the same evlbWireBoards", /function evlbWireEvent[\s\S]{0,600}evlbWireBoards\(body\)/.test(src));
// v2.529.0: it opens the Skins rules IN PLACE on the Cup tab's Event Info
// (Kerry 10/8), the same body /member/lonestarcup/info shows
check("the board offers How skins work -> Event Info, Skins, in place",
      /href="\?info=skins" data-lscinfo="skins">How skins work/.test(src));
console.log(fails ? `\nFAILED (${fails})` : "\nALL PASS");
process.exit(fails ? 1 : 0);
