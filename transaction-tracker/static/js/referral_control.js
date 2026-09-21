/* Who referred them — the attribution control, once.
 *
 * Named for the question Kerry actually asks (2026-09-21:
 * "Modal should probably be who referred them, not who brought
 * them"). The distinction matters now that naming someone can
 * trigger a referral fee: "brought" is a ride to the course,
 * "referred" is the thing TGF pays for.
 *
 * Kerry 2026-09-21: "going to the customers board then clicking info
 * then choosing is way too many steps." The answer was to put the same
 * control on the dashboard (in a modal) and on the Leads page band as
 * well as the customer card — which only stays honest if all three are
 * literally the same code. This module is that code.
 *
 * It owns the two vocabularies, the markup, the people index and the
 * POST. A host page supplies nothing but a customer object; if it
 * already has the roster loaded it can seed the index with setPeople()
 * and save the fetch.
 */
(function (global) {
    "use strict";

    var FOUND_US_LABELS = {
        facebook_ad: "Facebook ad", instagram: "Instagram", search: "Search",
        website: "Website", drove_by: "Drove by / saw us",
        event_flyer: "Flyer at an event", work: "Work / colleague",
        other: "Other", unknown: "Don't know"
    };
    var REFERRED_SOURCE_LABELS = {
        bought_spot: "bought their spot", coupon: "referral coupon",
        partner_request: "asked to play with them",
        lead_form: "said so on the form", member_claim: "told us",
        kerry: "Kerry"
    };

    // Self-contained: this runs on pages with no escapeHtml of their own.
    function esc(s) {
        return String(s === null || s === undefined ? "" : s)
            .replace(/&/g, "&amp;").replace(/</g, "&lt;")
            .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }

    var PEOPLE = null;        // [{customer_id, customer_name}]
    var peopleFetch = null;
    var RECORDS = {};         // cid -> the customer object last rendered
    var listeners = [];       // saved-callbacks, so a host can refresh

    function setPeople(list) {
        PEOPLE = (list || []).filter(function (c) {
            return c && c.customer_id && String(c.customer_name || "").trim();
        });
        return PEOPLE;
    }

    function ensurePeople() {
        if (PEOPLE) return Promise.resolve(PEOPLE);
        if (!peopleFetch) {
            peopleFetch = fetch("/api/customers/roster")
                .then(function (r) { return r.ok ? r.json() : []; })
                .then(function (list) { return setPeople(list); })
                .catch(function () { return setPeople([]); });
        }
        return peopleFetch;
    }

    function onSaved(fn) { if (typeof fn === "function") listeners.push(fn); }

    /* The one-line answer, on its own so re-rendering after a save is a
     * function call rather than a regex over the block's own markup. */
    function currentHtml(customer) {
        var name = String(customer.referred_by_name || "").trim();
        var src = customer.referred_by_source || "";
        var via = customer.found_us_via || "";
        if (name) {
            return "<strong>" + esc(name) + "</strong>" +
                (REFERRED_SOURCE_LABELS[src]
                    ? ' <span style="color:var(--text-muted);">(' +
                      esc(REFERRED_SOURCE_LABELS[src]) + ")</span>"
                    : "");
        }
        if (via) {
            return "<span>Not a referral — " +
                esc(FOUND_US_LABELS[via] || via) + "</span>";
        }
        return '<span style="color:var(--text-muted);">Nobody recorded yet</span>';
    }

    /* opts.heading  — override the "WHO BROUGHT THEM" label
     * opts.compact  — drop the top border/margin (for a modal body) */
    function render(customer, opts) {
        opts = opts || {};
        var cid = customer && customer.customer_id;
        if (!cid) return "";
        RECORDS[cid] = customer;
        var via = customer.found_us_via || "";
        var name = String(customer.referred_by_name || "").trim();
        var optionTags = Object.keys(FOUND_US_LABELS).map(function (k) {
            return '<option value="' + k + '"' + (k === via ? " selected" : "") +
                ">" + esc(FOUND_US_LABELS[k]) + "</option>";
        }).join("");
        var frame = opts.compact
            ? "max-width:500px;"
            : "margin-top:0.75rem; padding-top:0.5rem; " +
              "border-top:1px solid var(--border); max-width:500px;";
        return '<div style="' + frame + '" data-refblock="' + cid + '">' +
            '<div style="font-weight:600; font-size:0.7rem; color:var(--text-muted); ' +
                'text-transform:uppercase; letter-spacing:0.03em; margin-bottom:0.3rem;">' +
                esc(opts.heading || "Who referred them") + "</div>" +
            '<div style="font-size:0.82rem; min-height:1.2em;" data-refcurrent>' +
                currentHtml(customer) + "</div>" +
            '<div style="margin-top:0.45rem; display:flex; flex-wrap:wrap; gap:6px; align-items:center;">' +
                '<input list="ref-people-' + cid + '" data-refinput ' +
                    'placeholder="Type a member’s name…" autocomplete="off" ' +
                    'style="flex:1; min-width:170px; padding:5px 8px; font-size:0.82rem; ' +
                    'border:1px solid var(--border); border-radius:6px;">' +
                '<datalist id="ref-people-' + cid + '"></datalist>' +
                '<button type="button" class="btn-small" data-refsave>Save</button>' +
            "</div>" +
            '<div style="margin-top:0.4rem; display:flex; flex-wrap:wrap; gap:6px; align-items:center;">' +
                '<span style="font-size:0.75rem; color:var(--text-muted);">or not a referral:</span>' +
                '<select data-refvia style="padding:4px 8px; font-size:0.8rem; ' +
                    'border:1px solid var(--border); border-radius:6px;">' +
                    '<option value="">—</option>' + optionTags +
                "</select>" +
                ((name || via)
                    ? '<button type="button" class="btn-small" data-refclear ' +
                      'style="margin-left:auto;">Clear</button>' : "") +
            "</div>" +
            '<div data-refmsg style="margin-top:0.35rem; font-size:0.76rem; min-height:1em;"></div>' +
        "</div>";
    }

    function peopleOptions(excludeId) {
        return (PEOPLE || []).filter(function (c) {
            return c.customer_id !== excludeId;
        }).map(function (c) {
            return '<option value="' + esc(c.customer_name) +
                '" data-cid="' + c.customer_id + '"></option>';
        }).join("");
    }

    function resolveName(text, excludeId) {
        var t = String(text || "").trim().toLowerCase();
        if (!t) return null;
        var hit = (PEOPLE || []).find(function (c) {
            return c.customer_id !== excludeId &&
                String(c.customer_name || "").trim().toLowerCase() === t;
        });
        return hit ? hit.customer_id : null;
    }

    function post(cid, body, block) {
        var msg = block.querySelector("[data-refmsg]");
        msg.style.color = "var(--text-muted)";
        msg.textContent = "Saving…";
        return fetch("/api/customers/" + cid + "/referred-by", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        }).then(function (res) {
            return res.json().then(function (data) {
                if (!res.ok) throw new Error(data.error || ("HTTP " + res.status));
                return data;
            });
        }).then(function (data) {
            msg.style.color = "#15803D";
            msg.textContent = data.lead_created
                ? "Saved — added to the Lead Center."
                : "Saved.";
            var rec = RECORDS[cid] || { customer_id: cid };
            if ("referred_by_customer_id" in data) {
                rec.referred_by_customer_id = data.referred_by_customer_id;
                rec.referred_by_name = data.referred_by_name || "";
                rec.referred_by_source = data.referred_by_source || "";
            }
            if ("found_us_via" in data) rec.found_us_via = data.found_us_via || "";
            RECORDS[cid] = rec;
            var cur = block.querySelector("[data-refcurrent]");
            if (cur) cur.innerHTML = currentHtml(rec);
            listeners.forEach(function (fn) {
                try { fn(cid, data, rec); } catch (e) { /* a host's problem */ }
            });
            return data;
        }).catch(function (e) {
            msg.style.color = "#dc2626";
            msg.textContent = e.message;
            throw e;
        });
    }

    // Delegated once, at the document, so blocks drawn later — a modal
    // opened on click, a band re-rendered after a filter — just work.
    document.addEventListener("click", function (ev) {
        var block = ev.target.closest && ev.target.closest("[data-refblock]");
        if (!block) return;
        var cid = parseInt(block.getAttribute("data-refblock"), 10);
        if (ev.target.matches("[data-refsave]")) {
            var input = block.querySelector("[data-refinput]");
            var rid = resolveName(input.value, cid);
            if (!rid) {
                var msg = block.querySelector("[data-refmsg]");
                msg.style.color = "#dc2626";
                msg.textContent = input.value.trim()
                    ? "No customer by that name — pick one from the list."
                    : "Type a name first.";
                return;
            }
            post(cid, { referrer_customer_id: rid, source: "member_claim" }, block);
        } else if (ev.target.matches("[data-refclear]")) {
            post(cid, { referrer_customer_id: null, found_us_via: null }, block);
        }
    });
    document.addEventListener("change", function (ev) {
        var block = ev.target.closest && ev.target.closest("[data-refblock]");
        if (!block || !ev.target.matches("[data-refvia]")) return;
        var cid = parseInt(block.getAttribute("data-refblock"), 10);
        post(cid, { found_us_via: ev.target.value || null }, block);
    });
    // Fill the datalist the first time a picker is focused — building
    // 440 options for every card up front is wasted work.
    document.addEventListener("focusin", function (ev) {
        if (!ev.target.matches || !ev.target.matches("[data-refinput]")) return;
        var block = ev.target.closest("[data-refblock]");
        var cid = parseInt(block.getAttribute("data-refblock"), 10);
        var dl = block.querySelector("datalist");
        if (!dl || dl.innerHTML) return;
        ensurePeople().then(function () { dl.innerHTML = peopleOptions(cid); });
    });

    global.TGFRef = {
        render: render, currentHtml: currentHtml, post: post,
        setPeople: setPeople, ensurePeople: ensurePeople,
        peopleOptions: peopleOptions, resolveName: resolveName,
        onSaved: onSaved, record: function (cid) { return RECORDS[cid]; },
        FOUND_US_LABELS: FOUND_US_LABELS,
        REFERRED_SOURCE_LABELS: REFERRED_SOURCE_LABELS
    };
})(typeof window !== "undefined" ? window : this);
