// EVENTS BOARD: SUMMARY tab, projected WON, pot headers, money per tab,
// Match Play tab (Kerry 2026-10-19, leaderboard review §12-13, B10-B12).
//
// Runs the PAGE's own renderer (templates/contests.html) headless: the
// money blank, the notices and the whole board region including
// evlbEventHtml, so the tab row, the landing tab and the panels are the
// real ones.
//
// Run: node test_lb_summary.js
const fs = require('fs');
const src = fs.readFileSync(require('path').join(__dirname, 'templates/contests.html'), 'utf8');
const lines = src.split('\n');
const at = (pfx) => {
  const i = lines.findIndex(l => l.startsWith(pfx));
  if (i < 0) throw new Error('not found: ' + pfx);
  return i;
};
const slice = (a, b) => lines.slice(at(a), at(b)).join('\n');
const code = 'const escapeHtml = s => String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;");\n'
  + slice('    function evlbBlankMoney(d) {', '    // TEE COLOUR AS A DOT') + '\n'
  + slice('    const EVLB_FLIGHT_COLORS', '    function evlbAlignCard(') + '\n'
  + 'globalThis.R = { evlbEventHtml, evlbSummaryHtml, evlbSummaryShown, evlbBlankMoneyProj, '
  + 'evlbProjOn, evlbPotBandText, evlbPotLine, evlbGameMoney, evlbMatchPlayHtml, EVLB_GAME_CATS, evlbBlankMoney };';
eval(code);

let fails = 0;
const ck = (label, cond, detail) => {
  console.log(`  ${cond ? 'PASS' : 'FAIL'}  ${label}${cond ? '' : '  ' + (detail || '')}`);
  if (!cond) fails++;
};

const mk = (rid, name, g, n, pts, opts = {}) => Object.assign({
  player_name: name, customer_id: rid, scoring_round_id: rid, index: 5.5, hcp: 6,
  gross: g, net: n, net_pts: pts, par: 36, to_par_gross: g - 36, to_par_net: n - 36,
  win_net: false, win_gross: false, win_skins: false, win_mvp: false,
  net_flight: 1, gross_flight: 1, skins_flight: 1, won_total: 0, won_by_cat: {}
}, opts);

function payload(state) {
  const won = (cat, cents, detail) => [{ category: cat, label: cat, cents, detail }];
  const ov = [
    mk(1, 'Adam Baker', 38, 34, 11, { won_total: 63 + 30, won_by_cat: { individual_net: 63, team_net: 30 } }),
    mk(2, 'Bob Skins', 40, 36, 9, { won_total: 39, won_by_cat: { skins: 39 } }),
    mk(3, 'Mike Mvp', 42, 37, 12, { won_total: 40, won_by_cat: { mvp: 40 } }),
    mk(4, 'Pat Plain', 45, 40, 5),
  ];
  const nb = [
    { label: 'LOW FLIGHT', rows: [Object.assign({}, ov[0], { buyer: true, won: won('individual_net', 6300, '1st') }),
                                  Object.assign({}, ov[1], { buyer: true, won: [] })] },
    { label: 'HIGH FLIGHT', rows: [Object.assign({}, ov[2], { buyer: true, won: [] }),
                                   Object.assign({}, ov[3], { buyer: false, won: [] })] },
  ];
  return {
    event: { id: 9, name: 's10.20 Test', holes: 9, score_source: 'entry' },
    board_state: state,
    field_complete: state === 'in_review' || state === 'final',
    money_visible: state === 'in_review' || state === 'final',
    money_final: state === 'final',
    hole_cols: [1, 2, 3], hole_par: {}, hole_pts: {}, cards: { 1: [[1, 4, 0]], 2: [], 3: [], 4: [] },
    skin_cells: {}, games_off: [], waiting: [],
    overall_board: ov,
    net_board: nb,
    gross_board: nb.map(s => ({ label: s.label, rows: s.rows.map(r => Object.assign({}, r, { won: [] })) })),
    skins_board: [{ label: 'LOW FLIGHT', rows: [Object.assign({}, ov[1], { buyer: true, won: won('skins', 3900, 'Skins F1 ×1 holes 2') })] }],
    points_board: ov.map(r => Object.assign({}, r, { buyer: true, won: r.customer_id === 3 ? won('mvp', 4000, '') : [] })),
    teams: [{ position: '1', purse: 120, total_net: 30,
              players: [Object.assign({}, ov[0], { team_won: 30 }), Object.assign({}, ov[3], { team_won: 30 })] }],
    proxies: [{ label: 'CTP', player: 'Pat Plain', detail: 'hole 3', purse: 15 }],
    hio: [],
    pot: 252,
    pots: {
      net: { total: 135, flights: [{ flight_no: 1, players: 10, pot: 90, places: [60, 30] },
                                   { flight_no: 2, players: 6, pot: 45, places: [45] }] },
      skins: { total: 39, flights: [{ flight_no: 1, players: 8, pot: 39, places: [] }] },
      team: { total: 120, places: [80, 40] },
      prox: { total: 30, each: [15, 15] },
    },
    projected: null,
    match_play: [],
  };
}

console.log('== SUMMARY visibility by state ==');
for (const st of ['upcoming', 'live']) {
  const d = payload(st);
  if (d.money_visible === false) R.evlbBlankMoneyProj(d);
  const h = R.evlbEventHtml(d);
  ck(`${st}: no SUMMARY tab`, !/data-sub="summary"/.test(h));
  ck(`${st}: landing is TEAM, not SUMMARY`, /class="evlb-subtab active" data-sub="team"/.test(h), h.slice(0, 400));
}
{
  const d = payload('in_review');
  const h = R.evlbEventHtml(d);
  const btns = [...h.matchAll(/data-sub="([a-z]+)"/g)].map(m => m[1]);
  ck('in review: SUMMARY is the FIRST tab', btns[0] === 'summary', btns.join(','));
  ck('in review: SUMMARY is the landing tab', /evlb-subtab active" data-sub="summary"/.test(h));
  // Batch 1 (#2147 §3): SUMMARY uses the same style as every other tab
  ck('in review: SUMMARY has no colour of its own and no tab badge', !/evlb-sum-tab/.test(h));
  ck('in review: panel badge says IN REVIEW', /evlb-sum-badge in_review">IN REVIEW</.test(h));
  ck('in review: TEAM panel is hidden at landing', /data-panel="team" hidden/.test(h));
  const s = R.evlbSummaryHtml(d);
  ck('summary lists Team purse', /TEAM NET[\s\S]*\$120/.test(s));
  ck('summary lists Net winner with flight and $63', /LOW FLIGHT[\s\S]*Adam Baker[\s\S]*\$63/.test(s));
  ck('summary lists Skins $39', /SKINS[\s\S]*Bob Skins[\s\S]*\$39/.test(s));
  ck('summary lists MVP $40', /MVP[\s\S]*Mike Mvp[\s\S]*\$40/.test(s));
  ck('summary lists CTP $15', /CTPs[\s\S]*Pat Plain[\s\S]*\$15/.test(s));
  ck('summary blocks in tab order', s.indexOf('TEAM NET') < s.indexOf('>MVP<') && s.indexOf('>MVP<') < s.indexOf('>NET<')
     && s.indexOf('>NET<') < s.indexOf('>SKINS<') && s.indexOf('>SKINS<') < s.indexOf('>CTPs<'));
  ck('summary links to each board', ['team', 'points', 'net', 'skins', 'prox'].every(g => s.includes(`data-evlb-goto="${g}"`)));
  ck('in review amounts carry the in-review class', /evlb-sum in-review/.test(s));
  // an Unlock that moves a figure: SUMMARY reads the same rows
  d.net_board[0].rows[0].won = [{ category: 'individual_net', cents: 5700, detail: '1st' }];
  ck('summary follows a changed figure ($57)', /Adam Baker[\s\S]*\$57/.test(R.evlbSummaryHtml(d)));
}
{
  const d = payload('final');
  const h = R.evlbEventHtml(d);
  ck('final: panel badge says FINAL', /evlb-sum-badge final">FINAL</.test(h));
  ck('final: no in-review class', !/evlb-sum in-review/.test(R.evlbSummaryHtml(d)));
}
{
  const d = payload('in_review');
  d.games_off = [{ game: 'included' }];
  ck('no-games event: no SUMMARY', !R.evlbSummaryShown(d));
  const d2 = payload('in_review'); d2._moneyHeld = true;
  ck('money held: no SUMMARY', !R.evlbSummaryShown(d2));
}

console.log('== projected WON (LIVE) ==');
{
  const d = payload('live');
  d.projected = { by_cid: { '1': { individual_net: 60, team_net: 20 }, '2': { skins: 22.5 }, '3': { mvp: 40 } },
                  teams: [{ index: 0, purse: 80, slots: { '1': 20, '4': 20 } }], total: 162.5, rows: [] };
  R.evlbBlankMoneyProj(d);
  ck('projection switched on', R.evlbProjOn(d));
  ck('win tints stay off', d.overall_board.every(r => !r.win_net && !r.win_skins && !r.win_mvp));
  const h = R.evlbEventHtml(d);
  ck('WON header carries the PROJ. marker', /Won <span class="evlb-proj"[^>]*>PROJ\.<\/span>/.test(h));
  ck('board is not no-won while projecting', !/evlb-holes[^"]*no-won/.test(h));
  ck('board carries the projected style', /evlb-projwon/.test(h));
  const net = (h.split('data-panel="net"')[1] || '').split('data-panel=')[0];
  ck('NET tab: Adam projects $60.00', /Adam Baker[\s\S]*?class="won br">\$60\.00</.test(net), net.slice(0, 600));
  ck('NET tab: no team money in the NET WON', !/\$80\.00|\$20\.00/.test(net));
  const sk = (h.split('data-panel="skins"')[1] || '').split('data-panel=')[0];
  ck('SKINS tab: Bob projects $22.50', /\$22\.50/.test(sk));
  ck('SKINS tab: no net money', !/\$60\.00/.test(sk));
  const team = (h.split('data-panel="team"')[1] || '').split('data-panel=')[0];
  ck('TEAM tab: team purse projected $80', /\$80\.00/.test(team));
  // Batch 1 §5: the opened team card is N / ± / USED; per-player shares left it
  ck('TEAM tab: the opened card carries no per-player share', !/\$20\.00/.test(team));
  ck('TEAM tab: no net money', !/\$60\.00/.test(team));
  const px = (h.split('data-panel="prox"')[1] || '').split('data-panel=')[0];
  ck('CTPs tab: holder amount kept while LIVE', /\$15\.00/.test(px) && /evlb-projwon/.test(px));
  ck('no SUMMARY while LIVE', !/data-sub="summary"/.test(h));
}
{
  const d = payload('live');   // no projection from the server
  R.evlbBlankMoneyProj(d);
  ck('no projection: WON stays hidden', !R.evlbProjOn(d) && /no-won/.test(R.evlbEventHtml(d)));
}

console.log('== money only on its own tab ==');
{
  const cats = R.EVLB_GAME_CATS, seen = {};
  let disjoint = true;
  Object.entries(cats).forEach(([g, cs]) => cs.forEach(c => { if (seen[c]) disjoint = false; seen[c] = g; }));
  ck('each payout category belongs to one tab', disjoint);
  const r = { won_by_cat: { individual_net: 1, individual_gross: 2, skins: 4, mvp: 8, tgf_mvp: 16, team_net: 32, ctp: 64 }, won_total: 127 };
  ck('net tab = net only', R.evlbGameMoney(r, 'net') === 1);
  ck('gross tab = gross only', R.evlbGameMoney(r, 'gross') === 2);
  ck('skins tab = skins only', R.evlbGameMoney(r, 'skins') === 4);
  ck('mvp tab = City + TGF MVP only', R.evlbGameMoney(r, 'points') === 24);
  ck('team tab = team only', R.evlbGameMoney(r, 'team') === 32);
  ck('CTP money on no player tab', !Object.values(cats).some(cs => cs.includes('ctp')));
}

console.log('== pot headers ==');
{
  const d = payload('live');
  ck('LOW flight band text', R.evlbPotBandText(d, 'net', 1) === ' · 10 players · pot $90.00 (1st $60.00 · 2nd $30.00)',
     R.evlbPotBandText(d, 'net', 1));
  ck('one-place flight has no ladder', R.evlbPotBandText(d, 'net', 2) === ' · 6 players · pot $45.00');
  ck('skins says per skin', /split per skin/.test(R.evlbPotBandText(d, 'skins', 1)));
  ck('no pot, no text', R.evlbPotBandText(d, 'gross', 1) === '');
  const h = R.evlbEventHtml(d);
  ck('the band row carries the pot', /LOW FLIGHT<span class="evlb-bandpot"> · 10 players · pot \$90/.test(h));
  // Batch 1 §4: the team pot shows once, on the dial line
  ck('TEAM pot line', /Pot <b>\$120\.00<\/b><span class="pl"> &middot; 1st \$80\.00 &middot; 2nd \$40\.00/.test(h));
  ck('CTP pot line', /CTP pot \$30\.00 \(\$15\.00 · \$15\.00\)/.test(h));
}

console.log('== Match Play tab ==');
{
  const d = payload('final');
  ck('no matches: no Match Play tab', !/data-sub="mp"/.test(R.evlbEventHtml(d)));
  d.match_play = [{ kind: 'pool', chapter: 'San Antonio', pool_name: 'Pool A', player1_name: 'Adam Baker',
                    player2_name: 'Bob Skins', winner_name: 'Adam Baker', margin: '2&1', played_at: 'x' }];
  const h = R.evlbEventHtml(d);
  const btns = [...h.matchAll(/data-sub="([a-z]+)"/g)].map(m => m[1]);
  ck('matches: Match Play tab added last', btns[btns.length - 1] === 'mp', btns.join(','));
  ck('matches: panel in the standard mpv2 wrapper', /class="mpv2 evlb-mp"/.test(h));
  ck('matches: the match is listed', /Adam Baker vs Bob Skins/.test(R.evlbMatchPlayHtml(d)));
  ck('matches: grouped by chapter and pool', /San Antonio · Pool A/.test(R.evlbMatchPlayHtml(d)));
}

console.log(fails ? `\n${fails} FAILURE(S)` : '\nALL PASS');
process.exit(fails ? 1 : 0);
