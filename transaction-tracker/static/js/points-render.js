// Shared Points Races renderers: the three-level drill-down used by the
// Contests page (Points Races) and the Customers page (Points tab) —
// points-detail tables (DATE | EVENT | PTS | POS), rounds lists, and the
// hole-by-hole scorecard grid, plus their formatting helpers. Injects its
// own table CSS so host pages don't need the Contests stylesheet.
// (scorecard-render.js is the member-portal twin of prRenderScorecard —
// keep visual changes in sync until they are unified.)
(function () {
    "use strict";

    if (!document.getElementById("points-render-css")) {
        const st = document.createElement("style");
        st.id = "points-render-css";
        st.textContent = `
        .enrollment-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
        /* v2.56.1 (contests-handicaps-071026): Bitter hairline headers,
           soft dividers, tabular data — ratified typography rule #44 */
        .enrollment-table th {
            text-align: left; font: 700 10px/1.3 'Bitter', serif;
            letter-spacing: 1px; color: #9CA3AF; text-transform: uppercase;
            padding: 0.55rem 0.75rem 0.45rem; border-bottom: 1px solid var(--border);
        }
        .enrollment-table td {
            padding: 0.42rem 0.75rem; border-bottom: 1px solid #F3F2EF;
            font-variant-numeric: tabular-nums;
        }
        /* dashboard.css sets a GLOBAL tbody td { white-space: nowrap } — no
           table text can wrap unless a cell opts in via pr-wrap.
           Safari ignores overflow-wrap in table cells; word-break works */
        .enrollment-table td.pr-wrap {
            white-space: normal;
            overflow-wrap: anywhere;
            word-break: break-word;
        }
        @media (hover: hover) {
            .enrollment-table tbody tr:hover { background: var(--row-hover); }
        }
        .enrollment-table.pr-compact { font-size: 0.78rem; table-layout: fixed; }
        .enrollment-table.pr-compact th {
            padding: 0.3rem 0.25rem; font-size: 9px; letter-spacing: 0.5px;
        }
        .enrollment-table.pr-compact td { padding: 0.3rem 0.25rem; }
        /* Wide injected tables scroll inside their own container instead of
           widening the page (mobile audit wave 1 — body is overflow-x:clip,
           so an unwrapped wide table would be unreachable, not a slider). */
        .pr-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }`;
        document.head.appendChild(st);
    }

    function escapeHtml(s) {
        if (s == null) return '';
        return String(s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    // Phones get compact standings + scorecard variants. The physical-screen
    // check catches desktop-site mode, where the media query reports wide
    function prIsCompact() {
        return (window.matchMedia && window.matchMedia("(max-width: 640px)").matches)
            || (window.screen && Math.min(window.screen.width || 9999, window.screen.height || 9999) <= 640);
    }

    // Desktop: "2026-05-16" -> "May 16"; phones get the tighter "5/16"
    const PR_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    function prFmtAwardDate(v, short) {
        const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(v || "").trim());
        if (!m) return String(v || "");
        return short ? `${+m[2]}/${+m[3]}` : `${PR_MONTHS[+m[2] - 1]} ${+m[3]}`;
    }

    // A 9-hole round at a multi-nine facility gets its nine appended to
    // the event label ("s9.14 Hill Country" -> "… - Oaks"): the nine rides
    // in the imported course name ("… - OAKS"). Single short word only, so
    // annotated course names (archived markers etc.) never leak through.
    // Event-MVP badges (self-computed via /api/scoring/rounds flags): amber
    // City MVP (one per city per event) and teal TGF MVP. A tied result
    // (Kerry rule: points, then Net, then Gross — still tied = split) shows
    // "Co-MVP" / "Co-TGF MVP" instead of the sole title.
    function prMvpBadges(round) {
        const pill = (label, bg) =>
            ` <span style="background:${bg};color:#fff;font-size:0.62em;font-weight:700;padding:1px 4px;border-radius:3px;letter-spacing:0.03em;white-space:nowrap;vertical-align:1px;">${label}</span>`;
        if (!round) return "";
        let out = "";
        if (round.co_mvp) out += pill("Co-MVP", "#f59e0b");
        else if (round.mvp) out += pill("MVP", "#f59e0b");
        if (round.co_tgf_mvp) out += pill("Co-TGF MVP", "#0f766e");
        else if (round.tgf_mvp) out += pill("TGF MVP", "#0f766e");
        return out;
    }

    // Phones: badges drop to their own line under the event name — unless
    // the name is long enough to wrap already, then they stay inline at
    // the end (length heuristic; true wrap isn't knowable at render time)
    function prBadgeLayout(badges, text, compact) {
        if (!badges) return "";
        return compact && String(text || "").length <= 28
            ? `<span style="display:block;margin-top:1px;">${badges.replace(/^\s+/, "")}</span>`
            : badges;
    }

    function prNineSuffix(evt, round) {
        if (!round || /\b(front|back)\b/i.test(evt)) return "";
        const cn = String(round.course_name || "").trim();
        let nine = null;
        if (/^[A-Za-z]{3,10}$/.test(cn)) nine = cn;              // "Oaks"
        else {
            const m = /\s[-–—]\s([A-Za-z]{3,10})$/.exec(cn);     // "… - VALLEY"
            if (m) nine = m[1];
        }
        if (nine && !evt.toLowerCase().includes(nine.toLowerCase()))
            return " - " + nine.charAt(0).toUpperCase() + nine.slice(1).toLowerCase();
        // 18-hole venue, one nine played: the hole range says which nine
        // (holes 10-18 = Back). League rounds (HCM) play true 9-hole
        // nines — no front/back there.
        if (round.holes_played === 9 && round.first_hole != null && !round.gg_league_round_id)
            return round.first_hole >= 10 ? " - Back" : " - Front";
        return "";
    }

    // Phone display of GG event names: ALL-CAPS runs become Title Case
    // (KISSING TREE -> Kissing Tree; short tokens like TPC stay acronyms)
    // and the chapter prefix abbreviates (San Antonio Kickoff -> SA Kickoff).
    // Display-only — scorecard matching always uses the raw name.
    // Mobile course names drop venue boilerplate (v2.56.4, Kerry) —
    // mirrors derive_course_short_name() in database.py; keep in sync.
    function prShortCourse(n) {
        let out = String(n || "").trim()
            .replace(/^\s*(the\s+)?(club|course)\s+at\s+/i, "")
            .replace(/^\s*hyatt\s+(regency\s+)?/i, "");
        for (let i = 0; i < 2; i++) {
            out = out.replace(/\s+(golf\s+(club|course|resort|links)|country\s+club|golf\s*&\s*country\s+club|resort(\s*&\s*spa)?|ranch\s+resort|golf|club)\s*$/i, "");
        }
        out = out.replace(/^[\s\-|\u2013\u2014]+|[\s\-|\u2013\u2014]+$/g, "");
        return out || n;
    }

    function prPrettyEvent(name) {
        return String(name || "")
            .replace(/\b[A-Z][A-Z'&-]{2,}\b/g, w => /^(TPC|TGF|HCM)$/.test(w) ? w : w.charAt(0) + w.slice(1).toLowerCase())
            .replace(/\bSan Antonio\b/gi, "SA");
    }

    // ── Imported scorecards inside the player drill-down ──
    // /api/scoring/rounds rows → compact list; clicking a row lazy-loads
    // /api/scoring/scorecard/<id> and renders the classic hole-by-hole grid.

    function prRenderScoreRounds(rounds, opts = {}) {
        if (!rounds || !rounds.length) return "";
        const secTitle = opts.title || "NON-POINTS EVENTS";
        const secNote = opts.explainer !== undefined ? opts.explainer
            : "— rounds with no points line in this race; click a row for hole-by-hole";
        // Phones fold Course/Tee into a muted second line under the event
        // and shorten the date so all the numeric columns stay on screen
        const compact = prIsCompact();
        const rows = rounds.map(r => {
            const tee = (r.tee_name || "").replace(/^\d+\s*-\s*/, "");
            const course = [compact ? prShortCourse(r.course_name) : r.course_name, tee].filter(Boolean).join(" — ");
            const sr = [r.slope != null ? `slope ${r.slope}` : null,
                        r.rating != null ? `rating ${r.rating}` : null].filter(Boolean).join(", ");
            const dateTxt = prFmtAwardDate(r.round_date, compact);
            const courseCell = compact
                ? (course ? `<span style="display:block;color:var(--text-muted);font-size:0.85em;" title="${escapeHtml(sr)}">${escapeHtml(course)}</span>` : "")
                : "";
            return `<tr data-srid="${r.id}" style="cursor:pointer;" title="Click for the hole-by-hole scorecard">
                <td style="white-space:nowrap;">${escapeHtml(dateTxt)}</td>
                <td class="pr-wrap"><span class="pr-sc-chev" style="color:var(--primary);font-size:0.85rem;">&#9656;</span> ${escapeHtml((compact ? prPrettyEvent(r.event_name || "") : (r.event_name || "")).replace(/[–—]/g, "-"))}${prBadgeLayout(prMvpBadges(r), r.event_name, compact)}${courseCell}</td>
                ${compact ? "" : `<td>${escapeHtml(course)}${sr ? ` <span style="color:var(--text-muted);font-size:0.8em;">(${escapeHtml(sr)})</span>` : ""}</td>`}
                <td style="text-align:center;">${r.holes_played ?? ""}</td>
                <td style="text-align:center;">${prFmtHcp(r.playing_handicap)}</td>
                <td style="text-align:center;font-weight:700;">${r.gross ?? ""}</td>
                <td style="text-align:center;">${r.net ?? ""}</td>
            </tr>`;
        }).join("");
        return `<div style="margin-top:0.7rem;">
            <div style="font-weight:700;font-size:0.8rem;letter-spacing:0.04em;color:#334155;margin-bottom:0.25rem;">
                ${secTitle}${compact || !secNote ? "" : ` <span style="font-weight:400;color:var(--text-muted);">${secNote}</span>`}
            </div>
            <div class="pr-scroll">
            <table class="enrollment-table${compact ? " pr-compact" : ""}" style="margin:0;font-size:${compact ? "0.72rem" : "0.82rem"};">
                <thead><tr>
                    <th${compact ? ' style="width:36px;"' : ""}>Date</th><th>Event</th>
                    ${compact ? "" : "<th>Course / Tee</th>"}
                    <th style="text-align:center;${compact ? "width:20px;" : ""}" title="Holes played">${compact ? "H" : "Holes"}</th>
                    <th style="text-align:center;${compact ? "width:28px;" : ""}">HCP</th>
                    <th style="text-align:center;${compact ? "width:24px;" : ""}" title="Gross">${compact ? "G" : "Gross"}</th>
                    <th style="text-align:center;${compact ? "width:24px;" : ""}" title="Net">${compact ? "N" : "Net"}</th>
                </tr></thead>
                <tbody>${rows}</tbody>
            </table>
            </div>
        </div>`;
    }

    function prBindScorecardToggles(root) {
        // Any row carrying data-srid (a points line matched to an imported
        // round, or a fallback-list row) expands its scorecard in place
        root.querySelectorAll("tr[data-srid]").forEach(row => {
            row.addEventListener("click", async ev => {
                ev.stopPropagation();
                const chev = row.querySelector(".pr-sc-chev");
                const next = row.nextElementSibling;
                if (next && next.classList.contains("pr-sc-detail")) {
                    next.remove();
                    if (chev) chev.innerHTML = "&#9656;";
                    return;
                }
                const det = document.createElement("tr");
                det.className = "pr-sc-detail";
                det.innerHTML = `<td colspan="${row.children.length}" class="pr-wrap" style="background:#fff;padding:${prIsCompact() ? "0.4rem 0.1rem" : "0.5rem 0.75rem"};"><span style="color:var(--text-muted);">Loading scorecard…</span></td>`;
                row.after(det);
                if (chev) chev.innerHTML = "&#9662;";
                try {
                    const res = await fetch(`/api/scoring/scorecard/${row.dataset.srid}`);
                    const data = await res.json();
                    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
                    det.firstElementChild.innerHTML = prRenderScorecard(data);
                } catch (e) {
                    det.firstElementChild.innerHTML = `<span style="color:#b91c1c;">${escapeHtml(e.message)}</span>`;
                }
            });
        });
        // The CITY CHAMPIONSHIP line expands to the LIVE hole-by-hole card
        // straight off Golf Genius (championship day only). Errors PAINT —
        // a 500 and a still-loading state must never look identical.
        root.querySelectorAll("tr[data-champ-race]").forEach(row => {
            row.addEventListener("click", async ev => {
                ev.stopPropagation();
                const chev = row.querySelector(".pr-cc-chev");
                const next = row.nextElementSibling;
                if (next && next.classList.contains("pr-cc-detail")) {
                    next.remove();
                    if (chev) chev.innerHTML = "&#9656;";
                    return;
                }
                const det = document.createElement("tr");
                det.className = "pr-cc-detail";
                det.innerHTML = `<td colspan="${row.children.length}" class="pr-wrap" style="background:#fff;padding:${prIsCompact() ? "0.4rem 0.1rem" : "0.5rem 0.75rem"};"><span style="color:var(--text-muted);">Loading live card…</span></td>`;
                row.after(det);
                if (chev) chev.innerHTML = "&#9662;";
                try {
                    const res = await fetch(`/api/season-contests/points-race/champ-card?race=${encodeURIComponent(row.dataset.champRace)}&cid=${encodeURIComponent(row.dataset.champCid)}`, {cache: "no-store"});
                    const data = await res.json();
                    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
                    det.firstElementChild.innerHTML = prRenderChampCard(data);
                } catch (e) {
                    det.firstElementChild.innerHTML = `<span style="color:#b91c1c;">Live card unavailable: ${escapeHtml(e.message)}</span>`;
                }
            });
        });
    }

    // The live championship hole-by-hole card, PGA-Tour style (Kerry
    // 2026-08-01): BOTH nines always render, every hole showing, a dash
    // until a score lands — exactly how the Tour app shows a player who
    // hasn't teed off. Rows: HOLE / PAR / SCORE (gross, handicap dots as
    // superscripts) / PTS. PTS is OUR championship-scale Stableford
    // (0/0/1/2/3/4/5, gross ace 9) computed from the same gross + dots GG
    // shows — the card states when its total and the champ board disagree
    // instead of papering over it.
    function prRenderChampCard(card) {
        const holes = card.holes || [];
        const played = holes.filter(h => h.gross != null);
        const havePars = holes.some(h => h.par != null);
        const big = !!card._headline;
        const thruBit = card.board_thru
            ? `${/\d:\d\d/.test(String(card.board_thru)) ? "tees off" : "thru"} ${escapeHtml(String(card.board_thru))}`
            : "";
        // Name leads, pinned on top (the row scrolls to the top of the
        // screen when this card is the whole expansion).
        const head = `<div style="margin:0 0 0.45rem;font-size:${big ? "1.02rem" : "0.88rem"};">
            <span style="font-weight:800;color:#BF5700;">${escapeHtml(card.player_name || "")}</span>
            ${card.board_points != null ? `<span style="font-weight:800;color:#1B1B1B;"> &middot; ${escapeHtml(String(card.board_points))} pts</span>` : ""}
            ${thruBit ? ` <span style="font-weight:600;font-size:0.82em;color:#9A5B2E;">${thruBit}</span>` : ""}
        </div>`;
        // Projected winnings / points reset ride here on phones (Kerry
        // 2026-08-01 — the collapsed rows give that room back to names)
        const statline = card._statline
            ? `<div style="font-size:0.78rem;color:#4B5563;margin:-0.15rem 0 0.5rem;">${card._statline}</div>`
            : "";
        // Plus-handicap deduction (Kerry, championship day 2026-08-01): a
        // plus player's playing handicap comes OFF their points total. The
        // per-hole PTS row stays the raw Stableford (the cells must add
        // up); this line is where the smaller headline total is explained.
        const plusN = Number(card.plus_adjustment || 0);
        const plusNote = plusN
            ? `<div style="font-size:0.72rem;color:#9A5B2E;margin:-0.25rem 0 0.5rem;">Playing handicap +${plusN % 1 ? plusN.toFixed(1) : plusN}: ${plusN % 1 ? plusN.toFixed(1) : plusN} pts deducted from today's total (plus handicaps come off championship points).</div>`
            : "";
        if (!played.length && !havePars) {
            return head + statline + plusNote + `<span style="color:var(--text-muted);">No holes posted yet.</span>`;
        }
        const compact = prIsCompact();
        // Every HOLE column is the SAME fixed width (Kerry 2026-08-01) —
        // min-width let a circled score stretch its own column and the
        // grid read ragged. Sum/TOT columns size themselves.
        const holeW = compact ? "1.7em" : "2.2em";
        const td = `padding:${compact ? "2px 0" : "3px 2px"};text-align:center;border:1px solid #e2e8f0;width:${holeW};max-width:${holeW};overflow:hidden;white-space:nowrap;`;
        const sumTd = `padding:${compact ? "2px 2px" : "3px 6px"};text-align:center;border:1px solid #e2e8f0;min-width:${compact ? "1.6em" : "2.2em"};white-space:nowrap;`;
        const lbl = `padding:${compact ? "2px 3px" : "3px 8px"};border:1px solid #e2e8f0;font-weight:600;color:#475569;text-align:left;white-space:nowrap;`;
        const fs = compact ? "0.6rem" : "0.8rem";
        const dash = '<span style="color:#9CA3AF;">-</span>';
        const sumOr = (hs, k, fmt) => hs.some(h => h[k] != null)
            ? (fmt || String)(hs.reduce((a, h) => a + (h[k] ?? 0), 0)) : dash;
        // Classic scorecard marks on the gross score (same language as the
        // imported cards): red circle birdie, doubled ring eagle+, blue
        // square bogey, doubled square double+.
        const spanW = compact ? "1.2em" : "1.5em";
        const deco = d => {
            if (d == null) return "";
            if (d <= -2) return "border:1.5px solid #dc2626;border-radius:50%;box-shadow:0 0 0 2px #fff,0 0 0 3.5px #dc2626;";
            if (d === -1) return "border:1.5px solid #dc2626;border-radius:50%;";
            if (d === 1) return "border:1.5px solid #2563eb;";
            if (d >= 2) return "border:1.5px solid #2563eb;box-shadow:0 0 0 2px #fff,0 0 0 3.5px #2563eb;";
            return "";
        };
        const grossCell = h => {
            if (h.gross == null) return dash;
            const vs = h.par != null ? h.gross - h.par : null;
            return `<span style="display:inline-block;min-width:${spanW};line-height:${spanW};${deco(vs)}">${h.gross}</span>`
                + (h.dots ? `<sup style="font-size:50%;">` + "&#9679;".repeat(Math.min(h.dots, 3)) + "</sup>" : "");
        };
        const block = (label, hs, withTot) => {
            const cells = fn => hs.map(fn).join("");
            const totCell = (v, extra) => `<td style="${sumTd}font-weight:800;${extra || ""}">${v}</td>`;
            return `<table style="border-collapse:collapse;font-size:${fs};margin:0 0 0.45rem;">
                <tr><td style="${lbl}">HOLE</td>${cells(h => `<td style="${td}font-weight:700;background:#f8fafc;">${h.hole}</td>`)}<td style="${sumTd}font-weight:700;background:#f8fafc;">${label}</td>${withTot ? `<td style="${sumTd}font-weight:800;background:#f1f5f9;">TOT</td>` : ""}</tr>
                <tr><td style="${lbl}background:#eef1f5;">PAR</td>${cells(h => `<td style="${td}background:#eef1f5;color:#6B7280;">${h.par ?? "-"}</td>`)}<td style="${sumTd}background:#eef1f5;font-weight:700;color:#6B7280;">${sumOr(hs, "par")}</td>${withTot ? totCell(sumOr(holes, "par"), "background:#eef1f5;color:#6B7280;") : ""}</tr>
                <tr><td style="${lbl}">GROSS</td>${cells(h => `<td style="${td}">${grossCell(h)}</td>`)}<td style="${sumTd}font-weight:700;">${sumOr(hs, "gross")}</td>${withTot ? totCell(card.gross_total != null ? card.gross_total : sumOr(holes, "gross")) : ""}</tr>
                ${card.scoring === "gross" ? "" : `<tr><td style="${lbl}background:#eef1f5;">NET</td>${cells(h => `<td style="${td}background:#eef1f5;color:#475569;">${h.net != null ? h.net : dash}</td>`)}<td style="${sumTd}background:#eef1f5;font-weight:700;color:#475569;">${sumOr(hs, "net")}</td>${withTot ? totCell(sumOr(holes, "net"), "background:#eef1f5;color:#475569;") : ""}</tr>`}
                <tr><td style="${lbl}background:#FDF0E6;color:#BF5700;">PTS</td>${cells(h => `<td style="${td}background:#FDF0E6;color:#BF5700;font-weight:700;">${h.pts != null ? h.pts : dash}</td>`)}<td style="${sumTd}background:#FDF0E6;color:#BF5700;font-weight:800;">${sumOr(hs, "pts")}</td>${withTot ? totCell(card.computed_points != null ? card.computed_points : sumOr(holes, "pts"), "background:#FDF0E6;color:#BF5700;") : ""}</tr>
            </table>`;
        };
        const front = holes.filter(h => h.hole <= 9);
        const back = holes.filter(h => h.hole > 9);
        const html = block("OUT", front, false) + block("IN", back, true);
        // Two different GG surfaces feed this card: the scorecard partial
        // (per hole) and the points board (total + thru). The scorecard
        // often runs a hole AHEAD of the board for a minute — that is a
        // lag, not a disagreement, and it must not read like an error
        // (Kerry 2026-08-01: "Points aren't adding correctly" — they were,
        // the board just hadn't posted hole 2 yet).
        const boardThruN = /^\d+$/.test(String(card.board_thru || "").trim())
            ? parseInt(card.board_thru, 10)
            : (String(card.board_thru || "").trim().toUpperCase() === "F" ? 18 : null);
        // Parity compares like with like: both our total and the board
        // figure carry the plus-handicap deduction (the board's was applied
        // server-side in fetch_champ_points), so a plus player doesn't read
        // as a permanent disagreement of exactly their deduction.
        const compEff = card.computed_points_adj != null
            ? card.computed_points_adj
            : (card.computed_points != null ? card.computed_points - plusN : null);
        const differs = compEff != null && card.board_points != null
            && Number(compEff) !== Number(card.board_points);
        const boardLagging = differs && (boardThruN == null || boardThruN < played.length);
        const parity = !differs ? ""
            : boardLagging
                ? `<div style="color:#9CA3AF;font-size:0.72rem;margin-top:0.2rem;">Scorecard shows ${played.length} hole${played.length === 1 ? "" : "s"}; the points board is still thru ${escapeHtml(String(card.board_thru ?? "—"))} — totals sync on its next refresh.</div>`
                : `<div style="color:#b45309;font-size:0.72rem;margin-top:0.2rem;">Our per-hole total (${escapeHtml(String(compEff))}) differs from the GG board (${escapeHtml(String(card.board_points))}) — the board is official.</div>`;
        const src = card.stale
            ? `<div style="color:#b45309;font-size:0.72rem;margin-top:0.2rem;">Showing the last good read — Golf Genius did not answer.</div>` : "";
        return head + statline + plusNote + `<div class="pr-scroll">${html}</div>` + parity + src;
    }

    function prRenderScorecard(card) {
        const holes = card.holes || [];
        if (!holes.some(h => h.strokes != null)) {
            return '<span style="color:var(--text-muted);">No hole data on this card.</span>';
        }
        const blocks = [];
        const front = holes.filter(h => h.hole_number <= 9);
        const back = holes.filter(h => h.hole_number > 9);
        if (front.some(h => h.strokes != null)) blocks.push(["OUT", front]);
        if (back.some(h => h.strokes != null)) blocks.push(["IN", back]);

        // Compact variant on phones: tighter cells, smaller type, and
        // abbreviated row labels so a full nine fits with minimal scrolling
        const compact = prIsCompact();
        const td = `padding:${compact ? "1px 1px" : "2px 6px"};text-align:center;border:1px solid #e2e8f0;min-width:${compact ? "1.1em" : "2em"};white-space:nowrap;`;
        const lbl = `padding:${compact ? "1px 2px" : "2px 8px"};border:1px solid #e2e8f0;font-weight:600;color:#475569;text-align:left;white-space:nowrap;`;
        const L = compact
            ? { yds: "YDS", gs: "GROSS", gp: "G PTS", ns: "NET", np: "N PTS", adj: "ADJ" }
            : { yds: "YARDS", gs: "GROSS SCORE", gp: "GROSS PTS", ns: "NET SCORE", np: "NET PTS", adj: "ADJ SCORE" };
        // ADJ row (in sync with scorecard-render.js, Kerry 2026-07-14):
        // shown only when the WHS net-double-bogey cap lowered a hole;
        // capped holes render TGF orange.
        const anyCapped = (card.holes || []).some(h =>
            h.strokes != null && h.adjusted_strokes != null && h.adjusted_strokes !== h.strokes);
        const fs = compact ? "0.58rem" : "0.8rem";
        const spanW = compact ? "1.08em" : "1.4em";
        // Circle/square marks are vs-par symbols computed from OUR facts:
        // the GROSS row uses vs_par, the NET row uses net_vs_par (GG's own
        // markings are net-relative and stay stored for verification only)
        const decoFor = d => {
            if (d == null) return "";
            if (d <= -2) return "border:1.5px solid #dc2626;border-radius:50%;box-shadow:0 0 0 2px #fff,0 0 0 3.5px #dc2626;";
            if (d === -1) return "border:1.5px solid #dc2626;border-radius:50%;";
            if (d === 1) return "border:1.5px solid #2563eb;";
            if (d >= 2) return "border:1.5px solid #2563eb;box-shadow:0 0 0 2px #fff,0 0 0 3.5px #2563eb;";
            return "";
        };
        const scoreCell = (h, extra = "") => {
            if (h.strokes == null) return `<td style="${td}${extra}"></td>`;
            return `<td style="${td}${extra}"><span style="display:inline-block;min-width:${spanW};line-height:${spanW};${decoFor(h.vs_par)}">${h.strokes}</span></td>`;
        };
        // ● = stroke received; ○ = stroke GIVEN BACK (plus handicap) —
        // shown on the NET row (they're what turns gross into net), pinned
        // to the cell's top-right corner so they never displace the number
        const strokeDots = h => {
            const sr = h.strokes_received || 0;
            return sr
                ? `<span style="position:absolute;top:0;right:1px;font-size:0.55em;line-height:1.4;color:#334155;">${(sr > 0 ? "●" : "○").repeat(Math.abs(sr))}</span>`
                : "";
        };
        const sum = (hs, f) => hs.reduce((a, h) => a + (f(h) || 0), 0);
        // Stableford totals can legitimately be 0 or negative — show them
        const sumPts = (hs, f) => {
            let any = false, t = 0;
            hs.forEach(h => { const v = f(h); if (v != null) { any = true; t += v; } });
            return any ? t : "";
        };

        // Visual hierarchy: course facts on top, then a thick-bordered
        // score section (GROSS most important, then NET), then points
        const sectTop = "border-top:2px solid #1B1B1B;";
        const sectBot = "border-bottom:2px solid #1B1B1B;";
        const netOf = h => (h.strokes == null ? null : h.strokes - (h.strokes_received || 0));
        const tables = blocks.map(([label, hs]) => {
            const holeRow = hs.map(h => `<td style="${td}font-weight:700;background:#1B1B1B;color:#fff;">${h.hole_number}</td>`).join("");
            const info = "color:#1D4ED8;";
            const parRow = hs.map(h => `<td style="${td}${info}">${h.par ?? ""}</td>`).join("");
            const ydsRow = hs.map(h => `<td style="${td}${info}">${h.yardage ?? ""}</td>`).join("");
            const siRow = hs.map(h => `<td style="${td}${info}opacity:.75;">${h.stroke_index ?? ""}</td>`).join("");
            // GROSS section (bold score + its points on a grey band), then
            // NET section, each opened by a thick border — points sit
            // directly beneath their score and read visually subordinate
            const grey = "background:#EFF4FF;color:#1D4ED8;";
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
            const totHead = `style="${td}font-weight:700;background:#1B1B1B;color:#fff;"`;
            return `<table style="border-collapse:collapse;font-size:${fs};margin:0.25rem 0;">
                <tr><td style="${lbl}background:#1B1B1B;color:#fff;">HOLE</td>${holeRow}<td ${totHead}>${label}</td></tr>
                <tr><td style="${lbl}color:#1D4ED8;">PAR</td>${parRow}<td ${tot}>${sum(hs, h => h.par) || ""}</td></tr>
                <tr><td style="${lbl}color:#1D4ED8;">${L.yds}</td>${ydsRow}<td ${tot}>${sum(hs, h => h.yardage) || ""}</td></tr>
                <tr><td style="${lbl}color:#1D4ED8;" title="Hole handicap ranking (stroke index): 1 = hardest — decides which holes a player's handicap dots land on">HCP</td>${siRow}<td ${tot}></td></tr>
                <tr><td style="${lbl}${sectTop}font-weight:700;">${L.gs}</td>${scRow}<td ${totG}>${sum(hs, h => h.strokes) || ""}</td></tr>
                ${anyCapped ? `<tr><td style="${lbl}color:#E87C3E;" title="WHS net double bogey cap: par + 2 + strokes received. Orange holes were lowered for handicap purposes.">${L.adj}</td>${adjRow}<td style="${td}font-weight:700;background:#f1f5f9;color:#E87C3E;">${sum(hs, h => h.adjusted_strokes) || ""}</td></tr>` : ""}
                <tr><td style="${lbl}${grey}" title="Gross stableford points per hole">${L.gp}</td>${gpRow}<td ${totGP}>${sumPts(hs, h => h.stableford_gross)}</td></tr>
                <tr><td style="${lbl}${sectTop}font-weight:700;" title="Gross strokes minus handicap strokes received on the hole">${L.ns}</td>${netRow}<td ${totN}>${sumPts(hs, netOf)}</td></tr>
                <tr><td style="${lbl}${grey}${sectBot}" title="Net stableford points per hole (through the admin formula settings)">${L.np}</td>${npRow}<td ${totNP}>${sumPts(hs, h => h.stableford_net)}</td></tr>
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
            <div style="font-size:${compact ? "0.62rem" : "0.72rem"};color:var(--text-muted);margin-top:0.15rem;${noteW}">
                ● = handicap stroke${sep}○ = plus stroke${sep}<span style="border:1.5px solid #dc2626;border-radius:50%;padding:0 4px;">n</span> under par &nbsp;
                <span style="border:1.5px solid #2563eb;padding:0 4px;">n</span> over par
            </div>`;
    }

    // GG convention: plus handicaps display as "+1" (stored negative so
    // net = gross - ph stays uniform)
    function prFmtHcp(v) {
        if (v == null) return "";
        return v < 0 ? `+${Math.abs(v) % 1 ? Math.abs(v).toFixed(1) : Math.abs(v)}` : `${v}`;
    }

    function prRenderDetailTables(tables, rounds, claimed, opts = {}) {
        // opts.monthFilter (YYYY-MM) keeps only rows awarded that month;
        // opts.plain skips the counted/not-counted sections and CITY row
        // (the monthly race has no best-10 split)
        if (!tables || !tables.length) {
            return '<span style="color:var(--text-muted);">No round-by-round detail available for this player.</span>';
        }
        const compact = prIsCompact();
        // Index the player's imported scorecards by event name (and by the
        // event-code prefix as fallback) so points lines expand in place
        const codeOf = s => {
            const m = /^([a-z]+\d+(?:\.\d+)?)\b/i.exec((s || "").trim());
            return m ? m[1].toLowerCase() : null;
        };
        const byEvent = {}, byCode = {};
        (rounds || []).forEach(r => {
            if (!r.event_name) return;
            byEvent[r.event_name.trim().toLowerCase()] = r;
            const c = codeOf(r.event_name);
            if (c) byCode[c] = r;
        });
        return tables.map(t => {
            const orig = t[0] || [];
            // Reshape GG's columns: drop Event, lead with Points
            let order = null;
            if (orig.length) {
                const norm = orig.map(h => (h || "").trim().toLowerCase());
                const ptsIdx = norm.indexOf("points");
                const evIdx = norm.indexOf("event");
                const dateIdx = norm.findIndex(h => /date/.test(h));
                const tourIdx = norm.indexOf("tournament");
                if (ptsIdx > -1) {
                    // Admin order: DATE | EVENT | PTS | POSITION — points sit
                    // right of the event, mirroring the level-1 standings
                    order = [];
                    if (dateIdx > -1) order.push(dateIdx);
                    if (tourIdx > -1) order.push(tourIdx);
                    order.push(ptsIdx);
                    for (let i = 0; i < orig.length; i++) {
                        if (!order.includes(i) && i !== evIdx) order.push(i);
                    }
                }
            }
            // GG cells separate words with non-breaking spaces — swap them
            // for regular spaces or the text can't wrap and paints over the
            // neighboring column in the width-locked compact tables
            // ... and long/short hyphens vary between GG and admin naming \u2014
            // normalize every dash to a plain hyphen (admin preference)
            const nb = v => String(v ?? "").replace(/[\s\u200b\u2060]+/g, " ").replace(/[\u2013\u2014]/g, "-");
            const remap = row => (order && row.length === orig.length) ? order.map(i => row[i]) : row;
            let head = remap(orig).map(h => (h || "").trim().toLowerCase() === "tournament" ? "EVENT" : h);
            let evtCol = remap(orig).findIndex(h => (h || "").trim().toLowerCase() === "tournament");
            // Phones drop the Position column (the date shows instead)
            const fullWidth = head.length;
            const dropIdx = compact ? head.findIndex(h => /position/i.test(h || "")) : -1;
            const project = row => (dropIdx > -1 && row.length === fullWidth)
                ? row.filter((_, i) => i !== dropIdx) : row;
            head = project(head);
            if (dropIdx > -1 && evtCol > dropIdx) evtCol--;
            const width = head.length;
            const lowHead = head.map(h => (h || "").trim().toLowerCase());
            const ptsCol = lowHead.indexOf("points");
            const dateCol = lowHead.findIndex(h => /date/.test(h));
            // Desktop: a trailing spacer column mirrors the level-1 table's
            // post-points block (RESET 110 + Rounds 80 + Buy-in 110 = 300px
            // minus the 80px POS column, border-box) so PTS lines up exactly
            // under the standings PTS column. Phones skip the spacer — PTS
            // simply rides the right edge with room to breathe.
            const posCol = lowHead.findIndex(h => h === "position");
            const spacer = !compact && ptsCol > -1;
            const spacerW = posCol > -1 ? 220 : 300;
            const totalCols = width + (spacer ? 1 : 0);
            const body = t.slice(1).filter(r => r.some(c => (c || "").trim())).map(r => project(remap(r)));
            // Rows above GG's "not counted" divider are the counted scores
            // (best 10) — bold their Points + EVENT cells for contrast; the
            // CITY CHAMPIONSHIP Total line joins them (blank until played):
            // final = best 10 point totals + City Championship total.
            let counted = true;
            // CITY CHAMPIONSHIP sits at the TOP of the counted list, not the
            // bottom (Kerry 2026-07-31) — it is a REQUIRED, never-droppable
            // add-on, so it reads as the headline rather than a footnote, and
            // it carries a contrasting burnt-orange treatment against the
            // plain counted rows. opts.champPoints fills it live while the
            // round is in progress; blank until then.
            const _cc = (opts.champPoints != null && opts.champPoints !== "")
                ? String(opts.champPoints) : "";
            // a tee time is "tees off", a hole count is "thru" — a player
            // reading "thru 9:00 AM" is nonsense
            const _ccThru = opts.champThru ? ` <span style="font-weight:400;font-size:0.85em;color:#9A5B2E;">${/\d:\d\d/.test(String(opts.champThru)) ? "tees off" : "thru"} ${escapeHtml(String(opts.champThru))}</span>` : "";
            const ccCells = [];
            for (let ci = 0; ci < Math.max(0, totalCols - 2); ci++) {
                // Drop the live points under the PTS column when we know it.
                ccCells.push((ptsCol > -1 && ci === (ptsCol - 2) && _cc)
                    ? `<td style="font-weight:800;color:#BF5700;">${escapeHtml(_cc)}</td>`
                    : "<td></td>");
            }
            // With a race + customer the line expands to the LIVE hole-by-
            // hole card (championship day). Chevron only when expandable so
            // the off-season row stays inert.
            const _ccExpandable = !!(opts.champRace && opts.champCid);
            const _ccChev = _ccExpandable
                ? ' <span class="pr-cc-chev" style="color:#BF5700;font-size:0.85rem;" title="Live hole-by-hole">&#9656;</span>'
                : '';
            const ccRow = `<tr${_ccExpandable ? ` data-champ-race="${escapeHtml(String(opts.champRace))}" data-champ-cid="${escapeHtml(String(opts.champCid))}" style="cursor:pointer;` : ` style="`}background:#FDF0E6;border-top:2px solid #BF5700;border-bottom:2px solid #BF5700;">
                <td></td>
                <td style="font-weight:800;color:#BF5700;">CITY CHAMPIONSHIP Total${_ccThru}${_ccChev}</td>
                ${ccCells.join("")}
            </tr>`;
            // Admin-specced section banners: counted = black bar with white
            // text, not counted = 40% gray with black text (replaces GG's
            // "following points are not counted" sentence row)
            const secHdr = (label, bg, fg) => `<tr><td colspan="${totalCols}" class="pr-wrap" style="background:${bg};color:${fg};font:700 11px/1.5 'Bitter',serif;letter-spacing:1px;text-transform:uppercase;">${label}</td></tr>`;
            const parts = [];
            if (order && !opts.plain) parts.push(secHdr(`${compact ? "COUNTED" : "POINTS COUNTED"} <span style="font-weight:400;text-transform:none;letter-spacing:0;color:#9CA3AF;font-family:'Helvetica Neue',Arial,sans-serif;">(Best 10 + City Championship)</span>`, "#1B1B1B", "#fff"));
            // Top of the counted list, immediately under the banner.
            let ccPlaced = false;
            if (!opts.plain) { parts.push(ccRow); ccPlaced = true; }
            for (const r of body) {
                if (r.length !== width) {
                    if (opts.plain) continue;
                    if (counted) {
                        if (!ccPlaced) parts.push(ccRow);
                        counted = false;
                        if (order) { parts.push(secHdr(compact ? "Not Counted" : "Points Not Counted", "#B9B7B2", "#1B1B1B")); continue; }
                    }
                    parts.push(`<tr><td colspan="${totalCols}" class="pr-wrap" style="text-align:center;font-weight:600;background:#f8fafc;">${escapeHtml(nb(r.join(" ")))}</td></tr>`);
                    continue;
                }
                if (opts.monthFilter && dateCol > -1
                    && !nb(r[dateCol]).startsWith(opts.monthFilter)) continue;
                // Section banners carry the counted/not-counted contrast on
                // phones — bold event text there just crowds the column
                const bold = counted ? (compact ? "" : "font-weight:700;") : "color:var(--text-muted);";
                // Points line with an imported scorecard → click to expand
                // the hole-by-hole card right under this row
                let match = null;
                if (evtCol > -1 && (rounds || []).length) {
                    const evtRaw = nb(r[evtCol] || "").replace(/\s+[—-]\s+(Front|Back)$/i, "").trim();
                    // Code lookup tolerates a series-only event name: GG
                    // "a18.3" still finds a round under "a18 CRYSTAL FALLS"
                    const code = codeOf(evtRaw);
                    match = byEvent[evtRaw.toLowerCase()]
                        || (code ? byCode[code] || byCode[code.replace(/\.\d+$/, "")] : null);
                    // League lines have no code and a different name shape:
                    // GG "Hill Country Matches - Valley" vs imported round
                    // "Hill Country Matches | Comanche Trace" whose COURSE
                    // carries the nine ("… - VALLEY"). Fall back to base-name
                    // prefix + qualifier-vs-course/tee matching.
                    if (!match) {
                        const segs = evtRaw.split(/\s+[-–—|]\s+/);
                        const base = (segs[0] || "").trim().toLowerCase();
                        // last WORD of the qualifier: "R1 Valley" -> "valley"
                        const qual = segs.length > 1
                            ? (segs[segs.length - 1].trim().toLowerCase().split(/\s+/).pop() || "")
                            : "";
                        if (base.length >= 8 && qual) {
                            match = (rounds || []).find(x =>
                                (x.event_name || "").trim().toLowerCase().startsWith(base)
                                && `${x.event_name || ""} ${x.course_name || ""} ${x.tee_name || ""}`.toLowerCase().includes(qual)
                            ) || null;
                        }
                    }
                }
                if (match && claimed) claimed.add(match.id);
                parts.push(`<tr${match ? ` data-srid="${match.id}" style="cursor:pointer;" title="Click for the hole-by-hole scorecard"` : ""}>${r.map((c, i) => {
                    // PTS column mirrors the level-1 standings points column:
                    // centered, bold, 2px side borders
                    let style;
                    if (i === ptsCol) style = `text-align:center;font-weight:700;border-left:2px solid #cbd5e1;border-right:2px solid #cbd5e1;${counted ? "" : "color:var(--text-muted);"}`;
                    else if (i === evtCol) style = bold;
                    else if (i === posCol) style = "text-align:center;" + (counted ? "" : "color:var(--text-muted);");
                    else style = counted ? "" : "color:var(--text-muted);";
                    let val = nb(c);
                    if (i === dateCol) val = prFmtAwardDate(val, compact);
                    else if (compact && i === evtCol) val = prPrettyEvent(val);
                    if (i === evtCol && match) val += prNineSuffix(val, match);
                    const chev = match && i === evtCol ? '<span class="pr-sc-chev" style="color:var(--primary);font-size:0.85rem;">&#9656;</span> ' : "";
                    const badges = i === evtCol && match
                        ? prBadgeLayout(prMvpBadges(match), val, compact) : "";
                    return `<td${i === evtCol ? ' class="pr-wrap"' : ""} style="${style}">${chev}${escapeHtml(val)}${badges}</td>`;
                }).join("")}${spacer ? "<td></td>" : ""}</tr>`);
            }
            if (counted && !opts.plain) parts.push(ccRow);
            // A month filter can empty a table entirely — skip it rather
            // than render a lone header row
            if (opts.plain && !parts.length) return "";
            return `<div class="pr-scroll">
                <table class="enrollment-table${compact ? " pr-compact" : ""}" style="margin:0.35rem 0;font-size:${compact ? "0.72rem" : "0.82rem"};">
                <thead><tr>${head.map((c, i) => {
                    const key = (c || "").trim().toLowerCase();
                    if (i === ptsCol) return `<th style="width:${compact ? "40px" : "90px"};text-align:center;border-left:2px solid #cbd5e1;border-right:2px solid #cbd5e1;">${compact ? "PTS" : "POINTS"}</th>`;
                    if (i === dateCol) return `<th style="width:${compact ? "36px" : "110px"};">Date</th>`;
                    if (key === "position") return `<th style="width:80px;text-align:center;">POS</th>`;
                    return `<th>${escapeHtml(nb(c))}</th>`;
                }).join("")}${spacer ? `<th style="width:${spacerW}px;"></th>` : ""}</tr></thead>
                <tbody>${parts.join("")}</tbody>
                </table>
            </div>`;
        }).join("");
    }

    window.prIsCompact = prIsCompact;
    window.prFmtAwardDate = prFmtAwardDate;
    window.prMvpBadges = prMvpBadges;
    window.prBadgeLayout = prBadgeLayout;
    window.prNineSuffix = prNineSuffix;
    window.prPrettyEvent = prPrettyEvent;
    window.prShortCourse = prShortCourse;
    window.prFmtHcp = prFmtHcp;
    window.prRenderScoreRounds = prRenderScoreRounds;
    window.prRenderDetailTables = prRenderDetailTables;
    window.prRenderScorecard = prRenderScorecard;
    window.prBindScorecardToggles = prBindScorecardToggles;
    // The live expansion in contests.html renders the card directly —
    // without this export it threw "Can't find variable" on the course
    // (v2.180.1); the CC-row path never caught it because its binder
    // lives inside this closure.
    window.prRenderChampCard = prRenderChampCard;
})();
