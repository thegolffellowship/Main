/* =========================================================
   TGF Transaction Tracker — Shared Authentication
   Include this script on every page BEFORE page-specific scripts.
   Requires the login modal HTML and role badge/logout button in header.
   ========================================================= */

// Always start at the Transactions page on fresh app launch.
// sessionStorage persists during tab/navigation but clears when the
// standalone PWA is fully closed or the browser tab is closed.
(function() {
    if ("scrollRestoration" in history) history.scrollRestoration = "manual";
    if (!sessionStorage.getItem("tgf_session_active")) {
        sessionStorage.setItem("tgf_session_active", "1");
        if (window.location.pathname !== "/") {
            window.location.replace("/");
            return;
        }
    }
    window.scrollTo(0, 0);
})();

let currentRole = null;

async function checkRole() {
    try {
        const res = await fetch("/api/auth/role");
        const data = await res.json();
        currentRole = data.role;
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
        badge.textContent = currentRole === "admin" ? "Admin" : "Manager";
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
    // Hide admin-only tabs for non-admin roles
    document.querySelectorAll(".tab-nav a").forEach(link => {
        const href = link.getAttribute("href");
        if (href === "/audit" || href === "/matrix" || href === "/database") {
            link.style.display = (currentRole === "admin") ? "" : "none";
        }
    });
}

async function initAuth() {
    const role = await checkRole();
    if (!role) {
        showLoginModal();
    } else {
        updateRoleUI();
        updateNavForRole();
        if (typeof onAuthReady === "function") onAuthReady();
    }

    // Bind login modal events (with null guards)
    const loginSubmit = document.getElementById("login-submit");
    const loginPin = document.getElementById("login-pin");
    const logoutBtn = document.getElementById("btn-logout");
    if (loginSubmit) loginSubmit.addEventListener("click", handleLogin);
    if (loginPin) loginPin.addEventListener("keydown", (e) => { if (e.key === "Enter") handleLogin(); });
    if (logoutBtn) logoutBtn.addEventListener("click", handleLogout);
}
