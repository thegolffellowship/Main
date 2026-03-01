"""
Hospital Staff Scheduling Tool - FastAPI Backend

REST API for managing employees, preferences, schedule periods,
and auto-generated schedules.

Local:  uvicorn main:app --reload --port 8000
Cloud:  gunicorn main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker
"""

import os
from pathlib import Path
from datetime import date, timedelta, datetime
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_

# Resolve frontend directory (works from backend/ or project root)
_backend_dir = Path(__file__).resolve().parent
_frontend_dir = _backend_dir.parent / "frontend"

from database import init_db, get_db
from models import (
    Employee, Preference, ScheduleEntry, SchedulePeriod,
    ScheduleVersion, ScheduleVersionEntry, ScheduleChangeLog,
    EmployeeCreate, EmployeeUpdate, EmployeeOut,
    PreferenceSet, PreferenceOut,
    SchedulePeriodCreate, SchedulePeriodOut,
    ScheduleEntryOut, ScheduleEntryUpdate,
    Role, Shift, EmploymentType, PreferenceCode, ScheduleCode,
    ROLE_DISPLAY_ORDER, DAILY_MINIMUMS,
)
from scheduler import generate_schedule
from seed import seed_database

app = FastAPI(title="Hospital Staff Scheduler", version="1.0.0")

# CORS for local development
# v2: Restrict origins to production domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    """Initialize database and seed sample data on first run."""
    init_db()
    from database import SessionLocal
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()


# ──────────────────────────────────────────────
# Serve Frontend
# ──────────────────────────────────────────────

app.mount("/static", StaticFiles(directory=str(_frontend_dir)), name="static")


@app.get("/")
def serve_frontend():
    """Serve the main HTML page."""
    return FileResponse(str(_frontend_dir / "index.html"))


# ──────────────────────────────────────────────
# Employee Endpoints
# v2: Add pagination, bulk import/export, search
# ──────────────────────────────────────────────

@app.get("/api/employees", response_model=list[EmployeeOut])
def list_employees(
    role: Optional[str] = None,
    shift: Optional[str] = None,
    employment_type: Optional[str] = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    """List employees with optional filters."""
    query = db.query(Employee)
    if active_only:
        query = query.filter(Employee.is_active == True)
    if role:
        query = query.filter(Employee.role == role)
    if shift:
        query = query.filter(Employee.shift == shift)
    if employment_type:
        query = query.filter(Employee.employment_type == employment_type)
    return query.order_by(Employee.role, Employee.name).all()


@app.post("/api/employees", response_model=EmployeeOut)
def create_employee(emp: EmployeeCreate, db: Session = Depends(get_db)):
    """Add a new employee to the roster."""
    if emp.employment_type == EmploymentType.PRN and not emp.prn_tier:
        raise HTTPException(400, "PRN employees must have a tier assigned")
    if emp.employment_type == EmploymentType.FULL_TIME and emp.prn_tier:
        raise HTTPException(400, "Full-Time employees cannot have a PRN tier")

    employee = Employee(**emp.model_dump())
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


@app.get("/api/employees/{employee_id}", response_model=EmployeeOut)
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    """Get a single employee by ID."""
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(404, "Employee not found")
    return emp


@app.put("/api/employees/{employee_id}", response_model=EmployeeOut)
def update_employee(employee_id: int, updates: EmployeeUpdate, db: Session = Depends(get_db)):
    """Edit an employee record."""
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(404, "Employee not found")

    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(emp, key, value)

    emp.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(emp)
    return emp


@app.delete("/api/employees/{employee_id}")
def deactivate_employee(employee_id: int, db: Session = Depends(get_db)):
    """Deactivate (soft-delete) an employee."""
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(404, "Employee not found")
    emp.is_active = False
    emp.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Employee deactivated"}


# ──────────────────────────────────────────────
# Schedule Period Endpoints
# v2: Add period locking, approval workflow
# ──────────────────────────────────────────────

@app.get("/api/periods", response_model=list[SchedulePeriodOut])
def list_periods(db: Session = Depends(get_db)):
    """List all schedule periods."""
    return db.query(SchedulePeriod).order_by(SchedulePeriod.start_date.desc()).all()


@app.post("/api/periods", response_model=SchedulePeriodOut)
def create_period(period: SchedulePeriodCreate, db: Session = Depends(get_db)):
    """Create a new 6-week schedule period. Start date must be a Sunday."""
    if period.start_date.weekday() != 6:
        raise HTTPException(400, "Start date must be a Sunday")

    end_date = period.start_date + timedelta(days=41)
    sp = SchedulePeriod(
        name=period.name,
        start_date=period.start_date,
        end_date=end_date,
    )
    db.add(sp)
    db.commit()
    db.refresh(sp)
    return sp


@app.get("/api/periods/{period_id}", response_model=SchedulePeriodOut)
def get_period(period_id: int, db: Session = Depends(get_db)):
    """Get a single schedule period."""
    period = db.query(SchedulePeriod).filter(SchedulePeriod.id == period_id).first()
    if not period:
        raise HTTPException(404, "Schedule period not found")
    return period


# ──────────────────────────────────────────────
# Preference Endpoints
# v2: Add submission deadlines, approval workflow,
#     employee self-service submission
# ──────────────────────────────────────────────

@app.get("/api/preferences/{period_id}")
def get_all_preferences(period_id: int, db: Session = Depends(get_db)):
    """Get all preferences for a period, keyed by employee_id."""
    prefs = db.query(Preference).filter(Preference.period_id == period_id).all()
    result = {}
    for p in prefs:
        emp_id = str(p.employee_id)
        if emp_id not in result:
            result[emp_id] = {}
        result[emp_id][p.date.isoformat()] = p.code.value if hasattr(p.code, 'value') else p.code
    return result


@app.get("/api/preferences/{period_id}/{employee_id}")
def get_employee_preferences(period_id: int, employee_id: int, db: Session = Depends(get_db)):
    """Get preferences for one employee in a period."""
    prefs = db.query(Preference).filter(
        Preference.period_id == period_id,
        Preference.employee_id == employee_id,
    ).all()
    result = {}
    for p in prefs:
        result[p.date.isoformat()] = p.code.value if hasattr(p.code, 'value') else p.code
    return result


@app.post("/api/preferences")
def set_preferences(pref_set: PreferenceSet, db: Session = Depends(get_db)):
    """
    Bulk set/update preferences for one employee for a period.
    Pass date->code pairs. Empty string or missing date = available (delete pref).
    """
    # Validate employee and period exist
    emp = db.query(Employee).filter(Employee.id == pref_set.employee_id).first()
    if not emp:
        raise HTTPException(404, "Employee not found")
    period = db.query(SchedulePeriod).filter(SchedulePeriod.id == pref_set.period_id).first()
    if not period:
        raise HTTPException(404, "Schedule period not found")

    # Delete existing preferences for this employee/period
    db.query(Preference).filter(
        Preference.employee_id == pref_set.employee_id,
        Preference.period_id == pref_set.period_id,
    ).delete()

    # Insert new non-blank preferences
    for date_str, code_str in pref_set.preferences.items():
        if not code_str or code_str == "":
            continue  # blank = available, don't store
        try:
            d = date.fromisoformat(date_str)
        except ValueError:
            raise HTTPException(400, f"Invalid date format: {date_str}")

        # Validate PTO is only for FT employees
        if code_str == "PTO" and emp.employment_type != EmploymentType.FULL_TIME:
            raise HTTPException(400, f"PTO is only available for Full-Time employees")

        try:
            pref_code = PreferenceCode(code_str)
        except ValueError:
            raise HTTPException(400, f"Invalid preference code: {code_str}")

        pref = Preference(
            employee_id=pref_set.employee_id,
            period_id=pref_set.period_id,
            date=d,
            code=pref_code,
        )
        db.add(pref)

    db.commit()
    return {"message": "Preferences saved"}


# ──────────────────────────────────────────────
# Schedule Endpoints
# v2: Add schedule versioning, diff view, undo support
# ──────────────────────────────────────────────

@app.get("/api/schedule/{period_id}")
def get_schedule(
    period_id: int,
    shift: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Get the full schedule grid for a period.
    Returns entries grouped by employee with role ordering.
    """
    period = db.query(SchedulePeriod).filter(SchedulePeriod.id == period_id).first()
    if not period:
        raise HTTPException(404, "Schedule period not found")

    entries = db.query(ScheduleEntry).filter(
        ScheduleEntry.period_id == period_id
    ).all()

    # Get employees
    emp_query = db.query(Employee).filter(Employee.is_active == True)
    if shift:
        emp_query = emp_query.filter(Employee.shift == shift)
    employees = emp_query.all()

    emp_map = {e.id: e for e in employees}

    # Build grid: group by employee
    grid = {}
    for entry in entries:
        if entry.employee_id not in emp_map:
            continue
        emp_id = str(entry.employee_id)
        if emp_id not in grid:
            grid[emp_id] = {}
        code_val = entry.code.value if hasattr(entry.code, 'value') else entry.code
        grid[emp_id][entry.date.isoformat()] = {
            "code": code_val,
            "is_manual_override": entry.is_manual_override,
            "note": entry.note or "",
        }

    # Build employee list in role display order
    role_order = {r: i for i, r in enumerate(ROLE_DISPLAY_ORDER)}
    sorted_employees = sorted(employees, key=lambda e: (role_order.get(e.role, 99), e.name))

    employee_list = []
    for e in sorted_employees:
        employee_list.append({
            "id": e.id,
            "name": e.name,
            "role": e.role.value if hasattr(e.role, 'value') else e.role,
            "shift": e.shift.value if hasattr(e.shift, 'value') else e.shift,
            "employment_type": e.employment_type.value if hasattr(e.employment_type, 'value') else e.employment_type,
            "prn_tier": (e.prn_tier.value if e.prn_tier and hasattr(e.prn_tier, 'value') else e.prn_tier),
            "max_weekly_shifts": e.max_weekly_shifts,
        })

    return {
        "period": {
            "id": period.id,
            "name": period.name,
            "start_date": period.start_date.isoformat(),
            "end_date": period.end_date.isoformat(),
            "is_generated": period.is_generated,
        },
        "employees": employee_list,
        "grid": grid,
    }


@app.put("/api/schedule/{period_id}/{employee_id}/{date_str}")
def update_schedule_entry(
    period_id: int,
    employee_id: int,
    date_str: str,
    update: ScheduleEntryUpdate,
    db: Session = Depends(get_db),
):
    """
    Manually override a single schedule cell.
    Marks the entry as a manual override.
    """
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(400, "Invalid date format")

    entry = db.query(ScheduleEntry).filter(
        ScheduleEntry.period_id == period_id,
        ScheduleEntry.employee_id == employee_id,
        ScheduleEntry.date == d,
    ).first()

    try:
        code = ScheduleCode(update.code)
    except ValueError:
        raise HTTPException(400, f"Invalid schedule code: {update.code}")

    # Log the change for undo/redo
    old_code = ""
    old_note = None
    if entry:
        old_code = entry.code.value if hasattr(entry.code, 'value') else entry.code
        old_note = entry.note

    change_log = ScheduleChangeLog(
        period_id=period_id,
        employee_id=employee_id,
        date=d,
        old_code=old_code,
        new_code=update.code,
        old_note=old_note,
        new_note=update.note,
    )
    db.add(change_log)

    # Clear any "undone" entries ahead of this point (new branch in history)
    db.query(ScheduleChangeLog).filter(
        ScheduleChangeLog.period_id == period_id,
        ScheduleChangeLog.is_undone == True,
    ).delete()

    if entry:
        entry.code = code
        entry.is_manual_override = True
        if update.note is not None:
            entry.note = update.note if update.note else None
    else:
        entry = ScheduleEntry(
            employee_id=employee_id,
            period_id=period_id,
            date=d,
            code=code,
            is_manual_override=True,
            note=update.note if update.note else None,
        )
        db.add(entry)

    db.commit()
    return {"message": "Schedule entry updated"}


# ──────────────────────────────────────────────
# Auto-Scheduler Endpoint
# v2: Run as background task with progress tracking,
#     add configuration parameters
# ──────────────────────────────────────────────

@app.post("/api/schedule/{period_id}/generate")
def generate(period_id: int, db: Session = Depends(get_db)):
    """
    Run the auto-scheduler for a 6-week period.
    Saves a snapshot of the current schedule before generating a new one.
    """
    period = db.query(SchedulePeriod).filter(SchedulePeriod.id == period_id).first()
    if not period:
        raise HTTPException(404, "Schedule period not found")

    # Save current schedule as a version before overwriting
    _save_schedule_version(db, period, label="Auto-save before generate")

    # Clear undo history for this period (new generation = fresh start)
    db.query(ScheduleChangeLog).filter(ScheduleChangeLog.period_id == period_id).delete()

    summary = generate_schedule(db, period)

    # Save the newly generated schedule as a version too
    _save_schedule_version(db, period, label="Generated")

    return summary


# ──────────────────────────────────────────────
# Daily Staffing Summary Endpoint
# v2: Add trend charts, historical comparison
# ──────────────────────────────────────────────

@app.get("/api/schedule/{period_id}/daily-summary")
def daily_summary(period_id: int, db: Session = Depends(get_db)):
    """
    Get daily staffing counts for each shift across the period.
    Used for the totals row and flag highlighting.
    """
    period = db.query(SchedulePeriod).filter(SchedulePeriod.id == period_id).first()
    if not period:
        raise HTTPException(404, "Schedule period not found")

    entries = db.query(ScheduleEntry).filter(
        ScheduleEntry.period_id == period_id
    ).all()

    employees = db.query(Employee).filter(Employee.is_active == True).all()
    emp_map = {e.id: e for e in employees}

    all_dates = [period.start_date + timedelta(days=i) for i in range(42)]

    results = []
    for d in all_dates:
        for shift_val in [Shift.DAY, Shift.NIGHT]:
            counts = {"floor_rn": 0, "icu_rn": 0, "lvn": 0, "pct": 0, "unit_clerk": 0, "house_supervisor": 0}

            for entry in entries:
                if entry.date != d:
                    continue
                emp = emp_map.get(entry.employee_id)
                if not emp or emp.shift != shift_val:
                    continue
                code_val = entry.code.value if hasattr(entry.code, 'value') else entry.code
                if code_val not in ("W", "RO"):  # CI and CX do NOT count as working
                    continue

                role_val = emp.role.value if hasattr(emp.role, 'value') else emp.role
                if role_val == "Floor RN":
                    counts["floor_rn"] += 1
                elif role_val == "ICU RN":
                    counts["icu_rn"] += 1
                elif role_val == "LVN":
                    counts["lvn"] += 1
                elif role_val == "PCT":
                    counts["pct"] += 1
                elif role_val == "Unit Clerk":
                    counts["unit_clerk"] += 1
                elif role_val == "House Supervisor":
                    counts["house_supervisor"] += 1

            nurse_total = counts["floor_rn"] + counts["lvn"]
            clerk_min = DAILY_MINIMUMS["unit_clerks_day"] if shift_val == Shift.DAY else DAILY_MINIMUMS["unit_clerks_night"]

            flags = []
            if nurse_total < DAILY_MINIMUMS["nurses"]:
                flags.append(f"Nurses: {nurse_total}/{DAILY_MINIMUMS['nurses']}")
            if counts["floor_rn"] == 0 and nurse_total > 0:
                flags.append("No RN in nurse mix")
            if counts["icu_rn"] < DAILY_MINIMUMS["icu_rns"]:
                flags.append(f"ICU RNs: {counts['icu_rn']}/{DAILY_MINIMUMS['icu_rns']}")
            if counts["pct"] < DAILY_MINIMUMS["pcts"]:
                flags.append(f"PCTs: {counts['pct']}/{DAILY_MINIMUMS['pcts']}")
            if counts["unit_clerk"] < clerk_min:
                flags.append(f"Unit Clerks: {counts['unit_clerk']}/{clerk_min}")
            if counts["house_supervisor"] < DAILY_MINIMUMS["house_supervisors"]:
                flags.append(f"Supervisors: {counts['house_supervisor']}/{DAILY_MINIMUMS['house_supervisors']}")

            results.append({
                "date": d.isoformat(),
                "shift": shift_val.value,
                "floor_rn_count": counts["floor_rn"],
                "icu_rn_count": counts["icu_rn"],
                "lvn_count": counts["lvn"],
                "nurse_total": nurse_total,
                "has_rn_in_nurses": counts["floor_rn"] > 0,
                "pct_count": counts["pct"],
                "unit_clerk_count": counts["unit_clerk"],
                "house_supervisor_count": counts["house_supervisor"],
                "is_below_minimum": len(flags) > 0,
                "flags": flags,
            })

    return results


# ──────────────────────────────────────────────
# Helper: Save Schedule Version
# ──────────────────────────────────────────────

def _save_schedule_version(db: Session, period: SchedulePeriod, label: str = None):
    """Save current schedule entries as a version snapshot."""
    entries = db.query(ScheduleEntry).filter(
        ScheduleEntry.period_id == period.id
    ).all()

    if not entries:
        return  # Nothing to save

    # Determine next version number
    max_ver = db.query(ScheduleVersion).filter(
        ScheduleVersion.period_id == period.id
    ).count()
    next_ver = max_ver + 1

    version = ScheduleVersion(
        period_id=period.id,
        version_number=next_ver,
        label=label or f"v{next_ver}",
    )
    db.add(version)
    db.flush()

    # Copy all current entries into the version
    for entry in entries:
        code_val = entry.code.value if hasattr(entry.code, 'value') else entry.code
        ve = ScheduleVersionEntry(
            version_id=version.id,
            employee_id=entry.employee_id,
            date=entry.date,
            code=code_val,
            note=entry.note,
        )
        db.add(ve)

    db.commit()
    return version


# ──────────────────────────────────────────────
# Save Schedule (explicit save button)
# ──────────────────────────────────────────────

@app.post("/api/schedule/{period_id}/save")
def save_schedule(period_id: int, label: Optional[str] = Query(None), db: Session = Depends(get_db)):
    """Explicitly save the current schedule as a named version."""
    period = db.query(SchedulePeriod).filter(SchedulePeriod.id == period_id).first()
    if not period:
        raise HTTPException(404, "Schedule period not found")

    version = _save_schedule_version(db, period, label=label or None)
    if not version:
        raise HTTPException(400, "No schedule entries to save")

    return {
        "message": "Schedule saved",
        "version_number": version.version_number,
        "label": version.label,
    }


# ──────────────────────────────────────────────
# Schedule Versions (list / restore)
# ──────────────────────────────────────────────

@app.get("/api/schedule/{period_id}/versions")
def list_versions(period_id: int, db: Session = Depends(get_db)):
    """List all saved schedule versions for a period."""
    versions = db.query(ScheduleVersion).filter(
        ScheduleVersion.period_id == period_id
    ).order_by(ScheduleVersion.version_number.desc()).all()

    return [{
        "id": v.id,
        "version_number": v.version_number,
        "label": v.label,
        "created_at": v.created_at.isoformat() if v.created_at else None,
    } for v in versions]


@app.post("/api/schedule/{period_id}/versions/{version_id}/restore")
def restore_version(period_id: int, version_id: int, db: Session = Depends(get_db)):
    """Restore a previously saved schedule version."""
    version = db.query(ScheduleVersion).filter(
        ScheduleVersion.id == version_id,
        ScheduleVersion.period_id == period_id,
    ).first()
    if not version:
        raise HTTPException(404, "Version not found")

    # Save current schedule before restoring
    period = db.query(SchedulePeriod).filter(SchedulePeriod.id == period_id).first()
    _save_schedule_version(db, period, label="Auto-save before restore")

    # Delete current entries
    db.query(ScheduleEntry).filter(ScheduleEntry.period_id == period_id).delete()

    # Restore entries from the version
    for ve in version.entries:
        try:
            code = ScheduleCode(ve.code)
        except ValueError:
            code = ScheduleCode.OFF
        entry = ScheduleEntry(
            employee_id=ve.employee_id,
            period_id=period_id,
            date=ve.date,
            code=code,
            is_manual_override=True,
            note=ve.note,
        )
        db.add(entry)

    # Clear undo log
    db.query(ScheduleChangeLog).filter(ScheduleChangeLog.period_id == period_id).delete()
    db.commit()

    return {"message": f"Restored version {version.version_number}: {version.label}"}


# ──────────────────────────────────────────────
# Undo / Redo
# ──────────────────────────────────────────────

@app.post("/api/schedule/{period_id}/undo")
def undo_change(period_id: int, db: Session = Depends(get_db)):
    """Undo the most recent schedule cell change."""
    # Find last non-undone change
    change = db.query(ScheduleChangeLog).filter(
        ScheduleChangeLog.period_id == period_id,
        ScheduleChangeLog.is_undone == False,
    ).order_by(ScheduleChangeLog.id.desc()).first()

    if not change:
        raise HTTPException(400, "Nothing to undo")

    # Apply the old values
    entry = db.query(ScheduleEntry).filter(
        ScheduleEntry.period_id == period_id,
        ScheduleEntry.employee_id == change.employee_id,
        ScheduleEntry.date == change.date,
    ).first()

    if change.old_code == "":
        # Was empty before, delete the entry
        if entry:
            db.delete(entry)
    else:
        try:
            old_code = ScheduleCode(change.old_code)
        except ValueError:
            old_code = ScheduleCode.OFF

        if entry:
            entry.code = old_code
            entry.note = change.old_note
        else:
            entry = ScheduleEntry(
                employee_id=change.employee_id,
                period_id=period_id,
                date=change.date,
                code=old_code,
                is_manual_override=True,
                note=change.old_note,
            )
            db.add(entry)

    change.is_undone = True
    db.commit()

    return {
        "message": "Undone",
        "employee_id": change.employee_id,
        "date": change.date.isoformat(),
        "restored_code": change.old_code,
        "restored_note": change.old_note or "",
    }


@app.post("/api/schedule/{period_id}/redo")
def redo_change(period_id: int, db: Session = Depends(get_db)):
    """Redo the most recently undone change."""
    # Find oldest undone change
    change = db.query(ScheduleChangeLog).filter(
        ScheduleChangeLog.period_id == period_id,
        ScheduleChangeLog.is_undone == True,
    ).order_by(ScheduleChangeLog.id.asc()).first()

    if not change:
        raise HTTPException(400, "Nothing to redo")

    # Apply the new values
    entry = db.query(ScheduleEntry).filter(
        ScheduleEntry.period_id == period_id,
        ScheduleEntry.employee_id == change.employee_id,
        ScheduleEntry.date == change.date,
    ).first()

    if change.new_code == "":
        if entry:
            db.delete(entry)
    else:
        try:
            new_code = ScheduleCode(change.new_code)
        except ValueError:
            new_code = ScheduleCode.OFF

        if entry:
            entry.code = new_code
            if change.new_note is not None:
                entry.note = change.new_note if change.new_note else None
        else:
            entry = ScheduleEntry(
                employee_id=change.employee_id,
                period_id=period_id,
                date=change.date,
                code=new_code,
                is_manual_override=True,
                note=change.new_note if change.new_note else None,
            )
            db.add(entry)

    change.is_undone = False
    db.commit()

    return {
        "message": "Redone",
        "employee_id": change.employee_id,
        "date": change.date.isoformat(),
        "restored_code": change.new_code,
        "restored_note": change.new_note or "",
    }


# ──────────────────────────────────────────────
# Employee Report
# ──────────────────────────────────────────────

@app.get("/api/report/employee/{employee_id}/{period_id}")
def employee_report(employee_id: int, period_id: int, db: Session = Depends(get_db)):
    """
    Pull a detailed report for a single employee for a given period.
    Includes: all schedule entries, totals by code, weekly breakdown.
    """
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(404, "Employee not found")

    period = db.query(SchedulePeriod).filter(SchedulePeriod.id == period_id).first()
    if not period:
        raise HTTPException(404, "Period not found")

    entries = db.query(ScheduleEntry).filter(
        ScheduleEntry.employee_id == employee_id,
        ScheduleEntry.period_id == period_id,
    ).order_by(ScheduleEntry.date).all()

    all_dates = [period.start_date + timedelta(days=i) for i in range(42)]

    # Build daily detail
    daily_detail = []
    code_counts = {}
    for d in all_dates:
        entry = next((e for e in entries if e.date == d), None)
        code_val = ""
        note = ""
        if entry:
            code_val = entry.code.value if hasattr(entry.code, 'value') else entry.code
            note = entry.note or ""
            code_counts[code_val] = code_counts.get(code_val, 0) + 1

        daily_detail.append({
            "date": d.isoformat(),
            "day": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][d.weekday()],
            "code": code_val,
            "note": note,
        })

    # Weekly breakdown
    weekly = []
    for week_idx in range(6):
        week_start = week_idx * 7
        week_dates = all_dates[week_start:week_start + 7]
        shifts = sum(1 for d in week_dates
                     if any(e.date == d and (e.code.value if hasattr(e.code, 'value') else e.code) in ('W', 'RO')
                            for e in entries))
        ci_count = sum(1 for d in week_dates
                       if any(e.date == d and (e.code.value if hasattr(e.code, 'value') else e.code) == 'CI'
                              for e in entries))
        lco_count = sum(1 for d in week_dates
                        if any(e.date == d and (e.code.value if hasattr(e.code, 'value') else e.code) == 'LCO'
                               for e in entries))
        lci_count = sum(1 for d in week_dates
                        if any(e.date == d and (e.code.value if hasattr(e.code, 'value') else e.code) == 'LCI'
                               for e in entries))
        weekly.append({
            "week": week_idx + 1,
            "start_date": week_dates[0].isoformat(),
            "end_date": week_dates[-1].isoformat(),
            "shifts_worked": shifts,
            "call_ins": ci_count,
            "late_clock_offs": lco_count,
            "late_clock_ins": lci_count,
        })

    total_shifts = code_counts.get("W", 0) + code_counts.get("RO", 0)

    return {
        "employee": {
            "id": emp.id,
            "name": emp.name,
            "role": emp.role.value if hasattr(emp.role, 'value') else emp.role,
            "shift": emp.shift.value if hasattr(emp.shift, 'value') else emp.shift,
            "employment_type": emp.employment_type.value if hasattr(emp.employment_type, 'value') else emp.employment_type,
        },
        "period": {
            "name": period.name,
            "start_date": period.start_date.isoformat(),
            "end_date": period.end_date.isoformat(),
        },
        "total_shifts_worked": total_shifts,
        "code_counts": code_counts,
        "weekly_breakdown": weekly,
        "daily_detail": daily_detail,
    }
