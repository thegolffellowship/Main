/* =========================================================
   Transaction Tracker — Dashboard JavaScript
   ========================================================= */

let allTransactions = [];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function parseAmount(amountStr) {
    return parseFloat((amountStr || "0").replace(/[$,]/g, "")) || 0;
}

// ---------------------------------------------------------------------------
// Data fetching
// ---------------------------------------------------------------------------
async function fetchTransactions() {
    try {
        const res = await fetch("/api/transactions");
        allTransactions = await res.json();
        renderTable(allTransactions);
    } catch (err) {
        console.error("Failed to fetch transactions:", err);
        document.getElementById("txn-body").innerHTML =
            '<tr class="empty-row"><td colspan="8">Failed to load transactions.</td></tr>';
    }
}

async function fetchStats() {
    try {
        const res = await fetch("/api/stats");
        const stats = await res.json();
        document.getElementById("stat-count").textContent = stats.total_count;
        document.getElementById("stat-spent").textContent = stats.total_spent;
        document.getElementById("stat-earliest").textContent = stats.earliest_date;
        document.getElementById("stat-latest").textContent = stats.latest_date;
    } catch (err) {
        console.error("Failed to fetch stats:", err);
    }
}

async function checkConfig() {
    try {
        const res = await fetch("/api/config-status");
        const data = await res.json();
        const alert = document.getElementById("config-alert");
        alert.style.display = data.configured ? "none" : "block";
    } catch (err) {
        console.error("Failed to check config:", err);
    }
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------
function renderTable(transactions) {
    const tbody = document.getElementById("txn-body");

    if (!transactions.length) {
        tbody.innerHTML =
            '<tr class="empty-row"><td colspan="8">No transactions found. Click "Check Now" to scan your inbox.</td></tr>';
        document.getElementById("row-count").textContent = "";
        return;
    }

    tbody.innerHTML = transactions
        .map(
            (txn) => `
        <tr data-id="${txn.id}">
            <td>${escapeHtml(txn.date || "")}</td>
            <td>${escapeHtml(txn.customer || "—")}</td>
            <td>${escapeHtml(txn.merchant || "")}</td>
            <td class="amount-cell">${escapeHtml(txn.amount || "")}</td>
            <td><span class="order-id">${escapeHtml(txn.order_id || "—")}</span></td>
            <td><div class="items-cell">${renderItems(txn.items)}</div></td>
            <td>${escapeHtml(txn.subject || "")}</td>
            <td><button class="btn btn-danger" onclick="deleteTxn(${txn.id})">Delete</button></td>
        </tr>`
        )
        .join("");

    document.getElementById("row-count").textContent = `Showing ${transactions.length} transaction(s)`;
}

function renderItems(items) {
    if (!items || !items.length) return '<span style="color:var(--text-muted)">—</span>';
    return items
        .slice(0, 5)
        .map((item) => `<span class="item-tag" title="${escapeHtml(item)}">${escapeHtml(item)}</span>`)
        .join("");
}

// ---------------------------------------------------------------------------
// Sorting
// ---------------------------------------------------------------------------
function sortTransactions(transactions, sortKey) {
    const sorted = [...transactions];
    switch (sortKey) {
        case "date-desc":
            sorted.sort((a, b) => (b.date || "").localeCompare(a.date || ""));
            break;
        case "date-asc":
            sorted.sort((a, b) => (a.date || "").localeCompare(b.date || ""));
            break;
        case "amount-desc":
            sorted.sort((a, b) => parseAmount(b.amount) - parseAmount(a.amount));
            break;
        case "amount-asc":
            sorted.sort((a, b) => parseAmount(a.amount) - parseAmount(b.amount));
            break;
        case "merchant-asc":
            sorted.sort((a, b) => (a.merchant || "").localeCompare(b.merchant || ""));
            break;
        case "merchant-desc":
            sorted.sort((a, b) => (b.merchant || "").localeCompare(a.merchant || ""));
            break;
        case "customer-asc":
            sorted.sort((a, b) => (a.customer || "").localeCompare(b.customer || ""));
            break;
        case "customer-desc":
            sorted.sort((a, b) => (b.customer || "").localeCompare(a.customer || ""));
            break;
    }
    return sorted;
}

function applyFilters() {
    const query = document.getElementById("search-input").value.toLowerCase().trim();
    const sortKey = document.getElementById("sort-select").value;

    let filtered = allTransactions;
    if (query) {
        filtered = allTransactions.filter(
            (txn) =>
                (txn.customer || "").toLowerCase().includes(query) ||
                (txn.merchant || "").toLowerCase().includes(query) ||
                (txn.amount || "").toLowerCase().includes(query) ||
                (txn.subject || "").toLowerCase().includes(query) ||
                (txn.order_id || "").toLowerCase().includes(query) ||
                (txn.date || "").toLowerCase().includes(query)
        );
    }

    renderTable(sortTransactions(filtered, sortKey));
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------
async function deleteTxn(id) {
    if (!confirm("Delete this transaction?")) return;
    try {
        await fetch(`/api/transactions/${id}`, { method: "DELETE" });
        allTransactions = allTransactions.filter((t) => t.id !== id);
        applyFilters();
        fetchStats();
    } catch (err) {
        console.error("Delete failed:", err);
        alert("Failed to delete transaction.");
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
        } else {
            fetchTransactions();
            fetchStats();
        }
    } catch (err) {
        console.error("Check now failed:", err);
        alert("Failed to check inbox. See console for details.");
    } finally {
        btn.classList.remove("loading");
        btn.disabled = false;
    }
}

function exportCSV() {
    if (!allTransactions.length) {
        alert("No transactions to export.");
        return;
    }

    const headers = ["Date", "Customer", "Merchant", "Amount", "Order ID", "Items", "Subject"];
    const rows = allTransactions.map((txn) => [
        txn.date || "",
        txn.customer || "",
        txn.merchant || "",
        txn.amount || "",
        txn.order_id || "",
        (txn.items || []).join("; "),
        txn.subject || "",
    ]);

    const csvContent = [headers, ...rows]
        .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","))
        .join("\n");

    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `transactions_${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
    fetchTransactions();
    fetchStats();
    checkConfig();

    document.getElementById("search-input").addEventListener("input", applyFilters);
    document.getElementById("sort-select").addEventListener("change", applyFilters);
    document.getElementById("btn-check-now").addEventListener("click", checkNow);
    document.getElementById("btn-export-csv").addEventListener("click", exportCSV);

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
