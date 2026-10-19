// The 10/19 leaderboard rulings, board side (handoff 12.7 / 13): B1 tab
// order + OVERALL behind its dial, B2 CTPs / PROXIES, B4 the state strip,
// B6 live ranking on TEAM / MVP / SKINS, B7 the THRU column.
// Runs the PAGE's own renderer headless: evlbFmt .. evlbTeamCard sliced out
// of templates/contests.html. Run: node test_evlb_rulings_b1_b7.js
const fs = require('fs');
const src = fs.readFileSync(require('path').join(__dirname, 'templates/contests.html'), 'utf8');
const lines = src.split('\n');
const a = lines.findIndex(l => l.startsWith('    function evlbFmt(c)'));
const b = lines.findIndex(l => l.startsWith('    function evlbAlignCard('));
if (a < 0 || b < 0) throw new Error('renderer region not found');
globalThis.document = { addEventListener() {}, querySelector() { return null; } };
globalThis.$ = () => null;
const code = 'const escapeHtml = s => String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;");\n'
  + lines.slice(a, b).join('\n')
  + '\nObject.assign(globalThis, { evlbEventHtml, evlbStdBoard, evlbBoardBody, evlbColCount, EVLB_BOARDS,'
  + ' evlbThruCell, evlbTeamStanding, evlbTeamsLiveOrder, evlbStateStrip, evlbFinalNotice, evlbReadGuide, evlbPtsPace });';
eval(code);

let fails = 0;
const check = (label, cond, detail) => {
  console.log(`  ${cond ? 'PASS' : 'FAIL'}  ${label}${cond ? '' : '  ' + JSON.stringify(detail ?? '')}`);
  if (!cond) fails++;
};
const tabsOf = html => [...html.matchAll(/class="evlb-subtab[^"]*" data-sub="([a-z]+)"/g)].map(m => m[1]);
const activeOf = html => (html.match(/class="evlb-subtab active" data-sub="([a-z]+)"/) || [])[1];

// a nine, par 4 everywhere; four players
const HOLES = [1, 2, 3, 4, 5, 6, 7, 8, 9];
const par = {}; HOLES.forEach(n => { par[String(n)] = 4; });
const card = (scores) => scores.map((g, i) => [i + 1, g, 0]);
const mk = (rid, name, o) => Object.assign({
  player_name: name, customer_id: rid, scoring_round_id: rid, index: 5, hcp: 5,
  win_net: false, win_gross: false, win_skins: false, win_mvp: false,
  won_total: 0, won_by_cat: {}, net_flight: 1, gross_flight: 1, skins_flight: 1 }, o);
function payload(over) {
  const ov = [
    // finished: 36 gross, 31 net, 20 pts
    mk(1, 'Adam BAKER', { gross: 36, net: 31, par: 36, to_par_gross: 0, to_par_net: -5, net_pts: 20, thru: 9, finished: true }),
    // five holes: 21 gross (+1), 18 net (-2), 9 pts (+4 on a 1-point par)
    mk(2, 'Michelle DelCARMEN', { gross: 21, net: 18, par: 20, to_par_gross: 1, to_par_net: -2, net_pts: 9, thru: 5, finished: false }),
    // three holes: 11 gross (-1), 10 net (-2), 6 pts (+3)
    mk(3, 'Sean MacBride', { gross: 11, net: 10, par: 12, to_par_gross: -1, to_par_net: -2, net_pts: 6, thru: 3, finished: false }),
    // not teed off
    mk(4, 'Pat Late', { gross: null, net: null, par: null, to_par_gross: null, to_par_net: null, net_pts: null, thru: 0, finished: false,
                        tee_start: { tee_time: '3:40 PM', start_hole: '10' } }),
  ];
  const sec = rows => [{ label: null, rows: rows.map(r => Object.assign({}, r, { buyer: true })) }];
  return Object.assign({
    hole_cols: HOLES, hole_par: par,
    cards: { 1: card([4, 4, 4, 4, 4, 4, 4, 4, 4]), 2: card([4, 4, 4, 4, 5]), 3: card([3, 4, 4]), 4: [] },
    overall_board: ov, net_board: sec(ov), gross_board: sec(ov), skins_board: sec(ov),
    points_board: ov.slice().sort((x, y) => (y.net_pts ?? -99) - (x.net_pts ?? -99)),
    teams: [], proxies: [], hio: [], games_off: [], skins_variant: {}, tee_legend: [],
    pts_par_hole: 1, field_complete: false, money_visible: false,
  }, over || {});
}

console.log('== B1: tab order, OVERALL behind evlb_overall_tab ==');
let h = evlbEventHtml(payload());
check('TEAM, MVP, NET, GROSS, SKINS, CTPs, no OVERALL (dial off)',
  JSON.stringify(tabsOf(h)) === JSON.stringify(['team', 'points', 'net', 'gross', 'skins', 'prox']), tabsOf(h));
check('no team board: lands on NET', activeOf(h) === 'net', activeOf(h));
check('OVERALL\'s panel is not built when its tab is off', !h.includes('data-panel="overall"'));
h = evlbEventHtml(payload({ overall_tab: true }));
check('dial on: OVERALL comes back, last', tabsOf(h).slice(-1)[0] === 'overall' && tabsOf(h).length === 7, tabsOf(h));
h = evlbEventHtml(payload({ games_off: [{ game: 'included', note: 'none' }] }));
check('an event with no games keeps its one Overall board (Gross and Net side by side)',
  JSON.stringify(tabsOf(h)) === '["overall"]' && activeOf(h) === 'overall', tabsOf(h));
const tm = { position: '1', players: [{ scoring_round_id: 1 }, { scoring_round_id: 2 }] };
h = evlbEventHtml(payload({ teams: [tm], field_complete: true, money_visible: true }));
check('with teams: lands on TEAM', activeOf(h) === 'team', activeOf(h));

console.log('== B2: CTPs or PROXIES ==');
h = evlbEventHtml(payload());
check('default reads CTPs, kept in its own case inside the uppercase row',
  h.includes('data-sub="prox"><span class="evlb-keepcase">CTPs</span>'));
h = evlbEventHtml(payload({ proxy_tab_label: 'PROXIES' }));
check('a Longest Putt makes it PROXIES', h.includes('<span class="evlb-keepcase">PROXIES</span>'));
check('the CSS keeps the small s', /\.evlb-seg button \.evlb-keepcase \{ text-transform: none; \}/.test(src));
check('HOW IT WORKS names the Longest Putt on PROXIES',
  evlbReadGuide(payload({ proxy_tab_label: 'PROXIES' }), 'prox').includes('Longest Putt'));

console.log('== B4: the state strip ==');
const st = { board_state: 'live', board_state_word: 'LIVE', board_state_text: 'Scores are coming in hole by hole.',
             board_state_guide: [
               { state: 'upcoming', word: 'UPCOMING', text: 'Pairings are set.' },
               { state: 'live', word: 'LIVE', text: 'Scores are coming in.' },
               { state: 'in_review', word: 'IN REVIEW', text: 'Every score is in. Cards lock 15 minutes after.' },
               { state: 'final', word: 'FINAL', text: 'Results are closed and prizes are set.' }] };
h = evlbEventHtml(payload(st));
check('one strip, first thing on the board, word + line',
  h.startsWith('<div class="evlb-state s-live" data-state="live"><span class="w">LIVE</span><span class="t">Scores are coming in hole by hole.</span></div>'),
  h.slice(0, 160));
const ir = payload(Object.assign({}, st, { board_state: 'in_review', board_state_word: 'IN REVIEW',
  board_state_text: 'Every score is in.', money_visible: true, field_complete: true,
  money_final: false, money_final_at: '2026-10-20T01:42:00Z' }));
check('IN REVIEW adds the card-lock time', evlbStateStrip(ir).includes('Cards lock at'), evlbStateStrip(ir));
check('the old "not final yet" banner yields to the strip', evlbFinalNotice(ir) === '');
const held = Object.assign({}, ir, { board_state_held: true, board_state_text: 'Results are being checked.' });
check('a hold reads "Results are being checked." with no lock time',
  evlbStateStrip(held).includes('IN REVIEW') && evlbStateStrip(held).includes('Results are being checked.')
  && !evlbStateStrip(held).includes('Cards lock'));
const g = evlbReadGuide(payload(st), 'net');
check('HOW IT WORKS explains all four state words',
  g.includes('State words') && ['UPCOMING', 'LIVE', 'IN REVIEW', 'FINAL'].every(w => g.includes('<b>' + w + '</b>'))
  && g.includes('Results are being checked.'));
check('...and THRU', g.includes('>Thru<'));
check('no strip without a server state (older payloads)', evlbStateStrip({}) === '');

console.log('== B7: THRU, PGA style ==');
const P = payload().overall_board;
check('finished on GROSS: F and the gross total', evlbThruCell({}, P[0], 'gross').includes('<span class="f">F</span>36'));
check('finished on NET: F and the net total', evlbThruCell({}, P[0], 'net').includes('<span class="f">F</span>31'));
check('finished on MVP: F and the points', evlbThruCell({}, P[0], 'points').includes('<span class="f">F</span>20'));
check('in play: holes completed', />5<\/td>$/.test(evlbThruCell({}, P[1], 'net')), evlbThruCell({}, P[1], 'net'));
check('before the tee: tee time and start hole', evlbThruCell({}, P[3], 'net').includes('3:40 PM · 10'));
check('before the tee with no pairing: a dash', evlbThruCell({}, Object.assign({}, P[3], { tee_start: null }), 'net').includes('–'));
const dd = payload({ field_complete: true, money_visible: true });
const html = evlbStdBoard(dd, { sections: [{ label: null, rows: dd.overall_board }], game: 'gross', gameCol: false, netCol: false, sort: 'gross' });
const id = (html.match(/data-board="(evb\d+)"/) || [])[1];
const ths = (html.match(/<th /g) || []).length;
check('a Thru header on the board', html.includes('class="sortable thru"'));
check('the column count still matches the header (bands span the full width)', evlbColCount(dd, EVLB_BOARDS[id].board) === ths, [evlbColCount(dd, EVLB_BOARDS[id].board), ths]);
check('every body row carries one thru cell', (html.match(/<td class="thru/g) || []).length === dd.overall_board.length + 1 /* PAR row */);
check('a payload with no THRU (the Cup boards) hides the column',
  !html.includes(' no-thru"') && evlbStdBoard({ hole_cols: [1], cards: {}, overall_board: [{ scoring_round_id: 9, player_name: 'X' }] },
    { sections: [{ label: null, rows: [{ scoring_round_id: 9, player_name: 'X' }] }], sort: 'net' }).includes(' no-thru"'));
check('hidden while the hole-by-hole grid shows',/\.evlb-ovr:not\(\.no-holes\) \.thru \{ display: none; \}/.test(src));
const tH = evlbStdBoard(dd, { sections: [{ label: 'T1', rows: [P[0], P[1]] }], teamBands: true,
  teams: [{ position: '1', players: [{ scoring_round_id: 1 }, { scoring_round_id: 2 }] }],
  game: 'team', gameCol: false, grossCol: false, sort: 'keep' });
check('the TEAM NET row carries the team THRU (holes every ball posted)',
  /<tr class="teamrow">[\s\S]*<td class="thru">5<\/td>/.test(tH));

console.log('== B6: live ranking on to-par, then holes done ==');
const live = payload({ field_complete: false });
const order = (board) => {
  const x = evlbStdBoard(live, board);
  const bid = (x.match(/data-board="(evb\d+)"/) || [])[1];
  return [...evlbBoardBody(bid).matchAll(/data-rid="(\d+)"/g)].map(m => +m[1]);
};
check('NET: tied at -2, five holes beats three', JSON.stringify(order(
  { sections: [{ label: null, rows: [P[2], P[1]] }], game: 'net', gameCol: false, sort: 'tpn' })) === '[2,3]');
// MVP: Baker 20 pts over 9 (+11), DelCarmen 9 over 5 (+4), MacBride 6 over 3 (+3)
check('MVP pace = points less a par point per hole played', evlbPtsPace(live, P[1]) === 4 && evlbPtsPace(live, P[2]) === 3);
h = evlbEventHtml(live);
const mvpId = (h.match(/data-panel="points"[^>]*>[\s\S]*?data-board="(evb\d+)"/) || [])[1];
check('MVP while LIVE ranks on points against par', EVLB_BOARDS[mvpId].sortKey === 'ptspace', EVLB_BOARDS[mvpId] && EVLB_BOARDS[mvpId].sortKey);
h = evlbEventHtml(payload({ field_complete: true, money_visible: true }));
const mvpId2 = (h.match(/data-panel="points"[^>]*>[\s\S]*?data-board="(evb\d+)"/) || [])[1];
check('MVP once the field is in keeps the server order (and its MVP tiebreak)', EVLB_BOARDS[mvpId2].sortKey === 'keep');
// SKINS: same skins count, gross to-par decides, then holes
const sk = payload({ field_complete: false, skin_cells: {} });
const skx = evlbStdBoard(sk, { sections: [{ label: null, rows: [P[1], P[2]] }], game: 'skins', sort: 'gamecol',
  gameCol: { key: 'skins', label: '#', value: (d0, r) => ((d0.skin_cells || {})[String(r.scoring_round_id)] || []).length },
  gameColAfterWon: true, netCol: false });
const skId = (skx.match(/data-board="(evb\d+)"/) || [])[1];
check('SKINS while LIVE: level on skins, the better gross to-par first',
  JSON.stringify([...evlbBoardBody(skId).matchAll(/data-rid="(\d+)"/g)].map(m => +m[1])) === '[3,2]');
// TEAM: team A (1+2) has 5 holes all posted at 4,4,4,4,4 -> 20 vs par 20 = E;
// team B (3+4) has none posted by player 4 -> no standing, sorts last
const tA = { position: '2', players: [{ scoring_round_id: 1 }, { scoring_round_id: 2 }] };
const tB = { position: '1', players: [{ scoring_round_id: 3 }, { scoring_round_id: 4 }] };
const tC = { position: '3', players: [{ scoring_round_id: 1 }, { scoring_round_id: 3 }] };
const sA = evlbTeamStanding(live, tA), sC = evlbTeamStanding(live, tC);
check('a hole counts for the team only once every ball has posted it', sA.thru === 5 && sC.thru === 3, [sA, sC]);
check('team to-par is against par for those holes', sA.toPar === 0 && sC.toPar === -1, [sA.toPar, sC.toPar]);
const ord = evlbTeamsLiveOrder(live, [tA, tB, tC]);
check('teams rank on to-par, then holes; a team with nothing counted goes last',
  ord[0] === tC && ord[1] === tA && ord[2] === tB, ord.map(t => t.position));
check('the position label follows the live order', tC.position === '1' && tA.position === '2' && tB.position === '', [tC.position, tA.position, tB.position]);

console.log(fails ? `\n${fails} FAILED` : '\nALL PASS');
process.exit(fails ? 1 : 0);
