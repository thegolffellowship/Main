/**
 * PAM Health Nurse Scheduler — Dashboard Page
 */

(function () {
    let currentWeekStart = new Date();

    function init() {
        UI.initSidebar();
        setCurrentDate();
        updateStats();
        initCalendar();
        renderTodayCoverage();

        document.getElementById('prevWeek').addEventListener('click', () => navigateWeek(-1));
        document.getElementById('nextWeek').addEventListener('click', () => navigateWeek(1));
        document.getElementById('todayBtn').addEventListener('click', () => {
            currentWeekStart = new Date();
            renderCalendar();
        });
    }

    function setCurrentDate() {
        const el = document.getElementById('currentDate');
        el.textContent = new Date().toLocaleDateString('en-US', {
            weekday: 'long',
            month: 'long',
            day: 'numeric',
            year: 'numeric'
        });
    }

    function updateStats() {
        const nurses = Store.getActiveNurses();
        const todayStr = DateUtil.today();
        const todayShifts = Store.getShiftsForDate(todayStr);
        const pendingTimeOff = Store.getPendingTimeOff();

        // Count open shifts (assume 4 day + 3 night = 7 needed per day)
        const dayShifts = todayShifts.filter(s => s.type === 'day').length;
        const nightShifts = todayShifts.filter(s => s.type === 'night').length;
        const openShifts = Math.max(0, 4 - dayShifts) + Math.max(0, 3 - nightShifts);

        document.getElementById('totalNurses').textContent = nurses.length;
        document.getElementById('todayShifts').textContent = todayShifts.length;
        document.getElementById('openShifts').textContent = openShifts;
        document.getElementById('timeOffRequests').textContent = pendingTimeOff.length;
    }

    function initCalendar() {
        renderCalendar();
    }

    function navigateWeek(direction) {
        currentWeekStart.setDate(currentWeekStart.getDate() + direction * 7);
        renderCalendar();
    }

    function renderCalendar() {
        const weekDates = DateUtil.getWeekDates(currentWeekStart);
        document.getElementById('weekRange').textContent = DateUtil.getWeekRangeLabel(weekDates);

        const grid = document.getElementById('calendarGrid');
        grid.innerHTML = '';

        const startStr = DateUtil.toDateString(weekDates[0]);
        const endStr = DateUtil.toDateString(weekDates[6]);
        const weekShifts = Store.getShiftsForDateRange(startStr, endStr);
        const nurses = Store.getNurses();

        weekDates.forEach(date => {
            const dateStr = DateUtil.toDateString(date);
            const isToday = DateUtil.isToday(date);
            const dayShifts = weekShifts.filter(s => s.date === dateStr);

            const dayEl = document.createElement('div');
            dayEl.className = `calendar-day${isToday ? ' today' : ''}`;

            const dayTypeShifts = dayShifts.filter(s => s.type === 'day');
            const nightTypeShifts = dayShifts.filter(s => s.type === 'night');

            // Show up to 3 nurse names then a "+X more" count
            let shiftsHTML = '';
            const maxVisible = 3;
            const allShiftsSorted = [...dayTypeShifts, ...nightTypeShifts];

            allShiftsSorted.slice(0, maxVisible).forEach(shift => {
                const nurse = nurses.find(n => n.id === shift.nurseId);
                if (nurse) {
                    const typeClass = shift.type === 'day' ? 'day-type' : 'night-type';
                    shiftsHTML += `<div class="cal-shift ${typeClass}">${nurse.firstName} ${nurse.lastName[0]}.</div>`;
                }
            });

            if (allShiftsSorted.length > maxVisible) {
                shiftsHTML += `<div class="cal-shift-count">+${allShiftsSorted.length - maxVisible} more</div>`;
            }

            if (allShiftsSorted.length === 0) {
                shiftsHTML = '<div class="cal-shift-count">No shifts</div>';
            }

            dayEl.innerHTML = `
                <div class="calendar-day-header">
                    <span class="day-name">${DateUtil.getDayName(date)}</span>
                    <span class="day-number">${date.getDate()}</span>
                </div>
                <div class="calendar-shifts">
                    ${shiftsHTML}
                </div>
            `;

            grid.appendChild(dayEl);
        });
    }

    function renderTodayCoverage() {
        const todayStr = DateUtil.today();
        const todayShifts = Store.getShiftsForDate(todayStr);
        const nurses = Store.getNurses();

        const dayShifts = todayShifts.filter(s => s.type === 'day');
        const nightShifts = todayShifts.filter(s => s.type === 'night');

        renderShiftList('dayShiftList', dayShifts, nurses);
        renderShiftList('nightShiftList', nightShifts, nurses);
    }

    function renderShiftList(listId, shifts, nurses) {
        const list = document.getElementById(listId);

        if (shifts.length === 0) {
            list.innerHTML = '<li class="empty-state">No nurses assigned</li>';
            return;
        }

        list.innerHTML = '';
        shifts.forEach(shift => {
            const nurse = nurses.find(n => n.id === shift.nurseId);
            if (!nurse) return;

            const li = document.createElement('li');
            li.innerHTML = `
                <div class="nurse-avatar ${UI.getAvatarClass(nurse.role)}">${UI.getInitials(nurse.firstName, nurse.lastName)}</div>
                <div class="nurse-list-info">
                    <div class="nurse-list-name">${nurse.firstName} ${nurse.lastName}</div>
                    <div class="nurse-list-role">${nurse.role}${shift.notes ? ' — ' + shift.notes : ''}</div>
                </div>
            `;
            list.appendChild(li);
        });
    }

    document.addEventListener('DOMContentLoaded', init);
})();
