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

        const td = "padding:2px 6px;text-align:center;border:1px solid #e2e8f0;min-width:2em;";
        const lbl = "padding:2px 8px;border:1px solid #e2e8f0;font-weight:600;color:#475569;text-align:left;white-space:nowrap;";
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
            const deco = decoFor(h.vs_par);
            const sr = h.strokes_received || 0;
            const dots = sr
                ? `<span style="font-size:0.6em;vertical-align:super;color:#334155;">${(sr > 0 ? "●" : "○").repeat(Math.abs(sr))}</span>`
                : "";
            return `<td style="${td}${extra}"><span style="display:inline-block;min-width:1.4em;line-height:1.4em;${deco}">${h.strokes}</span>${dots}</td>`;
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
            const scRow = hs.map(h => scoreCell(h, sectTop + "font-weight:700;")).join("");
            const netRow = hs.map(h => {
                const n = netOf(h);
                if (n == null) return `<td style="${td}${sectBot}"></td>`;
                return `<td style="${td}${sectBot}"><span style="display:inline-block;min-width:1.4em;line-height:1.4em;${decoFor(h.net_vs_par)}">${n}</span></td>`;
            }).join("");
            const npRow = hs.map(h => `<td style="${td}">${h.stableford_net ?? ""}</td>`).join("");
            const gpRow = hs.map(h => `<td style="${td}color:#64748b;">${h.stableford_gross ?? ""}</td>`).join("");
            const tot = `style="${td}font-weight:700;background:#f1f5f9;"`;
            const totG = `style="${td}${sectTop}font-weight:700;background:#f1f5f9;"`;
            const totN = `style="${td}${sectBot}font-weight:700;background:#f1f5f9;"`;
            const totHead = `style="${td}font-weight:700;background:#111;color:#fff;"`;
            return `<table style="border-collapse:collapse;font-size:0.8rem;margin:0.25rem 0;">
                <tr><td style="${lbl}background:#111;color:#fff;">HOLE</td>${holeRow}<td ${totHead}>${label}</td></tr>
                <tr><td style="${lbl}">PAR</td>${parRow}<td ${tot}>${sum(hs, h => h.par) || ""}</td></tr>
                <tr><td style="${lbl}">YARDS</td>${ydsRow}<td ${tot}>${sum(hs, h => h.yardage) || ""}</td></tr>
                <tr><td style="${lbl}" title="Hole handicap ranking: 1 = hardest">HCP</td>${siRow}<td ${tot}></td></tr>
                <tr><td style="${lbl}${sectTop}font-weight:700;">GROSS SCORE</td>${scRow}<td ${totG}>${sum(hs, h => h.strokes) || ""}</td></tr>
                <tr><td style="${lbl}${sectBot}">NET SCORE</td>${netRow}<td ${totN}>${sumPts(hs, netOf)}</td></tr>
                <tr><td style="${lbl}">NET PTS</td>${npRow}<td ${tot}>${sumPts(hs, h => h.stableford_net)}</td></tr>
                <tr><td style="${lbl}color:#64748b;">GROSS PTS</td>${gpRow}<td ${tot}>${sumPts(hs, h => h.stableford_gross)}</td></tr>
            </table>`;
        }).join("");

        const r = card.round || {}, dt = card.derived_totals || {};
        const bits = [];
        if (r.gross != null) bits.push(`Gross <strong>${r.gross}</strong>`);
        if (r.net != null) bits.push(`Net <strong>${r.net}</strong>${r.playing_handicap != null ? ` (HCP ${fmtHcp(r.playing_handicap)})` : ""}`);
        if (dt.stableford_net != null) bits.push(`Stableford ${dt.stableford_net} net / ${dt.stableford_gross} gross`);
        return `<div style="overflow-x:auto;">${tables}</div>
            <div style="font-size:0.8rem;color:#334155;margin-top:0.25rem;">${bits.join(" &nbsp;·&nbsp; ")}</div>
            <div style="font-size:0.72rem;color:#64748b;margin-top:0.15rem;">
                ● = handicap stroke received &nbsp;·&nbsp; ○ = stroke given back (plus handicap) &nbsp;·&nbsp;
                <span style="border:1.5px solid #dc2626;border-radius:50%;padding:0 4px;">n</span> under par &nbsp;
                <span style="border:1.5px solid #2563eb;padding:0 4px;">n</span> over par (doubled = by 2+) —
                gross row vs par, net row vs net
            </div>`;
    }

    window.tgfRenderScorecard = renderScorecard;
    window.tgfFmtHcp = fmtHcp;
})();
