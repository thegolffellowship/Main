/* =========================================================
   TGF Transaction Tracker — Dashboard JavaScript
   ========================================================= */

let allItems = [];
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
    "item_name", "item_price", "city", "course", "handicap",
    "side_games", "tee_choice", "member_status", "golf_or_compete",
    "post_game", "order_id", "order_date", "event_date", "merchant",
];

// Column definitions for toggle and rendering
const TABLE_COLUMNS = [
    { key: "event_date", label: "Event Date", default: true },
    { key: "customer", label: "Customer", default: true },
    { key: "item_name", label: "Item", default: true },
    { key: "item_price", label: "Price", default: true },
    { key: "city", label: "City", default: true },
    { key: "course", label: "Course", default: true },
    { key: "handicap", label: "Handicap", default: true },
    { key: "side_games", label: "Side Games", default: true },
    { key: "tee_choice", label: "Tee", default: true },
    { key: "member_status", label: "Status", default: true },
    { key: "golf_or_compete", label: "Type", default: true },
    { key: "order_id", label: "Order ID", default: true },
    { key: "order_date", label: "Order Date", default: true },
    { key: "actions", label: "Actions", default: true },
];

// Active category filter
let activeCategory = "all";

// Non-event keywords (memberships, merchandise, etc.)
const NON_EVENT_KEYWORDS = [
    "member", "membership", "shirt", "merch", "hat", "polo",
    "donation", "gift card", "season pass",
];

// Classify an item as "membership", "upcoming", or "past" event
function classifyItem(item) {
    const name = (item.item_name || "").toLowerCase();
    // Check for membership/merch
    for (const kw of NON_EVENT_KEYWORDS) {
        if (name.includes(kw)) return "membership";
    }
    // It's an event — check if upcoming or past
    const eventDate = item.event_date || "";
    if (eventDate) {
        const today = new Date().toISOString().split("T")[0];
        return eventDate >= today ? "upcoming" : "past";
    }
    // No event date but has course/month keywords → treat as past (no date known)
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
    document.getElementById("cat-count-all").textContent = allItems.length;
    document.getElementById("cat-count-upcoming").textContent = upcoming;
    document.getElementById("cat-count-past").textContent = past;
    document.getElementById("cat-count-membership").textContent = membership;
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

function cell(value, field, rowId) {
    const display = escapeHtml(value || "\u2014");
    return `<span class="cell-value" data-field="${field}" data-id="${rowId}" data-original="${escapeHtml(value || "")}">${display}</span>`;
}

// Cross-link cells: customer and item_name link to their respective pages
function linkedCell(value, field, rowId) {
    if (!value) return cell(value, field, rowId);
    const display = escapeHtml(value);
    if (field === "customer") {
        return `<a class="cell-link" href="/customers?name=${encodeURIComponent(value)}" title="View all transactions for ${display}">${display}</a>`;
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
        // All body cells in this column index
        document.querySelectorAll(`#txn-body tr`).forEach(tr => {
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
        const res = await fetch("/api/items");
        allItems = await res.json();
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
        document.getElementById("stat-items").textContent = s.total_items;
        document.getElementById("stat-orders").textContent = s.total_orders;
        document.getElementById("stat-spent").textContent = s.total_spent;
        document.getElementById("stat-earliest").textContent = s.earliest_date;
        document.getElementById("stat-latest").textContent = s.latest_date;
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

        // Show connector panel if connector is configured
        const connPanel = document.getElementById("connector-panel");
        if (data.connector) {
            connPanel.style.display = "block";
            // Set the full URL for the connector endpoint
            document.getElementById("connector-url").textContent =
                window.location.origin + "/api/connector/ingest";
        }

        // Show Send Report button if daily report is configured
        const reportBtn = document.getElementById("btn-send-report");
        if (data.daily_report) {
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
    if (row.transferred_from_id) return '<span class="status-tag status-tag-from-transfer">From Transfer</span>';
    return "";
}

function cellForColumn(key, row) {
    if (key === "event_date") return cell(row.event_date || row.order_date, "event_date", row.id);
    if (key === "customer") return linkedCell(row.customer, "customer", row.id);
    if (key === "item_name") return linkedCell(row.item_name, "item_name", row.id) + statusTag(row);
    if (key === "item_price") return cell(row.item_price, "item_price", row.id);
    if (key === "order_id") return `<span class="order-id">${cell(row.order_id, "order_id", row.id)}</span>`;
    if (key === "actions") {
        const status = row.transaction_status || "active";
        let btns = `<button class="btn btn-edit" onclick="openEditModal(${row.id})">Edit</button>`;
        if (status === "active" && !row.transferred_from_id) {
            btns += ` <button class="btn btn-credit" onclick="openCreditModal(${row.id})">Credit</button>`;
        } else if (status === "credited" || status === "transferred") {
            btns += ` <button class="btn btn-reverse" onclick="reverseCreditAction(${row.id})">Reverse</button>`;
        }
        if (currentRole === "admin") {
            btns += ` <button class="btn btn-danger" onclick="deleteItem(${row.id})">Delete</button>`;
        }
        return btns;
    }
    return cell(row[key], key, row.id);
}

function tdClass(key) {
    if (key === "item_name") return ' class="item-name-cell"';
    if (key === "item_price") return ' class="price-cell"';
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

    container.innerHTML = items.map(row => {
        const status = row.transaction_status || "active";
        const statusClass = status !== "active" ? ` row-${status}` : (row.transferred_from_id ? ' row-from-transfer' : '');
        const tag = statusTag(row);
        const sideGameLabel = classifyGameType(row.side_games);
        const tee = (row.tee_choice || "").trim();
        const topTags = `<span class="mc-type">${escapeHtml(sideGameLabel)}</span>${tee ? `<span class="mc-type mc-tee">${escapeHtml(tee)}</span>` : ''}`;

        // Detail fields
        const fields = [
            ["Date", row.event_date || row.order_date || "\u2014"],
            ["Price", row.item_price || "\u2014"],
            ["City", row.city || "\u2014"],
            ["Course", row.course || "\u2014"],
            ["Handicap", row.handicap || "\u2014"],
            ["Status", row.member_status || "\u2014"],
            ["Order ID", row.order_id || "\u2014"],
            ["Order Date", row.order_date || "\u2014"],
        ];

        // Action buttons
        let actionHtml = `<button class="btn btn-edit" onclick="openEditModal(${row.id})">Edit</button>`;
        if (status === "active" && !row.transferred_from_id) {
            actionHtml += ` <button class="btn btn-credit" onclick="openCreditModal(${row.id})">Credit</button>`;
        } else if (status === "credited" || status === "transferred") {
            actionHtml += ` <button class="btn btn-reverse" onclick="reverseCreditAction(${row.id})">Reverse</button>`;
        }
        if (currentRole === "admin") {
            actionHtml += ` <button class="btn btn-danger" onclick="deleteItem(${row.id})">Delete</button>`;
        }

        return `
        <div class="mobile-card${statusClass}" data-id="${row.id}">
            <div class="mobile-card-top" onclick="this.parentElement.classList.toggle('expanded')">
                <div class="mc-primary">
                    <span class="mc-customer">${escapeHtml(row.customer || "Unknown")}</span>
                    ${topTags} ${tag}
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
    }).join("");
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
    tbody.innerHTML = items
        .map(
            (row) => {
                const status = row.transaction_status || "active";
                const rowClass = status !== "active" ? ` class="row-${status}"` : (row.transferred_from_id ? ' class="row-from-transfer"' : '');
                return `
        <tr data-id="${row.id}"${rowClass}>
            ${ordered.map(col => `<td${tdClass(col.key)}>${cellForColumn(col.key, row)}</td>`).join("")}
        </tr>`;
            }
        )
        .join("");

    // Apply column visibility to newly rendered rows
    applyColumnVisibility();

    // Render mobile card view (shown/hidden via CSS media query)
    renderMobileCards(items);

    document.getElementById("row-count").textContent = `Showing ${items.length} item(s)`;
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
    const last = parts.pop();
    return (last + ", " + parts.join(" ")).toLowerCase();
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
    currentSortField = "event_date";
    currentSortDir = "desc";
    document.getElementById("sort-select").value = "event_date-desc";
    activeCategory = "all";
    document.querySelectorAll(".category-btn").forEach(b => b.classList.remove("active"));
    document.querySelector('.category-btn[data-category="all"]').classList.add("active");
    applyFilters();
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------
async function deleteItem(id) {
    if (!confirm("Delete this item?")) return;
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

function exportCSV() {
    if (!allItems.length) {
        alert("No items to export.");
        return;
    }

    const headers = [
        "Event Date", "Order Date", "Customer", "Email", "Phone",
        "Item", "Price", "Transaction Fees", "City", "Chapter", "Course",
        "Handicap", "Has Handicap",
        "Side Games", "Tee Choice", "Member Status", "Golf or Compete",
        "Post Game", "Returning/New", "Shirt Size", "Guest Name",
        "Date of Birth",
        "Net Points Race", "Gross Points Race", "City Match Play",
        "Order ID", "Total Amount", "Merchant",
    ];

    const fields = [
        "event_date", "order_date", "customer", "customer_email", "customer_phone",
        "item_name", "item_price", "transaction_fees", "city", "chapter", "course",
        "handicap", "has_handicap",
        "side_games", "tee_choice", "member_status",
        "golf_or_compete", "post_game", "returning_or_new", "shirt_size",
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
    "customer", "item_name", "item_price", "transaction_fees", "event_date",
    "city", "chapter", "course", "handicap", "has_handicap", "side_games",
    "tee_choice", "member_status", "golf_or_compete",
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
let creditType = "credit";  // "credit" or "transfer"
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
        `<strong>${escapeHtml(item.customer || "Unknown")}</strong> &mdash; ${escapeHtml(item.item_name || "")}<br>` +
        `Price: <strong>${escapeHtml(item.item_price || "$0")}</strong>`;

    // Reset UI
    document.querySelectorAll(".credit-type-btn").forEach(b => b.classList.toggle("active", b.dataset.type === "credit"));
    document.getElementById("credit-transfer-fields").style.display = "none";
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
        // Only refresh when no modal is open and no edit in progress
        const editOpen = document.getElementById("edit-overlay").style.display === "flex";
        const creditOpen = document.getElementById("credit-overlay").style.display === "flex";
        const loginOpen = document.getElementById("login-overlay").style.display === "flex";
        if (!editOpen && !creditOpen && !loginOpen && !activeEditor) {
            await fetchItems();
            await fetchStats();
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
            document.getElementById("credit-submit").textContent = creditType === "transfer" ? "Transfer" : "Apply Credit";
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
