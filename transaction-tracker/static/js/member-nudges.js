// First-use member nudges — design-claude spec (mailbox #139/#140),
// Kerry-ratified with the #141 welcome-copy edit. The whisper pattern:
// anchored card, Bitter eyebrow + one line of system-sans body, orange
// twice only (eyebrow + 3px keyline), 40x40 one-tap dismiss, NO scrim,
// no reflow (absolute overlay), bottom-toast degrade when the anchor
// is off-screen. Once per device via localStorage; "one at a time" —
// the welcome card wins and defers contextual nudges to the next visit.
// SCOPE GUARD (#141, ratified): .nudge is for DISCOVERY TIPS ONLY —
// never actionable, time-sensitive, or financial messaging.
(function () {
    "use strict";
    if (!window.MEMBER_MODE) return;

    const KEYS = {
        welcome: "tgf_nudge_welcome",
        standings: "tgf_nudge_standings",
        spotlight: "tgf_nudge_spotlight_search",
    };

    function seen(key) {
        try { return !!localStorage.getItem(key); } catch (e) { return true; }
    }
    function markSeen(key) {
        try { localStorage.setItem(key, String(new Date().getTime())); } catch (e) { /* private mode */ }
    }
    function beacon(kind, key) {
        // impression/dismiss to /traffic via the member beacon (respects #notrack)
        try { if (window.tgfMemberMetric) window.tgfMemberMetric("nudge", key + ":" + kind); } catch (e) { /* never break the page */ }
    }

    const CSS = `
.tgf-nudge { position: absolute; z-index: 260; background: #fff; border: 1px solid var(--border, #E5E7EB);
  border-radius: 13px; box-shadow: 0 8px 30px rgba(0,0,0,.16); padding: 13px 44px 13px 15px; }
.tgf-nudge.tgf-nudge-toast { position: fixed; left: 16px; right: 16px; bottom: 22px; }
.tgf-nudge::before { content: ""; position: absolute; left: 0; top: 11px; bottom: 11px; width: 3px;
  border-radius: 3px; background: var(--primary, #E87C3E); }
.tgf-nudge-eye { font: 700 8.5px/1 'Bitter', serif; letter-spacing: 1.6px; text-transform: uppercase;
  color: var(--primary, #E87C3E); }
.tgf-nudge-body { font: 500 13px/1.45 'Helvetica Neue', Arial, sans-serif; color: #1B1B1B;
  margin-top: 6px; max-width: 290px; }
.tgf-nudge-x { position: absolute; top: 2px; right: 2px; width: 40px; height: 40px; display: flex;
  align-items: flex-start; justify-content: flex-end; padding: 9px 9px 0 0; color: #B7B2A8;
  font-size: 15px; cursor: pointer; background: transparent; border: none; }
.tgf-nudge-x:hover { color: #6B7280; }
.tgf-nudge-arrow { position: absolute; top: -8px; width: 15px; height: 15px; background: #fff;
  border: 1px solid var(--border, #E5E7EB); border-right: none; border-bottom: none;
  transform: rotate(45deg); }`;

    function injectCss() {
        const s = document.createElement("style");
        s.textContent = CSS;
        document.head.appendChild(s);
    }

    function show(key, eyebrow, bodyText, anchor, arrowLeft, fixedTop) {
        const card = document.createElement("div");
        card.className = "tgf-nudge";
        card.setAttribute("role", "status");
        card.innerHTML =
            (anchor ? `<div class="tgf-nudge-arrow" style="left:${arrowLeft || 64}px"></div>` : "") +
            `<button class="tgf-nudge-x" aria-label="Dismiss">✕</button>` +
            `<div class="tgf-nudge-eye"></div><div class="tgf-nudge-body"></div>`;
        card.querySelector(".tgf-nudge-eye").textContent = eyebrow;
        card.querySelector(".tgf-nudge-body").textContent = bodyText;

        let anchored = false;
        if (fixedTop) {
            // welcome card floats over the top of content (mock 5b) —
            // fixed under the member nav, no arrow, no reflow
            card.style.position = "fixed";
            card.style.top = "74px";
            card.style.left = "16px";
            card.style.right = "16px";
            anchored = true;
        } else if (anchor) {
            const r = anchor.getBoundingClientRect();
            const vh = window.innerHeight || 800;
            // anchor visibly on screen → anchored card with pointer;
            // otherwise degrade to the bottom toast (5d)
            if (r.top >= 0 && r.top < vh * 0.75) {
                card.style.top = (r.bottom + (window.scrollY || 0) + 10) + "px";
                card.style.left = "16px";
                card.style.right = "16px";
                anchored = true;
            }
        }
        if (!anchored) {
            card.classList.add("tgf-nudge-toast");
            const arrow = card.querySelector(".tgf-nudge-arrow");
            if (arrow) arrow.remove();
        }
        document.body.appendChild(card);
        beacon("impression", key);
        card.querySelector(".tgf-nudge-x").addEventListener("click", () => {
            markSeen(key);
            beacon("dismiss", key);
            card.remove();
        });
    }

    // Wait for an async-rendered anchor (standings load after fetch);
    // gives up quietly — a nudge must never demand attention.
    function whenAnchor(selector, cb, tries) {
        const el = document.querySelector(selector);
        if (el) return cb(el);
        if ((tries || 0) >= 20) return;
        setTimeout(() => whenAnchor(selector, cb, (tries || 0) + 1), 500);
    }

    function init() {
        injectCss();
        const path = location.pathname;
        if (path.indexOf("/member/spotlight") === 0) {
            if (!seen(KEYS.spotlight)) {
                whenAnchor(".spt-searchbox", el => show(
                    KEYS.spotlight, "TIP",
                    "Search any member — including yourself. Every player has a page.",
                    el, null));
            }
            return;
        }
        if (path.indexOf("/member/contests") === 0 || path === "/member" || path === "/member/") {
            if (!seen(KEYS.welcome)) {
                // welcome card wins; standings nudge defers to next visit
                markSeen(KEYS.welcome);  // one show only, even without dismiss
                show(KEYS.welcome, "WELCOME TO THE FELLOWSHIP",
                    "Welcome to the Fellowship. Tap HOW IT WORKS on any contest " +
                    "to see exactly how it pays — and tap any player to explore " +
                    "their season.", null, null, true);
                return;
            }
            if (!seen(KEYS.standings)) {
                whenAnchor("#pr-table-container tr[data-cid], #pr-table-container tbody tr", el => show(
                    KEYS.standings, "TIP",
                    "Tap any player to see their rounds — event by event, hole by hole.",
                    el, 64));
            }
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
