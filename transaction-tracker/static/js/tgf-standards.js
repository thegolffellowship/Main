// TGF UNIVERSAL DISPLAY STANDARDS (Kerry-ratified 2026-08-03).
//
// 1. TGF_CARD_STYLE — THE hole-by-hole card standard. Every scorecard
//    grid in the app (Contests drill-down event cards, the live City
//    Championship card, the member Handicaps page cards, /me) builds
//    from this one function. "That card standard should be the
//    universal standard moving forward, so that if we make a change to
//    the look of it, it will change universally." Change values HERE,
//    never inline in a renderer.
//
// 2. TGF_STAT_COL — THE stat-column standard for leaderboard tables:
//    110px desktop / 50px compact, centered, 6px horizontal padding
//    ("POINTS RESET is the one to follow... It's 6 right?" — and where
//    two columns disagreed on width, "the wider of the two dictates").
//    Callers append borders/weights/colors on top of the base.
//
// Load this file BEFORE points-render.js / scorecard-render.js.
(function () {
    "use strict";

    window.TGF_CARD_STYLE = function (compact) {
        return {
            td: `padding:${compact ? "1px 1px" : "2px 6px"};text-align:center;border:1px solid #e2e8f0;min-width:${compact ? "1.1em" : "2em"};white-space:nowrap;`,
            lbl: `padding:${compact ? "1px 2px" : "2px 8px"};border:1px solid #e2e8f0;font-weight:600;color:#475569;text-align:left;white-space:nowrap;`,
            fs: compact ? "0.58rem" : "0.8rem",
            spanW: compact ? "1.08em" : "1.4em",
            // thick borders open the GROSS and NET score sections
            sectTop: "border-top:2px solid #1B1B1B;",
            sectBot: "border-bottom:2px solid #1B1B1B;",
            // tinted band under the points rows
            grey: "background:#EFF4FF;color:#1D4ED8;",
            // course-fact rows (PAR / YARDS / HCP) render info-blue
            info: "color:#1D4ED8;",
            // the HOLE header band + OUT/IN total header
            dark: "background:#1B1B1B;color:#fff;",
            // classic vs-par marks: red circle birdie (double ring
            // eagle+), blue square bogey (double square double+)
            deco: function (d) {
                if (d == null) return "";
                if (d <= -2) return "border:1.5px solid #dc2626;border-radius:50%;box-shadow:0 0 0 2px #fff,0 0 0 3.5px #dc2626;";
                if (d === -1) return "border:1.5px solid #dc2626;border-radius:50%;";
                if (d === 1) return "border:1.5px solid #2563eb;";
                if (d >= 2) return "border:1.5px solid #2563eb;box-shadow:0 0 0 2px #fff,0 0 0 3.5px #2563eb;";
                return "";
            },
        };
    };

    window.TGF_STAT_COL = function (compact) {
        return `width:${compact ? "50px" : "110px"};text-align:center;padding-left:6px;padding-right:6px;`;
    };
})();
