/* =========================================================
   TGF Transaction Tracker — Shared Authentication
   Include this script on every page BEFORE page-specific scripts.
   Requires the login modal HTML and role badge/logout button in header.
   ========================================================= */

// Always start at the EVENTS page on fresh app launch (Kerry,
// 2026-07-08 — was Transactions). sessionStorage persists during
// tab/navigation but clears when the standalone PWA is fully closed
// or the browser tab is closed. Only REAL deep links (?txn=, ?item=,
// ?cid= — links from emails/notifications) keep a fresh launch in
// place; any other restored URL redirects. iOS resurrects the PWA's
// LAST url on relaunch (e.g. /customers?name=James%20Baker after
// tapping a customer link), and "any query string stays put" made
// that stale state the landing page (Kerry, 2026-07-08).
(function() {
    if ("scrollRestoration" in history) history.scrollRestoration = "manual";
    if (!sessionStorage.getItem("tgf_session_active")) {
        sessionStorage.setItem("tgf_session_active", "1");
        const isDeepLink = /[?&](txn|item|cid)=/.test(window.location.search);
        // Public member pages (/member/*) are their own destination — a
        // member opening the shared URL must never be bounced to /events
        // (which would just show them the login modal). (v2.53.0, Kerry)
        const isMemberPage = window.location.pathname.startsWith("/member");
        if (window.location.pathname !== "/events" && !isDeepLink && !isMemberPage) {
            window.location.replace("/events");
            return;
        }
    }
    window.scrollTo(0, 0);
})();

let currentRole = null;
let currentChapter = null;   // chapter-manager sessions carry their chapter

async function checkRole() {
    try {
        const res = await fetch("/api/auth/role");
        const data = await res.json();
        currentRole = data.role;
        currentChapter = data.chapter || null;
        return currentRole;
    } catch (err) {
        console.error("Failed to check role:", err);
        return null;
    }
}

function showLoginModal() {
    const overlay = document.getElementById("login-overlay");
    const pin = document.getElementById("login-pin");
    const err = document.getElementById("login-error");
    if (overlay) overlay.style.display = "flex";
    if (pin) { pin.value = ""; pin.focus(); }
    if (err) err.style.display = "none";
}

function hideLoginModal() {
    document.getElementById("login-overlay").style.display = "none";
}

async function handleLogin() {
    const pin = document.getElementById("login-pin").value.trim();
    if (!pin) return;

    const errorEl = document.getElementById("login-error");
    errorEl.style.display = "none";

    try {
        const res = await fetch("/api/auth/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pin }),
        });
        const data = await res.json();

        if (!res.ok) {
            errorEl.textContent = data.error || "Login failed.";
            errorEl.style.display = "block";
            return;
        }

        currentRole = data.role;
        currentChapter = data.chapter || null;
        hideLoginModal();
        updateRoleUI();
        updateNavForRole();
        if (typeof onAuthReady === "function") onAuthReady();
    } catch (err) {
        errorEl.textContent = "Connection error. Please try again.";
        errorEl.style.display = "block";
    }
}

async function handleLogout() {
    try {
        await fetch("/api/auth/logout", { method: "POST" });
    } catch (err) {
        console.error("Logout failed:", err);
    }
    currentRole = null;
    updateRoleUI();
    showLoginModal();
}

function updateRoleUI() {
    const badge = document.getElementById("role-badge");
    const logoutBtn = document.getElementById("btn-logout");
    if (!badge || !logoutBtn) return;
    if (currentRole) {
        badge.textContent = currentRole === "admin" ? "Admin"
            : currentRole === "view-only" ? "View Only"
            : (currentChapter ? currentChapter.toUpperCase() + " Manager" : "Manager");
        badge.className = "role-badge role-" + currentRole;
        badge.style.display = "";
        logoutBtn.style.display = "";
    } else {
        badge.style.display = "none";
        logoutBtn.style.display = "none";
    }
    // Show admin-only buttons
    const expandQtyBtn = document.getElementById("btn-expand-qty");
    if (expandQtyBtn) expandQtyBtn.style.display = (currentRole === "admin") ? "" : "none";
}

function updateNavForRole() {
    // Admin-only tabs (Payouts, Admin) show only for admin; view-only
    // sessions are reduced to EVENTS | CONTESTS | HANDICAPS (Kerry,
    // 2026-07-08) — other tabs hide and their pages redirect server-side.
    const VIEW_ONLY_TABS = ["/events", "/contests", "/handicaps"];
    // Shell v2 (nav-shell-070926): the same rules drive the dark nav's
    // desktop links and the mobile drawer links.
    document.querySelectorAll(".tab-nav a, .shell-nav-links a, .shell-drawer-nav a").forEach(link => {
        const href = link.getAttribute("href") || "";
        if (link.classList.contains("admin-nav")) {
            link.style.display = (currentRole === "admin") ? "" : "none";
        } else if (currentRole === "view-only") {
            link.style.display = VIEW_ONLY_TABS.includes(href) ? "" : "none";
        } else {
            link.style.display = "";
        }
    });
    // Header ops buttons are admin-only (Kerry, 2026-07-08): managers and
    // view-only never see Sync Events / Check RSVPs / Check Now anywhere.
    ["btn-sync", "btn-check-rsvps", "btn-check-now"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = (currentRole === "admin") ? "" : "none";
    });
    // Admin-only buttons that are conditionally SHOWN elsewhere (config
    // check / onAuthReady) — here we only force-hide for non-admins so a
    // role switch on the same page can't leave them visible.
    ["btn-send-report", "btn-match-venmo"].forEach(id => {
        const el = document.getElementById(id);
        if (el && currentRole !== "admin") el.style.display = "none";
    });
    // Show/hide admin sub-nav on pages where it is conditionally rendered (e.g. changelog)
    document.querySelectorAll(".admin-subnav.admin-nav").forEach(el => {
        el.style.display = (currentRole === "admin") ? "" : "none";
    });
    // Shell v2: role densities (drawer vs inline tabs, drawer role pill,
    // ops-row collapse) — no-op on legacy pages
    if (typeof window.shellApplyRole === "function") window.shellApplyRole(currentRole, currentChapter);
}

// Anonymous member-page traffic beacons (v2.62.0, Kerry): one 'open' per
// page load + a 'click' per button/link tap, labeled by the control's id
// or text. PII-free; admin reads the aggregates at /traffic.
function _memberTraffic() {
    const send = (event, detail) => {
        try {
            const body = JSON.stringify({ event, path: location.pathname, detail: detail || "" });
            if (navigator.sendBeacon) {
                navigator.sendBeacon("/api/member-metric", new Blob([body], { type: "application/json" }));
            } else {
                fetch("/api/member-metric", { method: "POST", keepalive: true,
                    headers: { "Content-Type": "application/json" }, body });
            }
        } catch (e) { /* analytics must never break the page */ }
    };
    send("open");
    document.addEventListener("click", e => {
        const el = e.target.closest("button, a");
        if (!el) return;
        const label = (el.textContent || el.id || "").replace(/\s+/g, " ").trim().slice(0, 60);
        if (label) send("click", label);
    }, true);
}

async function initAuth() {
    // Public member pages set window.MEMBER_MODE before this script loads:
    // no PIN, no login modal, no role. Page code runs with currentRole =
    // null so every manager/admin-only element stays hidden. (v2.53.0, Kerry)
    if (window.MEMBER_MODE) {
        currentRole = null;
        currentChapter = null;
        if (typeof onAuthReady === "function") onAuthReady();
        requestAnimationFrame(_setStickyOffsets);
        _memberTraffic();
        return;
    }
    const role = await checkRole();
    if (!role) {
        showLoginModal();
    } else {
        updateRoleUI();
        updateNavForRole();
        if (typeof onAuthReady === "function") onAuthReady();
        // Recalculate sticky offsets after browser reflows newly-shown buttons
        requestAnimationFrame(_setStickyOffsets);
    }

    // Bind login modal events (with null guards)
    const loginSubmit = document.getElementById("login-submit");
    const loginPin = document.getElementById("login-pin");
    const logoutBtn = document.getElementById("btn-logout");
    if (loginSubmit) loginSubmit.addEventListener("click", handleLogin);
    if (loginPin) loginPin.addEventListener("keydown", (e) => { if (e.key === "Enter") handleLogin(); });
    if (logoutBtn) logoutBtn.addEventListener("click", handleLogout);

}

// Sticky offsets — runs on every page that loads auth.js, regardless of initAuth()
function _setStickyOffsets() {
    const hdr = document.querySelector("header");
    const nav = document.querySelector(".tab-nav");
    if (hdr && nav) {
        nav.style.top = hdr.offsetHeight + "px";
    }
    const adminSub = document.querySelector(".admin-subnav");
    if (hdr && nav && adminSub) {
        adminSub.style.top = (hdr.offsetHeight + nav.offsetHeight) + "px";
    } else if (hdr && adminSub) {
        // Shell v2 pages have no .tab-nav — sub-nav sticks under the dark bar
        adminSub.style.top = hdr.offsetHeight + "px";
    }
}
// Run immediately, on DOM ready, on load, and on resize
_setStickyOffsets();
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", _setStickyOffsets);
}
window.addEventListener("load", _setStickyOffsets);
window.addEventListener("resize", _setStickyOffsets);

// Update version badge from version.js (runs on every page)
(function _setVersionBadge() {
    const update = () => {
        const el = document.getElementById("version-badge");
        if (el && window.TGF_VERSION) el.textContent = "v" + window.TGF_VERSION;
    };
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", update);
    } else {
        update();
    }
})();
