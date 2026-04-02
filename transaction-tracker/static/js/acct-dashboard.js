/* =========================================================
   Accounting Module — Dashboard Tab
   ========================================================= */

async function loadDashboard() {
    const preset = $('#date-range-preset').value;
    const { start, end } = getDateRange(preset);
    const qs = buildQS({ entity_id: ACCT.activeEntity, start_date: start, end_date: end });

    try {
        const [summary, monthly, balances, txnData] = await Promise.all([
            api('/reports/summary' + qs),
            api('/reports/monthly' + buildQS({ entity_id: ACCT.activeEntity, months: 12 })),
            api('/accounts/balances'),
            api('/transactions' + buildQS({ entity_id: ACCT.activeEntity, limit: 10 })),
        ]);

        // Summary cards
        $('#card-income').textContent = fmt(summary.total_income);
        $('#card-expenses').textContent = fmt(summary.total_expenses);
        $('#card-net').textContent = fmt(summary.net);
        $('#card-net').className = 'acct-card-value ' + (summary.net >= 0 ? 'acct-positive' : 'acct-negative');

        // Monthly chart
        renderMonthlyChart(monthly);

        // Account balances
        renderAccountBalancesDashboard(balances);

        // Recent transactions
        renderRecentTransactions(txnData.transactions || []);
    } catch (e) {
        console.error('Dashboard load error:', e);
    }
}

function renderMonthlyChart(data) {
    const el = $('#monthly-chart');
    if (!data.length) { el.innerHTML = '<p class="acct-empty">No data yet</p>'; return; }

    const maxVal = Math.max(...data.map(d => Math.max(d.income, d.expenses)), 1);
    const bars = data.map(d => {
        const iPct = (d.income / maxVal * 100).toFixed(1);
        const ePct = (d.expenses / maxVal * 100).toFixed(1);
        const label = d.month.substring(5); // MM from YYYY-MM
        return `<div class="acct-chart-col">
            <div class="acct-chart-bars">
                <div class="acct-chart-bar acct-bar-income" style="height:${iPct}%" title="Income: ${fmt(d.income)}"></div>
                <div class="acct-chart-bar acct-bar-expense" style="height:${ePct}%" title="Expenses: ${fmt(d.expenses)}"></div>
            </div>
            <div class="acct-chart-label">${label}</div>
        </div>`;
    }).join('');

    el.innerHTML = `
        <div class="acct-chart-legend">
            <span class="acct-legend-item"><span class="acct-legend-dot acct-bar-income"></span> Income</span>
            <span class="acct-legend-item"><span class="acct-legend-dot acct-bar-expense"></span> Expenses</span>
        </div>
        <div class="acct-chart">${bars}</div>`;
}

function renderAccountBalancesDashboard(accounts) {
    const el = $('#account-balances-dashboard');
    if (!accounts.length) {
        el.innerHTML = '<p class="acct-empty">No accounts yet. <a href="#" onclick="switchTab(\'accounts\');return false;">Add one</a></p>';
        return;
    }
    el.innerHTML = `<div class="acct-balance-grid">${accounts.map(a => `
        <div class="acct-balance-card">
            <div class="acct-balance-name">${a.name}</div>
            <div class="acct-balance-type">${a.account_type.replace('_', ' ')}</div>
            <div class="acct-balance-amount ${a.current_balance >= 0 ? 'acct-positive' : 'acct-negative'}">
                ${fmt(a.current_balance)}
            </div>
        </div>`).join('')}</div>`;
}

function renderRecentTransactions(txns) {
    const el = $('#recent-transactions');
    if (!txns.length) {
        el.innerHTML = '<p class="acct-empty">No transactions yet</p>';
        return;
    }
    el.innerHTML = `<table class="acct-table">
        <thead><tr><th>Date</th><th>Description</th><th>Entity</th><th>Category</th><th class="text-right">Amount</th><th>Type</th></tr></thead>
        <tbody>${txns.map(t => {
            const split = t.splits[0] || {};
            return `<tr class="acct-txn-row" data-id="${t.id}">
                <td>${t.date}</td>
                <td>${t.description}</td>
                <td><span class="acct-entity-badge" style="background:${split.entity_color || '#6b7280'}">${split.entity_name || '—'}</span></td>
                <td>${split.category_name || '—'}</td>
                <td class="text-right ${t.type === 'income' ? 'acct-positive' : 'acct-negative'}">${fmt(t.total_amount)}</td>
                <td><span class="acct-type-badge acct-type-${t.type}">${t.type}</span></td>
            </tr>`;
        }).join('')}</tbody></table>`;

    el.querySelectorAll('.acct-txn-row').forEach(row => {
        row.addEventListener('click', () => openEditTransaction(parseInt(row.dataset.id)));
    });
}
