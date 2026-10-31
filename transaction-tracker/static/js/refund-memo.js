// REFUND MEMOS (Kerry 2026-10-28, Event Ops #2475-2 / #2476-4): "It's the
// [What] for [Event or Season Contest name]" -> "Refund for a9.29 Teravista".
// Twin of email_parser/refund_memo.py — change both together.
(function () {
    "use strict";
    const CODE = /^[a-z]+\d+(\.\d+)?$/i;
    // kept upper case when an ALL-CAPS name is cased
    const ACRONYMS = new Set(["TPC", "TGF", "LSC", "MVP", "CC", "GC", "HIO", "PGA"]);
    function displayName(name) {
        const s = String(name == null ? "" : name).split(/\s+/).filter(Boolean).join(" ");
        // a leading lower-case code ("s9.28") doesn't stop the rest being cased
        const ws = s.split(" ");
        if (ws.length > 1 && CODE.test(ws[0])) return ws[0].toLowerCase() + " " + displayName(ws.slice(1).join(" "));
        if (!s || !/[A-Za-z]/.test(s) || s !== s.toUpperCase()) return s;
        return s.split(" ").map(w => {
            if (CODE.test(w)) return w.toLowerCase();
            if (ACRONYMS.has(w)) return w;
            if (/\d/.test(w)) return w;
            return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
        }).join(" ");
    }
    window.refundMemoName = displayName;
    // "First Last": a stored "YOUNG, Jeff" is turned round
    function playerName(name) {
        let s = String(name == null ? "" : name).split(/\s+/).filter(Boolean).join(" ");
        if (s.includes(",")) {
            const i = s.indexOf(",");
            const last = s.slice(0, i).trim(), first = s.slice(i + 1).trim();
            s = `${first} ${last === last.toUpperCase() ? last.charAt(0) + last.slice(1).toLowerCase() : last}`.trim();
        }
        return s;
    }
    // Kerry 10/30: "[First Name] [Last Name] - [What] for [Event]"
    window.refundMemo = function (what, name, player) {
        const w = String(what || "").split(/\s+/).filter(Boolean).join(" ") || "Refund";
        const n = displayName(name);
        const body = n ? `${w} for ${n}` : w;
        const p = playerName(player);
        return p ? `${p} - ${body}` : body;
    };
})();
