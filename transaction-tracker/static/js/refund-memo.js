// REFUND MEMOS (Kerry 2026-10-28, Event Ops #2475-2 / #2476-4): "It's the
// [What] for [Event or Season Contest name]" -> "Refund for a9.29 Teravista".
// Twin of email_parser/refund_memo.py — change both together.
(function () {
    "use strict";
    function displayName(name) {
        const s = String(name == null ? "" : name).split(/\s+/).filter(Boolean).join(" ");
        if (!s || !/[A-Za-z]/.test(s) || s !== s.toUpperCase()) return s;
        return s.split(" ").map(w => {
            if (/^[a-z]+\d+(\.\d+)?$/i.test(w)) return w.toLowerCase();
            if (/\d/.test(w)) return w;
            return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
        }).join(" ");
    }
    window.refundMemoName = displayName;
    window.refundMemo = function (what, name) {
        const w = String(what || "").split(/\s+/).filter(Boolean).join(" ") || "Refund";
        const n = displayName(name);
        return n ? `${w} for ${n}` : w;
    };
})();
