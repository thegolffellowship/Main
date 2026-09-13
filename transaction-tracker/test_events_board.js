const fs = require('fs');
const src = fs.readFileSync(require('path').join(__dirname,'templates/contests.html'),'utf8');
// slice the whole renderer region out of the page and run it headless
const lines = src.split('\n');
const a = lines.findIndex(l => l.startsWith('    const EVLB_FLIGHT_COLORS'));
const b = lines.findIndex(l => l.startsWith('    function evlbEventHtml(d) {'));
if (a < 0 || b < 0) throw new Error('renderer region not found');
const code = 'let evlbShowHoles = true;\n'
  + 'const escapeHtml = s => String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;");\n'
  + lines.slice(a, b).join('\n')
  + '\nglobalThis.EVLB_BOARDS = EVLB_BOARDS;'
  + '\nglobalThis.evlbStdBoard = evlbStdBoard;'
  + '\nglobalThis.evlbBoardBody = evlbBoardBody;'
  + '\nglobalThis.evlbOvOf = evlbOvOf;'
  + '\nglobalThis.evlbSecsFrom = evlbSecsFrom;';
eval(code);

// synthetic event: 4 players, 2 flights, 9 holes
const mk = (rid, name, g, n, pts, opts={}) => Object.assign({
  player_name:name, customer_id:rid, scoring_round_id:rid, index:5.5, hcp:6,
  gross:g, net:n, net_pts:pts, par:36, to_par_gross:g-36, to_par_net:n-36,
  win_net:false, win_gross:false, win_skins:false, win_mvp:false,
  net_flight:1, gross_flight:1, skins_flight:1, won_total:0, won_by_cat:{} }, opts);
const d = {
  hole_cols:[1,2,3,4,5,6,7,8,9],
  // par per hole for the header's PAR row; hole 7 is deliberately
  // ABSENT — the tees disagreed there, so it must render blank
  hole_par:{"1":4,"2":4,"3":3,"4":5,"5":4,"6":4,"8":4,"9":5},
  // net stableford points per hole -> the MVP/Points tab's PTS row
  hole_pts:{"1":{"1":2,"2":1},"2":{"1":1},"3":{"1":3}},
  // [hole, gross, strokes_received] — rid 1 pops on hole 2, rid 3 gets
  // two on hole 1, so the dot rendering is exercised at 0/1/2 strokes
  cards:{ 1:[[1,4,0],[2,5,1]], 2:[[1,5,0]], 3:[[1,6,2]], 4:[[1,4,0]] },
  skin_cells:{ "2":[1] },
  overall_board:[
    // won_total is the whole event; won_by_cat is what each game paid,
    // so a game tab can show only its own money (Kerry 2026-09-13)
    mk(1,'LOW, Player',38,34,11,{win_net:true,won_total:135.5,net_flight:1,
        won_by_cat:{individual_net:79.5, team_net:56}}),
    mk(2,'SKIN, Winner',40,36,9,{win_skins:true,won_total:39,skins_flight:2,
        won_by_cat:{skins:39}}),
    mk(3,'MVP, Guy',42,37,12,{win_mvp:true,won_total:30,
        won_by_cat:{tgf_mvp:30}}),
    mk(4,'PLAIN, Nobody',45,40,5),
  ],
};
// the per-GAME boards carry `buyer`; the OVERALL board deliberately
// does not, which is what keeps both of Kerry's rules true at once
const withBuyer = (r, b) => Object.assign({}, r, {buyer:b});
d.net_board=[{label:'LOW Flight',rows:[withBuyer(d.overall_board[0],true),
                                       withBuyer(d.overall_board[1],true)]},
             {label:'HIGH Flight',rows:[withBuyer(d.overall_board[2],true),
                                        withBuyer(d.overall_board[3],false)]}];
d.gross_board=d.net_board;
d.skins_board=d.net_board;
d.points_board=d.overall_board.map(r=>Object.assign({},r,{buyer:!!r.win_mvp,
  mvp_note:r.win_mvp?'MVP tiebreak 2 — low Gross (42)':null}));
d.teams=[{position:'1',gg_total:59,purse:224,players:[d.overall_board[0],d.overall_board[1]]}];

// use the PAGE's own row mapping, not a copy of it — a copy went stale
// once already (the team-band tap target) and hid a real behavior change
const ovIx={}; d.overall_board.forEach(r=>{ovIx[String(r.scoring_round_id)]=r;});
const ovOf=(x,note)=>evlbOvOf(ovIx,x,note);
const secsFrom=b=>evlbSecsFrom(ovIx,b);
const skinsCount=(dd,r)=>((dd.skin_cells||{})[String(r.scoring_round_id)]||[]).length||"";

// mirrors the page's boards object: `game` scopes a tab to its own
// results/money/colors; gameCol:false drops the Pts slot on the tabs
// whose own result isn't points
const boards={
  overall:{sections:[{label:null,rows:d.overall_board}],sort:'net'},
  net:{sections:secsFrom(d.net_board),sort:'net',game:'net',gameCol:false},
  gross:{sections:secsFrom(d.gross_board),sort:'gross',game:'gross',gameCol:false},
  skins:{sections:secsFrom(d.skins_board),sort:'gamecol',game:'skins',gameCol:{key:'skins',label:'Skins',value:skinsCount}},
  points:{sections:[{label:null,rows:d.points_board.map(x=>ovOf(x,x.mvp_note)).filter(Boolean)}],sort:'keep',game:'points'},
  team:{teamBands:true,teams:d.teams,game:'team',gameCol:false,sections:d.teams.map(t=>({label:`${t.position} · total ${t.gg_total}`,rows:t.players.map(x=>ovOf(x)).filter(Boolean)})),sort:'keep'},
};

let fails=0;
const ck=(l,c,dt='')=>{ if(c) console.log('  PASS  '+l); else { console.log('  FAIL  '+l+'  '+dt); fails++; } };

const colCount = h => (h.match(/<th /g)||[]).length;
const htmls = {};
for (const k of Object.keys(boards)) htmls[k] = evlbStdBoard(d, boards[k]);

console.log('== every tab is the same table ==');
const base = colCount(htmls.overall);
for (const k of ['overall','skins','points'])
  ck(`${k}: identical column count (${base})`, colCount(htmls[k]) === base, colCount(htmls[k]));
for (const k of ['net','gross','team'])
  ck(`${k}: drops the Pts slot, one column narrower`, colCount(htmls[k]) === base - 1, colCount(htmls[k]));
ck('skins relabels the game column to Skins', /class="sortable bl br[^"]*">Skins</.test(htmls.skins), '');
ck('points keeps Pts in that slot', /class="sortable bl br[^"]*">Pts</.test(htmls.points));
ck('net has no Pts column', !/>Pts</.test(htmls.net));
for (const k of Object.keys(boards))
  ck(`${k}: has the hole-by-hole toggle`, htmls[k].includes('data-ovr-holes'));

console.log('== bands + order ==');
ck('net board carries both flight bands',
   (htmls.net.match(/class="evlb-band"/g)||[]).length === 2);
ck('overall has no bands', !htmls.overall.includes('evlb-band'));
ck('team bands are tappable', htmls.team.includes('data-team="0"'));
ck('points keeps the MVP tiebreak note', htmls.points.includes('MVP tiebreak 2'));

console.log('== rank runs within a band ==');
const bodyNet = evlbBoardBody(Object.keys(EVLB_BOARDS).find(id=>EVLB_BOARDS[id].board===boards.net));
const ranks = [...bodyNet.matchAll(/<tr class="evlb-plr[^"]*"[^>]*>\s*<td>([^<]*)<\/td>/g)].map(m=>m[1]);
ck('each flight restarts at 1', JSON.stringify(ranks) === JSON.stringify(['1','2','1','2']), JSON.stringify(ranks));

console.log('== each tab lights up ONLY its own game ==');
ck('overall: net winner tinted', /title="won Individual Net/.test(htmls.overall));
ck('overall: skins circled', /evlb-circ/.test(htmls.overall));
ck('overall: MVP tinted', /title="Event MVP"/.test(htmls.overall));
ck('net tab: net winner tinted', /title="won Individual Net/.test(htmls.net));
ck('net tab: no skins circles', !/evlb-circ/.test(htmls.net));
ck('net tab: no MVP tint', !/title="Event MVP"/.test(htmls.net));
ck('skins tab: circles present', /evlb-circ/.test(htmls.skins));
ck('skins tab: no net tint', !/title="won Individual Net/.test(htmls.skins));
ck('gross tab: no net tint', !/title="won Individual Net/.test(htmls.gross));
ck('points tab: MVP tinted', /title="Event MVP"/.test(htmls.points));
ck('points tab: no net tint', !/title="won Individual Net/.test(htmls.points));
ck('team tab: no other-game tints', !/title="won Individual Net/.test(htmls.team) && !/evlb-circ/.test(htmls.team));

console.log('== Won is whole-event on overall, this game only per tab ==');
ck('overall shows the full $135.50', /\$135\.50/.test(htmls.overall));
ck('net tab shows only the $79.50 net money', /\$79\.50/.test(htmls.net) && !/\$135\.50/.test(htmls.net));
ck('team tab shows only the $56.00 team money', /\$56\.00/.test(htmls.team) && !/\$135\.50/.test(htmls.team));
ck('skins tab shows only the $39.00 skins money', /\$39\.00/.test(htmls.skins) && !/\$135\.50/.test(htmls.skins));
ck('gross tab pays nobody (no gross game)', !/\$/.test(htmls.gross.replace(/<thead[\s\S]*?<\/thead>/,'')));

console.log('== buy-in coloring on the NET/GROSS bundle tabs ==');
for (const k of ['net','gross','skins','points']) {
  ck(`${k}: buyers get a green row`, /class="evlb-plr bought"/.test(htmls[k]));
  ck(`${k}: non-buyers get a grey row`, /class="evlb-plr nobuy"/.test(htmls[k]));
  ck(`${k}: zebra stripe steps aside for the buy-in wash`,
     !/class="evlb-plr alt"/.test(htmls[k]));
}
ck('OVERALL never identifies buy-ins',
   !/bought|nobuy/.test(htmls.overall) && /class="evlb-plr alt"/.test(htmls.overall));
ck('TEAM never identifies buy-ins (entry includes it)',
   !/bought|nobuy/.test(htmls.team));
ck('the overall payload rows carry no buy-in flag at all',
   d.overall_board.every(r => !('buyer' in r) && !('_buyer' in r)));
// the mapping itself: _buyer rides only on rows that came off a GAME
// board, never on the shared overall row it copies from
ck('_buyer is lifted off the game board row, not the overall row',
   boards.net.sections[0].rows[0]._buyer === true
   && boards.net.sections[1].rows[1]._buyer === false
   && !('_buyer' in d.overall_board[0]),
   JSON.stringify(boards.net.sections.map(x=>x.rows.map(r=>r._buyer))));

console.log('== POPS on the hole scores (Kerry 2026-09-13) ==');
ck('one stroke received renders one dot',
   /<td class="h"><span class="evlb-pops">\u25CF<\/span>5<\/td>/.test(htmls.overall),
   (htmls.overall.match(/evlb-pops[^<]*<\/span>./g)||[]).join('|'));
ck('two strokes render two dots',
   /<span class="evlb-pops">\u25CF\u25CF<\/span>6/.test(htmls.overall));
ck('no stroke received renders no dots on that cell',
   /<td class="h">4<\/td>/.test(htmls.overall));
for (const k of Object.keys(boards))
  ck(`${k}: pops show on the hole scores`, /evlb-pops/.test(htmls[k]));
ck('the team tab keeps the dots on its NET cells',
   /class="h[^"]*"[^>]*><span class="evlb-pops">/.test(htmls.team), '');
ck('PAR row carries no pops',
   !/evlb-pops/.test((htmls.overall.match(/<tr class="evlb-parrow">[\s\S]*?<\/tr>/)||[''])[0]));

console.log('== PTS row per player on MVP/Points (Kerry 2026-09-13) ==');
const ptsRows = htmls.points.match(/<tr class="evlb-ptsrow">[\s\S]*?<\/tr>/g) || [];
ck('every player with points gets a PTS row', ptsRows.length === 3, ptsRows.length);
ck('PTS row is labelled', /<td class="nm">PTS<\/td>/.test(ptsRows[0] || ''), ptsRows[0]);
ck('PTS row carries the per-hole points (2 then 1)',
   /<td class="h">2<\/td><td class="h">1<\/td>/.test(ptsRows[0] || ''), ptsRows[0]);
ck('PTS row repeats the total under the Pts column',
   />11<\/td>/.test(ptsRows[0] || ''), ptsRows[0]);
ck('PTS row has the same column count as a player row',
   ((ptsRows[0]||'').match(/<td/g)||[]).length
   === ((htmls.points.match(/<tr class="evlb-plr[\s\S]*?<\/tr>/)||[''])[0].match(/<td/g)||[]).length,
   ((ptsRows[0]||'').match(/<td/g)||[]).length);
ck('PTS hole cells carry .h so the hole toggle hides them',
   ((ptsRows[0]||'').match(/class="h"/g)||[]).length === 9);
ck('PTS row is not tappable as a player row', !/evlb-plr/.test(ptsRows[0] || 'evlb-plr'));
ck('a player with no points data grows no PTS row',
   ptsRows.length === Object.keys(d.hole_pts).length);
ck('only the MVP/Points tab grows PTS rows',
   ['overall','net','gross','skins','team'].every(k => !/evlb-ptsrow/.test(htmls[k])));

console.log('== PAR row under the hole numbers (Kerry 2026-09-13) ==');
for (const k of Object.keys(boards))
  ck(`${k}: has a PAR row in the thead`,
     /<thead>[\s\S]*?<tr class="evlb-parrow">[\s\S]*?<\/thead>/.test(htmls[k]));
const prow = (htmls.overall.match(/<tr class="evlb-parrow">[\s\S]*?<\/tr>/)||[''])[0];
ck('PAR row is labelled', /<td class="nm">PAR<\/td>/.test(prow), prow);
ck('PAR row carries each hole par', /<td class="h">4<\/td><td class="h">4<\/td><td class="h">3<\/td>/.test(prow), prow);
ck('a hole whose tees disagree renders BLANK, not a guess',
   (prow.match(/<td class="h"><\/td>/g)||[]).length === 1, prow);
ck('total par blank while any hole par is missing',
   !/>33</.test(prow) && !/>36</.test(prow), prow);
ck('PAR row has the same column count as a player row',
   (prow.match(/<td/g)||[]).length
   === ((htmls.overall.match(/<tr class="evlb-plr[\s\S]*?<\/tr>/)||[''])[0].match(/<td/g)||[]).length,
   (prow.match(/<td/g)||[]).length);
ck('PAR hole cells carry .h so the hole toggle hides them',
   (prow.match(/class="h"/g)||[]).length === 9, prow);
// complete par data -> the total appears under BOTH score columns
const dFull = Object.assign({}, d, {hole_par:Object.assign({}, d.hole_par, {"7":3})});
const fullPar = (evlbStdBoard(dFull, {sections:[{label:null,rows:d.overall_board}],sort:'net'})
  .match(/<tr class="evlb-parrow">[\s\S]*?<\/tr>/)||[''])[0];
ck('complete par data totals to 36 under G and N',
   (fullPar.match(/>36</g)||[]).length === 2, fullPar);
// no par data at all -> no row rather than a row of blanks
const dNoPar = Object.assign({}, d, {hole_par:{}});
ck('no par data -> no PAR row at all',
   !/evlb-parrow/.test(evlbStdBoard(dNoPar, {sections:[{label:null,rows:d.overall_board}],sort:'net'})));

console.log('== TEAM NET total row (Kerry 2026-09-13) ==');
const trow = (htmls.team.match(/<tr class="teamrow">[\s\S]*?<\/tr>/) || [''])[0];
ck('team band closes with a TEAM NET row', /TEAM NET/.test(trow), trow.slice(0,120));
// rid 1 pops on hole 2, so its net there is 4 — the best ball follows
// the STROKES RECEIVED, not the gross
ck('team row carries the per-hole best ball (4 then 4, net of the pop)',
   /<td class="h">4<\/td><td class="h">4<\/td>/.test(trow), trow);
ck('team row shows GG posted total as the score of record',
   /<b>59<\/b>/.test(trow), trow);
ck('reconstruction disclosed when it differs from GG',
   /\(holes 8\)/.test(trow), trow);
ck('team row shows the WHOLE purse, not a share', /\$224\.00/.test(trow), trow);
ck('team row to-par computed off team par', />\+23</.test(trow), trow);
ck('team row is not tappable as a player row', !/evlb-plr/.test(trow));
ck('team row has the same column count as a player row',
   (trow.match(/<td/g)||[]).length
   === ((htmls.team.match(/<tr class="evlb-plr[\s\S]*?<\/tr>/)||[''])[0].match(/<td/g)||[]).length,
   (trow.match(/<td/g)||[]).length);
ck('team tab hole cells are NET, with the counting ball marked',
   /class="h count"/.test(htmls.team));
ck('other tabs keep GROSS hole cells (no counting marks)',
   !/class="h count"/.test(htmls.overall) && !/class="h count"/.test(htmls.net));
ck('only the team tab grows a teamrow',
   ['overall','net','gross','skins','points'].every(k => !/teamrow/.test(htmls[k])));

console.log('== sorting re-ranks within bands ==');
const nid = Object.keys(EVLB_BOARDS).find(id=>EVLB_BOARDS[id].board===boards.net);
EVLB_BOARDS[nid].sortKey='won'; EVLB_BOARDS[nid].sortDir=-1;
const sorted = evlbBoardBody(nid);
ck('re-sorted body still has both bands', (sorted.match(/class="evlb-band"/g)||[]).length===2);
ck('blank Won rows sink (rank blank)', /<td><\/td>/.test(sorted));

console.log(fails ? `\n${fails} FAILURE(S)` : '\nALL PASS');
process.exit(fails?1:0);
