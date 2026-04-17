/* =========================================================
   Accounting Module — Dashboard Tab
   ========================================================= */

async function loadDashboard() {
    const preset = $('#date-range-preset').value;
    const { start, end } = getDateRange(preset);
    const qs = buildQS({ entity_id: ACCT.activeEntity, start_date: start, end_date: end });

    try {
        const [summary, monthly, balances, txnData, aiStats, closeStatus] = await Promise.all([
            api('/reports/summary' + qs),
            api('/reports/monthly' + buildQS({ entity_id: ACCT.activeEntity, months: 12 })),
            api('/accounts/balances'),
            api('/transactions' + buildQS({ entity_id: ACCT.activeEntity, limit: 10 })),
            api('/ai/stats').catch(() => null),
            fetch('/api/accounting/month-close').then(r => r.json()).catch(() => null),
        ]);

        // Month Close checklist + Financial Position
        if (closeStatus) renderMonthClose(closeStatus);

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

    // Desktop table
    const tableHTML = `<table class="acct-table acct-table-mobile-hide">
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

    // Mobile cards
    const cardsHTML = `<div class="acct-mobile-cards">${txns.map(t => {
        const split = t.splits[0] || {};
        return `<div class="acct-mobile-card" data-id="${t.id}">
            <div class="acct-mobile-card-top">
                <div class="acct-mc-left">
                    <div class="acct-mc-date">${t.date} <span class="acct-type-badge acct-type-${t.type}" style="font-size:0.6rem;">${t.type}</span></div>
                    <div class="acct-mc-desc">${t.description}</div>
                </div>
                <div class="acct-mc-right">
                    <span class="acct-mc-amount ${t.type === 'income' ? 'acct-positive' : 'acct-negative'}">${fmt(t.total_amount)}</span>
                    <span class="acct-mc-chevron">&#9654;</span>
                </div>
            </div>
            <div class="acct-mobile-card-details">
                <div class="acct-mc-fields">
                    <div class="acct-mc-field">
                        <span class="acct-mc-label">Entity</span>
                        <span class="acct-mc-value"><span class="acct-entity-badge" style="background:${split.entity_color || '#6b7280'}">${split.entity_name || '—'}</span></span>
                    </div>
                    <div class="acct-mc-field">
                        <span class="acct-mc-label">Category</span>
                        <span class="acct-mc-value">${split.category_name || '—'}</span>
                    </div>
                </div>
            </div>
        </div>`;
    }).join('')}</div>`;

    el.innerHTML = tableHTML + cardsHTML;

    // Mobile card expand/collapse
    el.querySelectorAll('.acct-mobile-card-top').forEach(top => {
        top.addEventListener('click', () => {
            top.closest('.acct-mobile-card').classList.toggle('expanded');
        });
    });

    // Click to open editor (desktop)
    el.querySelectorAll('.acct-txn-row').forEach(row => {
        row.addEventListener('click', () => openEditTransaction(parseInt(row.dataset.id)));
    });

    // Tap description to open editor (mobile)
    el.querySelectorAll('.acct-mobile-card .acct-mc-desc').forEach(desc => {
        desc.addEventListener('click', (e) => {
            e.stopPropagation();
            openEditTransaction(parseInt(desc.closest('.acct-mobile-card').dataset.id));
        });
    });
}


// ── AI Bookkeeper ────────────────────────────────────────

function renderBookkeeperBanner(stats) {
    const banner = $('#bookkeeper-banner');
    const pending = (stats?.pending_expenses || 0) + (stats?.uncategorized || 0);
    if (!stats || (stats.total === 0 && pending === 0)) {
        banner.style.display = 'none';
        return;
    }
    banner.style.display = 'flex';
    const statusEl = $('#bookkeeper-status');
    const btn = $('#btn-ai-categorize');
    if (pending === 0) {
        statusEl.innerHTML = `<span class="acct-positive">All transactions categorized ✓</span>`;
        btn.style.display = 'none';
        $('#btn-review-queue').style.display = 'none';
    } else {
        const parts = [];
        if (stats.pending_expenses > 0) parts.push(`${stats.pending_expenses} inbox`);
        if (stats.uncategorized > 0) parts.push(`${stats.uncategorized} uncategorized`);
        statusEl.innerHTML = `<span class="acct-negative">${parts.join(' · ')} — needs review</span>`;
        const totalPending = (stats.pending_expenses || 0) + (stats.uncategorized || 0);
        btn.textContent = `Review Batch (${totalPending})`;
        btn.style.display = '';
        $('#btn-review-queue').style.display = '';
    }
}

// ── Batch Categorization Preview ──────────────────────────────────────────

const BATCH = { offset: 0, limit: 20, total: 0, categories: [], entities: [] };

const CONF_BADGE = {
    high:   { label: 'High',   bg: '#dcfce7', color: '#166534' },
    medium: { label: 'Medium', bg: '#fef9c3', color: '#854d0e' },
    rule:   { label: 'Rule',   bg: '#dbeafe', color: '#1e40af' },
    ai:     { label: 'AI',     bg: '#f3e8ff', color: '#6b21a8' },
    none:   { label: 'None',   bg: '#f3f4f6', color: '#6b7280' },
};

async function runAiCategorize() {
    await openBatchPreview(0);
}

async function openBatchPreview(offset = 0) {
    const panel = $('#batch-preview-panel');
    const list  = $('#batch-preview-list');
    list.innerHTML = '<div style="padding:1.5rem; text-align:center; color:var(--text-muted);">Loading suggestions…</div>';
    panel.style.display = '';
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    try {
        const data = await api(`/ai/batch?limit=${BATCH.limit}&offset=${offset}`);
        BATCH.offset     = offset;
        BATCH.total      = data.total;
        BATCH.categories = data.categories || [];
        BATCH.entities   = data.entities   || [];
        renderBatchPreview(data.items);
        updateBatchControls();
    } catch (e) {
        list.innerHTML = `<div style="padding:1.5rem; color:var(--danger);">Error: ${e.message}</div>`;
    }
}

function renderBatchPreview(items) {
    const list = $('#batch-preview-list');

    if (!items || !items.length) {
        list.innerHTML = '<div style="padding:1.5rem; text-align:center; color:var(--text-muted);">No pending transactions — inbox is clear! 🎉</div>';
        $('#btn-batch-approve').disabled = true;
        return;
    }

    const catOpts = (selected) => {
        const grouped = { income: [], expense: [] };
        BATCH.categories.forEach(c => {
            if (grouped[c.type]) grouped[c.type].push(c);
        });
        const makeGroup = (label, cats) => cats.length
            ? `<optgroup label="${label}">${cats.map(c =>
                `<option value="${c.name}" ${c.name === selected ? 'selected' : ''}>${c.name}</option>`
              ).join('')}</optgroup>`
            : '';
        return `<option value="">— Category —</option>` +
               makeGroup('Income', grouped.income) +
               makeGroup('Expense', grouped.expense);
    };

    const entOpts = (selected) =>
        BATCH.entities.map(e =>
            `<option value="${e.short_name}" ${e.short_name === selected ? 'selected' : ''}>${e.short_name}</option>`
        ).join('');

    const srcBadge = (src, itemType) => {
        if (itemType === 'acct') {
            return `<span style="font-size:0.7rem; padding:1px 6px; border-radius:9999px; background:#374151; color:#fff; white-space:nowrap;">Ledger</span>`;
        }
        const labels = { chase_alert: 'Chase', venmo: 'Venmo', receipt: 'Receipt' };
        const colors = { chase_alert: '#1d4ed8', venmo: '#1e3a5f', receipt: '#047857' };
        const label = labels[src] || src || 'Manual';
        const bg    = colors[src] || '#6b7280';
        return `<span style="font-size:0.7rem; padding:1px 6px; border-radius:9999px; background:${bg}; color:#fff; white-space:nowrap;">${label}</span>`;
    };

    const confBadge = (conf) => {
        const b = CONF_BADGE[conf] || CONF_BADGE.none;
        return `<span style="font-size:0.7rem; padding:1px 6px; border-radius:9999px; background:${b.bg}; color:${b.color}; white-space:nowrap;">${b.label}</span>`;
    };

    list.innerHTML = items.map((item, i) => {
        const sugCat = item.suggestion?.category_name || '';
        const sugEnt = item.suggestion?.entity_name   || '';
        const conf   = item.suggestion?.confidence    || 'none';
        const isDupe = item.is_duplicate;

        return `<div class="batch-row" data-id="${item.id}" data-item-type="${item.item_type || 'expense'}" style="display:flex; align-items:flex-start; gap:0.75rem; padding:0.65rem 1rem; border-bottom:1px solid var(--border); ${isDupe ? 'background:#fff7ed;' : ''}">
            <div style="padding-top:2px; flex-shrink:0;">
                <input type="checkbox" class="batch-chk" data-id="${item.id}" ${isDupe ? '' : 'checked'} style="width:16px; height:16px; cursor:pointer;">
            </div>
            <div style="flex:1; min-width:0;">
                <div style="display:flex; align-items:center; gap:0.4rem; flex-wrap:wrap; margin-bottom:0.3rem;">
                    <span style="font-size:0.82rem; color:var(--text-muted);">${item.date || '—'}</span>
                    ${srcBadge(item.source_type, item.item_type)}
                    ${isDupe ? '<span style="font-size:0.7rem; padding:1px 6px; border-radius:9999px; background:#fef3c7; color:#92400e; white-space:nowrap;">⚠ Possible Duplicate</span>' : ''}
                    ${confBadge(conf)}
                </div>
                <div style="font-weight:500; font-size:0.9rem; margin-bottom:0.35rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${item.merchant}">${item.merchant || '(unknown)'}</div>
                ${item.notes ? `<div style="font-size:0.78rem; color:var(--text-muted); margin-bottom:0.35rem; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${item.notes}</div>` : ''}
                <div style="display:flex; gap:0.5rem; flex-wrap:wrap;">
                    <select class="batch-cat acct-select-sm" data-id="${item.id}" style="min-width:160px;">${catOpts(sugCat)}</select>
                    <select class="batch-ent acct-select-sm" data-id="${item.id}" style="min-width:80px;"><option value="">— Entity —</option>${entOpts(sugEnt)}</select>
                </div>
            </div>
            <div style="flex-shrink:0; text-align:right; min-width:60px;">
                <span style="font-weight:600; font-size:0.9rem; color:${item.transaction_type === 'income' ? 'var(--success)' : 'var(--danger)'};">${fmtAmt(item.amount)}</span>
            </div>
        </div>`;
    }).join('');

    bindBatchEvents();
    updateApproveButton();
}

function fmtAmt(v) {
    if (v == null) return '—';
    return '$' + Math.abs(parseFloat(v)).toFixed(2);
}

function bindBatchEvents() {
    const list = $('#batch-preview-list');

    // Checkbox changes → update approve button count
    list.querySelectorAll('.batch-chk').forEach(chk => {
        chk.addEventListener('change', updateApproveButton);
    });

    // Select-all checkbox
    const selectAll = $('#batch-select-all');
    if (selectAll) {
        selectAll.checked = false;
        selectAll.onchange = () => {
            list.querySelectorAll('.batch-chk').forEach(chk => {
                const row = chk.closest('.batch-row');
                const isDupe = row && row.style.background.includes('fff7ed');
                if (!isDupe) chk.checked = selectAll.checked;
            });
            updateApproveButton();
        };
    }
}

function updateApproveButton() {
    const checked = document.querySelectorAll('.batch-chk:checked').length;
    const btn = $('#btn-batch-approve');
    btn.disabled = checked === 0;
    btn.textContent = `Approve Selected (${checked})`;
}

function updateBatchControls() {
    const totalPages = Math.ceil(BATCH.total / BATCH.limit) || 1;
    const currentPage = Math.floor(BATCH.offset / BATCH.limit) + 1;
    $('#batch-preview-count').textContent = `${BATCH.total} pending`;
    $('#batch-page-label').textContent     = `Page ${currentPage} of ${totalPages}`;
    $('#btn-batch-prev').disabled = BATCH.offset === 0;
    $('#btn-batch-next').disabled = BATCH.offset + BATCH.limit >= BATCH.total;
}

async function submitBatchApprove() {
    const btn = $('#btn-batch-approve');
    btn.disabled = true;
    btn.textContent = 'Approving…';

    const items = [];
    document.querySelectorAll('.batch-row').forEach(row => {
        const id       = parseInt(row.dataset.id);
        const itemType = row.dataset.itemType || 'expense';
        const chk      = row.querySelector('.batch-chk');
        if (!chk?.checked) return;
        const cat = row.querySelector('.batch-cat')?.value || '';
        const ent = row.querySelector('.batch-ent')?.value || '';
        items.push({ id, item_type: itemType, category_name: cat || null, entity_name: ent || null });
    });

    if (!items.length) return;

    try {
        const res = await api('/ai/batch-approve', { method: 'POST', body: { items } });
        const msg = `✓ Approved ${res.approved}` +
            (res.skipped ? `, skipped ${res.skipped}` : '') +
            (res.errors?.length ? `, ${res.errors.length} errors` : '');
        showToast(msg, 'success');

        // Advance to next batch or close if done
        const nextOffset = BATCH.offset; // stay on same page — approved rows are gone
        const remaining  = BATCH.total - res.approved;
        if (remaining <= 0) {
            $('#batch-preview-panel').style.display = 'none';
        } else {
            await openBatchPreview(Math.min(nextOffset, Math.max(0, remaining - BATCH.limit)));
        }
        loadDashboard();
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
        btn.disabled = false;
        btn.textContent = `Approve Selected`;
    }
}

function showToast(msg, type = 'info') {
    let t = document.getElementById('acct-toast');
    if (!t) {
        t = document.createElement('div');
        t.id = 'acct-toast';
        t.style.cssText = 'position:fixed;bottom:1.5rem;right:1.5rem;padding:0.65rem 1rem;border-radius:6px;font-size:0.875rem;z-index:9999;max-width:320px;box-shadow:0 4px 12px rgba(0,0,0,.15);transition:opacity .3s;';
        document.body.appendChild(t);
    }
    t.textContent = msg;
    t.style.background = type === 'success' ? '#166534' : type === 'error' ? '#991b1b' : '#1e3a5f';
    t.style.color = '#fff';
    t.style.opacity = '1';
    clearTimeout(t._hide);
    t._hide = setTimeout(() => { t.style.opacity = '0'; }, 3500);
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

    const catOptions = (type) => ACCT.categories.filter(c => c.type === type).map(c =>
        `<option value="${c.id}">${c.name}</option>`
    ).join('');
    const entityOptions = ACCT.entities.map(e =>
        `<option value="${e.id}">${e.short_name}</option>`
    ).join('');

    // Desktop table
    const tableHTML = `<table class="acct-table acct-table-mobile-hide">
        <thead><tr><th>Date</th><th>Description</th><th>Amount</th><th>Type</th><th>Category</th><th>Entity</th></tr></thead>
        <tbody>${txns.map(t => `<tr class="acct-txn-row" data-id="${t.id}">
            <td>${t.date}</td>
            <td>${t.description}</td>
            <td class="${t.type === 'income' ? 'acct-positive' : 'acct-negative'}">${fmt(t.total_amount)}</td>
            <td><span class="acct-type-badge acct-type-${t.type}">${t.type}</span></td>
            <td>
                <select class="acct-select-sm review-cat" data-txn-id="${t.id}">
                    <option value="">— Select —</option>
                    ${catOptions(t.type)}
                </select>
            </td>
            <td>
                <select class="acct-select-sm review-entity" data-txn-id="${t.id}">
                    ${entityOptions}
                </select>
            </td>
        </tr>`).join('')}</tbody></table>`;

    // Mobile cards
    const cardsHTML = `<div class="acct-mobile-cards">${txns.map(t => `
        <div class="acct-mobile-card" data-id="${t.id}">
            <div class="acct-mobile-card-top">
                <div class="acct-mc-left">
                    <div class="acct-mc-date">${t.date}</div>
                    <div class="acct-mc-desc">${t.description}</div>
                </div>
                <div class="acct-mc-right">
                    <span class="acct-mc-amount ${t.type === 'income' ? 'acct-positive' : 'acct-negative'}">${fmt(t.total_amount)}</span>
                    <span class="acct-mc-chevron">&#9654;</span>
                </div>
            </div>
            <div class="acct-mobile-card-details">
                <div class="acct-mc-fields">
                    <div class="acct-mc-field">
                        <span class="acct-mc-label">Type</span>
                        <span class="acct-mc-value"><span class="acct-type-badge acct-type-${t.type}">${t.type}</span></span>
                    </div>
                    <div class="acct-mc-field">
                        <span class="acct-mc-label">Amount</span>
                        <span class="acct-mc-value ${t.type === 'income' ? 'acct-positive' : 'acct-negative'}">${fmt(t.total_amount)}</span>
                    </div>
                </div>
                <div class="acct-mc-actions">
                    <select class="review-cat" data-txn-id="${t.id}">
                        <option value="">— Category —</option>
                        ${catOptions(t.type)}
                    </select>
                    <select class="review-entity" data-txn-id="${t.id}">
                        ${entityOptions}
                    </select>
                </div>
            </div>
        </div>`).join('')}</div>`;

    el.innerHTML = tableHTML + cardsHTML;

    // Mobile card expand/collapse
    el.querySelectorAll('.acct-mobile-card-top').forEach(top => {
        top.addEventListener('click', (e) => {
            if (e.target.tagName === 'SELECT') return;
            top.closest('.acct-mobile-card').classList.toggle('expanded');
        });
    });

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

    // Click row to open full editor (desktop)
    el.querySelectorAll('.acct-txn-row').forEach(row => {
        row.addEventListener('click', (e) => {
            if (e.target.tagName === 'SELECT') return;
            openEditTransaction(parseInt(row.dataset.id));
        });
    });

    // Tap card to open full editor (mobile — on description, not on selects)
    el.querySelectorAll('.acct-mobile-card .acct-mc-desc').forEach(desc => {
        desc.addEventListener('click', (e) => {
            e.stopPropagation();
            openEditTransaction(parseInt(desc.closest('.acct-mobile-card').dataset.id));
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
        return `<div class="coo-review-item" data-id="${item.id}" style="cursor:pointer;">
            <div class="coo-review-top">
                <span class="coo-source-badge ${badgeClass}">${badge}</span>
                <span class="coo-review-merchant">${item.merchant || '—'}</span>
                ${item.amount ? `<span class="coo-review-amount">${fmt(item.amount)}</span>` : ''}
                <span class="coo-review-date">${item.transaction_date || ''}</span>
                <span class="coo-confidence" title="AI confidence">${item.confidence || 0}%</span>
            </div>
            ${item.notes ? `<div class="coo-review-notes">${item.notes}</div>` : ''}
        </div>`;
    }).join('');

    // Click any item to open the unified review modal
    el.querySelectorAll('.coo-review-item').forEach(row => {
        row.addEventListener('click', () => {
            openExpenseReview(parseInt(row.dataset.id));
        });
    });
}

// ═══════════════════════════════════════════════════
// LIABILITIES DASHBOARD
// ═══════════════════════════════════════════════════

let _liabData = null;
let _liabEditKey = null;

function loadLiabilities() {
    const content = document.getElementById('liabilities-content');
    const loading = document.getElementById('liabilities-loading');
    if (loading) loading.style.display = 'block';
    if (content) content.style.display = 'none';

    fetch('/api/accounting/liabilities')
        .then(r => r.json())
        .then(data => {
            _liabData = data;
            renderLiabilities(data);
        })
        .catch(() => {
            if (loading) loading.textContent = 'Failed to load liabilities.';
        });
}

function renderLiabilities(d) {
    const loading = document.getElementById('liabilities-loading');
    const content = document.getElementById('liabilities-content');
    if (loading) loading.style.display = 'none';
    if (content) content.style.display = 'block';

    const $ = id => document.getElementById(id);

    const fmt = v => '$' + Number(v || 0).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    const amtEl = (el, v) => {
        if (!el) return;
        el.textContent = fmt(v);
        el.classList.toggle('zero', !v || v === 0);
    };

    // Event Obligations
    amtEl($('liab-prize-pools'), d.event_obligations.prize_pools.total);
    amtEl($('liab-course-fees'), d.event_obligations.course_fees_owed);
    const evtTotal = d.event_obligations.prize_pools.total + d.event_obligations.course_fees_owed;
    const evtEl = $('liab-total-event');
    if (evtEl) evtEl.textContent = fmt(evtTotal);

    // Per-event prize pool breakdown
    const breakdown = $('liab-prize-breakdown');
    if (breakdown) {
        const rows = d.event_obligations.prize_pools.per_event;
        if (rows && rows.length) {
            breakdown.innerHTML = rows.map(e =>
                `<div class="liab-prize-event-row"><span>${e.event}</span><span>${fmt(e.amount)}</span></div>`
            ).join('');
        } else {
            breakdown.innerHTML = '<div style="font-size:0.82rem;color:var(--text-muted);padding:0.25rem 0;">No upcoming events with prize pools</div>';
        }
    }

    // Running Pools
    amtEl($('liab-hio-pot'), d.running_pools.hio_pot);
    amtEl($('liab-season-contests'), d.running_pools.season_contests);
    amtEl($('liab-lone-star'), d.running_pools.lone_star_cup_shirts);
    const poolTotal = d.running_pools.hio_pot + d.running_pools.season_contests + d.running_pools.lone_star_cup_shirts;
    const poolEl = $('liab-total-pools');
    if (poolEl) poolEl.textContent = fmt(poolTotal);

    // Operational
    amtEl($('liab-chapter-mgr'), d.operational.chapter_manager_payouts);
    amtEl($('liab-tax-reserve'), d.operational.tax_reserve_ytd);
    const opTotal = d.operational.chapter_manager_payouts + d.operational.tax_reserve_ytd;
    const opEl = $('liab-total-operational');
    if (opEl) opEl.textContent = fmt(opTotal);

    // Debts
    amtEl($('liab-investor-debt'), d.debts.investor_debt);
    amtEl($('liab-member-credits'), d.debts.member_credits_2025);
    amtEl($('liab-irs'), d.debts.irs_balance);
    amtEl($('liab-chase-biz'), d.debts.chase_biz_7680);
    amtEl($('liab-chase-saph'), d.debts.chase_sapphire_6159);
    const debtTotal = d.debts.investor_debt + d.debts.member_credits_2025
        + d.debts.irs_balance + d.debts.chase_biz_7680 + d.debts.chase_sapphire_6159;
    const debtEl = $('liab-total-debts');
    if (debtEl) debtEl.textContent = fmt(debtTotal);

    // Grand total
    const gt = $('liabilities-grand-total');
    if (gt) gt.textContent = fmt(d.grand_total);
}

function openLiabEditModal(key, currentValue) {
    _liabEditKey = key;
    const labels = {
        hio_pot: 'HIO Pot',
        season_contests_total: 'Season Contests Total',
        lone_star_cup_shirts: 'Lone Star Cup Shirt Fund',
        chapter_manager_payouts: 'Chapter Manager Payouts',
        grandparent_loan: 'Investor Debt',
        member_credits_2025: 'Member Credits 2025',
        irs_balance: 'IRS Balance',
        chase_biz_7680: 'Chase Biz (7680)',
        chase_sapphire_6159: 'Chase Sapphire (6159)',
    };
    const modal = document.getElementById('liab-edit-modal');
    const title = document.getElementById('liab-modal-title');
    const input = document.getElementById('liab-modal-input');
    if (title) title.textContent = 'Update: ' + (labels[key] || key);
    if (input) { input.value = Number(currentValue || 0).toFixed(2); input.focus(); input.select(); }
    if (modal) modal.style.display = 'flex';
}

function saveLiabEdit() {
    const input = document.getElementById('liab-modal-input');
    const value = parseFloat(input ? input.value : 0);
    if (isNaN(value)) { showToast('Enter a valid number', 'error'); return; }
    fetch('/api/accounting/liabilities/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: _liabEditKey, value }),
    })
    .then(r => r.json())
    .then(res => {
        if (res.error) { showToast(res.error, 'error'); return; }
        closeLiabModal();
        loadLiabilities();
        showToast('Saved', 'success');
    })
    .catch(() => showToast('Save failed', 'error'));
}

function closeLiabModal() {
    const modal = document.getElementById('liab-edit-modal');
    if (modal) modal.style.display = 'none';
    _liabEditKey = null;
}

function initLiabilitiesTab() {
    // Edit buttons
    document.querySelectorAll('.liab-edit-btn').forEach(btn => {
        const row = btn.closest('.liab-editable');
        if (!row) return;
        btn.addEventListener('click', () => {
            const key = row.dataset.key;
            // Find current value from rendered element
            const amtMap = {
                hio_pot: 'liab-hio-pot',
                season_contests_total: 'liab-season-contests',
                lone_star_cup_shirts: 'liab-lone-star',
                chapter_manager_payouts: 'liab-chapter-mgr',
                grandparent_loan: 'liab-investor-debt',
                member_credits_2025: 'liab-member-credits',
                irs_balance: 'liab-irs',
                chase_biz_7680: 'liab-chase-biz',
                chase_sapphire_6159: 'liab-chase-saph',
            };
            const elId = amtMap[key];
            const el = elId ? document.getElementById(elId) : null;
            const raw = el ? el.textContent.replace(/[$,]/g, '') : '0';
            openLiabEditModal(key, parseFloat(raw) || 0);
        });
    });

    // Expand prize pools breakdown
    const expandBtn = document.getElementById('btn-expand-prize');
    const breakdown = document.getElementById('liab-prize-breakdown');
    if (expandBtn && breakdown) {
        expandBtn.addEventListener('click', () => {
            const open = breakdown.style.display !== 'none';
            breakdown.style.display = open ? 'none' : 'block';
            expandBtn.textContent = open ? '▾' : '▴';
        });
    }

    // Modal buttons
    const saveBtn = document.getElementById('liab-modal-save');
    const cancelBtn = document.getElementById('liab-modal-cancel');
    const input = document.getElementById('liab-modal-input');
    if (saveBtn) saveBtn.addEventListener('click', saveLiabEdit);
    if (cancelBtn) cancelBtn.addEventListener('click', closeLiabModal);
    if (input) input.addEventListener('keydown', e => { if (e.key === 'Enter') saveLiabEdit(); if (e.key === 'Escape') closeLiabModal(); });

    // Refresh button
    const refreshBtn = document.getElementById('btn-liabilities-refresh');
    if (refreshBtn) refreshBtn.addEventListener('click', loadLiabilities);

    // Load data
    loadLiabilities();
}

// ═══════════════════════════════════════════════════
// MONTH CLOSE CHECKLIST
// ═══════════════════════════════════════════════════

function renderMonthClose(d) {
    const fmt = v => '$' + Number(v || 0).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    const $ = id => document.getElementById(id);

    // Period label
    const periodEl = $('month-close-period');
    if (periodEl) periodEl.textContent = (d.period && d.period.month) || '';

    // Financial position cards
    const fp = d.financial_position || {};
    const setCard = (id, val) => { const el = $(id); if (el) el.textContent = fmt(val); };
    setCard('mc-ytd-income', fp.ytd_income);
    setCard('mc-ytd-expenses', fp.ytd_expenses);
    setCard('mc-ytd-net', fp.ytd_net);
    setCard('mc-cash', fp.cash_on_hand);
    setCard('mc-liabilities', fp.total_liabilities);
    setCard('mc-net-position', fp.net_position);

    // Color net and position cards
    const netCard = $('mc-net-card');
    if (netCard) netCard.className = 'mc-fin-card ' + ((fp.ytd_net || 0) >= 0 ? 'mc-net-positive' : 'mc-net-negative');
    const posCard = $('mc-pos-card');
    if (posCard) posCard.className = 'mc-fin-card ' + ((fp.net_position || 0) >= 0 ? 'mc-pos-positive' : 'mc-pos-negative');

    // Checklist items
    const cl = d.checklist || {};
    const items = [
        {
            label: 'Transactions categorized',
            count: cl.uncategorized_ledger,
            zero: 'All ledger entries categorized',
            nonzero: n => `${n} ledger entr${n === 1 ? 'y' : 'ies'} uncategorized`,
            action: n => n > 0 ? { label: 'Review Batch', fn: () => { switchTab('dashboard'); document.getElementById('btn-ai-categorize') && document.getElementById('btn-ai-categorize').click(); } } : null,
        },
        {
            label: 'Inbox clear',
            count: cl.pending_inbox,
            zero: 'No pending inbox items',
            nonzero: n => `${n} inbox item${n === 1 ? '' : 's'} awaiting review`,
            action: n => n > 0 ? { label: 'Review Batch', fn: () => { switchTab('dashboard'); document.getElementById('btn-ai-categorize') && document.getElementById('btn-ai-categorize').click(); } } : null,
        },
        {
            label: 'Bank deposits matched',
            count: cl.unmatched_deposits,
            zero: 'All deposits matched',
            nonzero: n => `${n} deposit${n === 1 ? '' : 's'} unmatched`,
            action: n => n > 0 ? { label: 'Go to Reconcile', fn: () => { window.location.href = '/accounting/reconcile'; } } : null,
        },
        {
            label: 'Ledger reconciled',
            count: cl.unreconciled_entries,
            zero: 'All entries reconciled',
            nonzero: n => `${n} entr${n === 1 ? 'y' : 'ies'} not confirmed in bank`,
            action: n => n > 0 ? { label: 'Go to Reconcile', fn: () => { window.location.href = '/accounting/reconcile'; } } : null,
        },
        {
            label: 'Events accounted',
            count: cl.events_no_entries,
            zero: 'All this-month events have ledger entries',
            nonzero: n => `${n} event${n === 1 ? '' : 's'} with no ledger entries`,
            action: n => n > 0 ? { label: 'View Events', fn: () => { window.location.href = '/'; } } : null,
        },
        {
            label: 'Tax reserve',
            count: null,  // informational
            zero: `Tax reserve YTD: ${fmt(cl.tax_reserve_ytd)}`,
            nonzero: () => `Tax reserve YTD: ${fmt(cl.tax_reserve_ytd)}`,
            action: () => ({ label: 'View Liabilities', fn: () => switchTab('liabilities') }),
        },
    ];

    let doneCount = 0;
    const rows = items.map(item => {
        const count = item.count;
        const isInfo = count === null;
        const isDone = isInfo ? true : count === 0;
        if (isDone) doneCount++;

        let dotClass = 'mc-dot-green';
        if (!isInfo && count > 0 && count <= 5) dotClass = 'mc-dot-amber';
        else if (!isInfo && count > 5) dotClass = 'mc-dot-red';

        const detail = isDone ? item.zero : (typeof item.nonzero === 'function' ? item.nonzero(count) : item.nonzero);
        const actionObj = item.action ? item.action(count) : null;
        const actionHtml = actionObj
            ? `<button class="mc-item-action" onclick="(${actionObj.fn.toString()})()">${actionObj.label}</button>`
            : '';

        return `<div class="mc-item">
            <div class="mc-dot ${dotClass}"></div>
            <div class="mc-item-label">${item.label}</div>
            <div class="mc-item-detail">${detail}</div>
            ${actionHtml}
        </div>`;
    }).join('');

    const scoreEl = $('month-close-score');
    if (scoreEl) scoreEl.textContent = `${doneCount}/${items.length} complete`;

    const checklistEl = $('month-close-checklist');
    if (checklistEl) checklistEl.innerHTML = rows;
}

// ═══════════════════════════════════════════════════
// CONTRACTORS TAB
// ═══════════════════════════════════════════════════

const CTRS = { payouts: [], managers: [], filterStatus: '' };

async function loadContractors() {
    const [payouts, managers] = await Promise.all([
        fetch('/api/accounting/contractors').then(r => r.json()).catch(() => []),
        fetch('/api/accounting/contractors/managers').then(r => r.json()).catch(() => []),
    ]);
    CTRS.payouts = payouts;
    CTRS.managers = managers;
    populateManagerDropdown();
    renderContractors();
}

function populateManagerDropdown() {
    const sel = document.getElementById('contractor-manager-select');
    if (!sel) return;
    sel.innerHTML = '<option value="">Select manager…</option>' +
        CTRS.managers.map(m =>
            `<option value="${m.customer_id}">${m.name}${m.chapter_name ? ' — ' + m.chapter_name : ''}</option>`
        ).join('');
}

function renderContractors() {
    const fmt = v => '$' + Number(v || 0).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    const statusFilter = (document.getElementById('contractor-filter-status') || {}).value || '';

    const filtered = statusFilter
        ? CTRS.payouts.filter(p => p.status === statusFilter)
        : CTRS.payouts;

    // Summary strip
    const totalOwed = CTRS.payouts.reduce((s, p) => s + (p.amount_owed || 0), 0);
    const totalPaid = CTRS.payouts.reduce((s, p) => s + (p.amount_paid || 0), 0);
    const outstanding = totalOwed - totalPaid;
    const summaryEl = document.getElementById('contractor-summary');
    if (summaryEl) {
        summaryEl.innerHTML = [
            { label: 'Total Owed', val: totalOwed, cls: '' },
            { label: 'Total Paid', val: totalPaid, cls: 'color:#16a34a' },
            { label: 'Outstanding', val: outstanding, cls: outstanding > 0 ? 'color:#dc2626;font-weight:700' : 'color:#16a34a;font-weight:700' },
        ].map(c => `<div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:0.6rem 1rem;min-width:120px;">
            <div style="font-size:0.75rem;color:var(--text-muted)">${c.label}</div>
            <div style="font-size:1rem;${c.cls}">${fmt(c.val)}</div>
        </div>`).join('');
    }

    const listEl = document.getElementById('contractor-payout-list');
    if (!listEl) return;

    if (!filtered.length) {
        listEl.innerHTML = `<div style="padding:2rem;text-align:center;color:var(--text-muted);">
            ${CTRS.payouts.length ? 'No payouts match the filter.' : 'No contractor payouts recorded yet. Click <strong>+ Add Payout</strong> to start.'}
        </div>`;
        return;
    }

    const STATUS_COLORS = { pending: '#f59e0b', partial: '#2563eb', paid: '#16a34a' };

    listEl.innerHTML = `<table style="width:100%;border-collapse:collapse;font-size:0.85rem;">
        <thead style="background:var(--surface-alt,#f8fafc);">
            <tr>
                <th style="padding:0.6rem 0.9rem;text-align:left;font-weight:600;border-bottom:1px solid var(--border);">Manager</th>
                <th style="padding:0.6rem 0.9rem;text-align:left;font-weight:600;border-bottom:1px solid var(--border);">Event</th>
                <th style="padding:0.6rem 0.9rem;text-align:left;font-weight:600;border-bottom:1px solid var(--border);">Date</th>
                <th style="padding:0.6rem 0.9rem;text-align:right;font-weight:600;border-bottom:1px solid var(--border);">Owed</th>
                <th style="padding:0.6rem 0.9rem;text-align:right;font-weight:600;border-bottom:1px solid var(--border);">Paid</th>
                <th style="padding:0.6rem 0.9rem;text-align:center;font-weight:600;border-bottom:1px solid var(--border);">Status</th>
                <th style="padding:0.6rem 0.9rem;text-align:right;font-weight:600;border-bottom:1px solid var(--border);">Actions</th>
            </tr>
        </thead>
        <tbody>${filtered.map((p, i) => {
            const balance = (p.amount_owed || 0) - (p.amount_paid || 0);
            const rowBg = i % 2 === 1 ? 'background:var(--surface-alt,#f8fafc)' : '';
            const statusColor = STATUS_COLORS[p.status] || '#6b7280';
            return `<tr style="${rowBg};border-bottom:1px solid var(--border-light,#f0f0f0);" data-id="${p.id}">
                <td style="padding:0.6rem 0.9rem;">
                    <div style="font-weight:500">${p.manager_name || '—'}</div>
                    ${p.chapter_name ? `<div style="font-size:0.75rem;color:var(--text-muted)">${p.chapter_name}</div>` : ''}
                </td>
                <td style="padding:0.6rem 0.9rem;">${p.event_name || '<span style="color:var(--text-muted)">—</span>'}</td>
                <td style="padding:0.6rem 0.9rem;color:var(--text-muted)">${p.event_date || '—'}</td>
                <td style="padding:0.6rem 0.9rem;text-align:right;font-weight:500">${fmt(p.amount_owed)}</td>
                <td style="padding:0.6rem 0.9rem;text-align:right;color:#16a34a">${p.amount_paid > 0 ? fmt(p.amount_paid) : '<span style="color:var(--text-muted)">—</span>'}</td>
                <td style="padding:0.6rem 0.9rem;text-align:center;">
                    <span style="font-size:0.75rem;font-weight:600;color:${statusColor};background:${statusColor}1a;border:1px solid ${statusColor}40;border-radius:4px;padding:2px 7px;">${p.status}</span>
                </td>
                <td style="padding:0.6rem 0.9rem;text-align:right;white-space:nowrap;">
                    ${p.status !== 'paid' ? `<button class="liab-edit-btn" onclick="openContractorPayModal(${p.id},${p.amount_owed},${p.amount_paid})" title="Record payment">Pay</button> ` : ''}
                    <button class="liab-edit-btn" style="color:#dc2626" onclick="deleteContractorPayout(${p.id})" title="Delete">✕</button>
                </td>
            </tr>`;
        }).join('')}</tbody>
    </table>`;
}

function openContractorPayModal(id, owed, paid) {
    document.getElementById('contractor-pay-id').value = id;
    const remaining = Math.max(0, (owed || 0) - (paid || 0));
    const amtEl = document.getElementById('contractor-pay-amount');
    if (amtEl) { amtEl.value = remaining.toFixed(2); amtEl.focus(); amtEl.select(); }
    const modal = document.getElementById('contractor-pay-modal');
    if (modal) modal.style.display = 'flex';
}

function closeContractorPayModal() {
    const modal = document.getElementById('contractor-pay-modal');
    if (modal) modal.style.display = 'none';
}

async function saveContractorPayment() {
    const id = parseInt(document.getElementById('contractor-pay-id').value);
    const amount = parseFloat(document.getElementById('contractor-pay-amount').value || 0);
    const method = document.getElementById('contractor-pay-method').value;

    const payout = CTRS.payouts.find(p => p.id === id);
    if (!payout) return;
    const newStatus = amount >= (payout.amount_owed || 0) ? 'paid' : amount > 0 ? 'partial' : 'pending';

    const res = await fetch(`/api/accounting/contractors/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ amount_paid: amount, status: newStatus, payment_method: method }),
    }).then(r => r.json()).catch(() => null);

    if (res && res.ok) {
        closeContractorPayModal();
        loadContractors();
        showToast('Payment recorded', 'success');
    } else {
        showToast('Save failed', 'error');
    }
}

function openAddContractorModal() {
    document.getElementById('contractor-manager-select').value = '';
    document.getElementById('contractor-event-name').value = '';
    document.getElementById('contractor-event-date').value = '';
    document.getElementById('contractor-amount-owed').value = '';
    document.getElementById('contractor-notes').value = '';
    document.getElementById('contractor-modal-title').textContent = 'Add Payout';
    const modal = document.getElementById('contractor-modal');
    if (modal) modal.style.display = 'flex';
}

function closeContractorModal() {
    const modal = document.getElementById('contractor-modal');
    if (modal) modal.style.display = 'none';
}

async function saveContractorPayout() {
    const mgr = parseInt(document.getElementById('contractor-manager-select').value);
    if (!mgr) { showToast('Select a manager', 'error'); return; }
    const amount = parseFloat(document.getElementById('contractor-amount-owed').value || 0);
    if (!amount || amount <= 0) { showToast('Enter an amount', 'error'); return; }

    const res = await fetch('/api/accounting/contractors', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            manager_customer_id: mgr,
            event_name: document.getElementById('contractor-event-name').value.trim() || null,
            event_date: document.getElementById('contractor-event-date').value || null,
            amount_owed: amount,
            notes: document.getElementById('contractor-notes').value.trim() || null,
        }),
    }).then(r => r.json()).catch(() => null);

    if (res && res.ok) {
        closeContractorModal();
        loadContractors();
        showToast('Payout added', 'success');
    } else {
        showToast('Save failed', 'error');
    }
}

async function deleteContractorPayout(id) {
    if (!confirm('Delete this payout record?')) return;
    const res = await fetch(`/api/accounting/contractors/${id}`, { method: 'DELETE' })
        .then(r => r.json()).catch(() => null);
    if (res && res.ok) {
        loadContractors();
        showToast('Deleted', 'success');
    } else {
        showToast('Delete failed', 'error');
    }
}

function initContractorsTab() {
    document.getElementById('btn-add-contractor-payout')
        ?.addEventListener('click', openAddContractorModal);
    document.getElementById('contractor-modal-cancel')
        ?.addEventListener('click', closeContractorModal);
    document.getElementById('contractor-modal-save')
        ?.addEventListener('click', saveContractorPayout);
    document.getElementById('contractor-pay-cancel')
        ?.addEventListener('click', closeContractorPayModal);
    document.getElementById('contractor-pay-save')
        ?.addEventListener('click', saveContractorPayment);
    document.getElementById('contractor-filter-status')
        ?.addEventListener('change', renderContractors);
    loadContractors();
}
