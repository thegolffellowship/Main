/* EVENT PHOTOS (Kerry 2026-10-29, #2460-J: "photos of champions this
   Saturday, and possibly photos on regular event nights too ... super
   simple"). Add photo -> phone camera -> optional caption + optional player
   tag -> Upload. Managers and admins only (the server checks the session).
   The picture is shrunk on the phone (1600 px long side, JPEG) before it is
   sent; the server re-encodes it. On the manager Live Scoring page the list
   shows below with "Spotlight" for a photo tagged with a player: that is the
   only way a photo becomes a Spotlight headshot.
   Usage: TGFEventPhotos.mount(el, {eventId, t, manage}) */
(function () {
    "use strict";
    var CSS = ".evp-btn{font:600 14px 'Helvetica Neue',Helvetica,Arial,sans-serif;padding:8px 16px;border-radius:999px;" +
        "border:2px solid #1B1B1B;background:#fff;color:#1B1B1B;cursor:pointer}" +
        ".evp-btn.go{background:#0d7556;border-color:#0d7556;color:#fff}" +
        ".evp-sheet{position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:1000;display:flex;align-items:flex-end;justify-content:center}" +
        ".evp-panel{background:#fff;width:100%;max-width:480px;border-radius:16px 16px 0 0;padding:16px 16px 24px;box-sizing:border-box;" +
        "font:15px 'Helvetica Neue',Helvetica,Arial,sans-serif;color:#1B1B1B;max-height:92vh;overflow:auto}" +
        ".evp-panel h3{font:700 18px Bitter,Georgia,serif;margin:0 0 10px}" +
        ".evp-panel img{width:100%;border-radius:10px;display:block;margin:8px 0}" +
        ".evp-panel input[type=text],.evp-panel select{width:100%;box-sizing:border-box;font:16px 'Helvetica Neue',Helvetica,Arial,sans-serif;" +
        "padding:10px;border:1px solid #D1D5DB;border-radius:10px;margin:6px 0}" +
        ".evp-row{display:flex;gap:8px;margin-top:12px}.evp-row .evp-btn{flex:1}" +
        ".evp-msg{font-size:13px;color:#4B5563;margin-top:8px}.evp-msg.err{color:#991B1B}" +
        ".evp-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px;margin-top:10px}" +
        ".evp-item{border:1px solid #E5E7EB;border-radius:10px;overflow:hidden;background:#fff;font-size:13px}" +
        ".evp-item img{width:100%;height:120px;object-fit:cover;display:block}" +
        ".evp-item .c{padding:6px 8px}.evp-item .evp-btn{padding:4px 10px;font-size:12px;margin:0 8px 8px}";

    function css() {
        if (document.getElementById("evp-css")) return;
        var s = document.createElement("style"); s.id = "evp-css"; s.textContent = CSS;
        document.head.appendChild(s);
    }
    function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
        return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]; }); }
    function q(opts) {
        return opts.eventId ? "event_id=" + encodeURIComponent(opts.eventId) : "t=" + encodeURIComponent(opts.t || "");
    }

    // shrink on the phone: 1600 px on the long side, JPEG 0.85
    function shrink(file) {
        return new Promise(function (resolve) {
            try {
                var url = URL.createObjectURL(file), img = new Image();
                img.onload = function () {
                    try {
                        var k = Math.min(1, 1600 / Math.max(img.width, img.height));
                        var c = document.createElement("canvas");
                        c.width = Math.round(img.width * k); c.height = Math.round(img.height * k);
                        c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
                        c.toBlob(function (b) { URL.revokeObjectURL(url); resolve(b || file); }, "image/jpeg", 0.85);
                    } catch (e) { resolve(file); }
                };
                img.onerror = function () { resolve(file); };
                img.src = url;
            } catch (e) { resolve(file); }
        });
    }

    function players(opts) {
        return fetch("/api/event-photos/players?" + q(opts), {credentials: "same-origin"})
            .then(function (r) { return r.ok ? r.json() : {players: []}; })
            .catch(function () { return {players: []}; });
    }

    function openSheet(opts, onDone) {
        css();
        var wrap = document.createElement("div"); wrap.className = "evp-sheet";
        wrap.innerHTML = '<div class="evp-panel" role="dialog" aria-label="Add photo"><h3>Add photo</h3>' +
            '<input type="file" accept="image/*" capture="environment" id="evp-file" style="display:none">' +
            '<button class="evp-btn" id="evp-pick" type="button" style="width:100%">Take or choose a photo</button>' +
            '<img id="evp-prev" alt="" hidden>' +
            '<input type="text" id="evp-cap" maxlength="200" placeholder="Caption (optional)">' +
            '<select id="evp-who"><option value="">Tag a player (optional, e.g. the champion)</option></select>' +
            '<div class="evp-row"><button class="evp-btn" id="evp-cancel" type="button">Cancel</button>' +
            '<button class="evp-btn go" id="evp-up" type="button" disabled>Upload</button></div>' +
            '<div class="evp-msg" id="evp-msg"></div></div>';
        document.body.appendChild(wrap);
        var file = null, $ = function (id) { return wrap.querySelector("#" + id); };
        var close = function () { wrap.remove(); };
        wrap.addEventListener("click", function (e) { if (e.target === wrap) close(); });
        $("evp-cancel").onclick = close;
        $("evp-pick").onclick = function () { $("evp-file").click(); };
        $("evp-file").onchange = function () {
            file = this.files && this.files[0];
            if (!file) return;
            var p = $("evp-prev"); p.src = URL.createObjectURL(file); p.hidden = false;
            $("evp-pick").textContent = "Retake";
            $("evp-up").disabled = false;
        };
        players(opts).then(function (j) {
            var sel = $("evp-who");
            (j.players || []).forEach(function (p) {
                var o = document.createElement("option"); o.value = p.customer_id; o.textContent = p.name;
                sel.appendChild(o);
            });
        });
        $("evp-up").onclick = function () {
            if (!file) return;
            var b = this; b.disabled = true; $("evp-msg").className = "evp-msg"; $("evp-msg").textContent = "Uploading…";
            shrink(file).then(function (blob) {
                var fd = new FormData();
                fd.append("photo", blob, "photo.jpg");
                fd.append("caption", $("evp-cap").value || "");
                fd.append("customer_id", $("evp-who").value || "");
                if (opts.eventId) fd.append("event_id", opts.eventId); else fd.append("t", opts.t || "");
                return fetch("/api/event-photos/upload", {method: "POST", body: fd, credentials: "same-origin"});
            }).then(function (r) { return r.json().then(function (j) { return {ok: r.ok, j: j}; }); })
              .then(function (x) {
                if (!x.ok || x.j.error) throw new Error(x.j.error || "Upload failed");
                $("evp-msg").textContent = "Saved.";
                setTimeout(close, 700);
                if (onDone) onDone(x.j.photo);
            }).catch(function (e) {
                b.disabled = false; $("evp-msg").className = "evp-msg err";
                $("evp-msg").textContent = (e && e.message) || "Upload failed. Try again.";
            });
        };
        $("evp-file").click();
    }

    function list(el, opts) {
        var box = el.querySelector(".evp-list");
        if (!box) return;
        fetch("/api/event-photos/" + encodeURIComponent(opts.eventId) + "?staff=1", {credentials: "same-origin"})
            .then(function (r) { return r.json(); })
            .then(function (j) {
                var rows = j.photos || [];
                box.innerHTML = rows.length ? rows.map(function (p) {
                    return '<div class="evp-item"><a href="' + esc(p.url) + '" target="_blank" rel="noopener">' +
                        '<img src="' + esc(p.url) + '" alt="' + esc(p.caption) + '" loading="lazy"></a>' +
                        '<div class="c">' + (esc(p.caption) || '<span style="color:#9CA3AF">No caption</span>') +
                        (p.player ? '<br><b>' + esc(p.player) + '</b>' : '') +
                        (p.promoted_at ? '<br><span style="color:#15803D">On the Spotlight ' + esc(p.promoted_at) + '</span>' : '') +
                        '</div>' + (p.customer_id ? '<button class="evp-btn" type="button" data-spot="' + esc(p.id) +
                        '" data-nm="' + esc(p.player || "this player") + '">' + (p.promoted_at ? "Spotlight again" : "Spotlight") +
                        '</button>' : '') + '</div>';
                }).join("") : '<div style="color:#6B7280;font-size:14px">No photos yet.</div>';
            }).catch(function () {});
    }

    function mount(el, opts) {
        if (!el) return;
        css();
        el.innerHTML = '<button class="evp-btn" type="button" data-evp-add>&#128247; Add photo</button>' +
            (opts.manage ? '<div class="evp-list"></div>' : '');
        el.addEventListener("click", function (e) {
            if (e.target.closest("[data-evp-add]")) { openSheet(opts, function () { if (opts.manage) list(el, opts); }); return; }
            var s = e.target.closest("[data-spot]");
            if (s && opts.manage) {
                if (!confirm("Make this photo " + s.dataset.nm + "'s Spotlight headshot? It is cropped square; " +
                             "an earlier Spotlight photo is kept on file.")) return;
                s.disabled = true;
                fetch("/api/event-photos/" + encodeURIComponent(opts.eventId) + "/" + encodeURIComponent(s.dataset.spot) +
                      "/spotlight", {method: "POST", credentials: "same-origin"})
                    .then(function (r) { return r.json(); })
                    .then(function (j) { if (j.error) alert(j.error); list(el, opts); })
                    .catch(function () { s.disabled = false; });
            }
        });
        if (opts.manage) list(el, opts);
    }

    window.TGFEventPhotos = {mount: mount, open: openSheet};
})();
