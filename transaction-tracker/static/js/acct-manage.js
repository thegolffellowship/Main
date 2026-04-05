/* =========================================================
   Accounting Module — Accounts, Categories & CSV Import
   ========================================================= */

// ── Accounts Tab ─────────────────────────────────────────

async function loadAccounts() {
    try {
        const data = await api('/accounts/balances');
        renderAccountsGrid(data);
    } catch (e) {
        console.error('Accounts load error:', e);
    }
}

function renderAccountsGrid(accounts) {
    const el = $('#accounts-grid');
    if (!accounts.length) {
        el.innerHTML = '<p class="acct-empty">No accounts yet. Click "+ Add Account" to get started.</p>';
        return;
    }
    el.innerHTML = accounts.map(a => `
        <div class="acct-account-card" data-id="${a.id}">
            <div class="acct-account-header">
                <h4>${a.name}</h4>
                <span class="acct-account-type">${a.account_type.replace('_', ' ')}</span>
            </div>
            <div class="acct-account-details">
                ${a.institution ? `<div class="acct-account-inst">${a.institution}${a.last_four ? ' ••' + a.last_four : ''}</div>` : ''}
                <div class="acct-account-balance ${a.current_balance >= 0 ? 'acct-positive' : 'acct-negative'}">
                    ${fmt(a.current_balance)}
                </div>
            </div>
        </div>
    `).join('');
}

function openAccountModal() {
    $('#account-edit-id').value = '';
    $('#account-modal-title').textContent = 'Add Account';
    $('#account-name').value = '';
    $('#account-type').value = 'checking';
    $('#account-institution').value = '';
    $('#account-last-four').value = '';
    $('#account-balance').value = '0';
    $('#account-modal').style.display = 'flex';
}

async function saveAccount() {
    const data = {
        name: $('#account-name').value.trim(),
        account_type: $('#account-type').value,
        entity_id: $('#account-entity').value ? parseInt($('#account-entity').value) : null,
        institution: $('#account-institution').value.trim() || null,
        last_four: $('#account-last-four').value.trim() || null,
        opening_balance: parseFloat($('#account-balance').value) || 0,
    };
    if (!data.name) { alert('Account name is required'); return; }

    try {
        const editId = $('#account-edit-id').value;
        if (editId) {
            await api('/accounts/' + editId, { method: 'PATCH', body: data });
        } else {
            await api('/accounts', { method: 'POST', body: data });
        }
        $('#account-modal').style.display = 'none';
        await reloadMasterData();
        loadAccounts();
    } catch (e) {
        alert('Error: ' + e.message);
    }
}


// ── Categories Tab ───────────────────────────────────────

async function loadCategories() {
    const type = document.querySelector('.acct-cat-type-toggle .acct-subtab.active');
    const catType = type ? type.dataset.cattype : 'expense';
    try {
        const data = await api('/categories' + buildQS({ type: catType }));
        renderCategoriesList(data);
    } catch (e) {
        console.error('Categories load error:', e);
    }
}

function renderCategoriesList(cats) {
    const el = $('#categories-list');
    if (!cats.length) {
        el.innerHTML = '<p class="acct-empty">No categories found</p>';
        return;
    }
    el.innerHTML = `<div class="acct-cat-grid">${cats.map(c => {
        const ent = c.entity_id ? entityName(c.entity_id) : 'All';
        return `<div class="acct-cat-item">
            <span class="acct-cat-name">${c.icon || ''} ${c.name}</span>
            <span class="acct-cat-entity">${ent}</span>
            <button class="btn-icon-sm acct-btn-del" data-id="${c.id}" title="Delete">&times;</button>
        </div>`;
    }).join('')}</div>`;

    el.querySelectorAll('.acct-btn-del').forEach(btn => {
        btn.addEventListener('click', async () => {
            if (!confirm('Delete this category?')) return;
            await api('/categories/' + btn.dataset.id, { method: 'DELETE' });
            loadCategories();
        });
    });
}

function openCategoryModal() {
    $('#category-name').value = '';
    const activeType = document.querySelector('.acct-cat-type-toggle .acct-subtab.active');
    $('#category-type').value = activeType ? activeType.dataset.cattype : 'expense';
    $('#category-modal').style.display = 'flex';
}

async function saveCategory() {
    const data = {
        name: $('#category-name').value.trim(),
        type: $('#category-type').value,
        entity_id: $('#category-entity').value ? parseInt($('#category-entity').value) : null,
    };
    if (!data.name) { alert('Category name is required'); return; }

    try {
        await api('/categories', { method: 'POST', body: data });
        $('#category-modal').style.display = 'none';
        await reloadMasterData();
        loadCategories();
    } catch (e) {
        alert('Error: ' + e.message);
    }
}


// ── CSV Import (Smart Auto-Detect) ───────────────────────

let _csvHeaders = [];
let _csvMapping = {};
let _csvRawFile = null;

function openCsvModal() {
    $('#csv-step-upload').style.display = '';
    $('#csv-step-preview').style.display = 'none';
    $('#csv-file').value = '';
    ACCT.csvData = null;
    _csvHeaders = [];
    _csvMapping = {};
    _csvRawFile = null;
    $('#csv-modal').style.display = 'flex';
}

async function previewCsv() {
    const fileInput = $('#csv-file');
    if (!fileInput.files.length) { alert('Choose a CSV file'); return; }

    _csvRawFile = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', _csvRawFile);

    try {
        const res = await fetch('/api/accounting/import/preview', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.error) { alert(data.error); return; }

        _csvHeaders = data.headers || [];
        _csvMapping = data.mapping || {};
        ACCT.csvData = data.rows;

        renderCsvMapping(_csvHeaders, _csvMapping);
        $('#csv-preview-count').textContent = data.count;
        renderCsvPreview(data.rows);
        showTransferSection(data.rows);
        $('#csv-step-upload').style.display = 'none';
        $('#csv-step-preview').style.display = '';
    } catch (e) {
        alert('Preview error: ' + e.message);
    }
}

function renderCsvMapping(headers, mapping) {
    const el = $('#csv-mapping-row');
    if (!headers.length) { el.innerHTML = ''; return; }

    const fields = [
        { key: 'date', label: 'Date', required: true },
        { key: 'description', label: 'Description', required: true },
        { key: 'amount', label: 'Amount', required: true },
        { key: 'category', label: 'Category', required: false },
        { key: 'memo', label: 'Memo', required: false },
    ];

    el.innerHTML = fields.map(f => {
        const opts = headers.map((h, i) =>
            `<option value="${i}" ${mapping[f.key] === i ? 'selected' : ''}>${h}</option>`
        ).join('');
        const matched = mapping[f.key] != null;
        return `<div class="acct-form-group">
            <label>${f.label} ${f.required ? '*' : ''}</label>
            <select class="csv-col-map" data-field="${f.key}" ${matched ? 'style="border-color:var(--green);"' : ''}>
                <option value="">— skip —</option>
                ${opts}
            </select>
            ${matched ? '<span class="acct-csv-match-ok">auto-matched</span>' : ''}
        </div>`;
    }).join('');
}

async function remapCsv() {
    if (!_csvRawFile) return;

    // Collect user-adjusted mapping from dropdowns
    const formData = new FormData();
    formData.append('file', _csvRawFile);
    $$('.csv-col-map').forEach(sel => {
        if (sel.value !== '') {
            formData.append(sel.dataset.field + '_col', sel.value);
        }
    });

    try {
        const res = await fetch('/api/accounting/import/preview', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.error) { alert(data.error); return; }

        _csvMapping = data.mapping || {};
        ACCT.csvData = data.rows;

        renderCsvMapping(data.headers || _csvHeaders, _csvMapping);
        $('#csv-preview-count').textContent = data.count;
        renderCsvPreview(data.rows);
    } catch (e) {
        alert('Re-map error: ' + e.message);
    }
}

function renderCsvPreview(rows) {
    const el = $('#csv-preview-table');
    if (!rows.length) { el.innerHTML = '<p class="acct-empty">No transactions found in CSV. Check column mapping above.</p>'; return; }
    const preview = rows.slice(0, 50);
    const hasCat = rows.some(r => r.category);
    const hasMemo = rows.some(r => r.memo);
    el.innerHTML = `<table class="acct-table">
        <thead><tr>
            <th>Date</th><th>Description</th>
            ${hasCat ? '<th>Category</th>' : ''}
            <th class="text-right">Amount</th><th>Type</th>
            ${hasMemo ? '<th>Memo</th>' : ''}
        </tr></thead>
        <tbody>${preview.map(r => `<tr>
            <td>${r.date}</td>
            <td>${r.description}</td>
            ${hasCat ? `<td class="acct-muted">${r.category || ''}</td>` : ''}
            <td class="text-right ${r.type === 'income' ? 'acct-positive' : 'acct-negative'}">${fmt(r.amount)}</td>
            <td><span class="acct-type-badge acct-type-${r.type}">${r.type}</span></td>
            ${hasMemo ? `<td class="acct-muted">${r.memo || ''}</td>` : ''}
        </tr>`).join('')}</tbody>
    </table>${rows.length > 50 ? `<p class="acct-muted">Showing 50 of ${rows.length} transactions...</p>` : ''}`;
}

function showTransferSection(rows) {
    const transferCount = rows.filter(r => r.type === 'transfer').length;
    const section = $('#csv-transfer-section');
    if (transferCount === 0) {
        section.style.display = 'none';
        return;
    }
    section.style.display = '';
    $('#csv-transfer-count').textContent = transferCount;

    // Populate transfer account dropdown (exclude the import account)
    const importAccountId = $('#csv-account').value;
    const opts = ACCT.accounts
        .filter(a => String(a.id) !== importAccountId)
        .map(a => `<option value="${a.id}">${a.name}</option>`)
        .join('');
    $('#csv-transfer-account').innerHTML =
        '<option value="">— Don\'t link (decide later) —</option>' + opts;
}

async function commitCsvImport() {
    if (!ACCT.csvData || !ACCT.csvData.length) return;
    const accountId = $('#csv-account').value;
    const entityId = $('#csv-entity').value;
    if (!accountId || !entityId) { alert('Select an account and entity'); return; }

    const transferAccountId = $('#csv-transfer-account') && $('#csv-transfer-account').value
        ? parseInt($('#csv-transfer-account').value) : null;

    try {
        const res = await api('/import/commit', {
            method: 'POST',
            body: {
                rows: ACCT.csvData,
                account_id: parseInt(accountId),
                entity_id: parseInt(entityId),
                transfer_account_id: transferAccountId,
            },
        });
        const parts = [`Imported ${res.imported} transactions`];
        if (res.matched) parts.push(`${res.matched} transfers matched to existing`);
        alert(parts.join(', '));
        $('#csv-modal').style.display = 'none';
        refreshActiveTab();
    } catch (e) {
        alert('Import error: ' + e.message);
    }
}


// ── Reports Tab ──────────────────────────────────────────

async function loadReports() {
    const reportType = $('#report-type').value;
    const preset = $('#report-period').value;
    const { start, end } = getDateRange(preset);
    const qs = buildQS({ entity_id: ACCT.activeEntity, start_date: start, end_date: end });

    try {
        if (reportType === 'pnl') {
            const data = await api('/reports/summary' + qs);
            renderPnlReport(data);
        } else if (reportType === 'category_breakdown') {
            const [expenses, income] = await Promise.all([
                api('/reports/categories' + buildQS({ entity_id: ACCT.activeEntity, type: 'expense', start_date: start, end_date: end })),
                api('/reports/categories' + buildQS({ entity_id: ACCT.activeEntity, type: 'income', start_date: start, end_date: end })),
            ]);
            renderCategoryReport(expenses, income);
        } else if (reportType === 'monthly_trend') {
            const data = await api('/reports/monthly' + buildQS({ entity_id: ACCT.activeEntity, months: 24 }));
            renderMonthlyReport(data);
        }
    } catch (e) {
        console.error('Report error:', e);
    }
}

function renderPnlReport(data) {
    const el = $('#report-content');
    el.innerHTML = `
        <div class="acct-report-pnl">
            <h3>Income</h3>
            <table class="acct-table">
                <tbody>
                    ${data.income_by_category.map(r => `<tr><td>${r.category || 'Uncategorized'}</td><td class="text-right acct-positive">${fmt(r.total)}</td></tr>`).join('')}
                    <tr class="acct-report-total"><td><strong>Total Income</strong></td><td class="text-right acct-positive"><strong>${fmt(data.total_income)}</strong></td></tr>
                </tbody>
            </table>
            <h3>Expenses</h3>
            <table class="acct-table">
                <tbody>
                    ${data.expense_by_category.map(r => `<tr><td>${r.category || 'Uncategorized'}</td><td class="text-right acct-negative">${fmt(r.total)}</td></tr>`).join('')}
                    <tr class="acct-report-total"><td><strong>Total Expenses</strong></td><td class="text-right acct-negative"><strong>${fmt(data.total_expenses)}</strong></td></tr>
                </tbody>
            </table>
            <div class="acct-report-net">
                <h3>Net ${data.net >= 0 ? 'Profit' : 'Loss'}</h3>
                <span class="${data.net >= 0 ? 'acct-positive' : 'acct-negative'}">${fmt(data.net)}</span>
            </div>
        </div>`;
}

function renderCategoryReport(expenses, income) {
    const el = $('#report-content');
    const renderBars = (items, color) => {
        if (!items.length) return '<p class="acct-empty">No data</p>';
        const max = Math.max(...items.map(i => i.total), 1);
        return items.map(i => `
            <div class="acct-cat-bar-row">
                <span class="acct-cat-bar-label">${i.category} (${i.count})</span>
                <div class="acct-cat-bar-track">
                    <div class="acct-cat-bar-fill" style="width:${(i.total/max*100).toFixed(1)}%;background:${color}"></div>
                </div>
                <span class="acct-cat-bar-val">${fmt(i.total)}</span>
            </div>`).join('');
    };
    el.innerHTML = `
        <h3>Expenses by Category</h3>
        ${renderBars(expenses, 'var(--red)')}
        <h3 style="margin-top:2rem;">Income by Category</h3>
        ${renderBars(income, 'var(--green)')}`;
}

function renderMonthlyReport(data) {
    const el = $('#report-content');
    if (!data.length) { el.innerHTML = '<p class="acct-empty">No data</p>'; return; }
    el.innerHTML = `<table class="acct-table">
        <thead><tr><th>Month</th><th class="text-right">Income</th><th class="text-right">Expenses</th><th class="text-right">Net</th></tr></thead>
        <tbody>${data.map(d => `<tr>
            <td>${d.month}</td>
            <td class="text-right acct-positive">${fmt(d.income)}</td>
            <td class="text-right acct-negative">${fmt(d.expenses)}</td>
            <td class="text-right ${d.net >= 0 ? 'acct-positive' : 'acct-negative'}">${fmt(d.net)}</td>
        </tr>`).join('')}</tbody>
    </table>`;
}


// ── Reconciliation Tab ──────────────────────────────────

let _reconFilter = 'all';
let _reconData = null;

async function loadReconciliation() {
    // Load chart of accounts
    try {
        const coa = await api('/chart-of-accounts');
        renderChartOfAccounts(coa);
    } catch (e) {}
}

function renderChartOfAccounts(coa) {
    const el = $('#coa-table');
    if (!coa.length) { el.innerHTML = '<p class="acct-empty">No accounts configured</p>'; return; }
    const grouped = {};
    for (const a of coa) {
        if (!grouped[a.account_type]) grouped[a.account_type] = [];
        grouped[a.account_type].push(a);
    }
    let html = '';
    for (const [type, accounts] of Object.entries(grouped)) {
        html += `<h4 style="margin:1rem 0 0.3rem; text-transform:capitalize; color:var(--text-muted); font-size:0.8rem;">${type}</h4>`;
        html += '<table class="acct-table"><thead><tr><th>Code</th><th>Name</th><th>Schedule C</th></tr></thead><tbody>';
        for (const a of accounts) {
            html += `<tr><td style="font-weight:600;">${a.code}</td><td>${a.name}</td><td class="acct-muted">${a.schedule_c_line || '—'}</td></tr>`;
        }
        html += '</tbody></table>';
    }
    el.innerHTML = html;
}

async function importBankStatement() {
    const fileInput = $('#recon-file');
    if (!fileInput.files.length) { alert('Choose a CSV file'); return; }
    const last4 = $('#recon-last4').value.trim();
    if (!last4) { alert('Enter account last 4 digits'); return; }

    const fd = new FormData();
    fd.append('file', fileInput.files[0]);
    fd.append('account_last4', last4);

    try {
        const res = await fetch('/api/accounting/bank-import', { method: 'POST', body: fd });
        const data = await res.json();
        if (data.error) { alert(data.error); return; }
        const el = $('#recon-import-result');
        el.style.display = '';
        el.innerHTML = `<div class="acct-csv-preview-info" style="margin:1rem 0;">
            Imported <strong>${data.imported}</strong> rows (${data.skipped} skipped as duplicates).
            Format: ${data.detected_format}. Import ID: ${data.import_id}
        </div>`;
    } catch (e) {
        alert('Import error: ' + e.message);
    }
}

async function runReconciliation() {
    const month = $('#recon-month').value;
    const last4 = $('#recon-last4').value.trim();
    try {
        const res = await fetch('/api/accounting/reconcile', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ month: month || null, account_last4: last4 || null }),
        });
        _reconData = await res.json();
        if (_reconData.error) { alert(_reconData.error); return; }
        $('#recon-filter-bar').style.display = 'flex';
        $('#recon-summary').textContent =
            `${_reconData.matched} matched, ${_reconData.unmatched_bank} unmatched in bank, ${_reconData.unmatched_tracker} missing from bank`;
        renderReconResults();
    } catch (e) {
        alert('Reconciliation error: ' + e.message);
    }
}

function renderReconResults() {
    if (!_reconData) return;
    const el = $('#recon-results');
    let rows = [];

    if (_reconFilter === 'all' || _reconFilter === 'matched' || _reconFilter === 'unmatched_bank') {
        for (const r of _reconData.bank_results) {
            if (_reconFilter !== 'all' && r.match_status !== _reconFilter) continue;
            rows.push(r);
        }
    }
    if (_reconFilter === 'all' || _reconFilter === 'unmatched_tracker') {
        for (const r of _reconData.tracker_unmatched) {
            rows.push(r);
        }
    }

    if (!rows.length) {
        el.innerHTML = '<p class="acct-empty">No results for this filter</p>';
        return;
    }

    el.innerHTML = `<table class="acct-table acct-table-full">
        <thead><tr><th>Status</th><th>Date</th><th>Description</th><th class="text-right">Amount</th><th>Match</th></tr></thead>
        <tbody>${rows.map(r => {
            const status = r.match_status === 'matched' ? '<span style="color:var(--green);">&#10003; Matched</span>'
                : r.match_status === 'unmatched_bank' ? '<span style="color:var(--red);">&#9888; In Bank Only</span>'
                : '<span style="color:#d97706;">&#128308; Missing from Bank</span>';
            const desc = r.description || '';
            const amt = r.amount != null ? fmt(r.amount) : '—';
            const match = r.matched_detail || '—';
            const date = r.transaction_date || r.date || '';
            return `<tr>
                <td>${status}</td>
                <td>${date}</td>
                <td>${desc}</td>
                <td class="text-right">${amt}</td>
                <td class="acct-muted">${match}</td>
            </tr>`;
        }).join('')}</tbody></table>`;
}

async function closeMonth() {
    const month = $('#recon-month').value;
    if (!month) { alert('Select a month first'); return; }
    if (!confirm(`Close period ${month}? This generates the month-end summary.`)) return;
    try {
        const res = await fetch('/api/accounting/close-period', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ period: month }),
        });
        const data = await res.json();
        alert(`Period ${month} closed.\nIncome: ${fmt(data.total_income)}\nExpenses: ${fmt(data.total_expenses)}\nNet: ${fmt(data.net)}\nTax Reserve: ${fmt(data.tax_reserve)}\nUnreconciled: ${data.unreconciled}`);
    } catch (e) {
        alert('Close error: ' + e.message);
    }
}
