from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from teilauto.core.timeparse import parse_duration, parse_time

NOW = datetime(2026, 7, 12, 15, 0, tzinfo=timezone(timedelta(hours=2)))


def test_now():
    assert parse_time("now", now=NOW) == NOW


def test_hhmm_future_today():
    assert parse_time("16:30", now=NOW) == NOW.replace(hour=16, minute=30)


def test_hhmm_past_rolls_to_tomorrow():
    assert parse_time("09:00", now=NOW) == NOW.replace(hour=9, minute=0) + timedelta(days=1)


def test_today_prefix_stays_today_even_if_past():
    assert parse_time("today 09:00", now=NOW) == NOW.replace(hour=9, minute=0)


def test_tomorrow():
    expected = NOW.replace(hour=8, minute=15) + timedelta(days=1)
    assert parse_time("tomorrow 08:15", now=NOW) == expected


def test_iso_naive_gets_local_tz():
    dt = parse_time("2026-08-01 10:00", now=NOW)
    assert dt == datetime(2026, 8, 1, 10, 0, tzinfo=NOW.tzinfo)


def test_iso_with_tz_preserved():
    dt = parse_time("2026-08-01T10:00:00+00:00", now=NOW)
    assert dt.utcoffset() == timedelta(0)


def test_bad_time_raises():
    with pytest.raises(ValueError, match="Cannot parse time"):
        parse_time("banana", now=NOW)


def test_z_suffix_parses_as_utc():
    dt = parse_time("2026-08-01T10:00:00Z", now=NOW)
    assert dt.utcoffset() == timedelta(0)


def test_naive_iso_in_other_dst_season_gets_correct_offset():
    berlin_summer = datetime(2026, 7, 12, 15, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    dt = parse_time("2026-12-15 10:00", now=berlin_summer)
    assert dt.utcoffset() == timedelta(hours=1)  # CET in December, not CEST


def test_tomorrow_across_dst_end_gets_correct_offset():
    # DST ends 2026-10-25 in Europe/Berlin
    now = datetime(2026, 10, 24, 15, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    dt = parse_time("tomorrow 15:00", now=now)
    assert dt.utcoffset() == timedelta(hours=1)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("30m", timedelta(minutes=30)),
        ("2h", timedelta(hours=2)),
        ("1h30m", timedelta(hours=1, minutes=30)),
        ("90", timedelta(minutes=90)),
        ("45min", timedelta(minutes=45)),
    ],
)
def test_durations(text, expected):
    assert parse_duration(text) == expected


def test_bad_duration_raises():
    with pytest.raises(ValueError, match="Cannot parse duration"):
        parse_duration("soon")
