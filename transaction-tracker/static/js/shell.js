/* =========================================================
   TGF Nav Shell v2 — nav-shell-070926 (Kerry-ratified #58)
   Drawer, ops bottom sheet, role densities. Loaded (defer)
   by _shell_nav.html; auth.js calls window.shellApplyRole
   after the role is known.
   ========================================================= */
(function () {
    "use strict";
    const $ = (id) => document.getElementById(id);

    // ── Drawer ───────────────────────────────────────────
    const burger = $("shell-burger"), drawer = $("shell-drawer"), scrim = $("shell-scrim");
    function openDrawer() {
        if (!drawer) return;
        drawer.classList.add("open"); scrim.classList.add("open");
        drawer.setAttribute("aria-hidden", "false");
        if (burger) burger.setAttribute("aria-expanded", "true");
    }
    function closeDrawer() {
        if (!drawer) return;
        drawer.classList.remove("open"); scrim.classList.remove("open");
        drawer.setAttribute("aria-hidden", "true");
        if (burger) burger.setAttribute("aria-expanded", "false");
    }
    if (burger) burger.addEventListener("click", openDrawer);
    if ($("shell-drawer-close")) $("shell-drawer-close").addEventListener("click", closeDrawer);
    if (scrim) scrim.addEventListener("click", closeDrawer);
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") { closeDrawer(); closeSheet(); }
    });

    // Drawer footer Log Out delegates to auth.js
    const drawerLogout = $("shell-drawer-logout");
    if (drawerLogout) drawerLogout.addEventListener("click", () => {
        if (typeof handleLogout === "function") handleLogout();
    });

    // ── Ops bottom sheet (view 1f) ───────────────────────
    const sheet = $("shell-sheet"), sheetScrim = $("shell-sheet-scrim"),
          sheetBody = $("shell-sheet-body"), opsRow = $("shell-ops"),
          moreBtn = $("shell-ops-more");
    function openSheet() {
        if (!sheet) return;
        sheet.classList.add("open"); sheetScrim.classList.add("open");
        sheet.setAttribute("aria-hidden", "false");
    }
    function closeSheet() {
        if (!sheet) return;
        sheet.classList.remove("open"); sheetScrim.classList.remove("open");
        sheet.setAttribute("aria-hidden", "true");
    }
    if (moreBtn) moreBtn.addEventListener("click", openSheet);
    if (sheetScrim) sheetScrim.addEventListener("click", closeSheet);
    if ($("shell-sheet-cancel")) $("shell-sheet-cancel").addEventListener("click", closeSheet);
    // Any action tapped in the sheet closes it (the action's own handler still runs)
    if (sheetBody) sheetBody.addEventListener("click", (e) => {
        if (e.target.closest("button, a")) closeSheet();
    });

    // Move [data-sheet] ops into the sheet on mobile, back on desktop.
    // Elements keep their ids so page handlers stay bound.
    const mq = window.matchMedia("(max-width: 768px)");
    let sheetItems = null; // captured once, in original order
    function placeOps() {
        if (!opsRow || !sheetBody) return;
        if (sheetItems === null) sheetItems = Array.from(opsRow.querySelectorAll("[data-sheet]"));
        if (mq.matches) {
            sheetItems.forEach(el => sheetBody.appendChild(el));
        } else {
            closeSheet();
            sheetItems.forEach(el => opsRow.insertBefore(el, moreBtn));
        }
        updateOpsVisibility();
    }
    // Hide the ops row (and ⋯ Actions) when the current role sees no ops.
    // "Visible" = the element's inline display isn't none (role gating on
    // these buttons is done via inline style, per the existing pages).
    function updateOpsVisibility() {
        if (!opsRow) return;
        const rowVisible = Array.from(opsRow.children).some(el =>
            el !== moreBtn && !el.classList.contains("shell-ops-divider")
            && el.style.display !== "none");
        const anySheet = sheetBody ? Array.from(sheetBody.children)
            .some(el => el.style.display !== "none") : false;
        if (moreBtn) moreBtn.style.display = (mq.matches && anySheet) ? "" : "none";
        opsRow.classList.toggle("shell-ops-empty", !rowVisible && !anySheet);
    }
    if (mq.addEventListener) mq.addEventListener("change", placeOps);
    placeOps();

    // ── Role densities (spec 1g + Kerry's drawer threshold rule) ──
    // Called by auth.js after the role is known. member pages never
    // reach here (member shell has no drawer and auth.js short-circuits).
    window.shellApplyRole = function (role) {
        const nav = $("shell-nav");
        if (!nav) return;
        // view-only sees 3 sections → inline tabs, no drawer (rule 2)
        nav.classList.toggle("shell-inline", role === "view-only");
        // Desktop ADMIN pill links to /accounting. It sits in
        // .shell-nav-right (outside auth.js's nav-link selectors), so we
        // gate it here; for admins it REPLACES the redundant role badge
        // on desktop (mobile keeps the badge in the bar — the drawer's
        // Admin row is the mobile route in).
        const adminLink = nav.querySelector(".shell-admin-link");
        if (adminLink) adminLink.style.display = (role === "admin") ? "" : "none";
        const badge = $("role-badge");
        if (badge) badge.classList.toggle("shell-badge-desktop-hide", role === "admin");
        // Sync the drawer's role pill from the canonical #role-badge
        const src = $("role-badge");
        document.querySelectorAll(".shell-drawer-role").forEach(el => {
            if (!src) return;
            el.textContent = src.textContent;
            el.className = src.className.replace("role-badge", "role-badge shell-drawer-role");
            el.style.display = src.style.display;
        });
        // Ops buttons were shown/hidden for this role — re-evaluate the row
        setTimeout(updateOpsVisibility, 0);
    };
})();
