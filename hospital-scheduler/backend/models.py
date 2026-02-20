"""
Data models for Hospital Staff Scheduling Tool.

Defines SQLAlchemy ORM models and Pydantic schemas for:
- Employees (staff roster with role, shift, employment type)
- Preferences (per-employee per-day scheduling preferences)
- ScheduleEntries (generated schedule assignments)
- SchedulePeriods (6-week scheduling windows)

v2 notes: Add relationships to User model for auth, audit trail fields
(created_by, modified_by), and soft-delete with timestamps.
"""

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import (
    Column, Integer, String, Date, DateTime, Boolean, Enum as SAEnum,
    ForeignKey, UniqueConstraint, Text
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class Role(str, Enum):
    ICU_RN = "ICU RN"
    FLOOR_RN = "Floor RN"
    LVN = "LVN"
    PCT = "PCT"
    UNIT_CLERK = "Unit Clerk"
    HOUSE_SUPERVISOR = "House Supervisor"


class Shift(str, Enum):
    DAY = "Day"
    NIGHT = "Night"


class EmploymentType(str, Enum):
    FULL_TIME = "Full-Time"
    PRN = "PRN"


class PRNTier(str, Enum):
    TIER_1 = "Tier 1"  # 6 shifts/month minimum
    TIER_2 = "Tier 2"  # 8 shifts/month minimum


class PreferenceCode(str, Enum):
    AVAILABLE = ""       # blank = available, no preference
    REQUEST_OFF = "RO"   # prefers not to work, CAN be scheduled
    PTO = "PTO"          # paid time off (FT only), counts as shift
    CANNOT_WORK = "X"    # do not schedule


class ScheduleCode(str, Enum):
    WORKING = "W"           # scheduled to work
    RO_OVERRIDE = "RO"      # request-off was overridden to work
    PTO = "PTO"             # paid time off (not working)
    CANNOT_WORK = "X"       # cannot work (not scheduled)
    CALLED_IN = "CI"        # employee called in (sick, etc.)
    CANCELED = "CX"         # shift canceled by us
    OFF = ""                # not scheduled, available day unused


# Display order for roles in the schedule grid
ROLE_DISPLAY_ORDER = [
    Role.ICU_RN,
    Role.FLOOR_RN,
    Role.LVN,
    Role.PCT,
    Role.UNIT_CLERK,
    Role.HOUSE_SUPERVISOR,
]


# ──────────────────────────────────────────────
# SQLAlchemy ORM Models
# ──────────────────────────────────────────────

class Employee(Base):
    """
    Staff member record.

    v2: Add hire_date, certifications, skills, contact info,
    linked user account for self-service portal.
    """
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    role = Column(SAEnum(Role), nullable=False)
    shift = Column(SAEnum(Shift), nullable=False)
    employment_type = Column(SAEnum(EmploymentType), nullable=False)
    prn_tier = Column(SAEnum(PRNTier), nullable=True)  # NULL for Full-Time
    max_weekly_shifts = Column(Integer, default=3, nullable=False)  # max shifts per week
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    preferences = relationship("Preference", back_populates="employee", cascade="all, delete-orphan")
    schedule_entries = relationship("ScheduleEntry", back_populates="employee", cascade="all, delete-orphan")


class SchedulePeriod(Base):
    """
    A 6-week scheduling window (42 days, Sunday-Saturday).

    v2: Add status workflow (draft, published, locked), approval tracking,
    version history for schedule revisions.
    """
    __tablename__ = "schedule_periods"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)          # e.g. "Mar 2 - Apr 12, 2026"
    start_date = Column(Date, nullable=False)            # must be a Sunday
    end_date = Column(Date, nullable=False)              # 41 days after start (Saturday)
    is_generated = Column(Boolean, default=False)        # has auto-scheduler run?
    generated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    preferences = relationship("Preference", back_populates="period", cascade="all, delete-orphan")
    schedule_entries = relationship("ScheduleEntry", back_populates="period", cascade="all, delete-orphan")


class Preference(Base):
    """
    Per-employee per-day preference code for a schedule period.

    Only non-blank preferences are stored (blank = available = no row).

    v2: Add employee self-service submission, approval workflow,
    submission deadline enforcement.
    """
    __tablename__ = "preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    period_id = Column(Integer, ForeignKey("schedule_periods.id"), nullable=False)
    date = Column(Date, nullable=False)
    code = Column(SAEnum(PreferenceCode), nullable=False)

    # Relationships
    employee = relationship("Employee", back_populates="preferences")
    period = relationship("SchedulePeriod", back_populates="preferences")

    __table_args__ = (
        UniqueConstraint("employee_id", "period_id", "date", name="uq_pref_emp_period_date"),
    )


class ScheduleEntry(Base):
    """
    Generated (or manually edited) schedule assignment per employee per day.

    v2: Add swap requests, call-in tracking, replacement assignment,
    audit log of all changes.
    """
    __tablename__ = "schedule_entries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    period_id = Column(Integer, ForeignKey("schedule_periods.id"), nullable=False)
    date = Column(Date, nullable=False)
    code = Column(SAEnum(ScheduleCode), nullable=False)
    is_manual_override = Column(Boolean, default=False)  # hand-edited after generation
    note = Column(Text, nullable=True)  # free-form note per cell

    # Relationships
    employee = relationship("Employee", back_populates="schedule_entries")
    period = relationship("SchedulePeriod", back_populates="schedule_entries")

    __table_args__ = (
        UniqueConstraint("employee_id", "period_id", "date", name="uq_sched_emp_period_date"),
    )


# ──────────────────────────────────────────────
# Pydantic Schemas (API request/response)
# ──────────────────────────────────────────────

class EmployeeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    role: Role
    shift: Shift
    employment_type: EmploymentType
    prn_tier: Optional[PRNTier] = None
    max_weekly_shifts: int = Field(default=3, ge=1, le=7)

class EmployeeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    role: Optional[Role] = None
    shift: Optional[Shift] = None
    employment_type: Optional[EmploymentType] = None
    prn_tier: Optional[PRNTier] = None
    max_weekly_shifts: Optional[int] = Field(None, ge=1, le=7)
    is_active: Optional[bool] = None

class EmployeeOut(BaseModel):
    id: int
    name: str
    role: Role
    shift: Shift
    employment_type: EmploymentType
    prn_tier: Optional[PRNTier]
    max_weekly_shifts: int
    is_active: bool

    class Config:
        from_attributes = True


class PreferenceSet(BaseModel):
    """Bulk set preferences for one employee for a period."""
    employee_id: int
    period_id: int
    # date string (YYYY-MM-DD) -> preference code (RO, PTO, X, or "" to clear)
    preferences: dict[str, str]


class PreferenceOut(BaseModel):
    employee_id: int
    date: date
    code: str

    class Config:
        from_attributes = True


class SchedulePeriodCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    start_date: date  # must be a Sunday


class SchedulePeriodOut(BaseModel):
    id: int
    name: str
    start_date: date
    end_date: date
    is_generated: bool
    generated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ScheduleEntryOut(BaseModel):
    employee_id: int
    date: date
    code: str
    is_manual_override: bool
    note: Optional[str] = None

    class Config:
        from_attributes = True


class ScheduleEntryUpdate(BaseModel):
    """Manual override of a single cell."""
    code: str  # W, RO, PTO, X, CI, CX, or "" (off)
    note: Optional[str] = None  # free-form note (None = no change)


class DailyStaffingSummary(BaseModel):
    """Per-day staffing counts for the summary panel."""
    date: date
    shift: Shift
    floor_rn_count: int
    icu_rn_count: int
    lvn_count: int
    nurse_total: int        # Floor RN + LVN (must be >= 7)
    has_rn_in_nurses: bool  # at least 1 RN in the nurse_total
    pct_count: int
    unit_clerk_count: int
    house_supervisor_count: int
    is_below_minimum: bool
    flags: list[str]


class EmployeeScheduleSummary(BaseModel):
    """Per-employee summary after generation."""
    employee_id: int
    employee_name: str
    role: Role
    shift: Shift
    employment_type: EmploymentType
    total_shifts: int
    weeks_meeting_requirement: int
    weeks_short: int
    ro_overrides: int
    meets_minimum: bool


class GenerationSummary(BaseModel):
    """Full summary returned after auto-schedule generation."""
    understaffed_days: list[DailyStaffingSummary]
    employee_summaries: list[EmployeeScheduleSummary]
    ro_overrides: list[dict]  # {employee_name, date, reason}
    total_flags: int


# ──────────────────────────────────────────────
# Constants - Daily Minimum Staffing Targets
# ──────────────────────────────────────────────

DAILY_MINIMUMS = {
    "nurses": 7,            # Floor RN + LVN combined (NOT ICU RNs)
    "icu_rns": 3,
    "pcts": 3,
    "house_supervisors": 1,
    "unit_clerks_day": 2,
    "unit_clerks_night": 1,
}

# Full-Time scheduling rules
FT_SHIFTS_PER_WEEK = 3
FT_MAX_CONSECUTIVE_DAYS = 5
MIN_REST_HOURS = 12

# PRN minimum shifts per month
PRN_TIER_MINIMUMS = {
    PRNTier.TIER_1: 6,
    PRNTier.TIER_2: 8,
}
