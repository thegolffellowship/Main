/* =========================================================
   COO Dashboard — Operations Command Center
   ========================================================= */

const COO = { actionFilter: 'open', chatMessages: [], context: {}, selectedItems: new Set(), chatSessionId: null, chatSessions: [] };

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
    COO.selectedItems.clear();
    updateDismissSelectedBtn();

    if (!items.length) {
        el.innerHTML = '<p class="coo-empty">No action items</p>';
        return;
    }

    // Group items by category (topic)
    const groups = {};
    items.forEach(item => {
        const cat = item.category || 'other';
        if (!groups[cat]) groups[cat] = [];
        groups[cat].push(item);
    });

    // Sort groups: most items first
    const sortedCats = Object.keys(groups).sort((a, b) => groups[b].length - groups[a].length);

    function renderItem(item) {
        const urgencyIcon = item.urgency === 'high' ? '\ud83d\udfe5' : item.urgency === 'medium' ? '\ud83d\udfe8' : '\u26aa';
        const isCompleted = item.status === 'completed';
        const isDismissed = item.status === 'dismissed';
        const completedClass = isCompleted ? 'coo-item-done' : isDismissed ? 'coo-item-done' : '';
        const isActionable = !isCompleted && !isDismissed;
        return `<div class="coo-action-item ${completedClass}" data-id="${item.id}">
            <div class="coo-action-top">
                ${isActionable ? `<input type="checkbox" class="coo-select-cb" data-id="${item.id}" title="Select for batch action">` : ''}
                <span class="coo-urgency">${urgencyIcon}</span>
                <span class="coo-action-date">${item.email_date || ''}</span>
                <span class="coo-action-from">${item.from_name || ''}</span>
                ${isActionable ? `<button class="btn btn-secondary btn-sm coo-btn-dismiss" data-id="${item.id}" style="margin-left:auto;font-size:0.7rem;padding:0.15rem 0.5rem;color:var(--text-muted);">Dismiss</button>` : ''}
                ${isDismissed ? '<span style="margin-left:auto;font-size:0.7rem;color:var(--text-muted);font-style:italic;">dismissed</span>' : ''}
            </div>
            <div class="coo-action-summary">${item.summary || item.subject || ''}</div>
            ${item.resolution_notes ? `<div class="coo-resolution">${item.resolution_notes}</div>` : ''}
            ${isActionable ? `<div class="coo-action-resolve" id="resolve-${item.id}" style="display:none;">
                <textarea class="coo-resolve-input" placeholder="Resolution notes..." rows="2"></textarea>
                <div class="coo-resolve-actions">
                    <button class="btn btn-primary btn-sm coo-btn-complete" data-id="${item.id}">Mark Complete</button>
                    <button class="btn btn-secondary btn-sm coo-btn-advice" data-id="${item.id}">Get AI Advice</button>
                </div>
            </div>` : ''}
        </div>`;
    }

    // Render grouped by topic with collapsible headers
    el.innerHTML = sortedCats.map(cat => {
        const catItems = groups[cat];
        const actionableCount = catItems.filter(i => i.status !== 'completed' && i.status !== 'dismissed').length;
        return `<div class="coo-topic-group" data-category="${cat}">
            <div class="coo-topic-header">
                <span class="coo-topic-toggle">&#9660;</span>
                <span class="coo-cat-badge">${cat}</span>
                <span class="coo-topic-count">${catItems.length} item${catItems.length !== 1 ? 's' : ''}${actionableCount !== catItems.length ? ` (${actionableCount} actionable)` : ''}</span>
                <button class="btn btn-secondary btn-sm coo-btn-dismiss-group" data-category="${cat}" style="margin-left:auto;font-size:0.7rem;padding:0.15rem 0.5rem;color:var(--text-muted);">Dismiss Group</button>
            </div>
            <div class="coo-topic-items">${catItems.map(renderItem).join('')}</div>
        </div>`;
    }).join('');

    // Select checkbox → track for batch actions
    el.querySelectorAll('.coo-select-cb').forEach(cb => {
        cb.addEventListener('change', () => {
            const id = parseInt(cb.dataset.id);
            if (cb.checked) {
                COO.selectedItems.add(id);
            } else {
                COO.selectedItems.delete(id);
            }
            updateDismissSelectedBtn();
            // Also show resolve form when checked
            const resolveEl = $(`#resolve-${id}`);
            if (cb.checked && resolveEl) resolveEl.style.display = '';
            else if (resolveEl) resolveEl.style.display = 'none';
        });
    });

    // Individual dismiss
    el.querySelectorAll('.coo-btn-dismiss').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const id = btn.dataset.id;
            await api(`/action-items/${id}`, {
                method: 'PATCH',
                body: { status: 'dismissed' },
            });
            loadActionItems();
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

    // Topic group collapse/expand
    el.querySelectorAll('.coo-topic-header').forEach(header => {
        header.addEventListener('click', (e) => {
            if (e.target.closest('.coo-btn-dismiss-group')) return;
            const group = header.closest('.coo-topic-group');
            const items = group.querySelector('.coo-topic-items');
            const toggle = header.querySelector('.coo-topic-toggle');
            const collapsed = items.style.display === 'none';
            items.style.display = collapsed ? '' : 'none';
            toggle.innerHTML = collapsed ? '&#9660;' : '&#9654;';
        });
    });

    // Dismiss entire topic group
    el.querySelectorAll('.coo-btn-dismiss-group').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation();
            const cat = btn.dataset.category;
            if (!confirm(`Dismiss all "${cat}" items?`)) return;
            btn.disabled = true;
            const groupItems = items.filter(i => (i.category || 'other') === cat && i.status !== 'completed' && i.status !== 'dismissed');
            const ids = groupItems.map(i => i.id);
            if (ids.length) {
                await api('/action-items/batch-dismiss', {
                    method: 'POST',
                    body: { item_ids: ids },
                });
                loadActionItems();
            }
            btn.disabled = false;
        });
    });
}

function updateDismissSelectedBtn() {
    const btn = document.getElementById('btn-dismiss-selected');
    const count = document.getElementById('dismiss-count');
    if (!btn) return;
    if (COO.selectedItems.size > 0) {
        btn.style.display = '';
        if (count) count.textContent = COO.selectedItems.size;
    } else {
        btn.style.display = 'none';
    }
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

    appendChatBubble('user', text);
    input.value = '';
    input.disabled = true;
    $('#btn-chat-send').disabled = true;

    try {
        const resp = await api('/chat', {
            method: 'POST',
            body: {
                message: text,
                session_id: COO.chatSessionId,
                context: COO.context,
            },
        });
        if (resp.session_id) {
            COO.chatSessionId = resp.session_id;
        }
        if (resp.content) {
            appendChatBubble('assistant', resp.content);
        } else if (resp.error) {
            appendChatBubble('assistant', `Error: ${resp.error}`);
        }
        // Refresh session list sidebar
        loadChatSessions();
    } catch (e) {
        appendChatBubble('assistant', `Chat error: ${e.message}`);
    }

    input.disabled = false;
    $('#btn-chat-send').disabled = false;
    input.focus();
}

// ── Chat Session Management ─────────────────────────────────

async function loadChatSessions() {
    try {
        const sessions = await api('/chat-sessions');
        COO.chatSessions = sessions;
        renderChatSessionList(sessions);
    } catch (e) { /* silent */ }
}

function renderChatSessionList(sessions) {
    const el = document.getElementById('chat-session-list');
    if (!el) return;
    if (!sessions.length) {
        el.innerHTML = '<div class="coo-chat-no-sessions">No previous chats</div>';
        return;
    }
    el.innerHTML = sessions.map(s => {
        const active = s.id === COO.chatSessionId ? 'coo-session-active' : '';
        const date = s.updated_at ? new Date(s.updated_at + 'Z').toLocaleDateString() : '';
        const count = s.message_count || 0;
        return `<div class="coo-session-item ${active}" data-sid="${s.id}">
            <div class="coo-session-title">${(s.title || 'New Chat').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>
            <div class="coo-session-meta">${date} · ${count} msg${count !== 1 ? 's' : ''}</div>
        </div>`;
    }).join('');

    el.querySelectorAll('.coo-session-item').forEach(item => {
        item.addEventListener('click', () => loadChatSession(parseInt(item.dataset.sid)));
    });
}

async function loadChatSession(sessionId) {
    try {
        const session = await api(`/chat-sessions/${sessionId}`);
        COO.chatSessionId = session.id;
        const container = $('#chat-messages');
        // Clear and rebuild from DB messages
        container.innerHTML = `<div class="coo-chat-msg coo-chat-assistant">
            <div class="coo-chat-bubble">Hey Kerry. I'm your COO Agent. Ask me anything about TGF operations, finances, or action items. I have full context on your current state.</div>
        </div>`;
        (session.messages || []).forEach(m => {
            appendChatBubble(m.role, m.content);
        });
        // Update active state in sidebar
        renderChatSessionList(COO.chatSessions);
    } catch (e) {
        console.error('Failed to load session:', e);
    }
}

async function startNewChat() {
    COO.chatSessionId = null;
    const container = $('#chat-messages');
    container.innerHTML = `<div class="coo-chat-msg coo-chat-assistant">
        <div class="coo-chat-bubble">Hey Kerry. I'm your COO Agent. Ask me anything about TGF operations, finances, or action items. I have full context on your current state.</div>
    </div>`;
    renderChatSessionList(COO.chatSessions);
    $('#chat-input').focus();
}

async function deleteCurrentChat() {
    if (!COO.chatSessionId) return;
    if (!confirm('Delete this chat session?')) return;
    await api(`/chat-sessions/${COO.chatSessionId}`, { method: 'DELETE' });
    await startNewChat();
    loadChatSessions();
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
        loadChatSessions(),
    ]);

    // Auto-load most recent session if one exists
    if (COO.chatSessions.length > 0) {
        const latest = COO.chatSessions[0];
        if (latest.message_count > 0) {
            await loadChatSession(latest.id);
        }
    }

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
    const btnNewChat = document.getElementById('btn-new-chat');
    if (btnNewChat) btnNewChat.addEventListener('click', startNewChat);
    const btnDelChat = document.getElementById('btn-delete-chat');
    if (btnDelChat) btnDelChat.addEventListener('click', deleteCurrentChat);

    // ── Bulk Action Buttons ────────────────────────────────
    // Consolidate Duplicates
    const btnConsolidate = document.getElementById('btn-consolidate');
    if (btnConsolidate) {
        btnConsolidate.addEventListener('click', async () => {
            btnConsolidate.disabled = true;
            btnConsolidate.textContent = 'Consolidating…';
            try {
                const res = await api('/action-items/consolidate', { method: 'POST' });
                const msg = res.consolidated
                    ? `Consolidated ${res.consolidated} duplicate(s) across ${res.groups} group(s).`
                    : 'No duplicates found.';
                alert(msg);
                loadActionItems();
            } catch (e) {
                alert('Error consolidating: ' + e.message);
            }
            btnConsolidate.disabled = false;
            btnConsolidate.textContent = 'Consolidate Duplicates';
        });
    }

    // Dismiss Selected
    const btnDismissSelected = document.getElementById('btn-dismiss-selected');
    if (btnDismissSelected) {
        btnDismissSelected.addEventListener('click', async () => {
            if (!COO.selectedItems.size) return;
            if (!confirm(`Dismiss ${COO.selectedItems.size} selected item(s)?`)) return;
            btnDismissSelected.disabled = true;
            try {
                await api('/action-items/batch-dismiss', {
                    method: 'POST',
                    body: { item_ids: [...COO.selectedItems] },
                });
                COO.selectedItems.clear();
                updateDismissSelectedBtn();
                loadActionItems();
            } catch (e) {
                alert('Error dismissing: ' + e.message);
            }
            btnDismissSelected.disabled = false;
        });
    }

    // Dismiss All Visible
    const btnDismissAll = document.getElementById('btn-dismiss-all');
    if (btnDismissAll) {
        btnDismissAll.addEventListener('click', async () => {
            const filterLabel = COO.actionFilter || 'all';
            if (!confirm(`Dismiss ALL visible "${filterLabel}" items?`)) return;
            btnDismissAll.disabled = true;
            try {
                await api('/action-items/batch-dismiss', {
                    method: 'POST',
                    body: { status_filter: COO.actionFilter || '' },
                });
                loadActionItems();
            } catch (e) {
                alert('Error dismissing: ' + e.message);
            }
            btnDismissAll.disabled = false;
        });
    }

    // Modal overlay click
    $$('.modal-overlay').forEach(ov => {
        ov.addEventListener('click', (e) => {
            if (e.target === ov) ov.style.display = 'none';
        });
    });
});
