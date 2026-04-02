/* =========================================================
   Accounting Module — Core State & Utilities
   ========================================================= */

const ACCT = {
    entities: [],
    accounts: [],
    categories: [],
    tags: [],
    activeEntity: null,   // null = "All"
    activeTab: 'dashboard',
    txnPage: 0,
    txnLimit: 50,
    csvData: null,
};

function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }

function fmt(n) {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n || 0);
}

async function api(path, opts = {}) {
    const url = '/api/accounting' + path;
    if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
        opts.headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
        opts.body = JSON.stringify(opts.body);
    }
    const res = await fetch(url, opts);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(err.error || 'Request failed');
    }
    return res.json();
}

function getDateRange(preset) {
    const now = new Date();
    const y = now.getFullYear(), m = now.getMonth();
    switch (preset) {
        case 'this_month':
            return { start: `${y}-${String(m+1).padStart(2,'0')}-01`, end: null };
        case 'last_month': {
            const lm = m === 0 ? 11 : m - 1;
            const ly = m === 0 ? y - 1 : y;
            const last = new Date(ly, lm + 1, 0).getDate();
            return { start: `${ly}-${String(lm+1).padStart(2,'0')}-01`,
                     end: `${ly}-${String(lm+1).padStart(2,'0')}-${last}` };
        }
        case 'this_quarter': {
            const qs = Math.floor(m / 3) * 3;
            return { start: `${y}-${String(qs+1).padStart(2,'0')}-01`, end: null };
        }
        case 'this_year':
            return { start: `${y}-01-01`, end: null };
        case 'last_year':
            return { start: `${y-1}-01-01`, end: `${y-1}-12-31` };
        case 'all':
            return { start: null, end: null };
        default:
            return { start: null, end: null };
    }
}

function buildQS(params) {
    const p = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
        if (v != null && v !== '') p.set(k, v);
    }
    return p.toString() ? '?' + p.toString() : '';
}

function entityColor(id) {
    const e = ACCT.entities.find(x => x.id === id);
    return e ? e.color : '#6b7280';
}

function entityName(id) {
    const e = ACCT.entities.find(x => x.id === id);
    return e ? e.short_name : '—';
}
