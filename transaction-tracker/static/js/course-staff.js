// COURSE CONTACTS panel (Kerry 2026-10-13, migration 0014): one course's people
// and roles, with Add / Make primary / Remove / Restore. Shared by the Courses
// page (inline under the course row) and the event editor (a modal, Kerry
// 10/13: "Manage Contacts link in the Quarry event didn't take me to a manage
// contacts modal or page"). Reads/writes /api/courses/<id>/staff (POST admin).
(function () {
    "use strict";
    const esc = s => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    if (!document.getElementById("tgf-cs-style")) {
        const st = document.createElement("style");
        st.id = "tgf-cs-style";
        st.textContent = `
.tgf-cs { white-space: normal; }
.tgf-cs .tgf-cs-files { font-size: 13px; margin-bottom: 6px; }
.tgf-cs table { width: 100%; border-collapse: collapse; font-size: 12.5px; margin-bottom: 8px; }
.tgf-cs th { text-align: left; font-size: 11px; color: #6B7280; font-weight: 600; }
.tgf-cs td, .tgf-cs th { padding: 4px 6px; border-bottom: 1px solid #EEE; white-space: normal; }
.tgf-cs tr.off td { color: #9CA3AF; }
.tgf-cs .tgf-cs-add { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.tgf-cs .tgf-cs-add input, .tgf-cs .tgf-cs-add select { font-size: 12.5px; padding: 4px 6px; }
.tgf-cs .tgf-cs-note { font-size: 11.5px; color: #6B7280; margin-top: 4px; }
.tgf-cs-ov { position: fixed; inset: 0; background: rgba(0,0,0,.45); z-index: 10050; display: flex; align-items: flex-start; justify-content: center; padding: 6vh 12px; overflow-y: auto; }
.tgf-cs-modal { background: #fff; border-radius: 12px; max-width: 760px; width: 100%; padding: 18px 20px; box-shadow: 0 10px 40px rgba(0,0,0,.25); }
.tgf-cs-modal h3 { margin: 0 0 10px; font-family: 'Bitter', serif; font-size: 18px; display: flex; justify-content: space-between; align-items: center; }
.tgf-cs-modal h3 button { font-size: 20px; line-height: 1; background: none; border: none; cursor: pointer; color: #6B7280; }`;
        document.head.appendChild(st);
    }

    async function render(box, courseId, opts) {
        opts = opts || {};
        box.classList.add("tgf-cs");
        box.innerHTML = '<div style="color:#94a3b8;padding:6px 0;">Loading contacts…</div>';
        const res = await fetch(`/api/courses/${courseId}/staff`);
        const d = await res.json().catch(() => ({}));
        if (!res.ok) { box.innerHTML = `<div style="color:#b91c1c;">${esc(d.error || "Could not load contacts.")}</div>`; return; }
        const roles = d.roles || [], labels = d.role_labels || {};
        const roleOpts = sel => roles.map(r => `<option value="${r}"${r === sel ? " selected" : ""}>${esc(labels[r] || r)}</option>`).join("");
        const rows = (d.staff || []).map(st => `
            <tr class="${st.active ? "" : "off"}" data-cid="${st.customer_id}" data-role="${esc(st.role)}">
                <td>${esc(st.name)}</td>
                <td>${esc(st.role_label)}${st.notes ? `<div style="font-size:11px;color:#6B7280;">${esc(st.notes)}</div>` : ""}</td>
                <td>${esc(st.email || "—")}${st.phone ? `<div style="font-size:11px;color:#6B7280;">${esc(st.phone)}</div>` : ""}</td>
                <td style="text-align:center;">${st.is_primary ? "<b style='color:#E87C3E;'>PRIMARY</b>" : (st.active ? '<button class="cs-make-primary">Make primary</button>' : "")}</td>
                <td>${st.active ? '<button class="cs-deactivate">Remove</button>' : '<button class="cs-reactivate">Restore</button>'}</td>
            </tr>`).join("");
        const files = d.print_to
            ? `Course Files go to <b>${esc(d.print_to)}</b>${(d.print_cc || []).length ? ", cc " + esc(d.print_cc.join(", ")) : ""} (and you).`
            : `<span style="color:#b45309;">Course Files can't be sent yet: ${esc(d.print_why || "no primary TGF contact")}.</span>`;
        box.innerHTML = `
            <div class="tgf-cs-files">${files}</div>
            <table><thead><tr><th>Name</th><th>Role</th><th>Email</th><th>Primary</th><th></th></tr></thead>
                <tbody>${rows || '<tr><td colspan="5" style="color:#94a3b8;">No contacts on file yet.</td></tr>'}</tbody></table>
            <div class="tgf-cs-add">
                <input class="cs-name" placeholder="First Last">
                <input class="cs-email" type="email" placeholder="email">
                <input class="cs-phone" placeholder="phone (optional)">
                <select class="cs-role">${roleOpts("tgf_contact")}</select>
                <label style="font-size:12px;display:flex;align-items:center;gap:4px;"><input type="checkbox" class="cs-primary"> primary</label>
                <button class="cs-add">Add contact</button>
            </div>
            <div class="tgf-cs-note">The primary TGF contact gets the Course Files; other TGF contacts are CC'd. One person can hold several roles (add them once per role). Course contacts never get member emails.</div>`;
        const again = () => { render(box, courseId, opts); if (opts.onChange) opts.onChange(); };
        const post = async body => {
            const r = await fetch(`/api/courses/${courseId}/staff`, { method: "POST",
                headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
            const j = await r.json().catch(() => ({}));
            if (!r.ok) { alert(j.refused || j.error || "Not saved."); return false; }
            return true;
        };
        box.querySelector(".cs-add").addEventListener("click", async () => {
            const name = box.querySelector(".cs-name").value.trim();
            if (!name) { alert("Enter the person's first and last name."); return; }
            if (await post({ name, email: box.querySelector(".cs-email").value.trim(),
                             phone: box.querySelector(".cs-phone").value.trim(),
                             role: box.querySelector(".cs-role").value,
                             is_primary: box.querySelector(".cs-primary").checked })) again();
        });
        box.querySelectorAll("tr[data-cid]").forEach(tr => {
            const base = { customer_id: parseInt(tr.dataset.cid), role: tr.dataset.role };
            const on = (sel, body, ask) => { const b = tr.querySelector(sel); if (b) b.addEventListener("click", async () => {
                if (ask && !confirm(ask)) return;
                if (await post({ ...base, ...body })) again(); }); };
            on(".cs-make-primary", { is_primary: true });
            on(".cs-deactivate", { active: false }, "Remove this contact from the course? (Kept in history; Restore brings it back.)");
            on(".cs-reactivate", { active: true });
        });
    }

    function modal(courseId, courseName, onClose) {
        const ov = document.createElement("div");
        ov.className = "tgf-cs-ov";
        ov.innerHTML = `<div class="tgf-cs-modal" role="dialog" aria-label="Course contacts">
            <h3><span>Contacts · ${esc(courseName || "")}</span><button type="button" aria-label="Close">&times;</button></h3>
            <div class="tgf-cs-body"></div></div>`;
        const close = () => { ov.remove(); document.removeEventListener("keydown", onKey); if (onClose) onClose(); };
        const onKey = e => { if (e.key === "Escape") close(); };
        ov.addEventListener("click", e => { if (e.target === ov) close(); });
        ov.querySelector("h3 button").addEventListener("click", close);
        document.addEventListener("keydown", onKey);
        document.body.appendChild(ov);
        render(ov.querySelector(".tgf-cs-body"), courseId);
    }

    window.tgfCourseStaffPanel = render;
    window.tgfCourseStaffModal = modal;
})();
