"""Central-time helpers.

The app runs in a UTC container (Railway). Any "what day is it" computation
done with a naive datetime.now()/utcnow()/date.today() rolls over at 00:00 UTC
— roughly 6-7 PM US/Central — so transactions, daily emails, dashboard "today"
figures and membership notices all jump a day early in the evening.

Use these helpers for every USER-FACING day boundary, date stamp, and
"today"-relative comparison. Do NOT use them to rewrite stored historical
timestamps — existing rows keep whatever they were saved with.

Naive (tz-stripped) values are returned on purpose: the rest of the codebase
does `.strftime("%Y-%m-%d")` and `+ timedelta(...)` arithmetic on naive
datetimes, and mixing naive/aware values raises TypeError.
"""

from datetime import date, datetime

import pytz

CENTRAL = pytz.timezone("America/Chicago")


def now_central() -> datetime:
    """Current wall-clock time in US/Central, as a naive datetime."""
    return datetime.now(CENTRAL).replace(tzinfo=None)


def today_central() -> date:
    """Current calendar date in US/Central."""
    return now_central().date()


def today_central_str() -> str:
    """Current US/Central date as 'YYYY-MM-DD'."""
    return now_central().strftime("%Y-%m-%d")
