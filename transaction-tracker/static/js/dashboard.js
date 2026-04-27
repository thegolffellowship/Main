/* =========================================================
   TGF Transaction Tracker — Dashboard JavaScript
   ========================================================= */

let allItems = [];
let reconciledItemMap = {};  // item_id → bank_deposit_id, from /api/reconciliation/reconciled-items
// currentRole is provided by auth.js

function classifyGameType(sideGames) {
    const sg = (sideGames || "").toUpperCase().trim();
    if (!sg || sg === "NONE" || sg === "\u2014") return "NONE";
    if (sg === "BOTH" || (sg.includes("NET") && sg.includes("GROSS"))) return "BOTH";
    if (sg.includes("NET")) return "NET";
    if (sg.includes("GROSS")) return "GROSS";
    return "NET";
}

// Sort state — independent of dropdown so header clicks always work
let currentSortField = "order_date";
let currentSortDir = "desc";

// Columns that are searchable when "All columns" filter is selected
const SEARCHABLE_FIELDS = [
    "customer", "customer_email", "customer_phone",
    "item_name", "item_price", "chapter", "course", "handicap",
    "side_games", "tee_choice", "user_status",
    "post_game", "order_id", "order_date", "merchant",
];

// Column definitions for toggle and rendering
const TABLE_COLUMNS = [
    { key: "order_date", label: "Order Date", default: true },
    { key: "customer", label: "Customer", default: true },
    { key: "item_name", label: "Item", default: true },
    { key: "item_price", label: "Price", default: true },
    { key: "handicap", label: "Handicap", default: true },
    { key: "side_games", label: "Side Games", default: true },
    { key: "holes", label: "Holes", default: true },
    { key: "tee_choice", label: "Tee", default: true },
    { key: "user_status", label: "Status", default: true },
    { key: "partner_request", label: "Partner Request", default: false },
    { key: "fellowship", label: "Fellowship", default: false },
    { key: "notes", label: "Notes", default: false },
    { key: "order_id", label: "Order ID", default: true },
    { key: "actions", label: "Actions", default: true },
];

// Active category filter
let activeCategory = "all";

// Non-event keywords (memberships, merchandise, etc.)
const NON_EVENT_KEYWORDS = [
    "member", "membership", "shirt", "merch", "hat", "polo",
    "donation", "gift card", "season pass",
];

// Placeholder merchants that are not real transactions (roster imports, manual entries, etc.)
const PLACEHOLDER_MERCHANTS = [
    "Roster Import", "Customer Entry", "RSVP Import", "RSVP Email Link",
];

// Classify an item as "membership", "upcoming", or "past" event
function classifyItem(item) {
    const name = (item.item_name || "").toLowerCase();
    // Check for membership/merch
    for (const kw of NON_EVENT_KEYWORDS) {
        if (name.includes(kw)) return "membership";
    }
    // It's an event — classify by order_date as a proxy
    const orderDate = item.order_date || "";
    if (orderDate) {
        const today = new Date().toISOString().split("T")[0];
        // Orders placed less than 30 days ago are likely upcoming events
        const cutoff = new Date(Date.now() - 30 * 86400000).toISOString().split("T")[0];
        return orderDate >= cutoff ? "upcoming" : "past";
    }
    return "past";
}

function updateCategoryCounts() {
    let upcoming = 0, past = 0, membership = 0;
    allItems.forEach(item => {
        const cat = classifyItem(item);
        if (cat === "upcoming") upcoming++;
        else if (cat === "past") past++;
        else if (cat === "membership") membership++;
    });
    const el = (id) => document.getElementById(id);
    if (el("cat-count-all")) el("cat-count-all").textContent = allItems.length;
    if (el("cat-count-upcoming")) el("cat-count-upcoming").textContent = upcoming;
    if (el("cat-count-past")) el("cat-count-past").textContent = past;
    if (el("cat-count-membership")) el("cat-count-membership").textContent = membership;
}

// Track which columns are visible (persisted in localStorage)
let visibleColumns = {};

// Track column order (persisted in localStorage)
let columnOrder = [];

function loadColumnOrder() {
    try {
        const saved = localStorage.getItem("tgf_column_order");
        if (saved) {
            const parsed = JSON.parse(saved);
            // Validate: must have same keys as TABLE_COLUMNS
            const allKeys = TABLE_COLUMNS.map(c => c.key);
            if (parsed.length === allKeys.length && parsed.every(k => allKeys.includes(k))) {
                columnOrder = parsed;
                return;
            }
        }
    } catch (e) {}
    columnOrder = TABLE_COLUMNS.map(c => c.key);
}

function saveColumnOrder() {
    try {
        localStorage.setItem("tgf_column_order", JSON.stringify(columnOrder));
    } catch (e) {}
}

function getOrderedColumns() {
    return columnOrder.map(key => TABLE_COLUMNS.find(c => c.key === key));
}

function loadColumnPrefs() {
    try {
        const saved = localStorage.getItem("tgf_visible_columns");
        if (saved) {
            visibleColumns = JSON.parse(saved);
            return;
        }
    } catch (e) {}
    // Default: all visible
    TABLE_COLUMNS.forEach(c => { visibleColumns[c.key] = c.default; });
}

function saveColumnPrefs() {
    try {
        localStorage.setItem("tgf_visible_columns", JSON.stringify(visibleColumns));
    } catch (e) {}
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function parsePrice(priceStr) {
    return parseFloat((priceStr || "0").replace(/[$,]/g, "")) || 0;
}

// Strip the " (credit transfer)" suffix from item_price for display only.
// Storage stays "$76.59 (credit transfer)"; merchant column + circled-T tag
// already convey the transfer context. Other suffixes like "(credit)" and
// "(comp)" are intentionally preserved.
function stripPriceSuffix(priceStr) {
    return (priceStr || "").replace(/\s*\(credit transfer\)\s*$/i, "");
}

function cell(value, field, rowId) {
    const display = escapeHtml(value || "\u2014");
    return `<span class="cell-value" data-field="${field}" data-id="${rowId}" data-original="${escapeHtml(value || "")}">${display}</span>`;
}

// Cross-link cells: customer and item_name link to their respective pages
function linkedCell(value, field, rowId, status) {
    if (!value) return cell(value, field, rowId);
    const display = escapeHtml(value);
    if (field === "customer") {
        const dn = escapeHtml(displayName(value, status));
        return `<a class="cell-link" href="/customers?name=${encodeURIComponent(value)}" title="View all transactions for ${display}">${dn}</a>`;
    }
    if (field === "item_name") {
        return `<a class="cell-link" href="/events?item=${encodeURIComponent(value)}" title="View event details for ${display}">${display}</a>`;
    }
    return cell(value, field, rowId);
}

// ---------------------------------------------------------------------------
// Column visibility
// ---------------------------------------------------------------------------
function buildColumnToggle() {
    const dropdown = document.getElementById("col-toggle-dropdown");
    dropdown.innerHTML = TABLE_COLUMNS
        .filter(c => c.key !== "actions")
        .map(c => {
            const checked = visibleColumns[c.key] !== false ? "checked" : "";
            return `<label><input type="checkbox" data-col="${c.key}" ${checked}> ${c.label}</label>`;
        }).join("");

    dropdown.querySelectorAll("input[type=checkbox]").forEach(cb => {
        cb.addEventListener("change", () => {
            visibleColumns[cb.dataset.col] = cb.checked;
            saveColumnPrefs();
            applyColumnVisibility();
            applyFilters();
        });
    });
}

function applyColumnVisibility() {
    const ordered = getOrderedColumns();
    ordered.forEach((col, idx) => {
        const visible = visibleColumns[col.key] !== false;
        // Header
        const th = document.querySelector(`th[data-col="${col.key}"]`);
        if (th) th.style.display = visible ? "" : "none";
        // All body cells in this column index (skip summary rows which use colspan)
        document.querySelectorAll(`#txn-body tr:not(.order-summary)`).forEach(tr => {
            const tds = tr.querySelectorAll("td");
            if (tds[idx]) tds[idx].style.display = visible ? "" : "none";
        });
    });
}

// ---------------------------------------------------------------------------
// Inline editing
// ---------------------------------------------------------------------------
let activeEditor = null;

function startEdit(span) {
    if (activeEditor) cancelEdit();
    const field = span.dataset.field;
    const rowId = span.dataset.id;
    const original = span.dataset.original;

    const input = document.createElement("input");
    input.type = "text";
    input.className = "cell-edit-input";
    input.value = original;
    input.dataset.field = field;
    input.dataset.id = rowId;
    input.dataset.original = original;

    span.replaceWith(input);
    input.focus();
    input.select();
    activeEditor = input;

    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            saveEdit(input);
        } else if (e.key === "Escape") {
            e.preventDefault();
            cancelEdit();
        } else if (e.key === "Tab") {
            e.preventDefault();
            saveEdit(input);
            // Move to next editable cell in the row
            const td = input.closest ? input.parentElement : null;
            if (td) {
                const nextTd = e.shiftKey ? td.previousElementSibling : td.nextElementSibling;
                if (nextTd) {
                    const nextSpan = nextTd.querySelector(".cell-value");
                    if (nextSpan) setTimeout(() => startEdit(nextSpan), 50);
                }
            }
        }
    });

    input.addEventListener("blur", () => {
        // Small delay to allow Tab/Enter handlers to fire first
        setTimeout(() => {
            if (activeEditor === input) saveEdit(input);
        }, 100);
    });
}

async function saveEdit(input) {
    const field = input.dataset.field;
    const rowId = input.dataset.id;
    const original = input.dataset.original;
    const newValue = input.value.trim();
    activeEditor = null;

    // No change — just revert
    if (newValue === original) {
        revertToSpan(input, original, field, rowId);
        return;
    }

    // Optimistically show the new value
    revertToSpan(input, newValue, field, rowId);

    try {
        const res = await fetch(`/api/items/${rowId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ [field]: newValue || null }),
        });
        if (!res.ok) throw new Error("Save failed");

        // Update local data
        const item = allItems.find((r) => r.id === parseInt(rowId));
        if (item) item[field] = newValue || null;
    } catch (err) {
        console.error("Failed to save edit:", err);
        // Revert on failure
        const span = document.querySelector(`.cell-value[data-id="${rowId}"][data-field="${field}"]`);
        if (span) {
            span.textContent = original || "\u2014";
            span.dataset.original = original;
        }
    }
}

function cancelEdit() {
    if (!activeEditor) return;
    const original = activeEditor.dataset.original;
    const field = activeEditor.dataset.field;
    const rowId = activeEditor.dataset.id;
    revertToSpan(activeEditor, original, field, rowId);
    activeEditor = null;
}

function revertToSpan(input, value, field, rowId) {
    const span = document.createElement("span");
    span.className = "cell-value";
    span.dataset.field = field;
    span.dataset.id = rowId;
    span.dataset.original = value || "";
    span.textContent = value || "\u2014";
    // Re-attach click listener so the cell stays editable (only for item_name)
    if (field === "item_name") {
        span.classList.add("cell-editable");
        span.addEventListener("click", () => startEdit(span));
    }
    if (input.parentElement) {
        input.replaceWith(span);
    }
}

// ---------------------------------------------------------------------------
// Data fetching
// ---------------------------------------------------------------------------
async function fetchItems() {
    try {
        const [res, reconRes] = await Promise.all([
            fetch("/api/items"),
            fetch("/api/reconciliation/reconciled-items").catch(() => ({ ok: false })),
        ]);
        const raw = await res.json();
        allItems = raw.filter(i => !PLACEHOLDER_MERCHANTS.includes(i.merchant) && i.transaction_status !== "rsvp_only");
        // Load reconciled item map for green dots (admin-only endpoint, fails gracefully)
        if (reconRes.ok) {
            try { reconciledItemMap = await reconRes.json(); } catch(_) {}
        }
        updateCategoryCounts();
        applyFilters();
    } catch (err) {
        console.error("Failed to fetch items:", err);
        document.getElementById("txn-body").innerHTML =
            '<tr class="empty-row"><td colspan="14">Failed to load data.</td></tr>';
    }
}

async function fetchStats() {
    try {
        const res = await fetch("/api/stats");
        const s = await res.json();
        const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
        set("stat-items", s.total_items);
        set("stat-orders", s.total_orders);
        set("stat-spent", s.total_spent);
        set("stat-earliest", s.earliest_date);
        set("stat-latest", s.latest_date);
    } catch (err) {
        console.error("Failed to fetch stats:", err);
    }
}

async function checkConfig() {
    try {
        const res = await fetch("/api/config-status");
        const data = await res.json();
        const alertEl = document.getElementById("config-alert");
        const msg = document.getElementById("config-alert-msg");

        if (alertEl && msg) {
            if (data.configured) {
                alertEl.style.display = "none";
            } else {
                alertEl.style.display = "block";
                if (!data.email && !data.ai) {
                    msg.textContent = "Email and Anthropic API key not configured. Set up your .env file.";
                } else if (!data.email) {
                    msg.textContent = "Email credentials not configured. Add them to your .env file.";
                } else {
                    msg.textContent = "Anthropic API key not configured. Add ANTHROPIC_API_KEY to your .env file.";
                }
            }
        }

        // Show connector panel if connector is configured
        const connPanel = document.getElementById("connector-panel");
        if (connPanel && data.connector) {
            connPanel.style.display = "block";
            const connUrl = document.getElementById("connector-url");
            if (connUrl) connUrl.textContent = window.location.origin + "/api/connector/ingest";
        }

        // Show Send Report button if daily report is configured
        const reportBtn = document.getElementById("btn-send-report");
        if (reportBtn && data.daily_report) {
            reportBtn.style.display = "inline-flex";
        }
    } catch (err) {
        console.error("Failed to check config:", err);
    }
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------
function statusTag(row) {
    const s = row.transaction_status || "active";
    if (s === "credited") return '<span class="status-tag status-tag-credited">Credit</span>';
    if (s === "transferred") return '<span class="status-tag status-tag-transferred">Transferred</span>';
    if (s === "refunded") return '<span class="status-tag status-tag-refunded">Refunded</span>';
    if (row.transferred_from_id) return '<span class="status-tag status-tag-from-transfer">From Transfer</span>';
    return "";
}

function couponTag(row) {
    const code = (row.coupon_code || "").trim();
    const amt = (row.coupon_amount || "").trim();
    if (!code && !amt) return "";
    const parts = [];
    if (code) parts.push(`Coupon: ${code}`);
    if (amt) parts.push(`-${amt.startsWith("$") ? amt : "$" + amt}`);
    const tip = parts.join(" ");
    return ` <span class="coupon-badge" title="${escapeHtml(tip)}">C</span>`;
}

function formatOrderDateTime(row) {
    const date = row.order_date || "\u2014";
    if (!row.order_time) return date;
    // Convert HH:MM:SS or HH:MM to 12-hour format
    const parts = row.order_time.split(":");
    let h = parseInt(parts[0], 10);
    const m = parts[1] || "00";
    const ampm = h >= 12 ? "PM" : "AM";
    if (h === 0) h = 12;
    else if (h > 12) h -= 12;
    return `${date} ${h}:${m} ${ampm}`;
}

function cellForChildPayment(key, row) {
    // Child payment rows show limited columns with muted styling
    if (key === "customer") {
        return `<span style="padding-left:1.5rem;color:#059669;font-size:0.78rem;font-weight:600;">+PAY</span> <span style="font-size:0.78rem;color:#6b7280;">${escapeHtml(row.side_games || row.notes || "Payment")}</span>`;
    }
    if (key === "item_price") return `<span style="font-size:0.82rem;">${escapeHtml(stripPriceSuffix(row.item_price) || "\u2014")}</span>`;
    if (key === "order_date") return `<span style="font-size:0.78rem;color:#6b7280;">${escapeHtml(row.order_date || "\u2014")}</span>`;
    if (key === "side_games") return `<span style="font-size:0.82rem;">${escapeHtml(row.side_games || "\u2014")}</span>`;
    if (key === "actions") {
        let btns = "";
        const status = row.transaction_status || "active";
        if (status === "active") {
            btns += `<button class="btn btn-credit" data-action="credit" data-id="${row.id}" style="font-size:0.65rem;">Credit</button>`;
        } else if (status === "credited" || status === "refunded") {
            btns += `<button class="btn btn-reverse" data-action="reverse" data-id="${row.id}" style="font-size:0.65rem;">Reverse</button>`;
        }
        if (currentRole === "admin") {
            btns += ` <button class="btn btn-danger" data-action="delete" data-id="${row.id}" style="font-size:0.65rem;" title="Delete">&times;</button>`;
        }
        return btns;
    }
    if (key === "item_name") return `<span style="font-size:0.78rem;color:#6b7280;">\u2014</span>`;
    return `<span style="font-size:0.78rem;color:#6b7280;">\u2014</span>`;
}

function _reconDot(row) {
    // Only visible for admin
    if (currentRole !== 'admin') return '';
    const s = row.transaction_status || "active";
    const uid = row.email_uid || "";
    const grey = '<span title="No bank match expected" style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#d1d5db;margin-right:4px;vertical-align:middle;"></span>';
    if (uid.startsWith("manual-comp") || s === "rsvp_only") return grey;
    if (s === "refunded" || s === "credited" || s === "transferred") return grey;
    // Green = reconciled (matched to bank deposit) — clickable to view match
    const depId = reconciledItemMap[row.id];
    if (depId) return `<a href="/accounting/reconcile?deposit_id=${depId}" title="Reconciled — click to view match" style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#16a34a;margin-right:4px;vertical-align:middle;cursor:pointer;" onclick="event.stopPropagation();"></a>`;
    // Yellow = awaiting bank match
    return '<span title="Awaiting bank match" style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#fbbf24;margin-right:4px;vertical-align:middle;"></span>';
}

function cellForColumn(key, row) {
    if (key === "order_date") {
        const display = formatOrderDateTime(row);
        return `${_reconDot(row)}<span class="cell-value" data-field="order_date" data-id="${row.id}" data-original="${row.order_date || ""}">${display}</span>`;
    }
    if (key === "customer") return linkedCell(row.customer, "customer", row.id, row.user_status);
    if (key === "item_name") return linkedCell(row.item_name, "item_name", row.id) + statusTag(row) + couponTag(row);
    if (key === "item_price") {
        // Display strips "(credit transfer)" suffix, but data-original keeps the
        // raw stored value so inline-edit save doesn't clobber it.
        const raw = row.item_price || "";
        const shown = stripPriceSuffix(raw) || "—";
        return `<span class="cell-value" data-field="item_price" data-id="${row.id}" data-original="${escapeHtml(raw)}">${escapeHtml(shown)}</span>`;
    }
    if (key === "order_id") return `<span class="order-id">${cell(row.order_id, "order_id", row.id)}</span>`;
    if (key === "actions") {
        const status = row.transaction_status || "active";
        let btns = "";
        if (currentRole === "admin") {
            btns += `<button class="btn btn-edit" data-action="edit" data-id="${row.id}">Edit</button>`;
        }
        if (status === "active" && !row.transferred_from_id) {
            btns += ` <button class="btn btn-credit" data-action="credit" data-id="${row.id}">Credit</button>`;
        } else if (status === "credited" || status === "transferred" || status === "refunded") {
            btns += ` <button class="btn btn-reverse" data-action="reverse" data-id="${row.id}">Reverse</button>`;
        }
        if (currentRole === "admin") {
            btns += ` <button class="btn btn-danger" data-action="delete" data-id="${row.id}" title="Delete">&times;</button>`;
        }
        return btns;
    }
    return cell(row[key], key, row.id);
}

function tdClass(key) {
    if (key === "customer") return ' class="customer-cell"';
    if (key === "item_name") return ' class="item-name-cell"';
    if (key === "item_price") return ' class="price-cell"';
    if (key === "side_games") return ' class="side-games-cell"';
    return "";
}

function renderHeaderRow() {
    const headerRow = document.getElementById("txn-header-row");
    const ordered = getOrderedColumns();
    headerRow.innerHTML = ordered.map(col => {
        const sortable = col.key !== "order_id" && col.key !== "actions" ? ' class="sortable"' : '';
        const sortAttr = sortable ? ` data-sort="${col.key}"` : '';
        return `<th${sortable}${sortAttr} data-col="${col.key}" draggable="true">${col.label}</th>`;
    }).join("");
    applyColumnVisibility();
    attachHeaderDrag();
    attachHeaderSort();
}

function renderMobileCard(row) {
    const status = row.transaction_status || "active";
    const statusClass = status !== "active" ? ` row-${status}` : (row.transferred_from_id ? ' row-from-transfer' : '');
    const tag = statusTag(row);
    const sideGameLabel = classifyGameType(row.side_games);
    const tee = (row.tee_choice || "").trim();
    const holes = (row.holes || "").trim();
    const topTags = `${holes ? `<span class="mc-type mc-holes">${escapeHtml(holes)}h</span>` : ''}<span class="mc-type">${escapeHtml(sideGameLabel)}</span>${tee ? `<span class="mc-type mc-tee">${escapeHtml(tee)}</span>` : ''}`;

    // Detail fields
    const fields = [
        ["Order Date", formatOrderDateTime(row)],
        ["Price", stripPriceSuffix(row.item_price) || "\u2014"],
        ["Total Amount", row.total_amount || "\u2014"],
        ["Transaction Fees", row.transaction_fees || "\u2014"],
        ["Coupon Code", row.coupon_code || "\u2014"],
        ["Coupon Amount", row.coupon_amount || "\u2014"],
        ["Handicap", row.handicap || "\u2014"],
        ["Status", row.user_status || "\u2014"],
        ["Holes", row.holes || "\u2014"],
        ["Partner Request", row.partner_request || "\u2014"],
        ["Fellowship", row.fellowship || "\u2014"],
        ["Notes", row.notes || "\u2014"],
        ["Order ID", row.order_id || "\u2014"],
    ];

    // Action buttons — Edit/Delete only for admin; Credit for all roles
    let actionHtml = "";
    if (currentRole === "admin") {
        actionHtml += `<button class="btn btn-edit" data-action="edit" data-id="${row.id}">Edit</button>`;
    }
    if (status === "active" && !row.transferred_from_id) {
        actionHtml += ` <button class="btn btn-credit" data-action="credit" data-id="${row.id}">Credit</button>`;
    } else if (status === "credited" || status === "transferred" || status === "refunded") {
        actionHtml += ` <button class="btn btn-reverse" data-action="reverse" data-id="${row.id}">Reverse</button>`;
    }
    if (currentRole === "admin") {
        actionHtml += ` <button class="btn btn-danger" data-action="delete" data-id="${row.id}" title="Delete">&times;</button>`;
    }

    return `
    <div class="mobile-card${statusClass}" data-id="${row.id}">
        <div class="mobile-card-top" data-action="toggle-expand">
            <div class="mc-primary">
                <span class="mc-customer">${escapeHtml(row.customer || "Unknown")}</span>
                ${topTags} ${tag}${couponTag(row)}
                <br><span class="mc-event">${escapeHtml(row.item_name || "\u2014")}</span>
            </div>
            <span class="mc-chevron">&#9656;</span>
        </div>
        <div class="mobile-card-details">
            <div class="mc-field-grid">
                ${fields.map(([l, v]) => `<div class="mc-field"><span class="mc-field-label">${l}</span><span class="mc-field-value">${escapeHtml(v)}</span></div>`).join("")}
            </div>
            <div class="mc-actions">${actionHtml}</div>
        </div>
    </div>`;
}

function renderMobileChildCard(child) {
    const status = child.transaction_status || "active";
    const statusCls = status !== "active" ? ` row-${status}` : "";
    const opacity = status !== "active" ? "opacity:0.6;" : "";
    let actionHtml = "";
    if (status === "active") {
        actionHtml += `<button class="btn btn-credit" data-action="credit" data-id="${child.id}" style="font-size:0.65rem;">Credit</button>`;
    } else if (status === "credited" || status === "refunded") {
        actionHtml += `<button class="btn btn-reverse" data-action="reverse" data-id="${child.id}" style="font-size:0.65rem;">Reverse</button>`;
    }
    if (currentRole === "admin") {
        actionHtml += ` <button class="btn btn-danger" data-action="delete" data-id="${child.id}" style="font-size:0.65rem;" title="Delete">&times;</button>`;
    }
    return `
    <div class="mobile-card child-payment-card${statusCls}" data-id="${child.id}" style="margin-left:1.2rem;border-left:3px solid #059669;background:#f0fdf4;${opacity}">
        <div class="mobile-card-top" data-action="toggle-expand">
            <div class="mc-primary">
                <span style="color:#059669;font-size:0.72rem;font-weight:600;">+PAY</span>
                <span class="mc-customer" style="font-size:0.82rem;">${escapeHtml(child.side_games || child.notes || "Payment")}</span>
                <span style="font-size:0.78rem;color:var(--text-muted);">${escapeHtml(child.item_price || "\u2014")}</span>
                ${status !== "active" ? `<span class="mc-type" style="background:#fef3c7;color:#92400e;font-size:0.65rem;">${status}</span>` : ""}
            </div>
        </div>
        <div class="mobile-card-details">
            <div class="mc-actions">${actionHtml}</div>
        </div>
    </div>`;
}

function renderMobileCards(items) {
    let container = document.getElementById("txn-mobile-cards");
    if (!container) {
        container = document.createElement("div");
        container.id = "txn-mobile-cards";
        container.className = "mobile-card-list";
        const wrapper = document.querySelector(".table-wrapper");
        wrapper.parentNode.insertBefore(container, wrapper.nextSibling);
    }

    if (!items.length) {
        container.innerHTML = '<div style="text-align:center; padding:2rem; color:var(--text-muted); font-style:italic;">No items found.</div>';
        return;
    }

    // Build parent → children map
    const childMap = new Map();
    const childIds = new Set();
    items.forEach(row => {
        if (row.parent_item_id) {
            const pid = String(row.parent_item_id);
            if (!childMap.has(pid)) childMap.set(pid, []);
            childMap.get(pid).push(row);
            childIds.add(row.id);
        }
    });

    function renderChildCards(parentId) {
        const children = childMap.get(String(parentId));
        if (!children || !children.length) return "";
        return children.map(c => renderMobileChildCard(c)).join("");
    }

    // Group items by order_id for order grouping (same logic as desktop)
    const orderGroups = new Map();
    items.forEach(row => {
        const oid = row.order_id;
        if (oid) {
            if (!orderGroups.has(oid)) orderGroups.set(oid, []);
            orderGroups.get(oid).push(row);
        }
    });

    const seen = new Set();
    let html = "";
    items.forEach(row => {
        // Skip child payment rows — rendered after their parent
        if (childIds.has(row.id)) return;

        const oid = row.order_id;
        if (oid && orderGroups.has(oid) && orderGroups.get(oid).filter(r => !childIds.has(r.id)).length > 1) {
            if (seen.has(oid)) return;
            seen.add(oid);
            const group = orderGroups.get(oid).filter(r => !childIds.has(r.id));
            const total = group.reduce((s, r) => s + parsePrice(r.item_price), 0);
            const customer = group[0].customer || "Unknown";
            const date = formatOrderDateTime(group[0]);
            const names = group.map(r => r.item_name || "\u2014").join(", ");
            const truncNames = names.length > 50 ? names.slice(0, 47) + "..." : names;

            html += `<div class="mobile-order-group" data-order-id="${escapeHtml(oid)}">
                <div class="mobile-order-summary" data-order-id="${escapeHtml(oid)}">
                    <div class="order-summary-left">
                        <span><span class="order-chevron">&#9662;</span> ${escapeHtml(customer)}</span>
                        <span style="font-weight:400;font-size:0.78rem;color:var(--text-muted);">${escapeHtml(truncNames)}</span>
                    </div>
                    <div class="order-summary-right">
                        <span>${group.length} items &mdash; $${total.toFixed(2)}</span><br>
                        <span style="font-weight:400;font-size:0.75rem;color:var(--text-muted);">${escapeHtml(date)}</span>
                    </div>
                </div>
                ${group.map(r => renderMobileCard(r) + renderChildCards(r.id)).join("")}
            </div>`;
        } else {
            html += renderMobileCard(row);
            html += renderChildCards(row.id);
        }
    });

    container.innerHTML = html;

    // Attach collapse/expand to mobile order summaries
    container.querySelectorAll(".mobile-order-summary").forEach(summary => {
        summary.addEventListener("click", () => {
            const oid = summary.dataset.orderId;
            const collapsed = summary.classList.toggle("collapsed");
            const group = summary.closest(".mobile-order-group");
            group.querySelectorAll(".mobile-card").forEach(card => {
                card.classList.toggle("order-item-hidden", collapsed);
            });
        });
    });
}

function renderTable(items) {
    const tbody = document.getElementById("txn-body");
    const visibleCount = getOrderedColumns().filter(c => visibleColumns[c.key] !== false).length;

    if (!items.length) {
        tbody.innerHTML =
            `<tr class="empty-row"><td colspan="${visibleCount}">No items found. Click "Check Now" to scan your inbox.</td></tr>`;
        document.getElementById("row-count").textContent = "";
        renderMobileCards([]);
        return;
    }

    const ordered = getOrderedColumns();

    // Build parent → children map for payment sub-rows
    const childMap = new Map();  // parent_item_id → [child rows]
    const childIds = new Set();
    items.forEach(row => {
        if (row.parent_item_id) {
            const pid = String(row.parent_item_id);
            if (!childMap.has(pid)) childMap.set(pid, []);
            childMap.get(pid).push(row);
            childIds.add(row.id);
        }
    });

    // Helper to render child payment rows after a parent
    function renderChildRows(parentId) {
        const children = childMap.get(String(parentId));
        if (!children || !children.length) return "";
        let childHtml = "";
        children.forEach(child => {
            const cStatus = child.transaction_status || "active";
            const cClass = cStatus !== "active" ? ` row-${cStatus}` : "";
            childHtml += `<tr data-id="${child.id}" class="child-payment-row${cClass}" style="background:#f0fdf4;">
                ${ordered.map(col => `<td${tdClass(col.key)}>${cellForChildPayment(col.key, child)}</td>`).join("")}
            </tr>`;
        });
        return childHtml;
    }

    // Group items by order_id for order grouping
    const orderGroups = new Map();
    const ungrouped = [];
    items.forEach(row => {
        const oid = row.order_id;
        if (oid) {
            if (!orderGroups.has(oid)) orderGroups.set(oid, []);
            orderGroups.get(oid).push(row);
        } else {
            ungrouped.push(row);
        }
    });

    // Build rows in display order (preserving sort order of first item per group)
    const seen = new Set();
    let html = "";
    items.forEach(row => {
        // Skip child payment rows — they're rendered after their parent
        if (childIds.has(row.id)) return;

        const oid = row.order_id;
        if (oid && orderGroups.has(oid) && orderGroups.get(oid).length > 1) {
            // Multi-item order — render summary + item rows on first encounter
            if (seen.has(oid)) return;
            seen.add(oid);
            const group = orderGroups.get(oid).filter(r => !childIds.has(r.id));
            const total = group.reduce((s, r) => s + parsePrice(r.item_price), 0);
            const names = group.map(r => r.item_name || "\u2014").join(", ");
            const truncNames = names.length > 60 ? names.slice(0, 57) + "..." : names;
            const customer = group[0].customer || "Unknown";
            const date = formatOrderDateTime(group[0]);

            // Summary row
            html += `<tr class="order-summary" data-order-id="${escapeHtml(oid)}">
                <td colspan="${visibleCount}">
                    <span class="order-chevron">&#9662;</span>
                    ${escapeHtml(date)} &mdash; <strong>${escapeHtml(customer)}</strong>
                    &mdash; ${group.length} items &mdash; $${total.toFixed(2)}
                    &mdash; <span style="color:var(--text-muted);font-weight:400;">${escapeHtml(truncNames)}</span>
                </td>
            </tr>`;

            // Item rows (indented) + their child payments
            group.forEach(r => {
                const status = r.transaction_status || "active";
                const statusCls = status !== "active" ? ` row-${status}` : (r.transferred_from_id ? ' row-from-transfer' : '');
                html += `<tr data-id="${r.id}" class="order-item${statusCls}" data-order-id="${escapeHtml(oid)}">
                    ${ordered.map(col => `<td${tdClass(col.key)}>${cellForColumn(col.key, r)}</td>`).join("")}
                </tr>`;
                html += renderChildRows(r.id);
            });
        } else {
            // Single-item order or no order_id — regular flat row
            const status = row.transaction_status || "active";
            const rowClass = status !== "active" ? ` class="row-${status}"` : (row.transferred_from_id ? ' class="row-from-transfer"' : '');
            html += `<tr data-id="${row.id}"${rowClass}>
                ${ordered.map(col => `<td${tdClass(col.key)}>${cellForColumn(col.key, row)}</td>`).join("")}
            </tr>`;
            html += renderChildRows(row.id);
        }
    });

    tbody.innerHTML = html;

    // Attach collapse/expand click handlers to summary rows
    tbody.querySelectorAll("tr.order-summary").forEach(summaryRow => {
        summaryRow.addEventListener("click", () => {
            const oid = summaryRow.dataset.orderId;
            const collapsed = summaryRow.classList.toggle("collapsed");
            tbody.querySelectorAll(`tr.order-item[data-order-id="${oid}"]`).forEach(itemRow => {
                itemRow.classList.toggle("order-item-hidden", collapsed);
            });
        });
    });

    // Apply column visibility to newly rendered rows
    applyColumnVisibility();

    // Render mobile card view (shown/hidden via CSS media query)
    renderMobileCards(items);

    document.getElementById("row-count").textContent = `Showing ${items.length} item(s)`;

    // Deep-link: highlight a specific transaction if ?txn= param is present
    if (window._pendingTxnHighlight) {
        const txnId = window._pendingTxnHighlight;
        const targetRow = tbody.querySelector(`tr[data-id="${txnId}"]`);
        if (targetRow) {
            window._pendingTxnHighlight = null;
            // If inside a collapsed order group, expand it first
            const oid = targetRow.dataset.orderId;
            if (oid) {
                const summary = tbody.querySelector(`tr.order-summary[data-order-id="${oid}"]`);
                if (summary && summary.classList.contains("collapsed")) {
                    summary.click();
                }
            }
            // Scroll and highlight
            setTimeout(() => {
                targetRow.scrollIntoView({ behavior: "smooth", block: "center" });
                targetRow.classList.add("txn-highlight");
                setTimeout(() => targetRow.classList.remove("txn-highlight"), 3000);
            }, 100);
            // Clean up URL
            window.history.replaceState({}, "", "/");
        }
    }
}

// ---------------------------------------------------------------------------
// Sorting
// ---------------------------------------------------------------------------

/** Extract last name from a full name string for sorting purposes. */
function getLastName(name) {
    const parts = String(name).trim().split(/\s+/);
    return parts.length > 1 ? parts[parts.length - 1] : parts[0];
}

/** Build a "LastName, FirstName..." key for consistent name sorting. */
function lastNameSortKey(name) {
    const s = String(name).trim();
    const parts = s.split(/\s+/);
    if (parts.length <= 1) return s.toLowerCase();
    const suffixes = new Set(["jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"]);
    let suffix = "";
    while (parts.length > 1 && suffixes.has(parts[parts.length - 1].toLowerCase())) {
        suffix = parts.pop() + " " + suffix;
    }
    const last = parts.pop() || "";
    return (last + ", " + parts.join(" ") + " " + suffix).toLowerCase().trim();
}

/** Format "First Last" → "Last, First" for display. Handles suffixes. */
function isElevatedStatus(status) {
    if (!status) return false;
    const s = String(status).trim().toUpperCase();
    return s === "MEMBER" || s === "MEMBER+" || s === "MANAGER" || s === "OWNER";
}

function displayName(name, status) {
    const s = String(name || "").trim();
    if (!s) return "\u2014";
    const elevated = isElevatedStatus(status);
    const parts = s.split(/\s+/);
    if (parts.length <= 1) return elevated ? s.toUpperCase() : s;
    const suffixes = new Set(["jr", "jr.", "sr", "sr.", "ii", "iii", "iv", "v"]);
    const suffixParts = [];
    while (parts.length > 1 && suffixes.has(parts[parts.length - 1].toLowerCase())) {
        suffixParts.unshift(parts.pop());
    }
    if (parts.length <= 1) return elevated ? s.toUpperCase() : s;
    const last = parts.pop();
    const lastDisplay = elevated ? last.toUpperCase() : last;
    return lastDisplay + ", " + parts.join(" ") + (suffixParts.length ? " " + suffixParts.join(" ") : "");
}

function sortItems(items, sortKey) {
    const [field, dir] = sortKey.split("-");
    const asc = dir === "asc";
    const sorted = [...items];

    sorted.sort((a, b) => {
        let va = a[field] || "";
        let vb = b[field] || "";

        // Numeric sort for price fields
        if (field === "item_price" || field === "total_amount") {
            va = parsePrice(va);
            vb = parsePrice(vb);
            return asc ? va - vb : vb - va;
        }

        // Name fields sort by last name
        if (field === "customer") {
            va = lastNameSortKey(va);
            vb = lastNameSortKey(vb);
            return asc ? va.localeCompare(vb) : vb.localeCompare(va);
        }

        // String sort
        va = String(va).toLowerCase();
        vb = String(vb).toLowerCase();
        if (va < vb) return asc ? -1 : 1;
        if (va > vb) return asc ? 1 : -1;

        // Tiebreaker: when sorting by order_date, use order_time then id (newest first)
        if (field === "order_date") {
            const ta = a.order_time || "";
            const tb = b.order_time || "";
            if (ta !== tb) return asc ? ta.localeCompare(tb) : tb.localeCompare(ta);
            // Final tiebreaker: higher id = more recent
            return asc ? (a.id - b.id) : (b.id - a.id);
        }
        return 0;
    });

    return sorted;
}

// ---------------------------------------------------------------------------
// Filtering
// ---------------------------------------------------------------------------
function applyFilters() {
    const query = document.getElementById("search-input").value.toLowerCase().trim();
    const filterCol = document.getElementById("filter-column").value;
    const sortKey = `${currentSortField}-${currentSortDir}`;

    let filtered = allItems;

    // Category filter
    if (activeCategory !== "all") {
        filtered = filtered.filter(item => classifyItem(item) === activeCategory);
    }

    if (query) {
        if (filterCol) {
            // Search within a specific column only
            filtered = filtered.filter(
                (row) => (row[filterCol] || "").toLowerCase().includes(query)
            );
        } else {
            // Search across all searchable fields
            filtered = filtered.filter((row) =>
                SEARCHABLE_FIELDS.some(
                    (f) => (row[f] || "").toLowerCase().includes(query)
                )
            );
        }
    }

    updateClearButton();
    renderTable(sortItems(filtered, sortKey));
}

function updateClearButton() {
    const query = document.getElementById("search-input").value.trim();
    const filterCol = document.getElementById("filter-column").value;
    const hasFilters = query || filterCol || activeCategory !== "all";
    document.getElementById("btn-clear-filters").classList.toggle("visible", !!hasFilters);
}

function clearAllFilters() {
    document.getElementById("search-input").value = "";
    document.getElementById("filter-column").value = "";
    currentSortField = "order_date";
    currentSortDir = "desc";
    document.getElementById("sort-select").value = "order_date-desc";
    activeCategory = "all";
    document.querySelectorAll(".category-btn").forEach(b => b.classList.remove("active"));
    document.querySelector('.category-btn[data-category="all"]').classList.add("active");
    applyFilters();
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------
async function deleteItem(id) {
    if (!confirm("Are you sure you want to delete this item? This action cannot be undone.")) return;
    try {
        await fetch(`/api/items/${id}`, { method: "DELETE" });
        allItems = allItems.filter((r) => r.id !== id);
        applyFilters();
        fetchStats();
    } catch (err) {
        console.error("Delete failed:", err);
        alert("Failed to delete item.");
    }
}

async function checkNow() {
    const btn = document.getElementById("btn-check-now");
    btn.classList.add("loading");
    btn.disabled = true;

    try {
        const res = await fetch("/api/check-now", { method: "POST" });
        const data = await res.json();
        if (data.error) {
            alert(data.error);
            btn.classList.remove("loading");
            btn.disabled = false;
            return;
        }

        // Poll for completion
        pollCheckStatus();
    } catch (err) {
        console.error("Check now failed:", err);
        alert("Failed to check inbox. See console for details.");
        btn.classList.remove("loading");
        btn.disabled = false;
    }
}

function pollCheckStatus() {
    const btn = document.getElementById("btn-check-now");
    const interval = setInterval(async () => {
        try {
            // Refresh the table on every poll so new items appear incrementally
            fetchItems();
            fetchStats();

            const res = await fetch("/api/check-status");
            const data = await res.json();

            // Show progress while running
            if (data.status === "running") {
                const p = data.progress || {};
                if (p.emails_fetched > 0) {
                    btn.textContent = `Parsing ${p.emails_parsed}/${p.emails_fetched}...`;
                }
                return; // keep polling
            }

            clearInterval(interval);
            btn.classList.remove("loading");
            btn.disabled = false;
            btn.textContent = "Check Now";

            if (data.status === "error") {
                alert("Inbox check failed:\n\n" + data.error);
            } else if (data.message) {
                const p = data.progress || {};
                if (p.items_saved > 0) {
                    alert(`Done! Saved ${p.items_saved} item(s) from ${p.emails_fetched} email(s).`);
                } else {
                    alert(data.message);
                }
            }
            // Final refresh to catch any last items
            fetchItems();
            fetchStats();
        } catch (err) {
            clearInterval(interval);
            btn.classList.remove("loading");
            btn.disabled = false;
            btn.textContent = "Check Now";
            console.error("Poll failed:", err);
        }
    }, 3000); // poll every 3 seconds
}

async function sendReport() {
    const btn = document.getElementById("btn-send-report");
    btn.disabled = true;
    btn.textContent = "Sending...";

    try {
        const res = await fetch("/api/report/send-now", { method: "POST" });
        const data = await res.json();
        if (data.error) {
            alert(data.error);
        } else {
            alert("Report sent to " + data.sent_to);
        }
    } catch (err) {
        console.error("Send report failed:", err);
        alert("Failed to send report.");
    } finally {
        btn.disabled = false;
        btn.textContent = "Send Report";
    }
}

async function expandQuantities() {
    const btn = document.getElementById("btn-expand-qty");
    if (!confirm("This will split any x2/x3 purchases into separate player entries. Continue?")) return;
    btn.disabled = true;
    btn.textContent = "Expanding...";

    try {
        const res = await fetch("/api/audit/expand-quantities", { method: "POST" });
        const data = await res.json();
        if (data.error) {
            alert("Error: " + data.error);
        } else if (data.created === 0) {
            alert("No quantity purchases found to expand.");
        } else {
            alert(`Done! Created ${data.created} new player entries:\n\n${data.details.join("\n")}`);
            loadData();
        }
    } catch (err) {
        console.error("Expand quantities failed:", err);
        alert("Failed to expand quantities.");
    } finally {
        btn.disabled = false;
        btn.textContent = "Expand Qty Purchases";
    }
}

function exportCSV() {
    if (!allItems.length) {
        alert("No items to export.");
        return;
    }

    const headers = [
        "Order Date", "Customer", "Email", "Phone",
        "Item", "Price", "Transaction Fees", "Coupon Code", "Coupon Amount", "Chapter", "Course",
        "Handicap", "Has Handicap",
        "Holes", "Side Games", "Tee Choice", "Member Status", "Golf or Compete",
        "Post Game", "Returning/New", "Shirt Size", "Guest Name",
        "Date of Birth",
        "Net Points Race", "Gross Points Race", "City Match Play",
        "Order ID", "Total Amount", "Merchant",
    ];

    const fields = [
        "order_date", "customer", "customer_email", "customer_phone",
        "item_name", "item_price", "transaction_fees", "coupon_code", "coupon_amount", "chapter", "course",
        "handicap", "has_handicap",
        "holes", "side_games", "tee_choice", "user_status",
        "post_game", "returning_or_new", "shirt_size",
        "guest_name", "date_of_birth",
        "net_points_race", "gross_points_race", "city_match_play",
        "order_id", "total_amount", "merchant",
    ];

    const rows = allItems.map((row) => fields.map((f) => row[f] || ""));

    const csvContent = [headers, ...rows]
        .map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(","))
        .join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `tgf_transactions_${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Column header drag-and-drop
// ---------------------------------------------------------------------------
let dragSrcCol = null;

function attachHeaderDrag() {
    const ths = document.querySelectorAll("#txn-header-row th[draggable]");
    ths.forEach(th => {
        th.addEventListener("dragstart", (e) => {
            dragSrcCol = th.dataset.col;
            th.classList.add("col-dragging");
            e.dataTransfer.effectAllowed = "move";
            e.dataTransfer.setData("text/plain", dragSrcCol);
        });
        th.addEventListener("dragover", (e) => {
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
            th.classList.add("col-drag-over");
        });
        th.addEventListener("dragleave", () => {
            th.classList.remove("col-drag-over");
        });
        th.addEventListener("drop", (e) => {
            e.preventDefault();
            th.classList.remove("col-drag-over");
            const targetCol = th.dataset.col;
            if (dragSrcCol && dragSrcCol !== targetCol) {
                const fromIdx = columnOrder.indexOf(dragSrcCol);
                const toIdx = columnOrder.indexOf(targetCol);
                if (fromIdx !== -1 && toIdx !== -1) {
                    columnOrder.splice(fromIdx, 1);
                    columnOrder.splice(toIdx, 0, dragSrcCol);
                    saveColumnOrder();
                    renderHeaderRow();
                    applyFilters();
                }
            }
        });
        th.addEventListener("dragend", () => {
            th.classList.remove("col-dragging");
            document.querySelectorAll("#txn-header-row th").forEach(h => h.classList.remove("col-drag-over"));
        });
    });
}

function syncSortDropdown() {
    const select = document.getElementById("sort-select");
    const desired = `${currentSortField}-${currentSortDir}`;
    // Only update dropdown if a matching option exists; otherwise leave it alone
    const hasOption = Array.from(select.options).some(o => o.value === desired);
    if (hasOption) {
        select.value = desired;
    } else {
        select.value = "";
    }
}

function attachHeaderSort() {
    document.querySelectorAll("th.sortable").forEach((th) => {
        th.addEventListener("click", () => {
            const field = th.dataset.sort;
            if (currentSortField === field) {
                currentSortDir = currentSortDir === "asc" ? "desc" : "asc";
            } else {
                currentSortField = field;
                currentSortDir = "asc";
            }
            syncSortDropdown();
            applyFilters();
        });
    });
}

// ---------------------------------------------------------------------------
// Authentication — provided by shared auth.js
// onAuthReady is called after successful login to re-render with role context
// ---------------------------------------------------------------------------
function onAuthReady() {
    applyFilters();
}

// ---------------------------------------------------------------------------
// Edit Modal
// ---------------------------------------------------------------------------
const EDIT_FIELDS = [
    "customer", "item_name", "item_price", "transaction_fees", "coupon_code", "coupon_amount",
    "chapter", "course", "handicap", "has_handicap", "side_games",
    "tee_choice", "user_status",
    "partner_request", "fellowship", "notes",
    "returning_or_new", "date_of_birth",
    "net_points_race", "gross_points_race", "city_match_play",
];

function openEditModal(itemId) {
    const item = allItems.find(r => r.id === itemId);
    if (!item) return;

    document.getElementById("edit-id").value = itemId;
    EDIT_FIELDS.forEach(field => {
        const input = document.getElementById("edit-" + field);
        if (input) input.value = item[field] || "";
    });

    document.getElementById("edit-overlay").style.display = "flex";
}

function closeEditModal() {
    document.getElementById("edit-overlay").style.display = "none";
}

async function handleEditSubmit(e) {
    e.preventDefault();
    const itemId = document.getElementById("edit-id").value;
    const item = allItems.find(r => r.id === parseInt(itemId));
    if (!item) return;

    // Collect changed fields only
    const changes = {};
    EDIT_FIELDS.forEach(field => {
        const input = document.getElementById("edit-" + field);
        if (!input) return;
        const newVal = input.value.trim() || null;
        const oldVal = item[field] || null;
        if (newVal !== oldVal) {
            changes[field] = newVal;
        }
    });

    if (Object.keys(changes).length === 0) {
        closeEditModal();
        return;
    }

    try {
        const res = await fetch(`/api/items/${itemId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(changes),
        });
        if (!res.ok) throw new Error("Save failed");

        // Update local data
        Object.assign(item, changes);
        closeEditModal();
        applyFilters();
    } catch (err) {
        console.error("Failed to save edit:", err);
        alert("Failed to save changes.");
    }
}

// ---------------------------------------------------------------------------
// Credit / Transfer Modal
// ---------------------------------------------------------------------------
let creditItemId = null;
let creditType = "credit";  // "credit", "transfer", or "refund"
let cachedEvents = null;

function buildEventPickerOptions(events) {
    const today = new Date().toISOString().split("T")[0];
    const upcoming = events.filter(e => e.event_date && e.event_date >= today).sort((a, b) => (a.event_date || "").localeCompare(b.event_date || ""));
    const past = events.filter(e => e.event_date && e.event_date < today).sort((a, b) => (b.event_date || "").localeCompare(a.event_date || ""));
    const noDate = events.filter(e => !e.event_date);
    let html = '<option value="">Select an event...</option>';
    if (upcoming.length) html += '<optgroup label="Upcoming">' + upcoming.map(e => `<option value="${escapeHtml(e.item_name)}">${escapeHtml(e.item_name)} (${e.event_date})</option>`).join("") + '</optgroup>';
    if (past.length) html += '<optgroup label="Past">' + past.map(e => `<option value="${escapeHtml(e.item_name)}">${escapeHtml(e.item_name)} (${e.event_date})</option>`).join("") + '</optgroup>';
    if (noDate.length) html += '<optgroup label="No Date">' + noDate.map(e => `<option value="${escapeHtml(e.item_name)}">${escapeHtml(e.item_name)}</option>`).join("") + '</optgroup>';
    return html;
}

async function loadEventsForPicker() {
    if (cachedEvents) return cachedEvents;
    try {
        const res = await fetch("/api/events");
        cachedEvents = await res.json();
        return cachedEvents;
    } catch { return []; }
}

async function openCreditModal(itemId) {
    const item = allItems.find(r => r.id === itemId);
    if (!item) return;
    creditItemId = itemId;
    creditType = "credit";

    // Populate info
    document.getElementById("credit-info").innerHTML =
        `<strong>${escapeHtml(displayName(item.customer || "Unknown", item.user_status))}</strong> &mdash; ${escapeHtml(item.item_name || "")}<br>` +
        `Price: <strong>${escapeHtml(item.item_price || "$0")}</strong>`;

    // Reset UI
    document.querySelectorAll(".credit-type-btn").forEach(b => b.classList.toggle("active", b.dataset.type === "credit"));
    document.getElementById("credit-transfer-fields").style.display = "none";
    document.getElementById("credit-refund-fields").style.display = "none";
    document.getElementById("credit-refund-method").value = "";
    document.getElementById("credit-note").value = "";
    document.getElementById("credit-submit").textContent = "Apply Credit";

    // Load events for dropdown — upcoming first, then past
    const events = await loadEventsForPicker();
    const select = document.getElementById("credit-target-event");
    select.innerHTML = buildEventPickerOptions(events);

    document.getElementById("credit-overlay").style.display = "flex";
}

function closeCreditModal() {
    document.getElementById("credit-overlay").style.display = "none";
    creditItemId = null;
}

async function submitCredit() {
    if (!creditItemId) return;
    const note = document.getElementById("credit-note").value.trim();

    try {
        if (creditType === "credit") {
            const res = await fetch(`/api/items/${creditItemId}/credit`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ note }),
            });
            if (!res.ok) throw new Error((await res.json()).error || "Credit failed");
        } else if (creditType === "refund") {
            const method = document.getElementById("credit-refund-method").value;
            if (!method) { alert("Please select a refund method."); return; }
            const res = await fetch(`/api/items/${creditItemId}/refund`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ method, note }),
            });
            if (!res.ok) throw new Error((await res.json()).error || "Refund failed");
        } else {
            const target = document.getElementById("credit-target-event").value;
            if (!target) { alert("Please select a target event."); return; }
            const res = await fetch(`/api/items/${creditItemId}/transfer`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ target_event: target, note }),
            });
            if (!res.ok) throw new Error((await res.json()).error || "Transfer failed");
        }
        closeCreditModal();
        cachedEvents = null;  // bust cache
        await fetchItems();
        await fetchStats();
    } catch (err) {
        alert(err.message);
    }
}

async function reverseCreditAction(itemId) {
    const item = allItems.find(r => r.id === itemId);
    if (!item) return;
    const status = item.transaction_status || "active";
    if (!confirm(`Reverse ${status} for ${item.customer}? This will restore the original transaction.`)) return;

    try {
        const res = await fetch(`/api/items/${itemId}/reverse-credit`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
        });
        if (!res.ok) throw new Error((await res.json()).error || "Reverse failed");
        cachedEvents = null;
        await fetchItems();
        await fetchStats();
    } catch (err) {
        alert(err.message);
    }
}

// ---------------------------------------------------------------------------
// Auto-refresh (keeps multiple users in sync)
// ---------------------------------------------------------------------------
let autoRefreshInterval = null;

function startAutoRefresh() {
    if (autoRefreshInterval) return;
    autoRefreshInterval = setInterval(async () => {
        try {
            // Only refresh when no modal is open and no edit in progress
            const editOverlay = document.getElementById("edit-overlay");
            const creditOverlay = document.getElementById("credit-overlay");
            const loginOverlay = document.getElementById("login-overlay");
            const editOpen = editOverlay && editOverlay.style.display === "flex";
            const creditOpen = creditOverlay && creditOverlay.style.display === "flex";
            const loginOpen = loginOverlay && loginOverlay.style.display === "flex";
            if (!editOpen && !creditOpen && !loginOpen && !activeEditor) {
                await fetchItems();
                await fetchStats();
            }
        } catch (err) {
            console.warn("Auto-refresh failed:", err);
        }
    }, 30000); // every 30 seconds
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", async () => {
    // Prevent browser from restoring previous scroll position; start at top
    if ("scrollRestoration" in history) history.scrollRestoration = "manual";
    window.scrollTo(0, 0);
    // Collapse any cards restored from bfcache
    document.querySelectorAll(".mobile-card.expanded").forEach(c => c.classList.remove("expanded"));

    // Auth (shared auth.js) — will call onAuthReady() after login
    await initAuth();

    loadColumnPrefs();
    loadColumnOrder();
    buildColumnToggle();
    renderHeaderRow();

    // Check for deep-link to a specific transaction (from Customers page)
    const _urlParams = new URLSearchParams(window.location.search);
    if (_urlParams.get("txn")) {
        window._pendingTxnHighlight = _urlParams.get("txn");
    }

    fetchItems();
    fetchStats();
    checkConfig();
    startAutoRefresh();

    document.getElementById("search-input").addEventListener("input", applyFilters);
    document.getElementById("filter-column").addEventListener("change", applyFilters);
    document.getElementById("sort-select").addEventListener("change", () => {
        const val = document.getElementById("sort-select").value;
        if (val) {
            const [f, d] = val.split("-");
            currentSortField = f;
            currentSortDir = d;
        }
        applyFilters();
    });
    document.getElementById("btn-check-now").addEventListener("click", checkNow);
    document.getElementById("btn-export-csv").addEventListener("click", exportCSV);
    document.getElementById("btn-clear-filters").addEventListener("click", clearAllFilters);
    document.getElementById("btn-send-report").addEventListener("click", sendReport);
    document.getElementById("btn-expand-qty").addEventListener("click", expandQuantities);

    // Edit modal
    document.getElementById("edit-form").addEventListener("submit", handleEditSubmit);
    document.getElementById("edit-cancel").addEventListener("click", closeEditModal);
    document.getElementById("edit-close").addEventListener("click", closeEditModal);
    document.getElementById("edit-overlay").addEventListener("click", (e) => {
        if (e.target === e.currentTarget) closeEditModal();
    });

    // Credit/Transfer modal
    document.getElementById("credit-submit").addEventListener("click", submitCredit);
    document.getElementById("credit-cancel").addEventListener("click", closeCreditModal);
    document.getElementById("credit-close").addEventListener("click", closeCreditModal);
    document.getElementById("credit-overlay").addEventListener("click", (e) => {
        if (e.target === e.currentTarget) closeCreditModal();
    });
    document.querySelectorAll(".credit-type-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            creditType = btn.dataset.type;
            document.querySelectorAll(".credit-type-btn").forEach(b => b.classList.toggle("active", b.dataset.type === creditType));
            document.getElementById("credit-transfer-fields").style.display = creditType === "transfer" ? "block" : "none";
            document.getElementById("credit-refund-fields").style.display = creditType === "refund" ? "block" : "none";
            const labels = { credit: "Apply Credit", transfer: "Transfer", refund: "Refund" };
            document.getElementById("credit-submit").textContent = labels[creditType] || "Apply Credit";
        });
    });

    // Category filter buttons
    document.querySelectorAll(".category-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            activeCategory = btn.dataset.category;
            document.querySelectorAll(".category-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            applyFilters();
        });
    });

    // Connector panel toggle
    const connHeader = document.getElementById("connector-header");
    if (connHeader) connHeader.addEventListener("click", () => {
        const body = document.getElementById("connector-body");
        if (body) body.classList.toggle("hidden");
    });

    // Delegated action handlers for table and mobile card buttons
    document.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-action]");
        if (!btn) return;
        const action = btn.dataset.action;
        const id = parseInt(btn.dataset.id);
        if (action === "edit") openEditModal(id);
        else if (action === "credit") openCreditModal(id);
        else if (action === "reverse") reverseCreditAction(id);
        else if (action === "delete") deleteItem(id);
        else if (action === "toggle-expand") btn.parentElement.classList.toggle("expanded");
    });

    // Column toggle dropdown
    const colBtn = document.getElementById("col-toggle-btn");
    const colDrop = document.getElementById("col-toggle-dropdown");
    colBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        colDrop.classList.toggle("open");
    });
    document.addEventListener("click", (e) => {
        if (!colDrop.contains(e.target) && e.target !== colBtn) {
            colDrop.classList.remove("open");
        }
    });
});

// When PWA resumes from bfcache, reset to clean state
window.addEventListener("pageshow", (e) => {
    if (e.persisted) {
        window.scrollTo(0, 0);
        document.querySelectorAll(".mobile-card.expanded").forEach(c => c.classList.remove("expanded"));
    }
});
