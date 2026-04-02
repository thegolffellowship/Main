/* =========================================================
   Accounting Module — Initialization & Event Binding
   ========================================================= */

async function reloadMasterData() {
    const [entities, accounts, categories, tags] = await Promise.all([
        api('/entities'), api('/accounts'), api('/categories'), api('/tags'),
    ]);
    ACCT.entities = entities;
    ACCT.accounts = accounts;
    ACCT.categories = categories;
    ACCT.tags = tags;
    renderEntityPills();
    populateDropdowns();
}

function renderEntityPills() {
    const el = $('#entity-pills');
    const allActive = ACCT.activeEntity === null;
    let html = `<button class="acct-pill ${allActive ? 'active' : ''}" data-entity="">All</button>`;
    html += ACCT.entities.map(e =>
        `<button class="acct-pill ${ACCT.activeEntity === e.id ? 'active' : ''}"
                 data-entity="${e.id}" style="--pill-color:${e.color}">
            ${e.short_name}
        </button>`
    ).join('');
    el.innerHTML = html;

    el.querySelectorAll('.acct-pill').forEach(btn => {
        btn.addEventListener('click', () => {
            ACCT.activeEntity = btn.dataset.entity ? parseInt(btn.dataset.entity) : null;
            renderEntityPills();
            refreshActiveTab();
        });
    });
}

function switchTab(tab) {
    ACCT.activeTab = tab;
    $$('.acct-subtab[data-tab]').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
    $$('.acct-tab-panel').forEach(p => p.classList.toggle('active', p.id === 'panel-' + tab));
    refreshActiveTab();
}

function refreshActiveTab() {
    switch (ACCT.activeTab) {
        case 'dashboard': loadDashboard(); break;
        case 'transactions': loadTransactions(); break;
        case 'accounts': loadAccounts(); break;
        case 'categories': loadCategories(); break;
        case 'reports': loadReports(); break;
    }
}

// ── Init ─────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
    // Load master data
    await reloadMasterData();

    // Sub-tab switching
    $$('.acct-subtab[data-tab]').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // Category type toggle
    $$('.acct-cat-type-toggle .acct-subtab').forEach(btn => {
        btn.addEventListener('click', () => {
            $$('.acct-cat-type-toggle .acct-subtab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            loadCategories();
        });
    });

    // Transaction modal
    $('#btn-add-txn').addEventListener('click', openNewTransaction);
    $('#txn-modal-close').addEventListener('click', closeTxnModal);
    $('#txn-modal-cancel').addEventListener('click', closeTxnModal);
    $('#txn-modal-save').addEventListener('click', saveTransaction);
    $('#btn-add-split').addEventListener('click', addSplitRow);
    $('#txn-amount').addEventListener('input', updateSplitTotal);
    $('#txn-type').addEventListener('change', () => {
        $('#transfer-row').style.display = $('#txn-type').value === 'transfer' ? '' : 'none';
    });

    // Receipt upload
    $('#btn-upload-receipt').addEventListener('click', () => $('#receipt-file').click());
    $('#receipt-file').addEventListener('change', async () => {
        const file = $('#receipt-file').files[0];
        if (!file) return;
        const fd = new FormData();
        fd.append('file', file);
        try {
            const res = await fetch('/api/accounting/upload-receipt', { method: 'POST', body: fd });
            const data = await res.json();
            $('#receipt-filename').textContent = data.filename;
        } catch (e) {
            alert('Upload failed');
        }
    });

    // Account modal
    $('#btn-add-account').addEventListener('click', openAccountModal);
    $('#account-modal-close').addEventListener('click', () => $('#account-modal').style.display = 'none');
    $('#account-modal-cancel').addEventListener('click', () => $('#account-modal').style.display = 'none');
    $('#account-modal-save').addEventListener('click', saveAccount);

    // Category modal
    $('#btn-add-category').addEventListener('click', openCategoryModal);
    $('#category-modal-close').addEventListener('click', () => $('#category-modal').style.display = 'none');
    $('#category-modal-cancel').addEventListener('click', () => $('#category-modal').style.display = 'none');
    $('#category-modal-save').addEventListener('click', saveCategory);

    // CSV import
    $('#btn-import-csv').addEventListener('click', openCsvModal);
    $('#csv-modal-close').addEventListener('click', () => $('#csv-modal').style.display = 'none');
    $('#btn-csv-preview').addEventListener('click', previewCsv);
    $('#btn-csv-back').addEventListener('click', () => {
        $('#csv-step-upload').style.display = '';
        $('#csv-step-preview').style.display = 'none';
    });
    $('#btn-csv-commit').addEventListener('click', commitCsvImport);

    // Transaction filters
    let _searchTimer;
    $('#txn-search').addEventListener('input', () => {
        clearTimeout(_searchTimer);
        _searchTimer = setTimeout(() => { ACCT.txnPage = 0; loadTransactions(); }, 300);
    });
    ['#txn-filter-type', '#txn-filter-account', '#txn-filter-category'].forEach(sel => {
        $(sel).addEventListener('change', () => { ACCT.txnPage = 0; loadTransactions(); });
    });

    // Dashboard date range
    $('#date-range-preset').addEventListener('change', () => {
        const custom = $('#date-range-preset').value === 'custom';
        $('#date-start').style.display = custom ? '' : 'none';
        $('#date-end').style.display = custom ? '' : 'none';
        if (!custom) loadDashboard();
    });
    $('#date-start').addEventListener('change', loadDashboard);
    $('#date-end').addEventListener('change', loadDashboard);

    // Reports
    $('#report-type').addEventListener('change', loadReports);
    $('#report-period').addEventListener('change', loadReports);

    // Close modals on overlay click
    $$('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.style.display = 'none';
        });
    });

    // Load dashboard
    loadDashboard();
});
