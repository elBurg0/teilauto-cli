# teilauto CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `teilauto`, a publishable CLI (PyPI package `teilauto-cli`) for teilauto/CityFlitzer carsharing: search cars, prices, bookings CRUD, notify-only `watch`, and `autobook` that books a matching car the moment it appears and notifies via Telegram/ntfy.

**Architecture:** Layered src-layout package: `api/` (httpx client + frozen dataclass models for the Cantamen casirest/v3 backend), `services/` (availability merge, watcher engine, notifiers), `core/` (config, token store, time parsing, geo), `output/` (rich renderers + JSON), `cli/` (rich-click command groups). CLI never touches httpx; services never print.

**Tech Stack:** Python ≥3.10, click 8.4, rich 15, rich-click 1.9, httpx 0.28, keyring, platformdirs, tomli-w (+tomli on 3.10). Dev: uv, pytest, respx, ruff. Spec: `docs/superpowers/specs/2026-07-12-teilauto-cli-design.md`.

## Global Constraints

- `requires-python = ">=3.10"`; no 3.11+-only stdlib (use `timezone.utc` not `datetime.UTC`; `tomllib` behind a try/except falling back to `tomli`).
- Every module starts with `from __future__ import annotations`.
- CLI modules import click as `import rich_click as click`. Non-CLI layers never import click or rich.
- API base `https://de1.cantamen.de/casirest/v3`, public app key `6b4d4759-8fd1-b25a-c099-09c2af9c70ce` (safe in source), provider id `"118"`.
- Exit codes: 0 ok, 1 error, 2 usage/no-match, 3 auth required, 4 not found.
- All timestamps sent to the API as UTC `%Y-%m-%dT%H:%M:%S.000Z`; user-facing times in local tz.
- Command name `teilauto`; `-h`/`--help` everywhere via `context_settings`.
- Tests never hit the live API (respx only); no real sleeps (injected sleeper / mocked `time.sleep`).
- Run everything through uv: `uv run pytest`, `uv run ruff check .`.
- GitHub repo URL: `https://github.com/maxboettinger/teilauto-cli`. Author: Max Boettinger <max@bttngr.de>. License MIT.
- Commit after every task (conventional commits: `feat:`, `test:`, `chore:`, `docs:`, `ci:`).

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `LICENSE`, `src/teilauto/__init__.py`, `src/teilauto/cli/__init__.py`, `tests/test_smoke.py`, `.python-version`

**Interfaces:**
- Produces: installable package with entry point `teilauto = "teilauto.cli:main"`; `teilauto.cli.cli` (click group) and `teilauto.cli.main()`; `teilauto.__version__`.

- [ ] **Step 1: Write pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "teilauto-cli"
version = "0.1.0"
description = "Modern CLI for teilauto/CityFlitzer carsharing - search cars, check prices, manage bookings, and auto-book with notifications."
readme = "README.md"
license = "MIT"
license-files = ["LICENSE"]
requires-python = ">=3.10"
authors = [{ name = "Max Boettinger", email = "max@bttngr.de" }]
keywords = ["teilauto", "cityflitzer", "carsharing", "cli", "leipzig"]
classifiers = [
  "Development Status :: 4 - Beta",
  "Environment :: Console",
  "Intended Audience :: End Users/Desktop",
  "Operating System :: OS Independent",
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3.10",
  "Programming Language :: Python :: 3.11",
  "Programming Language :: Python :: 3.12",
  "Programming Language :: Python :: 3.13",
  "Programming Language :: Python :: 3.14",
  "Topic :: Utilities",
]
dependencies = [
  "click>=8.1",
  "rich>=13.0",
  "rich-click>=1.8",
  "httpx>=0.27",
  "keyring>=24.0",
  "platformdirs>=4.0",
  "tomli>=2.0; python_version < '3.11'",
  "tomli-w>=1.0",
]

[project.scripts]
teilauto = "teilauto.cli:main"

[project.urls]
Homepage = "https://github.com/maxboettinger/teilauto-cli"
Repository = "https://github.com/maxboettinger/teilauto-cli"
Issues = "https://github.com/maxboettinger/teilauto-cli/issues"
Changelog = "https://github.com/maxboettinger/teilauto-cli/blob/main/CHANGELOG.md"

[dependency-groups]
dev = ["pytest>=8", "respx>=0.22", "ruff>=0.6"]

[tool.ruff]
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Write .gitignore, LICENSE, .python-version**

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
dist/
build/
*.egg-info/
.pytest_cache/
.ruff_cache/
.coverage
```

`.python-version`: `3.14`

`LICENSE`: standard MIT text, `Copyright (c) 2026 Max Boettinger`.

- [ ] **Step 3: Write package skeleton**

`src/teilauto/__init__.py`:
```python
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("teilauto-cli")
except PackageNotFoundError:  # running from a checkout without install
    __version__ = "0.0.0.dev0"
```

`src/teilauto/cli/__init__.py` (minimal for now; Task 12 expands it):
```python
from __future__ import annotations

import sys

import rich_click as click

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(package_name="teilauto-cli", prog_name="teilauto")
def cli() -> None:
    """Manage teilauto/CityFlitzer carsharing from your terminal."""


def main() -> None:
    try:
        cli(standalone_mode=False)
    except click.exceptions.Exit as exc:
        sys.exit(exc.exit_code)
    except click.ClickException as exc:
        exc.show()
        sys.exit(exc.exit_code)
```

- [ ] **Step 4: Write smoke test**

`tests/test_smoke.py`:
```python
from __future__ import annotations

from click.testing import CliRunner

from teilauto import __version__
from teilauto.cli import cli


def test_version_flag():
    result = CliRunner().invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "teilauto" in result.output


def test_h_shows_help():
    result = CliRunner().invoke(cli, ["-h"])
    assert result.exit_code == 0
    assert "Manage teilauto/CityFlitzer" in result.output


def test_version_attribute():
    assert __version__
```

- [ ] **Step 5: Sync env and run**

Run: `uv sync && uv run pytest -q`
Expected: 3 passed.

Run: `uv run teilauto -h`
Expected: rich-click formatted help with the docstring.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "chore: scaffold teilauto-cli package (uv, hatchling, rich-click entry point)"
```

---

### Task 2: core/geo.py — haversine

**Files:**
- Create: `src/teilauto/core/__init__.py` (empty), `src/teilauto/core/geo.py`
- Test: `tests/test_geo.py`

**Interfaces:**
- Produces: `haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float` (metres).

- [ ] **Step 1: Write failing test** — `tests/test_geo.py`:

```python
from __future__ import annotations

from teilauto.core.geo import haversine_m


def test_zero_distance():
    assert haversine_m(51.34, 12.37, 51.34, 12.37) == 0.0


def test_known_distance_leipzig():
    # Leipzig Hbf -> Augustusplatz is roughly 1.0-1.3 km
    d = haversine_m(51.3455, 12.3821, 51.3387, 12.3818)
    assert 700 < d < 800


def test_symmetry():
    a = haversine_m(51.3, 12.3, 51.4, 12.5)
    b = haversine_m(51.4, 12.5, 51.3, 12.3)
    assert abs(a - b) < 1e-6
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_geo.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement** — `src/teilauto/core/geo.py`:

```python
from __future__ import annotations

import math

_EARTH_RADIUS_M = 6371000.0


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in metres between two WGS84 coordinates."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))
```

- [ ] **Step 4: Run** — `uv run pytest tests/test_geo.py -q` → 3 passed.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: haversine distance helper"`

---

### Task 3: core/timeparse.py — friendly times & durations

**Files:**
- Create: `src/teilauto/core/timeparse.py`
- Test: `tests/test_timeparse.py`

**Interfaces:**
- Produces: `parse_time(text: str, *, now: datetime | None = None) -> datetime` (tz-aware, local tz; accepts `now`, `HH:MM`, `today HH:MM`, `tomorrow HH:MM`, ISO-8601; bare `HH:MM` already >1 min in the past rolls to tomorrow; raises `ValueError` with a helpful message otherwise). `parse_duration(text: str) -> timedelta` (accepts `30m`, `2h`, `1h30m`, bare int = minutes; raises `ValueError`).

- [ ] **Step 1: Write failing test** — `tests/test_timeparse.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
    assert parse_time("tomorrow 08:15", now=NOW) == NOW.replace(hour=8, minute=15) + timedelta(days=1)


def test_iso_naive_gets_local_tz():
    dt = parse_time("2026-08-01 10:00", now=NOW)
    assert dt == datetime(2026, 8, 1, 10, 0, tzinfo=NOW.tzinfo)


def test_iso_with_tz_preserved():
    dt = parse_time("2026-08-01T10:00:00+00:00", now=NOW)
    assert dt.utcoffset() == timedelta(0)


def test_bad_time_raises():
    with pytest.raises(ValueError, match="Cannot parse time"):
        parse_time("banana", now=NOW)


@pytest.mark.parametrize(
    ("text", "expected"),
    [("30m", timedelta(minutes=30)), ("2h", timedelta(hours=2)),
     ("1h30m", timedelta(hours=1, minutes=30)), ("90", timedelta(minutes=90)),
     ("45min", timedelta(minutes=45))],
)
def test_durations(text, expected):
    assert parse_duration(text) == expected


def test_bad_duration_raises():
    with pytest.raises(ValueError, match="Cannot parse duration"):
        parse_duration("soon")
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_timeparse.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement** — `src/teilauto/core/timeparse.py`:

```python
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
```

- [ ] **Step 4: Run** — `uv run pytest tests/test_timeparse.py -q` → all pass.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: friendly time and duration parsing"`

---

### Task 4: api/errors.py + api/models.py + shared fixtures

**Files:**
- Create: `src/teilauto/api/__init__.py` (empty), `src/teilauto/api/errors.py`, `src/teilauto/api/models.py`
- Create: `tests/conftest.py`, `tests/fixtures/pointsofinterest.json`, `tests/fixtures/bookingproposals.json`, `tests/fixtures/prices.json`, `tests/fixtures/bookings.json`, `tests/fixtures/token.json`, `tests/fixtures/unavailabilities.json`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces:
  - Errors: `TeilautoError(message, *, hint: str | None = None)` with `.exit_code = 1`, `.hint`; subclasses `ApiError` (1), `AuthRequiredError` (3, default message + hint "Run `teilauto auth login`…"), `NotFoundError` (4), `RateLimitedError(ApiError)`, `ConfigError` (1), `NoMatchError` (2).
  - Models (all `@dataclass(frozen=True)`): `Car(id, name, plate, fuel, car_type, lat, lng, address)` + `Car.from_bookee(bookee: dict, place: dict | None = None)`; `cars_from_poi(poi: list[dict]) -> list[Car]`; `Proposal(bookee_id, free_from)` + `.from_api`; `Price(total: float | None, currency: str | None, raw: dict)` + `.from_api`; `Booking(id, bookee_id, start, end, state, raw)` + `.from_api`; `Unavailability(start, end)` + `.from_api`; `TokenInfo(id, expiry, customer_id)` + `.from_api`. Constant `CITYFLITZER_TYPE = "cityFlitzer"`.
  - `tests/conftest.py` with `load_fixture(name)` and fixtures `poi_json`, `proposals_json`, `prices_json`, `bookings_json`, `token_json`, `unavailabilities_json`.

- [ ] **Step 1: Write fixture files** (shapes mirror the reverse-engineered casirest v3 responses in the sibling `teilauto` repo README):

`tests/fixtures/pointsofinterest.json`:
```json
[
  {
    "id": "poi-1",
    "places": [
      {
        "id": "place-1",
        "name": "Dresdner Str. 6",
        "geoCoordinate": {"latitude": 51.339, "longitude": 12.392},
        "bookees": [
          {"id": "111", "displayName": "VW Polo", "licenseNumber": "L-TA 1111",
           "fuelLevel": 80, "bookeeType": {"name": "cityFlitzer"}},
          {"id": "222", "displayName": "VW Golf", "licenseNumber": "L-TA 2222",
           "fuelLevel": 20, "bookeeType": {"name": "cityFlitzer"}}
        ]
      },
      {
        "id": "place-2",
        "name": "Station Ost",
        "geoCoordinate": {"latitude": 51.34, "longitude": 12.395},
        "bookees": [
          {"id": "333", "displayName": "Kombi", "licenseNumber": "L-TA 3333",
           "fuelLevel": 90, "bookeeType": {"name": "classic"}}
        ]
      }
    ]
  }
]
```

`tests/fixtures/bookingproposals.json`:
```json
[
  {"bookeeId": "111",
   "timeRange": {"start": "2026-07-12T10:00:00.000Z", "end": "2026-07-12T10:30:00.000Z"},
   "availabilitySize": 1}
]
```

`tests/fixtures/prices.json`:
```json
[
  {"bookeeId": "111",
   "priceItems": [
     {"type": "time", "gross": {"amount": 390, "currency": "EUR"}},
     {"type": "startFee", "gross": {"amount": 100, "currency": "EUR"}}
   ]}
]
```

`tests/fixtures/bookings.json`:
```json
[
  {"id": "b-1", "bookeeId": "111", "state": "CONFIRMED",
   "timeRange": {"start": "2026-07-12T10:00:00.000Z", "end": "2026-07-12T11:00:00.000Z"}},
  {"id": "b-0", "bookeeId": "222", "state": "FINISHED",
   "timeRange": {"start": "2026-07-01T10:00:00.000Z", "end": "2026-07-01T11:00:00.000Z"}}
]
```

`tests/fixtures/token.json`:
```json
{"id": "tok-abc123", "expiry": "2026-10-10T00:00:00.000Z", "customerId": "cust-9"}
```

`tests/fixtures/unavailabilities.json`:
```json
[
  {"timeRange": {"start": "2026-07-12T18:00:00.000Z", "end": "2026-07-12T20:00:00.000Z"}}
]
```

- [ ] **Step 2: Write conftest** — `tests/conftest.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def poi_json():
    return load_fixture("pointsofinterest.json")


@pytest.fixture
def proposals_json():
    return load_fixture("bookingproposals.json")


@pytest.fixture
def prices_json():
    return load_fixture("prices.json")


@pytest.fixture
def bookings_json():
    return load_fixture("bookings.json")


@pytest.fixture
def token_json():
    return load_fixture("token.json")


@pytest.fixture
def unavailabilities_json():
    return load_fixture("unavailabilities.json")
```

- [ ] **Step 3: Write failing tests** — `tests/test_models.py`:

```python
from __future__ import annotations

from teilauto.api.errors import (
    ApiError,
    AuthRequiredError,
    NoMatchError,
    NotFoundError,
    TeilautoError,
)
from teilauto.api.models import (
    Booking,
    Car,
    Price,
    Proposal,
    TokenInfo,
    Unavailability,
    cars_from_poi,
)


def test_error_exit_codes_and_hint():
    assert TeilautoError("x").exit_code == 1
    assert ApiError("x").exit_code == 1
    err = AuthRequiredError()
    assert err.exit_code == 3
    assert "teilauto auth login" in (err.hint or "")
    assert NotFoundError("x").exit_code == 4
    assert NoMatchError("x").exit_code == 2


def test_cars_from_poi(poi_json):
    cars = cars_from_poi(poi_json)
    assert [c.id for c in cars] == ["111", "222", "333"]
    polo = cars[0]
    assert polo == Car(
        id="111", name="VW Polo", plate="L-TA 1111", fuel=80,
        car_type="cityFlitzer", lat=51.339, lng=12.392, address="Dresdner Str. 6",
    )


def test_proposal_from_api(proposals_json):
    p = Proposal.from_api(proposals_json[0])
    assert p.bookee_id == "111"
    assert p.free_from == "2026-07-12T10:00:00.000Z"


def test_price_sums_gross_items(prices_json):
    price = Price.from_api(prices_json[0])
    assert price.total == 4.90
    assert price.currency == "EUR"


def test_price_unknown_shape_gives_none():
    price = Price.from_api({"something": "else"})
    assert price.total is None
    assert price.raw == {"something": "else"}


def test_booking_from_api(bookings_json):
    b = Booking.from_api(bookings_json[0])
    assert (b.id, b.bookee_id, b.state) == ("b-1", "111", "CONFIRMED")
    assert b.start == "2026-07-12T10:00:00.000Z"


def test_unavailability_from_api(unavailabilities_json):
    u = Unavailability.from_api(unavailabilities_json[0])
    assert u.start == "2026-07-12T18:00:00.000Z"


def test_token_info(token_json):
    t = TokenInfo.from_api(token_json)
    assert (t.id, t.customer_id) == ("tok-abc123", "cust-9")
    assert t.expiry == "2026-10-10T00:00:00.000Z"
```

- [ ] **Step 4: Run to verify failure** — `uv run pytest tests/test_models.py -q` → ModuleNotFoundError.

- [ ] **Step 5: Implement** — `src/teilauto/api/errors.py`:

```python
from __future__ import annotations


class TeilautoError(Exception):
    """Base error; the CLI root handler renders message + hint and exits with exit_code."""

    exit_code = 1

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint


class ApiError(TeilautoError):
    pass


class RateLimitedError(ApiError):
    pass


class AuthRequiredError(TeilautoError):
    exit_code = 3

    def __init__(self, message: str = "Not logged in or token expired.") -> None:
        super().__init__(message, hint="Run `teilauto auth login` to authenticate.")


class NotFoundError(TeilautoError):
    exit_code = 4


class ConfigError(TeilautoError):
    pass


class NoMatchError(TeilautoError):
    exit_code = 2
```

`src/teilauto/api/models.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

CITYFLITZER_TYPE = "cityFlitzer"


@dataclass(frozen=True)
class Car:
    id: str
    name: str
    plate: str | None
    fuel: float | None
    car_type: str | None
    lat: float | None
    lng: float | None
    address: str | None

    @classmethod
    def from_bookee(cls, bookee: dict, place: dict | None = None) -> Car:
        place = place or bookee.get("place") or {}
        coord = place.get("geoCoordinate") or {}
        return cls(
            id=str(bookee["id"]),
            name=bookee.get("displayName") or bookee.get("name") or "?",
            plate=bookee.get("licenseNumber"),
            fuel=bookee.get("fuelLevel"),
            car_type=(bookee.get("bookeeType") or {}).get("name"),
            lat=coord.get("latitude"),
            lng=coord.get("longitude"),
            address=place.get("name"),
        )


def cars_from_poi(poi: list[dict]) -> list[Car]:
    """Flatten a /pointsofinterest response into cars, deduplicated by id."""
    seen: dict[str, Car] = {}
    for point in poi:
        for place in point.get("places", []):
            for bookee in place.get("bookees", []):
                car = Car.from_bookee(bookee, place)
                seen.setdefault(car.id, car)
    return list(seen.values())


@dataclass(frozen=True)
class Proposal:
    bookee_id: str
    free_from: str | None

    @classmethod
    def from_api(cls, data: dict) -> Proposal:
        return cls(
            bookee_id=str(data.get("bookeeId")),
            free_from=(data.get("timeRange") or {}).get("start"),
        )


@dataclass(frozen=True)
class Price:
    total: float | None
    currency: str | None
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict) -> Price:
        total_cents = 0
        currency: str | None = None
        found = False
        for item in data.get("priceItems") or []:
            gross = item.get("gross") or {}
            if "amount" in gross:
                total_cents += gross["amount"]
                currency = gross.get("currency") or currency
                found = True
        if not found:
            gross = data.get("gross") or {}
            if "amount" in gross:
                total_cents = gross["amount"]
                currency = gross.get("currency")
                found = True
        return cls(total=total_cents / 100 if found else None, currency=currency, raw=data)


@dataclass(frozen=True)
class Booking:
    id: str
    bookee_id: str | None
    start: str | None
    end: str | None
    state: str | None
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict) -> Booking:
        time_range = data.get("timeRange") or {}
        bookee_id = data.get("bookeeId")
        return cls(
            id=str(data.get("id")),
            bookee_id=str(bookee_id) if bookee_id is not None else None,
            start=time_range.get("start"),
            end=time_range.get("end"),
            state=data.get("state") or data.get("bookingState"),
            raw=data,
        )


@dataclass(frozen=True)
class Unavailability:
    start: str | None
    end: str | None

    @classmethod
    def from_api(cls, data: dict) -> Unavailability:
        time_range = data.get("timeRange") or data
        return cls(start=time_range.get("start"), end=time_range.get("end"))


@dataclass(frozen=True)
class TokenInfo:
    id: str
    expiry: str | None
    customer_id: str | None

    @classmethod
    def from_api(cls, data: dict) -> TokenInfo:
        customer = data.get("customerId")
        return cls(
            id=str(data["id"]),
            expiry=data.get("expiry"),
            customer_id=str(customer) if customer is not None else None,
        )
```

- [ ] **Step 6: Run** — `uv run pytest tests/test_models.py -q` → all pass.
- [ ] **Step 7: Commit** — `git add -A && git commit -m "feat: API error hierarchy, typed models, recorded fixtures"`

---

### Task 5: api/client.py — CantamenClient

**Files:**
- Create: `src/teilauto/api/client.py`
- Test: `tests/test_client.py`

**Interfaces:**
- Consumes: models + errors from Task 4.
- Produces: `API_KEY`, `BASE_URL`, `PROV_ID` constants; `iso_utc(dt: datetime) -> str`;
  `CantamenClient(*, token_id: str | None = None, base_url: str = BASE_URL, api_key: str = API_KEY, timeout: float = 20.0, verbose: bool = False, retries: int = 2)` — context manager with `.close()`. Methods:
  `points_of_interest(*, lat, lng, radius_m, start, end) -> list[Car]`;
  `booking_proposals(*, lat, lng, radius_m, start, end) -> list[Proposal]`;
  `get_car(bookee_id: str) -> Car`; `unavailabilities(bookee_id, start, end) -> list[Unavailability]`;
  `price(bookee_id, start, end) -> Price`; `login(login, credential, prov_id=PROV_ID) -> TokenInfo`;
  `list_bookings() -> list[Booking]`; `get_booking(booking_id) -> Booking`;
  `create_booking(bookee_id, start, end) -> Booking`; `cancel_booking(booking_id) -> None`.
  All `start`/`end` are tz-aware datetimes. HTTP: retries transport errors and 5xx (`retries` extra attempts), 401 → `AuthRequiredError`, 404 → `NotFoundError`, 429 → `RateLimitedError`, other 4xx → `ApiError`; verbose logs `METHOD path -> status` to stderr.

- [ ] **Step 1: Write failing tests** — `tests/test_client.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from teilauto.api.client import BASE_URL, CantamenClient, iso_utc
from teilauto.api.errors import ApiError, AuthRequiredError, NotFoundError, RateLimitedError

START = datetime(2026, 7, 12, 10, 0, tzinfo=timezone.utc)
END = datetime(2026, 7, 12, 10, 30, tzinfo=timezone.utc)


def test_iso_utc_formats_z():
    assert iso_utc(START) == "2026-07-12T10:00:00.000Z"


def test_points_of_interest_parses_cars(respx_mock, poi_json):
    route = respx_mock.get(f"{BASE_URL}/pointsofinterest").mock(
        return_value=httpx.Response(200, json=poi_json)
    )
    with CantamenClient() as client:
        cars = client.points_of_interest(lat=51.33, lng=12.39, radius_m=500, start=START, end=END)
    assert [c.id for c in cars] == ["111", "222", "333"]
    params = route.calls.last.request.url.params
    assert params["range"] == "500"
    assert params["start"] == "2026-07-12T10:00:00.000Z"
    assert route.calls.last.request.headers["x-api-key"]


def test_booking_proposals(respx_mock, proposals_json):
    respx_mock.get(f"{BASE_URL}/bookingproposals").mock(
        return_value=httpx.Response(200, json=proposals_json)
    )
    with CantamenClient() as client:
        props = client.booking_proposals(lat=51.33, lng=12.39, radius_m=500, start=START, end=END)
    assert props[0].bookee_id == "111"


def test_token_header_sent(respx_mock, bookings_json):
    route = respx_mock.get(f"{BASE_URL}/bookings").mock(
        return_value=httpx.Response(200, json=bookings_json)
    )
    with CantamenClient(token_id="tok-abc123") as client:
        bookings = client.list_bookings()
    assert len(bookings) == 2
    auth = route.calls.last.request.headers["authorization"]
    assert auth.startswith("Basic ")  # base64("tok-abc123:")
    assert auth == "Basic dG9rLWFiYzEyMzo="


def test_create_booking_body(respx_mock, bookings_json):
    route = respx_mock.post(f"{BASE_URL}/bookings").mock(
        return_value=httpx.Response(200, json=bookings_json[0])
    )
    with CantamenClient(token_id="t") as client:
        booking = client.create_booking("111", START, END)
    assert booking.id == "b-1"
    import json as jsonlib

    body = jsonlib.loads(route.calls.last.request.content)
    assert body == {
        "bookeeId": "111",
        "timeRange": {"start": "2026-07-12T10:00:00.000Z", "end": "2026-07-12T10:30:00.000Z"},
    }


def test_login_posts_credentials(respx_mock, token_json):
    route = respx_mock.post(f"{BASE_URL}/tokens").mock(
        return_value=httpx.Response(200, json=token_json)
    )
    with CantamenClient() as client:
        info = client.login("me@example.org", "secret")
    assert info.id == "tok-abc123"
    import json as jsonlib

    body = jsonlib.loads(route.calls.last.request.content)
    assert body["login"] == "me@example.org"
    assert body["provId"] == "118"
    assert body["storeLogin"] is True


def test_price_takes_first_list_item(respx_mock, prices_json):
    respx_mock.get(f"{BASE_URL}/prices").mock(return_value=httpx.Response(200, json=prices_json))
    with CantamenClient() as client:
        price = client.price("111", START, END)
    assert price.total == 4.90


def test_401_raises_auth_required(respx_mock):
    respx_mock.get(f"{BASE_URL}/bookings").mock(return_value=httpx.Response(401))
    with CantamenClient() as client, pytest.raises(AuthRequiredError):
        client.list_bookings()


def test_404_and_429(respx_mock):
    respx_mock.get(f"{BASE_URL}/bookees/nope").mock(return_value=httpx.Response(404))
    respx_mock.get(f"{BASE_URL}/prices").mock(return_value=httpx.Response(429))
    with CantamenClient() as client:
        with pytest.raises(NotFoundError):
            client.get_car("nope")
        with pytest.raises(RateLimitedError):
            client.price("111", START, END)


def test_retries_5xx_then_succeeds(respx_mock, proposals_json):
    route = respx_mock.get(f"{BASE_URL}/bookingproposals")
    route.side_effect = [httpx.Response(500), httpx.Response(200, json=proposals_json)]
    with CantamenClient() as client:
        props = client.booking_proposals(lat=1, lng=2, radius_m=3, start=START, end=END)
    assert len(props) == 1
    assert route.call_count == 2


def test_exhausted_retries_raise_api_error(respx_mock):
    respx_mock.get(f"{BASE_URL}/bookingproposals").mock(return_value=httpx.Response(502))
    with CantamenClient(retries=1) as client, pytest.raises(ApiError, match="502"):
        client.booking_proposals(lat=1, lng=2, radius_m=3, start=START, end=END)


def test_cancel_booking_deletes(respx_mock):
    route = respx_mock.delete(f"{BASE_URL}/bookings/b-1").mock(return_value=httpx.Response(204))
    with CantamenClient(token_id="t") as client:
        client.cancel_booking("b-1")
    assert route.called
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_client.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement** — `src/teilauto/api/client.py`:

```python
from __future__ import annotations

import base64
import sys
from datetime import datetime, timezone
from typing import Any

import httpx

from teilauto.api.errors import ApiError, AuthRequiredError, NotFoundError, RateLimitedError
from teilauto.api.models import (
    Booking,
    Car,
    Price,
    Proposal,
    TokenInfo,
    Unavailability,
    cars_from_poi,
)

# Public app key baked into the buchen.teilauto.net frontend JS.
# It identifies the app (not a user) and only unlocks read-only data.
API_KEY = "6b4d4759-8fd1-b25a-c099-09c2af9c70ce"
BASE_URL = "https://de1.cantamen.de/casirest/v3"
PROV_ID = "118"  # teilauto/CityFlitzer Mitteldeutschland


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


class CantamenClient:
    """Thin typed client for the Cantamen casirest/v3 API."""

    def __init__(
        self,
        *,
        token_id: str | None = None,
        base_url: str = BASE_URL,
        api_key: str = API_KEY,
        timeout: float = 20.0,
        verbose: bool = False,
        retries: int = 2,
    ) -> None:
        headers = {"x-api-key": api_key, "Accept": "application/json"}
        if token_id:
            encoded = base64.b64encode(f"{token_id}:".encode()).decode()
            headers["authorization"] = f"Basic {encoded}"
        self._http = httpx.Client(base_url=base_url, headers=headers, timeout=timeout)
        self._verbose = verbose
        self._retries = retries

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> CantamenClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _request(
        self, method: str, path: str, *, params: dict | None = None, json: dict | None = None
    ) -> Any:
        last_error: str = "no attempts made"
        for _attempt in range(self._retries + 1):
            try:
                resp = self._http.request(method, path, params=params, json=json)
            except httpx.TransportError as exc:
                last_error = f"network error: {exc}"
                continue
            if self._verbose:
                print(f"[http] {method} {path} -> {resp.status_code}", file=sys.stderr)
            if resp.status_code == 401:
                raise AuthRequiredError()
            if resp.status_code == 404:
                raise NotFoundError(f"Not found: {path}")
            if resp.status_code == 429:
                raise RateLimitedError("Rate limited by the API — slow down and retry later.")
            if resp.status_code >= 500:
                last_error = f"server error {resp.status_code}"
                continue
            if resp.status_code >= 400:
                raise ApiError(f"API error {resp.status_code}: {resp.text[:200]}")
            if resp.status_code == 204 or not resp.content:
                return None
            return resp.json()
        raise ApiError(f"Request failed after {self._retries + 1} attempts ({last_error}).")

    # -- read-only ---------------------------------------------------------

    def points_of_interest(
        self, *, lat: float, lng: float, radius_m: int, start: datetime, end: datetime
    ) -> list[Car]:
        data = self._request(
            "GET",
            "/pointsofinterest",
            params={
                "expand": "place.bookee.bookeeType",
                "lat": lat,
                "lng": lng,
                "range": radius_m,
                "start": iso_utc(start),
                "end": iso_utc(end),
                "sort": "distance",
            },
        )
        return cars_from_poi(data or [])

    def booking_proposals(
        self, *, lat: float, lng: float, radius_m: int, start: datetime, end: datetime
    ) -> list[Proposal]:
        data = self._request(
            "GET",
            "/bookingproposals",
            params={
                "expand": "bookeeId",
                "lat": lat,
                "lng": lng,
                "range": radius_m,
                "start": iso_utc(start),
                "end": iso_utc(end),
            },
        )
        return [Proposal.from_api(item) for item in data or []]

    def get_car(self, bookee_id: str) -> Car:
        data = self._request(
            "GET", f"/bookees/{bookee_id}", params={"expand": ["bookeeType", "place"]}
        )
        return Car.from_bookee(data)

    def unavailabilities(
        self, bookee_id: str, start: datetime, end: datetime
    ) -> list[Unavailability]:
        data = self._request(
            "GET",
            "/unavailabilities",
            params={"bookeeId": bookee_id, "start": iso_utc(start), "end": iso_utc(end)},
        )
        return [Unavailability.from_api(item) for item in data or []]

    def price(self, bookee_id: str, start: datetime, end: datetime) -> Price:
        data = self._request(
            "GET",
            "/prices",
            params={"bookeeId": bookee_id, "start": iso_utc(start), "end": iso_utc(end)},
        )
        if isinstance(data, list):
            data = data[0] if data else {}
        return Price.from_api(data or {})

    # -- member actions ------------------------------------------------------

    def login(self, login: str, credential: str, prov_id: str = PROV_ID) -> TokenInfo:
        data = self._request(
            "POST",
            "/tokens",
            json={
                "login": login,
                "credential": credential,
                "provId": prov_id,
                "storeLogin": True,
            },
        )
        return TokenInfo.from_api(data)

    def list_bookings(self) -> list[Booking]:
        data = self._request("GET", "/bookings")
        return [Booking.from_api(item) for item in data or []]

    def get_booking(self, booking_id: str) -> Booking:
        data = self._request("GET", f"/bookings/{booking_id}")
        return Booking.from_api(data)

    def create_booking(self, bookee_id: str, start: datetime, end: datetime) -> Booking:
        data = self._request(
            "POST",
            "/bookings",
            json={
                "bookeeId": bookee_id,
                "timeRange": {"start": iso_utc(start), "end": iso_utc(end)},
            },
        )
        return Booking.from_api(data)

    def cancel_booking(self, booking_id: str) -> None:
        self._request("DELETE", f"/bookings/{booking_id}")
```

- [ ] **Step 4: Run** — `uv run pytest tests/test_client.py -q` → all pass.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: Cantamen casirest v3 client with retries and typed responses"`

---

### Task 6: core/config.py — TOML config + env overrides

**Files:**
- Create: `src/teilauto/core/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: `ConfigError` from `teilauto.api.errors`.
- Produces:
  - `DEFAULTS` (nested dict): `location.{lat=51.33853, lng=12.39163, radius_m=500}`, `defaults.{min_fuel=0.0, window_min=30, interval_sec=120}`, `api.{prov_id="118"}`, `notify.{channels=[], telegram.chat_id="", ntfy.topic="", ntfy.server="https://ntfy.sh"}`.
  - `KNOWN_KEYS: tuple[str, ...]` — dotted paths of all leaves above.
  - `config_dir() -> Path` (respects `TEILAUTO_CONFIG_DIR` env, else `platformdirs.user_config_path("teilauto")`), `config_file() -> Path`.
  - `read_raw(path=None) -> dict`, `write_raw(data, path=None)`.
  - `get_value(data: dict, key: str)`, `set_value(data, key, value)`, `unset_value(data, key)` — dotted-key helpers; `coerce_value(text: str) -> object` (bool/int/float/comma-list/str).
  - `Settings` frozen dataclass: `lat: float, lng: float, radius_m: int, min_fuel: float, window_min: int, interval_sec: int, prov_id: str, channels: tuple[str, ...], tg_chat_id: str, ntfy_topic: str, ntfy_server: str`.
  - `load_settings(path=None) -> Settings` — defaults ← file ← env (`TEILAUTO_<PATH_WITH_UNDERSCORES>`, e.g. `TEILAUTO_LOCATION_LAT`, `TEILAUTO_NOTIFY_CHANNELS` comma-separated, `TEILAUTO_NOTIFY_TELEGRAM_CHAT_ID`); values cast to the default's type; a `channels` string becomes a 1-tuple.
  - `effective_config(path=None) -> dict[str, object]` — flat dotted-key map of merged values (for `config list`).

- [ ] **Step 1: Write failing tests** — `tests/test_config.py`:

```python
from __future__ import annotations

import pytest

from teilauto.core import config as cfg


@pytest.fixture
def config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("TEILAUTO_CONFIG_DIR", str(tmp_path))
    return tmp_path


def test_defaults_when_no_file(config_home):
    s = cfg.load_settings()
    assert (s.lat, s.lng, s.radius_m) == (51.33853, 12.39163, 500)
    assert s.interval_sec == 120
    assert s.channels == ()
    assert s.ntfy_server == "https://ntfy.sh"


def test_file_overrides_defaults(config_home):
    data = cfg.read_raw()
    cfg.set_value(data, "location.radius_m", 900)
    cfg.set_value(data, "notify.channels", ["telegram"])
    cfg.set_value(data, "notify.telegram.chat_id", "42")
    cfg.write_raw(data)
    s = cfg.load_settings()
    assert s.radius_m == 900
    assert s.channels == ("telegram",)
    assert s.tg_chat_id == "42"


def test_env_overrides_file(config_home, monkeypatch):
    data = cfg.read_raw()
    cfg.set_value(data, "location.radius_m", 900)
    cfg.write_raw(data)
    monkeypatch.setenv("TEILAUTO_LOCATION_RADIUS_M", "250")
    monkeypatch.setenv("TEILAUTO_NOTIFY_CHANNELS", "telegram,ntfy")
    s = cfg.load_settings()
    assert s.radius_m == 250
    assert s.channels == ("telegram", "ntfy")


def test_channels_string_becomes_tuple(config_home):
    data = cfg.read_raw()
    cfg.set_value(data, "notify.channels", "telegram")
    cfg.write_raw(data)
    assert cfg.load_settings().channels == ("telegram",)


def test_get_set_unset_roundtrip(config_home):
    data = cfg.read_raw()
    cfg.set_value(data, "defaults.min_fuel", 25.0)
    assert cfg.get_value(data, "defaults.min_fuel") == 25.0
    cfg.unset_value(data, "defaults.min_fuel")
    assert cfg.get_value(data, "defaults.min_fuel") is None


def test_coerce_value():
    assert cfg.coerce_value("true") is True
    assert cfg.coerce_value("42") == 42
    assert cfg.coerce_value("1.5") == 1.5
    assert cfg.coerce_value("a,b") == ["a", "b"]
    assert cfg.coerce_value("hello") == "hello"


def test_effective_config_is_flat(config_home):
    flat = cfg.effective_config()
    assert flat["location.lat"] == 51.33853
    assert "notify.ntfy.server" in flat
    assert set(flat) == set(cfg.KNOWN_KEYS)


def test_config_file_under_config_dir(config_home):
    assert cfg.config_file().parent == config_home
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_config.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement** — `src/teilauto/core/config.py`:

```python
from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from pathlib import Path

import platformdirs
import tomli_w

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

DEFAULTS: dict = {
    "location": {"lat": 51.33853, "lng": 12.39163, "radius_m": 500},
    "defaults": {"min_fuel": 0.0, "window_min": 30, "interval_sec": 120},
    "api": {"prov_id": "118"},
    "notify": {
        "channels": [],
        "telegram": {"chat_id": ""},
        "ntfy": {"topic": "", "server": "https://ntfy.sh"},
    },
}


def _leaf_keys(tree: dict, prefix: str = "") -> list[str]:
    keys: list[str] = []
    for name, value in tree.items():
        dotted = f"{prefix}{name}"
        if isinstance(value, dict):
            keys.extend(_leaf_keys(value, f"{dotted}."))
        else:
            keys.append(dotted)
    return keys


KNOWN_KEYS: tuple[str, ...] = tuple(_leaf_keys(DEFAULTS))


def config_dir() -> Path:
    override = os.getenv("TEILAUTO_CONFIG_DIR")
    if override:
        return Path(override)
    return platformdirs.user_config_path("teilauto")


def config_file() -> Path:
    return config_dir() / "config.toml"


def read_raw(path: Path | None = None) -> dict:
    path = path or config_file()
    if not path.is_file():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


def write_raw(data: dict, path: Path | None = None) -> None:
    path = path or config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as fh:
        tomli_w.dump(data, fh)


def get_value(data: dict, key: str):
    node = data
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def set_value(data: dict, key: str, value: object) -> None:
    parts = key.split(".")
    node = data
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def unset_value(data: dict, key: str) -> None:
    parts = key.split(".")
    node = data
    for part in parts[:-1]:
        node = node.get(part)
        if not isinstance(node, dict):
            return
    node.pop(parts[-1], None)


def coerce_value(text: str) -> object:
    low = text.strip().lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    if "," in text:
        return [part.strip() for part in text.split(",") if part.strip()]
    return text


def _merged(path: Path | None = None) -> dict:
    merged = copy.deepcopy(DEFAULTS)

    def deep_update(base: dict, extra: dict) -> None:
        for name, value in extra.items():
            if isinstance(value, dict) and isinstance(base.get(name), dict):
                deep_update(base[name], value)
            else:
                base[name] = value

    deep_update(merged, read_raw(path))
    for key in KNOWN_KEYS:
        env_name = "TEILAUTO_" + key.replace(".", "_").upper()
        raw = os.getenv(env_name)
        if raw is None:
            continue
        default = get_value(DEFAULTS, key)
        value: object
        if isinstance(default, list):
            value = [part.strip() for part in raw.split(",") if part.strip()]
        elif isinstance(default, float):
            value = float(raw)
        elif isinstance(default, int):
            value = int(raw)
        else:
            value = raw
        set_value(merged, key, value)
    return merged


def effective_config(path: Path | None = None) -> dict[str, object]:
    merged = _merged(path)
    return {key: get_value(merged, key) for key in KNOWN_KEYS}


@dataclass(frozen=True)
class Settings:
    lat: float
    lng: float
    radius_m: int
    min_fuel: float
    window_min: int
    interval_sec: int
    prov_id: str
    channels: tuple[str, ...]
    tg_chat_id: str
    ntfy_topic: str
    ntfy_server: str


def load_settings(path: Path | None = None) -> Settings:
    merged = _merged(path)
    channels = get_value(merged, "notify.channels")
    if isinstance(channels, str):
        channels = [channels]
    return Settings(
        lat=float(get_value(merged, "location.lat")),
        lng=float(get_value(merged, "location.lng")),
        radius_m=int(get_value(merged, "location.radius_m")),
        min_fuel=float(get_value(merged, "defaults.min_fuel")),
        window_min=int(get_value(merged, "defaults.window_min")),
        interval_sec=int(get_value(merged, "defaults.interval_sec")),
        prov_id=str(get_value(merged, "api.prov_id")),
        channels=tuple(channels or ()),
        tg_chat_id=str(get_value(merged, "notify.telegram.chat_id") or ""),
        ntfy_topic=str(get_value(merged, "notify.ntfy.topic") or ""),
        ntfy_server=str(get_value(merged, "notify.ntfy.server") or "https://ntfy.sh"),
    )
```

- [ ] **Step 4: Run** — `uv run pytest tests/test_config.py -q` → all pass.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: TOML config with defaults, file and env override layers"`

---

### Task 7: core/tokenstore.py — keyring with file fallback

**Files:**
- Create: `src/teilauto/core/tokenstore.py`
- Test: `tests/test_tokenstore.py`

**Interfaces:**
- Consumes: `config_dir()` from Task 6.
- Produces: `SERVICE = "teilauto-cli"`, `TOKEN_KEY = "cantamen-token"`, `TG_BOT_TOKEN_KEY = "telegram-bot-token"`;
  `StoredToken` frozen dataclass `(id: str, expiry: str | None, customer_id: str | None)`;
  `save_secret(name: str, value: str) -> None`, `load_secret(name: str) -> str | None`, `delete_secret(name: str) -> None` — keyring first, transparent fallback to `config_dir()/secrets.json` (chmod 600, one-time stderr warning) when keyring raises;
  `save_token(token: StoredToken)`, `load_token() -> StoredToken | None` (env `TEILAUTO_TOKEN` wins, giving `StoredToken(id=env, expiry=None, customer_id=None)`), `delete_token()`.

- [ ] **Step 1: Write failing tests** — `tests/test_tokenstore.py`:

```python
from __future__ import annotations

import json
import stat
import sys

import pytest

from teilauto.core import tokenstore
from teilauto.core.tokenstore import StoredToken


class _WorkingKeyring:
    def __init__(self):
        self.store = {}

    def set_password(self, service, name, value):
        self.store[(service, name)] = value

    def get_password(self, service, name):
        return self.store.get((service, name))

    def delete_password(self, service, name):
        self.store.pop((service, name), None)


class _BrokenKeyring:
    def set_password(self, *a):
        raise RuntimeError("no backend")

    def get_password(self, *a):
        raise RuntimeError("no backend")

    def delete_password(self, *a):
        raise RuntimeError("no backend")


@pytest.fixture
def config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("TEILAUTO_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("TEILAUTO_TOKEN", raising=False)
    return tmp_path


def test_secret_roundtrip_via_keyring(config_home, monkeypatch):
    monkeypatch.setattr(tokenstore, "keyring", _WorkingKeyring())
    tokenstore.save_secret("x", "s3cret")
    assert tokenstore.load_secret("x") == "s3cret"
    tokenstore.delete_secret("x")
    assert tokenstore.load_secret("x") is None


def test_file_fallback_when_keyring_broken(config_home, monkeypatch):
    monkeypatch.setattr(tokenstore, "keyring", _BrokenKeyring())
    tokenstore.save_secret("x", "s3cret")
    secrets_file = config_home / "secrets.json"
    assert secrets_file.is_file()
    assert json.loads(secrets_file.read_text())["x"] == "s3cret"
    if sys.platform != "win32":
        assert stat.S_IMODE(secrets_file.stat().st_mode) == 0o600
    assert tokenstore.load_secret("x") == "s3cret"
    tokenstore.delete_secret("x")
    assert tokenstore.load_secret("x") is None


def test_token_roundtrip(config_home, monkeypatch):
    monkeypatch.setattr(tokenstore, "keyring", _BrokenKeyring())
    token = StoredToken(id="tok-1", expiry="2026-10-10T00:00:00.000Z", customer_id="c1")
    tokenstore.save_token(token)
    assert tokenstore.load_token() == token
    tokenstore.delete_token()
    assert tokenstore.load_token() is None


def test_env_token_wins(config_home, monkeypatch):
    monkeypatch.setattr(tokenstore, "keyring", _BrokenKeyring())
    tokenstore.save_token(StoredToken(id="stored", expiry=None, customer_id=None))
    monkeypatch.setenv("TEILAUTO_TOKEN", "from-env")
    assert tokenstore.load_token() == StoredToken(id="from-env", expiry=None, customer_id=None)
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_tokenstore.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement** — `src/teilauto/core/tokenstore.py`:

```python
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import keyring

from teilauto.core.config import config_dir

SERVICE = "teilauto-cli"
TOKEN_KEY = "cantamen-token"
TG_BOT_TOKEN_KEY = "telegram-bot-token"

_warned_fallback = False


@dataclass(frozen=True)
class StoredToken:
    id: str
    expiry: str | None
    customer_id: str | None


def _secrets_file() -> Path:
    return config_dir() / "secrets.json"


def _warn_fallback() -> None:
    global _warned_fallback
    if not _warned_fallback:
        print(
            "warning: no usable OS keyring; storing secrets in "
            f"{_secrets_file()} (chmod 600)",
            file=sys.stderr,
        )
        _warned_fallback = True


def _file_read() -> dict:
    path = _secrets_file()
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _file_write(data: dict) -> None:
    path = _secrets_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    path.chmod(0o600)


def save_secret(name: str, value: str) -> None:
    try:
        keyring.set_password(SERVICE, name, value)
    except Exception:
        _warn_fallback()
        data = _file_read()
        data[name] = value
        _file_write(data)


def load_secret(name: str) -> str | None:
    try:
        value = keyring.get_password(SERVICE, name)
    except Exception:
        value = None
    if value is not None:
        return value
    return _file_read().get(name)


def delete_secret(name: str) -> None:
    try:
        keyring.delete_password(SERVICE, name)
    except Exception:
        pass
    data = _file_read()
    if name in data:
        del data[name]
        _file_write(data)


def save_token(token: StoredToken) -> None:
    save_secret(
        TOKEN_KEY,
        json.dumps({"id": token.id, "expiry": token.expiry, "customer_id": token.customer_id}),
    )


def load_token() -> StoredToken | None:
    env_token = os.getenv("TEILAUTO_TOKEN")
    if env_token:
        return StoredToken(id=env_token, expiry=None, customer_id=None)
    raw = load_secret(TOKEN_KEY)
    if not raw:
        return None
    data = json.loads(raw)
    return StoredToken(
        id=data["id"], expiry=data.get("expiry"), customer_id=data.get("customer_id")
    )


def delete_token() -> None:
    delete_secret(TOKEN_KEY)
```

- [ ] **Step 4: Run** — `uv run pytest tests/test_tokenstore.py -q` → all pass.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: secret/token store with keyring and chmod-600 file fallback"`

---

### Task 8: output/json_out.py

**Files:**
- Create: `src/teilauto/output/__init__.py` (empty), `src/teilauto/output/json_out.py`
- Test: `tests/test_json_out.py`

**Interfaces:**
- Produces: `to_jsonable(obj) -> object` (recurses dataclasses/dicts/lists/tuples; `datetime` → `.isoformat()`; `Path` → `str`); `print_json(obj) -> None` (one `json.dumps(..., indent=2, ensure_ascii=False)` document via `click.echo`).

- [ ] **Step 1: Write failing test** — `tests/test_json_out.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from teilauto.output.json_out import print_json, to_jsonable


@dataclass(frozen=True)
class Inner:
    when: datetime


@dataclass(frozen=True)
class Outer:
    name: str
    inner: Inner
    tags: tuple[str, ...]
    where: Path


def test_to_jsonable_recurses():
    obj = Outer(
        name="x",
        inner=Inner(when=datetime(2026, 7, 12, tzinfo=timezone.utc)),
        tags=("a", "b"),
        where=Path("/tmp/x"),
    )
    assert to_jsonable(obj) == {
        "name": "x",
        "inner": {"when": "2026-07-12T00:00:00+00:00"},
        "tags": ["a", "b"],
        "where": "/tmp/x",
    }


def test_print_json_single_document(capsys):
    print_json([{"a": 1}])
    out = capsys.readouterr().out
    assert json.loads(out) == [{"a": 1}]
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_json_out.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement** — `src/teilauto/output/json_out.py`:

```python
from __future__ import annotations

import dataclasses
import json
from datetime import datetime
from pathlib import Path

import click


def to_jsonable(obj: object) -> object:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {
            f.name: to_jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)
        }
    if isinstance(obj, dict):
        return {key: to_jsonable(value) for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(item) for item in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    return obj


def print_json(obj: object) -> None:
    click.echo(json.dumps(to_jsonable(obj), indent=2, ensure_ascii=False))
```

- [ ] **Step 4: Run** — `uv run pytest tests/test_json_out.py -q` → all pass.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: JSON output serializer"`

---

### Task 9: services/availability.py

**Files:**
- Create: `src/teilauto/services/__init__.py` (empty), `src/teilauto/services/availability.py`
- Test: `tests/test_availability.py`

**Interfaces:**
- Consumes: `CantamenClient` (Task 5), `haversine_m` (Task 2), models (Task 4).
- Produces: `CarAvailability` frozen dataclass `(car: Car, distance_m: int | None, available: bool, free_from: str | None)`;
  `find_cars(client, *, lat, lng, radius_m, start, end, car_type: str | None = CITYFLITZER_TYPE, min_fuel: float = 0.0, only_available: bool = False) -> list[CarAvailability]` — POI+proposals merged, type/fuel/haversine-radius filtered, distance-sorted;
  `describe(ca: CarAvailability) -> str` — one-line plain-text summary used for notifications.

- [ ] **Step 1: Write failing tests** — `tests/test_availability.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

import httpx

from teilauto.api.client import BASE_URL, CantamenClient
from teilauto.services.availability import describe, find_cars

START = datetime(2026, 7, 12, 10, 0, tzinfo=timezone.utc)
END = datetime(2026, 7, 12, 10, 30, tzinfo=timezone.utc)
HOME = {"lat": 51.33853, "lng": 12.39163, "radius_m": 500}


def _mock_routes(respx_mock, poi_json, proposals_json):
    respx_mock.get(f"{BASE_URL}/pointsofinterest").mock(
        return_value=httpx.Response(200, json=poi_json)
    )
    respx_mock.get(f"{BASE_URL}/bookingproposals").mock(
        return_value=httpx.Response(200, json=proposals_json)
    )


def test_find_cars_filters_type_and_merges_availability(respx_mock, poi_json, proposals_json):
    _mock_routes(respx_mock, poi_json, proposals_json)
    with CantamenClient() as client:
        items = find_cars(client, start=START, end=END, **HOME)
    # only the two cityFlitzers; the "classic" station car is filtered out
    assert [ca.car.id for ca in items] == ["111", "222"]
    assert items[0].available is True
    assert items[0].free_from == "2026-07-12T10:00:00.000Z"
    assert items[1].available is False
    # both fixtures are within a few hundred metres of HOME
    assert items[0].distance_m is not None and items[0].distance_m < 500
    # sorted by distance ascending
    assert items[0].distance_m <= (items[1].distance_m or 0) or items[0].car.id == "111"


def test_min_fuel_filter(respx_mock, poi_json, proposals_json):
    _mock_routes(respx_mock, poi_json, proposals_json)
    with CantamenClient() as client:
        items = find_cars(client, start=START, end=END, min_fuel=50, **HOME)
    assert [ca.car.id for ca in items] == ["111"]  # Golf has 20% fuel


def test_only_available_filter(respx_mock, poi_json, proposals_json):
    _mock_routes(respx_mock, poi_json, proposals_json)
    with CantamenClient() as client:
        items = find_cars(client, start=START, end=END, only_available=True, **HOME)
    assert [ca.car.id for ca in items] == ["111"]


def test_car_type_none_includes_all(respx_mock, poi_json, proposals_json):
    _mock_routes(respx_mock, poi_json, proposals_json)
    with CantamenClient() as client:
        items = find_cars(client, start=START, end=END, car_type=None, **HOME)
    assert len(items) == 3


def test_describe_line(respx_mock, poi_json, proposals_json):
    _mock_routes(respx_mock, poi_json, proposals_json)
    with CantamenClient() as client:
        items = find_cars(client, start=START, end=END, **HOME)
    line = describe(items[0])
    assert "VW Polo" in line
    assert "L-TA 1111" in line
    assert "Dresdner Str. 6" in line
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_availability.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement** — `src/teilauto/services/availability.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from teilauto.api.client import CantamenClient
from teilauto.api.models import CITYFLITZER_TYPE, Car
from teilauto.core.geo import haversine_m


@dataclass(frozen=True)
class CarAvailability:
    car: Car
    distance_m: int | None
    available: bool
    free_from: str | None


def find_cars(
    client: CantamenClient,
    *,
    lat: float,
    lng: float,
    radius_m: int,
    start: datetime,
    end: datetime,
    car_type: str | None = CITYFLITZER_TYPE,
    min_fuel: float = 0.0,
    only_available: bool = False,
) -> list[CarAvailability]:
    """Merge car metadata (POI) with the bookability oracle (proposals).

    The API's own distance field is unreliable; distances are recomputed via
    haversine and cars outside radius_m are dropped.
    """
    cars = client.points_of_interest(lat=lat, lng=lng, radius_m=radius_m, start=start, end=end)
    free_from_by_id = {
        p.bookee_id: p.free_from
        for p in client.booking_proposals(
            lat=lat, lng=lng, radius_m=radius_m, start=start, end=end
        )
    }
    items: list[CarAvailability] = []
    for car in cars:
        if car_type is not None and car.car_type != car_type:
            continue
        if (car.fuel or 0) < min_fuel:
            continue
        distance = None
        if car.lat is not None and car.lng is not None:
            distance = round(haversine_m(lat, lng, car.lat, car.lng))
            if distance > radius_m:
                continue
        available = car.id in free_from_by_id
        if only_available and not available:
            continue
        items.append(
            CarAvailability(
                car=car,
                distance_m=distance,
                available=available,
                free_from=free_from_by_id.get(car.id),
            )
        )
    items.sort(key=lambda ca: (ca.distance_m is None, ca.distance_m or 0))
    return items


def describe(ca: CarAvailability) -> str:
    """One-line plain-text car summary for notifications and logs."""
    car = ca.car
    bits = [f"{car.name} ({car.plate})" if car.plate else car.name]
    if ca.distance_m is not None:
        bits.append(f"{ca.distance_m}m away")
    if car.fuel is not None:
        bits.append(f"fuel {car.fuel:.0f}%")
    line = ", ".join(bits)
    if car.address:
        line += f" @ {car.address}"
    return line
```

- [ ] **Step 4: Run** — `uv run pytest tests/test_availability.py -q` → all pass.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: availability service merging POI metadata with booking proposals"`

---

### Task 10: services/notify — Telegram + ntfy

**Files:**
- Create: `src/teilauto/services/notify/__init__.py`, `src/teilauto/services/notify/base.py`, `src/teilauto/services/notify/telegram.py`, `src/teilauto/services/notify/ntfy.py`
- Test: `tests/test_notify.py`

**Interfaces:**
- Consumes: `Settings` (Task 6), `tokenstore.load_secret`/`TG_BOT_TOKEN_KEY` (Task 7), `ConfigError` (Task 4).
- Produces (re-exported from `teilauto.services.notify`):
  `Notifier` protocol (`name: str`, `send(title: str, message: str) -> None`);
  `TelegramNotifier(bot_token: str, chat_id: str)`; `NtfyNotifier(server: str, topic: str)`;
  `build_notifiers(settings: Settings) -> list[Notifier]` — env `TEILAUTO_TG_BOT_TOKEN` beats keyring secret; raises `ConfigError` with hint if a configured channel is missing its settings or unknown;
  `send_all(notifiers, title, message) -> list[str]` — never raises, returns error strings.
  ntfy titles must stay ASCII (HTTP header); put emoji in the message body only.

- [ ] **Step 1: Write failing tests** — `tests/test_notify.py`:

```python
from __future__ import annotations

import httpx
import pytest

from teilauto.api.errors import ConfigError
from teilauto.core.config import Settings
from teilauto.services.notify import (
    NtfyNotifier,
    TelegramNotifier,
    build_notifiers,
    send_all,
)


def _settings(**kw) -> Settings:
    base = dict(
        lat=51.0, lng=12.0, radius_m=500, min_fuel=0.0, window_min=30, interval_sec=120,
        prov_id="118", channels=(), tg_chat_id="", ntfy_topic="", ntfy_server="https://ntfy.sh",
    )
    base.update(kw)
    return Settings(**base)


def test_telegram_sends(respx_mock):
    route = respx_mock.post("https://api.telegram.org/botTOK/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    TelegramNotifier("TOK", "42").send("Title", "Body")
    body = route.calls.last.request.content.decode()
    assert "chat_id=42" in body
    assert "Title" in body


def test_ntfy_sends_title_header(respx_mock):
    route = respx_mock.post("https://ntfy.sh/my-topic").mock(return_value=httpx.Response(200))
    NtfyNotifier("https://ntfy.sh", "my-topic").send("Car booked", "VW Polo")
    req = route.calls.last.request
    assert req.headers["title"] == "Car booked"
    assert req.content == b"VW Polo"


def test_build_notifiers_from_settings(monkeypatch):
    monkeypatch.setenv("TEILAUTO_TG_BOT_TOKEN", "TOK")
    notifiers = build_notifiers(
        _settings(channels=("telegram", "ntfy"), tg_chat_id="42", ntfy_topic="t")
    )
    assert [n.name for n in notifiers] == ["telegram", "ntfy"]


def test_build_notifiers_missing_telegram_config(monkeypatch):
    monkeypatch.delenv("TEILAUTO_TG_BOT_TOKEN", raising=False)
    monkeypatch.setattr(
        "teilauto.services.notify.base.load_secret", lambda name: None
    )
    with pytest.raises(ConfigError, match="[Tt]elegram"):
        build_notifiers(_settings(channels=("telegram",), tg_chat_id="42"))


def test_build_notifiers_unknown_channel():
    with pytest.raises(ConfigError, match="pigeon"):
        build_notifiers(_settings(channels=("pigeon",)))


def test_send_all_isolates_failures(respx_mock):
    respx_mock.post("https://ntfy.sh/t").mock(return_value=httpx.Response(500))
    errors = send_all([NtfyNotifier("https://ntfy.sh", "t")], "x", "y")
    assert len(errors) == 1
    assert "ntfy" in errors[0]
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_notify.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement**

`src/teilauto/services/notify/telegram.py`:
```python
from __future__ import annotations

import httpx


class TelegramNotifier:
    name = "telegram"

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id

    def send(self, title: str, message: str) -> None:
        text = f"{title}\n{message}" if title else message
        resp = httpx.post(
            f"https://api.telegram.org/bot{self._bot_token}/sendMessage",
            data={"chat_id": self._chat_id, "text": text},
            timeout=20.0,
        )
        resp.raise_for_status()
```

`src/teilauto/services/notify/ntfy.py`:
```python
from __future__ import annotations

import httpx


class NtfyNotifier:
    name = "ntfy"

    def __init__(self, server: str, topic: str) -> None:
        self._url = f"{server.rstrip('/')}/{topic}"

    def send(self, title: str, message: str) -> None:
        # HTTP headers are latin-1: keep titles ASCII, emoji go in the body.
        headers = {"Title": title} if title else {}
        resp = httpx.post(self._url, content=message.encode(), headers=headers, timeout=20.0)
        resp.raise_for_status()
```

`src/teilauto/services/notify/base.py`:
```python
from __future__ import annotations

import os
from typing import Protocol, Sequence

from teilauto.api.errors import ConfigError
from teilauto.core.config import Settings
from teilauto.core.tokenstore import TG_BOT_TOKEN_KEY, load_secret
from teilauto.services.notify.ntfy import NtfyNotifier
from teilauto.services.notify.telegram import TelegramNotifier


class Notifier(Protocol):
    name: str

    def send(self, title: str, message: str) -> None: ...


def build_notifiers(settings: Settings) -> list[Notifier]:
    notifiers: list[Notifier] = []
    for channel in settings.channels:
        if channel == "telegram":
            token = os.getenv("TEILAUTO_TG_BOT_TOKEN") or load_secret(TG_BOT_TOKEN_KEY)
            if not token or not settings.tg_chat_id:
                raise ConfigError(
                    "Telegram channel is configured but bot token or chat_id is missing.",
                    hint=(
                        "Set the token with `teilauto config set notify.telegram.bot_token "
                        "<token>` and the chat with `teilauto config set "
                        "notify.telegram.chat_id <id>`."
                    ),
                )
            notifiers.append(TelegramNotifier(token, settings.tg_chat_id))
        elif channel == "ntfy":
            if not settings.ntfy_topic:
                raise ConfigError(
                    "ntfy channel is configured but no topic is set.",
                    hint="Run `teilauto config set notify.ntfy.topic <topic>`.",
                )
            notifiers.append(NtfyNotifier(settings.ntfy_server, settings.ntfy_topic))
        else:
            raise ConfigError(
                f"Unknown notification channel: {channel!r}.",
                hint="Valid channels: telegram, ntfy.",
            )
    return notifiers


def send_all(notifiers: Sequence[Notifier], title: str, message: str) -> list[str]:
    """Send to every notifier; never raises. Returns human-readable error strings."""
    errors: list[str] = []
    for notifier in notifiers:
        try:
            notifier.send(title, message)
        except Exception as exc:
            errors.append(f"{notifier.name}: {exc}")
    return errors
```

`src/teilauto/services/notify/__init__.py`:
```python
from __future__ import annotations

from teilauto.services.notify.base import Notifier, build_notifiers, send_all
from teilauto.services.notify.ntfy import NtfyNotifier
from teilauto.services.notify.telegram import TelegramNotifier

__all__ = ["Notifier", "NtfyNotifier", "TelegramNotifier", "build_notifiers", "send_all"]
```

- [ ] **Step 4: Run** — `uv run pytest tests/test_notify.py -q` → all pass.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: pluggable Telegram and ntfy notifiers"`

---

### Task 11: services/watcher.py — poll engine

**Files:**
- Create: `src/teilauto/services/watcher.py`
- Test: `tests/test_watcher.py`

**Interfaces:**
- Consumes: `CarAvailability` (Task 9).
- Produces: `WatchTick` frozen dataclass `(nearby: int, available: int, new: tuple[CarAvailability, ...], error: str | None = None)`;
  `watch(fetch: Callable[[], list[CarAvailability]], *, interval: float, max_sleep: float = 1800.0, sleeper: Callable[[float], None] = time.sleep) -> Iterator[WatchTick]` — infinite generator; yields a tick per poll (first tick reports every currently-available car as new); on `fetch` exception yields an error tick, doubles sleep up to `max_sleep`, keeps the previous seen-set; success resets sleep; sleeps AFTER each yield.

- [ ] **Step 1: Write failing tests** — `tests/test_watcher.py`:

```python
from __future__ import annotations

from itertools import islice

import pytest

from teilauto.api.models import Car
from teilauto.services.availability import CarAvailability
from teilauto.services.watcher import WatchTick, watch


def _car(car_id: str, available: bool = True) -> CarAvailability:
    return CarAvailability(
        car=Car(id=car_id, name=f"Car {car_id}", plate=None, fuel=50,
                car_type="cityFlitzer", lat=None, lng=None, address=None),
        distance_m=100, available=available, free_from=None,
    )


def test_first_tick_reports_available_as_new():
    fetch_results = iter([[_car("1"), _car("2", available=False)]])
    ticks = list(islice(watch(lambda: next(fetch_results), interval=1, sleeper=lambda s: None), 1))
    assert ticks[0].nearby == 2
    assert ticks[0].available == 1
    assert [ca.car.id for ca in ticks[0].new] == ["1"]


def test_only_transitions_are_new():
    results = iter([[_car("1")], [_car("1"), _car("2")], [_car("1"), _car("2")]])
    gen = watch(lambda: next(results), interval=1, sleeper=lambda s: None)
    t1, t2, t3 = islice(gen, 3)
    assert [ca.car.id for ca in t1.new] == ["1"]
    assert [ca.car.id for ca in t2.new] == ["2"]
    assert t3.new == ()


def test_disappear_and_reappear_is_new_again():
    results = iter([[_car("1")], [], [_car("1")]])
    gen = watch(lambda: next(results), interval=1, sleeper=lambda s: None)
    t1, t2, t3 = islice(gen, 3)
    assert len(t1.new) == 1
    assert t2.new == ()
    assert len(t3.new) == 1


def test_backoff_doubles_and_resets():
    sleeps: list[float] = []
    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        if calls["n"] in (2, 3):
            raise RuntimeError("api down")
        return [_car("1")]

    gen = watch(fetch, interval=10, max_sleep=25, sleeper=sleeps.append)
    ticks = list(islice(gen, 5))
    assert ticks[1].error == "api down"
    assert ticks[2].error == "api down"
    assert ticks[3].error is None
    assert sleeps == [10, 20, 25, 10, 10]


def test_error_keeps_seen_set():
    results = iter([[_car("1")], RuntimeError("x"), [_car("1")]])

    def fetch():
        item = next(results)
        if isinstance(item, Exception):
            raise item
        return item

    gen = watch(fetch, interval=1, sleeper=lambda s: None)
    t1, t2, t3 = islice(gen, 3)
    assert len(t1.new) == 1
    assert t2.error == "x"
    assert t3.new == ()  # car "1" was already known before the outage
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_watcher.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement** — `src/teilauto/services/watcher.py`:

```python
from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from teilauto.services.availability import CarAvailability


@dataclass(frozen=True)
class WatchTick:
    nearby: int
    available: int
    new: tuple[CarAvailability, ...]
    error: str | None = None


def watch(
    fetch: Callable[[], list[CarAvailability]],
    *,
    interval: float,
    max_sleep: float = 1800.0,
    sleeper: Callable[[float], None] = time.sleep,
) -> Iterator[WatchTick]:
    """Poll `fetch` forever, yielding a tick per cycle.

    `new` contains cars that transitioned into availability since the last
    successful poll (the first tick reports everything available as new).
    Failed polls yield an error tick, double the sleep (capped at max_sleep)
    and keep the previous seen-set so recovery does not re-notify.
    """
    seen: set[str] = set()
    sleep = interval
    while True:
        try:
            cars = fetch()
        except Exception as exc:
            yield WatchTick(nearby=0, available=0, new=(), error=str(exc))
            sleep = min(sleep * 2, max_sleep)
        else:
            available = [ca for ca in cars if ca.available]
            current = {ca.car.id for ca in available}
            new = tuple(ca for ca in available if ca.car.id not in seen)
            seen = current
            sleep = interval
            yield WatchTick(nearby=len(cars), available=len(available), new=new)
        sleeper(sleep)
```

- [ ] **Step 4: Run** — `uv run pytest tests/test_watcher.py -q` → all pass.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: transition-based watcher engine with failure backoff"`

---

### Task 12: CLI root — context, error handling, shared options, render basics

**Files:**
- Modify: `src/teilauto/cli/__init__.py` (replace with full version)
- Create: `src/teilauto/cli/options.py`, `src/teilauto/output/render.py`
- Modify: `tests/conftest.py` (add CLI fixtures)
- Test: `tests/test_cli_root.py`

**Interfaces:**
- Consumes: `load_settings`/`Settings` (6), `tokenstore` (7), `CantamenClient` (5), errors (4), `parse_time`/`parse_duration` (3).
- Produces:
  - `teilauto.cli.AppContext` dataclass `(settings: Settings, verbose: bool = False, quiet: bool = False)` with `client() -> CantamenClient` (token attached if stored) and `require_auth_client() -> CantamenClient` (raises `AuthRequiredError` when no token). Attribute `token: StoredToken | None` property.
  - `teilauto.cli.cli` root group (populated with subgroups in later tasks via `cli.add_command`), `main()` mapping `TeilautoError` → stderr message+hint & `exit_code`, `KeyboardInterrupt` → 130, `click.exceptions.Abort` → "Aborted." & 1.
  - `teilauto.cli.options`: `json_option(f)` (flag `--json` → param `as_json`); `location_options(f)` (`--lat`, `--lng`, `--radius` → `radius_m`, all default None); `window_options(f)` (`--from` → `start_text` default `"now"`, `--for` → `duration_text`, `--until` → `until_text`); `resolve_location(settings, lat, lng, radius_m) -> tuple[float, float, int]`; `resolve_window(start_text, duration_text, until_text, *, default_minutes) -> tuple[datetime, datetime]` (raises `click.UsageError` when both `--for`/`--until` given or end ≤ start; wraps `ValueError` in `click.BadParameter`).
  - `teilauto.output.render`: `console: Console`, `err_console: Console(stderr=True)`, `fuel_text(fuel: float | None) -> Text` (green ≥50, yellow ≥25, red <25, dim "?" when None), `kv_panel(title: str, mapping: dict[str, object]) -> Panel`, `local_time(iso: str | None) -> str` (ISO/Z string → `%Y-%m-%d %H:%M` local, "—" for None/unparseable).
  - conftest: `runner` fixture (`CliRunner()`), `isolated_config` fixture (sets `TEILAUTO_CONFIG_DIR` to tmp, disables keyring, clears `TEILAUTO_TOKEN`/`TEILAUTO_TG_BOT_TOKEN`), `logged_in` fixture (isolated_config + stored token `tok-abc123`).

- [ ] **Step 1: Extend conftest** — append to `tests/conftest.py`:

```python
from click.testing import CliRunner

from teilauto.core import tokenstore as _tokenstore
from teilauto.core.tokenstore import StoredToken


class _NoKeyring:
    def set_password(self, *a):
        raise RuntimeError("no keyring in tests")

    def get_password(self, *a):
        raise RuntimeError("no keyring in tests")

    def delete_password(self, *a):
        raise RuntimeError("no keyring in tests")


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("TEILAUTO_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("TEILAUTO_TOKEN", raising=False)
    monkeypatch.delenv("TEILAUTO_TG_BOT_TOKEN", raising=False)
    monkeypatch.setattr(_tokenstore, "keyring", _NoKeyring())
    return tmp_path


@pytest.fixture
def logged_in(isolated_config):
    _tokenstore.save_token(
        StoredToken(id="tok-abc123", expiry="2026-10-10T00:00:00.000Z", customer_id="cust-9")
    )
    return isolated_config
```

- [ ] **Step 2: Write failing tests** — `tests/test_cli_root.py`:

```python
from __future__ import annotations

import click
import pytest

from teilauto.cli import cli, main
from teilauto.cli.options import resolve_location, resolve_window
from teilauto.core.config import Settings
from teilauto.output.render import fuel_text, local_time

SETTINGS = Settings(
    lat=51.0, lng=12.0, radius_m=500, min_fuel=0.0, window_min=30, interval_sec=120,
    prov_id="118", channels=(), tg_chat_id="", ntfy_topic="", ntfy_server="https://ntfy.sh",
)


def test_help_lists_groups(runner, isolated_config):
    result = runner.invoke(cli, ["-h"])
    assert result.exit_code == 0


def test_resolve_location_flag_beats_settings():
    assert resolve_location(SETTINGS, 50.0, None, None) == (50.0, 12.0, 500)
    assert resolve_location(SETTINGS, None, None, 900) == (51.0, 12.0, 900)


def test_resolve_window_default_minutes():
    start, end = resolve_window("now", None, None, default_minutes=30)
    assert (end - start).total_seconds() == 30 * 60


def test_resolve_window_for_and_until_conflict():
    with pytest.raises(click.UsageError, match="mutually exclusive"):
        resolve_window("now", "1h", "18:00", default_minutes=30)


def test_resolve_window_bad_time_is_bad_parameter():
    with pytest.raises(click.BadParameter, match="Cannot parse"):
        resolve_window("banana", None, None, default_minutes=30)


def test_main_renders_teilauto_error(monkeypatch, capsys, isolated_config):
    monkeypatch.setattr("sys.argv", ["teilauto", "bookings", "list"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 3  # not logged in
    err = capsys.readouterr().err
    assert "auth login" in err


def test_fuel_text_colors():
    assert fuel_text(80).style == "green"
    assert fuel_text(30).style == "yellow"
    assert fuel_text(10).style == "red"
    assert "?" in str(fuel_text(None))


def test_local_time_handles_z_and_none():
    assert local_time(None) == "—"
    assert local_time("2026-07-12T10:00:00.000Z") != "—"
```

Note: `test_main_renders_teilauto_error` needs `bookings list` which arrives in
Task 15. Until then mark it `@pytest.mark.xfail(reason="bookings group lands in Task 15")`
— Task 15 removes the marker.

- [ ] **Step 3: Run to verify failure** — `uv run pytest tests/test_cli_root.py -q` → ImportError.

- [ ] **Step 4: Implement**

`src/teilauto/output/render.py`:
```python
from __future__ import annotations

from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()
err_console = Console(stderr=True)


def fuel_text(fuel: float | None) -> Text:
    if fuel is None:
        return Text("?", style="dim")
    style = "green" if fuel >= 50 else "yellow" if fuel >= 25 else "red"
    return Text(f"{fuel:.0f}%", style=style)


def local_time(iso: str | None) -> str:
    """Render an API ISO/Z timestamp as local '%Y-%m-%d %H:%M'."""
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return iso
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


def kv_panel(title: str, mapping: dict[str, object]) -> Panel:
    body = Text()
    width = max((len(key) for key in mapping), default=0)
    for key, value in mapping.items():
        body.append(f"{key.rjust(width)}  ", style="bold dim")
        body.append(f"{value}\n")
    return Panel(body, title=title, expand=False)
```

`src/teilauto/cli/options.py`:
```python
from __future__ import annotations

from datetime import datetime

import rich_click as click

from teilauto.core.config import Settings
from teilauto.core.timeparse import parse_duration, parse_time


def json_option(f):
    return click.option("--json", "as_json", is_flag=True, help="Output machine-readable JSON.")(f)


def location_options(f):
    f = click.option("--radius", "radius_m", type=int, default=None, metavar="METRES",
                     help="Search radius in metres (default: config).")(f)
    f = click.option("--lng", type=float, default=None, help="Longitude (default: config).")(f)
    f = click.option("--lat", type=float, default=None, help="Latitude (default: config).")(f)
    return f


def window_options(f):
    f = click.option("--until", "until_text", default=None, metavar="TIME",
                     help="Window end, e.g. '18:00' or 'tomorrow 09:00'.")(f)
    f = click.option("--for", "duration_text", default=None, metavar="DURATION",
                     help="Window length, e.g. '30m', '2h', '1h30m'.")(f)
    f = click.option("--from", "start_text", default="now", metavar="TIME", show_default=True,
                     help="Window start, e.g. 'now', '14:30', 'tomorrow 09:00'.")(f)
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
```

`src/teilauto/cli/__init__.py` (full replacement):
```python
from __future__ import annotations

import sys
from dataclasses import dataclass, field

import rich_click as click

from teilauto.api.client import CantamenClient
from teilauto.api.errors import AuthRequiredError, TeilautoError
from teilauto.core import tokenstore
from teilauto.core.config import Settings, load_settings
from teilauto.core.tokenstore import StoredToken
from teilauto.output.render import err_console

click.rich_click.SHOW_ARGUMENTS = True

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@dataclass
class AppContext:
    settings: Settings
    verbose: bool = False
    quiet: bool = False
    _token: StoredToken | None = field(default=None, init=False, repr=False)
    _token_loaded: bool = field(default=False, init=False, repr=False)

    @property
    def token(self) -> StoredToken | None:
        if not self._token_loaded:
            self._token = tokenstore.load_token()
            self._token_loaded = True
        return self._token

    def client(self) -> CantamenClient:
        token = self.token
        return CantamenClient(token_id=token.id if token else None, verbose=self.verbose)

    def require_auth_client(self) -> CantamenClient:
        if self.token is None:
            raise AuthRequiredError()
        return CantamenClient(token_id=self.token.id, verbose=self.verbose)


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(package_name="teilauto-cli", prog_name="teilauto")
@click.option("-v", "--verbose", is_flag=True, help="Show HTTP requests and debug detail.")
@click.option("-q", "--quiet", is_flag=True, help="Suppress non-essential output.")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, quiet: bool) -> None:
    """Manage teilauto/CityFlitzer carsharing from your terminal.

    Search cars, check prices, manage bookings — and auto-book a car the
    moment it becomes available.
    """
    ctx.obj = AppContext(settings=load_settings(), verbose=verbose, quiet=quiet)


def main() -> None:
    try:
        cli(standalone_mode=False)
    except click.exceptions.Exit as exc:
        sys.exit(exc.exit_code)
    except click.exceptions.Abort:
        err_console.print("Aborted.")
        sys.exit(1)
    except click.ClickException as exc:
        exc.show()
        sys.exit(exc.exit_code)
    except TeilautoError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        if exc.hint:
            err_console.print(f"[dim]{exc.hint}[/dim]")
        sys.exit(exc.exit_code)
    except KeyboardInterrupt:
        err_console.print("\nStopped.")
        sys.exit(130)
```

- [ ] **Step 5: Run** — `uv run pytest tests/test_cli_root.py tests/test_smoke.py -q` → pass (1 xfail).
- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: CLI root with app context, shared options, rich error handling"`

---

### Task 13: `teilauto auth` group

**Files:**
- Create: `src/teilauto/cli/auth.py`
- Modify: `src/teilauto/cli/__init__.py` (register group at the bottom, before `main`)
- Test: `tests/test_cli_auth.py`

**Interfaces:**
- Consumes: `AppContext`, `CantamenClient.login`, `tokenstore`, `kv_panel`, `local_time`, `print_json`, `json_option`.
- Produces: `auth` group with `login`, `status` (exit 3 when not logged in; `--json` gives `{"logged_in", "expiry", "customer_id"}`), `logout`.

- [ ] **Step 1: Write failing tests** — `tests/test_cli_auth.py`:

```python
from __future__ import annotations

import json

import httpx

from teilauto.cli import cli
from teilauto.core import tokenstore


def test_login_stores_token(runner, isolated_config, respx_mock, token_json):
    respx_mock.post("https://de1.cantamen.de/casirest/v3/tokens").mock(
        return_value=httpx.Response(200, json=token_json)
    )
    result = runner.invoke(cli, ["auth", "login"], input="me@example.org\nhunter2\n")
    assert result.exit_code == 0, result.output
    assert "Logged in" in result.output
    stored = tokenstore.load_token()
    assert stored is not None and stored.id == "tok-abc123"


def test_status_logged_in_json(runner, logged_in):
    result = runner.invoke(cli, ["auth", "status", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["logged_in"] is True
    assert data["customer_id"] == "cust-9"


def test_status_not_logged_in_exits_3(runner, isolated_config):
    result = runner.invoke(cli, ["auth", "status"])
    assert result.exit_code == 3
    assert "Not logged in" in result.output


def test_logout_removes_token(runner, logged_in):
    result = runner.invoke(cli, ["auth", "logout"])
    assert result.exit_code == 0
    assert tokenstore.load_token() is None
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_cli_auth.py -q` → fails (no `auth` command).

- [ ] **Step 3: Implement** — `src/teilauto/cli/auth.py`:

```python
from __future__ import annotations

import rich_click as click

from teilauto.api.client import CantamenClient
from teilauto.cli.options import json_option
from teilauto.core import tokenstore
from teilauto.core.tokenstore import StoredToken
from teilauto.output.json_out import print_json
from teilauto.output.render import console, kv_panel, local_time


@click.group()
def auth() -> None:
    """Log in to your teilauto account and manage the session token."""


@auth.command()
@click.option("--email", prompt="Email", help="Your teilauto account email.")
@click.option("--password", prompt="Password", hide_input=True,
              help="Account password (never stored — only the session token is kept).")
@click.pass_obj
def login(app, email: str, password: str) -> None:
    """Authenticate once; the returned token is valid for about 90 days."""
    with CantamenClient(verbose=app.verbose) as client:
        info = client.login(email, password, prov_id=app.settings.prov_id)
    tokenstore.save_token(
        StoredToken(id=info.id, expiry=info.expiry, customer_id=info.customer_id)
    )
    console.print(
        f"[green]✓ Logged in.[/green] Token valid until {local_time(info.expiry)}."
    )


@auth.command()
@json_option
@click.pass_obj
def status(app, as_json: bool) -> None:
    """Show whether you are logged in and until when the token is valid."""
    token = app.token
    if as_json:
        print_json(
            {
                "logged_in": token is not None,
                "expiry": token.expiry if token else None,
                "customer_id": token.customer_id if token else None,
            }
        )
        if token is None:
            raise SystemExit(3)
        return
    if token is None:
        console.print("[yellow]Not logged in.[/yellow] Run `teilauto auth login`.")
        raise SystemExit(3)
    console.print(
        kv_panel(
            "Session",
            {
                "logged in": "yes",
                "token expiry": local_time(token.expiry),
                "customer id": token.customer_id or "—",
            },
        )
    )


@auth.command()
def logout() -> None:
    """Delete the stored session token."""
    tokenstore.delete_token()
    console.print("Logged out — token removed.")
```

Register in `src/teilauto/cli/__init__.py` after the `cli` group definition
(import placed there to avoid circular imports):

```python
from teilauto.cli.auth import auth  # noqa: E402

cli.add_command(auth)
```

- [ ] **Step 4: Run** — `uv run pytest tests/test_cli_auth.py -q` → all pass.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: auth login/status/logout commands"`

---

### Task 14: `teilauto cars` group + `teilauto price` + tables

**Files:**
- Create: `src/teilauto/cli/cars.py`, `src/teilauto/cli/price.py`
- Modify: `src/teilauto/output/render.py` (add `cars_table`, `car_detail`, `unavailability_table`), `src/teilauto/cli/__init__.py` (register)
- Test: `tests/test_cli_cars.py`

**Interfaces:**
- Consumes: `find_cars`, `CarAvailability`, client methods, options helpers, render/json helpers.
- Produces:
  - `cars` group: `cars list` (options: location, window, `--type [cityflitzer|all]` default cityflitzer, `--available`, `--min-fuel FLOAT`, `--json`), `cars show CAR_ID` (window options for the unavailability range, default 24h ⇒ `default_minutes=1440`, `--json` gives `{"car": ..., "distance_m": null, "unavailabilities": [...]}`).
  - `price` command: `price CAR_ID` + window options + `--json` (`{"car_id", "start", "end", "total", "currency"}`).
  - Render: `cars_table(items: list[CarAvailability]) -> Table` (columns ID, Name, Plate, Fuel, Distance, Address, Available — ✓ green when available), `car_detail(car: Car) -> Panel`, `unavailability_table(items: list[Unavailability]) -> Table`.

- [ ] **Step 1: Write failing tests** — `tests/test_cli_cars.py`:

```python
from __future__ import annotations

import json

import httpx

from teilauto.api.client import BASE_URL
from teilauto.cli import cli


def _mock_search(respx_mock, poi_json, proposals_json):
    respx_mock.get(f"{BASE_URL}/pointsofinterest").mock(
        return_value=httpx.Response(200, json=poi_json)
    )
    respx_mock.get(f"{BASE_URL}/bookingproposals").mock(
        return_value=httpx.Response(200, json=proposals_json)
    )


def test_cars_list_table(runner, isolated_config, respx_mock, poi_json, proposals_json):
    _mock_search(respx_mock, poi_json, proposals_json)
    result = runner.invoke(cli, ["cars", "list"])
    assert result.exit_code == 0, result.output
    assert "VW Polo" in result.output
    assert "L-TA 1111" in result.output
    assert "Kombi" not in result.output  # station car filtered by default type


def test_cars_list_json(runner, isolated_config, respx_mock, poi_json, proposals_json):
    _mock_search(respx_mock, poi_json, proposals_json)
    result = runner.invoke(cli, ["cars", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data[0]["car"]["id"] == "111"
    assert data[0]["available"] is True


def test_cars_list_type_all(runner, isolated_config, respx_mock, poi_json, proposals_json):
    _mock_search(respx_mock, poi_json, proposals_json)
    result = runner.invoke(cli, ["cars", "list", "--type", "all", "--json"])
    assert len(json.loads(result.output)) == 3


def test_cars_list_empty_message(runner, isolated_config, respx_mock):
    respx_mock.get(f"{BASE_URL}/pointsofinterest").mock(return_value=httpx.Response(200, json=[]))
    respx_mock.get(f"{BASE_URL}/bookingproposals").mock(return_value=httpx.Response(200, json=[]))
    result = runner.invoke(cli, ["cars", "list"])
    assert result.exit_code == 0
    assert "No cars" in result.output


def test_cars_show(runner, isolated_config, respx_mock, poi_json, unavailabilities_json):
    bookee = poi_json[0]["places"][0]["bookees"][0] | {"place": poi_json[0]["places"][0]}
    respx_mock.get(f"{BASE_URL}/bookees/111").mock(return_value=httpx.Response(200, json=bookee))
    respx_mock.get(f"{BASE_URL}/unavailabilities").mock(
        return_value=httpx.Response(200, json=unavailabilities_json)
    )
    result = runner.invoke(cli, ["cars", "show", "111"])
    assert result.exit_code == 0
    assert "VW Polo" in result.output


def test_price_json(runner, isolated_config, respx_mock, prices_json):
    respx_mock.get(f"{BASE_URL}/prices").mock(return_value=httpx.Response(200, json=prices_json))
    result = runner.invoke(cli, ["price", "111", "--for", "1h", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total"] == 4.9
    assert data["currency"] == "EUR"
    assert data["car_id"] == "111"
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_cli_cars.py -q` → fails.

- [ ] **Step 3: Implement**

Append to `src/teilauto/output/render.py`:
```python
from rich.table import Table

from teilauto.api.models import Car, Unavailability
from teilauto.services.availability import CarAvailability


def cars_table(items: list[CarAvailability]) -> Table:
    table = Table(title="Cars", header_style="bold")
    for column in ("ID", "Name", "Plate", "Fuel", "Distance", "Address", "Available"):
        table.add_column(column)
    for ca in items:
        available = (
            Text("✓ now", style="green")
            if ca.available
            else Text("✗", style="dim")
        )
        table.add_row(
            ca.car.id,
            ca.car.name,
            ca.car.plate or "—",
            fuel_text(ca.car.fuel),
            f"{ca.distance_m} m" if ca.distance_m is not None else "—",
            ca.car.address or "—",
            available,
        )
    return table


def car_detail(car: Car) -> Panel:
    return kv_panel(
        f"{car.name} ({car.id})",
        {
            "plate": car.plate or "—",
            "type": car.car_type or "—",
            "fuel": f"{car.fuel:.0f}%" if car.fuel is not None else "—",
            "address": car.address or "—",
            "position": f"{car.lat}, {car.lng}" if car.lat is not None else "—",
        },
    )


def unavailability_table(items: list[Unavailability]) -> Table:
    table = Table(title="Blocked time ranges", header_style="bold")
    table.add_column("From")
    table.add_column("Until")
    for item in items:
        table.add_row(local_time(item.start), local_time(item.end))
    return table
```

`src/teilauto/cli/cars.py`:
```python
from __future__ import annotations

import rich_click as click

from teilauto.api.models import CITYFLITZER_TYPE
from teilauto.cli.options import (
    json_option,
    location_options,
    resolve_location,
    resolve_window,
    window_options,
)
from teilauto.output.json_out import print_json
from teilauto.output.render import car_detail, cars_table, console, unavailability_table
from teilauto.services.availability import find_cars


@click.group()
def cars() -> None:
    """Find cars near you and inspect their availability."""


@cars.command("list")
@location_options
@window_options
@click.option("--type", "car_type", type=click.Choice(["cityflitzer", "all"]),
              default="cityflitzer", show_default=True, help="Car type filter.")
@click.option("--available", "only_available", is_flag=True,
              help="Show only cars bookable in the window.")
@click.option("--min-fuel", type=float, default=None, metavar="PERCENT",
              help="Hide cars below this fuel level (default: config).")
@json_option
@click.pass_obj
def list_cars(app, lat, lng, radius_m, start_text, duration_text, until_text,
              car_type, only_available, min_fuel, as_json) -> None:
    """List cars near a location, closest first."""
    settings = app.settings
    lat, lng, radius_m = resolve_location(settings, lat, lng, radius_m)
    start, end = resolve_window(
        start_text, duration_text, until_text, default_minutes=settings.window_min
    )
    with app.client() as client:
        items = find_cars(
            client,
            lat=lat, lng=lng, radius_m=radius_m, start=start, end=end,
            car_type=None if car_type == "all" else CITYFLITZER_TYPE,
            min_fuel=settings.min_fuel if min_fuel is None else min_fuel,
            only_available=only_available,
        )
    if as_json:
        print_json(items)
        return
    if not items:
        console.print("No cars found — try a bigger --radius or --type all.")
        return
    console.print(cars_table(items))


@cars.command("show")
@click.argument("car_id")
@window_options
@json_option
@click.pass_obj
def show_car(app, car_id, start_text, duration_text, until_text, as_json) -> None:
    """Show one car in detail, including when it is blocked (next 24h by default)."""
    start, end = resolve_window(start_text, duration_text, until_text, default_minutes=1440)
    with app.client() as client:
        car = client.get_car(car_id)
        blocked = client.unavailabilities(car_id, start, end)
    if as_json:
        print_json({"car": car, "unavailabilities": blocked})
        return
    console.print(car_detail(car))
    if blocked:
        console.print(unavailability_table(blocked))
    else:
        console.print("[green]No blocked time ranges in the window.[/green]")
```

`src/teilauto/cli/price.py`:
```python
from __future__ import annotations

import rich_click as click

from teilauto.api.client import iso_utc
from teilauto.cli.options import json_option, resolve_window, window_options
from teilauto.output.json_out import print_json
from teilauto.output.render import console, kv_panel


@click.command()
@click.argument("car_id")
@window_options
@json_option
@click.pass_obj
def price(app, car_id, start_text, duration_text, until_text, as_json) -> None:
    """Show the price of booking CAR_ID for a time window."""
    start, end = resolve_window(
        start_text, duration_text, until_text, default_minutes=app.settings.window_min
    )
    with app.client() as client:
        result = client.price(car_id, start, end)
    if as_json:
        print_json(
            {
                "car_id": car_id,
                "start": iso_utc(start),
                "end": iso_utc(end),
                "total": result.total,
                "currency": result.currency,
            }
        )
        return
    total = f"{result.total:.2f} {result.currency}" if result.total is not None else "unknown"
    console.print(
        kv_panel(
            f"Price for car {car_id}",
            {"from": start.strftime("%Y-%m-%d %H:%M"),
             "until": end.strftime("%Y-%m-%d %H:%M"),
             "total": total},
        )
    )
```

Register in `src/teilauto/cli/__init__.py`:
```python
from teilauto.cli.cars import cars  # noqa: E402
from teilauto.cli.price import price  # noqa: E402

cli.add_command(cars)
cli.add_command(price)
```

- [ ] **Step 4: Run** — `uv run pytest tests/test_cli_cars.py -q` → all pass.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: cars list/show and price commands with rich tables"`

---

### Task 15: `teilauto bookings` group

**Files:**
- Create: `src/teilauto/cli/bookings.py`
- Modify: `src/teilauto/output/render.py` (add `bookings_table`), `src/teilauto/cli/__init__.py` (register)
- Modify: `tests/test_cli_root.py` (remove the xfail marker from `test_main_renders_teilauto_error`)
- Test: `tests/test_cli_bookings.py`

**Interfaces:**
- Consumes: `require_auth_client`, `Booking`, `Price`, render/json helpers.
- Produces: `bookings` group: `list` (`--all` includes past; default hides bookings whose `end` is in the past), `show BOOKING_ID`, `create CAR_ID --from --for/--until [--yes]` (shows car + price panel, `click.confirm` unless `--yes`), `cancel BOOKING_ID [--yes]`. Render: `bookings_table(bookings: list[Booking]) -> Table` (ID, Car, From, Until, State).

- [ ] **Step 1: Write failing tests** — `tests/test_cli_bookings.py`:

```python
from __future__ import annotations

import json

import httpx

from teilauto.api.client import BASE_URL
from teilauto.cli import cli


def test_bookings_require_auth(runner, isolated_config):
    result = runner.invoke(cli, ["bookings", "list"])
    assert result.exit_code != 0
    assert isinstance(result.exception, Exception)


def test_bookings_list_hides_past_by_default(runner, logged_in, respx_mock, bookings_json):
    respx_mock.get(f"{BASE_URL}/bookings").mock(
        return_value=httpx.Response(200, json=bookings_json)
    )
    result = runner.invoke(cli, ["bookings", "list", "--json"])
    assert result.exit_code == 0, result.output
    ids = [b["id"] for b in json.loads(result.output)]
    assert ids == ["b-1"]  # b-0 ended 2026-07-01, before "now" (2026-07-12+)


def test_bookings_list_all(runner, logged_in, respx_mock, bookings_json):
    respx_mock.get(f"{BASE_URL}/bookings").mock(
        return_value=httpx.Response(200, json=bookings_json)
    )
    result = runner.invoke(cli, ["bookings", "list", "--all", "--json"])
    assert len(json.loads(result.output)) == 2


def test_bookings_show(runner, logged_in, respx_mock, bookings_json):
    respx_mock.get(f"{BASE_URL}/bookings/b-1").mock(
        return_value=httpx.Response(200, json=bookings_json[0])
    )
    result = runner.invoke(cli, ["bookings", "show", "b-1"])
    assert result.exit_code == 0
    assert "b-1" in result.output


def test_create_prompts_and_books(runner, logged_in, respx_mock,
                                  poi_json, prices_json, bookings_json):
    bookee = poi_json[0]["places"][0]["bookees"][0] | {"place": poi_json[0]["places"][0]}
    respx_mock.get(f"{BASE_URL}/bookees/111").mock(return_value=httpx.Response(200, json=bookee))
    respx_mock.get(f"{BASE_URL}/prices").mock(return_value=httpx.Response(200, json=prices_json))
    post = respx_mock.post(f"{BASE_URL}/bookings").mock(
        return_value=httpx.Response(200, json=bookings_json[0])
    )
    result = runner.invoke(cli, ["bookings", "create", "111", "--for", "1h"], input="y\n")
    assert result.exit_code == 0, result.output
    assert post.called
    assert "Booked" in result.output


def test_create_aborts_on_no(runner, logged_in, respx_mock, poi_json, prices_json):
    bookee = poi_json[0]["places"][0]["bookees"][0] | {"place": poi_json[0]["places"][0]}
    respx_mock.get(f"{BASE_URL}/bookees/111").mock(return_value=httpx.Response(200, json=bookee))
    respx_mock.get(f"{BASE_URL}/prices").mock(return_value=httpx.Response(200, json=prices_json))
    post = respx_mock.post(f"{BASE_URL}/bookings")
    result = runner.invoke(cli, ["bookings", "create", "111", "--for", "1h"], input="n\n")
    assert result.exit_code != 0
    assert not post.called


def test_cancel_with_yes(runner, logged_in, respx_mock):
    route = respx_mock.delete(f"{BASE_URL}/bookings/b-1").mock(
        return_value=httpx.Response(204)
    )
    result = runner.invoke(cli, ["bookings", "cancel", "b-1", "--yes"])
    assert result.exit_code == 0, result.output
    assert route.called
    assert "cancelled" in result.output.lower()
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_cli_bookings.py -q` → fails.

- [ ] **Step 3: Implement**

Append to `src/teilauto/output/render.py`:
```python
from teilauto.api.models import Booking


def bookings_table(bookings: list[Booking]) -> Table:
    table = Table(title="Bookings", header_style="bold")
    for column in ("ID", "Car", "From", "Until", "State"):
        table.add_column(column)
    for booking in bookings:
        table.add_row(
            booking.id,
            booking.bookee_id or "—",
            local_time(booking.start),
            local_time(booking.end),
            booking.state or "—",
        )
    return table
```

`src/teilauto/cli/bookings.py`:
```python
from __future__ import annotations

from datetime import datetime, timezone

import rich_click as click

from teilauto.api.errors import TeilautoError
from teilauto.api.models import Booking
from teilauto.cli.options import json_option, resolve_window, window_options
from teilauto.output.json_out import print_json
from teilauto.output.render import bookings_table, console, kv_panel, local_time


def _is_past(booking: Booking) -> bool:
    if not booking.end:
        return False
    try:
        end = datetime.fromisoformat(booking.end.replace("Z", "+00:00"))
    except ValueError:
        return False
    return end < datetime.now(timezone.utc)


@click.group()
def bookings() -> None:
    """List, create and cancel your bookings (login required)."""


@bookings.command("list")
@click.option("--all", "show_all", is_flag=True, help="Include past bookings.")
@json_option
@click.pass_obj
def list_bookings(app, show_all, as_json) -> None:
    """Show your bookings (upcoming only by default)."""
    with app.require_auth_client() as client:
        items = client.list_bookings()
    if not show_all:
        items = [b for b in items if not _is_past(b)]
    if as_json:
        print_json(items)
        return
    if not items:
        console.print("No bookings." if show_all else "No upcoming bookings (try --all).")
        return
    console.print(bookings_table(items))


@bookings.command("show")
@click.argument("booking_id")
@json_option
@click.pass_obj
def show_booking(app, booking_id, as_json) -> None:
    """Show one booking in detail."""
    with app.require_auth_client() as client:
        booking = client.get_booking(booking_id)
    if as_json:
        print_json(booking)
        return
    console.print(
        kv_panel(
            f"Booking {booking.id}",
            {
                "car": booking.bookee_id or "—",
                "from": local_time(booking.start),
                "until": local_time(booking.end),
                "state": booking.state or "—",
            },
        )
    )


@bookings.command("create")
@click.argument("car_id")
@window_options
@click.option("--yes", "-y", is_flag=True, help="Skip the confirmation prompt.")
@json_option
@click.pass_obj
def create_booking(app, car_id, start_text, duration_text, until_text, yes, as_json) -> None:
    """Book CAR_ID for a time window. Asks for confirmation — this costs money."""
    start, end = resolve_window(
        start_text, duration_text, until_text, default_minutes=app.settings.window_min
    )
    with app.require_auth_client() as client:
        car = client.get_car(car_id)
        try:
            price = client.price(car_id, start, end)
            price_line = (
                f"{price.total:.2f} {price.currency}" if price.total is not None else "unknown"
            )
        except TeilautoError:
            price_line = "unknown"
        console.print(
            kv_panel(
                "Confirm booking",
                {
                    "car": f"{car.name} ({car.plate or car.id})",
                    "from": start.strftime("%Y-%m-%d %H:%M"),
                    "until": end.strftime("%Y-%m-%d %H:%M"),
                    "price": price_line,
                },
            )
        )
        if not yes:
            click.confirm("Book this car?", abort=True)
        booking = client.create_booking(car_id, start, end)
    if as_json:
        print_json(booking)
        return
    console.print(f"[green]✓ Booked.[/green] Booking id: {booking.id}")


@bookings.command("cancel")
@click.argument("booking_id")
@click.option("--yes", "-y", is_flag=True, help="Skip the confirmation prompt.")
@click.pass_obj
def cancel_booking(app, booking_id, yes) -> None:
    """Cancel a booking."""
    if not yes:
        click.confirm(f"Cancel booking {booking_id}?", abort=True)
    with app.require_auth_client() as client:
        client.cancel_booking(booking_id)
    console.print(f"[green]✓ Booking {booking_id} cancelled.[/green]")
```

Register in `src/teilauto/cli/__init__.py`:
```python
from teilauto.cli.bookings import bookings  # noqa: E402

cli.add_command(bookings)
```

Remove the `@pytest.mark.xfail(...)` line from `test_main_renders_teilauto_error` in `tests/test_cli_root.py`.

- [ ] **Step 4: Run** — `uv run pytest tests/test_cli_bookings.py tests/test_cli_root.py -q` → all pass, no xfail.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: bookings list/show/create/cancel with confirmation prompts"`

---

### Task 16: `teilauto config` group + `teilauto notify test`

**Files:**
- Create: `src/teilauto/cli/config_cmd.py`, `src/teilauto/cli/notify_cmd.py`
- Modify: `src/teilauto/cli/__init__.py` (register)
- Test: `tests/test_cli_config.py`

**Interfaces:**
- Consumes: config module (Task 6), `tokenstore.save_secret`/`TG_BOT_TOKEN_KEY` (7), `build_notifiers`/`send_all` (10).
- Produces: `config` group: `list [--json]` (effective merged config), `get KEY`, `set KEY VALUE`, `unset KEY`, `path`. Unknown keys → `ConfigError` listing valid keys. Secret key mapping: `notify.telegram.bot_token` is accepted by `set` but stored via `save_secret(TG_BOT_TOKEN_KEY, ...)`, never written to the TOML. `notify` group: `test` sends "Test notification from teilauto ✓" through all configured channels and reports per-channel success/failure; no channels configured → `ConfigError` with hint.

- [ ] **Step 1: Write failing tests** — `tests/test_cli_config.py`:

```python
from __future__ import annotations

import json

import httpx

from teilauto.cli import cli
from teilauto.core import tokenstore


def test_config_set_get_roundtrip(runner, isolated_config):
    assert runner.invoke(cli, ["config", "set", "location.radius_m", "900"]).exit_code == 0
    result = runner.invoke(cli, ["config", "get", "location.radius_m"])
    assert result.exit_code == 0
    assert result.output.strip() == "900"


def test_config_list_json_shows_effective(runner, isolated_config):
    runner.invoke(cli, ["config", "set", "location.radius_m", "900"])
    result = runner.invoke(cli, ["config", "list", "--json"])
    data = json.loads(result.output)
    assert data["location.radius_m"] == 900
    assert data["location.lat"] == 51.33853  # default still present


def test_config_unknown_key_fails(runner, isolated_config):
    result = runner.invoke(cli, ["config", "set", "nope.nope", "1"])
    assert result.exit_code != 0


def test_config_unset(runner, isolated_config):
    runner.invoke(cli, ["config", "set", "location.radius_m", "900"])
    assert runner.invoke(cli, ["config", "unset", "location.radius_m"]).exit_code == 0
    result = runner.invoke(cli, ["config", "get", "location.radius_m"])
    assert result.output.strip() == "500"  # back to default


def test_config_path(runner, isolated_config):
    result = runner.invoke(cli, ["config", "path"])
    assert result.exit_code == 0
    assert str(isolated_config) in result.output


def test_bot_token_goes_to_secret_store_not_toml(runner, isolated_config):
    result = runner.invoke(cli, ["config", "set", "notify.telegram.bot_token", "TOK123"])
    assert result.exit_code == 0, result.output
    config_toml = isolated_config / "config.toml"
    assert "TOK123" not in (config_toml.read_text() if config_toml.exists() else "")
    assert tokenstore.load_secret(tokenstore.TG_BOT_TOKEN_KEY) == "TOK123"


def test_notify_test_no_channels(runner, isolated_config):
    result = runner.invoke(cli, ["notify", "test"])
    assert result.exit_code != 0


def test_notify_test_sends(runner, isolated_config, respx_mock, monkeypatch):
    monkeypatch.setenv("TEILAUTO_NOTIFY_CHANNELS", "ntfy")
    monkeypatch.setenv("TEILAUTO_NOTIFY_NTFY_TOPIC", "t")
    route = respx_mock.post("https://ntfy.sh/t").mock(return_value=httpx.Response(200))
    result = runner.invoke(cli, ["notify", "test"])
    assert result.exit_code == 0, result.output
    assert route.called
    assert "ntfy" in result.output
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_cli_config.py -q` → fails.

- [ ] **Step 3: Implement**

`src/teilauto/cli/config_cmd.py`:
```python
from __future__ import annotations

import rich_click as click

from teilauto.api.errors import ConfigError
from teilauto.cli.options import json_option
from teilauto.core import config as cfg
from teilauto.core import tokenstore
from teilauto.output.json_out import print_json
from teilauto.output.render import console

SECRET_KEYS = {"notify.telegram.bot_token": tokenstore.TG_BOT_TOKEN_KEY}


def _check_key(key: str) -> None:
    if key not in cfg.KNOWN_KEYS and key not in SECRET_KEYS:
        valid = ", ".join((*cfg.KNOWN_KEYS, *SECRET_KEYS))
        raise ConfigError(f"Unknown config key: {key!r}.", hint=f"Valid keys: {valid}")


@click.group("config")
def config_group() -> None:
    """View and edit configuration (config file, overridable via TEILAUTO_* env vars)."""


@config_group.command("list")
@json_option
def list_config(as_json: bool) -> None:
    """Show the effective configuration (defaults + file + environment)."""
    flat = cfg.effective_config()
    if as_json:
        print_json(flat)
        return
    from rich.table import Table

    table = Table(title="Configuration", header_style="bold")
    table.add_column("Key")
    table.add_column("Value")
    for key, value in flat.items():
        table.add_row(key, repr(value))
    console.print(table)


@config_group.command("get")
@click.argument("key")
def get_config(key: str) -> None:
    """Print one effective config value."""
    _check_key(key)
    click.echo(cfg.effective_config()[key])


@config_group.command("set")
@click.argument("key")
@click.argument("value")
def set_config(key: str, value: str) -> None:
    """Set a config value, e.g. `teilauto config set location.radius_m 800`.

    Secrets (notify.telegram.bot_token) are stored in the OS keyring, not the file.
    """
    _check_key(key)
    if key in SECRET_KEYS:
        tokenstore.save_secret(SECRET_KEYS[key], value)
        console.print(f"[green]✓[/green] {key} stored securely.")
        return
    data = cfg.read_raw()
    cfg.set_value(data, key, cfg.coerce_value(value))
    cfg.write_raw(data)
    console.print(f"[green]✓[/green] {key} = {cfg.coerce_value(value)!r}")


@config_group.command("unset")
@click.argument("key")
def unset_config(key: str) -> None:
    """Remove a value from the config file (reverts to the default)."""
    _check_key(key)
    if key in SECRET_KEYS:
        tokenstore.delete_secret(SECRET_KEYS[key])
        console.print(f"[green]✓[/green] {key} removed.")
        return
    data = cfg.read_raw()
    cfg.unset_value(data, key)
    cfg.write_raw(data)
    console.print(f"[green]✓[/green] {key} removed.")


@config_group.command("path")
def config_path() -> None:
    """Print the config file location."""
    click.echo(cfg.config_file())
```

`src/teilauto/cli/notify_cmd.py`:
```python
from __future__ import annotations

import rich_click as click

from teilauto.api.errors import ConfigError
from teilauto.output.render import console
from teilauto.services.notify import build_notifiers, send_all


@click.group()
def notify() -> None:
    """Notification channels (used by watch and autobook)."""


@notify.command("test")
@click.pass_obj
def test_notify(app) -> None:
    """Send a test message through every configured channel."""
    notifiers = build_notifiers(app.settings)
    if not notifiers:
        raise ConfigError(
            "No notification channels configured.",
            hint="Run `teilauto config set notify.channels telegram` (or ntfy) first.",
        )
    errors = send_all(notifiers, "teilauto test", "Test notification from teilauto ✓")
    failed = {e.split(":", 1)[0] for e in errors}
    for notifier in notifiers:
        if notifier.name in failed:
            console.print(f"[red]✗ {notifier.name} failed[/red]")
        else:
            console.print(f"[green]✓ {notifier.name} ok[/green]")
    if errors:
        raise ConfigError("; ".join(errors))
```

Register in `src/teilauto/cli/__init__.py`:
```python
from teilauto.cli.config_cmd import config_group  # noqa: E402
from teilauto.cli.notify_cmd import notify  # noqa: E402

cli.add_command(config_group)
cli.add_command(notify)
```

- [ ] **Step 4: Run** — `uv run pytest tests/test_cli_config.py -q` → all pass.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: config get/set/list/unset/path and notify test commands"`

---

### Task 17: `teilauto watch`

**Files:**
- Create: `src/teilauto/cli/watch.py`
- Modify: `src/teilauto/cli/__init__.py` (register)
- Test: `tests/test_cli_watch.py`

**Interfaces:**
- Consumes: `watch` engine (11), `find_cars`/`describe` (9), `build_notifiers`/`send_all` (10), options (12).
- Produces: `watch_cmd` (registered as `watch`): options location, `--min-fuel`, `--window MINUTES` (availability window, default config `window_min`), `--interval SECONDS` (default config `interval_sec`). Sends a startup notification, prints a status line per tick, notifies (`"CityFlitzer available"` title) per new car. Works without configured channels (prints warning once, terminal-only). Module-level `import time` so tests can monkeypatch `teilauto.cli.watch.time.sleep`.

- [ ] **Step 1: Write failing tests** — `tests/test_cli_watch.py`:

```python
from __future__ import annotations

import httpx
import pytest

from teilauto.api.client import BASE_URL
from teilauto.cli import cli


class StopLoop(Exception):
    """Raised by the fake sleeper to end the infinite watch loop in tests.

    (Not KeyboardInterrupt: CliRunner only catches Exception subclasses.)
    """


@pytest.fixture
def one_cycle(monkeypatch):
    """Let the watch loop run exactly one poll, then stop it."""

    def fake_sleep(seconds):
        raise StopLoop

    monkeypatch.setattr("teilauto.cli.watch.time.sleep", fake_sleep)


def _mock_search(respx_mock, poi_json, proposals_json):
    respx_mock.get(f"{BASE_URL}/pointsofinterest").mock(
        return_value=httpx.Response(200, json=poi_json)
    )
    respx_mock.get(f"{BASE_URL}/bookingproposals").mock(
        return_value=httpx.Response(200, json=proposals_json)
    )


def test_watch_prints_status_and_new_car(runner, isolated_config, respx_mock,
                                         poi_json, proposals_json, one_cycle):
    _mock_search(respx_mock, poi_json, proposals_json)
    result = runner.invoke(cli, ["watch"])
    assert isinstance(result.exception, StopLoop)
    # click >= 8.2: result.output is stdout only; warnings go to result.stderr
    assert "bookable" in result.output
    assert "VW Polo" in result.output
    assert "no notification channels" in result.stderr.lower()


def test_watch_notifies_via_ntfy(runner, isolated_config, respx_mock, monkeypatch,
                                 poi_json, proposals_json, one_cycle):
    monkeypatch.setenv("TEILAUTO_NOTIFY_CHANNELS", "ntfy")
    monkeypatch.setenv("TEILAUTO_NOTIFY_NTFY_TOPIC", "t")
    _mock_search(respx_mock, poi_json, proposals_json)
    ntfy_route = respx_mock.post("https://ntfy.sh/t").mock(return_value=httpx.Response(200))
    result = runner.invoke(cli, ["watch"])
    assert isinstance(result.exception, StopLoop)
    # startup message + one new car
    assert ntfy_route.call_count == 2
```

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_cli_watch.py -q` → fails.

- [ ] **Step 3: Implement** — `src/teilauto/cli/watch.py`:

```python
from __future__ import annotations

import time
from datetime import datetime, timedelta

import rich_click as click

from teilauto.cli.options import location_options, resolve_location
from teilauto.output.render import console, err_console
from teilauto.services.availability import describe, find_cars
from teilauto.services.notify import build_notifiers, send_all
from teilauto.services.watcher import watch


@click.command("watch")
@location_options
@click.option("--min-fuel", type=float, default=None, metavar="PERCENT",
              help="Ignore cars below this fuel level (default: config).")
@click.option("--window", "window_min", type=int, default=None, metavar="MINUTES",
              help="Booking window tested for availability (default: config).")
@click.option("--interval", type=int, default=None, metavar="SECONDS",
              help="Seconds between polls (default: config).")
@click.pass_obj
def watch_cmd(app, lat, lng, radius_m, min_fuel, window_min, interval) -> None:
    """Watch for CityFlitzers becoming available and send a notification.

    Notify-only: nothing is ever booked. Use `teilauto autobook` to book
    automatically. Runs until interrupted with Ctrl-C.
    """
    settings = app.settings
    lat, lng, radius_m = resolve_location(settings, lat, lng, radius_m)
    min_fuel = settings.min_fuel if min_fuel is None else min_fuel
    window_min = settings.window_min if window_min is None else window_min
    interval = settings.interval_sec if interval is None else interval

    notifiers = build_notifiers(settings)
    if not notifiers and not app.quiet:
        err_console.print(
            "[yellow]No notification channels configured — printing to terminal only.[/yellow]"
        )

    with app.client() as client:

        def fetch():
            start = datetime.now().astimezone()
            end = start + timedelta(minutes=window_min)
            return find_cars(
                client, lat=lat, lng=lng, radius_m=radius_m,
                start=start, end=end, min_fuel=min_fuel,
            )

        if not app.quiet:
            console.print(
                f"Watching CityFlitzers within {radius_m} m of ({lat}, {lng}); "
                f"polling every {interval}s. Ctrl-C to stop."
            )
        send_all(notifiers, "teilauto watch",
                 f"🚗 Watcher started (radius {radius_m} m, every {interval}s)")

        for tick in watch(fetch, interval=interval, sleeper=time.sleep):
            stamp = datetime.now().astimezone().strftime("%H:%M:%S")
            if tick.error:
                err_console.print(f"[dim]{stamp}[/dim] [red]poll failed:[/red] {tick.error}")
                continue
            extra = f", [green]{len(tick.new)} new[/green]" if tick.new else ""
            console.print(
                f"[dim]{stamp}[/dim] {tick.nearby} nearby, {tick.available} bookable{extra}"
            )
            for ca in tick.new:
                line = describe(ca)
                console.print(f"  [green]★[/green] {line}")
                for error in send_all(notifiers, "CityFlitzer available", f"🚗 {line}"):
                    err_console.print(f"[red]notify failed:[/red] {error}")
```

Register in `src/teilauto/cli/__init__.py`:
```python
from teilauto.cli.watch import watch_cmd  # noqa: E402

cli.add_command(watch_cmd)
```

- [ ] **Step 4: Run** — `uv run pytest tests/test_cli_watch.py -q` → all pass.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: notify-only watch command"`

---

### Task 18: `teilauto autobook`

**Files:**
- Create: `src/teilauto/cli/autobook.py`
- Modify: `src/teilauto/cli/__init__.py` (register)
- Test: `tests/test_cli_autobook.py`

**Interfaces:**
- Consumes: everything from Tasks 5, 9, 10, 11, 12; `NoMatchError`, `AuthRequiredError`.
- Produces: `autobook_cmd` (registered as `autobook`): options location, `--for DURATION` / `--until TIME` (booking window; exactly one required), `--min-fuel`, `--max-price EUR`, `--deadline TIME`, `--interval SECONDS`, `--dry-run`, `--yes/-y`, `--json`. Behavior: requires login unless `--dry-run`; criteria panel + confirm unless `--yes`; startup notification; polls; per new candidate (closest first): price check (skip if over `--max-price`), then books (or dry-runs) and exits 0; booking failure → keep polling; `--deadline` reached → notification + `NoMatchError` (exit 2). Module-level `import time` for test monkeypatching.

- [ ] **Step 1: Write failing tests** — `tests/test_cli_autobook.py`:

```python
from __future__ import annotations

import json

import httpx

from teilauto.api.client import BASE_URL
from teilauto.cli import cli


def _mock_search(respx_mock, poi_json, proposals_json):
    respx_mock.get(f"{BASE_URL}/pointsofinterest").mock(
        return_value=httpx.Response(200, json=poi_json)
    )
    respx_mock.get(f"{BASE_URL}/bookingproposals").mock(
        return_value=httpx.Response(200, json=proposals_json)
    )


def test_autobook_requires_duration(runner, logged_in):
    result = runner.invoke(cli, ["autobook", "--yes"])
    assert result.exit_code == 2
    # click >= 8.2: usage errors are printed to stderr
    assert "--for" in result.stderr


def test_autobook_requires_login(runner, isolated_config):
    result = runner.invoke(cli, ["autobook", "--for", "1h", "--yes"])
    assert result.exception is not None


def test_autobook_books_first_match(runner, logged_in, respx_mock,
                                    poi_json, proposals_json, prices_json, bookings_json):
    _mock_search(respx_mock, poi_json, proposals_json)
    respx_mock.get(f"{BASE_URL}/prices").mock(return_value=httpx.Response(200, json=prices_json))
    post = respx_mock.post(f"{BASE_URL}/bookings").mock(
        return_value=httpx.Response(200, json=bookings_json[0])
    )
    result = runner.invoke(cli, ["autobook", "--for", "1h", "--yes", "--json"])
    assert result.exit_code == 0, result.output
    assert post.called
    data = json.loads(result.output)
    assert data["status"] == "booked"
    assert data["booking"]["id"] == "b-1"
    assert data["car"]["id"] == "111"


def test_autobook_dry_run_does_not_post(runner, logged_in, respx_mock,
                                        poi_json, proposals_json, prices_json):
    _mock_search(respx_mock, poi_json, proposals_json)
    respx_mock.get(f"{BASE_URL}/prices").mock(return_value=httpx.Response(200, json=prices_json))
    post = respx_mock.post(f"{BASE_URL}/bookings")
    result = runner.invoke(cli, ["autobook", "--for", "1h", "--yes", "--dry-run", "--json"])
    assert result.exit_code == 0, result.output
    assert not post.called
    assert json.loads(result.output)["status"] == "dry_run"


def test_autobook_respects_max_price(runner, logged_in, respx_mock, monkeypatch,
                                     poi_json, proposals_json, prices_json):
    # stop after the first cycle: candidate too expensive, then deadline passes
    monkeypatch.setattr("teilauto.cli.autobook.time.sleep", lambda s: None)
    _mock_search(respx_mock, poi_json, proposals_json)
    respx_mock.get(f"{BASE_URL}/prices").mock(return_value=httpx.Response(200, json=prices_json))
    post = respx_mock.post(f"{BASE_URL}/bookings")
    result = runner.invoke(
        cli,
        ["autobook", "--for", "1h", "--yes", "--max-price", "2.00", "--deadline", "now"],
    )
    assert not post.called
    assert result.exception is not None  # NoMatchError via runner


def test_autobook_keeps_polling_when_booking_races(runner, logged_in, respx_mock, monkeypatch,
                                                   poi_json, proposals_json, prices_json,
                                                   bookings_json):
    monkeypatch.setattr("teilauto.cli.autobook.time.sleep", lambda s: None)
    _mock_search(respx_mock, poi_json, proposals_json)
    respx_mock.get(f"{BASE_URL}/prices").mock(return_value=httpx.Response(200, json=prices_json))
    post = respx_mock.post(f"{BASE_URL}/bookings")
    post.side_effect = [
        httpx.Response(409, json={"message": "already booked"}),
        httpx.Response(200, json=bookings_json[0]),
    ]
    result = runner.invoke(cli, ["autobook", "--for", "1h", "--yes"])
    assert result.exit_code == 0, result.output
    assert post.call_count == 2
    assert "Booked" in result.output
```

Note on the race test: the first candidate (car 111) 409s; the only other new
candidate in the same tick is unavailable, so the loop sleeps (no-op) and the
next tick re-lists car 111 as new because a failed booking removes it from the
seen-set — implement by tracking `attempted_and_failed` ids and retrying them.
Simplest correct approach shown in the implementation below: after a failed
booking attempt, continue with the next candidate; when a tick produces no
bookable success, the seen-set diff naturally re-yields nothing — so the
implementation must re-try failed candidates by keeping them OUT of the
watcher's seen-set. Achieve this by feeding the watcher a fetch that excludes
nothing, but iterating over `tick.new` PLUS previously failed candidates that
are still available. Track `failed_ids: set[str]` and iterate
`candidates = list(tick.new) + [ca for ca in current_available if ca.car.id in failed_ids]`.
The implementation below includes `current_available`; keep it exactly.

- [ ] **Step 2: Run to verify failure** — `uv run pytest tests/test_cli_autobook.py -q` → fails.

- [ ] **Step 3: Implement** — `src/teilauto/cli/autobook.py`:

```python
from __future__ import annotations

import time
from datetime import datetime, timedelta

import rich_click as click

from teilauto.api.errors import AuthRequiredError, NoMatchError, TeilautoError
from teilauto.cli.options import json_option, location_options, resolve_location
from teilauto.core.timeparse import parse_duration, parse_time
from teilauto.output.json_out import print_json
from teilauto.output.render import console, err_console, kv_panel
from teilauto.services.availability import CarAvailability, describe, find_cars
from teilauto.services.notify import build_notifiers, send_all
from teilauto.services.watcher import watch


@click.command("autobook")
@location_options
@click.option("--for", "duration_text", default=None, metavar="DURATION",
              help="Booking duration once a car is found, e.g. '45m', '2h'.")
@click.option("--until", "until_text", default=None, metavar="TIME",
              help="Fixed booking end time instead of --for.")
@click.option("--min-fuel", type=float, default=None, metavar="PERCENT",
              help="Ignore cars below this fuel level (default: config).")
@click.option("--max-price", type=float, default=None, metavar="EUR",
              help="Skip cars whose booking would cost more than this.")
@click.option("--deadline", "deadline_text", default=None, metavar="TIME",
              help="Give up (exit 2) if no car was booked by this time.")
@click.option("--interval", type=int, default=None, metavar="SECONDS",
              help="Seconds between polls (default: config).")
@click.option("--dry-run", is_flag=True,
              help="Do everything except the actual booking (no login needed).")
@click.option("--yes", "-y", is_flag=True, help="Skip the confirmation prompt.")
@json_option
@click.pass_obj
def autobook_cmd(app, lat, lng, radius_m, duration_text, until_text, min_fuel,
                 max_price, deadline_text, interval, dry_run, yes, as_json) -> None:
    """Book the closest matching CityFlitzer the moment one becomes available.

    This spends real money on your real account. Safety rails: a criteria
    confirmation before starting, --dry-run, --max-price, and an explicit
    booking duration. Exits as soon as a car is booked.
    """
    settings = app.settings
    lat, lng, radius_m = resolve_location(settings, lat, lng, radius_m)
    if duration_text and until_text:
        raise click.UsageError("--for and --until are mutually exclusive.")
    if not duration_text and not until_text:
        raise click.UsageError("Give the booking length via --for (e.g. --for 1h) or --until.")
    try:
        duration = parse_duration(duration_text) if duration_text else None
        fixed_end = parse_time(until_text) if until_text else None
        deadline = parse_time(deadline_text) if deadline_text else None
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc
    min_fuel = settings.min_fuel if min_fuel is None else min_fuel
    interval = settings.interval_sec if interval is None else interval

    if app.token is None and not dry_run:
        raise AuthRequiredError()

    notifiers = build_notifiers(settings)
    if not notifiers and not app.quiet:
        err_console.print(
            "[yellow]No notification channels configured — printing to terminal only.[/yellow]"
        )

    if not yes:
        console.print(
            kv_panel(
                "Autobook criteria",
                {
                    "location": f"{lat}, {lng} (±{radius_m} m)",
                    "duration": duration_text or f"until {until_text}",
                    "min fuel": f"{min_fuel:.0f}%",
                    "max price": f"{max_price:.2f} EUR" if max_price is not None else "—",
                    "deadline": deadline_text or "—",
                    "mode": "DRY RUN" if dry_run else "books immediately",
                },
            )
        )
        click.confirm("Start autobook with these criteria?", abort=True)

    def booking_window() -> tuple[datetime, datetime]:
        start = datetime.now().astimezone()
        end = fixed_end if fixed_end is not None else start + duration
        return start, end

    def finish(status: str, ca: CarAvailability | None, booking, price) -> None:
        if as_json:
            print_json({"status": status, "car": ca.car if ca else None,
                        "booking": booking, "price": price})

    with app.client() as client:

        def fetch():
            start, end = booking_window()
            if end <= start:
                raise NoMatchError("--until time has already passed.")
            return find_cars(
                client, lat=lat, lng=lng, radius_m=radius_m,
                start=start, end=end, min_fuel=min_fuel,
            )

        send_all(notifiers, "teilauto autobook",
                 f"🤖 Autobook started (radius {radius_m} m, every {interval}s)")
        if not app.quiet:
            console.print(f"Hunting for a car... polling every {interval}s. Ctrl-C to stop.")

        failed_ids: set[str] = set()
        for tick in watch(fetch, interval=interval, sleeper=time.sleep):
            stamp = datetime.now().astimezone().strftime("%H:%M:%S")
            if tick.error:
                err_console.print(f"[dim]{stamp}[/dim] [red]poll failed:[/red] {tick.error}")
            else:
                if not app.quiet:
                    console.print(
                        f"[dim]{stamp}[/dim] {tick.nearby} nearby, {tick.available} bookable"
                    )
                retries = [ca for ca in tick.retryable if ca.car.id in failed_ids]
                for ca in list(tick.new) + retries:
                    start, end = booking_window()
                    price = None
                    try:
                        price = client.price(ca.car.id, start, end)
                    except TeilautoError:
                        pass
                    if (
                        max_price is not None
                        and price is not None
                        and price.total is not None
                        and price.total > max_price
                    ):
                        console.print(
                            f"  [yellow]skip[/yellow] {describe(ca)} "
                            f"({price.total:.2f} {price.currency} > max)"
                        )
                        continue
                    price_line = (
                        f" for {price.total:.2f} {price.currency}"
                        if price and price.total is not None
                        else ""
                    )
                    if dry_run:
                        message = f"Would have booked: {describe(ca)}{price_line}"
                        console.print(f"[green]✓ DRY RUN[/green] {message}")
                        send_all(notifiers, "teilauto dry-run", f"🤖 {message}")
                        finish("dry_run", ca, None, price)
                        return
                    try:
                        booking = client.create_booking(ca.car.id, start, end)
                    except TeilautoError as exc:
                        failed_ids.add(ca.car.id)
                        err_console.print(
                            f"  [yellow]booking failed (car taken?):[/yellow] {exc} — continuing"
                        )
                        continue
                    message = (
                        f"Booked {describe(ca)}{price_line} — booking id {booking.id}"
                    )
                    console.print(f"[green]✓ Booked![/green] {message}")
                    send_all(notifiers, "Car booked", f"🚗 {message}")
                    finish("booked", ca, booking, price)
                    return
            if deadline is not None and datetime.now().astimezone() >= deadline:
                send_all(notifiers, "Autobook gave up",
                         "⏰ No matching car became available before the deadline.")
                finish("no_match", None, None, None)
                raise NoMatchError("Deadline reached — no matching car was booked.")
```

`tick.retryable` does not exist on `WatchTick` — add it in
`src/teilauto/services/watcher.py` as part of this task (it is the full list of
currently-available cars, letting consumers re-try candidates they failed on):

```python
@dataclass(frozen=True)
class WatchTick:
    nearby: int
    available: int
    new: tuple[CarAvailability, ...]
    retryable: tuple[CarAvailability, ...] = ()
    error: str | None = None
```

and in `watch()`'s success branch:

```python
            yield WatchTick(
                nearby=len(cars),
                available=len(available),
                new=new,
                retryable=tuple(available),
            )
```

(Existing watcher tests construct `WatchTick` only via `watch()` and don't
assert on `retryable`, so they stay green.)

Register in `src/teilauto/cli/__init__.py`:
```python
from teilauto.cli.autobook import autobook_cmd  # noqa: E402

cli.add_command(autobook_cmd)
```

- [ ] **Step 4: Run** — `uv run pytest tests/test_cli_autobook.py tests/test_watcher.py -q` → all pass.
- [ ] **Step 5: Run the whole suite** — `uv run pytest -q` → all pass.
- [ ] **Step 6: Commit** — `git add -A && git commit -m "feat: autobook command - poll, price-check, book, notify"`

---

### Task 19: Lint pass, CI, and packaging checks

**Files:**
- Create: `.github/workflows/ci.yml`, `.github/workflows/release.yml`
- Modify: any files ruff flags

- [ ] **Step 1: Ruff** — `uv run ruff check --fix . && uv run ruff format .` then `uv run pytest -q` (must stay green). Fix any remaining warnings by hand — no `# noqa` unless genuinely needed (the deferred imports in `cli/__init__.py` keep their `# noqa: E402`).

- [ ] **Step 2: CI workflow** — `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python: ["3.10", "3.12", "3.14"]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v7
        with:
          python-version: ${{ matrix.python }}
      - run: uv sync --dev
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run pytest -q

  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v7
      - run: uv build
      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/
```

- [ ] **Step 3: Release workflow** — `.github/workflows/release.yml` (inert until a PyPI trusted publisher is configured):

```yaml
name: Release

on:
  push:
    tags: ["v*"]

jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v7
      - run: uv build
      - uses: pypa/gh-action-pypi-publish@release/v1
```

- [ ] **Step 4: Package sanity** — `uv build` → wheel + sdist in `dist/`. Then `uv tool install --from dist/*.whl teilauto-cli --force && teilauto --version && teilauto -h` (uninstall after with `uv tool uninstall teilauto-cli` if undesired).

- [ ] **Step 5: Commit** — `git add -A && git commit -m "ci: lint+test matrix and PyPI release workflow"`

---

### Task 20: README, CHANGELOG, docs polish

**Files:**
- Create: `README.md`, `CHANGELOG.md`

- [ ] **Step 1: Write README.md** following the funnel from the spec. Structure (write real content for each; command output examples may be composed from the fixtures' data):

```markdown
# teilauto-cli

> Book a CityFlitzer before anyone else does — from your terminal.

Badges: CI (github actions workflow badge), PyPI version, Python versions, License MIT.

One-paragraph pitch: unofficial CLI for teilauto/CityFlitzer carsharing
(Leipzig & Mitteldeutschland): search cars, check prices, manage bookings —
plus `autobook`, which books a matching car the second it becomes available
and pings you on Telegram or ntfy.

## Install
    uv tool install teilauto-cli     # or: pipx install teilauto-cli

## 30 seconds to your first car
    teilauto auth login                      # once; token lasts ~90 days
    teilauto config set location.lat 51.3385 # your home coordinates
    teilauto config set location.lng 12.3916
    teilauto cars list                       # what's nearby?
    teilauto bookings create <car-id> --for 1h

## Autobook (the good part)
Explanation + example:
    teilauto autobook --for 45m --radius 800 --max-price 10 --deadline 18:00
What it does step by step, the safety rails (--dry-run, confirmation,
--max-price), and that it exits after booking. Note on race conditions.

## Notifications
Telegram setup (BotFather steps, config set notify.telegram.bot_token/chat_id)
and ntfy setup (config set notify.ntfy.topic; point phone app at the topic).
`teilauto notify test` to verify.

## Commands
Table of every command with a one-liner. Mention -h/--help everywhere.

## Configuration
The config.toml keys table (all KNOWN_KEYS with defaults + meaning), the
TEILAUTO_* env override rule, `teilauto config path`. Token storage:
keyring → chmod-600 secrets.json fallback → TEILAUTO_TOKEN env.

## JSON output & scripting
--json on every data command; two jq examples, e.g.
    teilauto cars list --available --json | jq -r '.[].car.name'
    teilauto auth status --json | jq .expiry
Exit codes table (0/1/2/3/4).

## How it works / API notes
Short section: reverse-engineered Cantamen casirest/v3, public x-api-key is
an app identifier not a secret, link to the sibling research README.

## Responsible use
Unofficial, personal use, poll gently (120 s default), autobook spends real
money, endpoints may change without notice.

## Future extensions
systemd/launchd service helpers, geocoding, quiet hours.

## Development
uv sync, uv run pytest, uv run ruff check ., project layout summary,
conventional commits, MIT.
```

- [ ] **Step 2: Write CHANGELOG.md** (Keep a Changelog format, `## [0.1.0] - 2026-07-12` with an Added list naming every command group).

- [ ] **Step 3: Check docs against reality** — for every command mentioned in the README, run `uv run teilauto <command> -h` and confirm flags/names match what's documented.

- [ ] **Step 4: Nori docs** — per the user's global CLAUDE.md, run the nori documentation tooling (updating-noridocs skill / nori-initial-documenter agent, whichever applies to a fresh repo) so codebase docs exist and are current.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "docs: README funnel, changelog, noridocs"`

---

### Task 21: Final verification & live smoke test

- [ ] **Step 1: Full check** — `uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv build`. All green.

- [ ] **Step 2: Fresh-install simulation** — in a temp dir: `uv tool install --from <repo>/dist/*.whl teilauto-cli --force`, then `teilauto --version`, `teilauto -h`, `teilauto config path`, `teilauto config set location.radius_m 800`, `teilauto config list`. Confirms a new machine gets a working install with config bootstrapping.

- [ ] **Step 3: Live read-only smoke (real API, no auth, gentle)** — run once: `uv run teilauto cars list --lat 51.3397 --lng 12.3731 --radius 1500` (Leipzig center) and `uv run teilauto cars list --json --lat 51.3397 --lng 12.3731 --radius 1500`. Verify real cars parse. If the live response shape differs from fixtures, fix `models.py` parsing and the fixtures to match reality, re-run the suite. Do NOT live-test login/booking/cancel — member actions are verified against fixtures only; note in README that booking payload shape is best-effort reverse engineering.

- [ ] **Step 4: Verify checklist against spec** — every spec section has a shipped counterpart (commands, JSON, exit codes, config precedence, notifications, packaging, README).

- [ ] **Step 5: Commit anything outstanding** — `git add -A && git commit -m "chore: final verification fixes"` (only if changes were needed).
