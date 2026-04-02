/* =========================================================
   Accounting Module — Transactions Tab & Modal
   ========================================================= */

async function loadTransactions() {
    const qs = buildQS({
        entity_id: ACCT.activeEntity,
        account_id: $('#txn-filter-account').value || null,
        category_id: $('#txn-filter-category').value || null,
        type: $('#txn-filter-type').value || null,
        search: $('#txn-search').value || null,
        limit: ACCT.txnLimit,
        offset: ACCT.txnPage * ACCT.txnLimit,
    });
    try {
        const data = await api('/transactions' + qs);
        renderTransactionList(data.transactions, data.total);
    } catch (e) {
        console.error('Transaction load error:', e);
    }
}

function renderTransactionList(txns, total) {
    const el = $('#txn-list');
    if (!txns.length) {
        el.innerHTML = '<p class="acct-empty">No transactions found</p>';
        $('#txn-pagination').innerHTML = '';
        return;
    }

    el.innerHTML = `<table class="acct-table acct-table-full">
        <thead><tr>
            <th>Date</th><th>Description</th><th>Splits</th>
            <th class="text-right">Amount</th><th>Type</th><th>Account</th>
            <th></th>
        </tr></thead>
        <tbody>${txns.map(t => {
            const splitBadges = t.splits.map(s =>
                `<span class="acct-split-badge" style="border-color:${s.entity_color || '#6b7280'}">
                    <strong>${s.entity_name || '?'}</strong> ${s.category_name || ''} ${fmt(s.amount)}
                </span>`
            ).join(' ');
            return `<tr class="acct-txn-row" data-id="${t.id}">
                <td>${t.date}</td>
                <td>
                    ${t.description}
                    ${t.is_reconciled ? '<span class="acct-reconciled" title="Reconciled">&#10003;</span>' : ''}
                    ${t.tags.map(tg => `<span class="acct-tag-chip" style="background:${tg.color}">${tg.name}</span>`).join('')}
                </td>
                <td class="acct-split-cell">${splitBadges}</td>
                <td class="text-right ${t.type === 'income' ? 'acct-positive' : 'acct-negative'}">${fmt(t.total_amount)}</td>
                <td><span class="acct-type-badge acct-type-${t.type}">${t.type}</span></td>
                <td>${t.account_name || '—'}</td>
                <td>
                    <button class="btn-icon-sm acct-btn-del" data-id="${t.id}" title="Delete">&times;</button>
                </td>
            </tr>`;
        }).join('')}</tbody></table>`;

    // Click row to edit
    el.querySelectorAll('.acct-txn-row').forEach(row => {
        row.addEventListener('click', (e) => {
            if (e.target.closest('.acct-btn-del')) return;
            openEditTransaction(parseInt(row.dataset.id));
        });
    });

    // Delete buttons
    el.querySelectorAll('.acct-btn-del').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            if (!confirm('Delete this transaction?')) return;
            await api('/transactions/' + btn.dataset.id, { method: 'DELETE' });
            loadTransactions();
        });
    });

    // Pagination
    const pages = Math.ceil(total / ACCT.txnLimit);
    const pagEl = $('#txn-pagination');
    if (pages <= 1) { pagEl.innerHTML = ''; return; }
    let html = '';
    for (let i = 0; i < pages; i++) {
        html += `<button class="acct-page-btn ${i === ACCT.txnPage ? 'active' : ''}" data-page="${i}">${i + 1}</button>`;
    }
    pagEl.innerHTML = html;
    pagEl.querySelectorAll('.acct-page-btn').forEach(b => {
        b.addEventListener('click', () => { ACCT.txnPage = parseInt(b.dataset.page); loadTransactions(); });
    });
}

// ── Transaction Modal ────────────────────────────────────

function populateDropdowns() {
    // Account dropdowns
    const acctOpts = '<option value="">— None —</option>' +
        ACCT.accounts.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
    ['#txn-account', '#txn-transfer-to', '#csv-account'].forEach(sel => {
        const el = $(sel);
        if (el) el.innerHTML = acctOpts;
    });

    // Entity dropdowns
    const entOpts = ACCT.entities.map(e => `<option value="${e.id}">${e.short_name}</option>`).join('');
    ['#account-entity', '#csv-entity', '#category-entity'].forEach(sel => {
        const el = $(sel);
        if (el) {
            const blank = sel === '#category-entity' ? '<option value="">All Entities</option>' : '';
            el.innerHTML = blank + entOpts;
        }
    });

    // Filter dropdowns
    const filterAcct = $('#txn-filter-account');
    if (filterAcct) {
        filterAcct.innerHTML = '<option value="">All Accounts</option>' +
            ACCT.accounts.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
    }
    const filterCat = $('#txn-filter-category');
    if (filterCat) {
        filterCat.innerHTML = '<option value="">All Categories</option>' +
            ACCT.categories.map(c => `<option value="${c.id}">[${c.type}] ${c.name}</option>`).join('');
    }
}

function openNewTransaction() {
    $('#txn-edit-id').value = '';
    $('#txn-modal-title').textContent = 'Add Transaction';
    $('#txn-date').value = new Date().toISOString().split('T')[0];
    $('#txn-description').value = '';
    $('#txn-amount').value = '';
    $('#txn-type').value = 'expense';
    $('#txn-account').value = '';
    $('#txn-notes').value = '';
    $('#receipt-filename').textContent = '';
    $('#transfer-row').style.display = 'none';

    // Default single split
    const defaultEntity = ACCT.activeEntity || (ACCT.entities[0] && ACCT.entities[0].id);
    renderSplitRows([{ entity_id: defaultEntity, category_id: '', amount: '', memo: '' }]);
    renderTagChips([]);

    $('#txn-modal').style.display = 'flex';
}

async function openEditTransaction(id) {
    try {
        const txn = await api('/transactions/' + id);
        $('#txn-edit-id').value = txn.id;
        $('#txn-modal-title').textContent = 'Edit Transaction';
        $('#txn-date').value = txn.date;
        $('#txn-description').value = txn.description;
        $('#txn-amount').value = txn.total_amount;
        $('#txn-type').value = txn.type;
        $('#txn-account').value = txn.account_id || '';
        $('#txn-notes').value = txn.notes || '';
        $('#receipt-filename').textContent = txn.receipt_path ? txn.receipt_path.split('/').pop() : '';
        $('#transfer-row').style.display = txn.type === 'transfer' ? '' : 'none';
        if (txn.transfer_to_account_id) $('#txn-transfer-to').value = txn.transfer_to_account_id;

        renderSplitRows(txn.splits.map(s => ({
            entity_id: s.entity_id, category_id: s.category_id || '', amount: s.amount, memo: s.memo || ''
        })));
        renderTagChips(txn.tags.map(t => t.id));

        $('#txn-modal').style.display = 'flex';
    } catch (e) {
        alert('Error loading transaction: ' + e.message);
    }
}

async function saveTransaction() {
    const editId = $('#txn-edit-id').value;
    const data = {
        date: $('#txn-date').value,
        description: $('#txn-description').value.trim(),
        total_amount: parseFloat($('#txn-amount').value),
        type: $('#txn-type').value,
        account_id: $('#txn-account').value ? parseInt($('#txn-account').value) : null,
        transfer_to_account_id: $('#txn-type').value === 'transfer' && $('#txn-transfer-to').value
            ? parseInt($('#txn-transfer-to').value) : null,
        notes: $('#txn-notes').value.trim() || null,
        splits: collectSplits(),
        tag_ids: collectTagIds(),
    };

    if (!data.date || !data.description || isNaN(data.total_amount)) {
        alert('Please fill in date, description, and amount');
        return;
    }
    if (!data.splits.length) {
        alert('Add at least one split');
        return;
    }

    try {
        if (editId) {
            await api('/transactions/' + editId, { method: 'PUT', body: data });
        } else {
            await api('/transactions', { method: 'POST', body: data });
        }
        closeTxnModal();
        refreshActiveTab();
    } catch (e) {
        alert('Error: ' + e.message);
    }
}

function closeTxnModal() {
    $('#txn-modal').style.display = 'none';
}

// ── Split Rows ───────────────────────────────────────────

function renderSplitRows(splits) {
    const list = $('#splits-list');
    list.innerHTML = splits.map((s, i) => splitRowHTML(s, i)).join('');
    updateSplitTotal();
    bindSplitEvents();
}

function splitRowHTML(s, idx) {
    const entityOpts = ACCT.entities.map(e =>
        `<option value="${e.id}" ${e.id == s.entity_id ? 'selected' : ''}>${e.short_name}</option>`
    ).join('');
    const catOpts = '<option value="">—</option>' + ACCT.categories.map(c =>
        `<option value="${c.id}" ${c.id == s.category_id ? 'selected' : ''}>[${c.type[0].toUpperCase()}] ${c.name}</option>`
    ).join('');
    return `<div class="acct-split-row" data-idx="${idx}">
        <select class="split-entity acct-select-sm">${entityOpts}</select>
        <select class="split-category acct-select-sm">${catOpts}</select>
        <input type="number" class="split-amount acct-input-sm" step="0.01" value="${s.amount || ''}" placeholder="0.00">
        <input type="text" class="split-memo acct-input-sm" value="${s.memo || ''}" placeholder="Memo">
        <button class="btn-icon-sm split-remove" title="Remove">&times;</button>
    </div>`;
}

function bindSplitEvents() {
    $$('.split-amount').forEach(inp => inp.addEventListener('input', updateSplitTotal));
    $$('.split-remove').forEach(btn => btn.addEventListener('click', (e) => {
        e.target.closest('.acct-split-row').remove();
        updateSplitTotal();
    }));
}

function addSplitRow() {
    const list = $('#splits-list');
    const idx = list.children.length;
    const defaultEntity = ACCT.activeEntity || (ACCT.entities[0] && ACCT.entities[0].id);
    const remaining = getRemainingAmount();
    list.insertAdjacentHTML('beforeend', splitRowHTML({
        entity_id: defaultEntity, category_id: '', amount: remaining > 0 ? remaining.toFixed(2) : '', memo: ''
    }, idx));
    updateSplitTotal();
    bindSplitEvents();
}

function getRemainingAmount() {
    const total = parseFloat($('#txn-amount').value) || 0;
    let splitSum = 0;
    $$('.split-amount').forEach(inp => splitSum += parseFloat(inp.value) || 0);
    return Math.round((total - splitSum) * 100) / 100;
}

function updateSplitTotal() {
    let sum = 0;
    $$('.split-amount').forEach(inp => sum += parseFloat(inp.value) || 0);
    const total = parseFloat($('#txn-amount').value) || 0;
    const diff = Math.round((total - sum) * 100) / 100;
    $('#splits-total').textContent = fmt(sum);
    const diffEl = $('#splits-diff');
    if (Math.abs(diff) > 0.01) {
        diffEl.textContent = `(${diff > 0 ? '+' : ''}${fmt(diff)} remaining)`;
        diffEl.className = 'acct-splits-diff acct-negative';
    } else {
        diffEl.textContent = '(balanced)';
        diffEl.className = 'acct-splits-diff acct-positive';
    }
}

function collectSplits() {
    const splits = [];
    $$('.acct-split-row').forEach(row => {
        const amt = parseFloat(row.querySelector('.split-amount').value);
        if (!amt) return;
        splits.push({
            entity_id: parseInt(row.querySelector('.split-entity').value),
            category_id: row.querySelector('.split-category').value ? parseInt(row.querySelector('.split-category').value) : null,
            amount: amt,
            memo: row.querySelector('.split-memo').value.trim() || null,
        });
    });
    return splits;
}

// ── Tags ─────────────────────────────────────────────────

let _selectedTagIds = [];

function renderTagChips(selectedIds) {
    _selectedTagIds = [...selectedIds];
    const el = $('#txn-tags-input');
    const chips = ACCT.tags.map(t => {
        const sel = _selectedTagIds.includes(t.id);
        return `<span class="acct-tag-chip acct-tag-selectable ${sel ? 'selected' : ''}"
                      style="background:${sel ? t.color : 'transparent'}; border-color:${t.color}; color:${sel ? '#fff' : t.color}"
                      data-id="${t.id}">${t.name}</span>`;
    }).join('');
    el.innerHTML = chips;
    el.querySelectorAll('.acct-tag-selectable').forEach(chip => {
        chip.addEventListener('click', () => {
            const id = parseInt(chip.dataset.id);
            if (_selectedTagIds.includes(id)) {
                _selectedTagIds = _selectedTagIds.filter(x => x !== id);
            } else {
                _selectedTagIds.push(id);
            }
            renderTagChips(_selectedTagIds);
        });
    });
}

function collectTagIds() { return [..._selectedTagIds]; }
