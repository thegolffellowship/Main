/**
 * PAM Health Nurse Scheduler — Nurses Page
 */

(function () {
    let deleteTargetId = null;

    function init() {
        UI.initSidebar();
        renderNurses();

        // Add nurse button
        document.getElementById('addNurseBtn').addEventListener('click', () => openNurseModal());

        // Modal controls
        document.getElementById('closeModal').addEventListener('click', () => UI.closeModal('nurseModal'));
        document.getElementById('cancelBtn').addEventListener('click', () => UI.closeModal('nurseModal'));
        document.getElementById('cancelDeleteBtn').addEventListener('click', () => UI.closeModal('deleteModal'));

        // Form submission
        document.getElementById('nurseForm').addEventListener('submit', handleSaveNurse);

        // Delete confirmation
        document.getElementById('confirmDeleteBtn').addEventListener('click', handleDeleteNurse);

        // Filters
        document.getElementById('searchInput').addEventListener('input', renderNurses);
        document.getElementById('roleFilter').addEventListener('change', renderNurses);
        document.getElementById('statusFilter').addEventListener('change', renderNurses);

        // Close modals on overlay click
        document.querySelectorAll('.modal-overlay').forEach(overlay => {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) overlay.classList.remove('active');
            });
        });
    }

    function getFilteredNurses() {
        let nurses = Store.getNurses();
        const search = document.getElementById('searchInput').value.toLowerCase();
        const role = document.getElementById('roleFilter').value;
        const status = document.getElementById('statusFilter').value;

        if (search) {
            nurses = nurses.filter(n =>
                `${n.firstName} ${n.lastName}`.toLowerCase().includes(search)
            );
        }
        if (role) {
            nurses = nurses.filter(n => n.role === role);
        }
        if (status) {
            nurses = nurses.filter(n => n.status === status);
        }

        return nurses;
    }

    function renderNurses() {
        const nurses = getFilteredNurses();
        const grid = document.getElementById('nursesGrid');

        if (nurses.length === 0) {
            grid.innerHTML = '<div class="empty-state" style="grid-column: 1/-1; padding: 60px 0;">No nurses found. Click "+ Add Nurse" to get started.</div>';
            return;
        }

        grid.innerHTML = '';
        nurses.forEach(nurse => {
            const card = document.createElement('div');
            card.className = 'nurse-card';

            const shiftsThisWeek = getWeekShiftCount(nurse.id);
            const prefLabel = nurse.shiftPreference === 'day' ? 'Day' :
                              nurse.shiftPreference === 'night' ? 'Night' : 'Any';

            card.innerHTML = `
                <div class="nurse-card-header">
                    <div class="nurse-card-avatar ${UI.getAvatarClass(nurse.role)}">${UI.getInitials(nurse.firstName, nurse.lastName)}</div>
                    <div>
                        <div class="nurse-card-name">${nurse.firstName} ${nurse.lastName}</div>
                        <div class="nurse-card-role">${nurse.role} <span class="status-badge ${nurse.status === 'active' ? 'status-active' : 'status-inactive'}">${nurse.status}</span></div>
                    </div>
                </div>
                <div class="nurse-card-details">
                    <div>
                        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.127.96.361 1.903.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.907.339 1.85.573 2.81.7A2 2 0 0 1 22 16.92z"/>
                        </svg>
                        ${nurse.phone || 'No phone'}
                    </div>
                    <div>
                        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                            <polyline points="22,6 12,13 2,6"/>
                        </svg>
                        ${nurse.email || 'No email'}
                    </div>
                    <div>
                        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>
                        </svg>
                        Prefers: ${prefLabel} shift &bull; Max ${nurse.maxHours || 36}h/wk
                    </div>
                    <div>
                        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                            <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
                        </svg>
                        ${shiftsThisWeek} shifts this week
                    </div>
                    ${nurse.notes ? `<div style="font-style: italic; color: var(--gray-500);">${nurse.notes}</div>` : ''}
                </div>
                <div class="nurse-card-actions">
                    <button class="btn-secondary btn-sm" onclick="editNurse('${nurse.id}')">Edit</button>
                    <button class="btn-secondary btn-sm" onclick="toggleNurseStatus('${nurse.id}')">${nurse.status === 'active' ? 'Deactivate' : 'Activate'}</button>
                    <button class="btn-danger btn-sm" onclick="confirmDeleteNurse('${nurse.id}')">Delete</button>
                </div>
            `;
            grid.appendChild(card);
        });
    }

    function getWeekShiftCount(nurseId) {
        const weekDates = DateUtil.getWeekDates(new Date());
        const startStr = DateUtil.toDateString(weekDates[0]);
        const endStr = DateUtil.toDateString(weekDates[6]);
        return Store.getShiftsForDateRange(startStr, endStr)
            .filter(s => s.nurseId === nurseId).length;
    }

    function openNurseModal(nurse = null) {
        const form = document.getElementById('nurseForm');
        form.reset();

        if (nurse) {
            document.getElementById('modalTitle').textContent = 'Edit Nurse';
            document.getElementById('nurseId').value = nurse.id;
            document.getElementById('firstName').value = nurse.firstName;
            document.getElementById('lastName').value = nurse.lastName;
            document.getElementById('role').value = nurse.role;
            document.getElementById('phone').value = nurse.phone || '';
            document.getElementById('email').value = nurse.email || '';
            document.getElementById('hireDate').value = nurse.hireDate || '';
            document.getElementById('shiftPreference').value = nurse.shiftPreference || 'any';
            document.getElementById('maxHours').value = nurse.maxHours || 36;
            document.getElementById('notes').value = nurse.notes || '';
        } else {
            document.getElementById('modalTitle').textContent = 'Add Nurse';
            document.getElementById('nurseId').value = '';
        }

        UI.openModal('nurseModal');
    }

    function handleSaveNurse(e) {
        e.preventDefault();

        const nurseData = {
            firstName: document.getElementById('firstName').value.trim(),
            lastName: document.getElementById('lastName').value.trim(),
            role: document.getElementById('role').value,
            phone: document.getElementById('phone').value.trim(),
            email: document.getElementById('email').value.trim(),
            hireDate: document.getElementById('hireDate').value,
            shiftPreference: document.getElementById('shiftPreference').value,
            maxHours: parseInt(document.getElementById('maxHours').value) || 36,
            notes: document.getElementById('notes').value.trim(),
        };

        const existingId = document.getElementById('nurseId').value;

        if (existingId) {
            Store.updateNurse(existingId, nurseData);
            UI.showToast(`${nurseData.firstName} ${nurseData.lastName} updated`, 'success');
        } else {
            Store.addNurse(nurseData);
            UI.showToast(`${nurseData.firstName} ${nurseData.lastName} added to roster`, 'success');
        }

        UI.closeModal('nurseModal');
        renderNurses();
    }

    function handleDeleteNurse() {
        if (!deleteTargetId) return;

        const nurse = Store.getNurseById(deleteTargetId);
        Store.deleteNurse(deleteTargetId);
        deleteTargetId = null;

        UI.closeModal('deleteModal');
        UI.showToast(`${nurse.firstName} ${nurse.lastName} removed from roster`, 'success');
        renderNurses();
    }

    // Global functions for onclick handlers
    window.editNurse = function (id) {
        const nurse = Store.getNurseById(id);
        if (nurse) openNurseModal(nurse);
    };

    window.confirmDeleteNurse = function (id) {
        const nurse = Store.getNurseById(id);
        if (!nurse) return;
        deleteTargetId = id;
        document.getElementById('deleteNurseName').textContent = `${nurse.firstName} ${nurse.lastName}`;
        UI.openModal('deleteModal');
    };

    window.toggleNurseStatus = function (id) {
        const nurse = Store.getNurseById(id);
        if (!nurse) return;
        const newStatus = nurse.status === 'active' ? 'inactive' : 'active';
        Store.updateNurse(id, { status: newStatus });
        UI.showToast(`${nurse.firstName} ${nurse.lastName} is now ${newStatus}`, 'success');
        renderNurses();
    };

    document.addEventListener('DOMContentLoaded', init);
})();
