from __future__ import annotations

from datetime import datetime

import rich_click as click

from teilauto.core.config import Settings
from teilauto.core.timeparse import parse_duration, parse_time


def json_option(f):
    return click.option("--json", "as_json", is_flag=True, help="Output machine-readable JSON.")(f)


def location_options(f):
    f = click.option(
        "--radius",
        "radius_m",
        type=int,
        default=None,
        metavar="METRES",
        help="Search radius in metres (default: config).",
    )(f)
    f = click.option("--lng", type=float, default=None, help="Longitude (default: config).")(f)
    f = click.option("--lat", type=float, default=None, help="Latitude (default: config).")(f)
    return f


def window_options(f):
    f = click.option(
        "--until",
        "until_text",
        default=None,
        metavar="TIME",
        help="Window end, e.g. '18:00' or 'tomorrow 09:00'.",
    )(f)
    f = click.option(
        "--for",
        "duration_text",
        default=None,
        metavar="DURATION",
        help="Window length, e.g. '30m', '2h', '1h30m'.",
    )(f)
    f = click.option(
        "--from",
        "start_text",
        default="now",
        metavar="TIME",
        show_default=True,
        help="Window start, e.g. 'now', '14:30', 'tomorrow 09:00'.",
    )(f)
    return f


def resolve_location(
    settings: Settings, lat: float | None, lng: float | None, radius_m: int | None
) -> tuple[float, float, int]:
    return (
        settings.lat if lat is None else lat,
        settings.lng if lng is None else lng,
        settings.radius_m if radius_m is None else radius_m,
    )


def resolve_window(
    start_text: str,
    duration_text: str | None,
    until_text: str | None,
    *,
    default_minutes: int,
) -> tuple[datetime, datetime]:
    if duration_text and until_text:
        raise click.UsageError("--for and --until are mutually exclusive.")
    try:
        start = parse_time(start_text)
        if until_text:
            end = parse_time(until_text)
        elif duration_text:
            end = start + parse_duration(duration_text)
        else:
            end = start + parse_duration(f"{default_minutes}m")
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc
    if end <= start:
        raise click.UsageError("Window end must be after its start.")
    return start, end
