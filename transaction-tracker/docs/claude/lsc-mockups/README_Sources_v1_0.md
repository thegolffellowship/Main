# Lone Star Cup Screens — mockup sources v1.0 (canvas v29, 2026-10-07)

Chief of Staff's sign-off mockups, built on the live Tracker components (score_entry.html, contests.html, shell.css, cart_signs.html). Each board below is the body HTML of one Claude Design artboard; `lsc.css` is shared. Class names match the live templates where a component exists (`.se-*`, `.evlb-seg`, `.lsc-bd-*`, `.pr-hiw-link`, `.mp-match-*`); new classes are prefixed `lsc-`. Logo: Kerry's Lone Star Cup 2026 PNG (not included; Kerry uploads).

## lsc.css

```css
/* Lone Star Cup mockups: tokens and components copied from the live Tracker
   (templates/score_entry.html, templates/contests.html, static/css/shell.css).
   Fonts: Bitter for names/headings/labels, Helvetica Neue for body. */
body{margin:0;background:#FFFFFF;color:#1B1B1B;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif}
a{color:#B45A22}a:hover{color:#D06B2E}
.ph{width:390px;height:844px;box-sizing:border-box;display:flex;flex-direction:column;background:#FFFFFF;overflow:hidden;position:relative}
/* header.shell-nav.shell-member.shell-slim */
.shell-slim{background:#1B1B1B;min-height:77px;display:flex;align-items:center;justify-content:center;flex:none}
.tgf-mark{width:56px;height:56px;border-radius:50%;border:3px solid #FFFFFF;display:flex;align-items:center;justify-content:center;font:800 24px/1 Bitter,Georgia,serif;color:#FFFFFF}
/* header.shell-nav.shell-member (full) */
.shell-member{background:#1B1B1B;padding:10px 16px 0;flex:none}
.shell-member .row1{display:flex;align-items:center;gap:10px}
.shell-member .tgf-mark{width:34px;height:34px;border-width:2px;font-size:15px}
.shell-member .wordmark{font:700 15px Bitter,Georgia,serif;color:#FFFFFF}
.shell-cta-pill{margin-left:auto;background:#E87C3E;color:#FFFFFF;border-radius:99px;padding:7px 12px;font:700 10px/1 Bitter,Georgia,serif;letter-spacing:1px;text-transform:uppercase;text-decoration:none;white-space:nowrap}
.shell-member-tabs{display:flex;gap:18px;padding:10px 0 0}
.shell-member-tabs a{font:700 13px/1 Bitter,Georgia,serif;letter-spacing:1.2px;text-transform:uppercase;color:#9CA3AF;text-decoration:none;padding-bottom:10px;border-bottom:2px solid transparent}
.shell-member-tabs a.active{color:#E87C3E;border-bottom-color:#E87C3E}
/* .top-tabs on the Leaderboard page */
.top-tabs{display:flex;gap:16px;padding:0 16px;border-bottom:1px solid #E5E7EB;flex:none;overflow:hidden}
.top-tab{font:600 13px/1 'Helvetica Neue',Helvetica,Arial,sans-serif;color:#6B7280;padding:13px 0 11px;border-bottom:3px solid transparent;white-space:nowrap;text-decoration:none;display:flex;align-items:center;gap:6px}
.top-tab.active{color:#E87C3E;border-bottom-color:#E87C3E}
.evlb-beta{background:#FDE68A;color:#7C5E00;border-radius:99px;padding:1px 6px;font:700 9px/1.4 Bitter,Georgia,serif;text-transform:uppercase}
.lsc-chip{background:#FDF0E6;color:#BF5700;border-radius:99px;padding:3px 9px;font:700 10px/1.2 Bitter,Georgia,serif;letter-spacing:.5px;text-transform:uppercase;white-space:nowrap}
.tab-pill{background:#002868;color:#FFFFFF;border-radius:99px;padding:7px 12px;font:600 13px/1 'Helvetica Neue',Helvetica,Arial,sans-serif;text-decoration:none;white-space:nowrap;align-self:center;margin:6px 0}
.tab-pill.active{box-shadow:0 0 0 2px #E87C3E}
/* nav.se-toggle */
.se-toggle{padding:8px 16px;border-bottom:1px solid #EEF0F2;background:#FFFFFF;flex:none}
.se-tg-in{display:flex}
.se-tg-in a{flex:1;min-height:40px;border:1px solid #E5E7EB;display:flex;flex-direction:column;align-items:center;justify-content:center;font:700 12px/1 Bitter,Georgia,serif;letter-spacing:.06em;text-transform:uppercase;color:#6B7280;text-decoration:none;gap:3px}
.se-tg-in a:first-child{border-radius:99px 0 0 99px}
.se-tg-in a:last-child{border-radius:0 99px 99px 0;border-left:0}
.se-tg-in a.on{background:#1B1B1B;color:#FFFFFF;border-color:#1B1B1B}
.se-tg-s{font:600 9px/1 'Helvetica Neue',Helvetica,Arial,sans-serif;letter-spacing:.5px;opacity:.85;text-transform:none}
/* score-entry primitives */
.se-wrap{width:100%;box-sizing:border-box;align-self:stretch;min-width:0;padding:14px 16px 20px;flex:1;overflow:visible;display:flex;flex-direction:column;gap:8px}
.se-wrap>*{min-width:0;flex-shrink:0}
.se-eyebrow{font-size:12px;font-weight:700;letter-spacing:1.2px;color:#B45A22;text-transform:uppercase;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.se-h1{margin:2px 0 0;font-family:Bitter,Georgia,serif;font-size:30px;line-height:1.1;font-weight:700}
.se-sub{font-size:14px;color:#4B5563;margin-top:2px}
.se-copy{font-size:14px;line-height:1.5;color:#4B5563}
.se-stack{display:flex;flex-direction:column;gap:6px}
.se-pill{height:56px;border-radius:48px;font-size:17px;font-weight:600;font-family:inherit;width:100%;cursor:pointer;display:flex;align-items:center;justify-content:center;text-decoration:none;box-sizing:border-box}
.se-pill.go{border:none;background:#0d7556;color:#FFFFFF;font-weight:700}
.se-pill.dark{border:none;background:#1B1B1B;color:#FFFFFF}
.se-pill.line{border:1px solid #1B1B1B;background:transparent;color:#1B1B1B}
.se-name-btn{height:60px;border-radius:12px;border:1px solid #E5E7EB;background:#F8F8F8;display:flex;align-items:center;justify-content:space-between;padding:0 18px;font:600 18px Bitter,Georgia,serif;color:#1B1B1B;width:100%;cursor:pointer;box-sizing:border-box}
.se-name-btn span.m{font:500 13px 'Helvetica Neue',Helvetica,Arial,sans-serif;color:#4B5563}
.se-box{padding:12px 14px;border-radius:12px;border:1px solid #E5E7EB;background:#F8F8F8}
.se-lbl{font-size:11px;font-weight:700;letter-spacing:1px;color:#6B7280;text-transform:uppercase}
.se-status{display:flex;align-items:center;gap:8px;font-size:13px;color:#15803D}
.se-warn{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:12px;background:#FEF3C7;color:#78350F;font-size:13px}
.se-help{display:inline-flex;align-items:center;height:30px;padding:0 14px;border-radius:99px;background:#E87C3E;color:#FFFFFF;font:700 11px/1 Bitter,Georgia,serif;letter-spacing:1px;text-transform:uppercase;text-decoration:none}
/* rows with steppers */
.se-row{position:relative;display:flex;align-items:center;gap:4px;padding:7px 10px 7px 30px;border-radius:12px;border:1px solid #E5E7EB;background:#FFFFFF}
.se-tee{position:absolute;left:0;top:0;bottom:0;width:16px;border-radius:12px 0 0 12px}
.se-tee.ring{background:#FFFFFF;box-shadow:inset 0 0 0 2px #1B1B1B}
.se-who{flex-grow:1;min-width:0;display:flex;flex-direction:column;gap:1px;margin-right:6px}
.se-name{font:600 17px/1.2 Bitter,Georgia,serif;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.se-meta{font-size:12.5px;color:#4B5563;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.se-minus,.se-plus{width:44px;height:44px;border-radius:22px;font-size:24px;line-height:1;flex:none;font-family:inherit;display:flex;align-items:center;justify-content:center;cursor:pointer}
.se-minus{border:1px solid #1B1B1B;background:#FFFFFF;color:#1B1B1B}
.se-plus{border:none;background:#1B1B1B;color:#FFFFFF}
.se-score{width:40px;margin:0 6px;position:relative;display:flex;flex-direction:column;align-items:center;gap:1px;flex:none}
.se-score .v{font-family:Bitter,Georgia,serif;font-size:32px;font-weight:700;line-height:1;font-variant-numeric:tabular-nums}
.se-score .v.empty{color:#9CA3AF}
.se-score .v.waiting{color:#B45A22}
.se-score .r{font-size:11px;font-weight:600;color:#4B5563;white-space:nowrap}
.se-x{font:800 32px/1 Bitter,Georgia,serif}
.se-pops{position:absolute;top:50%;height:44px;transform:translateY(-50%);right:-9px;display:flex;flex-direction:column;justify-content:center;gap:3px}
.se-pops .g{display:flex;flex-direction:column;gap:2px}
.se-pop{width:7px;height:7px;border-radius:50%;background:#1B1B1B;display:block}
.se-pop.t{background:#E87C3E}
.se-lblrow{display:flex;justify-content:space-between;align-items:center;margin-top:4px}
.se-keepnote{display:inline-flex;align-items:center;gap:5px;font-size:12px;color:#4B5563}
.se-strip{display:grid;grid-template-columns:repeat(9,minmax(0,1fr));gap:4px}
.se-cell{height:34px;border-radius:8px;display:flex;align-items:center;justify-content:center;border:1px solid #E5E7EB;background:#FFFFFF;position:relative}
.se-cell .n{font-size:15px;font-weight:700;color:#4B5563;font-variant-numeric:tabular-nums}
.se-cell .k{position:absolute;top:2px;right:4px;font-size:9px;font-weight:800;line-height:1}
.se-cell.saved{background:#d1f4e0;border-color:#d1f4e0}
.se-cell.saved .n,.se-cell.saved .k{color:#0d7556}
.se-cell.waiting{background:#FEF3C7;border-color:#FEF3C7}
.se-cell.cur{background:#FFFFFF;border:2px solid #E87C3E}
.se-cell.cur .n{color:#1B1B1B}
.se-popkey{display:flex;flex-wrap:wrap;row-gap:4px;gap:12px;justify-content:center;align-items:center;font-size:11.5px;color:#4B5563;margin-top:6px}
.se-popkey span{display:inline-flex;align-items:center;gap:5px;white-space:nowrap}
.se-bottom{position:absolute;left:0;right:0;bottom:0;background:#FFFFFF;border-top:1px solid #EEF0F2;padding:10px 16px 18px}
.se-row-act{max-width:480px;margin:0 auto;display:flex;gap:8px;align-items:center}
.se-row-act .se-pill{flex:1;min-width:0;height:50px}
.se-nav button{width:50px;height:50px;border-radius:25px;border:1px solid #E5E7EB;background:#FFFFFF;display:flex;align-items:center;justify-content:center;font-size:20px;font-family:inherit;flex:none}
/* .se-cup team standings strip */
.se-cup{display:flex;align-items:stretch;border-radius:10px;overflow:hidden;border:1px solid #E5E7EB;background:#FFFFFF}
.se-cup .lbl{background:#002868;color:#FFFFFF;font:700 11px/1.2 Bitter,Georgia,serif;letter-spacing:1px;text-transform:uppercase;display:flex;align-items:center;justify-content:center;padding:0 8px;text-align:center;width:62px;flex:none}
.se-cup .tm{flex:1;display:flex;justify-content:space-between;align-items:center;padding:6px 10px;gap:6px;min-width:0}
.se-cup .tm b{font:800 20px/1 Bitter,Georgia,serif}
.se-cup .tm .nm{font:700 10.5px/1.2 Bitter,Georgia,serif;text-transform:uppercase;letter-spacing:.3px;min-width:0}
.se-cup .aus{border-left:5px solid #BF5700}
.se-cup .sa{border-left:5px solid #4B6274}
.se-cup .proj{display:block;font-size:9.5px;white-space:nowrap;color:#6B7280;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;font-weight:400;letter-spacing:0;text-transform:none}
/* .se-mcard / .mp-match-card */
.se-mstrip{display:flex;flex-direction:column;gap:6px}
.se-mcard{--ma:#BF5700;--mb:#4B6274;border:1px solid #E5E7EB;border-radius:10px;overflow:hidden;background:#FFFFFF;position:relative}
.se-mcard.won{border:2px solid #D4A017}
.mp-match-meta{background:#1B1B1B;color:#FFFFFF;display:flex;justify-content:space-between;align-items:center;padding:5px 10px;font:700 10px/1 Bitter,Georgia,serif;letter-spacing:.8px;text-transform:uppercase}
.mp-match-meta .live{color:#4ADE80}
.mp-match-meta .st{color:#E87C3E}
.se-mc-strip{display:flex;align-items:stretch;min-height:44px}
.se-mc-mono{width:36px;flex:none;display:flex;align-items:center;justify-content:center;font:700 13px/1 Bitter,Georgia,serif;color:#FFFFFF}
.se-mc-mono.a{background:var(--ma)}.se-mc-mono.b{background:var(--mb)}
.se-mc-name{flex:1;min-width:0;display:flex;flex-direction:column;justify-content:center;padding:0 8px}
.se-mc-name.r{align-items:flex-end;text-align:right}
.se-mc-name em{font-style:normal;font-size:11px;color:#6B7280;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}
.se-mc-name b{font:700 13px/1.1 Bitter,Georgia,serif;text-transform:uppercase;max-width:100%;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;word-break:break-word}
.se-mc-bar{flex:none;min-width:70px;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#FFFFFF;font:700 15px/1 Bitter,Georgia,serif;padding:0 8px}
.se-mc-bar small{font:600 9px/1.2 'Helvetica Neue',Helvetica,Arial,sans-serif;letter-spacing:.6px;text-transform:uppercase;opacity:.85;margin-top:2px}
.se-mc-bar.a{background:var(--ma);clip-path:polygon(12px 0,100% 0,100% 100%,12px 100%,0 50%);padding-left:16px}
.se-mc-bar.b{background:var(--mb);clip-path:polygon(0 0,calc(100% - 12px) 0,100% 50%,calc(100% - 12px) 100%,0 100%);padding-right:16px}
.se-mc-bar.tie{background:#BFB8AC}
.se-mc-dots{display:flex;flex-wrap:wrap;justify-content:center;gap:4px;padding:6px 8px}
.se-hd{width:9px;height:9px;border-radius:50%;display:block} /* mockup uses <i class="se-hd a|b|h|e"> */
.se-hd.a{background:var(--ma)}.se-hd.b{background:var(--mb)}.se-hd.h{background:#BFB8AC}.se-hd.e{border:1.5px solid #D6D3CC;box-sizing:border-box}
.se-mc-grid{border-top:1px solid #E5E7EB;padding:6px 6px 8px}
.se-mc-grid table{width:100%;border-collapse:collapse;table-layout:fixed;font-variant-numeric:tabular-nums;margin-bottom:6px}
.se-mc-grid th,.se-mc-grid td{text-align:center;font-size:13px;padding:4px 0;position:relative}
.se-mc-grid th:first-child,.se-mc-grid td:first-child{width:34px}
.se-mc-grid tr.h td,.se-mc-grid tr.h th{background:#1B1B1B;color:#FFFFFF;font-size:11px;font-weight:700}
.se-mc-grid tr.p td,.se-mc-grid tr.p th{color:#6B7280;font-size:11px}
.se-mc-grid td.dim{color:#C4C4C4}
.se-mc-grid .w{display:inline-block;min-width:22px;line-height:20px;border-radius:11px;color:#FFFFFF;font-weight:700}
.se-mc-grid .w.a{background:var(--ma)}.se-mc-grid .w.b{background:var(--mb)}
.se-mc-grid .pp{position:absolute;top:1px;left:0;right:0;display:flex;justify-content:center;gap:1px}
.se-mc-grid .pp i{width:4px;height:4px;border-radius:50%;background:#1B1B1B;display:block}
.se-mc-chip{display:inline-block;min-width:24px;padding:2px 3px;border-radius:4px;color:#FFFFFF;font:700 10px Bitter,Georgia,serif}
.se-mc-chip.a{background:var(--ma)}.se-mc-chip.b{background:var(--mb)}
.se-mc-note{font-size:11px;color:#6B7280;text-align:center}
.mp-open{font-size:11px;color:#6B7280;text-align:center;padding:0 0 6px}
/* Cup board */
.lsc-event{background:#002868;border-top:3px solid #E87C3E;color:#FFFFFF;border-radius:10px;padding:12px 14px;display:flex;flex-direction:column;gap:3px}
.lsc-event .ttl{font:700 20px/1.1 Bitter,Georgia,serif}
.lsc-event .sub{font-size:12.5px;opacity:.9}
.lsc-bd-head{display:flex;border-radius:10px;overflow:hidden}
.lsc-bd-head .t{flex:1;display:flex;align-items:center;gap:8px;padding:10px 12px;color:#FFFFFF;font:800 12px/1 Bitter,Georgia,serif;text-transform:uppercase;letter-spacing:.5px}
.lsc-bd-head .t .p{font:800 26px/1 Bitter,Georgia,serif}
.lsc-bd-head .t.austin{background:#BF5700}
.lsc-bd-head .t.sa{background:#4B6274;justify-content:flex-end}
.lsc-bd-head .mid{background:#002868;color:#FFFFFF;font:700 10.5px/1.25 Bitter,Georgia,serif;text-transform:uppercase;letter-spacing:.5px;display:flex;align-items:center;text-align:center;padding:0 10px;max-width:92px;flex:none}
.lsc-bd-proj{font-size:12.5px;color:#4B5563;text-align:center;line-height:1.4}
.lsc-bd-sess-h{display:flex;align-items:baseline;gap:8px;margin:6px 0 2px}
.lsc-bd-sess-h b{font:700 15px/1.2 Bitter,Georgia,serif}
.lsc-bd-sess-h .dt{font-size:12px;color:#6B7280}
.lsc-bd-sess-h .sc{margin-left:auto;font:800 15px/1 Bitter,Georgia,serif}
.lsc-bd-skins{font-size:13px;display:flex;justify-content:space-between;align-items:center;padding:7px 2px;border-top:1px solid #EEF0F2}
.lsc-bd-skins .h{font:700 11px/1 Bitter,Georgia,serif;text-transform:uppercase;color:#6B7280;letter-spacing:.5px}
.sk{font-weight:600}.sk.au{color:#BF5700}.sk.sa{color:#4B6274}.sk b{margin-left:6px;font:800 14px Bitter,Georgia,serif;color:#1B1B1B}
.evlb-seg{display:flex;border:1px solid #E5E7EB;border-radius:99px;overflow:hidden;background:#FFFFFF;padding:2px}
.evlb-seg a{flex:1;text-align:center;font:700 11px/1 Bitter,Georgia,serif;text-transform:uppercase;letter-spacing:.5px;color:#6B7280;padding:9px 0;border-radius:99px;text-decoration:none}
.evlb-seg a.active{background:#1B1B1B;color:#FFFFFF}
.evlb-seg.sub a.active{background:#E87C3E}
.pr-hiw-link{display:inline-flex;height:30px;align-items:center;padding:0 14px;border-radius:99px;background:#E87C3E;color:#FFFFFF;font:700 11px/1 Bitter,Georgia,serif;letter-spacing:1px;text-transform:uppercase;text-decoration:none;white-space:nowrap}
.lsc-sched{border:1px solid #E5E7EB;border-radius:12px;overflow:hidden;background:#FFFFFF}
.lsc-sched .d{display:flex;justify-content:space-between;gap:10px;padding:9px 12px;font-size:13.5px}
.lsc-sched .d:nth-child(even){background:#FBFAF8}
.lsc-sched .d dt{font:700 13.5px Bitter,Georgia,serif;margin:0}
.lsc-sched .d dd{margin:0;text-align:right;color:#4B5563}
.lsc-hiw-ul{margin:0;padding-left:18px;font-size:13.5px;line-height:1.5;color:#1B1B1B}
h4.sec{font:700 16px/1.2 Bitter,Georgia,serif;margin:10px 0 6px}
p.body{font-size:13.5px;line-height:1.5;margin:0;color:#1B1B1B}

```

## Landing — Cup landing · member Leaderboard

```html
<div class="ph">
  <div class="shell-member">
    <div class="row1"><div class="tgf-mark">F</div><div class="wordmark">The Golf Fellowship</div><a class="shell-cta-pill" href="#">Enter Events &amp; Contests</a></div>
    <div class="shell-member-tabs"><a href="#">Players</a><a href="#" class="active">Leaderboard</a><a href="#">Handicaps</a></div>
  </div>
  <div class="top-tabs"><a class="top-tab" href="#">Events <span class="evlb-beta">Beta</span></a><a class="top-tab" href="#">Points Races</a><a class="tab-pill active" href="Landing.dc.html">Lone Star Cup</a><a class="top-tab" href="#">Match Play</a></div>

  <div class="se-wrap" style="padding-top:12px;gap:10px">
    <div class="lsc-event">
      <div style="display:flex;align-items:center;gap:10px">
        <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.6" aria-hidden="true"><path d="M7 4h10v4a5 5 0 0 1-10 0V4z"/><path d="M7 6H4v2a3 3 0 0 0 3 3M17 6h3v2a3 3 0 0 1-3 3"/><path d="M12 13v4M9 20h6M10 17h4"/></svg>
        <div><div class="ttl">The Lone Star Cup</div><div class="sub">October 10–11, 2026 · The Hideout · Brownwood, TX</div></div>
      </div>
    </div>
    <div style="display:flex;justify-content:space-between;align-items:center"><a class="pr-hiw-link" href="EventInfo.dc.html">Event info</a><span class="lsc-chip">● Live · Sat AM</span></div>

    <div class="lsc-bd-head">
      <div class="t austin">Austin <span class="p">2</span></div>
      <div class="mid">28 points on the board</div>
      <div class="t sa"><span class="p">1</span> San Antonio</div>
    </div>
    <div class="lsc-bd-proj">With matches on the course: Austin 3 — 2 San Antonio<br>San Antonio holds the Cup and keeps it on a tie: 13 more to retain · Austin needs 12½ to win it.</div>

    <div class="lsc-bd-sess-h"><b>Sat AM Fourball</b><span class="dt">8:30 AM · live</span><span class="sc"><span style="color:#BF5700">2</span> — <span style="color:#4B6274">1</span></span></div>

    <div class="se-mcard">
      <div class="mp-match-meta"><span>Match 2 · Fourball · <span class="st">Your match</span></span><span class="live">Live · thru 5</span></div>
      <div class="se-mc-strip">
        <div class="se-mc-mono a">CC</div>
        <div class="se-mc-name"><em>Chris &amp; Matt</em><b>Cannon / Jenkins</b></div>
        <div class="se-mc-bar b">1 UP<small>thru 5</small></div>
        <div class="se-mc-name r"><em>Kerry &amp; Michael</em><b>Niester / Mesa</b></div>
        <div class="se-mc-mono b">KN</div>
      </div>
      <div class="se-mc-dots"><i class="se-hd b"></i><i class="se-hd h"></i><i class="se-hd a"></i><i class="se-hd b"></i><i class="se-hd h"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i></div>
      <div class="mp-open">› open card</div>
    </div>

    <div class="se-mcard">
      <div class="mp-match-meta"><span>Match 1 · Fourball</span><span class="live">Live · thru 7</span></div>
      <div class="se-mc-strip">
        <div class="se-mc-mono a">LY</div>
        <div class="se-mc-name"><em>Luke &amp; Neal</em><b>Youngs / Cloer</b></div>
        <div class="se-mc-bar b">2 UP<small>thru 7</small></div>
        <div class="se-mc-name r"><em>Pat &amp; Jeff</em><b>Youngs / Young</b></div>
        <div class="se-mc-mono b">PY</div>
      </div>
      <div class="se-mc-dots"><i class="se-hd b"></i><i class="se-hd a"></i><i class="se-hd b"></i><i class="se-hd h"></i><i class="se-hd b"></i><i class="se-hd h"></i><i class="se-hd b"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i></div>
      <div class="mp-open">› open card</div>
    </div>

    <div class="se-mcard">
      <div class="mp-match-meta"><span>Match 3 · Fourball</span><span>8:50 AM tee time</span></div>
      <div class="se-mc-strip">
        <div class="se-mc-mono a">JH</div>
        <div class="se-mc-name"><em>Jay &amp; Walter</em><b>Hogue / Hogue</b></div>
        <div class="se-mc-bar tie">AS</div>
        <div class="se-mc-name r"><em>Adam &amp; Luke</em><b>Baker / Mazanec</b></div>
        <div class="se-mc-mono b">AB</div>
      </div>
      <div class="mp-open">› open card</div>
    </div>
    <div class="se-mc-note">Updates every 20 s · Sat PM Foursomes and Sun Singles below</div>
  </div>
</div>
```

## SubNav — built already (#1366); omitted.

## Main — Scoring · Fourball hole screen

```html
<div class="ph">
  <div class="shell-slim"><div class="tgf-mark">F</div></div>
  <nav class="se-toggle"><div class="se-tg-in"><a href="Main.dc.html" class="on">Scoring<span class="se-tg-s">Hole 8</span></a><a href="Leaderboard.dc.html">Leaderboard</a></div></nav>

  <div class="se-wrap">
    <div>
      <div class="se-eyebrow">Sat AM Fourball · Group 1 · Match 1</div>
      <h1 class="se-h1">Hole 8</h1>
      <div class="se-sub">Par 4 · 388 yds · SI 3</div>
    </div>

    <div class="se-cup">
      <div class="lbl">Lone Star Cup</div>
      <div class="tm aus"><span class="nm">Austin<span class="proj">Fourball 2 · overall 2</span></span><b>2</b></div>
      <div class="tm sa"><span class="nm">San Antonio<span class="proj">Fourball 1 · overall 1</span></span><b>1</b></div>
    </div>

    <div class="se-mstrip">
      <div class="se-mcard">
        <div class="se-mc-strip">
          <div class="se-mc-mono a">LY</div>
          <div class="se-mc-name"><em>Luke &amp; Neal</em><b>Youngs / Cloer</b></div>
          <div class="se-mc-bar b">2 UP<small>thru 7</small></div>
          <div class="se-mc-name r"><em>Pat &amp; Jeff</em><b>Youngs / Young</b></div>
          <div class="se-mc-mono b">PY</div>
        </div>
        <div class="se-mc-dots"><i class="se-hd b"></i><i class="se-hd a"></i><i class="se-hd b"></i><i class="se-hd h"></i><i class="se-hd b"></i><i class="se-hd h"></i><i class="se-hd b"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i></div>
      </div>
    </div>

    <div class="se-stack">
      <div class="se-row"><span class="se-tee" style="background:#1F4E8C"></span>
        <div class="se-who"><div class="se-name">Pat Youngs</div><div class="se-meta">Blue · PH +3</div></div>
        <button class="se-minus" aria-label="minus">−</button>
        <div class="se-score"><span class="v">3</span><span class="r">Birdie</span></div>
        <button class="se-plus" aria-label="plus">+</button>
      </div>
      <div class="se-row"><span class="se-tee" style="background:#1F4E8C"></span>
        <div class="se-who"><div class="se-name">Jeff Young</div><div class="se-meta">Blue · PH 2</div></div>
        <button class="se-minus" aria-label="minus">−</button>
        <div class="se-score"><span class="v">5</span><span class="r">Bogey</span><div class="se-pops"><div class="g"><span class="se-pop t"></span></div></div></div>
        <button class="se-plus" aria-label="plus">+</button>
      </div>
      <div class="se-row"><span class="se-tee" style="background:#1F4E8C"></span>
        <div class="se-who"><div class="se-name">Luke Youngs</div><div class="se-meta">Blue · PH 0</div></div>
        <button class="se-minus" aria-label="minus">−</button>
        <div class="se-score"><span class="v">4</span><span class="r">Par</span></div>
        <button class="se-plus" aria-label="plus">+</button>
      </div>
      <div class="se-row"><span class="se-tee" style="background:#1F4E8C"></span>
        <div class="se-who"><div class="se-name">Neal Cloer</div><div class="se-meta">Blue · PH 2</div></div>
        <button class="se-minus" aria-label="minus">−</button>
        <div class="se-score"><span class="v se-x">X</span><span class="r">Picked up</span><div class="se-pops"><div class="g"><span class="se-pop t"></span></div></div></div>
        <button class="se-plus" aria-label="plus">+</button>
      </div>
    </div>

    <div class="se-box" style="display:flex;justify-content:space-between;align-items:center;padding:8px 14px">
      <div><div class="se-lbl">Team score · hole 8</div></div>
      <div style="display:flex;gap:14px;align-items:baseline"><span style="font:800 20px Bitter,Georgia,serif;color:#4B6274">SA 3</span><span style="font:800 20px Bitter,Georgia,serif;color:#BF5700">AUS 4</span></div>
    </div>

    <div class="se-lblrow"><span class="se-lbl">Group card</span><span class="se-keepnote"><!-- pencil icon -->You're keeping score</span></div>
    <div class="se-strip">
      <div class="se-cell saved"><span class="n">1</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">2</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">3</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">4</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">5</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">6</span><span class="k">✓</span></div><div class="se-cell waiting"><span class="n">7</span><span class="k">…</span></div><div class="se-cell cur"><span class="n">8</span></div><div class="se-cell"><span class="n">9</span></div>
      <div class="se-cell"><span class="n">10</span></div><div class="se-cell"><span class="n">11</span></div><div class="se-cell"><span class="n">12</span></div><div class="se-cell"><span class="n">13</span></div><div class="se-cell"><span class="n">14</span></div><div class="se-cell"><span class="n">15</span></div><div class="se-cell"><span class="n">16</span></div><div class="se-cell"><span class="n">17</span></div><div class="se-cell"><span class="n">18</span></div>
    </div>
    <div class="se-popkey"><span><span class="se-pop t"></span>Team match stroke</span><span><b style="font-family:Bitter,Georgia,serif">X</b> Picked up (the card keeps the triple)</span></div>
    <div style="text-align:center"><a class="pr-hiw-link" href="EventInfo.dc.html">How it works · Fourball</a></div>
  </div>

  <div class="se-bottom"><div class="se-row-act">
    <div class="se-nav"><button aria-label="Previous hole">‹</button></div>
    <button class="se-pill go">Save &amp; Go to Hole 9</button>
    <div class="se-nav"><button aria-label="Next hole">›</button></div>
  </div></div>
</div>
```

## ScoringFoursomes — Scoring · Foursomes (Chapman) hole screen

```html
<div class="ph">
  <div class="shell-slim"><div class="tgf-mark">F</div></div>
  <nav class="se-toggle"><div class="se-tg-in"><a href="ScoringFoursomes.dc.html" class="on">Scoring<span class="se-tg-s">Hole 12</span></a><a href="Leaderboard.dc.html">Leaderboard</a></div></nav>

  <div class="se-wrap">
    <div>
      <div class="se-eyebrow">Sat PM Foursomes · Group 3 · Match 3</div>
      <h1 class="se-h1">Hole 12</h1>
      <div class="se-sub">Par 5 · 521 yds · SI 1</div>
    </div>

    <div class="se-cup">
      <div class="lbl">Lone Star Cup</div>
      <div class="tm aus"><span class="nm">Austin<span class="proj">Foursomes 1 · overall 4</span></span><b>4</b></div>
      <div class="tm sa"><span class="nm">San Antonio<span class="proj">Foursomes 0 · overall 3</span></span><b>3</b></div>
    </div>

    <div class="se-mstrip">
      <div class="se-mcard">
        <div class="se-mc-strip">
          <div class="se-mc-mono a">DW</div>
          <div class="se-mc-name"><em>David &amp; John</em><b>Wetz / Wade</b></div>
          <div class="se-mc-bar tie">AS<small>thru 11</small></div>
          <div class="se-mc-name r"><em>Adam &amp; Luke</em><b>Baker / Mazanec</b></div>
          <div class="se-mc-mono b">AB</div>
        </div>
        <div class="se-mc-dots"><i class="se-hd a"></i><i class="se-hd h"></i><i class="se-hd b"></i><i class="se-hd h"></i><i class="se-hd a"></i><i class="se-hd b"></i><i class="se-hd h"></i><i class="se-hd h"></i><i class="se-hd b"></i><i class="se-hd a"></i><i class="se-hd h"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i></div>
      </div>
    </div>

    <div class="se-stack">
      <div class="se-row"><span class="se-tee" style="background:#1F4E8C"></span>
        <div class="se-who"><div class="se-name">Wetz / Wade</div><div class="se-meta">Team PH 9</div></div>
        <button class="se-minus" aria-label="minus">−</button>
        <div class="se-score"><span class="v">6</span><span class="r">Bogey</span><div class="se-pops"><div class="g"><span class="se-pop t"></span></div></div></div>
        <button class="se-plus" aria-label="plus">+</button>
      </div>
      <div class="se-row"><span class="se-tee" style="background:#1F4E8C"></span>
        <div class="se-who"><div class="se-name">Baker / Mazanec</div><div class="se-meta">Team PH 8</div></div>
        <button class="se-minus" aria-label="minus">−</button>
        <div class="se-score"><span class="v">5</span><span class="r">Par</span></div>
        <button class="se-plus" aria-label="plus">+</button>
      </div>
    </div>

    <div class="se-box" style="display:flex;justify-content:space-between;align-items:center;padding:8px 14px">
      <div><div class="se-lbl">Team score · hole 12</div></div>
      <div style="display:flex;gap:14px;align-items:baseline"><span style="font:800 20px Bitter,Georgia,serif;color:#BF5700">AUS 5</span><span style="font:800 20px Bitter,Georgia,serif;color:#4B6274">SA 5</span></div>
    </div>

    <div class="se-lblrow"><span class="se-lbl">Group card</span><span class="se-keepnote"><!-- pencil icon -->You're keeping score</span></div>
    <div class="se-strip">
      <div class="se-cell saved"><span class="n">1</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">2</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">3</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">4</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">5</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">6</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">7</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">8</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">9</span><span class="k">✓</span></div>
      <div class="se-cell saved"><span class="n">10</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">11</span><span class="k">✓</span></div><div class="se-cell cur"><span class="n">12</span></div><div class="se-cell"><span class="n">13</span></div><div class="se-cell"><span class="n">14</span></div><div class="se-cell"><span class="n">15</span></div><div class="se-cell"><span class="n">16</span></div><div class="se-cell"><span class="n">17</span></div><div class="se-cell"><span class="n">18</span></div>
    </div>
    <div class="se-popkey"><span><span class="se-pop t"></span>Team match stroke</span><span><b style="font-family:Bitter,Georgia,serif">X</b> Picked up (the card keeps the triple)</span></div>
    <div style="text-align:center"><a class="pr-hiw-link" href="EventInfo.dc.html">How it works · Foursomes</a></div>
  </div>

  <div class="se-bottom"><div class="se-row-act">
    <div class="se-nav"><button aria-label="Previous hole">‹</button></div>
    <button class="se-pill go">Save &amp; Go to Hole 13</button>
    <div class="se-nav"><button aria-label="Next hole">›</button></div>
  </div></div>
</div>
```

## ScoringSingles — Scoring · Singles hole screen

```html
<div class="ph">
  <div class="shell-slim"><div class="tgf-mark">F</div></div>
  <nav class="se-toggle"><div class="se-tg-in"><a href="ScoringSingles.dc.html" class="on">Scoring<span class="se-tg-s">Hole 10</span></a><a href="Leaderboard.dc.html">Leaderboard</a></div></nav>

  <div class="se-wrap">
    <div>
      <div class="se-eyebrow">Sun Singles · Group 2 · Matches 3 &amp; 4</div>
      <h1 class="se-h1">Hole 10</h1>
      <div class="se-sub">Par 4 · 402 yds · SI 6</div>
    </div>

    <div class="se-cup">
      <div class="lbl">Lone Star Cup</div>
      <div class="tm aus"><span class="nm">Austin<span class="proj">Singles · 7½ overall</span></span><b>7½</b></div>
      <div class="tm sa"><span class="nm">San Antonio<span class="proj">Singles · 7½ overall</span></span><b>7½</b></div>
    </div>

    <div class="se-mstrip">
      <div class="se-mcard">
        <div class="se-mc-strip">
          <div class="se-mc-mono a">CC</div>
          <div class="se-mc-name"><em>Chris</em><b>Cannon</b></div>
          <div class="se-mc-bar b">2 UP<small>thru 9</small></div>
          <div class="se-mc-name r"><em>Kerry</em><b>Niester</b></div>
          <div class="se-mc-mono b">KN</div>
        </div>
        <div class="se-mc-dots"><i class="se-hd b"></i><i class="se-hd h"></i><i class="se-hd a"></i><i class="se-hd b"></i><i class="se-hd h"></i><i class="se-hd a"></i><i class="se-hd h"></i><i class="se-hd b"></i><i class="se-hd b"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i></div>
      </div>
      <div class="se-mcard">
        <div class="se-mc-strip">
          <div class="se-mc-mono a">NC</div>
          <div class="se-mc-name"><em>Neal</em><b>Cloer</b></div>
          <div class="se-mc-bar a">1 UP<small>thru 9</small></div>
          <div class="se-mc-name r"><em>Michael</em><b>Mesa</b></div>
          <div class="se-mc-mono b">MM</div>
        </div>
        <div class="se-mc-dots"><i class="se-hd a"></i><i class="se-hd h"></i><i class="se-hd b"></i><i class="se-hd a"></i><i class="se-hd h"></i><i class="se-hd h"></i><i class="se-hd a"></i><i class="se-hd b"></i><i class="se-hd h"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i></div>
      </div>
    </div>

    <div class="se-stack">
      <div class="se-row"><span class="se-tee" style="background:#1F4E8C"></span>
        <div class="se-who"><div class="se-name">Kerry Niester</div><div class="se-meta">Blue · PH 1</div></div>
        <button class="se-minus" aria-label="minus">−</button>
        <div class="se-score"><span class="v empty">4</span></div>
        <button class="se-plus" aria-label="plus">+</button>
      </div>
      <div class="se-row"><span class="se-tee" style="background:#1F4E8C"></span>
        <div class="se-who"><div class="se-name">Chris Cannon</div><div class="se-meta">Blue · PH 8</div></div>
        <button class="se-minus" aria-label="minus">−</button>
        <div class="se-score"><span class="v empty">4</span><div class="se-pops"><div class="g"><span class="se-pop t"></span></div></div></div>
        <button class="se-plus" aria-label="plus">+</button>
      </div>
      <div class="se-row"><span class="se-tee" style="background:#1F4E8C"></span>
        <div class="se-who"><div class="se-name">Michael Mesa</div><div class="se-meta">Blue · PH 0</div></div>
        <button class="se-minus" aria-label="minus">−</button>
        <div class="se-score"><span class="v">4</span><span class="r">Par</span></div>
        <button class="se-plus" aria-label="plus">+</button>
      </div>
      <div class="se-row"><span class="se-tee" style="background:#1F4E8C"></span>
        <div class="se-who"><div class="se-name">Neal Cloer</div><div class="se-meta">Blue · PH 2</div></div>
        <button class="se-minus" aria-label="minus">−</button>
        <div class="se-score"><span class="v">5</span><span class="r">Bogey</span><div class="se-pops"><div class="g"><span class="se-pop t"></span></div></div></div>
        <button class="se-plus" aria-label="plus">+</button>
      </div>
    </div>

    <div class="se-lblrow"><span class="se-lbl">Group card</span><span class="se-keepnote"><!-- pencil icon -->You're keeping score</span></div>
    <div class="se-strip">
      <div class="se-cell saved"><span class="n">1</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">2</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">3</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">4</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">5</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">6</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">7</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">8</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">9</span><span class="k">✓</span></div>
      <div class="se-cell cur"><span class="n">10</span></div><div class="se-cell"><span class="n">11</span></div><div class="se-cell"><span class="n">12</span></div><div class="se-cell"><span class="n">13</span></div><div class="se-cell"><span class="n">14</span></div><div class="se-cell"><span class="n">15</span></div><div class="se-cell"><span class="n">16</span></div><div class="se-cell"><span class="n">17</span></div><div class="se-cell"><span class="n">18</span></div>
    </div>
    <div class="se-popkey"><span><span class="se-pop t"></span>Team match stroke</span><span><b style="font-family:Bitter,Georgia,serif">X</b> Picked up (the card keeps the triple)</span></div>
    <div style="text-align:center"><a class="pr-hiw-link" href="EventInfo.dc.html">How it works · Singles</a></div>
  </div>

  <div class="se-bottom"><div class="se-row-act">
    <div class="se-nav"><button aria-label="Previous hole">‹</button></div>
    <button class="se-pill go">Save &amp; Go to Hole 11</button>
    <div class="se-nav"><button aria-label="Next hole">›</button></div>
  </div></div>
</div>
```

## QRLanding — Scanned link · gate

```html
<div class="ph">
  <div class="shell-slim"><div class="tgf-mark">F</div></div>
  <div class="se-wrap" style="padding-top:22px;gap:14px">
    <div>
      <div class="se-eyebrow">Sat AM Fourball · Oct 10, 2026</div>
      <h1 class="se-h1" style="font-size:34px">Lone Star Cup</h1>
      <div class="se-sub">Group 2 · Match 2 · 18 holes</div>
    </div>
    <div class="se-box" style="background:#FFFFFF">
      <div class="se-lbl">This group</div>
      <div style="display:flex;justify-content:space-between;margin-top:6px;gap:10px">
        <div><div style="font:700 11px Bitter,Georgia,serif;text-transform:uppercase;letter-spacing:.5px;color:#4B6274">San Antonio</div><div style="font:600 16px Bitter,Georgia,serif;line-height:1.3">Kerry Niester<br>Michael Mesa</div></div>
        <div style="text-align:right"><div style="font:700 11px Bitter,Georgia,serif;text-transform:uppercase;letter-spacing:.5px;color:#BF5700">Austin</div><div style="font:600 16px Bitter,Georgia,serif;line-height:1.3">Chris Cannon<br>Matt Jenkins</div></div>
      </div>
    </div>
    <div class="se-status"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#15803D" stroke-width="2.2" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>Michael is already keeping score for this group.</div>
    <div class="se-stack" style="gap:10px">
      <a class="se-pill dark" href="WhoAreYou.dc.html">SCORE THIS GROUP</a>
      <a class="se-pill line" href="Leaderboard.dc.html">FOLLOW THE CUP</a>
    </div>
    <p class="se-copy" style="margin:0">One phone per group keeps the scores. Everyone else follows along on the Cup leaderboard, with this match open; following claims nothing. Take over only if Michael can't keep going.</p>
  </div>
</div>
```

## WhoAreYou — Who are you?

```html
<div class="ph">
  <div class="shell-slim"><div class="tgf-mark">F</div></div>
  <div class="se-wrap" style="padding-top:22px;gap:14px">
    <div>
      <div class="se-eyebrow">Sat AM Fourball · Group 2</div>
      <h1 class="se-h1" style="font-size:34px">Who are you?</h1>
      <div class="se-sub">The first person to start keeps score for the group.</div>
    </div>
    <div class="se-stack" style="gap:10px">
      <a class="se-name-btn" href="Main.dc.html">Kerry Niester<span class="m">PH 1</span></a>
      <a class="se-name-btn" href="Main.dc.html">Michael Mesa<span class="m">PH 0</span></a>
      <a class="se-name-btn" href="Main.dc.html">Chris Cannon<span class="m">PH 8</span></a>
      <a class="se-name-btn" href="Main.dc.html">Matt Jenkins<span class="m">PH 3</span></a>
    </div>
    <p class="se-copy" style="margin:0">Tap your name to keep the card. Your playing handicap is the locked one from the starter sheet. If someone already has the card you'll be asked before you take it over.</p>
    <a class="se-pill line" href="QRLanding.dc.html" style="height:50px;font-size:15px">Back</a>
  </div>
</div>
```

## Held — Group already held

```html
<div class="ph">
  <div class="shell-slim"><div class="tgf-mark">F</div></div>
  <div class="se-wrap" style="padding-top:22px;gap:14px">
    <div>
      <div class="se-eyebrow">Sat AM Fourball · Group 2</div>
      <h1 class="se-h1" style="font-size:34px">Michael is keeping score.</h1>
      <div class="se-sub">He has the card for this group, through hole 7.</div>
    </div>
    <div class="se-stack" style="gap:10px">
      <a class="se-pill line" href="Leaderboard.dc.html">Follow along</a>
      <a class="se-pill dark" href="Main.dc.html">Take over</a>
    </div>
    <p class="se-copy" style="margin:0">Take over only if Michael can't keep going. His holes stay saved; you pick up from the next one. There's no timeout and nothing happens by itself.</p>
    <div class="se-box"><div class="se-lbl">Saved so far</div>
      <div class="se-strip" style="margin-top:8px">
        <div class="se-cell saved"><span class="n">1</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">2</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">3</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">4</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">5</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">6</span><span class="k">✓</span></div><div class="se-cell saved"><span class="n">7</span><span class="k">✓</span></div><div class="se-cell"><span class="n">8</span></div><div class="se-cell"><span class="n">9</span></div>
      </div>
    </div>
  </div>
</div>
```

## Leaderboard — Cup board · collapsed

```html
<div class="ph">
  <div class="shell-slim"><div class="tgf-mark">F</div></div>
  <nav class="se-toggle"><div class="se-tg-in"><a href="ScoringFoursomes.dc.html">Scoring<span class="se-tg-s">Hole 12</span></a><a href="Leaderboard.dc.html" class="on">Leaderboard</a></div></nav>

  <div class="se-wrap" style="padding-top:12px;gap:8px">
    <div class="lsc-bd-head">
      <div class="t austin">Austin <span class="p">4</span></div>
      <div class="mid">28 points on the board</div>
      <div class="t sa"><span class="p">3</span> San Antonio</div>
    </div>
    <div class="lsc-bd-proj">With matches on the course: Austin 5 — 4 San Antonio</div>

    <div class="evlb-seg"><a href="#">Fourball</a><a href="#" class="active">Foursomes</a><a href="#">Singles</a></div>
    <div class="evlb-seg sub"><a href="Leaderboard.dc.html" class="active">Matches</a><a href="Skins.dc.html">Skins</a></div>

    <div class="lsc-bd-sess-h"><b>Sat PM Foursomes</b><span class="dt">1:30 PM · 6 on the course</span><span class="sc"><span style="color:#BF5700">1</span> — <span style="color:#4B6274">0</span></span></div>

    <div class="se-mcard">
      <div class="mp-match-meta"><span>Match 2 · Foursomes · <span class="st">Your match</span></span><span class="live">Live · thru 11</span></div>
      <div class="se-mc-strip">
        <div class="se-mc-mono a">CC</div>
        <div class="se-mc-name"><em>Chris &amp; Matt</em><b>Cannon / Jenkins</b></div>
        <div class="se-mc-bar b">1 UP<small>thru 11</small></div>
        <div class="se-mc-name r"><em>Kerry &amp; Michael</em><b>Niester / Mesa</b></div>
        <div class="se-mc-mono b">KN</div>
      </div>
      <div class="se-mc-dots"><i class="se-hd a"></i><i class="se-hd h"></i><i class="se-hd a"></i><i class="se-hd h"></i><i class="se-hd b"></i><i class="se-hd a"></i><i class="se-hd b"></i><i class="se-hd h"></i><i class="se-hd b"></i><i class="se-hd a"></i><i class="se-hd b"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i></div>
      <div class="mp-open">› open card</div>
    </div>

    <div class="se-mcard">
      <div class="mp-match-meta"><span>Match 1 · Foursomes</span><span class="live">Live · thru 12</span></div>
      <div class="se-mc-strip">
        <div class="se-mc-mono a">LY</div><div class="se-mc-name"><em>Luke &amp; Neal</em><b>Youngs / Cloer</b></div>
        <div class="se-mc-bar a">3 UP<small>thru 12</small></div>
        <div class="se-mc-name r"><em>Pat &amp; Jeff</em><b>Youngs / Young</b></div><div class="se-mc-mono b">PY</div>
      </div>
      <div class="mp-open">› open card</div>
    </div>

    <div class="se-mcard">
      <div class="mp-match-meta"><span>Match 3 · Foursomes</span><span class="live">Live · thru 11</span></div>
      <div class="se-mc-strip">
        <div class="se-mc-mono a">DW</div><div class="se-mc-name"><em>David &amp; John</em><b>Wetz / Wade</b></div>
        <div class="se-mc-bar tie">AS<small>thru 11</small></div>
        <div class="se-mc-name r"><em>Adam &amp; Luke</em><b>Baker / Mazanec</b></div><div class="se-mc-mono b">AB</div>
      </div>
      <div class="mp-open">› open card</div>
    </div>

    <div class="se-mcard won">
      <div class="mp-match-meta"><span>Match 4 · Foursomes</span><span class="st">Final</span></div>
      <div class="se-mc-strip">
        <div class="se-mc-mono a">JH</div><div class="se-mc-name"><em>Jay &amp; Walter</em><b>Hogue / Hogue</b></div>
        <div class="se-mc-bar a">2&amp;1<small>final</small></div>
        <div class="se-mc-name r"><em>Rob &amp; James</em><b>Callaway / Wilson</b></div><div class="se-mc-mono b">RC</div>
      </div>
      <div class="mp-open">› open card</div>
    </div>

    <div class="se-mcard">
      <div class="mp-match-meta"><span>Match 5 · Foursomes</span><span class="live">Live · thru 9</span></div>
      <div class="se-mc-strip">
        <div class="se-mc-mono a">KF</div><div class="se-mc-name"><em>Kyle &amp; Matt</em><b>Franz / Sharp</b></div>
        <div class="se-mc-bar b">2 UP<small>thru 9</small></div>
        <div class="se-mc-name r"><em>Gus &amp; Chuck</em><b>Vasquez / Fehlis</b></div><div class="se-mc-mono b">GV</div>
      </div>
      <div class="mp-open">› open card</div>
    </div>
    <div class="se-mc-note">Updates every 20 s · matches 6–7 below</div>
  </div>
</div>
```

## LeaderboardExpanded — Cup board · match open

```html
<div class="ph">
  <div class="shell-slim"><div class="tgf-mark">F</div></div>
  <nav class="se-toggle"><div class="se-tg-in"><a href="ScoringFoursomes.dc.html">Scoring<span class="se-tg-s">Hole 12</span></a><a href="Leaderboard.dc.html" class="on">Leaderboard</a></div></nav>

  <div class="se-wrap" style="padding-top:12px;gap:8px">
    <div class="lsc-bd-head">
      <div class="t austin">Austin <span class="p">4</span></div>
      <div class="mid">28 points on the board</div>
      <div class="t sa"><span class="p">3</span> San Antonio</div>
    </div>
    <div class="evlb-seg"><a href="#">Fourball</a><a href="#" class="active">Foursomes</a><a href="#">Singles</a></div>
    <div class="evlb-seg sub"><a href="Leaderboard.dc.html" class="active">Matches</a><a href="Skins.dc.html">Skins</a></div>
    <div class="lsc-bd-sess-h"><b>Sat PM Foursomes</b><span class="dt">1:30 PM</span><span class="sc"><span style="color:#BF5700">1</span> — <span style="color:#4B6274">0</span></span></div>

    <div class="se-mcard">
      <div class="mp-match-meta"><span>Match 2 · Foursomes · <span class="st">Your match</span></span><span class="live">Live · thru 11</span></div>
      <div class="se-mc-strip">
        <div class="se-mc-mono a">CC</div>
        <div class="se-mc-name"><em>Chris &amp; Matt</em><b>Cannon / Jenkins</b></div>
        <div class="se-mc-bar b">1 UP<small>thru 11</small></div>
        <div class="se-mc-name r"><em>Kerry &amp; Michael</em><b>Niester / Mesa</b></div>
        <div class="se-mc-mono b">KN</div>
      </div>
      <div class="se-mc-dots"><i class="se-hd a"></i><i class="se-hd h"></i><i class="se-hd a"></i><i class="se-hd h"></i><i class="se-hd b"></i><i class="se-hd a"></i><i class="se-hd b"></i><i class="se-hd h"></i><i class="se-hd b"></i><i class="se-hd a"></i><i class="se-hd b"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i><i class="se-hd e"></i></div>
      <div class="se-mc-grid">
        <table>
          <tr class="h"><th></th><th>1</th><th>2</th><th>3</th><th>4</th><th>5</th><th>6</th><th>7</th><th>8</th><th>9</th></tr>
          <tr class="p"><th>Par</th><td>4</td><td>5</td><td>3</td><td>4</td><td>4</td><td>3</td><td>5</td><td>4</td><td>5</td></tr>
          <tr><td><span class="se-mc-chip a">CC</span></td><td><span class="w a">3</span></td><td>5</td><td><span class="w a">3</span></td><td>4</td><td>5<span class="pp"><i></i></span></td><td><span class="w a">2</span></td><td>5<span class="pp"><i></i></span></td><td>5</td><td>5</td></tr>
          <tr><td><span class="se-mc-chip b">KN</span></td><td>4</td><td>5</td><td>4</td><td>4</td><td><span class="w b">4</span></td><td>3</td><td><span class="w b">4</span></td><td>5</td><td><span class="w b">4</span></td></tr>
        </table>
        <table>
          <tr class="h"><th></th><th>10</th><th>11</th><th>12</th><th>13</th><th>14</th><th>15</th><th>16</th><th>17</th><th>18</th></tr>
          <tr class="p"><th>Par</th><td>4</td><td>4</td><td>5</td><td>3</td><td>4</td><td>4</td><td>3</td><td>4</td><td>5</td></tr>
          <tr><td><span class="se-mc-chip a">CC</span></td><td><span class="w a">3</span><span class="pp"><i></i></span></td><td>5</td><td class="dim">·</td><td class="dim">·</td><td class="dim">·</td><td class="dim">·</td><td class="dim">·</td><td class="dim">·</td><td class="dim">·</td></tr>
          <tr><td><span class="se-mc-chip b">KN</span></td><td>4</td><td><span class="w b">4</span></td><td class="dim">·</td><td class="dim">·</td><td class="dim">·</td><td class="dim">·</td><td class="dim">·</td><td class="dim">·</td><td class="dim">·</td></tr>
        </table>
        <div class="se-mc-note">Circled: won the hole · dots: match strokes (Chapman 60/40, off the low team)</div>
      </div>
    </div>

    <div class="se-mcard">
      <div class="mp-match-meta"><span>Match 1 · Foursomes</span><span class="live">Live · thru 12</span></div>
      <div class="se-mc-strip">
        <div class="se-mc-mono a">LY</div><div class="se-mc-name"><em>Luke &amp; Neal</em><b>Youngs / Cloer</b></div>
        <div class="se-mc-bar a">3 UP<small>thru 12</small></div>
        <div class="se-mc-name r"><em>Pat &amp; Jeff</em><b>Youngs / Young</b></div><div class="se-mc-mono b">PY</div>
      </div>
      <div class="mp-open">› open card</div>
    </div>
    <div class="se-mc-note">Tap the head to close · stays open across the 20 s refresh</div>
  </div>
</div>
```

## Skins — Cup board · Skins pane

```html
<div class="ph">
  <div class="shell-slim"><div class="tgf-mark">F</div></div>
  <nav class="se-toggle"><div class="se-tg-in"><a href="ScoringFoursomes.dc.html">Scoring<span class="se-tg-s">Hole 12</span></a><a href="Leaderboard.dc.html" class="on">Leaderboard</a></div></nav>

  <div class="se-wrap" style="padding-top:12px;gap:8px">
    <div class="lsc-bd-head">
      <div class="t austin">Austin <span class="p">4</span></div>
      <div class="mid">28 points on the board</div>
      <div class="t sa"><span class="p">3</span> San Antonio</div>
    </div>
    <div class="evlb-seg"><a href="#">Fourball</a><a href="#" class="active">Foursomes</a><a href="#">Singles</a></div>
    <div class="evlb-seg sub"><a href="Leaderboard.dc.html">Matches</a><a href="Skins.dc.html" class="active">Skins</a></div>

    <div class="lsc-bd-sess-h"><b>Sat PM team skins</b><span class="dt">net · one flight · 1:30 PM</span></div>
    <div class="se-box" style="padding:4px 12px;background:#FFFFFF">
      <div class="lsc-bd-skins" style="border-top:0"><span class="h">Hole 2</span><span class="sk au">Youngs / Cloer <b>1</b></span></div>
      <div class="lsc-bd-skins"><span class="h">Hole 4</span><span class="sk sa">Youngs / Young <b>1</b></span></div>
      <div class="lsc-bd-skins"><span class="h">Hole 7</span><span class="sk au">Hogue / Hogue <b>1</b></span></div>
      <div class="lsc-bd-skins"><span class="h">Hole 8</span><span class="sk au">Hogue / Hogue <b>1</b></span></div>
      <div class="lsc-bd-skins"><span class="h">Hole 1 · 3 · 5 · 6 · 9 · 10 · 11</span><span style="color:#6B7280">Tied · no skin</span></div>
      <div class="lsc-bd-skins"><span class="h">Holes 12–18</span><span style="color:#9CA3AF">Open · 6 groups still on the course</span></div>
    </div>
    <div class="se-mc-note">Skins show as counts; TGF settles after the round. Team net on the one ball at the Chapman 60/40 allowance.</div>

    <div class="lsc-bd-sess-h" style="margin-top:10px"><b>Sat AM team skins</b><span class="dt">net · one flight · final</span></div>
    <div class="se-box" style="padding:4px 12px;background:#FFFFFF">
      <div class="lsc-bd-skins" style="border-top:0"><span class="h">Hole 3</span><span class="sk sa">Youngs / Young <b>1</b></span></div>
      <div class="lsc-bd-skins"><span class="h">Hole 12</span><span class="sk au">Cannon / Jenkins <b>1</b></span></div>
      <div class="lsc-bd-skins"><span class="h">Hole 13</span><span class="sk au">Cannon / Jenkins <b>1</b></span></div>
    </div>

    <div class="lsc-bd-sess-h" style="margin-top:10px"><b>Sun singles skins</b><span class="dt">gross · two flights · 8:30 AM</span></div>
    <div class="se-box" style="padding:10px 12px;background:#FFFFFF;display:flex;gap:12px">
      <div style="flex:1"><div class="se-lbl">Flight 1 · under 12.0</div><div style="font-size:12.5px;color:#4B5563;margin-top:3px">12 players · Pat Youngs to Wilson</div></div>
      <div style="flex:1"><div class="se-lbl">Flight 2 · 12.0 and up</div><div style="font-size:12.5px;color:#4B5563;margin-top:3px">10 players · Callaway to Rideout</div></div>
    </div>
    <div style="text-align:center;margin-top:4px"><a class="pr-hiw-link" href="EventInfo.dc.html">How skins work</a></div>
  </div>
</div>
```

## EventInfo — Event Info · Schedule, Teams, Formats

```html
<div class="ph" style="height:1500px">
  <div class="shell-member">
    <div class="row1"><div class="tgf-mark">F</div><div class="wordmark">The Golf Fellowship</div><a class="shell-cta-pill" href="#">Enter Events &amp; Contests</a></div>
    <div class="shell-member-tabs"><a href="#">Players</a><a href="#" class="active">Leaderboard</a><a href="#">Handicaps</a></div>
  </div>
  <div class="top-tabs"><a class="top-tab" href="#">Events <span class="evlb-beta">Beta</span></a><a class="top-tab" href="#">Points Races</a><a class="tab-pill active" href="Landing.dc.html">Lone Star Cup</a><a class="top-tab" href="#">Match Play</a></div>

  <div class="se-wrap" style="padding-top:12px;gap:10px">
    <div class="lsc-event">
      <div class="se-lbl" style="color:#FFFFFF;opacity:.85">Event information</div>
      <div class="ttl">The Lone Star Cup 2026</div>
      <div class="sub">Austin v San Antonio · October 9–11 · The Hideout Golf Club, Brownwood</div>
    </div>
    <div style="display:flex;justify-content:space-between;align-items:center"><a class="pr-hiw-link" href="#">Share link</a><a class="pr-hiw-link" href="#" style="background:#1B1B1B">Download PDF</a></div>

    <div class="evlb-seg"><a href="#" class="active">Schedule</a><a href="#">Teams</a><a href="#">Formats</a></div>
    <dl class="lsc-sched" style="margin:0">
      <div class="d"><dt>Fri · practice round</dt><dd>1:30–2:00 PM · 14 players</dd></div>
      <div class="d"><dt>Fri · dinner</dt><dd>Shirts issued · draw review</dd></div>
      <div class="d"><dt>Sat AM · Fourball</dt><dd>8:30 AM · every 10 min · 7 matches</dd></div>
      <div class="d"><dt>Sat PM · Foursomes</dt><dd>1:30 PM · every 10 min · 7 matches</dd></div>
      <div class="d"><dt>Sun · Singles</dt><dd>8:30 AM · every 10 min · 14 matches</dd></div>
      <div class="d"><dt>Sun · Cup presentation</dt><dd>After play</dd></div>
    </dl>
    <h4 class="sec">Shirts <span class="se-lbl" style="margin-left:6px">issued Friday dinner</span></h4>
    <dl class="lsc-sched" style="margin:0">
      <div class="d"><dt>Sat · Austin</dt><dd>White / light violet · grey bottoms</dd></div>
      <div class="d"><dt>Sat · San Antonio</dt><dd>Grey · navy bottoms</dd></div>
      <div class="d"><dt>Sun · Austin</dt><dd>Blue · khaki bottoms</dd></div>
      <div class="d"><dt>Sun · San Antonio</dt><dd>Purple · grey bottoms</dd></div>
    </dl>
    <p class="body" style="color:#4B5563;font-size:12.5px">Course: The Hideout, par 72 (37 / 35) on every tee · Blue · White · Red (65+) · Teal. Each group's scorecard and cart sign carry a QR code: one player scores, everyone else follows.</p>

    <div style="border-top:1px dashed #D1D5DB;margin:8px 0 2px"></div>
    <div class="evlb-seg"><a href="#">Schedule</a><a href="#" class="active">Teams</a><a href="#">Formats</a></div>
    <div style="display:flex;gap:12px">
      <div style="flex:1"><div style="font:700 12px Bitter,Georgia,serif;text-transform:uppercase;letter-spacing:.5px;color:#BF5700;border-bottom:2px solid #BF5700;padding-bottom:4px;margin-bottom:6px">Austin · Matt Jenkins (C)</div>
        <div style="font-size:13px;line-height:1.55">Cloer / J. Wade<br>Julius Jenkins / McDonnell<br>Jay Hogue / Walter Hogue<br>Franz / Sharp<br>L. Youngs / Cannon<br>Wetz / Barstow<br>Matt Jenkins / Mike Jenkins</div></div>
      <div style="flex:1"><div style="font:700 12px Bitter,Georgia,serif;text-transform:uppercase;letter-spacing:.5px;color:#4B6274;border-bottom:2px solid #4B6274;padding-bottom:4px;margin-bottom:6px">San Antonio · Rob Callaway (C)</div>
        <div style="font-size:13px;line-height:1.55">Pat Youngs / Jeff Young<br>Niester / Mesa<br>Baker / Mazanec<br>Callaway / Wilson<br>Vasquez / Fehlis<br>South / Mary Wade<br>Peterson / Rideout</div></div>
    </div>
    <p class="body" style="color:#4B5563;font-size:12.5px">Saturday pairs play both sessions. Low pool: the three lowest pairs on each team, drawn against each other; high pool: the other four. Sunday singles: low 7 and high 7 per team, drawn within each pool. Match draws: [POSTED AFTER THURSDAY'S DRAW]</p>

    <div style="border-top:1px dashed #D1D5DB;margin:8px 0 2px"></div>
    <div class="evlb-seg"><a href="#">Schedule</a><a href="#">Teams</a><a href="#" class="active">Formats</a></div>
    <dl class="lsc-sched" style="margin:0">
      <div class="d"><dt>Fourball</dt><dd>90% · off the low player in the match</dd></div>
      <div class="d"><dt>Foursomes (Chapman)</dt><dd>60% low + 40% high · off the low team</dd></div>
      <div class="d"><dt>Singles</dt><dd>100% · off the low player</dd></div>
      <div class="d"><dt>Points</dt><dd>1 per match · ½ each for a half · 28 total</dd></div>
      <div class="d"><dt>Ties</dt><dd>All square after 18 · no extra holes</dd></div>
      <div class="d"><dt>The Cup</dt><dd>14½ wins · SA retains at 14–14</dd></div>
    </dl>
    <h4 class="sec">Chapman relief rule</h4>
    <p class="body">Both partners tee off, then each plays one shot with the partner's ball. Only after those second shots does the team choose one ball and alternate. If a tee shot is lost, out of bounds, in a penalty area, or unplayable, the team may abandon that ball, or the partner may take TGF line-of-flight relief on it (one-stroke penalty, drop anywhere on the line of flight going back as far as desired) and play his shot with it; that shot is the team's third stroke on that ball. The ball carries the penalty, not the player.</p>
    <ol class="lsc-hiw-ul">
      <li>Both partners tee off (ball A, ball B).</li>
      <li>A lost, OB, penalty-area or unplayable tee ball: abandon it, or the partner drops it on its line of flight, one-stroke penalty.</li>
      <li>Each partner plays one shot with the other's ball: stroke 2 on a clean ball, stroke 3 on a dropped one.</li>
      <li>After both shots, pick one ball to finish the hole, whatever each lies.</li>
      <li>The partner who did not hit the chosen ball's last stroke plays next; alternate from there.</li>
      <li>Later lost or unplayable balls: same relief, played by whoever is up. The penalty never changes the order of play.</li>
    </ol>
    <h4 class="sec">Skins</h4>
    <dl class="lsc-sched" style="margin:0">
      <div class="d"><dt>Sat AM &amp; PM</dt><dd>Team · net · one flight · partners share</dd></div>
      <div class="d"><dt>Sunday</dt><dd>Individual · gross · two flights at 12.0</dd></div>
      <div class="d"><dt>Ties</dt><dd>No carryover · a tied low wins nothing</dd></div>
    </dl>
    <p class="body" style="color:#4B5563;font-size:12.5px">Saturday net uses the full session allowance (90% Fourball; 60/40 Chapman), not off-lowest. A pair with one buyer: the buyer takes the whole skin. A pair with no buyer is out of the hole and cannot tie one out.</p>
  </div>
</div>
```

## CartSign — Cart signs · cart_signs.html standard, team-themed

Board-local CSS:

```css
/* templates/cart_signs.html, unchanged in shape: letter portrait, two signs
   to a sheet, hairline where the paper is cut, two enormous Bitter names
   over one start line, score QR in the top-right corner, event footer.
   Lone Star Cup changes only the mark (the Cup logo for the TGF mark) and
   adds a team band so an Austin cart and a San Antonio cart read as such
   from across the staging area. */
*{box-sizing:border-box}
body{margin:0;background:#FFFFFF;color:#111;font-family:"Helvetica Neue",Arial,system-ui,sans-serif}
.page{width:816px;height:1056px;padding:.4in;background:#fff;display:grid;grid-template-rows:1fr 1fr;gap:.5in;position:relative}
.page::after{content:"";position:absolute;top:50%;left:.3in;right:.3in;border-top:1px solid #9CA3AF}
.sign{display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:6px 10px;position:relative}
.sign-logo{width:150px;height:150px;display:block;margin:0 auto 4px}
.team{font-family:Bitter,Georgia,serif;font-weight:700;font-size:15px;letter-spacing:4px;text-transform:uppercase;color:#fff;padding:6px 22px;border-radius:999px;margin:0 0 12px}
.aus .team{background:#BF5700}
.sa .team{background:#4B6274}
.names{width:100%}
.nm{font-family:Bitter,Georgia,serif;font-weight:700;font-size:62px;line-height:1.12;white-space:nowrap;overflow:hidden}
.start{font-family:Bitter,Georgia,serif;font-weight:700;font-size:41px;margin-top:16px;padding-top:13px;border-top:2px solid #111;width:78%;font-variant-numeric:tabular-nums}
.aus .start{border-top-color:#BF5700}
.sa .start{border-top-color:#4B6274}
.match{font-family:Bitter,Georgia,serif;font-weight:600;font-size:17px;color:#444;margin-top:8px}
.sign-foot{font-family:Bitter,Georgia,serif;font-weight:600;font-size:15px;color:#444;margin-top:11px}
.qr{position:absolute;top:4px;right:4px;width:.9in;text-align:center}
.qr svg{width:.9in;height:.9in;display:block;background:#fff}
.qr-copy{font-family:Bitter,Georgia,serif;font-weight:700;font-size:10px;line-height:1.2;margin-top:3px;letter-spacing:.3px}
```

```html
<div class="page">
  <div class="sign aus">
    <img class="sign-logo" src="./lsc-logo.png" alt="Lone Star Cup 2026">
    <div class="team">Austin</div>
    <div class="names"><div class="nm">Chris Cannon</div><div class="nm">Matt Jenkins</div></div>
    <div class="start">8:40 AM · Hole 1</div>
    <div class="match">Sat AM Fourball · Match 2 · v Niester / Mesa</div>
    <div class="qr">
      <!-- score QR svg (live: s.g.score_qr.svg) -->
      <div class="qr-copy">Scan to keep score</div>
    </div>
    <div class="sign-foot">Lone Star Cup 2026 · The Hideout Golf Club · Sat, Oct 10</div>
  </div>

  <div class="sign sa">
    <img class="sign-logo" src="./lsc-logo.png" alt="Lone Star Cup 2026">
    <div class="team">San Antonio</div>
    <div class="names"><div class="nm">Kerry Niester</div><div class="nm">Michael Mesa</div></div>
    <div class="start">8:40 AM · Hole 1</div>
    <div class="match">Sat AM Fourball · Match 2 · v Cannon / Jenkins</div>
    <div class="qr">
      <!-- score QR svg (live: s.g.score_qr.svg) -->
      <div class="qr-copy">Scan to keep score</div>
    </div>
    <div class="sign-foot">Lone Star Cup 2026 · The Hideout Golf Club · Sat, Oct 10</div>
  </div>
</div>
```
