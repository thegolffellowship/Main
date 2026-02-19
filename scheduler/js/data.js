/**
 * PAM Health Nurse Scheduler — Data Layer
 * Uses localStorage for persistence. All data operations go through this module.
 */

const Store = {
    // ===== Keys =====
    NURSES_KEY: 'pamScheduler_nurses',
    SHIFTS_KEY: 'pamScheduler_shifts',
    TIME_OFF_KEY: 'pamScheduler_timeOff',

    // ===== Nurses =====
    getNurses() {
        const data = localStorage.getItem(this.NURSES_KEY);
        return data ? JSON.parse(data) : [];
    },

    saveNurses(nurses) {
        localStorage.setItem(this.NURSES_KEY, JSON.stringify(nurses));
    },

    addNurse(nurse) {
        const nurses = this.getNurses();
        nurse.id = this.generateId();
        nurse.status = nurse.status || 'active';
        nurse.createdAt = new Date().toISOString();
        nurses.push(nurse);
        this.saveNurses(nurses);
        return nurse;
    },

    updateNurse(id, updates) {
        const nurses = this.getNurses();
        const index = nurses.findIndex(n => n.id === id);
        if (index !== -1) {
            nurses[index] = { ...nurses[index], ...updates };
            this.saveNurses(nurses);
            return nurses[index];
        }
        return null;
    },

    deleteNurse(id) {
        const nurses = this.getNurses().filter(n => n.id !== id);
        this.saveNurses(nurses);
        // Also remove their shifts
        const shifts = this.getShifts().filter(s => s.nurseId !== id);
        this.saveShifts(shifts);
        // And time-off requests
        const timeOff = this.getTimeOff().filter(t => t.nurseId !== id);
        this.saveTimeOff(timeOff);
    },

    getNurseById(id) {
        return this.getNurses().find(n => n.id === id) || null;
    },

    getActiveNurses() {
        return this.getNurses().filter(n => n.status === 'active');
    },

    // ===== Shifts =====
    getShifts() {
        const data = localStorage.getItem(this.SHIFTS_KEY);
        return data ? JSON.parse(data) : [];
    },

    saveShifts(shifts) {
        localStorage.setItem(this.SHIFTS_KEY, JSON.stringify(shifts));
    },

    addShift(shift) {
        const shifts = this.getShifts();
        shift.id = this.generateId();
        shift.createdAt = new Date().toISOString();
        shifts.push(shift);
        this.saveShifts(shifts);
        return shift;
    },

    deleteShift(id) {
        const shifts = this.getShifts().filter(s => s.id !== id);
        this.saveShifts(shifts);
    },

    getShiftsForDate(dateStr) {
        return this.getShifts().filter(s => s.date === dateStr);
    },

    getShiftsForDateRange(startDate, endDate) {
        return this.getShifts().filter(s => s.date >= startDate && s.date <= endDate);
    },

    getShiftsForNurse(nurseId) {
        return this.getShifts().filter(s => s.nurseId === nurseId);
    },

    // ===== Time-Off =====
    getTimeOff() {
        const data = localStorage.getItem(this.TIME_OFF_KEY);
        return data ? JSON.parse(data) : [];
    },

    saveTimeOff(timeOff) {
        localStorage.setItem(this.TIME_OFF_KEY, JSON.stringify(timeOff));
    },

    addTimeOff(request) {
        const timeOff = this.getTimeOff();
        request.id = this.generateId();
        request.status = request.status || 'pending';
        request.createdAt = new Date().toISOString();
        timeOff.push(request);
        this.saveTimeOff(timeOff);
        return request;
    },

    updateTimeOff(id, updates) {
        const timeOff = this.getTimeOff();
        const index = timeOff.findIndex(t => t.id === id);
        if (index !== -1) {
            timeOff[index] = { ...timeOff[index], ...updates };
            this.saveTimeOff(timeOff);
            return timeOff[index];
        }
        return null;
    },

    deleteTimeOff(id) {
        const timeOff = this.getTimeOff().filter(t => t.id !== id);
        this.saveTimeOff(timeOff);
    },

    getTimeOffForNurse(nurseId) {
        return this.getTimeOff().filter(t => t.nurseId === nurseId);
    },

    getPendingTimeOff() {
        return this.getTimeOff().filter(t => t.status === 'pending');
    },

    isNurseOffOnDate(nurseId, dateStr) {
        return this.getTimeOff().some(t =>
            t.nurseId === nurseId &&
            t.status === 'approved' &&
            dateStr >= t.startDate &&
            dateStr <= t.endDate
        );
    },

    // ===== Utilities =====
    generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
    },

    // ===== Seed Data =====
    seedSampleData() {
        if (this.getNurses().length > 0) return; // Already has data

        const nurses = [
            { id: 'n1', firstName: 'Maria', lastName: 'Garcia', role: 'RN', phone: '(210) 555-0101', email: 'mgarcia@pamhealth.com', shiftPreference: 'day', maxHours: 36, status: 'active', notes: 'ACLS certified, wound care specialist', hireDate: '2022-03-15', createdAt: new Date().toISOString() },
            { id: 'n2', firstName: 'James', lastName: 'Rodriguez', role: 'RN', phone: '(210) 555-0102', email: 'jrodriguez@pamhealth.com', shiftPreference: 'night', maxHours: 36, status: 'active', notes: 'ICU experience', hireDate: '2021-08-01', createdAt: new Date().toISOString() },
            { id: 'n3', firstName: 'Sarah', lastName: 'Johnson', role: 'Charge Nurse', phone: '(210) 555-0103', email: 'sjohnson@pamhealth.com', shiftPreference: 'day', maxHours: 36, status: 'active', notes: 'BSN, Charge nurse certified', hireDate: '2019-11-10', createdAt: new Date().toISOString() },
            { id: 'n4', firstName: 'David', lastName: 'Martinez', role: 'LVN', phone: '(210) 555-0104', email: 'dmartinez@pamhealth.com', shiftPreference: 'any', maxHours: 36, status: 'active', notes: 'Bilingual Spanish/English', hireDate: '2023-01-20', createdAt: new Date().toISOString() },
            { id: 'n5', firstName: 'Ashley', lastName: 'Williams', role: 'CNA', phone: '(210) 555-0105', email: 'awilliams@pamhealth.com', shiftPreference: 'day', maxHours: 36, status: 'active', notes: '', hireDate: '2023-06-01', createdAt: new Date().toISOString() },
            { id: 'n6', firstName: 'Robert', lastName: 'Brown', role: 'RN', phone: '(210) 555-0106', email: 'rbrown@pamhealth.com', shiftPreference: 'night', maxHours: 36, status: 'active', notes: 'Float pool, IV certified', hireDate: '2020-05-12', createdAt: new Date().toISOString() },
            { id: 'n7', firstName: 'Jessica', lastName: 'Hernandez', role: 'LVN', phone: '(210) 555-0107', email: 'jhernandez@pamhealth.com', shiftPreference: 'day', maxHours: 24, status: 'active', notes: 'Part-time', hireDate: '2022-09-15', createdAt: new Date().toISOString() },
            { id: 'n8', firstName: 'Michael', lastName: 'Davis', role: 'CNA', phone: '(210) 555-0108', email: 'mdavis@pamhealth.com', shiftPreference: 'night', maxHours: 36, status: 'active', notes: '', hireDate: '2024-01-08', createdAt: new Date().toISOString() },
            { id: 'n9', firstName: 'Linda', lastName: 'Wilson', role: 'RN', phone: '(210) 555-0109', email: 'lwilson@pamhealth.com', shiftPreference: 'any', maxHours: 48, status: 'active', notes: 'Willing to pick up OT, ACLS certified', hireDate: '2018-07-22', createdAt: new Date().toISOString() },
            { id: 'n10', firstName: 'Carlos', lastName: 'Perez', role: 'CNA', phone: '(210) 555-0110', email: 'cperez@pamhealth.com', shiftPreference: 'any', maxHours: 36, status: 'inactive', notes: 'On leave', hireDate: '2023-03-01', createdAt: new Date().toISOString() },
        ];
        this.saveNurses(nurses);

        // Seed some shifts for this week
        const today = new Date();
        const monday = new Date(today);
        monday.setDate(today.getDate() - today.getDay() + 1);

        const shifts = [];
        const dayNurses = ['n1', 'n3', 'n4', 'n5', 'n7', 'n9'];
        const nightNurses = ['n2', 'n6', 'n8'];

        for (let d = 0; d < 7; d++) {
            const date = new Date(monday);
            date.setDate(monday.getDate() + d);
            const dateStr = DateUtil.toDateString(date);

            // Assign day shifts
            const dayCount = d < 5 ? 4 : 2; // fewer on weekends
            for (let i = 0; i < dayCount && i < dayNurses.length; i++) {
                shifts.push({
                    id: this.generateId(),
                    nurseId: dayNurses[i],
                    date: dateStr,
                    type: 'day',
                    notes: i === 0 && d < 5 ? 'Charge' : '',
                    createdAt: new Date().toISOString()
                });
            }

            // Assign night shifts
            const nightCount = d < 5 ? 3 : 2;
            for (let i = 0; i < nightCount && i < nightNurses.length; i++) {
                shifts.push({
                    id: this.generateId(),
                    nurseId: nightNurses[i],
                    date: dateStr,
                    type: 'night',
                    notes: '',
                    createdAt: new Date().toISOString()
                });
            }
        }
        this.saveShifts(shifts);

        // Seed time-off requests
        const nextWeekMon = new Date(monday);
        nextWeekMon.setDate(monday.getDate() + 7);
        const nextWeekFri = new Date(nextWeekMon);
        nextWeekFri.setDate(nextWeekMon.getDate() + 4);

        const timeOff = [
            {
                id: this.generateId(),
                nurseId: 'n4',
                startDate: DateUtil.toDateString(nextWeekMon),
                endDate: DateUtil.toDateString(nextWeekFri),
                reason: 'PTO',
                notes: 'Family vacation',
                status: 'approved',
                createdAt: new Date().toISOString()
            },
            {
                id: this.generateId(),
                nurseId: 'n7',
                startDate: DateUtil.toDateString(new Date(monday.getTime() + 10 * 86400000)),
                endDate: DateUtil.toDateString(new Date(monday.getTime() + 12 * 86400000)),
                reason: 'Personal',
                notes: '',
                status: 'pending',
                createdAt: new Date().toISOString()
            }
        ];
        this.saveTimeOff(timeOff);
    }
};

// ===== Date Utilities =====
const DateUtil = {
    toDateString(date) {
        const y = date.getFullYear();
        const m = String(date.getMonth() + 1).padStart(2, '0');
        const d = String(date.getDate()).padStart(2, '0');
        return `${y}-${m}-${d}`;
    },

    parseDate(dateStr) {
        const [y, m, d] = dateStr.split('-').map(Number);
        return new Date(y, m - 1, d);
    },

    formatDate(dateStr) {
        const date = this.parseDate(dateStr);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    },

    formatDateShort(dateStr) {
        const date = this.parseDate(dateStr);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    },

    getWeekDates(referenceDate) {
        const date = new Date(referenceDate);
        const day = date.getDay();
        const monday = new Date(date);
        monday.setDate(date.getDate() - (day === 0 ? 6 : day - 1));

        const dates = [];
        for (let i = 0; i < 7; i++) {
            const d = new Date(monday);
            d.setDate(monday.getDate() + i);
            dates.push(d);
        }
        return dates;
    },

    getWeekRangeLabel(dates) {
        const start = dates[0];
        const end = dates[6];
        const startStr = start.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        const endStr = end.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        return `${startStr} — ${endStr}`;
    },

    getDayName(date) {
        return date.toLocaleDateString('en-US', { weekday: 'short' });
    },

    isToday(date) {
        const today = new Date();
        return date.getFullYear() === today.getFullYear() &&
               date.getMonth() === today.getMonth() &&
               date.getDate() === today.getDate();
    },

    today() {
        return this.toDateString(new Date());
    }
};

// ===== UI Helpers =====
const UI = {
    getAvatarClass(role) {
        switch (role) {
            case 'RN': return 'avatar-rn';
            case 'LVN': return 'avatar-lvn';
            case 'CNA': return 'avatar-cna';
            case 'Charge Nurse': return 'avatar-charge';
            default: return 'avatar-default';
        }
    },

    getInitials(firstName, lastName) {
        return (firstName[0] + lastName[0]).toUpperCase();
    },

    showToast(message, type = '') {
        const existing = document.querySelector('.toast');
        if (existing) existing.remove();

        const toast = document.createElement('div');
        toast.className = `toast ${type ? 'toast-' + type : ''}`;
        toast.textContent = message;
        document.body.appendChild(toast);

        requestAnimationFrame(() => toast.classList.add('show'));

        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    },

    openModal(modalId) {
        document.getElementById(modalId).classList.add('active');
    },

    closeModal(modalId) {
        document.getElementById(modalId).classList.remove('active');
    },

    initSidebar() {
        const toggle = document.querySelector('.menu-toggle');
        const sidebar = document.querySelector('.sidebar');
        if (toggle && sidebar) {
            toggle.addEventListener('click', () => {
                sidebar.classList.toggle('open');
            });
            // Close sidebar when clicking outside on mobile
            document.addEventListener('click', (e) => {
                if (window.innerWidth <= 768 &&
                    sidebar.classList.contains('open') &&
                    !sidebar.contains(e.target) &&
                    !toggle.contains(e.target)) {
                    sidebar.classList.remove('open');
                }
            });
        }
    }
};

// Seed sample data on first load
Store.seedSampleData();
