/**
 * ↓ ↑ Enter in every typeahead (Kerry 2026-09-23). Run: node test_typeahead_keys.js
 * The behaviour was verified in Chromium on Spotlight and Add Player; this
 * guards the wiring and the contract.
 */
const fs = require("fs");
let failures = 0;
function check(label, cond) { console.log((cond ? "  PASS  " : "  FAIL  ") + label); if (!cond) failures++; }
const js = fs.readFileSync("static/js/typeahead-keys.js", "utf8");
const shell = fs.readFileSync("templates/_shell_nav.html", "utf8");
check("the shell loads it on every page, after loading.js", shell.indexOf("loading.js") < shell.indexOf("typeahead-keys.js"));
check("one CAPTURE-phase keydown listener (runs before any page's own Enter / arrow code)", /addEventListener\("keydown", function \(e\) \{[\s\S]*\}, true\);/.test(js));
check("↓ / ↑ move a visible highlight class with an orange bar", /tgf-kb-active/.test(js) && /inset 3px 0 0 var\(--primary,#E87C3E\)/.test(js) && /ArrowDown/.test(js) && /ArrowUp/.test(js));
check("Enter with nothing highlighted leaves the page's own Enter alone", /if \(cur < 0\) return;/.test(js));
check("Enter with a row highlighted picks it like a tap and stops the page handler", /pick\(items\[cur\], list\)/.test(js) && /e\.preventDefault\(\); e\.stopPropagation\(\);\s*pick/.test(js) && /"mousedown"/.test(js) && /"click"/.test(js));
check("textareas and native <datalist> inputs are left to the browser", /TEXTAREA/.test(js) && /input\.list/.test(js));
check("aria-controls / data-suggest can name the list explicitly", /aria-controls/.test(js) && /data-suggest/.test(js));
console.log("\n" + (failures ? failures + " FAILURE(S)" : "ALL PASS"));
process.exit(failures ? 1 : 0);
