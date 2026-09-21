// Guard for the ONE mobile breakpoint.
//
// The trap this exists for: "is this a phone?" was answered in ~45
// places — CSS media queries, matchMedia() calls and innerWidth checks
// across twenty files — and they drifted (leads.html decided at 720px
// while its CSS decided at 768px). Kerry 2026-09-15: "Don't go to mobile
// view on desktop until the window gets much narrower." The number is
// 560px everywhere; a desktop window keeps the desktop layout above it.
// Cosmetic compaction rules at other widths (640px scorecard density,
// 720px pairing grids, 900px split panes) are NOT layout-mode switches
// and are left alone — this guard only hunts the 7xx-px family that
// used to mean "mobile".
const fs = require('fs');
const path = require('path');
const walk = (dir, exts) => fs.readdirSync(path.join(__dirname, dir))
  .filter(f => exts.some(e => f.endsWith(e)) && f !== 'version.js')
  .map(f => path.join(dir, f));
const files = [...walk('templates', ['.html']), ...walk('static/css', ['.css']),
               ...walk('static/js', ['.js'])];

let fails = 0;
const ck = (l, c, d = '') => { if (c) console.log('  PASS  ' + l);
  else { console.log('  FAIL  ' + l + '  ' + d); fails++; } };

const stray = [];
let nMax = 0, nMin = 0, nJs = 0;
for (const f of files) {
  const s = fs.readFileSync(path.join(__dirname, f), 'utf8');
  // The old family: 768/769 in any media query, matchMedia or innerWidth
  // test, plus the 720 leads.html used on its own.
  for (const m of s.matchAll(/(?:max|min)-width:\s*7[0-9]{2}px\)|innerWidth\s*<=?\s*7[0-9]{2}\b/g)) {
    // 700/720/760 grid collapses are cosmetic and allowed; only the
    // mobile-mode numbers are stray.
    if (/76[89]|720px\)"\)/.test(m[0]) || /innerWidth/.test(m[0])) stray.push(f + ': ' + m[0]);
  }
  nMax += (s.match(/\(max-width: 560px\)/g) || []).length;
  nMin += (s.match(/\(min-width: 561px\)/g) || []).length;
  nJs  += (s.match(/innerWidth <= 560\b/g) || []).length;
}
console.log('== one breakpoint ==');
ck('no 768/769 media query, matchMedia or innerWidth test survives', stray.length === 0,
   '\n    ' + stray.join('\n    '));
ck('the 560px max-width query is the one in use (' + nMax + ')', nMax >= 30);
ck('every desktop-only block pairs at 561px (' + nMin + ')', nMin >= 3);
ck('innerWidth checks use the same number (' + nJs + ')', nJs >= 4);

console.log('== nav wraps instead of overflowing on mid-width desktops ==');
const css = fs.readFileSync(path.join(__dirname, 'static/css/shell.css'), 'utf8');
const wrap = css.match(/@media \(min-width: 561px\) and \(max-width: 1479px\) \{[\s\S]*?\n\}/);
ck('two-row rule spans 561px to 1479px', !!wrap);
ck('header wraps in that band', !!wrap && /header\.shell-nav \{[^}]*flex-wrap: wrap/.test(wrap[0]));
ck('links take their own full row', !!wrap && /\.shell-nav-links[^{]*\{[^}]*order: 3;[^}]*flex: 1 1 100%/.test(wrap[0]));
ck('member tabs wrap the same way', !!wrap && /\.shell-member \.shell-member-tabs/.test(wrap[0]));
ck('drawer + mobile bar start at 560px', /@media \(max-width: 560px\) \{\s*header\.shell-nav/.test(css));
ck('shell.js moves ops to the sheet at the same number',
   /matchMedia\("\(max-width: 560px\)"\)/.test(fs.readFileSync(path.join(__dirname, 'static/js/shell.js'), 'utf8')));

console.log(fails ? `\n${fails} FAILED` : '\nALL PASSED');
process.exit(fails ? 1 : 0);
