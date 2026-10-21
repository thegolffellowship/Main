// TEAM tab (Kerry 10/19, leaderboard review 11.6 / 12.4 / 12.6 / 13):
//   B9  Team Net 1-, 2- and 3-ball: each hole sums the N lowest nets
//   B5  every ball that counted is green; a tie at the cutoff greens all tied
//   B8  collapsed by default — one row a team, tap to open, Expand all /
//       Collapse all. Since Batch 1 (design-claude #2147 §4-§5, Kerry-approved
//       10/20): # | TEAM | ± | THRU | WON/PROJ. (Net and ± merged, PGA
//       style); a finished team shows only its number in THRU; the opened
//       team is its card (HOLE / PAR / players / TEAM NET, N ± USED).
// Runs the PAGE's own renderer region headless.
// Run: node test_team_board_collapsed.js
const fs = require('fs');
const path = require('path');
const src = fs.readFileSync(path.join(__dirname, 'templates/contests.html'), 'utf8');
const lines = src.split('\n');
const a = lines.findIndex(l => l.startsWith('    const EVLB_FLIGHT_COLORS'));
const b = lines.findIndex(l => l.startsWith('    function evlbEventHtml(d) {'));
if (a < 0 || b < 0) throw new Error('renderer region not found');
eval('const escapeHtml = s => String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;");\n'
  + lines.slice(a, b).join('\n')
  + '\nObject.assign(globalThis, {evlbTeamMins, evlbTeamCounted, evlbTeamSummary, evlbTeamRows,'
  + ' evlbTeamPanel, evlbTeamDialLabel, evlbTeamSetOpen, evlbTeamToggleAll, evlbTeamAllOpen,'
  + ' evlbTeamSyncAll, evlbTeamThru, evlbTeamBalls, evlbTeamGrid});');
const txt = h => String(h).replace(/<[^>]+>/g, '');

let fails = 0;
const ck = (l, c, d) => { console.log(`  ${c ? 'PASS' : 'FAIL'}  ${l}${c ? '' : '  ' + (d ?? '')}`); if (!c) fails++; };

// 3 holes, par 4/3/5. Team A: rids 1-4; team B: rids 5-8. No pops.
const PAR = {1: 4, 2: 3, 3: 5};
const card = (rel) => [1, 2, 3].map((h, i) => rel[i] == null ? [h, null, 0] : [h, PAR[h] + rel[i], 0]);
const mkd = (balls, cards, teams, extra = {}) => Object.assign({
  hole_cols: [1, 2, 3], hole_par: {"1": 4, "2": 3, "3": 5}, team_balls: balls,
  team_allowance: balls === 2 ? 0.85 : (balls === 1 ? 0.75 : 1.0), team_unit: 'team',
  cards, teams, overall_board: Object.keys(cards).map(rid => ({
    scoring_round_id: Number(rid), player_name: 'P' + rid, net: 0, par: 12,
    won_by_cat: {}, won_total: 0})),
}, extra);
const P = (rid, extra = {}) => Object.assign({ scoring_round_id: rid, player_name: 'Player ' + rid }, extra);
const baseCards = {
  1: card([0, 0, 0]),       // par, par, par
  2: card([-1, 0, 1]),      // birdie on 1
  3: card([-1, 1, 1]),      // birdie on 1 too (tie with 2)
  4: card([2, 2, 2]),
  5: card([1, 1, 1]), 6: card([1, 1, 1]), 7: card([1, 1, 1]), 8: card([1, 1, 1]),
};
const teams = () => [
  { position: '', players: [P(1), P(2), P(3), P(4)], purse: 120 },
  { position: '', players: [P(5), P(6), P(7), P(8)], purse: null },
];

console.log('== B9: N-ball sums ==');
{
  const d1 = mkd(1, baseCards, teams());
  const m1 = evlbTeamMins(d1, d1.teams[0]);
  ck('Best 1: hole 1 is the single low net (3)', m1[1] === 3, m1[1]);
  const d2 = mkd(2, baseCards, teams());
  const m2 = evlbTeamMins(d2, d2.teams[0]);
  ck('Best 2: hole 1 sums the two low nets (3 + 3)', m2[1] === 6, m2[1]);
  ck('Best 2: hole 2 sums par + par (3 + 3)', m2[2] === 6, m2[2]);
  ck('Best 2: hole 3 sums 5 + 6', m2[3] === 11, m2[3]);
  const d3 = mkd(3, baseCards, teams());
  const m3 = evlbTeamMins(d3, d3.teams[0]);
  ck('Best 3: hole 1 sums 3 + 3 + 4', m3[1] === 10, m3[1]);
  const s2 = evlbTeamSummary(d2, d2.teams[0], m2);
  ck('Best 2 NET = 6 + 6 + 11 = 23', s2.net === 23, s2.net);
  ck('Best 2 ± is against 2 x par (24): -1', s2.toPar === -1, s2.toPar);
  const s3 = evlbTeamSummary(d3, d3.teams[0], m3);
  ck('Best 3 ± is against 3 x par', s3.toPar === (10 + (3+3+4) + (5+6+6)) - 36, s3.toPar);
  const dn = mkd(undefined, baseCards, teams());
  ck('a payload with no team_balls is Best 1', evlbTeamBalls(dn) === 1 && evlbTeamMins(dn, dn.teams[0])[1] === 3);
}

console.log('== B5: counted-ball highlight, ties included ==');
{
  const d1 = mkd(1, baseCards, teams());
  const m1 = evlbTeamMins(d1, d1.teams[0]);
  ck('Best 1, hole 1: both tied birdies are counted balls',
     evlbTeamCounted(m1, 2, 1) && evlbTeamCounted(m1, 3, 1) && !evlbTeamCounted(m1, 1, 1));
  ck('Best 1, hole 2: three pars tie for low, all three green, the double is not',
     [1, 2].every(r => evlbTeamCounted(m1, r, 2)) && !evlbTeamCounted(m1, 3, 2) && !evlbTeamCounted(m1, 4, 2));
  const d2 = mkd(2, baseCards, teams());
  const m2 = evlbTeamMins(d2, d2.teams[0]);
  ck('Best 2, hole 1: exactly the two birdies', evlbTeamCounted(m2, 2, 1) && evlbTeamCounted(m2, 3, 1)
     && !evlbTeamCounted(m2, 1, 1) && !evlbTeamCounted(m2, 4, 1));
  ck('Best 2, hole 3: the par (5) and the two bogeys tied at the cutoff (6) are all green',
     [1, 2, 3].every(r => evlbTeamCounted(m2, r, 3)) && !evlbTeamCounted(m2, 4, 3));
  // render the real team board and look at the cells
  const one = { teamBands: true, teams: [d2.teams[0]], game: 'team', gameCol: false, grossCol: false,
                sort: 'keep', holesOnLanding: true, noCard: true,
                sections: [{ label: 'A', rows: d2.teams[0].players.map(p =>
                  d2.overall_board.find(r => r.scoring_round_id === p.scoring_round_id)) }] };
  const html = evlbStdBoard(d2, one);
  ck('the board marks 2 + 2 + 3 = 7 counted cells on Best 2', (html.match(/class="h count"/g) || []).length === 7,
     (html.match(/class="h count"/g) || []).length);
  ck('the TEAM NET row carries the summed holes', /<tr class="teamrow">[\s\S]*?<td class="h">6<\/td><td class="h">6<\/td><td class="h">11<\/td>/.test(html));
  ck('the TEAM NET row ± is the summary ± (-1)', /<tr class="teamrow">[\s\S]*?<td class="tp br">-1<\/td>/.test(html));
  ck('no band chevron and no band tap target', !/data-team=/.test(html) && !/evlb-band[^>]*>\s*<td[^>]*><span class="tchev/.test(html));
}

console.log('== a hole counts once the whole team is in; blinds never wait ==');
{
  const c = Object.assign({}, baseCards, { 4: card([2, 2, null]) });
  const d = mkd(1, c, teams());
  const m = evlbTeamMins(d, d.teams[0]);
  ck('hole 3 waits on player 4', m[3] == null && !evlbTeamCounted(m, 1, 3));
  const s = evlbTeamSummary(d, d.teams[0], m);
  ck('THRU is 2', s.thru === 2 && !s.complete, JSON.stringify(s));
  ck('NET is holes 1-2 only (3 + 3)', s.net === 6, s.net);
  const tb = teams(); tb[0].players[3] = P(4, { blind: true, player_name: 'Bl[Player 4]' });
  const db = mkd(1, c, tb);
  ck('a blind with hole 3 still to come does not hold the hole', evlbTeamMins(db, db.teams[0])[3] === 5);
  const tn = teams(); tn[0].players[3] = P(4, { nh: true });
  const dnh = mkd(1, c, tn);
  ck('an N/H seat is not a ball and never holds a hole', evlbTeamMins(dnh, dnh.teams[0])[3] === 5);
}

console.log('== B8: collapsed row values ==');
{
  const d = mkd(2, baseCards, teams());
  const rows = evlbTeamRows(d);
  ck('ranked on ±: team A (-1) before team B (+6)', rows[0].i === 0 && rows[1].i === 1);
  ck('positions 1 and 2', rows[0].pos === '1' && rows[1].pos === '2', rows.map(r => r.pos).join());
  d.board_state = 'final';
  const html = evlbTeamPanel(d, { game: 'team', gameCol: false, grossCol: false, sort: 'keep', holesOnLanding: true, noCard: true });
  const r0 = (html.match(/<tr class="evlb-tsum-row[\s\S]*?<\/tr>/) || [''])[0];
  const cells = (r0.match(/<td[^>]*>[\s\S]*?<\/td>/g) || []);
  ck('five cells: # | TEAM | ± | THRU | WON', cells.length === 5, cells.length);
  ck('# is 1', />1<\/td>/.test(cells[0]), cells[0]);
  ck('TEAM names every player', ['Player 1', 'Player 2', 'Player 3', 'Player 4'].every(n => txt(cells[1]).includes(n)), cells[1]);
  ck('± is the big number, a true minus: −1', /class="tp red">−1</.test(cells[2]), cells[2]);
  ck('finished: THRU shows ONLY the team net, no F (Kerry 10/20)', txt(cells[3]) === '23' && !/F/.test(txt(cells[3])), cells[3]);
  ck('WON is the team purse, two decimals, FINAL green', /class="won fin">\$120\.00/.test(cells[4]), cells[4]);
  ck('heading reads the dial', html.includes('Team Net · best 2 of 4 · 85%') && !html.includes('allowance'),
     (html.match(/evlb-tdial-l">[^<]*/) || [])[0]);
  ck('every team row is followed by its hidden card',
     (html.match(/<tr class="evlb-tsum-exp" data-ti="\d+" hidden>/g) || []).length === 2);
  ck('the opened team is its card: HOLE, PAR, players, TEAM NET',
     /evlb-tsum-exp[\s\S]*?<table class="evlb-tgx">[\s\S]*?<tr class="hd">[\s\S]*?<tr class="par">[\s\S]*?<tr class="pl[\s\S]*?<tr class="tn">/.test(html));
  ck('no black band inside the opened team, no pot line repeated', !/evlb-band/.test(html.split('evlb-tsum-exp')[1] || '') && !/evlb-potline/.test(html));
  ck('Expand all control is there', /data-evlb-team-all[^>]*>EXPAND ALL</.test(html));
  const upd = Object.assign({}, d, { board_state: 'upcoming' });
  ck('WON column hides while UPCOMING', /<table class="evlb-tsum no-won"/.test(evlbTeamPanel(upd, { game: 'team' })));
  const lv = Object.assign({}, d, { board_state: 'live' });
  const lh = evlbTeamPanel(lv, { game: 'team' });
  ck('LIVE: the header reads PROJ. and the cells are grey italic', /<th class="won">PROJ\.<\/th>/.test(lh) && /class="won proj"/.test(lh));
  const rv = evlbTeamPanel(Object.assign({}, d, { board_state: 'in_review' }), { game: 'team' });
  ck('IN REVIEW: WON cells are marked (italic amber class)', /class="won rev"/.test(rv));
  // the card's numbers: team A, best 2, holes 1-3: team net 6 / 6 / 11 = 23 vs 24
  const m = evlbTeamMins(d, d.teams[0]);
  const g = evlbTeamGrid(d, d.teams[0], m);
  const tn = (g.match(/<tr class="tn">[\s\S]*?<\/tr>/) || [''])[0];
  const tnc = (tn.match(/<td[^>]*>[\s\S]*?<\/td>/g) || []).map(txt);
  ck('TEAM NET row: per-hole team net, N, ±, USED blank', tnc.join('|') === 'TEAM NET|6|6|11|23|−1|', tnc.join('|'));
  ck('TEAM NET: a hole under the team par is red (6 vs 8)', /<td class="red">6<\/td>/.test(tn), tn);
  const cnt = (g.match(/class="cnt"/g) || []).length;
  ck('every counted ball is green: 2 + 2 + 3 (a tie at the cutoff on 3 counts all tied)', cnt === 7, cnt);
  const p1 = (g.match(/<tr class="pl">[\s\S]*?<\/tr>/) || [''])[0];
  const p1c = (p1.match(/<td[^>]*>[\s\S]*?<\/td>/g) || []).map(txt);
  ck('player row: gross per hole, N, ±, USED', p1c.slice(-3).join('|') === '12|E|2', p1c.join('|'));
  ck('the fill runs edge to edge (#2149): PAR and TEAM NET rows fill every cell', /tr\.par td \{ background: #F3F1EC/.test(src) && /tr\.tn td \{ background: #F3F1EC/.test(src));
  ck('a 2px black rule sits before N', /td\.rule \{ border-left: 2px solid #1B1B1B/.test(src));

  // mid-round: team B has played more holes at the same ±
  const mid = Object.assign({}, baseCards, {
    1: card([0, 0, null]), 2: card([0, 0, null]), 3: card([0, 0, null]), 4: card([0, 0, null]),
    5: card([0, 0, 0]), 6: card([0, 0, 0]), 7: card([0, 0, 0]), 8: card([0, 0, 0]) });
  const dm = mkd(1, mid, teams());
  const rm = evlbTeamRows(dm);
  ck('level on ±: more holes played ranks first (team B thru 3)', rm[0].i === 1 && rm[0].s.thru === 3);
  ck('…and they share the place', rm[0].pos === 'T1' && rm[1].pos === 'T1', rm.map(r => r.pos).join());
  ck('THRU reads the hole count while playing', evlbTeamThru(dm.teams[0], rm[1].s) === '2');

  // upcoming: nothing posted, the start line shows in THRU
  const up = {1: [], 2: [], 3: [], 4: [], 5: [], 6: [], 7: [], 8: []};
  const tu = teams(); tu[0].start_line = '3:40 PM | Hole 1'; tu[0].purse = null;
  const du = mkd(1, up, tu);
  const ru = evlbTeamRows(du);
  ck('UPCOMING: THRU shows the team start, "4:30 PM · 1" form', /class="lf">3:40 PM · 1</.test(evlbTeamThru(du.teams[0], ru[0].s)), evlbTeamThru(du.teams[0], ru[0].s));
  ck('…with a short form for the phone', /class="sf">3:40 · 1</.test(evlbTeamThru(du.teams[0], ru[0].s)));
  ck('UPCOMING: no rank, no net', ru.every(r => r.pos === '' && r.s.net == null));

  // GG era keeps GG's order and positions
  const tg = teams(); tg[0].gg_position = '2'; tg[0].position = '2'; tg[1].gg_position = '1'; tg[1].position = '1';
  const dg = mkd(1, baseCards, [tg[1], tg[0]]);
  const rg = evlbTeamRows(dg);
  ck('GG era: the recorded order and positions are kept', rg[0].pos === '1' && rg[1].pos === '2' && rg[0].t === tg[1]);
}

console.log('== B8: expand / collapse ==');
{
  // a tiny DOM: just what the toggles touch
  const cls = () => { const s = new Set(); return { add: x => s.add(x), remove: x => s.delete(x),
    contains: x => s.has(x), toggle: (x, on) => (on ? s.add(x) : s.delete(x)) }; };
  const el = (c) => { const e = { classList: cls(), attrs: {}, hidden: false, textContent: '',
    setAttribute(k, v) { this.attrs[k] = v; } }; c.split(' ').forEach(x => e.classList.add(x)); return e; };
  const rows = [], exps = [];
  for (let i = 0; i < 3; i++) {
    const r = el('evlb-tsum-row'), x = el('evlb-tsum-exp'); x.hidden = true;
    r.nextElementSibling = x; rows.push(r); exps.push(x);
  }
  const btn = el('evlb-tall');
  const panel = { querySelectorAll: () => rows, querySelector: () => btn };
  evlbTeamSetOpen(rows[1], true);
  ck('tapping one team opens only that team', !exps[1].hidden && exps[0].hidden && exps[2].hidden
     && rows[1].classList.contains('open') && rows[1].attrs['aria-expanded'] === 'true');
  evlbTeamSyncAll(panel);
  ck('with one open the control still says Expand all', btn.textContent === 'EXPAND ALL');
  evlbTeamToggleAll(panel, true);
  ck('Expand all opens every team', exps.every(x => !x.hidden) && evlbTeamAllOpen(panel));
  ck('…and the control flips to Collapse all', btn.textContent === 'COLLAPSE ALL');
  evlbTeamSetOpen(rows[0], false);
  ck('one team closes on its own', exps[0].hidden && !exps[1].hidden && !exps[2].hidden);
  evlbTeamToggleAll(panel, false);
  ck('Collapse all closes every team', exps.every(x => x.hidden) && btn.textContent === 'EXPAND ALL');
}

console.log('== #2147 §5 sample: thru 7, best 2 nets 7·5·8·7·7·8·5 = 47 vs 54 -> −7 ==');
{
  const par = [4, 3, 4, 4, 4, 5, 3, 4, 5];
  const nets = [[3,3,4,4,4,4,3], [4,2,5,5,3,6,4], [5,4,4,3,5,5,4], [5,4,6,5,5,4,2]];
  const cards = {}; nets.forEach((ns, i) => { cards[i + 1] = par.map((p, h) => [h + 1, h < 7 ? ns[h] : null, 0]); });
  const hp = {}; par.forEach((p, i) => { hp[String(i + 1)] = p; });
  const ds = { hole_cols: [1,2,3,4,5,6,7,8,9], hole_par: hp, team_balls: 2, team_unit: 'team', cards,
    teams: [{ players: [1, 2, 3, 4].map(r => ({ scoring_round_id: r, player_name: 'P ' + r })) }] };
  const ms = evlbTeamMins(ds, ds.teams[0]);
  ck('per-hole team nets 7·5·8·7·7·8·5', [1,2,3,4,5,6,7].map(n => ms[n]).join('·') === '7·5·8·7·7·8·5');
  const ss = evlbTeamSummary(ds, ds.teams[0], ms);
  ck('the collapsed row\'s ± is −7, thru 7, net 47', ss.toPar === -7 && ss.thru === 7 && ss.net === 47, JSON.stringify(ss));
}

console.log('== page wiring ==');
ck('the TEAM panel replaces the always-open board',
   /team: \(d\.teams \|\| \[\]\)\.length\s*\? evlbTeamPanel\(d, boards\.team, offNotes\)/.test(src));
ck('the team-band "every player\'s card" handler is gone', !/Loading cards&hellip;/.test(src));
ck('the team board carries noCard (no tap-a-player scorecard on TEAM)',
   /sections: \(d\.teams \|\| \[\]\)\.map\(t => evlbTeamSection\(ovIx, t\)\),\s*sort: "keep",[\s\S]{0,300}noCard: true/.test(src));
ck('a row tap and the Expand all control are wired', /closest\("\[data-evlb-team-all\]"\)/.test(src)
   && /closest\("tr\.evlb-tsum-row"\)/.test(src));
ck('HOW IT WORKS on TEAM reads the dial', /team: `<b>\$\{escapeHtml\(evlbTeamDialLabel\(d\)\)\}<\/b>/.test(src));

console.log('\n' + (fails ? fails + ' FAILURE(S)' : 'ALL PASS'));
process.exit(fails ? 1 : 0);
