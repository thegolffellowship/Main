"""
Seed data: 10 sample employees across different roles and shifts
so the interface is not empty on first launch.

Also creates a default 6-week schedule period starting from the
next upcoming Sunday.

v2: Add more comprehensive test data, realistic preference patterns.
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from models import Employee, SchedulePeriod, Role, Shift, EmploymentType, PRNTier


def seed_database(db: Session):
    """Insert sample employees and a schedule period if DB is empty."""
    existing = db.query(Employee).count()
    if existing > 0:
        return  # Already seeded

    employees = [
        # Day Shift
        Employee(
            name="Sarah Johnson",
            role=Role.ICU_RN,
            shift=Shift.DAY,
            employment_type=EmploymentType.FULL_TIME,
        ),
        Employee(
            name="Michael Chen",
            role=Role.ICU_RN,
            shift=Shift.DAY,
            employment_type=EmploymentType.FULL_TIME,
        ),
        Employee(
            name="Lisa Rodriguez",
            role=Role.FLOOR_RN,
            shift=Shift.DAY,
            employment_type=EmploymentType.FULL_TIME,
        ),
        Employee(
            name="James Williams",
            role=Role.FLOOR_RN,
            shift=Shift.DAY,
            employment_type=EmploymentType.FULL_TIME,
        ),
        Employee(
            name="Emily Davis",
            role=Role.LVN,
            shift=Shift.DAY,
            employment_type=EmploymentType.FULL_TIME,
        ),
        Employee(
            name="Robert Martinez",
            role=Role.PCT,
            shift=Shift.DAY,
            employment_type=EmploymentType.FULL_TIME,
        ),
        Employee(
            name="Amanda Thompson",
            role=Role.UNIT_CLERK,
            shift=Shift.DAY,
            employment_type=EmploymentType.FULL_TIME,
        ),
        Employee(
            name="David Wilson",
            role=Role.HOUSE_SUPERVISOR,
            shift=Shift.DAY,
            employment_type=EmploymentType.FULL_TIME,
        ),
        # Night Shift
        Employee(
            name="Jennifer Brown",
            role=Role.ICU_RN,
            shift=Shift.NIGHT,
            employment_type=EmploymentType.FULL_TIME,
        ),
        Employee(
            name="Kevin Garcia",
            role=Role.FLOOR_RN,
            shift=Shift.NIGHT,
            employment_type=EmploymentType.PRN,
            prn_tier=PRNTier.TIER_1,
        ),
    ]

    db.add_all(employees)

    # Create a schedule period starting next Sunday
    today = date.today()
    days_until_sunday = (6 - today.weekday()) % 7
    if days_until_sunday == 0:
        next_sunday = today
    else:
        next_sunday = today + timedelta(days=days_until_sunday)

    end_date = next_sunday + timedelta(days=41)
    period_name = f"{next_sunday.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}"

    period = SchedulePeriod(
        name=period_name,
        start_date=next_sunday,
        end_date=end_date,
    )
    db.add(period)

    db.commit()
