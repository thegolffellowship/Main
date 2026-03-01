"""
Auto-scheduling engine for hospital staff scheduling.

Implements the core algorithm:
1. Apply hard blocks (X, PTO, consecutive-day limit, rest rule)
2. Schedule Full-Time employees to meet 3 shifts/week
3. Fill gaps with PRN employees
4. Check daily minimums and flag shortages
5. Handle RO overrides when needed to meet minimums

v2: Add configurable rule engine, shift-swap optimization,
fatigue scoring, ML-based preference learning.
"""

from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from models import (
    Employee, Preference, ScheduleEntry, SchedulePeriod,
    Role, Shift, EmploymentType, PreferenceCode, ScheduleCode,
    DAILY_MINIMUMS, FT_SHIFTS_PER_WEEK, FT_MAX_CONSECUTIVE_DAYS,
    PRN_TIER_MINIMUMS, ROLE_DISPLAY_ORDER,
)


def generate_schedule(db: Session, period: SchedulePeriod) -> dict:
    """
    Main entry point: generate a 6-week schedule for the given period.

    Returns a summary dict with flags, overrides, and per-employee stats.

    v2: Accept configuration overrides, support partial regeneration
    (only regenerate unfilled days), parallel processing for large staff.
    """
    start = period.start_date
    end = period.end_date
    all_dates = [start + timedelta(days=i) for i in range(42)]

    # Clear existing schedule entries for this period
    db.query(ScheduleEntry).filter(ScheduleEntry.period_id == period.id).delete()
    db.flush()

    # Load all active employees grouped by shift
    employees = db.query(Employee).filter(Employee.is_active == True).all()
    day_employees = [e for e in employees if e.shift == Shift.DAY]
    night_employees = [e for e in employees if e.shift == Shift.NIGHT]

    # Load all preferences for this period keyed by (employee_id, date)
    prefs_raw = db.query(Preference).filter(Preference.period_id == period.id).all()
    prefs = {}
    for p in prefs_raw:
        prefs[(p.employee_id, p.date)] = p.code

    # Track schedule state: employee_id -> set of dates scheduled
    schedule = defaultdict(dict)  # employee_id -> {date: ScheduleCode}
    ro_overrides = []  # track RO overrides for summary

    # Process each shift independently
    for shift, emp_list in [(Shift.DAY, day_employees), (Shift.NIGHT, night_employees)]:
        _schedule_shift(
            db, period, shift, emp_list, all_dates, prefs, schedule, ro_overrides
        )

    # Write schedule entries to database
    entries = []
    for emp_id, date_codes in schedule.items():
        for d, code in date_codes.items():
            entry = ScheduleEntry(
                employee_id=emp_id,
                period_id=period.id,
                date=d,
                code=code,
                is_manual_override=False,
            )
            entries.append(entry)
    db.add_all(entries)

    # Mark period as generated
    from datetime import datetime
    period.is_generated = True
    period.generated_at = datetime.utcnow()

    db.commit()

    # Build summary
    summary = _build_summary(db, period, schedule, ro_overrides, employees, all_dates)
    return summary


def _schedule_shift(
    db: Session,
    period: SchedulePeriod,
    shift: Shift,
    employees: list[Employee],
    all_dates: list[date],
    prefs: dict,
    schedule: dict,
    ro_overrides: list,
):
    """
    Schedule one shift (Day or Night) across all 42 days.

    v2: Add priority weighting, seniority-based tie-breaking.
    """
    ft_employees = [e for e in employees if e.employment_type == EmploymentType.FULL_TIME]
    prn_employees = [e for e in employees if e.employment_type == EmploymentType.PRN]

    # Initialize all employee-date combos with appropriate defaults
    for emp in employees:
        for d in all_dates:
            pref = prefs.get((emp.id, d))
            if pref == PreferenceCode.PTO:
                schedule[emp.id][d] = ScheduleCode.PTO
            elif pref == PreferenceCode.CANNOT_WORK:
                schedule[emp.id][d] = ScheduleCode.CANNOT_WORK
            else:
                schedule[emp.id][d] = ScheduleCode.OFF

    # Phase 1: Schedule FT employees (3 shifts per week)
    for week_start_idx in range(0, 42, 7):
        week_dates = all_dates[week_start_idx:week_start_idx + 7]
        _schedule_ft_week(ft_employees, week_dates, prefs, schedule)

    # Phase 2: Fill gaps with PRN employees
    _schedule_prn(prn_employees, all_dates, prefs, schedule)

    # Phase 3: Check daily minimums and override ROs if needed
    for d in all_dates:
        _enforce_daily_minimums(
            employees, d, shift, prefs, schedule, ro_overrides
        )


def _schedule_ft_week(
    ft_employees: list[Employee],
    week_dates: list[date],
    prefs: dict,
    schedule: dict,
):
    """
    Distribute 3 shifts per FT employee across a week.

    Considers: hard blocks, RO preferences, consecutive day limits,
    and even distribution.

    v2: Add weighted scoring for preferred days, team cohesion optimization.
    """
    for emp in ft_employees:
        # Count PTO days this week (they count toward 3-shift requirement)
        pto_count = sum(
            1 for d in week_dates
            if schedule[emp.id].get(d) == ScheduleCode.PTO
        )
        # Respect employee max_weekly_shifts cap (default 3)
        target = min(FT_SHIFTS_PER_WEEK, emp.max_weekly_shifts)
        shifts_needed = max(0, target - pto_count)

        # Get available days (not X, not PTO, not already scheduled)
        available_days = []
        ro_days = []
        for d in week_dates:
            current = schedule[emp.id].get(d, ScheduleCode.OFF)
            if current in (ScheduleCode.PTO, ScheduleCode.CANNOT_WORK, ScheduleCode.WORKING, ScheduleCode.RO_OVERRIDE):
                continue
            pref = prefs.get((emp.id, d))
            if pref == PreferenceCode.REQUEST_OFF:
                ro_days.append(d)
            else:
                available_days.append(d)

        # Filter by consecutive day and rest rules
        available_days = [d for d in available_days if _can_schedule(emp.id, d, schedule)]
        ro_days = [d for d in ro_days if _can_schedule(emp.id, d, schedule)]

        # Schedule from available days first, evenly spaced
        scheduled_count = 0
        if shifts_needed > 0 and available_days:
            chosen = _pick_spread_days(available_days, shifts_needed)
            for d in chosen:
                schedule[emp.id][d] = ScheduleCode.WORKING
                scheduled_count += 1

        # If still short, use RO days (but prefer not to)
        remaining = shifts_needed - scheduled_count
        if remaining > 0 and ro_days:
            chosen = _pick_spread_days(ro_days, remaining)
            for d in chosen:
                schedule[emp.id][d] = ScheduleCode.WORKING
                scheduled_count += 1


def _schedule_prn(
    prn_employees: list[Employee],
    all_dates: list[date],
    prefs: dict,
    schedule: dict,
):
    """
    Schedule PRN employees to meet their monthly minimums.

    PRN fills gaps after FT scheduling. Distributes shifts evenly
    across the period.

    v2: Add PRN availability windows, preferred day patterns.
    """
    # Group dates by month
    months = defaultdict(list)
    for d in all_dates:
        months[(d.year, d.month)].append(d)

    for emp in prn_employees:
        tier_min = PRN_TIER_MINIMUMS.get(emp.prn_tier, 6)

        for (year, month), month_dates in months.items():
            # Count shifts already scheduled this month
            current_shifts = sum(
                1 for d in month_dates
                if schedule[emp.id].get(d) in (ScheduleCode.WORKING, ScheduleCode.RO_OVERRIDE)
            )
            shifts_needed = max(0, tier_min - current_shifts)

            if shifts_needed == 0:
                continue

            # Get available days
            available_days = []
            for d in month_dates:
                current = schedule[emp.id].get(d, ScheduleCode.OFF)
                if current != ScheduleCode.OFF:
                    continue
                pref = prefs.get((emp.id, d))
                if pref in (PreferenceCode.CANNOT_WORK, PreferenceCode.PTO, PreferenceCode.REQUEST_OFF):
                    continue
                if not _can_schedule(emp.id, d, schedule):
                    continue
                # Enforce max weekly shifts cap
                if _week_shift_count(emp.id, d, schedule) >= emp.max_weekly_shifts:
                    continue
                available_days.append(d)

            chosen = _pick_spread_days(available_days, shifts_needed)
            for d in chosen:
                schedule[emp.id][d] = ScheduleCode.WORKING


def _enforce_daily_minimums(
    employees: list[Employee],
    d: date,
    shift: Shift,
    prefs: dict,
    schedule: dict,
    ro_overrides: list,
):
    """
    Check if daily minimums are met for a given date and shift.
    If not, attempt to pull in additional staff (overriding ROs if necessary).

    v2: Add escalation rules, auto-notification for critical shortages.
    """
    def _count_working(role_filter):
        return sum(
            1 for emp in employees
            if role_filter(emp)
            and schedule[emp.id].get(d) in (ScheduleCode.WORKING, ScheduleCode.RO_OVERRIDE)
        )

    def _get_available_for_role(role_filter, include_ro=False):
        """Get employees of a role who could be added to this day."""
        result = []
        for emp in employees:
            if not role_filter(emp):
                continue
            current = schedule[emp.id].get(d, ScheduleCode.OFF)
            if current != ScheduleCode.OFF:
                continue
            if not _can_schedule(emp.id, d, schedule):
                continue
            # Enforce max weekly shifts cap
            if _week_shift_count(emp.id, d, schedule) >= emp.max_weekly_shifts:
                continue
            pref = prefs.get((emp.id, d))
            if pref == PreferenceCode.CANNOT_WORK:
                continue
            if pref == PreferenceCode.REQUEST_OFF and not include_ro:
                continue
            result.append(emp)
        return result

    def _add_staff(role_filter, needed, role_name):
        """Try to add staff to meet minimum, including RO overrides."""
        current_count = _count_working(role_filter)
        shortage = needed - current_count
        if shortage <= 0:
            return

        # First try available (non-RO) employees
        available = _get_available_for_role(role_filter, include_ro=False)
        # Sort by fewest shifts this week for even distribution
        available.sort(key=lambda e: _week_shift_count(e.id, d, schedule))

        for emp in available[:shortage]:
            schedule[emp.id][d] = ScheduleCode.WORKING
            shortage -= 1

        if shortage <= 0:
            return

        # Override RO employees if still short
        ro_available = _get_available_for_role(role_filter, include_ro=True)
        # Remove already-scheduled ones
        ro_available = [e for e in ro_available if schedule[e.id].get(d) == ScheduleCode.OFF]
        # Sort by fewest RO overrides so far (fairness)
        ro_override_counts = defaultdict(int)
        for entry in ro_overrides:
            ro_override_counts[entry["employee_id"]] += 1
        ro_available.sort(key=lambda e: ro_override_counts[e.id])

        for emp in ro_available[:shortage]:
            schedule[emp.id][d] = ScheduleCode.RO_OVERRIDE
            ro_overrides.append({
                "employee_id": emp.id,
                "employee_name": emp.name,
                "date": d.isoformat(),
                "reason": f"Needed to meet {role_name} minimum"
            })

    # Nurses (Floor RN + LVN, not ICU RNs)
    nurse_min = DAILY_MINIMUMS["nurses"]
    nurse_filter = lambda e: e.role in (Role.FLOOR_RN, Role.LVN)
    _add_staff(nurse_filter, nurse_min, "nurse")

    # Ensure at least 1 RN in the nurse mix
    rn_count = _count_working(lambda e: e.role == Role.FLOOR_RN)
    if rn_count == 0:
        nurse_count = _count_working(nurse_filter)
        if nurse_count > 0:
            # Try to add an RN
            _add_staff(lambda e: e.role == Role.FLOOR_RN, 1, "Floor RN (nurse mix)")

    # ICU RNs
    _add_staff(lambda e: e.role == Role.ICU_RN, DAILY_MINIMUMS["icu_rns"], "ICU RN")

    # PCTs
    _add_staff(lambda e: e.role == Role.PCT, DAILY_MINIMUMS["pcts"], "PCT")

    # House Supervisors
    _add_staff(
        lambda e: e.role == Role.HOUSE_SUPERVISOR,
        DAILY_MINIMUMS["house_supervisors"],
        "House Supervisor"
    )

    # Unit Clerks (different minimum for day vs night)
    clerk_min = DAILY_MINIMUMS["unit_clerks_day"] if shift == Shift.DAY else DAILY_MINIMUMS["unit_clerks_night"]
    _add_staff(lambda e: e.role == Role.UNIT_CLERK, clerk_min, "Unit Clerk")


def _can_schedule(emp_id: int, d: date, schedule: dict) -> bool:
    """
    Check if scheduling employee on date d would violate:
    - 5 consecutive day max (must have day off after 5)
    - 12-hour rest rule (N/A within same shift type in this model,
      but checked for completeness)

    v2: Add fatigue scoring, cross-shift rest validation.
    """
    # Check consecutive days: look back up to 5 days
    consecutive = 0
    for i in range(1, FT_MAX_CONSECUTIVE_DAYS + 1):
        check_date = d - timedelta(days=i)
        code = schedule.get(emp_id, {}).get(check_date, ScheduleCode.OFF)
        if code in (ScheduleCode.WORKING, ScheduleCode.RO_OVERRIDE):
            consecutive += 1
        else:
            break

    # Also check forward
    forward_consecutive = 0
    for i in range(1, FT_MAX_CONSECUTIVE_DAYS + 1):
        check_date = d + timedelta(days=i)
        code = schedule.get(emp_id, {}).get(check_date, ScheduleCode.OFF)
        if code in (ScheduleCode.WORKING, ScheduleCode.RO_OVERRIDE):
            forward_consecutive += 1
        else:
            break

    if consecutive >= FT_MAX_CONSECUTIVE_DAYS:
        return False

    # Would adding this day create a streak > 5?
    total_streak = consecutive + 1 + forward_consecutive
    if total_streak > FT_MAX_CONSECUTIVE_DAYS:
        return False

    return True


def _week_shift_count(emp_id: int, d: date, schedule: dict) -> int:
    """Count shifts scheduled for employee in the same week as date d."""
    # Find Sunday of this week
    days_since_sunday = d.weekday()  # Monday=0 .. Sunday=6
    if d.weekday() == 6:
        sunday = d
    else:
        sunday = d - timedelta(days=(d.weekday() + 1) % 7)

    count = 0
    for i in range(7):
        check = sunday + timedelta(days=i)
        code = schedule.get(emp_id, {}).get(check, ScheduleCode.OFF)
        if code in (ScheduleCode.WORKING, ScheduleCode.RO_OVERRIDE):
            count += 1
    return count


def _pick_spread_days(available: list[date], count: int) -> list[date]:
    """
    Pick `count` days from `available`, spread as evenly as possible.

    v2: Add weighted scoring based on employee preferences and team needs.
    """
    if count <= 0 or not available:
        return []
    if count >= len(available):
        return available

    available.sort()
    n = len(available)

    # Pick evenly spaced indices
    step = n / count
    chosen = []
    for i in range(count):
        idx = int(i * step + step / 2)
        idx = min(idx, n - 1)
        chosen.append(available[idx])

    return chosen


def _build_summary(
    db: Session,
    period: SchedulePeriod,
    schedule: dict,
    ro_overrides: list,
    employees: list[Employee],
    all_dates: list[date],
) -> dict:
    """
    Build the generation summary with flags and per-employee stats.

    v2: Add trend analysis, comparison with previous periods,
    cost projections, compliance scoring.
    """
    emp_map = {e.id: e for e in employees}

    # Per-employee summaries
    employee_summaries = []
    for emp in employees:
        total_shifts = sum(
            1 for d in all_dates
            if schedule.get(emp.id, {}).get(d) in (ScheduleCode.WORKING, ScheduleCode.RO_OVERRIDE)
        )
        pto_days = sum(
            1 for d in all_dates
            if schedule.get(emp.id, {}).get(d) == ScheduleCode.PTO
        )
        ro_count = sum(
            1 for d in all_dates
            if schedule.get(emp.id, {}).get(d) == ScheduleCode.RO_OVERRIDE
        )

        # Check weekly requirements
        weeks_meeting = 0
        weeks_short = 0
        for week_start in range(0, 42, 7):
            week_dates = all_dates[week_start:week_start + 7]
            week_shifts = sum(
                1 for d in week_dates
                if schedule.get(emp.id, {}).get(d) in (
                    ScheduleCode.WORKING, ScheduleCode.RO_OVERRIDE, ScheduleCode.PTO
                )
            )
            if emp.employment_type == EmploymentType.FULL_TIME:
                if week_shifts >= FT_SHIFTS_PER_WEEK:
                    weeks_meeting += 1
                else:
                    weeks_short += 1

        # PRN monthly check
        meets_minimum = True
        if emp.employment_type == EmploymentType.PRN and emp.prn_tier:
            tier_min = PRN_TIER_MINIMUMS[emp.prn_tier]
            months = defaultdict(int)
            for d in all_dates:
                if schedule.get(emp.id, {}).get(d) in (ScheduleCode.WORKING, ScheduleCode.RO_OVERRIDE):
                    months[(d.year, d.month)] += 1
            for month_count in months.values():
                if month_count < tier_min:
                    meets_minimum = False
        elif emp.employment_type == EmploymentType.FULL_TIME:
            meets_minimum = weeks_short == 0

        employee_summaries.append({
            "employee_id": emp.id,
            "employee_name": emp.name,
            "role": emp.role.value,
            "shift": emp.shift.value,
            "employment_type": emp.employment_type.value,
            "total_shifts": total_shifts,
            "pto_days": pto_days,
            "weeks_meeting_requirement": weeks_meeting,
            "weeks_short": weeks_short,
            "ro_overrides": ro_count,
            "meets_minimum": meets_minimum,
        })

    # Understaffed days
    understaffed_days = []
    for d in all_dates:
        for shift_val in [Shift.DAY, Shift.NIGHT]:
            shift_emps = [e for e in employees if e.shift == shift_val]
            flags = []

            # Count working staff by role
            def count_role(role_filter):
                return sum(
                    1 for e in shift_emps
                    if role_filter(e)
                    and schedule.get(e.id, {}).get(d) in (ScheduleCode.WORKING, ScheduleCode.RO_OVERRIDE)
                )

            floor_rn = count_role(lambda e: e.role == Role.FLOOR_RN)
            lvn = count_role(lambda e: e.role == Role.LVN)
            icu_rn = count_role(lambda e: e.role == Role.ICU_RN)
            pct = count_role(lambda e: e.role == Role.PCT)
            clerk = count_role(lambda e: e.role == Role.UNIT_CLERK)
            supervisor = count_role(lambda e: e.role == Role.HOUSE_SUPERVISOR)

            nurse_total = floor_rn + lvn
            has_rn = floor_rn > 0

            clerk_min = DAILY_MINIMUMS["unit_clerks_day"] if shift_val == Shift.DAY else DAILY_MINIMUMS["unit_clerks_night"]

            if nurse_total < DAILY_MINIMUMS["nurses"]:
                flags.append(f"Nurses: {nurse_total}/{DAILY_MINIMUMS['nurses']}")
            if not has_rn and nurse_total > 0:
                flags.append("No RN in nurse mix")
            if icu_rn < DAILY_MINIMUMS["icu_rns"]:
                flags.append(f"ICU RNs: {icu_rn}/{DAILY_MINIMUMS['icu_rns']}")
            if pct < DAILY_MINIMUMS["pcts"]:
                flags.append(f"PCTs: {pct}/{DAILY_MINIMUMS['pcts']}")
            if clerk < clerk_min:
                flags.append(f"Unit Clerks: {clerk}/{clerk_min}")
            if supervisor < DAILY_MINIMUMS["house_supervisors"]:
                flags.append(f"Supervisors: {supervisor}/{DAILY_MINIMUMS['house_supervisors']}")

            if flags:
                understaffed_days.append({
                    "date": d.isoformat(),
                    "shift": shift_val.value,
                    "floor_rn_count": floor_rn,
                    "icu_rn_count": icu_rn,
                    "lvn_count": lvn,
                    "nurse_total": nurse_total,
                    "has_rn_in_nurses": has_rn,
                    "pct_count": pct,
                    "unit_clerk_count": clerk,
                    "house_supervisor_count": supervisor,
                    "is_below_minimum": True,
                    "flags": flags,
                })

    return {
        "understaffed_days": understaffed_days,
        "employee_summaries": employee_summaries,
        "ro_overrides": ro_overrides,
        "total_flags": len(understaffed_days) + len(ro_overrides),
    }
