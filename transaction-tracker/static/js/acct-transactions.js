/* =========================================================
   Accounting Module — Transactions Tab & Modal
   ========================================================= */

async function loadTransactions() {
    const qs = buildQS({
        entity_id: ACCT.activeEntity,
        account_id: $('#txn-filter-account').value || null,
        category_id: $('#txn-filter-category').value || null,
        type: $('#txn-filter-type').value || null,
        source: $('#txn-filter-source').value || null,
        review_status: $('#txn-filter-review').value || null,
        search: $('#txn-search').value || null,
        limit: ACCT.txnLimit,
        offset: ACCT.txnPage * ACCT.txnLimit,
    });
    try {
        const data = await api('/transactions/unified' + qs);
        renderTransactionList(data.transactions, data.total);
    } catch (e) {
        console.error('Transaction load error:', e);
    }
}

const _SOURCE_LABELS = {
    chase_alert: 'Chase Alert',
    venmo: 'Venmo',
    receipt: 'Receipt',
};

function renderTransactionList(txns, total) {
    const el = $('#txn-list');
    if (!txns.length) {
        el.innerHTML = '<p class="acct-empty">No transactions found</p>';
        $('#txn-pagination').innerHTML = '';
        return;
    }

    // Shared helpers
    function _txnMeta(t) {
        const isExp = t._is_expense;
        const splitBadges = t.splits.map(s =>
            `<span class="acct-split-badge" style="border-color:${s.entity_color || '#6b7280'}">
                <strong>${s.entity_name || '?'}</strong> ${s.category_name || ''}${s.event_name ? ' <em>' + s.event_name + '</em>' : ''} ${fmt(s.amount)}
            </span>`
        ).join(' ');
        const srcLabel = _SOURCE_LABELS[t.source];
        const sourceBadge = srcLabel
            ? `<span class="acct-source-badge acct-source-${t.source}">${srcLabel}</span>`
            : '';
        let reviewBadge = '';
        if (isExp && t.review_status === 'pending') {
            reviewBadge = '<span class="acct-review-badge acct-review-pending" title="Needs Review">Pending</span>';
        } else if (isExp && t.review_status === 'ignored') {
            reviewBadge = '<span class="acct-review-badge acct-review-ignored" title="Ignored">Ignored</span>';
        }
        const reconBadge = !isExp && t.is_reconciled ? '<span class="acct-reconciled" title="Reconciled">&#10003;</span>' : '';
        const tagBadges = (t.tags || []).map(tg => `<span class="acct-tag-chip" style="background:${tg.color}">${tg.name}</span>`).join('');
        return { isExp, splitBadges, sourceBadge, reviewBadge, reconBadge, tagBadges };
    }

    // Desktop table
    const tableHTML = `<table class="acct-table acct-table-full acct-table-mobile-hide">
        <thead><tr>
            <th>Date</th><th>Description</th><th>Splits</th>
            <th class="text-right">Amount</th><th>Type</th><th>Account</th>
            <th></th>
        </tr></thead>
        <tbody>${txns.map(t => {
            const m = _txnMeta(t);
            const rowClass = m.isExp
                ? `acct-txn-row acct-txn-expense${t.review_status === 'ignored' ? ' acct-txn-ignored' : ''}`
                : 'acct-txn-row';
            const rowData = m.isExp
                ? `data-id="${t.id}" data-expense-id="${t.expense_id}"`
                : `data-id="${t.id}"`;

            return `<tr class="${rowClass}" ${rowData}>
                <td>${t.date || ''}</td>
                <td>
                    ${t.description || ''}
                    ${m.sourceBadge}${m.reviewBadge}${m.reconBadge}${m.tagBadges}
                </td>
                <td class="acct-split-cell">${m.splitBadges}</td>
                <td class="text-right ${t.type === 'income' ? 'acct-positive' : 'acct-negative'}">${fmt(t.total_amount)}</td>
                <td><span class="acct-type-badge acct-type-${t.type}">${t.type}</span></td>
                <td>${t.account_name || '—'}</td>
                <td>
                    ${m.isExp ? '' : `<button class="btn-icon-sm acct-btn-del" data-id="${t.id}" title="Delete">&times;</button>`}
                </td>
            </tr>`;
        }).join('')}</tbody></table>`;

    // Mobile cards — build option strings once
    const _acctOpts = '<option value="">— Account —</option>' +
        ACCT.accounts.map(a => `<option value="${a.id}">${a.name}</option>`).join('');
    const _entOpts = ACCT.entities.map(e =>
        `<option value="${e.id}">${e.short_name}</option>`).join('');
    const _expEntOpts = '<option value="">— Entity —</option>' +
        ACCT.entities.map(e => `<option value="${e.short_name}">${e.short_name}</option>`).join('');
    const _expCatOpts = '<option value="">— Category —</option>' +
        ACCT.categories.filter(c => c.type === 'expense').map(c =>
            `<option value="${c.name}">${c.name}</option>`).join('');

    const _expAcctOpts = '<option value="">— Account —</option>' +
        ACCT.accounts.map(a => `<option value="${a.name}">${a.name}</option>`).join('') +
        '<option value="__new__">+ New Account</option>';

    function _catOptsForType(type, selectedId) {
        return '<option value="">— Category —</option>' +
            ACCT.categories.filter(c => c.type === type).map(c =>
                `<option value="${c.id}" ${c.id === selectedId ? 'selected' : ''}>${c.name}</option>`
            ).join('');
    }

    function _tagChipsHTML(tags) {
        if (!ACCT.tags.length) return '';
        const tagIds = (tags || []).map(tg => tg.id);
        return ACCT.tags.map(t => {
            const sel = tagIds.includes(t.id);
            return `<span class="acct-tag-chip acct-tag-selectable ${sel ? 'selected' : ''}"
                style="background:${sel ? t.color : 'transparent'}; border-color:${t.color}; color:${sel ? '#fff' : t.color}"
                data-tag-id="${t.id}">${t.name}</span>`;
        }).join('');
    }

    const cardsHTML = `<div class="acct-mobile-cards">${txns.map(t => {
        const m = _txnMeta(t);
        const cardClass = m.isExp
            ? `acct-mobile-card acct-mc-expense${t.review_status === 'ignored' ? ' acct-mc-ignored' : ''}`
            : 'acct-mobile-card';
        const cardData = m.isExp
            ? `data-id="${t.id}" data-expense-id="${t.expense_id}"`
            : `data-id="${t.id}"`;
        const split0 = t.splits[0] || {};

        if (m.isExp) {
            // ── Expense transaction: entity + category dropdowns + approve/ignore
            const sug = t.suggestion;
            const sugBadge = sug
                ? `<span class="acct-mc-sug-badge acct-mc-sug-${sug.confidence}" title="${sug.source || ''}">${
                    sug.confidence === 'learned' ? 'Learned' :
                    sug.confidence === 'rule' ? 'Rule' :
                    sug.confidence === 'history' ? 'History' :
                    sug.confidence === 'similar' ? 'Similar' : 'Suggested'
                }</span>`
                : '';
            return `<div class="${cardClass}" ${cardData} data-sug-cat="${sug ? (sug.category || '') : ''}" data-sug-ent="${sug ? (sug.entity || '') : ''}">
                <div class="acct-mobile-card-top">
                    <div class="acct-mc-left">
                        <div class="acct-mc-date">${t.date || ''} ${m.sourceBadge}${m.reviewBadge}${sugBadge}</div>
                        <div class="acct-mc-desc">${t.description || ''}</div>
                    </div>
                    <div class="acct-mc-right">
                        <span class="acct-mc-amount ${t.type === 'income' ? 'acct-positive' : 'acct-negative'}">${fmt(t.total_amount)}</span>
                        <span class="acct-mc-chevron">&#9654;</span>
                    </div>
                </div>
                <div class="acct-mobile-card-details">
                    <div class="acct-mc-controls">
                        <select class="mc-exp-entity" data-expense-id="${t.expense_id}">${_expEntOpts}</select>
                        <select class="mc-exp-category" data-expense-id="${t.expense_id}">${_expCatOpts}</select>
                        <select class="mc-exp-account" data-expense-id="${t.expense_id}">${_expAcctOpts}</select>
                    </div>
                    ${m.splitBadges ? `<div class="acct-mc-splits">${m.splitBadges}</div>` : ''}
                    <div class="acct-mc-btn-row">
                        <button class="btn btn-sm mc-exp-approve" data-expense-id="${t.expense_id}" style="background:var(--green);color:#fff;border:none;flex:1;">${sug ? 'Approve' : 'Approve'}</button>
                        <button class="btn btn-secondary btn-sm mc-exp-ignore" data-expense-id="${t.expense_id}" style="flex:1;">Ignore</button>
                        <button class="btn btn-secondary btn-sm mc-open-detail" style="flex:0 0 auto;">Edit</button>
                    </div>
                </div>
            </div>`;
        }

        // ── Regular transaction: entity + category + account + tags
        return `<div class="${cardClass}" ${cardData}>
            <div class="acct-mobile-card-top">
                <div class="acct-mc-left">
                    <div class="acct-mc-date">${t.date || ''} ${m.sourceBadge}${m.reconBadge}</div>
                    <div class="acct-mc-desc">${t.description || ''} ${m.tagBadges}</div>
                </div>
                <div class="acct-mc-right">
                    <span class="acct-mc-amount ${t.type === 'income' ? 'acct-positive' : 'acct-negative'}">${fmt(t.total_amount)}</span>
                    <span class="acct-mc-chevron">&#9654;</span>
                </div>
            </div>
            <div class="acct-mobile-card-details">
                <div class="acct-mc-controls">
                    <select class="mc-entity" data-id="${t.id}">${_entOpts}</select>
                    <select class="mc-category" data-id="${t.id}" data-type="${t.type}">${_catOptsForType(t.type, split0.category_id)}</select>
                    <select class="mc-account" data-id="${t.id}">${_acctOpts}</select>
                </div>
                ${ACCT.tags.length ? `<div class="acct-mc-tags" data-id="${t.id}">${_tagChipsHTML(t.tags)}</div>` : ''}
                ${m.splitBadges ? `<div class="acct-mc-splits">${m.splitBadges}</div>` : ''}
                <div class="acct-mc-btn-row">
                    <button class="btn btn-secondary btn-sm mc-open-detail" style="flex:1;">Full Edit</button>
                    <button class="btn btn-secondary btn-sm acct-btn-del" data-id="${t.id}" style="color:var(--red);">Delete</button>
                </div>
            </div>
        </div>`;
    }).join('')}</div>`;

    el.innerHTML = tableHTML + cardsHTML;

    // ── Mobile card: pre-select current values + apply suggestions ──
    el.querySelectorAll('.acct-mobile-cards .acct-mobile-card').forEach(card => {
        const txnId = card.dataset.id;
        const t = txns.find(x => String(x.id) === txnId);
        if (!t) return;
        const split0 = t.splits[0] || {};
        if (t._is_expense) {
            const entSel = card.querySelector('.mc-exp-entity');
            const catSel = card.querySelector('.mc-exp-category');

            // First try current values from split data
            let entMatch = split0.entity_name || '';
            let catMatch = split0.category_name || '';

            // If empty, use suggestion data
            const sugCat = card.dataset.sugCat;
            const sugEnt = card.dataset.sugEnt;
            if (!catMatch && sugCat) catMatch = sugCat;
            if ((!entMatch || entMatch === '?') && sugEnt) entMatch = sugEnt;

            // Apply to selects
            if (entSel && entMatch && entMatch !== '?') {
                for (const opt of entSel.options) {
                    if (opt.value && opt.value.toUpperCase() === entMatch.toUpperCase()) {
                        opt.selected = true; break;
                    }
                }
                if (sugEnt && entSel.value) {
                    entSel.style.borderColor = '#7dd3fc';
                }
            }
            if (catSel && catMatch) {
                for (const opt of catSel.options) {
                    if (opt.value && opt.value.toUpperCase() === catMatch.toUpperCase()) {
                        opt.selected = true; break;
                    }
                }
                if (sugCat && catSel.value) {
                    catSel.style.borderColor = '#7dd3fc';
                }
            }
            // Pre-select account
            const acctSel = card.querySelector('.mc-exp-account');
            const acctName = t.account_name || '';
            if (acctSel && acctName) {
                for (const opt of acctSel.options) {
                    if (opt.value && opt.value.toUpperCase() === acctName.toUpperCase()) {
                        opt.selected = true; break;
                    }
                }
            }
        } else {
            // Pre-select regular txn dropdowns
            const entSel = card.querySelector('.mc-entity');
            const acctSel = card.querySelector('.mc-account');
            if (entSel && split0.entity_id) entSel.value = split0.entity_id;
            if (acctSel && t.account_id) acctSel.value = t.account_id;
        }
    });

    // ── Mobile card: expand/collapse ──
    el.querySelectorAll('.acct-mobile-card-top').forEach(top => {
        top.addEventListener('click', () => {
            top.closest('.acct-mobile-card').classList.toggle('expanded');
        });
    });

    // ── Mobile card: "Full Edit" / "Edit" button opens modal ──
    el.querySelectorAll('.acct-mobile-cards .mc-open-detail').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const card = btn.closest('.acct-mobile-card');
            const expId = card.dataset.expenseId;
            if (expId) {
                openExpenseReview(parseInt(expId));
            } else {
                openEditTransaction(parseInt(card.dataset.id));
            }
        });
    });

    // ── Mobile card: inline save for REGULAR transactions ──
    el.querySelectorAll('.acct-mobile-cards .mc-entity, .acct-mobile-cards .mc-category, .acct-mobile-cards .mc-account').forEach(sel => {
        sel.addEventListener('change', async (e) => {
            e.stopPropagation();
            const card = sel.closest('.acct-mobile-card');
            const txnId = card.dataset.id;
            const entVal = card.querySelector('.mc-entity').value;
            const catVal = card.querySelector('.mc-category').value;
            const acctVal = card.querySelector('.mc-account').value;
            try {
                const txn = await api('/transactions/' + txnId);
                const body = {
                    splits: txn.splits.map(s => ({
                        entity_id: entVal ? parseInt(entVal) : s.entity_id,
                        category_id: catVal ? parseInt(catVal) : s.category_id,
                        amount: s.amount,
                        memo: s.memo,
                    })),
                };
                if (acctVal) body.account_id = parseInt(acctVal);
                await api('/transactions/' + txnId, { method: 'PUT', body });
                sel.style.borderColor = 'var(--green)';
                sel.style.boxShadow = '0 0 0 1px var(--green)';
                setTimeout(() => { sel.style.borderColor = ''; sel.style.boxShadow = ''; }, 2000);
            } catch (err) {
                alert('Save error: ' + err.message);
            }
        });
    });

    // ── Mobile card: inline save for EXPENSE transactions ──
    el.querySelectorAll('.acct-mobile-cards .mc-exp-entity, .acct-mobile-cards .mc-exp-category, .acct-mobile-cards .mc-exp-account').forEach(sel => {
        sel.addEventListener('change', async (e) => {
            e.stopPropagation();
            const card = sel.closest('.acct-mobile-card');
            const expId = card.dataset.expenseId;

            // Handle "+ New Account"
            const acctSel = card.querySelector('.mc-exp-account');
            if (acctSel && acctSel.value === '__new__') {
                const newName = prompt('New account name:');
                if (!newName || !newName.trim()) { acctSel.value = ''; return; }
                try {
                    const created = await api('/accounts', { method: 'POST', body: { name: newName.trim(), account_type: 'checking', opening_balance: 0 } });
                    ACCT.accounts.push({ id: created.id, name: newName.trim() });
                    const opt = document.createElement('option');
                    opt.value = newName.trim();
                    opt.textContent = newName.trim();
                    // Insert before the "+ New" option
                    acctSel.insertBefore(opt, acctSel.querySelector('option[value="__new__"]'));
                    acctSel.value = newName.trim();
                } catch (err) {
                    alert('Error creating account: ' + err.message);
                    acctSel.value = '';
                    return;
                }
            }

            const entity = card.querySelector('.mc-exp-entity').value || null;
            const category = card.querySelector('.mc-exp-category').value || null;
            const account_name = acctSel ? acctSel.value || null : null;
            try {
                const body = { entity, category, reviewed_at: new Date().toISOString(), reviewed_by: 'admin' };
                if (account_name && account_name !== '__new__') body.account_name = account_name;
                await api('/expense-transactions/' + expId, { method: 'PATCH', body });
                sel.style.borderColor = 'var(--green)';
                sel.style.boxShadow = '0 0 0 1px var(--green)';
                setTimeout(() => { sel.style.borderColor = ''; sel.style.boxShadow = ''; }, 2000);
            } catch (err) {
                alert('Save error: ' + err.message);
            }
        });
    });

    // ── Mobile card: Approve / Ignore expense ──
    el.querySelectorAll('.acct-mobile-cards .mc-exp-approve').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const card = btn.closest('.acct-mobile-card');
            const expId = card.dataset.expenseId;
            const entity = card.querySelector('.mc-exp-entity').value || null;
            const category = card.querySelector('.mc-exp-category').value || null;
            const acctSel = card.querySelector('.mc-exp-account');
            const account_name = acctSel ? acctSel.value || null : null;
            try {
                const body = { entity, category, review_status: 'approved', reviewed_at: new Date().toISOString(), reviewed_by: 'admin' };
                if (account_name && account_name !== '__new__') body.account_name = account_name;
                await api('/expense-transactions/' + expId, { method: 'PATCH', body });
                card.style.opacity = '0.5';
                btn.textContent = 'Approved';
                btn.disabled = true;
            } catch (err) {
                alert('Error: ' + err.message);
            }
        });
    });
    el.querySelectorAll('.acct-mobile-cards .mc-exp-ignore').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const card = btn.closest('.acct-mobile-card');
            const expId = card.dataset.expenseId;
            try {
                await api('/expense-transactions/' + expId, {
                    method: 'PATCH',
                    body: { review_status: 'ignored', reviewed_at: new Date().toISOString(), reviewed_by: 'admin' }
                });
                card.classList.add('acct-mc-ignored');
                btn.textContent = 'Ignored';
                btn.disabled = true;
            } catch (err) {
                alert('Error: ' + err.message);
            }
        });
    });

    // ── Mobile card: tag toggle ──
    el.querySelectorAll('.acct-mobile-cards .acct-mc-tags .acct-tag-selectable').forEach(chip => {
        chip.addEventListener('click', async (e) => {
            e.stopPropagation();
            const card = chip.closest('.acct-mobile-card');
            const txnId = card.dataset.id;
            const tagId = parseInt(chip.dataset.tagId);
            const isSel = chip.classList.contains('selected');
            try {
                const txn = await api('/transactions/' + txnId);
                let tagIds = txn.tags.map(tg => tg.id);
                if (isSel) {
                    tagIds = tagIds.filter(id => id !== tagId);
                } else {
                    tagIds.push(tagId);
                }
                await api('/transactions/' + txnId, { method: 'PUT', body: { tag_ids: tagIds } });
                // Toggle chip visual
                const tagObj = ACCT.tags.find(t => t.id === tagId);
                if (isSel) {
                    chip.classList.remove('selected');
                    chip.style.background = 'transparent';
                    chip.style.color = tagObj ? tagObj.color : '';
                } else {
                    chip.classList.add('selected');
                    chip.style.background = tagObj ? tagObj.color : '';
                    chip.style.color = '#fff';
                }
            } catch (err) {
                alert('Tag error: ' + err.message);
            }
        });
    });

    // Click row to edit (desktop — or review for expense transactions)
    el.querySelectorAll('.acct-txn-row').forEach(row => {
        row.addEventListener('click', (e) => {
            if (e.target.closest('.acct-btn-del')) return;
            const expId = row.dataset.expenseId;
            if (expId) {
                openExpenseReview(parseInt(expId));
            } else {
                openEditTransaction(parseInt(row.dataset.id));
            }
        });
    });

    // Delete buttons (both desktop and mobile)
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
            entity_id: s.entity_id, category_id: s.category_id || '', event_id: s.event_id || '', amount: s.amount, memo: s.memo || ''
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
    const eventOpts = '<option value="">No Event</option>' + ACCT.events.map(ev =>
        `<option value="${ev.id}" ${ev.id == s.event_id ? 'selected' : ''}>${ev.item_name}${ev.event_date ? ' (' + ev.event_date + ')' : ''}</option>`
    ).join('');
    return `<div class="acct-split-row" data-idx="${idx}">
        <select class="split-entity acct-select-sm">${entityOpts}</select>
        <select class="split-category acct-select-sm">${catOpts}</select>
        <select class="split-event acct-select-sm" title="Link to event">${eventOpts}</select>
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
        const eventSel = row.querySelector('.split-event');
        splits.push({
            entity_id: parseInt(row.querySelector('.split-entity').value),
            category_id: row.querySelector('.split-category').value ? parseInt(row.querySelector('.split-category').value) : null,
            event_id: eventSel && eventSel.value ? parseInt(eventSel.value) : null,
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

// ── Expense Review Modal ────────────────────────────────

async function openExpenseReview(expenseId) {
    try {
        const exp = await api('/expense-transactions/' + expenseId);
        $('#expense-review-id').value = exp.id;

        // Read-only fields
        const srcLabel = _SOURCE_LABELS[exp.source_type] || exp.source_type || '—';
        $('#expense-source').innerHTML = `<span class="acct-source-badge acct-source-${exp.source_type || ''}">${srcLabel}</span>`;
        $('#expense-date').textContent = exp.transaction_date || '—';
        $('#expense-confidence').textContent = exp.confidence != null ? exp.confidence + '%' : '—';
        $('#expense-merchant').textContent = exp.merchant || '(unknown)';
        $('#expense-amount').textContent = fmt(exp.amount);
        $('#expense-account').textContent = exp.account_name || (exp.account_last4 ? '...' + exp.account_last4 : '—');
        $('#expense-status').textContent = (exp.review_status || 'pending').toUpperCase();

        // Editable: Entity dropdown (text-based, match to acct_entities)
        const entOpts = '<option value="">— None —</option>' +
            ACCT.entities.map(e => `<option value="${e.short_name}" ${
                (exp.entity || '').toUpperCase() === e.short_name.toUpperCase() ? 'selected' : ''
            }>${e.short_name}</option>`).join('');
        $('#expense-entity').innerHTML = entOpts;

        // Editable: Category dropdown (text-based)
        const catOpts = '<option value="">— None —</option>' +
            ACCT.categories.filter(c => c.type === 'expense').map(c => `<option value="${c.name}" ${
                (exp.category || '').toUpperCase() === c.name.toUpperCase() ? 'selected' : ''
            }>${c.name}</option>`).join('');
        $('#expense-category').innerHTML = catOpts;

        // Editable: Event dropdown
        const evOpts = '<option value="">No Event</option>' +
            ACCT.events.map(ev => `<option value="${ev.item_name}" ${
                exp.event_name === ev.item_name ? 'selected' : ''
            }>${ev.item_name}${ev.event_date ? ' (' + ev.event_date + ')' : ''}</option>`).join('');
        $('#expense-event').innerHTML = evOpts;

        // Notes
        $('#expense-notes').value = exp.notes || '';

        $('#expense-review-modal').style.display = 'flex';
    } catch (e) {
        alert('Error loading expense: ' + e.message);
    }
}

async function saveExpenseReview(action) {
    const expId = $('#expense-review-id').value;
    if (!expId) return;

    const fields = {
        entity: $('#expense-entity').value || null,
        category: $('#expense-category').value || null,
        event_name: $('#expense-event').value || null,
        notes: $('#expense-notes').value.trim() || null,
        reviewed_at: new Date().toISOString(),
        reviewed_by: 'admin',
    };

    if (action === 'approve') {
        // If any field was changed from original, mark as corrected
        fields.review_status = 'approved';
    } else if (action === 'ignore') {
        fields.review_status = 'ignored';
    }

    try {
        await api('/expense-transactions/' + expId, { method: 'PATCH', body: fields });
        closeExpenseModal();
        refreshActiveTab();
    } catch (e) {
        alert('Error saving: ' + e.message);
    }
}

function closeExpenseModal() {
    $('#expense-review-modal').style.display = 'none';
}
