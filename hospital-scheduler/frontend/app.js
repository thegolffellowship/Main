/**
 * Hospital Staff Scheduler - Frontend Application
 *
 * Single-page app handling:
 * - Employee management (CRUD)
 * - Preference entry (click-to-cycle grid)
 * - Schedule grid display (Day/Night shift tabs, pay period dividers)
 * - Auto-schedule generation with summary panel
 * - Manual cell overrides
 *
 * v2: Add WebSocket for real-time updates, offline support,
 *     drag-and-drop scheduling, print/export functionality.
 */

const API = '';

// ─── State ───
let currentShift = 'Day';
let currentPeriodId = null;
let currentEmployeeId = null;
let pendingPrefs = {};  // date -> code for unsaved preference edits
let lastSummary = null;
let masterViewShift = 'Day';

// ─── Day names ───
const DAY_NAMES = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                     'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// ─── Role display order ───
const ROLE_ORDER = ['ICU RN', 'Floor RN', 'LVN', 'PCT', 'Unit Clerk', 'House Supervisor'];

// ─── Preference cycle ───
const PREF_CYCLE = ['', 'RO', 'PTO', 'X'];
const PREF_CYCLE_PRN = ['', 'RO', 'X'];  // PRN can't use PTO

// ─── Schedule code cycle for manual overrides ───
const SCHED_CYCLE = ['', 'W', 'RO', 'PTO', 'X', 'CI', 'CX', 'LCO', 'LCI', 'E', 'NB', 'SB', 'LD', 'SS', 'PU', 'NC', 'LV', 'TR', 'OD', 'VAC'];
const SCHED_CYCLE_PRN = ['', 'W', 'RO', 'X', 'CI', 'CX', 'LCO', 'LCI', 'E', 'NB', 'SB', 'LD', 'SS', 'PU', 'NC', 'LV', 'TR', 'OD', 'VAC'];

// ─── Note popup state ───
let notePopupEmpId = null;
let notePopupDate = null;
let notePopupCode = null;

// ─── Display helper: A for Day, P for Night ───
function displayScheduleCode(code, shift) {
    if (code === 'W') return shift === 'Day' ? 'A' : 'P';
    return code;
}

// ═══════════════════════════════════════════════
// Initialization
// ═══════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    setupNavigation();
    setupShiftTabs();
    setupEmployeeForm();
    setupPeriodForm();
    setupPreferences();
    setupSummaryTabs();
    setupMasterView();
    setupNotePopup();
    setupClearFilters();
    setupUndoRedo();
    setupSaveAndVersions();
    setupPrintSchedule();
    loadPeriods();
    loadEmployees();
});

// ═══════════════════════════════════════════════
// Navigation
// ═══════════════════════════════════════════════

function setupNavigation() {
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('tab-' + btn.dataset.tab).classList.add('active');

            // Refresh data when switching tabs
            if (btn.dataset.tab === 'employees') loadEmployees();
            if (btn.dataset.tab === 'preferences') loadPrefEmployeeList();
            if (btn.dataset.tab === 'schedule') loadScheduleGrid();
        });
    });
}

// ═══════════════════════════════════════════════
// API Helpers
// ═══════════════════════════════════════════════

async function apiFetch(url, options = {}) {
    try {
        const res = await fetch(API + url, {
            headers: { 'Content-Type': 'application/json', ...options.headers },
            ...options,
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || 'Request failed');
        }
        return res.json();
    } catch (e) {
        showToast(e.message, 'error');
        throw e;
    }
}

// ═══════════════════════════════════════════════
// Toast Notifications
// ═══════════════════════════════════════════════

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

// ═══════════════════════════════════════════════
// Date Helpers
// ═══════════════════════════════════════════════

function formatDateShort(dateStr) {
    const d = new Date(dateStr + 'T00:00:00');
    return `${MONTH_NAMES[d.getMonth()]} ${d.getDate()}`;
}

function getDayName(dateStr) {
    const d = new Date(dateStr + 'T00:00:00');
    return DAY_NAMES[d.getDay()];
}

function isWeekend(dateStr) {
    const d = new Date(dateStr + 'T00:00:00');
    return d.getDay() === 0 || d.getDay() === 6;
}

function generateDates(startDate, count) {
    const dates = [];
    const start = new Date(startDate + 'T00:00:00');
    for (let i = 0; i < count; i++) {
        const d = new Date(start);
        d.setDate(d.getDate() + i);
        dates.push(d.toISOString().split('T')[0]);
    }
    return dates;
}

// ═══════════════════════════════════════════════
// Periods
// ═══════════════════════════════════════════════

async function loadPeriods() {
    const periods = await apiFetch('/api/periods');
    populatePeriodSelects(periods);
    if (periods.length > 0) {
        currentPeriodId = periods[0].id;
    }
}

function populatePeriodSelects(periods) {
    const selects = ['schedule-period-select', 'pref-period-select'];
    selects.forEach(id => {
        const el = document.getElementById(id);
        el.innerHTML = periods.map(p =>
            `<option value="${p.id}">${p.name}</option>`
        ).join('');
        if (periods.length === 0) {
            el.innerHTML = '<option value="">No periods created</option>';
        }

        // Add "create new" option
        el.innerHTML += '<option value="__new__">+ Create New Period</option>';

        el.addEventListener('change', () => {
            if (el.value === '__new__') {
                openModal('period-modal');
                el.value = currentPeriodId || '';
                return;
            }
            currentPeriodId = parseInt(el.value);
            if (id === 'schedule-period-select') loadScheduleGrid();
            if (id === 'pref-period-select') loadPreferenceGrid();
        });
    });

    if (periods.length > 0) {
        currentPeriodId = periods[0].id;
    }
}

function setupPeriodForm() {
    document.getElementById('period-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = document.getElementById('period-name').value;
        const startDate = document.getElementById('period-start').value;

        try {
            await apiFetch('/api/periods', {
                method: 'POST',
                body: JSON.stringify({ name, start_date: startDate }),
            });
            showToast('Period created', 'success');
            closeAllModals();
            await loadPeriods();
        } catch (e) { /* toast already shown */ }
    });
}

// ═══════════════════════════════════════════════
// Employees
// ═══════════════════════════════════════════════

async function loadEmployees() {
    const role = document.getElementById('emp-filter-role').value;
    const shift = document.getElementById('emp-filter-shift').value;
    const type = document.getElementById('emp-filter-type').value;

    let url = '/api/employees?active_only=false';
    if (role) url += `&role=${encodeURIComponent(role)}`;
    if (shift) url += `&shift=${encodeURIComponent(shift)}`;
    if (type) url += `&employment_type=${encodeURIComponent(type)}`;

    const employees = await apiFetch(url);
    renderEmployeeTable(employees);
}

function renderEmployeeTable(employees) {
    const tbody = document.getElementById('employee-tbody');
    if (employees.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No employees found</td></tr>';
        return;
    }

    tbody.innerHTML = employees.map(emp => `
        <tr>
            <td><strong>${escapeHtml(emp.name)}</strong></td>
            <td>${emp.role}</td>
            <td>${emp.shift}</td>
            <td><span class="badge ${emp.employment_type === 'Full-Time' ? 'badge-ft' : 'badge-prn'}">${emp.employment_type}</span></td>
            <td>${emp.prn_tier || '—'}</td>
            <td>${emp.max_weekly_shifts || 3}</td>
            <td><span class="badge ${emp.is_active ? 'badge-active' : 'badge-inactive'}">${emp.is_active ? 'Active' : 'Inactive'}</span></td>
            <td>
                <button class="btn btn-sm btn-secondary" onclick="editEmployee(${emp.id})">Edit</button>
                <button class="btn btn-sm btn-secondary" onclick="pullEmployeeReport(${emp.id}, '${escapeHtml(emp.name)}')">Report</button>
                ${emp.is_active ? `<button class="btn btn-sm btn-danger" onclick="deactivateEmployee(${emp.id}, '${escapeHtml(emp.name)}')">Deactivate</button>` : ''}
            </td>
        </tr>
    `).join('');
}

function setupEmployeeForm() {
    // Filter change listeners
    ['emp-filter-role', 'emp-filter-shift', 'emp-filter-type'].forEach(id => {
        document.getElementById(id).addEventListener('change', loadEmployees);
    });

    // Add employee button
    document.getElementById('btn-add-employee').addEventListener('click', () => {
        document.getElementById('employee-modal-title').textContent = 'Add Employee';
        document.getElementById('employee-form').reset();
        document.getElementById('emp-edit-id').value = '';
        document.getElementById('emp-max-shifts').value = '3';
        document.getElementById('prn-tier-group').style.display = 'none';
        openModal('employee-modal');
    });

    // Toggle PRN tier visibility
    document.getElementById('emp-type').addEventListener('change', (e) => {
        document.getElementById('prn-tier-group').style.display =
            e.target.value === 'PRN' ? 'block' : 'none';
    });

    // Form submit
    document.getElementById('employee-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const editId = document.getElementById('emp-edit-id').value;
        const data = {
            name: document.getElementById('emp-name').value,
            role: document.getElementById('emp-role').value,
            shift: document.getElementById('emp-shift').value,
            employment_type: document.getElementById('emp-type').value,
            max_weekly_shifts: parseInt(document.getElementById('emp-max-shifts').value) || 3,
        };

        if (data.employment_type === 'PRN') {
            data.prn_tier = document.getElementById('emp-prn-tier').value;
        } else {
            data.prn_tier = null;
        }

        try {
            if (editId) {
                await apiFetch(`/api/employees/${editId}`, {
                    method: 'PUT',
                    body: JSON.stringify(data),
                });
                showToast('Employee updated', 'success');
            } else {
                await apiFetch('/api/employees', {
                    method: 'POST',
                    body: JSON.stringify(data),
                });
                showToast('Employee added', 'success');
            }
            closeAllModals();
            loadEmployees();
        } catch (e) { /* toast already shown */ }
    });
}

async function editEmployee(id) {
    const emp = await apiFetch(`/api/employees/${id}`);
    document.getElementById('employee-modal-title').textContent = 'Edit Employee';
    document.getElementById('emp-edit-id').value = emp.id;
    document.getElementById('emp-name').value = emp.name;
    document.getElementById('emp-role').value = emp.role;
    document.getElementById('emp-shift').value = emp.shift;
    document.getElementById('emp-type').value = emp.employment_type;

    document.getElementById('emp-max-shifts').value = emp.max_weekly_shifts || 3;

    if (emp.employment_type === 'PRN') {
        document.getElementById('prn-tier-group').style.display = 'block';
        document.getElementById('emp-prn-tier').value = emp.prn_tier || 'Tier 1';
    } else {
        document.getElementById('prn-tier-group').style.display = 'none';
    }

    openModal('employee-modal');
}

async function deactivateEmployee(id, name) {
    if (!confirm(`Deactivate ${name}? They will be excluded from future schedules.`)) return;
    try {
        await apiFetch(`/api/employees/${id}`, { method: 'DELETE' });
        showToast(`${name} deactivated`, 'success');
        loadEmployees();
    } catch (e) { /* toast already shown */ }
}

// ═══════════════════════════════════════════════
// Preferences
// ═══════════════════════════════════════════════

function setupPreferences() {
    document.getElementById('pref-employee-select').addEventListener('change', (e) => {
        currentEmployeeId = e.target.value ? parseInt(e.target.value) : null;
        if (currentEmployeeId) {
            document.getElementById('btn-save-prefs').disabled = false;
            loadPreferenceGrid();
        } else {
            document.getElementById('btn-save-prefs').disabled = true;
            document.getElementById('pref-grid-container').innerHTML =
                '<p class="empty-state">Select an employee to enter preferences.</p>';
        }
    });

    document.getElementById('btn-save-prefs').addEventListener('click', savePreferences);
}

async function loadPrefEmployeeList() {
    const employees = await apiFetch('/api/employees');
    const select = document.getElementById('pref-employee-select');
    select.innerHTML = '<option value="">-- Select Employee --</option>';
    select.innerHTML += employees.map(emp =>
        `<option value="${emp.id}">${emp.name} (${emp.role}, ${emp.shift})</option>`
    ).join('');
}

async function loadPreferenceGrid() {
    if (!currentPeriodId || !currentEmployeeId) return;

    const [period, prefs, emp] = await Promise.all([
        apiFetch(`/api/periods/${currentPeriodId}`),
        apiFetch(`/api/preferences/${currentPeriodId}/${currentEmployeeId}`),
        apiFetch(`/api/employees/${currentEmployeeId}`),
    ]);

    pendingPrefs = { ...prefs };
    const dates = generateDates(period.start_date, 42);
    const isPRN = emp.employment_type === 'PRN';

    renderPrefGrid(dates, isPRN);
}

function renderPrefGrid(dates, isPRN) {
    const container = document.getElementById('pref-grid-container');
    let html = '<table class="schedule-grid"><thead>';

    // Header row: all 42 dates in columns (same format as schedule grid)
    html += '<tr><th class="name-col">Preferences</th>';
    for (let i = 0; i < 42; i++) {
        const d = dates[i];
        const weekend = isWeekend(d) ? ' weekend-col' : '';
        const payDivider = (i > 0 && i % 14 === 0) ? ' pay-divider' : '';
        html += `<th class="${weekend}${payDivider}"><span class="header-day">${getDayName(d)}</span><br><span class="header-date">${formatDateShort(d)}</span></th>`;
    }
    html += '</tr></thead><tbody>';

    // Single row with all 42 dates
    html += '<tr><td class="name-col" style="font-weight:600">Click to set</td>';
    for (let i = 0; i < 42; i++) {
        const dateStr = dates[i];
        const code = pendingPrefs[dateStr] || '';
        const cellClass = code ? `cell-${code}` : 'cell-off';
        const weekend = isWeekend(dateStr) ? ' weekend-col' : '';
        const payDivider = (i > 0 && i % 14 === 0) ? ' pay-divider' : '';
        html += `<td class="pref-cell ${cellClass}${weekend}${payDivider}" data-date="${dateStr}" data-prn="${isPRN}">${code}</td>`;
    }
    html += '</tr>';

    html += '</tbody></table>';
    container.innerHTML = html;

    // Click-to-cycle handlers
    container.querySelectorAll('.pref-cell').forEach(cell => {
        cell.addEventListener('click', () => {
            const dateStr = cell.dataset.date;
            const isPRNCell = cell.dataset.prn === 'true';
            const cycle = isPRNCell ? PREF_CYCLE_PRN : PREF_CYCLE;
            const current = pendingPrefs[dateStr] || '';
            const nextIdx = (cycle.indexOf(current) + 1) % cycle.length;
            const nextCode = cycle[nextIdx];

            pendingPrefs[dateStr] = nextCode;
            cell.textContent = nextCode;
            cell.className = `pref-cell ${nextCode ? 'cell-' + nextCode : 'cell-off'}${isWeekend(dateStr) ? ' weekend-col' : ''}`;
        });
    });
}

async function savePreferences() {
    if (!currentPeriodId || !currentEmployeeId) return;

    try {
        await apiFetch('/api/preferences', {
            method: 'POST',
            body: JSON.stringify({
                employee_id: currentEmployeeId,
                period_id: currentPeriodId,
                preferences: pendingPrefs,
            }),
        });
        showToast('Preferences saved', 'success');
    } catch (e) { /* toast already shown */ }
}

// ─── Master View ───

function setupMasterView() {
    document.getElementById('btn-master-view').addEventListener('click', () => {
        openModal('master-view-modal');
        loadMasterView();
    });

    document.querySelectorAll('.master-shift-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.master-shift-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            masterViewShift = btn.dataset.shift;
            loadMasterView();
        });
    });
}

async function loadMasterView() {
    if (!currentPeriodId) return;

    const [period, allPrefs, employees] = await Promise.all([
        apiFetch(`/api/periods/${currentPeriodId}`),
        apiFetch(`/api/preferences/${currentPeriodId}`),
        apiFetch('/api/employees'),
    ]);

    const dates = generateDates(period.start_date, 42);
    const shiftEmps = employees.filter(e => e.shift === masterViewShift);

    // Sort by role order then name
    shiftEmps.sort((a, b) => {
        const ra = ROLE_ORDER.indexOf(a.role);
        const rb = ROLE_ORDER.indexOf(b.role);
        if (ra !== rb) return ra - rb;
        return a.name.localeCompare(b.name);
    });

    const container = document.getElementById('master-grid-container');
    let html = '<table class="schedule-grid"><thead>';

    // Header row
    html += '<tr><th class="name-col">Employee</th>';
    for (let i = 0; i < 42; i++) {
        const d = dates[i];
        const weekend = isWeekend(d) ? ' weekend-col' : '';
        const payDivider = (i > 0 && i % 14 === 0) ? ' pay-divider' : '';
        html += `<th class="${weekend}${payDivider}"><span class="header-day">${getDayName(d)}</span><br><span class="header-date">${formatDateShort(d)}</span></th>`;
    }
    html += '</tr></thead><tbody>';

    let lastRole = '';
    for (const emp of shiftEmps) {
        // Role group header
        if (emp.role !== lastRole) {
            lastRole = emp.role;
            html += `<tr class="role-header"><td colspan="${43}">${emp.role}s</td></tr>`;
        }

        const empPrefs = allPrefs[String(emp.id)] || {};
        const isPRN = emp.employment_type === 'PRN';
        html += `<tr><td class="name-col">${escapeHtml(emp.name)}</td>`;
        for (let i = 0; i < 42; i++) {
            const d = dates[i];
            const code = empPrefs[d] || '';
            const cellClass = code ? `cell-${code}` : 'cell-off';
            const weekend = isWeekend(d) ? ' weekend-col' : '';
            const payDivider = (i > 0 && i % 14 === 0) ? ' pay-divider' : '';
            html += `<td class="master-pref-cell ${cellClass}${weekend}${payDivider}" data-emp="${emp.id}" data-date="${d}" data-prn="${isPRN}">${code}</td>`;
        }
        html += '</tr>';
    }

    html += '</tbody></table>';
    container.innerHTML = html;

    // Make master view editable: click to cycle preference codes
    container.querySelectorAll('.master-pref-cell').forEach(cell => {
        cell.style.cursor = 'pointer';
        cell.addEventListener('click', async () => {
            const empId = parseInt(cell.dataset.emp);
            const dateStr = cell.dataset.date;
            const isPRN = cell.dataset.prn === 'true';
            const cycle = isPRN ? PREF_CYCLE_PRN : PREF_CYCLE;
            const currentCode = cell.textContent.trim();
            const nextIdx = (cycle.indexOf(currentCode) + 1) % cycle.length;
            const nextCode = cycle[nextIdx];

            // Update via API (send full preference set for this employee)
            const existingPrefs = allPrefs[String(empId)] || {};
            existingPrefs[dateStr] = nextCode;

            try {
                await apiFetch('/api/preferences', {
                    method: 'POST',
                    body: JSON.stringify({
                        employee_id: empId,
                        period_id: currentPeriodId,
                        preferences: existingPrefs,
                    }),
                });

                // Update cell display
                cell.textContent = nextCode;
                cell.className = `master-pref-cell ${nextCode ? 'cell-' + nextCode : 'cell-off'}${isWeekend(dateStr) ? ' weekend-col' : ''}`;
                allPrefs[String(empId)] = existingPrefs;
            } catch (e) { /* toast shown */ }
        });
    });
}

// ═══════════════════════════════════════════════
// Schedule Grid
// ═══════════════════════════════════════════════

function setupShiftTabs() {
    document.querySelectorAll('.shift-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.shift-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentShift = btn.dataset.shift;
            loadScheduleGrid();
        });
    });

    document.getElementById('btn-generate').addEventListener('click', generateSchedule);
}

async function loadScheduleGrid() {
    if (!currentPeriodId) return;

    const [schedData, dailySummary] = await Promise.all([
        apiFetch(`/api/schedule/${currentPeriodId}?shift=${currentShift}`),
        apiFetch(`/api/schedule/${currentPeriodId}/daily-summary`).catch(() => []),
    ]);

    renderScheduleGrid(schedData, dailySummary);
}

function renderScheduleGrid(schedData, dailySummary) {
    const container = document.getElementById('schedule-grid-container');
    const { period, employees, grid } = schedData;

    if (!period || employees.length === 0) {
        container.innerHTML = '<p class="empty-state">No employees found for this shift. Add employees first.</p>';
        return;
    }

    const dates = generateDates(period.start_date, 42);

    // Build daily summary lookup
    const dailyLookup = {};
    (dailySummary || []).forEach(ds => {
        dailyLookup[ds.date + '_' + ds.shift] = ds;
    });

    let html = '<table class="schedule-grid"><thead>';

    // Header row
    html += '<tr><th class="name-col">Employee</th>';
    for (let i = 0; i < 42; i++) {
        const d = dates[i];
        const weekend = isWeekend(d) ? ' weekend-col' : '';
        const payDivider = (i > 0 && i % 14 === 0) ? ' pay-divider' : '';
        html += `<th class="${weekend}${payDivider}"><span class="header-day">${getDayName(d)}</span><br><span class="header-date">${formatDateShort(d)}</span></th>`;
    }
    html += '<th style="min-width:50px">Total</th></tr></thead><tbody>';

    let lastRole = '';
    let roleEmployees = [];

    // Group employees by role for totals rows
    const roleGroups = {};
    for (const emp of employees) {
        if (!roleGroups[emp.role]) roleGroups[emp.role] = [];
        roleGroups[emp.role].push(emp);
    }

    for (const role of ROLE_ORDER) {
        const emps = roleGroups[role];
        if (!emps || emps.length === 0) continue;

        // Role group header
        html += `<tr class="role-header"><td class="name-col" style="background:#e9ecef">${role}s</td>`;
        for (let i = 0; i < 42; i++) {
            const payDivider = (i > 0 && i % 14 === 0) ? ' pay-divider' : '';
            html += `<td style="background:#e9ecef" class="${payDivider}"></td>`;
        }
        html += '<td style="background:#e9ecef"></td></tr>';

        // Employee rows
        for (const emp of emps) {
            const empGrid = grid[String(emp.id)] || {};
            let totalShifts = 0;

            html += `<tr><td class="name-col" title="${emp.employment_type}${emp.prn_tier ? ' - ' + emp.prn_tier : ''}">${escapeHtml(emp.name)}`;
            if (emp.employment_type === 'PRN') html += ' <small style="color:#664d03">(PRN)</small>';
            html += '</td>';

            for (let i = 0; i < 42; i++) {
                const d = dates[i];
                const entry = empGrid[d];
                const code = entry ? entry.code : '';
                const note = entry ? (entry.note || '') : '';
                const isOverride = entry ? entry.is_manual_override : false;

                if (code === 'W' || code === 'RO') totalShifts++;

                const cellClass = code ? `cell-${code}` : 'cell-off';
                const overrideClass = isOverride ? ' cell-override' : '';
                const noteClass = note ? ' has-note' : '';
                const weekend = isWeekend(d) ? ' weekend-col' : '';
                const payDivider = (i > 0 && i % 14 === 0) ? ' pay-divider' : '';
                const displayCode = code === 'W' ? (currentShift === 'Day' ? 'A' : 'P') : code;
                const tooltip = note ? ` title="${escapeHtml(note)}"` : '';

                html += `<td class="schedule-cell ${cellClass}${overrideClass}${noteClass}${weekend}${payDivider}" `
                    + `data-emp="${emp.id}" data-date="${d}" data-code="${code}" data-note="${escapeHtml(note)}" `
                    + `data-type="${emp.employment_type}" data-shift="${emp.shift}"${tooltip}>`
                    + `${displayCode}</td>`;
            }

            html += `<td style="font-weight:600;text-align:center">${totalShifts}</td></tr>`;
        }

        // Totals row for this role group
        html += `<tr class="totals-row"><td class="name-col" style="background:#f8f9fa;font-size:11px">${role} Count</td>`;
        for (let i = 0; i < 42; i++) {
            const d = dates[i];
            let count = 0;
            for (const emp of emps) {
                const entry = (grid[String(emp.id)] || {})[d];
                if (entry && (entry.code === 'W' || entry.code === 'RO')) count++;
            }

            // Check if this day is flagged for this role
            const ds = dailyLookup[d + '_' + currentShift];
            let flagged = false;
            if (ds && ds.is_below_minimum) {
                if (role === 'ICU RN' && ds.icu_rn_count < 3) flagged = true;
                if ((role === 'Floor RN' || role === 'LVN') && ds.nurse_total < 7) flagged = true;
                if (role === 'PCT' && ds.pct_count < 3) flagged = true;
                if (role === 'Unit Clerk') {
                    const min = currentShift === 'Day' ? 2 : 1;
                    if (ds.unit_clerk_count < min) flagged = true;
                }
                if (role === 'House Supervisor' && ds.house_supervisor_count < 1) flagged = true;
            }

            const payDivider = (i > 0 && i % 14 === 0) ? ' pay-divider' : '';
            html += `<td class="${flagged ? 'flagged' : ''}${payDivider}" title="${flagged && ds ? ds.flags.join(', ') : ''}">${count}</td>`;
        }
        html += '<td></td></tr>';
    }

    html += '</tbody></table>';
    container.innerHTML = html;

    // Click handlers for manual overrides (left-click cycles code)
    container.querySelectorAll('.schedule-cell').forEach(cell => {
        cell.addEventListener('click', () => {
            const empId = cell.dataset.emp;
            const dateStr = cell.dataset.date;
            const currentCode = cell.dataset.code;
            const empType = cell.dataset.type;

            // Determine available codes (includes CI and CX)
            let cycle = SCHED_CYCLE_PRN;
            if (empType === 'Full-Time') cycle = SCHED_CYCLE;

            const nextIdx = (cycle.indexOf(currentCode) + 1) % cycle.length;
            const nextCode = cycle[nextIdx];

            // Update via API
            updateScheduleCell(empId, dateStr, nextCode, cell);
        });

        // Right-click opens note popup
        cell.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            openNotePopup(cell, e);
        });
    });
}

async function updateScheduleCell(empId, dateStr, code, cell) {
    try {
        await apiFetch(`/api/schedule/${currentPeriodId}/${empId}/${dateStr}`, {
            method: 'PUT',
            body: JSON.stringify({ code }),
        });

        // Update cell display
        const empShift = cell.dataset.shift || currentShift;
        const display = code === 'W' ? (empShift === 'Day' ? 'A' : 'P') : code;
        cell.dataset.code = code;
        cell.textContent = display;
        cell.className = cell.className.replace(/cell-\S+/g, '').trim();
        cell.classList.add('schedule-cell');
        if (code) cell.classList.add(`cell-${code}`);
        else cell.classList.add('cell-off');
        cell.classList.add('cell-override');
        if (cell.dataset.note) cell.classList.add('has-note');

        // Preserve weekend/pay-divider classes
        if (isWeekend(dateStr)) cell.classList.add('weekend-col');
    } catch (e) { /* toast already shown */ }
}

// ═══════════════════════════════════════════════
// Schedule Generation
// ═══════════════════════════════════════════════

async function generateSchedule() {
    if (!currentPeriodId) {
        showToast('Select a schedule period first', 'error');
        return;
    }

    const confirmed = confirm(
        'Generate schedule for the selected period?\n\n' +
        'This will overwrite any existing schedule entries (including manual edits).'
    );
    if (!confirmed) return;

    const btn = document.getElementById('btn-generate');
    btn.disabled = true;
    btn.textContent = 'Generating...';

    try {
        lastSummary = await apiFetch(`/api/schedule/${currentPeriodId}/generate`, {
            method: 'POST',
        });

        showToast('Schedule generated successfully', 'success');
        loadScheduleGrid();
        showSummaryPanel(lastSummary);
    } catch (e) {
        /* toast already shown */
    } finally {
        btn.disabled = false;
        btn.textContent = 'Generate Schedule';
    }
}

// ═══════════════════════════════════════════════
// Summary Panel
// ═══════════════════════════════════════════════

function setupSummaryTabs() {
    document.querySelectorAll('.summary-tab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.summary-tab').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            if (lastSummary) renderSummaryContent(btn.dataset.summary);
        });
    });
}

function showSummaryPanel(summary) {
    const panel = document.getElementById('summary-panel');
    panel.classList.remove('hidden');
    renderSummaryContent('flags');
}

function renderSummaryContent(tab) {
    const container = document.getElementById('summary-content');

    if (tab === 'flags') {
        const days = lastSummary.understaffed_days || [];
        if (days.length === 0) {
            container.innerHTML = '<p style="color:#198754;padding:16px">All daily minimums met. No flags.</p>';
            return;
        }

        let html = `<p style="margin-bottom:12px">Understaffed days: <span class="flag-count">${days.length}</span></p>`;
        html += '<table class="summary-table"><thead><tr><th>Date</th><th>Shift</th><th>Issues</th></tr></thead><tbody>';
        for (const day of days) {
            html += `<tr class="danger"><td>${day.date}</td><td>${day.shift}</td><td>${day.flags.join('; ')}</td></tr>`;
        }
        html += '</tbody></table>';
        container.innerHTML = html;
    }

    if (tab === 'employees') {
        const emps = lastSummary.employee_summaries || [];
        let html = '<table class="summary-table"><thead><tr><th>Name</th><th>Role</th><th>Shift</th><th>Type</th><th>Shifts</th><th>Weeks Met</th><th>Weeks Short</th><th>RO Overrides</th><th>Status</th></tr></thead><tbody>';
        for (const emp of emps) {
            const cls = emp.meets_minimum ? '' : ' class="warning"';
            html += `<tr${cls}><td>${escapeHtml(emp.employee_name)}</td><td>${emp.role}</td><td>${emp.shift}</td><td>${emp.employment_type}</td>`;
            html += `<td>${emp.total_shifts}</td><td>${emp.weeks_meeting_requirement}</td><td>${emp.weeks_short}</td><td>${emp.ro_overrides}</td>`;
            html += `<td>${emp.meets_minimum ? '<span class="badge badge-active">OK</span>' : '<span class="badge badge-inactive">Short</span>'}</td></tr>`;
        }
        html += '</tbody></table>';
        container.innerHTML = html;
    }

    if (tab === 'overrides') {
        const overrides = lastSummary.ro_overrides || [];
        if (overrides.length === 0) {
            container.innerHTML = '<p style="color:#198754;padding:16px">No request-off overrides were needed.</p>';
            return;
        }

        let html = `<p style="margin-bottom:12px">RO Overrides: <span class="flag-count">${overrides.length}</span></p>`;
        html += '<table class="summary-table"><thead><tr><th>Employee</th><th>Date</th><th>Reason</th></tr></thead><tbody>';
        for (const o of overrides) {
            html += `<tr class="warning"><td>${escapeHtml(o.employee_name)}</td><td>${o.date}</td><td>${o.reason}</td></tr>`;
        }
        html += '</tbody></table>';
        container.innerHTML = html;
    }
}

// ═══════════════════════════════════════════════
// Note Popup
// ═══════════════════════════════════════════════

function setupNotePopup() {
    document.getElementById('note-popup-save').addEventListener('click', saveNote);
    document.getElementById('note-popup-clear').addEventListener('click', () => {
        document.getElementById('note-popup-text').value = '';
        saveNote();
    });
    document.getElementById('note-popup-close').addEventListener('click', closeNotePopup);

    // Close popup on click outside
    document.addEventListener('click', (e) => {
        const popup = document.getElementById('note-popup');
        if (!popup.classList.contains('hidden') && !popup.contains(e.target)) {
            closeNotePopup();
        }
    });
}

function openNotePopup(cell, event) {
    notePopupEmpId = cell.dataset.emp;
    notePopupDate = cell.dataset.date;
    notePopupCode = cell.dataset.code;

    const popup = document.getElementById('note-popup');
    document.getElementById('note-popup-text').value = cell.dataset.note || '';

    // Position near the cell
    const rect = cell.getBoundingClientRect();
    popup.style.top = (rect.bottom + window.scrollY + 4) + 'px';
    popup.style.left = Math.min(rect.left + window.scrollX, window.innerWidth - 280) + 'px';
    popup.classList.remove('hidden');

    document.getElementById('note-popup-text').focus();
}

function closeNotePopup() {
    document.getElementById('note-popup').classList.add('hidden');
    notePopupEmpId = null;
    notePopupDate = null;
    notePopupCode = null;
}

async function saveNote() {
    if (!notePopupEmpId || !notePopupDate || !currentPeriodId) return;

    const note = document.getElementById('note-popup-text').value.trim();
    const code = notePopupCode || '';

    try {
        await apiFetch(`/api/schedule/${currentPeriodId}/${notePopupEmpId}/${notePopupDate}`, {
            method: 'PUT',
            body: JSON.stringify({ code, note }),
        });

        // Update the cell's note data and indicator
        const cell = document.querySelector(
            `.schedule-cell[data-emp="${notePopupEmpId}"][data-date="${notePopupDate}"]`
        );
        if (cell) {
            cell.dataset.note = note;
            cell.title = note;
            if (note) {
                cell.classList.add('has-note');
            } else {
                cell.classList.remove('has-note');
            }
        }

        showToast(note ? 'Note saved' : 'Note cleared', 'success');
        closeNotePopup();
    } catch (e) { /* toast already shown */ }
}

// ═══════════════════════════════════════════════
// Clear Filters
// ═══════════════════════════════════════════════

function setupClearFilters() {
    document.getElementById('btn-clear-filters').addEventListener('click', () => {
        document.getElementById('emp-filter-role').value = '';
        document.getElementById('emp-filter-shift').value = '';
        document.getElementById('emp-filter-type').value = '';
        loadEmployees();
    });
}

// ═══════════════════════════════════════════════
// Modal Helpers
// ═══════════════════════════════════════════════

function openModal(id) {
    document.getElementById(id).classList.remove('hidden');
}

function closeAllModals() {
    document.querySelectorAll('.modal').forEach(m => m.classList.add('hidden'));
}

// Close modals on backdrop click or close button
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) closeAllModals();
    if (e.target.classList.contains('modal-close')) closeAllModals();
});

// ═══════════════════════════════════════════════
// Utility
// ═══════════════════════════════════════════════

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// ═══════════════════════════════════════════════
// Undo / Redo
// ═══════════════════════════════════════════════

function setupUndoRedo() {
    const btnUndo = document.getElementById('btn-undo');
    const btnRedo = document.getElementById('btn-redo');

    btnUndo.addEventListener('click', async () => {
        if (!currentPeriodId) return;
        try {
            const result = await apiFetch(`/api/schedule/${currentPeriodId}/undo`, { method: 'POST' });
            showToast('Undone', 'success');
            loadScheduleGrid();
        } catch (e) { /* toast already shown */ }
    });

    btnRedo.addEventListener('click', async () => {
        if (!currentPeriodId) return;
        try {
            const result = await apiFetch(`/api/schedule/${currentPeriodId}/redo`, { method: 'POST' });
            showToast('Redone', 'success');
            loadScheduleGrid();
        } catch (e) { /* toast already shown */ }
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'z' && !e.shiftKey) {
            e.preventDefault();
            btnUndo.click();
        }
        if (e.ctrlKey && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
            e.preventDefault();
            btnRedo.click();
        }
    });
}

// ═══════════════════════════════════════════════
// Save & Versions
// ═══════════════════════════════════════════════

function setupSaveAndVersions() {
    document.getElementById('btn-save-schedule').addEventListener('click', async () => {
        if (!currentPeriodId) {
            showToast('Select a period first', 'error');
            return;
        }
        const label = prompt('Enter a label for this version (optional):') || '';
        try {
            const result = await apiFetch(`/api/schedule/${currentPeriodId}/save?label=${encodeURIComponent(label)}`, {
                method: 'POST',
            });
            showToast(`Schedule saved as ${result.label}`, 'success');
        } catch (e) { /* toast already shown */ }
    });

    document.getElementById('btn-versions').addEventListener('click', async () => {
        if (!currentPeriodId) {
            showToast('Select a period first', 'error');
            return;
        }
        await loadVersionsList();
        openModal('versions-modal');
    });
}

async function loadVersionsList() {
    const versions = await apiFetch(`/api/schedule/${currentPeriodId}/versions`);
    const container = document.getElementById('versions-list');

    if (versions.length === 0) {
        container.innerHTML = '<p class="empty-state">No saved versions yet.</p>';
        return;
    }

    container.innerHTML = versions.map(v => `
        <div class="version-item">
            <div class="version-info">
                <div class="version-label">v${v.version_number} — ${escapeHtml(v.label || 'Untitled')}</div>
                <div class="version-date">${v.created_at ? new Date(v.created_at).toLocaleString() : ''}</div>
            </div>
            <button class="btn btn-sm btn-secondary" onclick="restoreVersion(${v.id})">Restore</button>
        </div>
    `).join('');
}

async function restoreVersion(versionId) {
    if (!confirm('Restore this version? Your current schedule will be auto-saved first.')) return;
    try {
        const result = await apiFetch(`/api/schedule/${currentPeriodId}/versions/${versionId}/restore`, {
            method: 'POST',
        });
        showToast(result.message, 'success');
        closeAllModals();
        loadScheduleGrid();
    } catch (e) { /* toast already shown */ }
}

// ═══════════════════════════════════════════════
// Print Schedule
// ═══════════════════════════════════════════════

function setupPrintSchedule() {
    document.getElementById('btn-print-schedule').addEventListener('click', () => {
        window.print();
    });

    // Print button in report modal
    document.getElementById('btn-print-report').addEventListener('click', () => {
        // Show only the report modal for printing
        document.getElementById('report-modal').classList.remove('hidden');
        window.print();
    });
}

// ═══════════════════════════════════════════════
// Employee Report
// ═══════════════════════════════════════════════

async function pullEmployeeReport(employeeId, employeeName) {
    if (!currentPeriodId) {
        // Use the first available period
        const schedSelect = document.getElementById('schedule-period-select');
        if (schedSelect.value && schedSelect.value !== '__new__') {
            currentPeriodId = parseInt(schedSelect.value);
        } else {
            showToast('Select a schedule period first', 'error');
            return;
        }
    }

    try {
        const report = await apiFetch(`/api/report/employee/${employeeId}/${currentPeriodId}`);
        renderEmployeeReport(report);
        document.getElementById('report-modal-title').textContent = `Report: ${employeeName}`;
        openModal('report-modal');
    } catch (e) { /* toast already shown */ }
}

function renderEmployeeReport(report) {
    const container = document.getElementById('report-content');
    const emp = report.employee;
    const period = report.period;

    let html = '';

    // Employee info header
    html += `<div class="report-section">
        <p><strong>${escapeHtml(emp.name)}</strong> — ${emp.role}, ${emp.shift} Shift, ${emp.employment_type}</p>
        <p style="color:var(--text-secondary);font-size:12px">Period: ${period.name} (${period.start_date} to ${period.end_date})</p>
    </div>`;

    // Summary stats
    html += `<div class="report-section">
        <h4>Summary</h4>
        <div class="report-stats">
            <div class="report-stat"><div class="report-stat-value">${report.total_shifts_worked}</div><div class="report-stat-label">Shifts Worked</div></div>`;

    const codeCounts = report.code_counts || {};
    for (const [code, count] of Object.entries(codeCounts)) {
        if (code && count > 0) {
            const label = code === 'W' ? 'Working' : code === 'RO' ? 'RO Override' : code === 'PTO' ? 'PTO' :
                code === 'CI' ? 'Called In' : code === 'CX' ? 'Canceled' : code === 'LCO' ? 'Late Clock Off' :
                code === 'LCI' ? 'Late Clock In' : code === 'E' ? 'Early Clock In' : code === 'NB' ? 'No Lunch Break' :
                code === 'SB' ? 'Short Break' : code === 'X' ? 'Cannot Work' :
                code === 'LD' ? 'Lite Duty' : code === 'SS' ? 'Switched Shifts' : code === 'PU' ? 'Picked Up' :
                code === 'NC' ? 'Needs Clarification' : code === 'LV' ? 'Leave' : code === 'TR' ? 'Transferred' :
                code === 'OD' ? 'Other Dept' : code === 'VAC' ? 'Vacation' : code;
            html += `<div class="report-stat"><div class="report-stat-value">${count}</div><div class="report-stat-label">${label}</div></div>`;
        }
    }
    html += `</div></div>`;

    // Weekly breakdown
    html += `<div class="report-section"><h4>Weekly Breakdown</h4>`;
    html += `<table class="summary-table"><thead><tr>
        <th>Week</th><th>Dates</th><th>Shifts</th><th>Call-Ins</th><th>Late Off</th><th>Late In</th>
    </tr></thead><tbody>`;
    for (const w of report.weekly_breakdown) {
        html += `<tr><td>Week ${w.week}</td><td>${w.start_date} — ${w.end_date}</td>
            <td>${w.shifts_worked}</td><td>${w.call_ins}</td><td>${w.late_clock_offs}</td><td>${w.late_clock_ins}</td></tr>`;
    }
    html += '</tbody></table></div>';

    // Daily detail
    html += `<div class="report-section"><h4>Daily Detail</h4>`;
    html += `<table class="summary-table"><thead><tr><th>Date</th><th>Day</th><th>Code</th><th>Note</th></tr></thead><tbody>`;
    for (const d of report.daily_detail) {
        const cls = d.code ? ` class="cell-${d.code}"` : '';
        html += `<tr><td>${d.date}</td><td>${d.day}</td><td${cls} style="text-align:center;font-weight:600">${d.code || '—'}</td><td>${escapeHtml(d.note || '')}</td></tr>`;
    }
    html += '</tbody></table></div>';

    container.innerHTML = html;
}
