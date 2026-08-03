// Shared hole-by-hole scorecard renderer (member portal: Handicaps page
// + /me). Builds from window.TGF_CARD_STYLE (tgf-standards.js) — THE
// universal card standard (Kerry 2026-08-03) — so it renders pixel-
// identical to the Contests drill-down cards and the live championship
// card. Templates must load tgf-standards.js before this file.
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
        // Nines render in PLAY order (Kerry 2026-08-03: the SA
        // championship teed off on the back) — first_hole >= 10 puts IN
        // above OUT, same rule as the Contests renderers
        if (((card.round || {}).first_hole || 1) >= 10) blocks.reverse();

        // Compact variant on phones: tighter cells, smaller type, and
        // abbreviated row labels so a full nine fits with minimal scrolling.
        // Physical-screen check catches desktop-site mode on phones too
        const compact = (window.matchMedia && window.matchMedia("(max-width: 640px)").matches)
            || (window.screen && Math.min(window.screen.width || 9999, window.screen.height || 9999) <= 640);
        const { td, lbl, fs, spanW, sectTop, sectBot, grey, info, dark, deco: decoFor } = window.TGF_CARD_STYLE(compact);
        const L = compact
            ? { yds: "YDS", gs: "GROSS", gp: "G PTS", ns: "NET", np: "N PTS", adj: "ADJ" }
            : { yds: "YARDS", gs: "GROSS SCORE", gp: "GROSS PTS", ns: "NET SCORE", np: "NET PTS", adj: "ADJ SCORE" };
        // ADJ row appears only when the WHS net-double-bogey cap actually
        // lowered a hole (Kerry 2026-07-14) — capped holes render orange so
        // you can see exactly where the handicap score diverges from gross.
        const anyCapped = holes.some(h =>
            h.strokes != null && h.adjusted_strokes != null && h.adjusted_strokes !== h.strokes);
        const netOf = h => (h.strokes == null ? null : h.strokes - (h.strokes_received || 0));

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
            const holeRow = hs.map(h => `<td style="${td}font-weight:700;${dark}">${h.hole_number}</td>`).join("");
            const parRow = hs.map(h => `<td style="${td}${info}">${h.par ?? ""}</td>`).join("");
            const ydsRow = hs.map(h => `<td style="${td}${info}">${h.yardage ?? ""}</td>`).join("");
            const siRow = hs.map(h => `<td style="${td}${info}opacity:.75;">${h.stroke_index ?? ""}</td>`).join("");
            // GROSS section (bold score + its points on the tinted band),
            // then NET section, each opened by a thick border
            const scRow = hs.map(h => scoreCell(h, sectTop + "font-weight:700;")).join("");
            const adjRow = !anyCapped ? "" : hs.map(h => {
                if (h.strokes == null || h.adjusted_strokes == null) return `<td style="${td}"></td>`;
                const hit = h.adjusted_strokes !== h.strokes;
                return `<td style="${td}${hit ? "color:#E87C3E;font-weight:700;" : "color:#94a3b8;"}">${h.adjusted_strokes}</td>`;
            }).join("");
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
            const totHead = `style="${td}font-weight:700;${dark}"`;
            const totADJ = `style="${td}font-weight:700;background:#f1f5f9;color:#E87C3E;"`;
            return `<table style="border-collapse:collapse;font-size:${fs};margin:0.25rem 0;">
                <tr><td style="${lbl}${dark}">HOLE</td>${holeRow}<td ${totHead}>${label}</td></tr>
                <tr><td style="${lbl}${info}">PAR</td>${parRow}<td ${tot}>${sum(hs, h => h.par) || ""}</td></tr>
                <tr><td style="${lbl}${info}">${L.yds}</td>${ydsRow}<td ${tot}>${sum(hs, h => h.yardage) || ""}</td></tr>
                <tr><td style="${lbl}${info}" title="Hole handicap ranking: 1 = hardest">HCP</td>${siRow}<td ${tot}></td></tr>
                <tr><td style="${lbl}${sectTop}font-weight:700;">${L.gs}</td>${scRow}<td ${totG}>${sum(hs, h => h.strokes) || ""}</td></tr>
                ${anyCapped ? `<tr><td style="${lbl}color:#E87C3E;" title="WHS net double bogey cap: par + 2 + strokes received. Orange holes were lowered for handicap purposes.">${L.adj}</td>${adjRow}<td ${totADJ}>${sum(hs, h => h.adjusted_strokes) || ""}</td></tr>` : ""}
                <tr><td style="${lbl}${grey}">${L.gp}</td>${gpRow}<td ${totGP}>${sumPts(hs, h => h.stableford_gross)}</td></tr>
                <tr><td style="${lbl}${sectTop}font-weight:700;">${L.ns}</td>${netRow}<td ${totN}>${sumPts(hs, netOf)}</td></tr>
                <tr><td style="${lbl}${grey}${sectBot}">${L.np}</td>${npRow}<td ${totNP}>${sumPts(hs, h => h.stableford_net)}</td></tr>
            </table>`;
        }).join("");

        // Gross/Net/Stableford totals already live in the grid's OUT/IN
        // columns — the note line carries only the derived extras
        const r = card.round || {}, dt = card.derived_totals || {};
        const bits = [];
        if (dt.adjusted_gross != null) bits.push(`Adj. gross <strong>${dt.adjusted_gross}</strong>`);
        if (dt.adjusted_gross != null && r.slope && r.rating != null) {
            bits.push(`Differential <strong>${((113 / r.slope) * (dt.adjusted_gross - r.rating)).toFixed(1)}</strong>`);
        }
        // Phones: plain-space separators (the &nbsp; glue defeats line
        // wrapping) and a hard viewport cap so the text always folds
        const sep = compact ? " · " : " &nbsp;·&nbsp; ";
        const noteW = compact ? "max-width:calc(100vw - 3rem);" : "";
        return `<div style="overflow-x:auto;max-width:calc(100vw - 2rem);">${tables}</div>
            <div style="font-size:${compact ? "0.7rem" : "0.8rem"};color:#334155;margin-top:0.25rem;${noteW}">${bits.join(sep)}</div>
            <div style="font-size:${compact ? "0.62rem" : "0.72rem"};color:#64748b;margin-top:0.15rem;${noteW}">
                ● = handicap stroke${sep}○ = plus stroke${sep}<span style="border:1.5px solid #dc2626;border-radius:50%;padding:0 4px;">n</span> under par &nbsp;
                <span style="border:1.5px solid #2563eb;padding:0 4px;">n</span> over par
            </div>`;
    }

    window.tgfRenderScorecard = renderScorecard;
    window.tgfFmtHcp = fmtHcp;
})();
