// Skins pane (Side Games, #1398; mockup docs/claude/lsc-mockups/Skins.dc.html).
// Runs the pane's own functions, cut from templates/contests.html, on a
// member board (no money) and a staff board, and checks what each shows.
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
const escapeHtml = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
eval(cut("lscHolesTxt") + "\n" + cut("lscSkinsGroupRows") + "\n" + cut("lscSkinsPane")
     + "\nglobalThis.pane = lscSkinsPane; globalThis.holesTxt = lscHolesTxt;");
let fails = 0;
const check = (l, c, d) => { console.log((c ? "  PASS  " : "  FAIL  ") + l + (c ? "" : "  " + (d || ""))); if (!c) fails++; };

const totals = [{ key: "M1:austin", label: "Youngs & Cloer", team: "austin", skins: 2 },
                { key: "M2:sa", label: "Youngs & Young", team: "sa", skins: 1 }];
const holes = [{ hole: 1, status: "tied" }, { hole: 2, status: "won", winner: "M1:austin", value: 1 },
               { hole: 3, status: "tied" }, { hole: 4, status: "won", winner: "M2:sa", value: 1 },
               { hole: 5, status: "won", winner: "M1:austin", value: 1 },
               { hole: 6, status: "pending" }, { hole: 7, status: "pending" }, { hole: 8, status: "pending" }];
const fsMember = { format: "chapman", label: "FOURSOMES",
    matches: [{ state: "live", tee_time: "1:30 PM" }, { state: "live" }, { state: "final" }],
    skins: { kind: "team", basis: "net", groups: [{ flight: null, totals, holes }] } };
const h = pane(fsMember);
check("title + basis line", h.includes("Foursomes team skins") && h.includes("net · one flight · live"), h);
check("a row per won hole with the team and count",
      h.includes("Hole 2</span><span class=\"sk au\">Youngs &amp; Cloer <b>1</b>")
      && h.includes("Hole 4</span><span class=\"sk sa\">Youngs &amp; Young <b>1</b>"), h);
check("tied holes on one line", h.includes("Hole 1 · 3</span><span class=\"lsc-sk-mute\">Tied · no skin"), h);
check("open holes on one line with groups on the course", h.includes("Holes 6–8") && h.includes("2 groups still on the course"), h);
check("member view shows no dollars", !h.includes("$"), h);
check("Chapman note", h.includes("Chapman 60/40 allowance"), h);

const staff = JSON.parse(JSON.stringify(fsMember));
Object.assign(staff.skins, { pot_cents: 57500, buyers_in_round: 23, flags: ["x flag"] });
staff.skins.groups[0].pot_cents = 57500;
staff.skins.groups[0].payouts = [{ key: "M1:austin", cents: 38333 }, { key: "M2:sa", cents: 19167 }];
const hs = pane(staff);
check("staff see the pot and each winner's amount", hs.includes("pot $575.00") && hs.includes("$383.33") && hs.includes("$191.67"), hs);
check("staff see flags", hs.includes("x flag"));

const sun = { format: "singles", matches: [{ state: "upcoming", tee_time: "8:30 AM" }],
    skins: { kind: "individual", basis: "gross", groups: [
        { flight: 1, members: [{ name: "Pat Youngs" }, { name: "Mesa" }, { name: "Walter Hogue" }], holes: [], totals: [] },
        { flight: 2, members: [{ name: "Callaway" }, { name: "Rideout" }], holes: [], totals: [] }] } };
const hn = pane(sun);
check("Sunday title + basis", hn.includes("Singles skins") && hn.includes("gross · two flights · 8:30 AM"), hn);
check("flight 1 count and range", hn.includes("Flight 1 · under 12.0") && hn.includes("3 players · Pat Youngs to Walter Hogue"), hn);
check("flight 2 count and range", hn.includes("Flight 2 · 12.0 and up") && hn.includes("2 players · Callaway to Rideout"), hn);
check("holes text", holesTxt([12, 13, 14]) === "Holes 12–14" && holesTxt([1, 3]) === "Hole 1 · 3" && holesTxt([9]) === "Hole 9");
check("no skins data -> nothing", pane({ skins: null }) === "");

check("the board offers How skins work -> Event Info #skins",
      // the staff preview board carries ?preview=1 into the link (Tracker Build)
      /href="\/member\/lonestarcup\/info[^"]*#skins">How skins work/.test(src.replace(/' \+ \(new URLSearchParams[^)]*\)\.get\("preview"\) === "1" \? "\?preview=1" : ""\) \+ '/g, "")));
console.log(fails ? `\nFAILED (${fails})` : "\nALL PASS");
process.exit(fails ? 1 : 0);
