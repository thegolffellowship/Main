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
  border-radius: 13px; box-shadow: 0 8px 30px rgba(0,0,0,.16); padding: 13px 44px 13px 15px;
  max-width: 360px; }
.tgf-nudge.tgf-nudge-toast { position: fixed; left: 16px; right: 16px; bottom: 22px;
  margin-left: auto; margin-right: auto; }
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
        const dismiss = kind => {
            if (!card.isConnected) return;
            markSeen(key);
            beacon(kind || "dismiss", key);
            card.remove();
        };
        card.querySelector(".tgf-nudge-x").addEventListener("click", () => dismiss("dismiss"));
        return dismiss;
    }

    // R2.1 (Kerry-ratified #149): FOLLOW-THROUGH = DISMISSED. Doing the
    // thing the tip teaches retires the tip — it must never keep covering
    // the content the member just reached. Accepted trade-off on record:
    // an accidental follow-through burns the tip.
    function onFollowThrough(pairs, dismiss) {
        const fns = [];
        const fire = () => {
            dismiss("followthrough");
            fns.forEach(([el, ev, fn]) => el.removeEventListener(ev, fn));
        };
        pairs.forEach(([el, ev]) => {
            const fn = () => fire();
            fns.push([el, ev, fn]);
            el.addEventListener(ev, fn, { passive: true });
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
        const onSpotlight = path.indexOf("/member/spotlight") === 0
            || path === "/member" || path === "/member/";
        const onContests = path.indexOf("/member/contests") === 0;

        // Welcome card: first visit to the app, whichever member page they
        // land on (the landing is now Spotlight — Kerry 2026-07-14). It wins
        // and defers the page-specific tip to the next visit.
        if ((onSpotlight || onContests) && !seen(KEYS.welcome)) {
            markSeen(KEYS.welcome);  // one show only, even without dismiss
            // #155 (Kerry-ratified verbatim, incl. the trailing "...and
            // pays!" — intentional Kerry voice): copy updated for the
            // Spotlight-first landing.
            show(KEYS.welcome, "WELCOME TO THE FELLOWSHIP",
                "Welcome to the Fellowship. Start with your own name — your " +
                "season, your stats, your winnings are all in here. Then tap " +
                "LEADERBOARD for every Season Contest and how it all " +
                "works...and pays!", null, null, true);
            return;
        }

        // R2.3 (Kerry-ratified #149): a ?player=/#player= deep-link arrival
        // means they were SENT here with a purpose — no contextual tip.
        const deepLinked = /[?#&]player=/.test(location.search + location.hash)
            || /[?&]player=/.test((location.hash.split("?")[1] || ""));

        if (onSpotlight) {
            if (!seen(KEYS.spotlight) && !deepLinked) {
                whenAnchor(".spt-searchbox", el => {
                    const dismiss = show(
                        KEYS.spotlight, "TIP",
                        "Search any member — including yourself. Every player has a page.",
                        el, null);
                    // follow-through: executing a search retires the tip
                    const inp = el.querySelector("input");
                    const pairs = [];
                    if (inp) pairs.push([inp, "input"]);
                    const sug = document.getElementById("spt-suggest");
                    if (sug) pairs.push([sug, "click"]);
                    if (pairs.length) onFollowThrough(pairs, dismiss);
                });
            }
            return;
        }
        if (onContests) {
            if (!seen(KEYS.standings) && !deepLinked) {
                whenAnchor("#pr-table-container tr[data-cid], #pr-table-container tbody tr", el => {
                    // R2.2 (Kerry-ratified #149): on DATA TABLES always use
                    // the bottom-toast variant — never cover rows. Passing
                    // no anchor routes show() to the 5d toast.
                    const dismiss = show(
                        KEYS.standings, "TIP",
                        "Tap any player to see their rounds — event by event, hole by hole.",
                        null, null);
                    // follow-through: expanding a row retires the tip
                    const cont = document.getElementById("pr-table-container");
                    if (cont) onFollowThrough([[cont, "click"]], dismiss);
                });
            }
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
