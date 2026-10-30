// REVERSE ON A CLOSED EVENT ASKS "DID HE PLAY?" (Kerry 10/30: "A reversed
// slot on a closed event should be asked right there one or the other";
// option A: "didn't play" re-credits to the buyer in the same step).
//
// window.tgfReverseAsk(itemId, playerName, label) -> Promise of the POST body
// for /api/items/<id>/reverse-credit, or null when the manager cancels.
//   * event not closed: the plain confirm, body {}
//   * closed: a three-button box
//       He played      -> {played: true}   spot back in the field and games
//       He didn't play -> {played: false}  credit undone and re-credited to
//                                          the buyer; the field stays as closed
//       Cancel         -> null
// Loaded by events.html, customers.html and index.html (dashboard.js).
(function () {
    "use strict";

    async function check(itemId) {
        try {
            const r = await fetch(`/api/items/${itemId}/reactivation-check`);
            return r.ok ? await r.json() : {};
        } catch (e) { return {}; }
    }

    function esc(s) {
        return String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
    }

    function box(name, eventName) {
        return new Promise(resolve => {
            const wrap = document.createElement("div");
            wrap.className = "tgf-reverse-ask";
            wrap.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:10000;display:flex;align-items:center;justify-content:center;padding:16px;";
            const btn = "display:block;width:100%;margin:8px 0 0;padding:11px 14px;border-radius:999px;font:600 15px Bitter,Georgia,serif;cursor:pointer;";
            wrap.innerHTML = `
              <div role="dialog" aria-modal="true" style="background:#fff;border-radius:12px;max-width:420px;width:100%;padding:20px;font-family:Helvetica Neue,Arial,sans-serif;color:#1B1B1B;">
                <div style="font:bold 11px Arial,sans-serif;letter-spacing:2px;color:#E87C3E;">THIS EVENT IS CLOSED</div>
                <div style="font:600 19px Bitter,Georgia,serif;margin:6px 0 4px;">Did ${esc(name)} play?</div>
                <div style="font-size:14px;color:#4B5563;line-height:1.45;">${esc(eventName || "This event")} has its payouts recorded. Reversing on a closed event needs one answer.</div>
                <button data-a="played" style="${btn}background:#1B1B1B;color:#fff;border:0;">He played: count him back in the field and games</button>
                <button data-a="not" style="${btn}background:#fff;color:#1B1B1B;border:2px solid #1B1B1B;">He didn't play: credit the buyer, keep the field as closed</button>
                <button data-a="cancel" style="${btn}background:#fff;color:#6B7280;border:1px solid #E5E7EB;">Cancel</button>
              </div>`;
            const done = v => { wrap.remove(); document.removeEventListener("keydown", onKey); resolve(v); };
            const onKey = e => { if (e.key === "Escape") done(null); };
            wrap.addEventListener("click", e => {
                const a = e.target && e.target.getAttribute && e.target.getAttribute("data-a");
                if (a === "played") done({ played: true });
                else if (a === "not") done({ played: false });
                else if (a === "cancel" || e.target === wrap) done(null);
            });
            document.addEventListener("keydown", onKey);
            document.body.appendChild(wrap);
        });
    }

    window.tgfReverseAsk = async function (itemId, playerName, label) {
        const c = await check(itemId);
        if (!c || !c.closed) {
            return confirm(`Reverse ${label || "this"} for ${playerName}?`) ? {} : null;
        }
        return box(playerName, c.event);
    };
})();
