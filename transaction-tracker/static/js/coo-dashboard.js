/* =========================================================
   COO Dashboard — Operations Command Center
   ========================================================= */

const COO = { actionFilter: 'open', chatMessages: [], context: {} };

function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }
function fmt(n) { return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n || 0); }

async function api(path, opts = {}) {
    const url = '/api/coo' + path;
    if (opts.body && typeof opts.body === 'object') {
        opts.headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
        opts.body = JSON.stringify(opts.body);
    }
    const res = await fetch(url, opts);
    return res.json();
}

// ── Action Items (Section 1) ────────────────────────────

async function loadActionItems() {
    const params = COO.actionFilter ? `?status=${COO.actionFilter}` : '';
    const items = await api('/action-items' + params);
    renderActionItems(items);
}

function renderActionItems(items) {
    const el = $('#action-items-list');
    if (!items.length) {
        el.innerHTML = '<p class="coo-empty">No action items</p>';
        return;
    }
    el.innerHTML = items.map(item => {
        const urgencyIcon = item.urgency === 'high' ? '\ud83d\udfe5' : item.urgency === 'medium' ? '\ud83d\udfe8' : '\u26aa';
        const checked = item.status === 'completed' ? 'checked' : '';
        const completedClass = item.status === 'completed' ? 'coo-item-done' : '';
        return `<div class="coo-action-item ${completedClass}" data-id="${item.id}">
            <div class="coo-action-top">
                <input type="checkbox" class="coo-checkbox" data-id="${item.id}" ${checked}>
                <span class="coo-urgency">${urgencyIcon}</span>
                <span class="coo-cat-badge">${item.category || 'other'}</span>
                <span class="coo-action-date">${item.email_date || ''}</span>
                <span class="coo-action-from">${item.from_name || ''}</span>
            </div>
            <div class="coo-action-summary">${item.summary || item.subject || ''}</div>
            ${item.status === 'completed' && item.resolution_notes ? `<div class="coo-resolution">${item.resolution_notes}</div>` : ''}
            <div class="coo-action-resolve" id="resolve-${item.id}" style="display:none;">
                <textarea class="coo-resolve-input" placeholder="Resolution notes..." rows="2"></textarea>
                <div class="coo-resolve-actions">
                    <button class="btn btn-primary btn-sm coo-btn-complete" data-id="${item.id}">Mark Complete</button>
                    <button class="btn btn-secondary btn-sm coo-btn-advice" data-id="${item.id}">Get AI Advice</button>
                </div>
            </div>
        </div>`;
    }).join('');

    // Checkbox click → show resolve form
    el.querySelectorAll('.coo-checkbox').forEach(cb => {
        cb.addEventListener('change', (e) => {
            const id = cb.dataset.id;
            const resolveEl = $(`#resolve-${id}`);
            if (cb.checked && resolveEl) {
                resolveEl.style.display = '';
            } else if (resolveEl) {
                resolveEl.style.display = 'none';
            }
        });
    });

    // Mark Complete
    el.querySelectorAll('.coo-btn-complete').forEach(btn => {
        btn.addEventListener('click', async () => {
            const id = btn.dataset.id;
            const textarea = $(`#resolve-${id} .coo-resolve-input`);
            await api(`/action-items/${id}`, {
                method: 'PATCH',
                body: {
                    status: 'completed',
                    completed_at: new Date().toISOString(),
                    resolution_notes: textarea ? textarea.value : '',
                },
            });
            loadActionItems();
        });
    });

    // Get AI Advice
    el.querySelectorAll('.coo-btn-advice').forEach(btn => {
        btn.addEventListener('click', () => {
            const itemEl = btn.closest('.coo-action-item');
            const summary = itemEl.querySelector('.coo-action-summary').textContent;
            const input = $('#chat-input');
            input.value = `I need advice on this action item: "${summary}"`;
            input.focus();
            document.getElementById('section-chat').scrollIntoView({ behavior: 'smooth' });
        });
    });
}

// ── Financial Snapshot (Section 2) ──────────────────────

async function loadFinancialSnapshot() {
    const data = await api('/financial-snapshot');
    COO.context.financial = data;

    // Accounts
    $('#val-checking').textContent = fmt(data.accounts.tgf_checking_0341);
    $('#val-mm').textContent = fmt(data.accounts.tgf_money_market_8045);
    $('#val-total').textContent = fmt(data.accounts.tgf_total);

    // Obligations
    $('#val-prizes').textContent = fmt(data.obligations.prize_pools_owed);
    $('#val-course-fees').textContent = fmt(data.obligations.course_fees_owed);
    $('#val-tax').textContent = fmt(data.obligations.tax_reserve_mtd);
    const avail = data.obligations.available_to_spend;
    const availEl = $('#val-available');
    availEl.textContent = fmt(avail);
    availEl.className = `coo-fin-value ${avail >= 0 ? 'coo-positive' : 'coo-negative'}`;

    // Debts
    $('#val-irs').textContent = fmt(data.debts.irs_balance);
    $('#val-grandparent').textContent = fmt(data.debts.grandparent_loan);
    $('#val-chase-biz').textContent = fmt(data.debts.chase_biz_7680);
    $('#val-chase-saph').textContent = fmt(data.debts.chase_sapphire_6159);
    $('#val-debt-total').textContent = fmt(data.debts.total_obligations);
}

// ── Review Queue (Section 3) ────────────────────────────

async function loadReviewQueue() {
    const items = await api('/review-queue');
    $('#review-count').textContent = items.length;
    COO.context.pending_review = items.length;
    renderReviewQueue(items);
}

function renderReviewQueue(items) {
    const el = $('#review-queue-coo');
    if (!items.length) {
        el.innerHTML = '<p class="coo-empty">All clear! Nothing to review.</p>';
        return;
    }
    el.innerHTML = items.map(item => {
        const typeBadge = {
            'chase_alert': 'Chase', 'venmo': 'Venmo', 'receipt': 'Receipt',
            'action_required': 'Action',
        }[item.source_type] || item.source_type;
        const typeClass = `coo-source-${item.source_type || 'other'}`;
        return `<div class="coo-review-item" data-id="${item.id}" data-type="${item.queue_type}">
            <div class="coo-review-top">
                <span class="coo-source-badge ${typeClass}">${typeBadge}</span>
                <span class="coo-review-merchant">${item.merchant || '—'}</span>
                ${item.amount ? `<span class="coo-review-amount">${fmt(item.amount)}</span>` : ''}
                <span class="coo-review-date">${item.transaction_date || ''}</span>
                <span class="coo-confidence" title="AI confidence">${item.confidence || 0}%</span>
            </div>
            ${item.notes ? `<div class="coo-review-notes">${item.notes}</div>` : ''}
            <div class="coo-review-actions">
                <select class="coo-review-category" data-id="${item.id}" data-type="${item.queue_type}">
                    <option value="">Category...</option>
                    <option ${item.category === 'AI Services' ? 'selected' : ''}>AI Services</option>
                    <option ${item.category === 'Automation Software' ? 'selected' : ''}>Automation Software</option>
                    <option ${item.category === 'Hosting' ? 'selected' : ''}>Hosting</option>
                    <option ${item.category === 'Platform Fees' ? 'selected' : ''}>Platform Fees</option>
                    <option ${item.category === 'Golf Course Fees' ? 'selected' : ''}>Golf Course Fees</option>
                    <option ${item.category === 'Event Supplies' ? 'selected' : ''}>Event Supplies</option>
                    <option ${item.category === 'contract' ? 'selected' : ''}>Contract</option>
                    <option ${item.category === 'payment' ? 'selected' : ''}>Payment</option>
                    <option ${item.category === 'member_inquiry' ? 'selected' : ''}>Member Inquiry</option>
                </select>
                <select class="coo-review-entity" data-id="${item.id}" data-type="${item.queue_type}">
                    <option value="TGF" ${item.entity === 'TGF' ? 'selected' : ''}>TGF</option>
                    <option value="Personal" ${item.entity === 'Personal' ? 'selected' : ''}>Personal</option>
                    <option value="Horizon" ${item.entity === 'Horizon' ? 'selected' : ''}>Horizon</option>
                </select>
                <button class="btn btn-primary btn-sm coo-btn-approve" data-id="${item.id}" data-type="${item.queue_type}">Approve</button>
                <button class="btn btn-secondary btn-sm coo-btn-ignore" data-id="${item.id}" data-type="${item.queue_type}">Ignore</button>
            </div>
        </div>`;
    }).join('');

    // Approve button
    el.querySelectorAll('.coo-btn-approve').forEach(btn => {
        btn.addEventListener('click', async () => {
            const id = btn.dataset.id;
            const type = btn.dataset.type;
            const row = btn.closest('.coo-review-item');
            const cat = row.querySelector('.coo-review-category').value;
            const entity = row.querySelector('.coo-review-entity').value;

            if (type === 'expense') {
                await fetch(`/api/accounting/expense-transactions/${id}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        review_status: 'approved',
                        reviewed_at: new Date().toISOString(),
                        category: cat || undefined,
                        entity: entity || undefined,
                    }),
                });
            } else {
                await api(`/action-items/${id}`, {
                    method: 'PATCH',
                    body: { status: 'open' },
                });
            }
            loadReviewQueue();
        });
    });

    // Ignore button
    el.querySelectorAll('.coo-btn-ignore').forEach(btn => {
        btn.addEventListener('click', async () => {
            const id = btn.dataset.id;
            const type = btn.dataset.type;
            if (type === 'expense') {
                await fetch(`/api/accounting/expense-transactions/${id}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ review_status: 'ignored' }),
                });
            } else {
                await api(`/action-items/${id}`, {
                    method: 'PATCH',
                    body: { status: 'dismissed' },
                });
            }
            loadReviewQueue();
        });
    });
}

// ── COO Chat (Section 4) ────────────────────────────────

async function sendChatMessage() {
    const input = $('#chat-input');
    const text = input.value.trim();
    if (!text) return;

    // Add user message
    COO.chatMessages.push({ role: 'user', content: text });
    appendChatBubble('user', text);
    input.value = '';
    input.disabled = true;
    $('#btn-chat-send').disabled = true;

    try {
        const resp = await api('/chat', {
            method: 'POST',
            body: {
                messages: COO.chatMessages,
                context: COO.context,
            },
        });
        if (resp.content) {
            COO.chatMessages.push({ role: 'assistant', content: resp.content });
            appendChatBubble('assistant', resp.content);
        } else if (resp.error) {
            appendChatBubble('assistant', `Error: ${resp.error}`);
        }
    } catch (e) {
        appendChatBubble('assistant', `Chat error: ${e.message}`);
    }

    input.disabled = false;
    $('#btn-chat-send').disabled = false;
    input.focus();
}

function appendChatBubble(role, text) {
    const container = $('#chat-messages');
    // Convert markdown-like formatting
    const html = text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
    const div = document.createElement('div');
    div.className = `coo-chat-msg coo-chat-${role}`;
    div.innerHTML = `<div class="coo-chat-bubble">${html}</div>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

// ── Editable Values ─────────────────────────────────────

function openEditModal(key, label, currentValue) {
    $('#edit-value-key').value = key;
    $('#edit-value-title').textContent = `Edit ${label}`;
    $('#edit-value-label').textContent = label;
    $('#edit-value-input').value = currentValue || 0;
    $('#edit-value-modal').style.display = 'flex';
    $('#edit-value-input').focus();
}

async function saveEditValue() {
    const key = $('#edit-value-key').value;
    const value = parseFloat($('#edit-value-input').value) || 0;
    await api('/manual-values', { method: 'POST', body: { key, value } });
    $('#edit-value-modal').style.display = 'none';
    loadFinancialSnapshot();
}

// ── Init ─────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
    // Block non-admin users
    if (typeof currentRole !== "undefined" && currentRole && currentRole !== "admin") {
        window.location.href = "/";
        return;
    }

    // Load all sections
    await Promise.all([
        loadActionItems(),
        loadFinancialSnapshot(),
        loadReviewQueue(),
    ]);

    // Build context for chat
    try {
        const actionItems = await api('/action-items?status=open');
        COO.context.action_items = actionItems.map(a => ({
            summary: a.summary || a.subject,
            urgency: a.urgency,
            category: a.category,
            from: a.from_name,
        }));
    } catch (e) {}

    // Action item filter pills
    $$('.coo-filter-pills .coo-pill').forEach(btn => {
        btn.addEventListener('click', () => {
            $$('.coo-filter-pills .coo-pill').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            COO.actionFilter = btn.dataset.filter;
            loadActionItems();
        });
    });

    // Editable values — click to edit
    $$('.coo-editable').forEach(el => {
        el.style.cursor = 'pointer';
        el.title = 'Click to edit';
        el.addEventListener('click', () => {
            const key = el.dataset.key;
            const label = el.closest('.coo-fin-card').querySelector('.coo-fin-label').textContent;
            const current = parseFloat(el.textContent.replace(/[$,]/g, '')) || 0;
            openEditModal(key, label, current);
        });
    });

    // Edit modal
    $('#edit-value-save').addEventListener('click', saveEditValue);
    $('#edit-value-cancel').addEventListener('click', () => $('#edit-value-modal').style.display = 'none');
    $('#edit-value-close').addEventListener('click', () => $('#edit-value-modal').style.display = 'none');

    // Chat
    $('#btn-chat-send').addEventListener('click', sendChatMessage);
    $('#chat-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage();
        }
    });

    // Modal overlay click
    $$('.modal-overlay').forEach(ov => {
        ov.addEventListener('click', (e) => {
            if (e.target === ov) ov.style.display = 'none';
        });
    });
});
