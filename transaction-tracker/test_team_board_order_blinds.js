// TEAM tab, collapsed rows (Kerry 10/20, s9.28 TPC Canyons before the round):
//   "These should show in Tee time order and be left aligned. Should also
//    show their blinds in a different font color or somehow denote it, so
//    they understand easily that player is a blind."
//   1. unscored / tied teams list in start order (server's start_order),
//      never alphabetically; scored teams still rank on to-par
//   2. the names cell is left-aligned (the row rule centres every cell)
//   3. a blind — drawn with no card yet (blinds_pending) or playing his
//      card (Bl[...]) — is a 4th name, tagged BLIND, in its own colour
// Runs the PAGE's own renderer region headless.
// Run: node test_team_board_order_blinds.js
const fs = require('fs');
const path = require('path');
const src = fs.readFileSync(path.join(__dirname, 'templates/contests.html'), 'utf8');
const lines = src.split('\n');
const a = lines.findIndex(l => l.startsWith('    const EVLB_FLIGHT_COLORS'));
const b = lines.findIndex(l => l.startsWith('    function evlbEventHtml(d) {'));
if (a < 0 || b < 0) throw new Error('renderer region not found');
eval('const escapeHtml = s => String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;");\n'
  + lines.slice(a, b).join('\n')
  + '\nObject.assign(globalThis, {evlbTeamRows, evlbTeamPanel, evlbTeamsLiveOrder, evlbTeamNames,'
  + ' evlbTeamNamesHtml, evlbTeamSection});');

let fails = 0;
const ck = (l, c, d) => { console.log(`  ${c ? 'PASS' : 'FAIL'}  ${l}${c ? '' : '  ' + (d ?? '')}`); if (!c) fails++; };

const PAR = {1: 4, 2: 3, 3: 5};
const card = (rel) => [1, 2, 3].map((h, i) => rel[i] == null ? [h, null, 0] : [h, PAR[h] + rel[i], 0]);
const P = (rid, nm, extra = {}) => Object.assign({ scoring_round_id: rid, player_name: nm }, extra);
const mkd = (cards, teams) => ({
  hole_cols: [1, 2, 3], hole_par: {"1": 4, "2": 3, "3": 5}, team_balls: 1, team_allowance: 0.75,
  team_unit: 'team', cards, teams,
  overall_board: Object.keys(cards).map(rid => ({ scoring_round_id: Number(rid),
    player_name: 'P' + rid, net: 0, par: 12, won_by_cat: {}, won_total: 0 })),
});
// pre-round: no scores; names chosen so the alphabet disagrees with the tee sheet
const pre = () => [
  { team_num: 1, start_order: 2, start_line: '4:50 PM | Hole 1', players: [P(1, 'Adam Baker'), P(2, 'Michael Mesa')] },
  { team_num: 2, start_order: 0, start_line: '4:30 PM | Hole 1', players: [P(3, 'Zed Young'), P(4, 'Yuri Xu')] },
  { team_num: 3, start_order: 1, start_line: '4:40 PM | Hole 1',
    players: [P(5, 'Kerry Niester'), P(6, 'Nic Skinner'), P(7, 'Dan Stich')],
    blinds_pending: [{ customer_id: 999, name: 'Reggie Johnson', reason: 'open_seat' }] },
];
const emptyCards = {1: card([null, null, null]), 2: card([null, null, null]), 3: card([null, null, null]),
  4: card([null, null, null]), 5: card([null, null, null]), 6: card([null, null, null]), 7: card([null, null, null])};

console.log('== 1. order ==');
{
  const d = mkd(emptyCards, pre());
  const rows = evlbTeamRows(d);
  ck('before the round: tee-time order (4:30, 4:40, 4:50), not alphabetical',
     rows.map(x => x.t.team_num).join(',') === '2,3,1', rows.map(x => x.t.team_num).join(','));
  ck('no position before any score', rows.every(x => !x.pos));
  const html = evlbTeamPanel(d, { key: 'team', rows: [] }, '');
  const firsts = ['Zed Young', 'Kerry Niester', 'Adam Baker'].map(n => html.indexOf(n));
  ck('the rendered panel lists the rows in tee-time order', firsts.every((v, i) => v > 0 && (i === 0 || v > firsts[i - 1])), firsts.join(','));

  // scored: team 1 leads; teams 2 and 3 tie -> their tee-time order breaks the tie
  const c = Object.assign({}, emptyCards, {
    1: card([-1, -1, -1]), 2: card([0, 0, 0]),
    3: card([1, 1, 1]), 4: card([1, 1, 1]),
    5: card([1, 1, 1]), 6: card([1, 1, 1]), 7: card([1, 1, 1]) });
  const ds = mkd(c, pre());
  const rs = evlbTeamRows(ds);
  ck('once scored, the to-par ranking stands (team 1 first)', rs[0].t.team_num === 1, rs.map(x => x.t.team_num).join(','));
  ck('tied teams fall back to tee-time order (2 before 3)', rs.map(x => x.t.team_num).join(',') === '1,2,3', rs.map(x => x.t.team_num).join(','));
  const live = evlbTeamsLiveOrder(ds, pre().reverse());
  ck('the live order breaks ties on start order too, not the given order', live.map(t => t.team_num).join(',') === '1,2,3', live.map(t => t.team_num).join(','));
}

console.log('== 2. left alignment ==');
{
  const rule = /table\.evlb-tsum tr\.evlb-tsum-row td\.nm \{[^}]*text-align:\s*left/.test(src);
  ck('the collapsed row\'s name cell is left-aligned at the row rule\'s weight', rule);
  ck('no phone rule re-centres it', !/tr\.evlb-tsum-row td\.nm \{[^}]*text-align:\s*center/.test(src));
  const d = mkd(emptyCards, pre());
  const html = evlbTeamPanel(d, { key: 'team', rows: [] }, '');
  ck('the chevron sits first in the names cell', /<td class="nm"><span class="tchev tgf-exp">/.test(html));
}

console.log('== 3. blinds ==');
{
  const d = mkd(emptyCards, pre());
  const t3 = d.teams[2];
  const h = evlbTeamNamesHtml(d, t3);
  ck('the pending blind is the 4th name', /Dan Stich.*Reggie Johnson/.test(h), h);
  ck('…tagged BLIND in its own colour class', /<span class="evlb-tmem blind"[^>]*><span class="evlb-blind">BLIND<\/span>Reggie Johnson/.test(h), h);
  ck('the blind style is a different colour + italic', /\.evlb-tmem\.blind \{[^}]*font-style:\s*italic;[^}]*color:/.test(src));
  ck('members are not marked', (h.match(/evlb-tmem blind/g) || []).length === 1);
  ck('names (sort + band label) carry the blind', evlbTeamNames(t3).join(', ') === 'Kerry Niester, Nic Skinner, Dan Stich, Reggie Johnson (blind)', evlbTeamNames(t3).join(', '));
  // in play: the blind's card is on the team as Bl[...]; a stale pending copy is not doubled
  const t = { team_num: 4, players: [P(5, 'Kerry Niester'), P(6, 'Nic Skinner'), P(7, 'Dan Stich'),
    P(8, 'Bl[Reggie Johnson]', { blind: true })],
    blinds_pending: [{ customer_id: 999, name: 'Reggie Johnson' }] };
  const h2 = evlbTeamNamesHtml(d, t);
  ck('a carded blind shows bare-named and tagged BLIND', /<span class="evlb-blind">BLIND<\/span>Reggie Johnson/.test(h2) && !/Bl\[/.test(h2), h2);
  ck('…once, not twice', (h2.match(/Reggie Johnson/g) || []).length === 1, h2);
  ck('the expanded band label names the blind', evlbTeamSection({}, t).label.includes('Reggie Johnson (blind)'));
  const noBl = { team_num: 5, players: [P(1, 'A B'), P(2, 'C D')] };
  ck('a team with no blind is unchanged', !/BLIND/.test(evlbTeamNamesHtml(d, noBl)));
}

console.log(fails ? `\n${fails} FAILED` : '\nALL PASS');
process.exit(fails ? 1 : 0);
