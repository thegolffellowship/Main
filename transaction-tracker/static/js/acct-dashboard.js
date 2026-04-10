/* =========================================================
   Accounting Module — Dashboard Tab
   ========================================================= */

async function loadDashboard() {
    const preset = $('#date-range-preset').value;
    const { start, end } = getDateRange(preset);
    const qs = buildQS({ entity_id: ACCT.activeEntity, start_date: start, end_date: end });

    try {
        const [summary, monthly, balances, txnData, aiStats] = await Promise.all([
            api('/reports/summary' + qs),
            api('/reports/monthly' + buildQS({ entity_id: ACCT.activeEntity, months: 12 })),
            api('/accounts/balances'),
            api('/transactions' + buildQS({ entity_id: ACCT.activeEntity, limit: 10 })),
            api('/ai/stats').catch(() => null),
        ]);

        // AI Bookkeeper banner
        renderBookkeeperBanner(aiStats);

        // Pending expenses (bank alerts, Venmo, receipts)
        loadPendingExpenses();

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


// ── AI Bookkeeper ────────────────────────────────────────

function renderBookkeeperBanner(stats) {
    const banner = $('#bookkeeper-banner');
    if (!stats || stats.total === 0) {
        banner.style.display = 'none';
        return;
    }
    banner.style.display = 'flex';
    const statusEl = $('#bookkeeper-status');
    if (stats.uncategorized === 0) {
        statusEl.innerHTML = `<span class="acct-positive">All ${stats.total} transactions categorized</span>`;
        $('#btn-ai-categorize').style.display = 'none';
        $('#btn-review-queue').style.display = 'none';
    } else {
        statusEl.innerHTML = `<span class="acct-negative">${stats.uncategorized} of ${stats.total} transactions need categorization</span> (${stats.pct}% done)`;
        $('#btn-ai-categorize').style.display = '';
        $('#btn-review-queue').style.display = '';
    }
}

async function runAiCategorize() {
    const btn = $('#btn-ai-categorize');
    btn.disabled = true;
    btn.textContent = 'Categorizing...';
    try {
        const res = await api('/ai/bulk-categorize', { method: 'POST' });
        alert(`AI categorized ${res.updated} of ${res.total} transactions`);
        loadDashboard();
    } catch (e) {
        alert('AI categorization error: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Auto-Categorize';
    }
}

async function loadReviewQueue() {
    $('#review-queue').style.display = '';
    try {
        const queue = await api('/ai/review-queue');
        renderReviewQueue(queue);
    } catch (e) {
        console.error('Review queue error:', e);
    }
}

function renderReviewQueue(txns) {
    const el = $('#review-queue-list');
    if (!txns.length) {
        el.innerHTML = '<p class="acct-empty">All transactions are categorized!</p>';
        return;
    }
    el.innerHTML = `<table class="acct-table">
        <thead><tr><th>Date</th><th>Description</th><th>Amount</th><th>Type</th><th>Category</th><th>Entity</th></tr></thead>
        <tbody>${txns.map(t => `<tr class="acct-txn-row" data-id="${t.id}">
            <td>${t.date}</td>
            <td>${t.description}</td>
            <td class="${t.type === 'income' ? 'acct-positive' : 'acct-negative'}">${fmt(t.total_amount)}</td>
            <td><span class="acct-type-badge acct-type-${t.type}">${t.type}</span></td>
            <td>
                <select class="acct-select-sm review-cat" data-txn-id="${t.id}">
                    <option value="">— Select —</option>
                    ${ACCT.categories.filter(c => c.type === t.type).map(c =>
                        `<option value="${c.id}">${c.name}</option>`
                    ).join('')}
                </select>
            </td>
            <td>
                <select class="acct-select-sm review-entity" data-txn-id="${t.id}">
                    ${ACCT.entities.map(e =>
                        `<option value="${e.id}">${e.short_name}</option>`
                    ).join('')}
                </select>
            </td>
        </tr>`).join('')}</tbody></table>`;

    // Bind change events — save immediately on select
    el.querySelectorAll('.review-cat').forEach(sel => {
        sel.addEventListener('change', async () => {
            const txnId = sel.dataset.txnId;
            const catId = sel.value ? parseInt(sel.value) : null;
            const entitySel = el.querySelector(`.review-entity[data-txn-id="${txnId}"]`);
            const entityId = entitySel ? parseInt(entitySel.value) : null;
            if (!catId) return;
            try {
                // Get existing transaction to preserve splits
                const txn = await api('/transactions/' + txnId);
                const splits = txn.splits.map(s => ({
                    entity_id: entityId || s.entity_id,
                    category_id: catId,
                    amount: s.amount,
                    memo: s.memo,
                }));
                await api('/transactions/' + txnId, { method: 'PUT', body: { splits } });
                sel.style.borderColor = 'var(--green)';
            } catch (e) {
                alert('Error: ' + e.message);
            }
        });
    });

    // Click row to open full editor
    el.querySelectorAll('.acct-txn-row').forEach(row => {
        row.addEventListener('click', (e) => {
            if (e.target.tagName === 'SELECT') return;
            openEditTransaction(parseInt(row.dataset.id));
        });
    });
}


// ── Pending Expenses (bank alerts, Venmo, receipts) ─────

async function loadPendingExpenses() {
    try {
        const items = await api('/expense-transactions?review_status=pending&limit=50');
        const container = $('#pending-expenses');
        if (!items.length) {
            container.style.display = 'none';
            return;
        }
        container.style.display = '';
        $('#pending-expense-count').textContent = items.length;
        renderPendingExpenses(items);
    } catch (e) {
        console.error('Pending expenses error:', e);
    }
}

function renderPendingExpenses(items) {
    const el = $('#pending-expense-list');
    const sourceLabels = {
        'chase_alert': 'Chase', 'venmo': 'Venmo', 'receipt': 'Receipt',
    };
    el.innerHTML = items.map(item => {
        const badge = sourceLabels[item.source_type] || item.source_type || 'Other';
        const badgeClass = `coo-source-${item.source_type || 'other'}`;
        return `<div class="coo-review-item" data-id="${item.id}">
            <div class="coo-review-top">
                <span class="coo-source-badge ${badgeClass}">${badge}</span>
                <span class="coo-review-merchant">${item.merchant || '—'}</span>
                ${item.amount ? `<span class="coo-review-amount">${fmt(item.amount)}</span>` : ''}
                <span class="coo-review-date">${item.transaction_date || ''}</span>
                <span class="coo-confidence" title="AI confidence">${item.confidence || 0}%</span>
            </div>
            ${item.notes ? `<div class="coo-review-notes">${item.notes}</div>` : ''}
            <div class="coo-review-actions">
                <select class="coo-review-entity" data-id="${item.id}">
                    <option value="TGF" ${item.entity === 'TGF' ? 'selected' : ''}>TGF</option>
                    <option value="Personal" ${item.entity === 'Personal' ? 'selected' : ''}>Personal</option>
                    <option value="Horizon" ${item.entity === 'Horizon' ? 'selected' : ''}>Horizon</option>
                </select>
                <button class="btn btn-primary btn-sm pending-btn-approve" data-id="${item.id}">Approve</button>
                <button class="btn btn-secondary btn-sm pending-btn-ignore" data-id="${item.id}">Ignore</button>
            </div>
        </div>`;
    }).join('');

    el.querySelectorAll('.pending-btn-approve').forEach(btn => {
        btn.addEventListener('click', async () => {
            const id = btn.dataset.id;
            const row = btn.closest('.coo-review-item');
            const entity = row.querySelector('.coo-review-entity').value;
            await api('/expense-transactions/' + id, {
                method: 'PATCH',
                body: {
                    review_status: 'approved',
                    reviewed_at: new Date().toISOString(),
                    entity: entity || undefined,
                },
            });
            loadPendingExpenses();
        });
    });

    el.querySelectorAll('.pending-btn-ignore').forEach(btn => {
        btn.addEventListener('click', async () => {
            const id = btn.dataset.id;
            await api('/expense-transactions/' + id, {
                method: 'PATCH',
                body: { review_status: 'ignored' },
            });
            loadPendingExpenses();
        });
    });
}
