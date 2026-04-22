/* =========================================================
   Accounting Module — Transactions Tab & Modal
   ========================================================= */

// ── Ledger Column Visibility ──────────────────────────────

const LEDGER_COLS = [
    { key: 'customer', label: 'Customer / Vendor', def: true },
    { key: 'splits',   label: 'Category',          def: true },
    { key: 'type',     label: 'Type',               def: true },
    { key: 'account',  label: 'Account',            def: true },
];
let _ledgerColPrefs = null;

function _loadLedgerColPrefs() {
    if (_ledgerColPrefs) return;
    try {
        const s = localStorage.getItem('acct_visible_cols');
        if (s) { _ledgerColPrefs = JSON.parse(s); return; }
    } catch(e) {}
    _ledgerColPrefs = {};
    LEDGER_COLS.forEach(c => { _ledgerColPrefs[c.key] = c.def; });
}

function _saveLedgerColPrefs() {
    try { localStorage.setItem('acct_visible_cols', JSON.stringify(_ledgerColPrefs)); } catch(e) {}
}

function applyLedgerColVisibility() {
    _loadLedgerColPrefs();
    const table = document.querySelector('#txn-list .acct-table-full');
    if (!table) return;
    LEDGER_COLS.forEach(c => table.classList.toggle(`acct-hide-${c.key}`, !_ledgerColPrefs[c.key]));
}

function buildLedgerColumnToggle() {
    _loadLedgerColPrefs();
    const drop = $('#ledger-col-dropdown');
    if (!drop) return;
    drop.innerHTML = LEDGER_COLS.map(c => `
        <label style="display:flex;align-items:center;gap:6px;padding:5px 12px;cursor:pointer;font-size:0.82rem;white-space:nowrap;">
            <input type="checkbox" data-col="${c.key}" ${_ledgerColPrefs[c.key] ? 'checked' : ''}> ${c.label}
        </label>`).join('');
    drop.querySelectorAll('input[type=checkbox]').forEach(cb => {
        cb.addEventListener('change', () => {
            _ledgerColPrefs[cb.dataset.col] = cb.checked;
            _saveLedgerColPrefs();
            applyLedgerColVisibility();
        });
    });
}

// ── Inline Match Queue state ──
const LMQ = {
    selectedDepositId: null,
    selectedDepositAmount: 0,
    selectedDepositAccountName: '',
    selectedTxnId: null,
    selectedTxnAmount: 0,
    deposits: [],
};

async function loadTransactions() {
    const acctPill = document.querySelector('#ledger-acct-pills .ledger-pill.active');
    const statusPill = document.querySelector('#ledger-status-pills .ledger-seg-btn.active');
    const acctId = acctPill?.dataset.acctId || null;
    const ledgerStatus = statusPill?.dataset.status || 'all';

    const params = {
        entity_id: ACCT.activeEntity,
        account_id: acctId,
        category_id: $('#txn-filter-category')?.value || null,
        type: $('#txn-filter-type')?.value || null,
        source: $('#txn-filter-source')?.value || null,
        search: $('#txn-search')?.value || null,
        limit: ACCT.txnLimit,
        offset: ACCT.txnPage * ACCT.txnLimit,
    };

    if (ledgerStatus === 'pending') {
        params.review_status = 'pending';
    } else if (ledgerStatus !== 'all') {
        params.ledger_status = ledgerStatus;
        // advanced review filter still respected when not using status pill shortcut
    } else {
        params.review_status = $('#txn-filter-review')?.value || null;
    }

    applyLedgerSplitMode(ledgerStatus === 'unreconciled');

    try {
        const data = await api('/transactions/unified' + buildQS(params));
        renderTransactionList(data.transactions, data.total);
        if (ledgerStatus === 'unreconciled') {
            // After list renders, re-apply highlighting if a deposit was selected
            if (LMQ.selectedDepositId) highlightAmountMatches(LMQ.selectedDepositAmount);
        }
    } catch (e) {
        console.error('Transaction load error:', e);
    }
}

// ── Inline Match Queue ───────────────────────────────────

function applyLedgerSplitMode(isOn) {
    const split = document.getElementById('ledger-split');
    if (!split) return;
    split.classList.toggle('split-on', isOn);
    if (isOn) {
        loadUnmatchedDeposits();
    } else {
        // Reset selection state when leaving unreconciled view
        LMQ.selectedDepositId = null;
        LMQ.selectedTxnId = null;
        updateMatchButtonState();
    }
}

async function loadUnmatchedDeposits() {
    const pane = document.getElementById('lmq-deposit-list');
    if (!pane) return;
    const acctPill = document.querySelector('#ledger-acct-pills .ledger-pill.active');
    const acctId = acctPill?.dataset.acctId || '';
    const acctName = (acctPill?.textContent || '').trim();
    pane.innerHTML = '<div class="lmq-empty">Loading deposits…</div>';
    try {
        const qs = new URLSearchParams({ status: 'unmatched' });
        const res = await fetch('/api/reconciliation/deposits?' + qs.toString());
        let deposits = await res.json();
        if (!Array.isArray(deposits)) deposits = [];
        // Client-side filter: match by account_name if a specific pill is active
        if (acctId && acctName && acctName !== 'All Accounts') {
            const filtered = deposits.filter(d => {
                const dn = (d.account_name || '').toLowerCase();
                const an = acctName.toLowerCase();
                // match either exact name or substring (e.g. "TGF Checking ••4500")
                return dn === an || an.includes(dn) || dn.includes(an.split(' ')[0] || an);
            });
            // Only apply the filter if it actually narrows the list — otherwise keep all
            if (filtered.length) deposits = filtered;
        }
        LMQ.deposits = deposits;
        renderDepositList(deposits);
    } catch (e) {
        pane.innerHTML = `<div class="lmq-empty" style="color:#dc2626;">Failed to load: ${e.message || e}</div>`;
    }
}

function renderDepositList(deposits) {
    const pane = document.getElementById('lmq-deposit-list');
    const countEl = document.getElementById('lmq-count');
    if (!pane) return;
    if (countEl) countEl.textContent = deposits.length ? `${deposits.length} unmatched` : '';
    if (!deposits.length) {
        pane.innerHTML = '<div class="lmq-empty">No unmatched deposits 🎉</div>';
        return;
    }
    pane.innerHTML = deposits.map(d => {
        const amt = d.amount || 0;
        const amtStr = amt >= 0 ? '$' + amt.toFixed(2) : '-$' + Math.abs(amt).toFixed(2);
        const sel = LMQ.selectedDepositId === d.id ? ' selected' : '';
        const status = d.status || 'unmatched';
        const desc = (d.description || '').replace(/</g, '&lt;');
        const acctTag = d.account_name ? ` <span style="font-size:.65rem;color:#6b7280;">${d.account_name}</span>` : '';
        return `<div class="lmq-deposit ${status}${sel}" data-id="${d.id}" data-amount="${amt}" data-acct-name="${d.account_name || ''}">
            <span class="lmq-date">${d.deposit_date || ''}</span>
            <span class="lmq-desc"><span class="lmq-dot"></span>${desc}${acctTag}</span>
            <span class="lmq-amt">${amtStr}</span>
        </div>`;
    }).join('');
    pane.querySelectorAll('.lmq-deposit').forEach(el => {
        el.addEventListener('click', () => selectDepositInline(parseInt(el.dataset.id)));
    });
}

function selectDepositInline(id) {
    const dep = LMQ.deposits.find(d => d.id === id);
    if (!dep) return;
    // Toggle off if clicking same deposit
    if (LMQ.selectedDepositId === id) {
        LMQ.selectedDepositId = null;
        LMQ.selectedDepositAmount = 0;
        LMQ.selectedDepositAccountName = '';
        clearAmountHighlights();
    } else {
        LMQ.selectedDepositId = id;
        LMQ.selectedDepositAmount = dep.amount || 0;
        LMQ.selectedDepositAccountName = dep.account_name || '';
        highlightAmountMatches(LMQ.selectedDepositAmount);
    }
    // Update visual selection
    document.querySelectorAll('#lmq-deposit-list .lmq-deposit').forEach(el => {
        el.classList.toggle('selected', parseInt(el.dataset.id) === LMQ.selectedDepositId);
    });
    updateMatchButtonState();
}

function highlightAmountMatches(targetAmount) {
    clearAmountHighlights();
    if (!targetAmount) return;
    const tol = 1.00; // within $1
    // Desktop table rows
    document.querySelectorAll('#txn-list .acct-txn-row').forEach(row => {
        // 4th td (text-right) holds the displayed amount
        const amtCell = row.querySelector('td:nth-child(4)');
        const num = amtCell ? parseFloat((amtCell.textContent || '').replace(/[^0-9.\-]/g, '')) : NaN;
        if (!isNaN(num) && Math.abs(num - targetAmount) <= tol) {
            row.classList.add('lmq-candidate');
        }
    });
    // Mobile cards
    document.querySelectorAll('#txn-list .acct-mobile-card').forEach(card => {
        const amtEl = card.querySelector('.acct-mc-amount');
        const num = amtEl ? parseFloat((amtEl.textContent || '').replace(/[^0-9.\-]/g, '')) : NaN;
        if (!isNaN(num) && Math.abs(num - targetAmount) <= tol) {
            card.classList.add('lmq-candidate');
        }
    });
}

function clearAmountHighlights() {
    document.querySelectorAll('#txn-list .lmq-candidate').forEach(el => el.classList.remove('lmq-candidate'));
}

function setSelectedLedgerTxn(id, amount) {
    LMQ.selectedTxnId = id;
    LMQ.selectedTxnAmount = amount || 0;
    document.querySelectorAll('#txn-list .acct-txn-row, #txn-list .acct-mobile-card').forEach(el => {
        el.classList.toggle('lmq-selected', parseInt(el.dataset.id) === id);
    });
    updateMatchButtonState();
}

function updateMatchButtonState() {
    const btn = document.getElementById('btn-lmq-match');
    if (!btn) return;
    const can = !!(LMQ.selectedDepositId && LMQ.selectedTxnId);
    btn.disabled = !can;
    if (can) {
        btn.textContent = `Match $${LMQ.selectedTxnAmount.toFixed(2)}`;
    } else if (LMQ.selectedDepositId) {
        btn.textContent = 'Pick a ledger entry';
    } else {
        btn.textContent = 'Match';
    }
}

async function matchSelectedInline() {
    if (!LMQ.selectedDepositId || !LMQ.selectedTxnId) return;
    const depId = LMQ.selectedDepositId;
    const txnId = LMQ.selectedTxnId;
    try {
        const res = await fetch('/api/reconciliation/match', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bank_deposit_id: depId, acct_transaction_id: txnId }),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.error || res.statusText);
        }
        // Fade matched row and remove deposit card
        const row = document.querySelector(`#txn-list [data-id="${txnId}"]`);
        if (row) {
            row.classList.add('lmq-matched');
            setTimeout(() => row.remove(), 400);
        }
        LMQ.deposits = LMQ.deposits.filter(d => d.id !== depId);
        LMQ.selectedDepositId = null;
        LMQ.selectedTxnId = null;
        renderDepositList(LMQ.deposits);
        clearAmountHighlights();
        updateMatchButtonState();
    } catch (e) {
        alert('Match failed: ' + (e.message || e));
    }
}

async function runInlineAutoMatch() {
    const btn = document.getElementById('btn-lmq-automatch');
    if (btn) { btn.disabled = true; btn.textContent = 'Matching…'; }
    try {
        const res = await fetch('/api/reconciliation/auto-match', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
        });
        const data = await res.json();
        const msg = `Auto-matched: ${data.auto_matched || 0} | Partial: ${data.partial || 0} | Unmatched: ${data.unmatched || 0}`;
        if (btn) btn.textContent = 'Auto-Match All';
        // Flash the message briefly
        const countEl = document.getElementById('lmq-count');
        if (countEl) {
            const prev = countEl.textContent;
            countEl.textContent = msg;
            setTimeout(() => { if (countEl.textContent === msg) countEl.textContent = prev; }, 3500);
        }
        loadTransactions();
    } catch (e) {
        alert('Auto-match failed: ' + (e.message || e));
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = 'Auto-Match All'; }
    }
}

function initLedgerPills() {
    const acctBar = document.getElementById('ledger-acct-pills');
    if (acctBar && ACCT.accounts.length) {
        const active = acctBar.querySelector('.ledger-pill.active')?.dataset.acctId || '';
        acctBar.innerHTML =
            `<button class="ledger-pill${active === '' ? ' active' : ''}" data-acct-id="">All Accounts</button>` +
            ACCT.accounts.map(a =>
                `<button class="ledger-pill${active === String(a.id) ? ' active' : ''}" data-acct-id="${a.id}">${acctDisplayName(a)}</button>`
            ).join('');
        acctBar.querySelectorAll('.ledger-pill').forEach(btn => {
            btn.addEventListener('click', () => {
                acctBar.querySelectorAll('.ledger-pill').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                ACCT.txnPage = 0;
                loadTransactions();
            });
        });
    }

    const statusBar = document.getElementById('ledger-status-pills');
    if (statusBar) {
        statusBar.querySelectorAll('.ledger-seg-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                statusBar.querySelectorAll('.ledger-seg-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                ACCT.txnPage = 0;
                loadTransactions();
            });
        });
    }

    document.getElementById('btn-ledger-adv')?.addEventListener('click', () => {
        const panel = document.getElementById('ledger-adv-panel');
        if (panel) panel.style.display = panel.style.display === 'none' ? '' : 'none';
    });
}

const _SOURCE_LABELS = {
    chase_alert: 'Chase Alert',
    venmo: 'Venmo',
    receipt: 'Receipt',
};

function _ledgerDot(t) {
    const GREY  = '<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#d1d5db;margin-right:5px;vertical-align:middle;flex-shrink:0;"></span>';
    const GREEN = '<span title="Reconciled" style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#16a34a;margin-right:5px;vertical-align:middle;flex-shrink:0;"></span>';
    const AMBER = '<span title="Awaiting bank match" style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#fbbf24;margin-right:5px;vertical-align:middle;flex-shrink:0;"></span>';
    if (t._is_expense) return GREY;
    if (t.status === 'reconciled') return GREEN;
    if (t.status === 'reversed' || t.status === 'merged') return GREY;
    if (t.type === 'income' || t.type === 'contra') return AMBER;
    return GREY;
}

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
        const tagBadges = (t.tags || []).map(tg => `<span class="acct-tag-chip" style="background:${tg.color}">${tg.name}</span>`).join('');
        return { isExp, splitBadges, sourceBadge, reviewBadge, tagBadges };
    }

    // Desktop table
    const tableHTML = `<table class="acct-table acct-table-full acct-table-mobile-hide">
        <thead><tr>
            <th>Date</th>
            <th class="col-customer">Customer / Vendor</th>
            <th>Description</th>
            <th class="col-splits">Category</th>
            <th class="text-right">Amount</th>
            <th class="col-type">Type</th>
            <th class="col-account">Account</th>
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
            const custName = t.customer_name || '';

            return `<tr class="${rowClass}" ${rowData}>
                <td style="white-space:nowrap;">${_ledgerDot(t)}${t.date || ''}</td>
                <td class="col-customer" style="max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:0.8rem;color:#6b7280;" title="${custName}">${custName}</td>
                <td>
                    ${t.description || ''}
                    ${m.sourceBadge}${m.reviewBadge}${m.tagBadges}
                </td>
                <td class="col-splits acct-split-cell">${m.splitBadges}</td>
                <td class="text-right ${t.type === 'income' ? 'acct-positive' : 'acct-negative'}">${fmt(t.total_amount)}</td>
                <td class="col-type"><span class="acct-type-badge acct-type-${t.type}">${t.type}</span></td>
                <td class="col-account">${t.account_name || '—'}</td>
                <td>
                    ${m.isExp ? '' : `<button class="btn-icon-sm acct-btn-del" data-id="${t.id}" title="Delete">&times;</button>`}
                </td>
            </tr>`;
        }).join('')}</tbody></table>`;

    // Mobile cards — build option strings once
    const _acctOpts = '<option value="">— Account —</option>' +
        ACCT.accounts.map(a => `<option value="${a.id}">${acctDisplayName(a)}</option>`).join('');
    const _entOpts = ACCT.entities.map(e =>
        `<option value="${e.id}">${e.short_name}</option>`).join('');
    const _expEntOpts = '<option value="">— Entity —</option>' +
        ACCT.entities.map(e => `<option value="${e.short_name}">${e.short_name}</option>`).join('');
    const _expCatOpts = '<option value="">— Category —</option>' +
        ACCT.categories.filter(c => c.type === 'expense').map(c =>
            `<option value="${c.name}">${c.name}</option>`).join('');

    const _expAcctOpts = '<option value="">— Account —</option>' +
        ACCT.accounts.map(a => `<option value="${a.name}">${acctDisplayName(a)}</option>`).join('') +
        '<option value="__new__">+ New Account</option>';
    const _expEventOpts = '<option value="">— Event —</option>' +
        ACCT.events.map(ev => `<option value="${ev.item_name}">${ev.item_name}${ev.event_date ? ' (' + ev.event_date + ')' : ''}</option>`).join('');

    // Guess event from description (for Zelle/Venmo memos)
    function _guessEvent(description) {
        if (!description || !ACCT.events.length) return null;
        const desc = description.toLowerCase();
        for (const ev of ACCT.events) {
            const name = (ev.item_name || '').toLowerCase();
            // Match course name keywords (2+ word fragments)
            const words = name.split(/[\s\-–—]+/).filter(w => w.length > 2);
            for (const w of words) {
                if (desc.includes(w)) return ev.item_name;
            }
        }
        return null;
    }

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
                        <select class="mc-exp-event" data-expense-id="${t.expense_id}">${_expEventOpts}</select>
                    </div>
                    ${m.splitBadges ? `<div class="acct-mc-splits">${m.splitBadges}</div>` : ''}
                    <div class="acct-mc-btn-row">
                        <button class="btn btn-sm mc-exp-approve" data-expense-id="${t.expense_id}" style="background:var(--green);color:#fff;border:none;flex:1;">${sug ? 'Approve' : 'Approve'}</button>
                        <button class="btn btn-secondary btn-sm mc-exp-ignore" data-expense-id="${t.expense_id}" style="flex:1;">Skip</button>
                        <button class="btn btn-secondary btn-sm mc-open-detail" style="flex:0 0 auto;">Edit</button>
                    </div>
                </div>
            </div>`;
        }

        // ── Regular transaction: entity + category + account + tags
        return `<div class="${cardClass}" ${cardData}>
            <div class="acct-mobile-card-top">
                <div class="acct-mc-left">
                    <div class="acct-mc-date">${_ledgerDot(t)}${t.date || ''} ${m.sourceBadge}</div>
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
            // Pre-select event (from data or guess from description)
            const evSel = card.querySelector('.mc-exp-event');
            const evName = split0.event_name || _guessEvent(t.description);
            if (evSel && evName) {
                for (const opt of evSel.options) {
                    if (opt.value === evName) {
                        opt.selected = true; break;
                    }
                }
                if (!split0.event_name && evSel.value) {
                    evSel.style.borderColor = '#7dd3fc';
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
    el.querySelectorAll('.acct-mobile-cards .mc-exp-entity, .acct-mobile-cards .mc-exp-category, .acct-mobile-cards .mc-exp-account, .acct-mobile-cards .mc-exp-event').forEach(sel => {
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
            const evSel = card.querySelector('.mc-exp-event');
            const event_name = evSel ? evSel.value || null : null;
            try {
                const body = { entity, category, reviewed_at: new Date().toISOString(), reviewed_by: 'admin' };
                if (account_name && account_name !== '__new__') body.account_name = account_name;
                if (event_name) body.event_name = event_name;
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
            const evSel = card.querySelector('.mc-exp-event');
            const event_name = evSel ? evSel.value || null : null;
            try {
                const body = { entity, category, review_status: 'approved', reviewed_at: new Date().toISOString(), reviewed_by: 'admin' };
                if (account_name && account_name !== '__new__') body.account_name = account_name;
                if (event_name) body.event_name = event_name;
                await api('/expense-transactions/' + expId, { method: 'PATCH', body });
                card.style.transition = 'opacity 0.3s, max-height 0.4s, margin 0.4s, padding 0.4s';
                card.style.opacity = '0';
                card.style.maxHeight = card.offsetHeight + 'px';
                requestAnimationFrame(() => {
                    card.style.maxHeight = '0';
                    card.style.marginBottom = '0';
                    card.style.overflow = 'hidden';
                });
                setTimeout(() => card.remove(), 450);
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
                card.style.transition = 'opacity 0.3s, max-height 0.4s, margin 0.4s, padding 0.4s';
                card.style.opacity = '0';
                card.style.maxHeight = card.offsetHeight + 'px';
                requestAnimationFrame(() => {
                    card.style.maxHeight = '0';
                    card.style.marginBottom = '0';
                    card.style.overflow = 'hidden';
                });
                setTimeout(() => card.remove(), 450);
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

    // Click row to edit (desktop — or review for expense transactions).
    // When the inline Match Queue is active, a click selects the row as a match candidate instead.
    el.querySelectorAll('.acct-txn-row').forEach(row => {
        row.addEventListener('click', (e) => {
            if (e.target.closest('.acct-btn-del')) return;
            const splitOn = document.getElementById('ledger-split')?.classList.contains('split-on');
            if (splitOn) {
                const amtCell = row.querySelector('td:nth-child(4)');
                const amt = amtCell ? parseFloat((amtCell.textContent || '').replace(/[^0-9.\-]/g, '')) : 0;
                setSelectedLedgerTxn(parseInt(row.dataset.id), isNaN(amt) ? 0 : amt);
                return;
            }
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

    // Apply column visibility after render
    applyLedgerColVisibility();

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

function _guessAccountId(txn) {
    const source = (txn.source || '').toLowerCase();
    const desc = (txn.description || '').toLowerCase();
    if (source === 'godaddy' || desc.startsWith('godaddy order')) {
        return ACCT.accounts.find(a => a.name.toLowerCase().includes('tgf checking'))?.id || null;
    }
    if (source === 'venmo') {
        return ACCT.accounts.find(a => a.account_type === 'venmo' || a.name.toLowerCase().includes('venmo'))?.id || null;
    }
    return null;
}

function _buildSmartSplit(txn) {
    // Entity: prefer TGF for income, else active/first
    const tgfEnt = ACCT.entities.find(e => e.short_name === 'TGF');
    const entityId = (txn.type === 'income' && tgfEnt) ? tgfEnt.id
        : (ACCT.activeEntity || ACCT.entities[0]?.id);

    // Category: income → "Event Revenue"
    const catId = txn.type === 'income'
        ? (ACCT.categories.find(c => c.type === 'income' && c.name.toLowerCase().includes('event revenue'))?.id || '')
        : '';

    // Event: match event_name field directly against ACCT.events
    const evId = txn.event_name
        ? (ACCT.events.find(e => e.item_name === txn.event_name)?.id || '')
        : '';

    return { entity_id: entityId, category_id: catId, event_id: evId, amount: txn.total_amount, memo: '' };
}

function populateDropdowns() {
    // Account dropdowns (with last 4 digits)
    const acctOpts = '<option value="">— None —</option>' +
        ACCT.accounts.map(a => `<option value="${a.id}">${acctDisplayName(a)}</option>`).join('');
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
            ACCT.accounts.map(a => `<option value="${a.id}">${acctDisplayName(a)}</option>`).join('');
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
    clearTxnCustomer();

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
        // Auto-assign account if not set
        if (!txn.account_id) {
            const guessedAcct = _guessAccountId(txn);
            if (guessedAcct) $('#txn-account').value = guessedAcct;
        }
        $('#txn-notes').value = txn.notes || '';
        $('#receipt-filename').textContent = txn.receipt_path ? txn.receipt_path.split('/').pop() : '';
        $('#transfer-row').style.display = txn.type === 'transfer' ? '' : 'none';
        if (txn.transfer_to_account_id) $('#txn-transfer-to').value = txn.transfer_to_account_id;

        if (txn.customer_id && txn.customer_name) {
            const cust = ACCT.customers.find(c => c.customer_id === txn.customer_id);
            setTxnCustomer(txn.customer_id, txn.customer_name, cust?.is_vendor);
        } else {
            clearTxnCustomer();
        }

        const splitsData = txn.splits.length > 0
            ? txn.splits.map(s => ({ entity_id: s.entity_id, category_id: s.category_id || '', event_id: s.event_id || '', amount: s.amount, memo: s.memo || '' }))
            : [_buildSmartSplit(txn)];
        renderSplitRows(splitsData);
        renderTagChips(txn.tags.map(t => t.id));

        $('#txn-modal').style.display = 'flex';
    } catch (e) {
        alert('Error loading transaction: ' + e.message);
    }
}

async function saveTransaction() {
    const editId = $('#txn-edit-id').value;
    const custId = $('#txn-customer-id').value ? parseInt($('#txn-customer-id').value) : null;
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
        customer_id: custId,
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

// Store original account for warning logic
let _expOriginalAccount = null;

async function openExpenseReview(expenseId) {
    try {
        const exp = await api('/expense-transactions/' + expenseId);
        $('#expense-review-id').value = exp.id;
        $('#expense-source-type').value = exp.source_type || '';

        // Title
        const status = (exp.review_status || 'pending');
        $('#expense-modal-title').textContent = status === 'pending' ? 'Review Transaction' : 'Edit Transaction';

        // Source info bar
        const srcLabel = _SOURCE_LABELS[exp.source_type] || exp.source_type || '';
        if (srcLabel) {
            $('#expense-source-row').style.display = '';
            $('#expense-source').innerHTML = `<span class="acct-source-badge acct-source-${exp.source_type || ''}">${srcLabel}</span>`;
            $('#expense-confidence').textContent = exp.confidence != null ? exp.confidence + '%' : '—';
            $('#expense-status').textContent = status.toUpperCase();
        } else {
            $('#expense-source-row').style.display = 'none';
        }

        // Editable core fields
        $('#expense-date-input').value = exp.transaction_date || '';
        $('#expense-merchant-input').value = exp.merchant || '';
        $('#expense-amount-input').value = exp.amount || '';

        // Type
        const txType = exp.transaction_type || 'expense';
        $('#expense-type').value = txType;
        $('#expense-transfer-row').style.display = txType === 'transfer' ? '' : 'none';
        $('#expense-account-label').textContent = txType === 'transfer' ? 'From Account' : 'Account';

        // Account dropdown (editable, with warning for source-detected)
        $('#expense-account-select').innerHTML = acctOptionsHTML('— Account —');
        $('#expense-transfer-to').innerHTML = acctOptionsHTML('— Transfer To —');

        // Match account by last4 digits first (most reliable), then by name
        const last4 = exp.account_last4 || '';
        const acctName = exp.account_name || '';
        let matchedAcctName = '';
        const sel = $('#expense-account-select');

        // Try matching by last 4 digits (ignores generic names like "Visa")
        // Also map known debit card numbers to their checking accounts
        const _debitCardMap = { '0695': '4500' }; // debit ••0695 = TGF Checking ••4500
        const effectiveLast4 = _debitCardMap[last4] || last4;
        if (effectiveLast4) {
            const byLast4 = ACCT.accounts.find(a => a.last_four === effectiveLast4);
            if (byLast4) {
                matchedAcctName = byLast4.name;
                sel.value = byLast4.name;
            }
        }
        // Fallback: match by account_name (skip generic card types)
        if (!matchedAcctName && acctName) {
            const generic = ['visa', 'mastercard', 'amex', 'discover'];
            if (!generic.includes(acctName.toLowerCase())) {
                for (const opt of sel.options) {
                    if (opt.value && opt.value.toUpperCase() === acctName.toUpperCase()) {
                        matchedAcctName = opt.value;
                        opt.selected = true; break;
                    }
                }
            }
        }
        _expOriginalAccount = matchedAcctName || acctName;
        // Show source info (card + last4) for reference, not as a warning
        const warnEl = $('#expense-account-warning');
        if (last4 || acctName) {
            const srcDesc = last4 ? `Card ••${last4}${acctName ? ' (' + acctName + ')' : ''}` : acctName;
            warnEl.textContent = matchedAcctName
                ? `Matched from ${srcDesc}`
                : `Source: ${srcDesc} — no matching account found`;
            warnEl.style.display = '';
            warnEl.style.color = matchedAcctName ? 'var(--text-muted)' : 'var(--red)';
        } else {
            warnEl.style.display = 'none';
        }

        // Entity dropdown
        const entOpts = '<option value="">— None —</option>' +
            ACCT.entities.map(e => `<option value="${e.short_name}" ${
                (exp.entity || '').toUpperCase() === e.short_name.toUpperCase() ? 'selected' : ''
            }>${e.short_name}</option>`).join('');
        $('#expense-entity').innerHTML = entOpts;

        // Category dropdown (show all categories, not just expense)
        const catType = txType === 'income' ? 'income' : 'expense';
        const catOpts = '<option value="">— None —</option>' +
            ACCT.categories.filter(c => c.type === catType).map(c => `<option value="${c.name}" ${
                (exp.category || '').toUpperCase() === c.name.toUpperCase() ? 'selected' : ''
            }>${c.name}</option>`).join('');
        $('#expense-category').innerHTML = catOpts;

        // Event dropdown
        const evOpts = '<option value="">No Event</option>' +
            ACCT.events.map(ev => `<option value="${ev.item_name}" ${
                exp.event_name === ev.item_name ? 'selected' : ''
            }>${ev.item_name}${ev.event_date ? ' (' + ev.event_date + ')' : ''}</option>`).join('');
        $('#expense-event').innerHTML = evOpts;

        // AI suggestion
        const sugBar = $('#expense-suggestion-bar');
        if (exp.suggestion) {
            const s = exp.suggestion;
            sugBar.style.display = '';
            const parts = [];
            if (s.category) parts.push(`Category: <strong>${s.category}</strong>`);
            if (s.entity) parts.push(`Entity: <strong>${s.entity}</strong>`);
            parts.push(`<em>(${s.confidence} — ${s.source || ''})</em>`);
            $('#expense-suggestion-text').innerHTML = 'Suggestion: ' + parts.join(' &middot; ');

            // Pre-fill from suggestion if fields are empty
            if (!exp.category && s.category) {
                for (const opt of $('#expense-category').options) {
                    if (opt.value && opt.value.toUpperCase() === s.category.toUpperCase()) {
                        opt.selected = true; break;
                    }
                }
            }
            if (!exp.entity && s.entity) {
                for (const opt of $('#expense-entity').options) {
                    if (opt.value && opt.value.toUpperCase() === s.entity.toUpperCase()) {
                        opt.selected = true; break;
                    }
                }
            }
        } else {
            sugBar.style.display = 'none';
        }

        // Event guess from description
        if (!exp.event_name) {
            const guess = _guessEventFromDesc(exp.merchant);
            if (guess) {
                for (const opt of $('#expense-event').options) {
                    if (opt.value === guess) { opt.selected = true; break; }
                }
            }
        }

        // Notes
        $('#expense-notes').value = exp.notes || '';

        // Source data (raw parsing output)
        const rawData = exp.raw_extract || null;
        const sourceDetails = $('#expense-source-data');
        const rawEl = $('#expense-raw-data');
        if (rawData || exp.email_uid) {
            sourceDetails.style.display = '';
            sourceDetails.removeAttribute('open');
            let dataStr = '';
            if (exp.email_uid) dataStr += `Email UID: ${exp.email_uid}\n`;
            if (exp.created_at) dataStr += `Parsed at: ${exp.created_at}\n`;
            if (exp.source_type) dataStr += `Source: ${exp.source_type}\n`;
            if (exp.account_last4) dataStr += `Card: ••${exp.account_last4}\n`;
            if (rawData) {
                dataStr += '\n--- Raw Extraction ---\n';
                try {
                    dataStr += JSON.stringify(JSON.parse(rawData), null, 2);
                } catch (_) {
                    dataStr += rawData;
                }
            }
            rawEl.textContent = dataStr;
        } else {
            sourceDetails.style.display = 'none';
        }

        // Show/hide approve+ignore+discard buttons based on status
        const isPending = status === 'pending';
        $('#expense-btn-approve').style.display = isPending ? '' : 'none';
        $('#expense-btn-discard').style.display = isPending ? '' : 'none';
        const hasMerchant = !!(exp.merchant || '').trim();
        $('#expense-btn-block').style.display = (isPending && hasMerchant) ? '' : 'none';
        $('#expense-btn-ignore').style.display = 'none';
        $('#expense-btn-save').style.display = isPending ? 'none' : '';

        $('#expense-review-modal').style.display = 'flex';
    } catch (e) {
        alert('Error loading expense: ' + e.message);
    }
}

// Guess event from merchant/description text
function _guessEventFromDesc(text) {
    if (!text || !ACCT.events.length) return null;
    const lower = text.toLowerCase();
    for (const ev of ACCT.events) {
        const name = (ev.item_name || '').toLowerCase();
        const words = name.split(/[\s\-–—]+/).filter(w => w.length > 2);
        for (const w of words) {
            if (lower.includes(w)) return ev.item_name;
        }
    }
    return null;
}

async function saveExpenseReview(action) {
    const expId = $('#expense-review-id').value;
    if (!expId) return;

    // Account change warning
    const newAcct = $('#expense-account-select').value || null;
    const sourceType = $('#expense-source-type').value;
    if (newAcct && _expOriginalAccount && sourceType &&
        newAcct.toUpperCase() !== _expOriginalAccount.toUpperCase()) {
        const srcName = _SOURCE_LABELS[sourceType] || sourceType;
        if (!confirm(`Account was detected from ${srcName} as "${_expOriginalAccount}".\n\nAre you sure you want to change it to "${newAcct}"?`)) {
            return;
        }
    }

    const fields = {
        merchant: $('#expense-merchant-input').value.trim() || null,
        amount: parseFloat($('#expense-amount-input').value) || null,
        transaction_date: $('#expense-date-input').value || null,
        transaction_type: $('#expense-type').value || 'expense',
        account_name: newAcct,
        entity: $('#expense-entity').value || null,
        category: $('#expense-category').value || null,
        event_name: $('#expense-event').value || null,
        notes: $('#expense-notes').value.trim() || null,
        reviewed_at: new Date().toISOString(),
        reviewed_by: 'admin',
    };

    if (action === 'approve') {
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

// ── Customer / Vendor Typeahead ───────────────────────────

function _customerDisplayName(c) {
    if (c.company_name) return c.company_name;
    if (c.display_name) return c.display_name;
    const fn = (c.first_name || '').trim();
    const ln = (c.last_name || '').trim();
    return fn && ln ? `${ln}, ${fn}` : (ln || fn);
}

function renderVendorChips() {
    const container = $('#txn-vendor-chips');
    if (!container) return;
    const vendors = _allVendors();
    if (!vendors.length) {
        container.innerHTML = '<span style="font-size:0.75rem;color:#9ca3af;font-style:italic;">No vendors yet — add one above</span>';
        return;
    }
    const selectedId = parseInt($('#txn-customer-id').value) || 0;
    container.innerHTML = vendors.map(v => {
        const active = v.customer_id === selectedId;
        const vName = _customerDisplayName(v);
        return `<button type="button" class="txn-vendor-chip" data-id="${v.customer_id}" data-name="${vName}"
            style="padding:3px 10px;border-radius:12px;font-size:0.78rem;font-weight:600;cursor:pointer;border:1.5px solid ${active ? '#d97706' : '#fcd34d'};background:${active ? '#fef3c7' : '#fffbeb'};color:#92400e;transition:all .15s;">
            ${vName}
        </button>`;
    }).join('');
    container.querySelectorAll('.txn-vendor-chip').forEach(btn => {
        btn.addEventListener('click', () => {
            setTxnCustomer(parseInt(btn.dataset.id), btn.dataset.name, true);
        });
    });
}

function setTxnCustomer(id, name, isVendor) {
    $('#txn-customer-id').value = id;
    $('#txn-customer-search').value = '';
    $('#txn-customer-dropdown').style.display = 'none';
    const sel = $('#txn-customer-selected');
    $('#txn-customer-selected-name').textContent = (isVendor ? '🏷 ' : '') + name;
    sel.style.display = 'flex';
    sel.style.background = isVendor ? '#fffbeb' : '#f0fdf4';
    sel.style.borderColor = isVendor ? '#fcd34d' : '#86efac';
}

function clearTxnCustomer() {
    $('#txn-customer-id').value = '';
    $('#txn-customer-search').value = '';
    $('#txn-customer-selected').style.display = 'none';
    $('#txn-customer-dropdown').style.display = 'none';
}

function _fuzzyMatchCustomers(query) {
    if (!query) return [];
    const q = query.toLowerCase();
    return ACCT.customers.filter(c => {
        const display = _customerDisplayName(c).toLowerCase();
        const full = `${c.first_name || ''} ${c.last_name || ''}`.toLowerCase();
        const rev = `${c.last_name || ''} ${c.first_name || ''}`.toLowerCase();
        return display.includes(q) || full.includes(q) || rev.includes(q);
    }).slice(0, 8);
}

function _allVendors() {
    return ACCT.customers.filter(c => c.is_vendor);
}

function _renderCustomerDropdown(matches, showVendorSection) {
    const dd = $('#txn-customer-dropdown');

    let html = '';

    if (showVendorSection) {
        const vendors = _allVendors();
        if (vendors.length) {
            html += `<div style="padding:4px 12px;font-size:0.65rem;font-weight:700;color:#92400e;background:#fffbeb;letter-spacing:.05em;border-bottom:1px solid #fde68a;">VENDORS</div>`;
            html += vendors.map(c => _customerItemHTML(c)).join('');
            if (matches.length) {
                html += `<div style="padding:4px 12px;font-size:0.65rem;font-weight:700;color:#6b7280;background:#f9fafb;letter-spacing:.05em;border-bottom:1px solid #f3f4f6;">CUSTOMERS</div>`;
            }
        }
    }

    html += matches.map(c => _customerItemHTML(c)).join('');

    if (!html) {
        dd.style.display = 'none';
        return;
    }

    // Always append + New Vendor footer
    html += `<div id="btn-new-vendor-inline" style="padding:8px 12px;cursor:pointer;font-size:0.8rem;color:#2563eb;font-weight:600;border-top:1px solid #e5e7eb;display:flex;align-items:center;gap:6px;">
        <span style="font-size:1rem;line-height:1;">＋</span> New Vendor
    </div>`;

    dd.innerHTML = html;
    dd.style.display = '';

    dd.querySelectorAll('.acct-cust-item').forEach(el => {
        el.addEventListener('mousedown', (e) => {
            e.preventDefault();
            setTxnCustomer(parseInt(el.dataset.id), el.dataset.name, el.dataset.vendor === '1');
        });
        el.addEventListener('mouseover', () => el.style.background = '#f9fafb');
        el.addEventListener('mouseout', () => el.style.background = '');
    });
    dd.querySelector('#btn-new-vendor-inline')?.addEventListener('mousedown', (e) => {
        e.preventDefault();
        dd.style.display = 'none';
        openVendorModal();
    });
}

function _customerItemHTML(c) {
    const label = c.is_vendor ? '<span style="font-size:0.65rem;background:#fef3c7;color:#92400e;padding:1px 5px;border-radius:8px;margin-left:4px;">Vendor</span>' : '';
    const sub = [c.chapter, c.current_player_status].filter(Boolean).join(' · ');
    return `<div class="acct-cust-item" data-id="${c.customer_id}" data-name="${_customerDisplayName(c)}" data-vendor="${c.is_vendor ? '1' : '0'}"
                 style="padding:8px 12px;cursor:pointer;border-bottom:1px solid #f3f4f6;">
        <div style="font-weight:500;font-size:0.875rem;">${_customerDisplayName(c)}${label}</div>
        ${sub ? `<div style="font-size:0.75rem;color:#6b7280;">${sub}</div>` : ''}
    </div>`;
}

function suggestCustomerFromDescription(desc) {
    if (!desc || !ACCT.customers.length) return;
    const words = desc.toLowerCase().split(/\s+/);
    let best = null, bestScore = 0;
    for (const c of ACCT.customers) {
        const full = _customerDisplayName(c).toLowerCase();
        const last = (c.last_name || '').toLowerCase();
        let score = 0;
        for (const w of words) {
            if (w.length < 3) continue;
            if (full.includes(w)) score += 2;
            else if (last.startsWith(w)) score += 1;
        }
        if (score > bestScore) { bestScore = score; best = c; }
    }
    if (best && bestScore >= 2) {
        const search = $('#txn-customer-search');
        search.value = '';
        search.placeholder = `Suggested: ${_customerDisplayName(best)} — press Enter to accept`;
        search._suggested = best;
    }
}

function initCustomerTypeahead() {
    const input = $('#txn-customer-search');
    const dd = $('#txn-customer-dropdown');
    if (!input) return;

    input.addEventListener('input', () => {
        input._suggested = null;
        input.placeholder = 'Search by name…';
        const q = input.value.trim();
        if (!q) {
            $('#txn-customer-id').value = '';
            $('#txn-customer-badge').style.display = 'none';
            // Show vendors on empty input
            _renderCustomerDropdown([], true);
            return;
        }
        _renderCustomerDropdown(_fuzzyMatchCustomers(q), false);
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') { dd.style.display = 'none'; }
        if (e.key === 'Enter') {
            e.preventDefault();
            if (input._suggested) {
                setTxnCustomer(input._suggested.customer_id, _customerDisplayName(input._suggested), input._suggested.is_vendor);
                input._suggested = null;
            } else {
                const first = dd.querySelector('.acct-cust-item');
                if (first) first.dispatchEvent(new Event('mousedown'));
            }
        }
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            const items = dd.querySelectorAll('.acct-cust-item');
            if (items.length) items[0].focus();
        }
    });

    input.addEventListener('blur', () => {
        setTimeout(() => { dd.style.display = 'none'; }, 150);
        if (!$('#txn-customer-id').value) {
            input.placeholder = 'Search by name…';
        }
    });

    input.addEventListener('focus', () => {
        const q = input.value.trim();
        if (q && !$('#txn-customer-id').value) {
            _renderCustomerDropdown(_fuzzyMatchCustomers(q), false);
        } else if (!q) {
            _renderCustomerDropdown([], true);
        }
    });
}

// ── Vendor Modal ─────────────────────────────────────────

function openVendorModal() {
    $('#vendor-name').value = '';
    $('#vendor-phone').value = '';
    $('#vendor-modal-error').style.display = 'none';
    $('#vendor-modal').style.display = 'flex';
    setTimeout(() => $('#vendor-name').focus(), 50);
}

async function runSmartFill() {
    // First do a dry run to show preview
    try {
        const preview = await api('/accounting/smart-fill', { method: 'POST', body: { dry_run: true } });
        if (preview.count === 0) {
            alert('All transactions already have categories assigned.');
            return;
        }
        const ok = confirm(
            `Smart Fill found ${preview.count} transaction(s) without a category split.\n\n` +
            `This will:\n` +
            `• Auto-assign TGF Checking account to GoDaddy income\n` +
            `• Create a default "Event Revenue" split for each income transaction\n` +
            `• You can still edit individual transactions to adjust\n\n` +
            `Apply to all ${preview.count} transactions?`
        );
        if (!ok) return;
        const result = await api('/accounting/smart-fill', { method: 'POST', body: { dry_run: false } });
        alert(`Done! Applied smart defaults to ${result.count} transaction(s).`);
        loadTransactions();
    } catch(e) {
        alert('Error: ' + e.message);
    }
}

async function saveNewVendor() {
    const name = $('#vendor-name').value.trim();
    const phone = $('#vendor-phone').value.trim();
    const errEl = $('#vendor-modal-error');

    if (!name) {
        errEl.textContent = 'Enter a vendor name.';
        errEl.style.display = '';
        return;
    }

    try {
        const vendor = await fetch('/api/accounting/vendors', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, phone }),
        }).then(async r => {
            if (!r.ok) {
                const e = await r.json().catch(() => ({}));
                throw new Error(e.error || 'Failed to create vendor');
            }
            return r.json();
        });

        // Add to local list and select
        const existing = ACCT.customers.findIndex(c => c.customer_id === vendor.customer_id);
        if (existing >= 0) ACCT.customers[existing] = vendor;
        else ACCT.customers.push(vendor);

        setTxnCustomer(vendor.customer_id, vendor.display_name, true);
        $('#vendor-modal').style.display = 'none';
    } catch (e) {
        errEl.textContent = e.message;
        errEl.style.display = '';
    }
}
