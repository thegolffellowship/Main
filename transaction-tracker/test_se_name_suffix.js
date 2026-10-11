// A name suffix is not a surname on the SCORING page (Kerry 2026-10-10:
// "James Wilson Jr.s last name is Wilson not jr. that's a suffix"). The
// match strip's single-player initials and the match-won banner's
// "First LAST" read the surname past a trailing Jr / Sr / II / III / IV / V.
const fs = require("fs"), path = require("path");
const src = fs.readFileSync(path.join(__dirname, "templates/score_entry.html"), "utf8");
let fails = 0;
const check = (n, ok, info) => { console.log(`  ${ok ? "PASS" : "FAIL"}  ${n}`); if (!ok) { fails++; if (info !== undefined) console.log("      ", info); } };
const line = (re) => { const m = src.match(re); if (!m) throw new Error("missing " + re); return m[0].replace(/^const /, "var "); };
eval(line(/const SE_SUFFIX = [^\n]*/));
eval(line(/const surnameAt = [^\n]*/));
const flSrc = src.slice(src.indexOf("const firstLAST = (n) => {"));
eval(flSrc.slice(0, flSrc.indexOf("\n        };") + 11).replace(/^const /, "var "));
const monoSrc = line(/const mono = \(side\) =>[^\n]*\n[^\n]*/);
eval(monoSrc);
check("banner: James WILSON Jr", firstLAST("James Wilson Jr") === "James WILSON Jr", firstLAST("James Wilson Jr"));
check("banner: plain name unchanged", firstLAST("Rob Callaway") === "Rob CALLAWAY" && firstLAST("Mary Ann Wade") === "Mary Ann WADE");
check("banner: Jr. and III too", firstLAST("Al Jones Jr.") === "Al JONES Jr." && firstLAST("Bob Smith III") === "Bob SMITH III");
check("strip initials: JW, not JJ", mono(["James Wilson Jr"]) === "JW" && mono(["Rob Callaway"]) === "RC", mono(["James Wilson Jr"]));
console.log(fails ? `\nFAILED (${fails})` : "\nALL PASS");
process.exit(fails ? 1 : 0);
