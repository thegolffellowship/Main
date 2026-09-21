// Guard for the dark nav's ORDER, LABELS and ROLE GATING.
//
// The trap this exists for: auth.js reveals admin-only links by walking
// ".tab-nav a, .shell-nav-links a, .shell-drawer-nav a". Anything moved
// into .shell-nav-right falls outside that walk and must be gated by
// shell.js instead — by CLASS, not by naming one link. Two Man Tour moved
// into that group on 2026-09-14 and would have been invisible to admins.
const fs = require('fs');
const path = require('path');
const read = f => fs.readFileSync(path.join(__dirname, f), 'utf8');
const tpl = read('templates/_shell_nav.html');
const shellJs = read('static/js/shell.js');
const authJs = read('static/js/auth.js');
const css = read('static/css/shell.css');

let fails = 0;
const ck = (l, c, d = '') => { if (c) console.log('  PASS  ' + l);
  else { console.log('  FAIL  ' + l + '  ' + d); fails++; } };

// The manager/admin half of the template: from the desktop nav row to
// the end. Slicing on '{% else %}' is not safe — the file has several.
const mgr = tpl.slice(tpl.indexOf('<nav class="shell-nav-links"'));
const links = re => [...mgr.matchAll(re)].map(m => m[1].trim());

console.log('== labels (Kerry 2026-09-14) ==');
ck('Queue, not CA Queue', /href="\/admin\/ca-queue"[^>]*>Queue</.test(mgr)
   && !/>CA Queue</.test(mgr));
ck('Members, not Member View', /href="\/member"[^>]*>Members</.test(mgr)
   && !/>Member View</.test(mgr));
ck('Leaderboard, not Season Contests',
   /href="\/contests"[^>]*>Leaderboard</.test(mgr) && !/>Season Contests</.test(mgr));

console.log('== order ==');
const order = links(/<a [^>]*href="(?:\/tgf|\/admin\/ca-queue|\/member|\/accounting|\/twomantour)"[^>]*>(?:<span[^>]*>)?([A-Za-z ]+)/g);
const want = ['Payouts', 'Queue', 'Members', 'Admin', 'Two Man Tour'];
ck('desktop row: ' + want.join(' | '),
   JSON.stringify(order.slice(0, 5)) === JSON.stringify(want), order.slice(0, 5).join(' | '));
ck('drawer repeats the same order',
   JSON.stringify(order.slice(5, 10)) === JSON.stringify(want), order.slice(5, 10).join(' | '));

console.log('== Members reads as a button ==');
ck('Members carries a pill class', /href="\/member"[^>]*class="[^"]*shell-members-pill/.test(mgr));
ck('the pill has its own colour, not the admin orange or the TMT gold',
   /\.shell-members-pill\s*\{[^}]*background:\s*#E2E2E2/i.test(css));
ck('and it is a real pill (fully rounded)',
   /\.shell-members-pill\s*\{[^}]*border-radius:\s*9999px/i.test(css));

console.log('== role gating survives the move ==');
ck('Two Man Tour now sits in .shell-nav-right',
   /shell-nav-right[\s\S]*?href="\/twomantour"/.test(mgr));
ck('auth.js does NOT walk .shell-nav-right (so shell.js must)',
   !/shell-nav-right/.test(authJs));
ck('shell.js gates that group by the admin-nav CLASS, not by one link name',
   /\.shell-nav-right \.admin-nav/.test(shellJs), 'a named-link selector would strand the next pill moved here');
ck('Two Man Tour is still admin-only',
   /href="\/twomantour"[^>]*class="[^"]*admin-nav/.test(mgr));
ck('Members is still admin-only',
   /href="\/member"[^>]*class="[^"]*admin-nav/.test(mgr));
ck('the right-hand pill is styled where it now lives',
   /\.shell-nav-right a\.shell-tmt-pill/.test(css));

console.log(fails ? `\n${fails} FAILURE(S)` : '\nALL PASS');
process.exit(fails ? 1 : 0);
