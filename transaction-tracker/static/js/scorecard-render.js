// Shared hole-by-hole scorecard renderer (member portal). Mirrors the
// Contests drill-down card (templates/contests.html prRenderScorecard) —
// keep visual changes in sync between the two until they are unified.
(function () {
    "use strict";

    function fmtHcp(v) {
        if (v == null) return "";
        return v < 0 ? `+${Math.abs(v) % 1 ? Math.abs(v).toFixed(1) : Math.abs(v)}` : `${v}`;
    }

    function renderScorecard(card) {
        const holes = card.holes || [];
        if (!holes.some(h => h.strokes != null)) {
            return '<span style="color:#64748b;">No hole data on this card.</span>';
        }
        const blocks = [];
        const front = holes.filter(h => h.hole_number <= 9);
        const back = holes.filter(h => h.hole_number > 9);
        if (front.some(h => h.strokes != null)) blocks.push(["OUT", front]);
        if (back.some(h => h.strokes != null)) blocks.push(["IN", back]);

        // Compact variant on phones: tighter cells, smaller type, and
        // abbreviated row labels so a full nine fits with minimal scrolling.
        // Physical-screen check catches desktop-site mode on phones too
        const compact = (window.matchMedia && window.matchMedia("(max-width: 640px)").matches)
            || (window.screen && Math.min(window.screen.width || 9999, window.screen.height || 9999) <= 640);
        const td = `padding:${compact ? "1px 1px" : "2px 6px"};text-align:center;border:1px solid #e2e8f0;min-width:${compact ? "1.1em" : "2em"};white-space:nowrap;`;
        const lbl = `padding:${compact ? "1px 2px" : "2px 8px"};border:1px solid #e2e8f0;font-weight:600;color:#475569;text-align:left;white-space:nowrap;`;
        const L = compact
            ? { yds: "YDS", gs: "GROSS", gp: "G PTS", ns: "NET", np: "N PTS" }
            : { yds: "YARDS", gs: "GROSS SCORE", gp: "GROSS PTS", ns: "NET SCORE", np: "NET PTS" };
        const fs = compact ? "0.58rem" : "0.8rem";
        const spanW = compact ? "1.08em" : "1.4em";
        const sectTop = "border-top:3px solid #0f172a;";
        const sectBot = "border-bottom:3px solid #0f172a;";
        const netOf = h => (h.strokes == null ? null : h.strokes - (h.strokes_received || 0));

        // Circle/square marks are vs-par symbols computed from tracker facts:
        // GROSS row uses vs_par, NET row uses net_vs_par
        const decoFor = d => {
            if (d == null) return "";
            if (d <= -2) return "border:1.5px solid #dc2626;border-radius:50%;box-shadow:0 0 0 2px #fff,0 0 0 3.5px #dc2626;";
            if (d === -1) return "border:1.5px solid #dc2626;border-radius:50%;";
            if (d === 1) return "border:1.5px solid #2563eb;";
            if (d >= 2) return "border:1.5px solid #2563eb;box-shadow:0 0 0 2px #fff,0 0 0 3.5px #2563eb;";
            return "";
        };
        const scoreCell = (h, extra) => {
            if (h.strokes == null) return `<td style="${td}${extra}"></td>`;
            return `<td style="${td}${extra}"><span style="display:inline-block;min-width:${spanW};line-height:${spanW};${decoFor(h.vs_par)}">${h.strokes}</span></td>`;
        };
        // stroke dots live on the NET row (they're what turns gross into
        // net), pinned to the cell corner so they never displace the number
        const strokeDots = h => {
            const sr = h.strokes_received || 0;
            return sr
                ? `<span style="position:absolute;top:0;right:1px;font-size:0.55em;line-height:1.4;color:#334155;">${(sr > 0 ? "●" : "○").repeat(Math.abs(sr))}</span>`
                : "";
        };
        const sum = (hs, f) => hs.reduce((a, h) => a + (f(h) || 0), 0);
        const sumPts = (hs, f) => {
            let any = false, t = 0;
            hs.forEach(h => { const v = f(h); if (v != null) { any = true; t += v; } });
            return any ? t : "";
        };

        const tables = blocks.map(([label, hs]) => {
            const holeRow = hs.map(h => `<td style="${td}font-weight:700;background:#111;color:#fff;">${h.hole_number}</td>`).join("");
            const parRow = hs.map(h => `<td style="${td}">${h.par ?? ""}</td>`).join("");
            const ydsRow = hs.map(h => `<td style="${td}">${h.yardage ?? ""}</td>`).join("");
            const siRow = hs.map(h => `<td style="${td}color:#64748b;">${h.stroke_index ?? ""}</td>`).join("");
            // GROSS section (bold score + its points on a grey band), then
            // NET section, each opened by a thick border
            const grey = "background:#eef2f7;color:#475569;";
            const scRow = hs.map(h => scoreCell(h, sectTop + "font-weight:700;")).join("");
            const gpRow = hs.map(h => `<td style="${td}${grey}">${h.stableford_gross ?? ""}</td>`).join("");
            const netRow = hs.map(h => {
                const n = netOf(h);
                if (n == null) return `<td style="${td}${sectTop}"></td>`;
                return `<td style="${td}${sectTop}font-weight:700;position:relative;">${strokeDots(h)}<span style="display:inline-block;min-width:${spanW};line-height:${spanW};${decoFor(h.net_vs_par)}">${n}</span></td>`;
            }).join("");
            const npRow = hs.map(h => `<td style="${td}${grey}${sectBot}">${h.stableford_net ?? ""}</td>`).join("");
            const tot = `style="${td}font-weight:700;background:#f1f5f9;"`;
            const totG = `style="${td}${sectTop}font-weight:700;background:#f1f5f9;"`;
            const totGP = `style="${td}${grey}font-weight:600;"`;
            const totN = `style="${td}${sectTop}font-weight:700;background:#f1f5f9;"`;
            const totNP = `style="${td}${grey}${sectBot}font-weight:600;"`;
            const totHead = `style="${td}font-weight:700;background:#111;color:#fff;"`;
            return `<table style="border-collapse:collapse;font-size:${fs};margin:0.25rem 0;">
                <tr><td style="${lbl}background:#111;color:#fff;">HOLE</td>${holeRow}<td ${totHead}>${label}</td></tr>
                <tr><td style="${lbl}">PAR</td>${parRow}<td ${tot}>${sum(hs, h => h.par) || ""}</td></tr>
                <tr><td style="${lbl}">${L.yds}</td>${ydsRow}<td ${tot}>${sum(hs, h => h.yardage) || ""}</td></tr>
                <tr><td style="${lbl}" title="Hole handicap ranking: 1 = hardest">HCP</td>${siRow}<td ${tot}></td></tr>
                <tr><td style="${lbl}${sectTop}font-weight:700;">${L.gs}</td>${scRow}<td ${totG}>${sum(hs, h => h.strokes) || ""}</td></tr>
                <tr><td style="${lbl}${grey}">${L.gp}</td>${gpRow}<td ${totGP}>${sumPts(hs, h => h.stableford_gross)}</td></tr>
                <tr><td style="${lbl}${sectTop}font-weight:700;">${L.ns}</td>${netRow}<td ${totN}>${sumPts(hs, netOf)}</td></tr>
                <tr><td style="${lbl}${grey}${sectBot}">${L.np}</td>${npRow}<td ${totNP}>${sumPts(hs, h => h.stableford_net)}</td></tr>
            </table>`;
        }).join("");

        const r = card.round || {}, dt = card.derived_totals || {};
        const bits = [];
        if (r.gross != null) bits.push(`Gross <strong>${r.gross}</strong>`);
        if (r.net != null) bits.push(`Net <strong>${r.net}</strong>${r.playing_handicap != null ? ` (HCP ${fmtHcp(r.playing_handicap)})` : ""}`);
        if (dt.stableford_net != null) bits.push(`Stableford ${dt.stableford_net} net / ${dt.stableford_gross} gross`);
        return `<div style="overflow-x:auto;max-width:calc(100vw - 2rem);">${tables}</div>
            <div style="font-size:${compact ? "0.7rem" : "0.8rem"};color:#334155;margin-top:0.25rem;">${bits.join(" &nbsp;·&nbsp; ")}</div>
            <div style="font-size:${compact ? "0.62rem" : "0.72rem"};color:#64748b;margin-top:0.15rem;">
                ● = handicap stroke received &nbsp;·&nbsp; ○ = stroke given back (plus handicap) &nbsp;·&nbsp;
                <span style="border:1.5px solid #dc2626;border-radius:50%;padding:0 4px;">n</span> under par &nbsp;
                <span style="border:1.5px solid #2563eb;padding:0 4px;">n</span> over par (doubled = by 2+) —
                gross row vs par, net row vs net
            </div>`;
    }

    window.tgfRenderScorecard = renderScorecard;
    window.tgfFmtHcp = fmtHcp;
})();
