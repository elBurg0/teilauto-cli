# Noridoc: api

Path: @/src/teilauto/api

### Overview

The HTTP boundary of the application: a thin, typed client for the reverse-engineered Cantamen `casirest/v3` REST API (base `https://de1.cantamen.de/casirest/v3`, provider id `118` = teilauto Mitteldeutschland), plus the frozen dataclass models that API responses are parsed into and the `TeilautoError` exception hierarchy that maps API failures to CLI exit codes.

### How it fits into the larger codebase

This is the only layer allowed to touch `httpx` for the Cantamen API (the notifiers in @/src/teilauto/services/notify make their own unrelated HTTP calls). `CantamenClient` instances are constructed exclusively by `AppContext.client()` / `AppContext.require_auth_client()` in @/src/teilauto/cli/__init__.py, which inject the stored token from @/src/teilauto/core/tokenstore.py. The service layer (@/src/teilauto/services/availability.py) calls client methods and consumes the models; the error hierarchy defined here is caught once, in `main()` in @/src/teilauto/cli/__init__.py, which renders `message` + `hint` and exits with the error's `exit_code`. Note the hierarchy in `errors.py` is used codebase-wide — even `ConfigError` (raised by @/src/teilauto/core/config.py and notifier construction) lives here so there is a single base class for the root handler.

### Core Implementation

`client.py` — `CantamenClient` wraps an `httpx.Client` with the public frontend `x-api-key` (an app identifier baked into the buchen.teilauto.net JS, deliberately committed to source; it only unlocks read-only endpoints) and, when a `token_id` is given, a `authorization: Basic base64("<tokenId>:")` header for member actions. All calls funnel through `_request()`, which retries transport errors and 5xx responses up to `retries + 1` attempts (default 3 total) and maps status codes: 401 → `AuthRequiredError` (exit 3), 404 → `NotFoundError` (exit 4), 429 → `RateLimitedError`, other 4xx → `ApiError` (exit 1). All datetimes are serialized to the API via `iso_utc()` as UTC `%Y-%m-%dT%H:%M:%S.000Z`. The client is a context manager; CLI commands use `with app.client() as client:`.

`models.py` — frozen dataclasses (`Car`, `Proposal`, `Price`, `Booking`, `Unavailability`, `TokenInfo`) each with a `from_api`/`from_bookee` classmethod that defensively parses raw dicts (`.get()` everywhere, ids coerced to `str`). `cars_from_poi()` flattens the nested `/pointsofinterest` response (points → places → bookees) and dedupes by car id. `Price.from_api` sums `priceItems[].priceIncl.amount` (cents), currency from `priceIncl.code` — this is the shape the live API actually sends; the legacy `gross.amount`/`gross.currency` shape (used by older fixtures/docs) is tried as a fallback at both the per-item and top-level scope. `total` is euros (`cents / 100`) or `None` when no amount was found in either shape. `unavailabilities_from_api()` flattens the live `/unavailabilities` shape (`[{"unavailabilityTimeRanges": [...]}]`) and still accepts flat items. `Booking.from_api` reads the expanded `bookee` (`list_bookings`/`get_booking` send `expand=bookee`): the car id comes from `bookee.actualBookeeId`, because `bookee.id` is a per-booking virtual id (`B118_…`); `car_label` renders `name (plate) [id]`; state falls back to `CANCELLED` when `cancelled` is true, then to `billingState` (`DELIVERED`/`NOT_DELIVERED`). `Booking` and `Price` keep the raw API dict in a `raw` field.

`errors.py` — `TeilautoError(message, hint=)` base with `exit_code = 1`; subclasses override it (`AuthRequiredError`=3, `NotFoundError`=4, `NoMatchError`=2 for the autobook deadline case). `RateLimitedError` and `ConfigError` inherit exit code 1.

### Things to Know

- Timestamps in models are kept as raw ISO strings from the API, not parsed to `datetime`; parsing to local time happens at render time in @/src/teilauto/output/render.py (`local_time`).
- The API's own `distance` field is known-unreliable, so the client does not expose it; distances are recomputed with haversine in @/src/teilauto/services/availability.py.
- `/prices` may return either a list or a single object; `CantamenClient.price()` normalizes by taking the first list element.
- For CityFlitzer (free-floating) cars, `/prices` ignores the requested time window entirely and always quotes a fixed now→+48h worst case (two days at the daily cap). Station-based cars honor the requested window (snapped to a 15-minute grid). This is why @/src/teilauto/cli/autobook.py no longer calls `/prices` at all — a per-candidate price lookup would report the same fixed number regardless of the actual booking. CityFlitzer billing is usage-based (first started hour billed in full, then 15-minute increments, plus kilometers and a daily cap), and the backend rewrites a booking's `timeRange.end` to the real trip end once it's returned.
- Cancelling a CityFlitzer booking rewrites `timeRange.end` to the cancel time but leaves `cancelled: false`. The caller's own active booking does not appear in that car's `/unavailabilities`.
- `GET /bookingproposals` is the availability oracle: a car is bookable for a window iff it appears there. `/pointsofinterest` supplies metadata only.
- Retries deliberately do not cover POSTs differently — `_request` treats all methods the same; only transport errors and 5xx are retried, so a 4xx booking conflict is surfaced immediately.
- The `verbose` flag prints `[http] METHOD path -> status` lines to stderr (never stdout), keeping `--json` stdout purity intact.

Created and maintained by Nori.
