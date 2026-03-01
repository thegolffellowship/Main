# Hospital Staff Scheduler

A smart scheduling tool for nurse managers. Auto-generates 6-week staff schedules based on employee preferences, role requirements, and daily minimum staffing targets.

## Quick Start

### 1. Install Python

You need Python 3.10 or newer. Check if you have it:

```
python3 --version
```

If not installed, download from https://www.python.org/downloads/

### 2. Install Dependencies

Open a terminal, navigate to this folder, and run:

```
cd hospital-scheduler
pip install -r requirements.txt
```

### 3. Start the Application

```
cd backend
python -m uvicorn main:app --reload --port 8000
```

### 4. Open in Browser

Go to: **http://localhost:8000**

That's it! The database is created automatically on first run with 10 sample employees.

---

## How to Use

### Step 1: Manage Employees
Click the **Employees** tab to add, edit, or deactivate staff members. Each employee needs:
- Name, Role, Shift (Day/Night), Employment Type (Full-Time/PRN)
- PRN employees also need a tier (Tier 1 = 6 shifts/month, Tier 2 = 8 shifts/month)

### Step 2: Enter Preferences
Click the **Preferences** tab. Select an employee and click on calendar days to cycle through:
- **Blank** = Available
- **RO** (yellow) = Request Off (prefers not to work, but can if needed)
- **PTO** (blue) = Paid Time Off (Full-Time only, counts as a shift)
- **X** (red) = Cannot Work (will not be scheduled)

Click **Save Preferences** when done. Use **Master View** to see all employees' preferences at once.

### Step 3: Generate Schedule
Click the **Schedule Grid** tab, select your period, and click **Generate Schedule**. The system will:
1. Block X days and PTO days
2. Schedule Full-Time employees for 3 shifts/week
3. Fill remaining gaps with PRN employees
4. Check daily minimums and override Request-Off days only if necessary

### Step 4: Review & Adjust
- Red-highlighted totals = below minimum staffing
- Blue dots on cells = manually edited after generation
- Click any cell to manually change it (cycles through codes)
- Review the **Summary Panel** for flags, employee stats, and RO overrides

---

## Daily Minimum Staffing Targets

| Role | Day Shift | Night Shift |
|------|-----------|-------------|
| Nurses (Floor RN + LVN) | 7 | 7 |
| ICU RNs | 3 | 3 |
| PCTs | 3 | 3 |
| Unit Clerks | 2 | 1 |
| House Supervisors | 1 | 1 |

---

## Scheduling Rules

- **Full-Time**: 3 shifts/week required, max 5 consecutive days, 12-hour rest between shifts
- **PRN Tier 1**: Minimum 6 shifts/month
- **PRN Tier 2**: Minimum 8 shifts/month
- **PTO** counts as one of the 3 required weekly shifts for Full-Time employees
- **Overtime** = any shift beyond 3 in a week (flagged, not blocked)
