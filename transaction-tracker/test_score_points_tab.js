// THE POINTS TAB's table (Kerry #2460-F): the top 10, then any of the
// group's players further down after a gap row, each of the group's rows
// highlighted by customer_id. Run: node test_score_points_tab.js
const fs = require('fs');
const src = fs.readFileSync(require('path').join(__dirname, 'templates/score_points.html'), 'utf8');
const lines = src.split('\n');
const a = lines.findIndex(l => l.includes('var TOP = 10;'));
const b = lines.findIndex(l => l.includes('function chOf(name)'));
if (a < 0 || b < 0) throw new Error('table region not found');
eval(lines.slice(a, b).join('\n') + '\nglobalThis.table = table;');

let fails = 0;
const check = (label, cond) => { console.log(`  ${cond ? 'PASS' : 'FAIL'}  ${label}`); if (!cond) fails++; };
const rows = Array.from({length: 20}, (_, i) => ({rank: String(i + 1), name: `P${i + 1}`, points: 100 - i, customer_id: 1000 + i}));

let h = table(rows, [1002, 1015]);
check('top ten shown', (h.match(/<tr/g) || []).length === 12);   // 10 + gap + P16
check('a group player outside the top ten still shown', h.includes('P16'));
check('a gap row before him', h.includes('class="gap"'));
check('the group rows highlighted', (h.match(/class="me"/g) || []).length === 2);
check('nobody else past 10', !h.includes('P12'));
h = table(rows.slice(0, 5), []);
check('short race: no gap, no highlight', !h.includes('gap') && !h.includes('class="me"'));
check('empty race says so', table([], []).includes('No points yet'));
check('names escaped', table([{rank: '1', name: '<b>x</b>', points: 1, customer_id: 1}], []).includes('&lt;b&gt;'));
// chapter bars on the monthly (Kerry 10/30)
check('a chapter row carries its bar class', table([{rank: '1', name: 'A', points: 1, customer_id: 1, ch: 'aus'}], [1]).includes('class="me c-aus"'));
console.log(fails ? `\n${fails} FAILED` : '\nALL PASS');
process.exit(fails ? 1 : 0);
