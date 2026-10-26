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


def to_central(value) -> datetime | None:
    """Read a STORED timestamp (naive UTC, the way every datetime column in
    this database is written) as US/Central wall-clock, naive.

    For deriving a user-facing DAY from a stored timestamp. Kerry texts
    prospects in the evening, so a 10 PM Central touch is stored as the
    next day in UTC — taking date() straight off the stored value puts
    the follow-up a day late. Accepts a datetime or a 'YYYY-MM-DD
    HH:MM:SS' string; returns None for anything unparseable.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip().replace("T", " ")[:19]
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        else:
            return None
    return (pytz.utc.localize(dt.replace(tzinfo=None))
            .astimezone(CENTRAL).replace(tzinfo=None))


# ── 12-hour display (Kerry 2026-10-26, CoS #2325: "Please don't use Military
# Time"). Every time a member, manager or course READS is 12-hour with AM/PM.
# Display only: stored values, cron strings, logs, ISO API stamps and sort
# keys stay 24-hour. The JS twin is static/js/time12.js (window.tgfTime12).
import re as _re

_HM = _re.compile(r"(?<![\d:])(\d{1,2}):(\d{2})(?::\d{2}(?:\.\d+)?)?(?![\d:])(?!\s*[AaPp]\.?[Mm])")


def _hm12(h: int, mm: str) -> str:
    return f"{h % 12 or 12}:{mm} {'PM' if h >= 12 else 'AM'}"


def clock12(value) -> str:
    """'16:30' (or a datetime) -> '4:30 PM'. A value already in 12-hour form,
    or anything that is not a bare clock time, comes back unchanged."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return _hm12(value.hour, f"{value.minute:02d}")
    s = str(value).strip()
    m = _re.fullmatch(r"(\d{1,2}):(\d{2})(?::\d{2})?", s)
    if not m or int(m.group(1)) > 23:
        return s
    return _hm12(int(m.group(1)), m.group(2))


def stamp12(value) -> str:
    """'2026-10-26 15:40' (or the ISO 'T' form, or a datetime) ->
    '2026-10-26 3:40 PM'. Every HH:MM in the text not already followed by
    AM/PM is converted; the rest of the text is kept."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return f"{value.strftime('%Y-%m-%d')} {_hm12(value.hour, f'{value.minute:02d}')}"
    s = _re.sub(r"^(\d{4}-\d{2}-\d{2})T", r"\1 ", str(value))

    def _sub(m):
        h = int(m.group(1))
        return m.group(0) if h > 23 else _hm12(h, m.group(2))
    return _HM.sub(_sub, s)
