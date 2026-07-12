from __future__ import annotations

import re
from datetime import datetime, timedelta

_HHMM = re.compile(r"(?:(today|tomorrow)\s+)?(\d{1,2}):(\d{2})")
_DURATION = re.compile(r"(?:(\d+)\s*h)?\s*(?:(\d+)\s*m(?:in)?)?")


def parse_time(text: str, *, now: datetime | None = None) -> datetime:
    """Parse a user-supplied time into a tz-aware local datetime.

    Accepts: 'now', 'HH:MM', 'today HH:MM', 'tomorrow HH:MM', ISO-8601.
    A bare 'HH:MM' more than a minute in the past means tomorrow.
    """
    now = now or datetime.now().astimezone()
    t = text.strip().lower()
    if t == "now":
        return now
    m = _HHMM.fullmatch(t)
    if m:
        day, hh, mm = m.group(1), int(m.group(2)), int(m.group(3))
        if hh > 23 or mm > 59:
            raise ValueError(f"Cannot parse time: {text!r} (hour 0-23, minute 0-59)")
        candidate = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if day == "tomorrow":
            candidate += timedelta(days=1)
        elif day is None and candidate <= now - timedelta(minutes=1):
            candidate += timedelta(days=1)
        return candidate
    try:
        dt = datetime.fromisoformat(text.strip())
    except ValueError:
        raise ValueError(
            f"Cannot parse time: {text!r}. Try 'now', '14:30', 'tomorrow 09:00' or ISO-8601."
        ) from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=now.tzinfo)
    return dt


def parse_duration(text: str) -> timedelta:
    """Parse '30m', '2h', '1h30m', '45min' or a bare number of minutes."""
    t = text.strip().lower()
    if t.isdigit():
        return timedelta(minutes=int(t))
    m = _DURATION.fullmatch(t)
    if not m or (m.group(1) is None and m.group(2) is None):
        raise ValueError(f"Cannot parse duration: {text!r}. Try '30m', '2h' or '1h30m'.")
    return timedelta(hours=int(m.group(1) or 0), minutes=int(m.group(2) or 0))
