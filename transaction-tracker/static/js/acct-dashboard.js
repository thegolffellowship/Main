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
        if (stats.pending_expenses > 0) parts.push(`${stats.pending_expenses} pending`);
        if (stats.uncategorized > 0) parts.push(`${stats.uncategorized} uncategorized`);
        statusEl.innerHTML = `<span class="acct-negative">${parts.join(' · ')} — needs review</span>`;
        btn.textContent = `Review Batch (${stats.pending_expenses || stats.uncategorized})`;
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

    const srcBadge = (src) => {
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

        return `<div class="batch-row" data-id="${item.id}" style="display:flex; align-items:flex-start; gap:0.75rem; padding:0.65rem 1rem; border-bottom:1px solid var(--border); ${isDupe ? 'background:#fff7ed;' : ''}">
            <div style="padding-top:2px; flex-shrink:0;">
                <input type="checkbox" class="batch-chk" data-id="${item.id}" ${isDupe ? '' : 'checked'} style="width:16px; height:16px; cursor:pointer;">
            </div>
            <div style="flex:1; min-width:0;">
                <div style="display:flex; align-items:center; gap:0.4rem; flex-wrap:wrap; margin-bottom:0.3rem;">
                    <span style="font-size:0.82rem; color:var(--text-muted);">${item.date || '—'}</span>
                    ${srcBadge(item.source_type)}
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
        const id  = parseInt(row.dataset.id);
        const chk = row.querySelector('.batch-chk');
        if (!chk?.checked) return;
        const cat = row.querySelector('.batch-cat')?.value || '';
        const ent = row.querySelector('.batch-ent')?.value || '';
        items.push({ id, category_name: cat || null, entity_name: ent || null });
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
