/**
 * PAM Health Nurse Scheduler — Schedule Manager Page
 */

(function () {
    let currentWeekStart = new Date();

    function init() {
        UI.initSidebar();
        renderSchedule();
        renderTimeOff();

        // Week navigation
        document.getElementById('prevWeek').addEventListener('click', () => navigateWeek(-1));
        document.getElementById('nextWeek').addEventListener('click', () => navigateWeek(1));
        document.getElementById('todayBtn').addEventListener('click', () => {
            currentWeekStart = new Date();
            renderSchedule();
        });

        // Filters
        document.getElementById('shiftTypeFilter').addEventListener('change', renderSchedule);
        document.getElementById('nurseRoleFilter').addEventListener('change', renderSchedule);

        // Shift modal
        document.getElementById('addShiftBtn').addEventListener('click', () => openShiftModal());
        document.getElementById('closeShiftModal').addEventListener('click', () => UI.closeModal('shiftModal'));
        document.getElementById('cancelShiftBtn').addEventListener('click', () => UI.closeModal('shiftModal'));
        document.getElementById('shiftForm').addEventListener('submit', handleSaveShift);

        // Time-off modal
        document.getElementById('addTimeOffBtn').addEventListener('click', () => openTimeOffModal());
        document.getElementById('closeTimeOffModal').addEventListener('click', () => UI.closeModal('timeOffModal'));
        document.getElementById('cancelTimeOffBtn').addEventListener('click', () => UI.closeModal('timeOffModal'));
        document.getElementById('timeOffForm').addEventListener('submit', handleSaveTimeOff);

        // Auto-schedule
        document.getElementById('autoScheduleBtn').addEventListener('click', () => UI.openModal('autoScheduleModal'));
        document.getElementById('cancelAutoBtn').addEventListener('click', () => UI.closeModal('autoScheduleModal'));
        document.getElementById('confirmAutoBtn').addEventListener('click', handleAutoSchedule);

        // Close modals on overlay click
        document.querySelectorAll('.modal-overlay').forEach(overlay => {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) overlay.classList.remove('active');
            });
        });
    }

    function navigateWeek(direction) {
        currentWeekStart.setDate(currentWeekStart.getDate() + direction * 7);
        renderSchedule();
    }

    // ===== Schedule Table =====
    function renderSchedule() {
        const weekDates = DateUtil.getWeekDates(currentWeekStart);
        document.getElementById('weekRange').textContent = DateUtil.getWeekRangeLabel(weekDates);

        const startStr = DateUtil.toDateString(weekDates[0]);
        const endStr = DateUtil.toDateString(weekDates[6]);
        const allShifts = Store.getShiftsForDateRange(startStr, endStr);
        const allNurses = Store.getActiveNurses();

        // Apply filters
        const shiftTypeFilter = document.getElementById('shiftTypeFilter').value;
        const roleFilter = document.getElementById('nurseRoleFilter').value;

        let filteredNurses = allNurses;
        if (roleFilter) {
            filteredNurses = filteredNurses.filter(n => n.role === roleFilter);
        }

        // Build header
        const header = document.getElementById('scheduleHeader');
        header.innerHTML = '<th>Nurse</th>';
        weekDates.forEach(date => {
            const isToday = DateUtil.isToday(date);
            const dayName = DateUtil.getDayName(date);
            const dayNum = date.getDate();
            header.innerHTML += `<th class="${isToday ? 'today-col' : ''}">${dayName}<br>${dayNum}</th>`;
        });

        // Build rows
        const body = document.getElementById('scheduleBody');
        body.innerHTML = '';

        if (filteredNurses.length === 0) {
            body.innerHTML = `<tr><td colspan="8" class="empty-state">No nurses found. Add nurses from the Nurses page first.</td></tr>`;
            return;
        }

        filteredNurses.forEach(nurse => {
            const row = document.createElement('tr');

            // Nurse name cell
            const nameCell = document.createElement('td');
            nameCell.innerHTML = `
                <div class="schedule-nurse-name">${nurse.firstName} ${nurse.lastName}</div>
                <div class="schedule-nurse-role">${nurse.role}</div>
            `;
            row.appendChild(nameCell);

            // Day cells
            weekDates.forEach(date => {
                const dateStr = DateUtil.toDateString(date);
                const isToday = DateUtil.isToday(date);
                const cell = document.createElement('td');
                if (isToday) cell.classList.add('today-col');

                const nurseShifts = allShifts.filter(s =>
                    s.nurseId === nurse.id && s.date === dateStr
                );

                // Check if nurse has time off
                const isOff = Store.isNurseOffOnDate(nurse.id, dateStr);

                if (isOff) {
                    cell.innerHTML = '<span class="shift-badge off-type">OFF</span>';
                } else if (nurseShifts.length > 0) {
                    let badges = '';
                    nurseShifts.forEach(shift => {
                        if (!shiftTypeFilter || shift.type === shiftTypeFilter) {
                            const typeClass = shift.type === 'day' ? 'day-type' : 'night-type';
                            const label = shift.type === 'day' ? 'DAY' : 'NIGHT';
                            badges += `<span class="shift-badge ${typeClass}" onclick="removeShift('${shift.id}')" title="Click to remove">${label}</span> `;
                        }
                    });
                    cell.innerHTML = badges || '—';
                } else {
                    cell.innerHTML = `<span class="add-shift-cell" onclick="quickAddShift('${nurse.id}', '${dateStr}')" title="Add shift">+</span>`;
                }

                row.appendChild(cell);
            });

            body.appendChild(row);
        });
    }

    // ===== Shift Modal =====
    function openShiftModal(prefillDate) {
        const form = document.getElementById('shiftForm');
        form.reset();
        document.getElementById('shiftId').value = '';

        // Populate nurse dropdown
        const select = document.getElementById('shiftNurse');
        select.innerHTML = '<option value="">Select a nurse...</option>';
        Store.getActiveNurses().forEach(nurse => {
            select.innerHTML += `<option value="${nurse.id}">${nurse.firstName} ${nurse.lastName} (${nurse.role})</option>`;
        });

        if (prefillDate) {
            document.getElementById('shiftDate').value = prefillDate;
        } else {
            document.getElementById('shiftDate').value = DateUtil.today();
        }

        UI.openModal('shiftModal');
    }

    function handleSaveShift(e) {
        e.preventDefault();

        const nurseId = document.getElementById('shiftNurse').value;
        const date = document.getElementById('shiftDate').value;
        const type = document.getElementById('shiftType').value;
        const notes = document.getElementById('shiftNotes').value.trim();

        // Check for duplicate
        const existing = Store.getShiftsForDate(date).find(
            s => s.nurseId === nurseId && s.type === type
        );
        if (existing) {
            UI.showToast('This nurse already has this shift on that date', 'error');
            return;
        }

        // Check time-off
        if (Store.isNurseOffOnDate(nurseId, date)) {
            UI.showToast('This nurse has approved time off on that date', 'error');
            return;
        }

        Store.addShift({ nurseId, date, type, notes });

        const nurse = Store.getNurseById(nurseId);
        UI.showToast(`${type === 'day' ? 'Day' : 'Night'} shift assigned to ${nurse.firstName}`, 'success');
        UI.closeModal('shiftModal');
        renderSchedule();
    }

    // ===== Time-Off Modal =====
    function openTimeOffModal() {
        const form = document.getElementById('timeOffForm');
        form.reset();

        const select = document.getElementById('timeOffNurse');
        select.innerHTML = '<option value="">Select a nurse...</option>';
        Store.getActiveNurses().forEach(nurse => {
            select.innerHTML += `<option value="${nurse.id}">${nurse.firstName} ${nurse.lastName} (${nurse.role})</option>`;
        });

        document.getElementById('timeOffStart').value = DateUtil.today();
        document.getElementById('timeOffEnd').value = DateUtil.today();

        UI.openModal('timeOffModal');
    }

    function handleSaveTimeOff(e) {
        e.preventDefault();

        const nurseId = document.getElementById('timeOffNurse').value;
        const startDate = document.getElementById('timeOffStart').value;
        const endDate = document.getElementById('timeOffEnd').value;
        const reason = document.getElementById('timeOffReason').value;
        const notes = document.getElementById('timeOffNotes').value.trim();

        if (endDate < startDate) {
            UI.showToast('End date must be on or after start date', 'error');
            return;
        }

        Store.addTimeOff({ nurseId, startDate, endDate, reason, notes });

        const nurse = Store.getNurseById(nurseId);
        UI.showToast(`Time-off request added for ${nurse.firstName}`, 'success');
        UI.closeModal('timeOffModal');
        renderTimeOff();
        renderSchedule();
    }

    // ===== Time-Off List =====
    function renderTimeOff() {
        const timeOffs = Store.getTimeOff();
        const list = document.getElementById('timeOffList');

        if (timeOffs.length === 0) {
            list.innerHTML = '<div class="empty-state">No time-off requests</div>';
            return;
        }

        // Sort: pending first, then by start date
        timeOffs.sort((a, b) => {
            if (a.status === 'pending' && b.status !== 'pending') return -1;
            if (a.status !== 'pending' && b.status === 'pending') return 1;
            return a.startDate.localeCompare(b.startDate);
        });

        list.innerHTML = '';
        timeOffs.forEach(req => {
            const nurse = Store.getNurseById(req.nurseId);
            if (!nurse) return;

            const card = document.createElement('div');
            card.className = 'time-off-card';

            const statusClass = req.status === 'approved' ? 'status-approved' :
                                req.status === 'denied' ? 'status-denied' : 'status-pending-review';

            card.innerHTML = `
                <span class="time-off-nurse">${nurse.firstName} ${nurse.lastName}</span>
                <span class="time-off-dates">${DateUtil.formatDateShort(req.startDate)} — ${DateUtil.formatDateShort(req.endDate)}</span>
                <span class="time-off-reason">${req.reason}</span>
                <span class="time-off-status ${statusClass}">${req.status}</span>
                <div class="time-off-actions">
                    ${req.status === 'pending' ? `
                        <button class="btn-primary btn-sm" onclick="approveTimeOff('${req.id}')">Approve</button>
                        <button class="btn-danger btn-sm" onclick="denyTimeOff('${req.id}')">Deny</button>
                    ` : ''}
                    <button class="btn-secondary btn-sm" onclick="deleteTimeOff('${req.id}')">Remove</button>
                </div>
            `;
            list.appendChild(card);
        });
    }

    // ===== Auto-Schedule =====
    function handleAutoSchedule() {
        const weekDates = DateUtil.getWeekDates(currentWeekStart);
        const dayNeeded = parseInt(document.getElementById('dayNursesNeeded').value) || 4;
        const nightNeeded = parseInt(document.getElementById('nightNursesNeeded').value) || 3;
        const activeNurses = Store.getActiveNurses();

        if (activeNurses.length === 0) {
            UI.showToast('No active nurses to schedule', 'error');
            UI.closeModal('autoScheduleModal');
            return;
        }

        // Track hours per nurse for fairness
        const hoursCount = {};
        activeNurses.forEach(n => { hoursCount[n.id] = 0; });

        // Count existing shifts this week
        const startStr = DateUtil.toDateString(weekDates[0]);
        const endStr = DateUtil.toDateString(weekDates[6]);
        const existingShifts = Store.getShiftsForDateRange(startStr, endStr);
        existingShifts.forEach(s => {
            if (hoursCount[s.nurseId] !== undefined) {
                hoursCount[s.nurseId] += 12;
            }
        });

        let shiftsAdded = 0;

        weekDates.forEach(date => {
            const dateStr = DateUtil.toDateString(date);
            const dayShifts = existingShifts.filter(s => s.date === dateStr);

            // Fill day shifts
            const existingDay = dayShifts.filter(s => s.type === 'day');
            const daySlots = dayNeeded - existingDay.length;
            if (daySlots > 0) {
                const candidates = getAvailableNurses(activeNurses, dateStr, 'day', hoursCount, existingShifts);
                candidates.slice(0, daySlots).forEach(nurse => {
                    Store.addShift({ nurseId: nurse.id, date: dateStr, type: 'day', notes: 'Auto-scheduled' });
                    hoursCount[nurse.id] += 12;
                    shiftsAdded++;
                });
            }

            // Fill night shifts
            const existingNight = dayShifts.filter(s => s.type === 'night');
            const nightSlots = nightNeeded - existingNight.length;
            if (nightSlots > 0) {
                const candidates = getAvailableNurses(activeNurses, dateStr, 'night', hoursCount, existingShifts);
                candidates.slice(0, nightSlots).forEach(nurse => {
                    Store.addShift({ nurseId: nurse.id, date: dateStr, type: 'night', notes: 'Auto-scheduled' });
                    hoursCount[nurse.id] += 12;
                    shiftsAdded++;
                });
            }
        });

        UI.closeModal('autoScheduleModal');
        UI.showToast(`Auto-schedule complete: ${shiftsAdded} shifts added`, 'success');
        renderSchedule();
    }

    function getAvailableNurses(allNurses, dateStr, shiftType, hoursCount, existingShifts) {
        return allNurses
            .filter(nurse => {
                // Not already scheduled for this shift on this date
                const alreadyScheduled = existingShifts.some(
                    s => s.nurseId === nurse.id && s.date === dateStr && s.type === shiftType
                );
                if (alreadyScheduled) return false;

                // Not on time off
                if (Store.isNurseOffOnDate(nurse.id, dateStr)) return false;

                // Not already working both shifts on this date
                const shiftsOnDate = existingShifts.filter(
                    s => s.nurseId === nurse.id && s.date === dateStr
                );
                if (shiftsOnDate.length >= 1) return false;

                // Under max hours
                const maxHours = nurse.maxHours || 36;
                if ((hoursCount[nurse.id] || 0) + 12 > maxHours) return false;

                return true;
            })
            .sort((a, b) => {
                // Prefer nurses who prefer this shift type
                const aPref = a.shiftPreference === shiftType ? 0 : (a.shiftPreference === 'any' ? 1 : 2);
                const bPref = b.shiftPreference === shiftType ? 0 : (b.shiftPreference === 'any' ? 1 : 2);
                if (aPref !== bPref) return aPref - bPref;

                // Then prefer nurses with fewer hours (fairness)
                return (hoursCount[a.id] || 0) - (hoursCount[b.id] || 0);
            });
    }

    // ===== Global Functions =====
    window.quickAddShift = function (nurseId, dateStr) {
        openShiftModal(dateStr);
        // Pre-select the nurse after modal opens
        setTimeout(() => {
            document.getElementById('shiftNurse').value = nurseId;
        }, 50);
    };

    window.removeShift = function (shiftId) {
        Store.deleteShift(shiftId);
        UI.showToast('Shift removed', 'success');
        renderSchedule();
    };

    window.approveTimeOff = function (id) {
        Store.updateTimeOff(id, { status: 'approved' });
        UI.showToast('Time-off approved', 'success');
        renderTimeOff();
        renderSchedule();
    };

    window.denyTimeOff = function (id) {
        Store.updateTimeOff(id, { status: 'denied' });
        UI.showToast('Time-off denied');
        renderTimeOff();
    };

    window.deleteTimeOff = function (id) {
        Store.deleteTimeOff(id);
        UI.showToast('Time-off request removed');
        renderTimeOff();
        renderSchedule();
    };

    document.addEventListener('DOMContentLoaded', init);
})();
