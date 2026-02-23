/* =========================================================
   TGF Transaction Tracker — Shared Authentication
   Include this script on every page BEFORE page-specific scripts.
   Requires the login modal HTML and role badge/logout button in header.
   ========================================================= */

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
    document.getElementById("login-overlay").style.display = "flex";
    document.getElementById("login-pin").value = "";
    document.getElementById("login-error").style.display = "none";
    document.getElementById("login-pin").focus();
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
}

function updateNavForRole() {
    // Hide Audit tab for non-admin roles
    document.querySelectorAll(".tab-nav a").forEach(link => {
        if (link.getAttribute("href") === "/audit") {
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

    // Bind login modal events
    document.getElementById("login-submit").addEventListener("click", handleLogin);
    document.getElementById("login-pin").addEventListener("keydown", (e) => {
        if (e.key === "Enter") handleLogin();
    });
    document.getElementById("btn-logout").addEventListener("click", handleLogout);
}
