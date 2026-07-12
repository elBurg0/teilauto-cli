from __future__ import annotations

import re
from datetime import datetime, timedelta

_HHMM = re.compile(r"(?:(today|tomorrow)\s+)?(\d{1,2}):(\d{2})")
_DURATION = re.compile(r"(?:(\d+)\s*h)?\s*(?:(\d+)\s*m(?:in)?)?")


def _hhmm_candidate(base: datetime, hh: int, mm: int, day: str | None) -> datetime:
    """Compute the HH:MM candidate relative to `base` (naive or aware alike).

    Only field replacement and timedelta arithmetic are used here, both of
    which are tzinfo-agnostic, so this helper works the same whether `base`
    is a naive wall-clock datetime or an aware one.
    """
    candidate = base.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if day == "tomorrow" or (day is None and candidate <= base - timedelta(minutes=1)):
        candidate += timedelta(days=1)
    return candidate


def parse_time(text: str, *, now: datetime | None = None) -> datetime:
    """Parse a user-supplied time into a tz-aware local datetime.

    Accepts: 'now', 'HH:MM', 'today HH:MM', 'tomorrow HH:MM', ISO-8601
    (a trailing 'Z'/'z' is accepted as shorthand for '+00:00').
    A bare 'HH:MM' more than a minute in the past means tomorrow.

    DST handling:
    - If `now` is passed explicitly (as tests do), its `tzinfo` is reused
      as-is via `replace(tzinfo=...)`/timedelta arithmetic. If that tzinfo
      is a real `ZoneInfo`, the UTC offset self-corrects for whatever date
      the result lands on, because `ZoneInfo.utcoffset()` is computed lazily
      from the datetime's own fields rather than baked in at construction
      time. A fixed-offset tzinfo (e.g. `timezone(timedelta(hours=2))`) has
      no such self-correction and is applied unchanged, by design (tests
      rely on this).
    - If `now` is NOT passed (real CLI usage), `datetime.now()` has no
      built-in notion of "the system timezone on some other date", so we
      never bake in a fixed offset up front. Instead we do the field
      replacement / rollover arithmetic on a *naive* wall-clock datetime and
      only localize the final naive candidate via `naive.astimezone()`,
      which asks the system for the correct (DST-aware) offset for that
      candidate's own date.
    """
    explicit_now = now is not None
    now = now if explicit_now else datetime.now().astimezone()
    stripped = text.strip()
    t = stripped.lower()
    if t == "now":
        return now
    m = _HHMM.fullmatch(t)
    if m:
        day, hh, mm = m.group(1), int(m.group(2)), int(m.group(3))
        if hh > 23 or mm > 59:
            raise ValueError(f"Cannot parse time: {text!r} (hour 0-23, minute 0-59)")
        if explicit_now:
            return _hhmm_candidate(now, hh, mm, day)
        return _hhmm_candidate(datetime.now(), hh, mm, day).astimezone()
    iso_text = stripped
    if iso_text.endswith(("Z", "z")):
        iso_text = iso_text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(iso_text)
    except ValueError:
        raise ValueError(
            f"Cannot parse time: {text!r}. Try 'now', '14:30', 'tomorrow 09:00' or ISO-8601."
        ) from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=now.tzinfo) if explicit_now else dt.astimezone()
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
