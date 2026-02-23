/* =========================================================
   TGF Transaction Tracker — Dashboard JavaScript
   ========================================================= */

let allItems = [];

// Columns that are searchable when "All columns" filter is selected
const SEARCHABLE_FIELDS = [
    "customer", "customer_email", "customer_phone",
    "item_name", "item_price", "city", "course", "handicap",
    "side_games", "tee_choice", "member_status", "golf_or_compete",
    "post_game", "order_id", "order_date", "event_date", "merchant",
];

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

function cell(value) {
    return escapeHtml(value || "—");
}

// ---------------------------------------------------------------------------
// Data fetching
// ---------------------------------------------------------------------------
async function fetchItems() {
    try {
        const res = await fetch("/api/items");
        allItems = await res.json();
        applyFilters();
    } catch (err) {
        console.error("Failed to fetch items:", err);
        document.getElementById("txn-body").innerHTML =
            '<tr class="empty-row"><td colspan="13">Failed to load data.</td></tr>';
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
function renderTable(items) {
    const tbody = document.getElementById("txn-body");

    if (!items.length) {
        tbody.innerHTML =
            '<tr class="empty-row"><td colspan="14">No items found. Click "Check Now" to scan your inbox.</td></tr>';
        document.getElementById("row-count").textContent = "";
        return;
    }

    tbody.innerHTML = items
        .map(
            (row) => `
        <tr data-id="${row.id}">
            <td>${cell(row.event_date || row.order_date)}</td>
            <td>${cell(row.customer)}</td>
            <td class="item-name-cell">${cell(row.item_name)}</td>
            <td class="price-cell">${cell(row.item_price)}</td>
            <td>${cell(row.city)}</td>
            <td>${cell(row.course)}</td>
            <td>${cell(row.handicap)}</td>
            <td>${cell(row.side_games)}</td>
            <td>${cell(row.tee_choice)}</td>
            <td>${cell(row.member_status)}</td>
            <td>${cell(row.golf_or_compete)}</td>
            <td><span class="order-id">${cell(row.order_id)}</span></td>
            <td>${cell(row.order_date)}</td>
            <td><button class="btn btn-danger" onclick="deleteItem(${row.id})">Delete</button></td>
        </tr>`
        )
        .join("");

    document.getElementById("row-count").textContent = `Showing ${items.length} item(s)`;
}

// ---------------------------------------------------------------------------
// Sorting
// ---------------------------------------------------------------------------
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
    const sortKey = document.getElementById("sort-select").value;

    let filtered = allItems;

    if (query) {
        if (filterCol) {
            // Search within a specific column only
            filtered = allItems.filter(
                (row) => (row[filterCol] || "").toLowerCase().includes(query)
            );
        } else {
            // Search across all searchable fields
            filtered = allItems.filter((row) =>
                SEARCHABLE_FIELDS.some(
                    (f) => (row[f] || "").toLowerCase().includes(query)
                )
            );
        }
    }

    renderTable(sortItems(filtered, sortKey));
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

            if (data.status === "running") return; // keep polling

            clearInterval(interval);
            btn.classList.remove("loading");
            btn.disabled = false;

            if (data.status === "error") {
                alert("Inbox check failed: " + data.error);
            }
            // Final refresh to catch any last items
            fetchItems();
            fetchStats();
        } catch (err) {
            clearInterval(interval);
            btn.classList.remove("loading");
            btn.disabled = false;
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
        "Item", "Price", "City", "Course", "Handicap",
        "Side Games", "Tee Choice", "Member Status", "Golf or Compete",
        "Post Game", "Returning/New", "Shirt Size", "Guest Name",
        "Net Points Race", "Gross Points Race", "City Match Play",
        "Order ID", "Total Amount", "Merchant",
    ];

    const fields = [
        "event_date", "order_date", "customer", "customer_email", "customer_phone",
        "item_name", "item_price", "city", "course",
        "handicap", "side_games", "tee_choice", "member_status",
        "golf_or_compete", "post_game", "returning_or_new", "shirt_size",
        "guest_name", "net_points_race", "gross_points_race", "city_match_play",
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
// Init
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
    fetchItems();
    fetchStats();
    checkConfig();

    document.getElementById("search-input").addEventListener("input", applyFilters);
    document.getElementById("filter-column").addEventListener("change", applyFilters);
    document.getElementById("sort-select").addEventListener("change", applyFilters);
    document.getElementById("btn-check-now").addEventListener("click", checkNow);
    document.getElementById("btn-export-csv").addEventListener("click", exportCSV);
    document.getElementById("btn-send-report").addEventListener("click", sendReport);

    // Column header sorting
    document.querySelectorAll("th.sortable").forEach((th) => {
        th.addEventListener("click", () => {
            const field = th.dataset.sort;
            const select = document.getElementById("sort-select");
            const current = select.value;
            // Toggle direction
            if (current === `${field}-asc`) {
                select.value = `${field}-desc`;
            } else {
                select.value = `${field}-asc`;
            }
            applyFilters();
        });
    });
});
