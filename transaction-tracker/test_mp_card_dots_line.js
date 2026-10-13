// OPEN CARD on the hole-dots line, every match card (Kerry 2026-10-13:
// "Can you move the OPEN CARD to same line as the dots for the hole results
// so we can reduce the vertical height? On mobile you can reduce OPEN CARD
// to OPEN. Do this for ALL Match Play events and matches, not just Lone Star
// cup"). City Match Play pools, knockout and the Cup all build their card in
// mpMatchCard, so the guard sits there.
const fs = require("fs"), path = require("path");
const src = fs.readFileSync(path.join(__dirname, "templates/contests.html"), "utf8");
let fails = 0;
const check = (name, ok, info) => { console.log(`  ${ok ? "PASS" : "FAIL"}  ${name}`); if (!ok) { fails++; if (info !== undefined) console.log("      ", info); } };
const grab = (name) => { const i = src.indexOf(`function ${name}(`); let d = 0, j = src.indexOf("{", i);
    for (let k = j; k < src.length; k++) { if (src[k] === "{") d++; else if (src[k] === "}") { d--; if (!d) return src.slice(i, k + 1); } } };
eval(grab("mpToggleHintHtml"));
const shut = mpToggleHintHtml(false), open = mpToggleHintHtml(true);
check("closed label: 'open' + ' card' only on desktop",
      /open<span class="mp-hint-long"> card<\/span>/.test(shut), shut);
check("open label: 'collapse card' on desktop, 'close' on the phone",
      /mp-hint-long">collapse card</.test(open) && /mp-hint-short">close</.test(open), open);
const card = grab("mpMatchCard");
check("the hint is built inside the dots line, beside the dots",
      /const dotsLine = `<div class="mp-dots-line">[\s\S]*?\$\{dots\}[\s\S]*?mp-toggle-hint">\$\{mpToggleHintHtml\(false\)\}/.test(card));
check("the head renders the dots line, no separate toggle row after the dots",
      /\$\{meta\}\$\{strip\}\$\{dotsLine\}/.test(card) && !/\$\{dots\}\$\{toggle\}/.test(card));
check("no hard-coded 'open card' label left anywhere",
      !/&rsaquo; open card/.test(src) && !/'&#9652; collapse card'/.test(src));
check("the toggle swaps the label through the one helper", /hint\.innerHTML = mpToggleHintHtml\(!open\)/.test(grab("mpCardToggle")));
const css = src.match(/@media \(max-width: 560px\) \{\s*\/\* phone: "OPEN"[\s\S]*?\n        \}/);
check("phone rule at the ONE breakpoint hides the long words, shows the short",
      !!css && /\.mp-hint-long \{ display: none; \}/.test(css[0]) && /\.mp-hint-short \{ display: inline; \}/.test(css[0]));
check("phone: dots and OPEN share row 1, a start-hole note drops to row 2",
      !!css && /grid-template-columns: 1fr auto/.test(css[0]) && /mp-illus-note \{ grid-row: 2/.test(css[0]));
check("a live re-render of an open card keeps the CLOSE label",
      /hint\.innerHTML = mpToggleHintHtml\(true\)/.test(src));
console.log(fails ? `\nFAILED (${fails})` : "\nALL PASS");
process.exit(fails ? 1 : 0);
