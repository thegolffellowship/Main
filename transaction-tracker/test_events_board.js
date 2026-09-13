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
  + '\nglobalThis.evlbBoardBody = evlbBoardBody;';
eval(code);

// synthetic event: 4 players, 2 flights, 9 holes
const mk = (rid, name, g, n, pts, opts={}) => Object.assign({
  player_name:name, customer_id:rid, scoring_round_id:rid, index:5.5, hcp:6,
  gross:g, net:n, net_pts:pts, par:36, to_par_gross:g-36, to_par_net:n-36,
  win_net:false, win_gross:false, win_skins:false, win_mvp:false,
  net_flight:1, gross_flight:1, skins_flight:1, won_total:0 }, opts);
const d = {
  hole_cols:[1,2,3,4,5,6,7,8,9],
  cards:{ 1:[[1,4,0],[2,5,0]], 2:[[1,5,0]], 3:[[1,6,0]], 4:[[1,4,0]] },
  skin_cells:{ "2":[1] },
  overall_board:[
    mk(1,'LOW, Player',38,34,11,{win_net:true,won_total:79.5,net_flight:1}),
    mk(2,'SKIN, Winner',40,36,9,{win_skins:true,won_total:39,skins_flight:2}),
    mk(3,'MVP, Guy',42,37,12,{win_mvp:true,won_total:30}),
    mk(4,'PLAIN, Nobody',45,40,5),
  ],
};
d.net_board=[{label:'LOW Flight',rows:[d.overall_board[0],d.overall_board[1]]},
             {label:'HIGH Flight',rows:[d.overall_board[2],d.overall_board[3]]}];
d.gross_board=d.net_board;
d.skins_board=d.net_board;
d.points_board=d.overall_board.map(r=>Object.assign({},r,{mvp_note:r.win_mvp?'MVP tiebreak 2 — low Gross (42)':null}));
d.teams=[{position:'1',gg_total:59,purse:224,players:[d.overall_board[0],d.overall_board[1]]}];

const ovIx={}; d.overall_board.forEach(r=>{ovIx[String(r.scoring_round_id)]=r;});
const ovOf=(x,note)=>{const b=x&&ovIx[String(x.scoring_round_id)];return b?(note?Object.assign({},b,{_note:note}):b):null;};
const secsFrom=b=>(b||[]).map(s=>({label:s.label,rows:(s.rows||[]).map(x=>ovOf(x)).filter(Boolean)})).filter(s=>s.rows.length);
const skinsCount=(dd,r)=>((dd.skin_cells||{})[String(r.scoring_round_id)]||[]).length||"";

const boards={
  overall:{sections:[{label:null,rows:d.overall_board}],sort:'net'},
  net:{sections:secsFrom(d.net_board),sort:'net'},
  gross:{sections:secsFrom(d.gross_board),sort:'gross'},
  skins:{sections:secsFrom(d.skins_board),sort:'gamecol',gameCol:{key:'skins',label:'Skins',value:skinsCount}},
  points:{sections:[{label:null,rows:d.points_board.map(x=>ovOf(x,x.mvp_note)).filter(Boolean)}],sort:'keep'},
  team:{teamBands:true,teams:d.teams,sections:d.teams.map(t=>({label:`${t.position} · total ${t.gg_total}`,rows:t.players.map(x=>ovOf(x)).filter(Boolean)})),sort:'keep'},
};

let fails=0;
const ck=(l,c,dt='')=>{ if(c) console.log('  PASS  '+l); else { console.log('  FAIL  '+l+'  '+dt); fails++; } };

const colCount = h => (h.match(/<th /g)||[]).length;
const htmls = {};
for (const k of Object.keys(boards)) htmls[k] = evlbStdBoard(d, boards[k]);

console.log('== every tab is the same table ==');
const base = colCount(htmls.overall);
for (const k of Object.keys(boards))
  ck(`${k}: identical column count (${base})`, colCount(htmls[k]) === base, colCount(htmls[k]));
ck('skins relabels the game column to Skins', /class="sortable bl br[^"]*">Skins</.test(htmls.skins), '');
ck('others keep Pts in that slot', /class="sortable bl br[^"]*">Pts</.test(htmls.net));
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

console.log('== highlights travel with the player on every tab ==');
for (const k of ['overall','net','gross','skins','points'])
  ck(`${k}: net winner still tinted`, /title="won Individual Net/.test(htmls[k]));
ck('skins circle rendered on the skins winner', /evlb-circ/.test(htmls.overall));
ck('Won column money present', /\$79\.50/.test(htmls.overall));

console.log('== sorting re-ranks within bands ==');
const nid = Object.keys(EVLB_BOARDS).find(id=>EVLB_BOARDS[id].board===boards.net);
EVLB_BOARDS[nid].sortKey='won'; EVLB_BOARDS[nid].sortDir=-1;
const sorted = evlbBoardBody(nid);
ck('re-sorted body still has both bands', (sorted.match(/class="evlb-band"/g)||[]).length===2);
ck('blank Won rows sink (rank blank)', /<td><\/td>/.test(sorted));

console.log(fails ? `\n${fails} FAILURE(S)` : '\nALL PASS');
process.exit(fails?1:0);
