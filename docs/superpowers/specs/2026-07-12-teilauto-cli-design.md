# teilauto CLI — Design Spec

**Date:** 2026-07-12
**Status:** Approved
**Package:** `teilauto-cli` · **Command:** `teilauto`

## Purpose

A modern, publishable CLI for managing teilauto/CityFlitzer carsharing (Cantamen
`casirest/v3` backend at `https://de1.cantamen.de`) covering all common use cases:
finding cars, checking availability and prices, managing bookings, a notify-only
watcher, and an `autobook` command that books a matching car the moment it becomes
available and notifies the user. Built with click + rich (via rich-click), layered
for maintainability, targeted at a public GitHub release.

## Background: the API

Reverse-engineered in the sibling `teilauto` repo (see its README for full notes):

- Base: `https://de1.cantamen.de/casirest/v3`; provider id `118` (teilauto Mitteldeutschland).
- Read-only endpoints need only the public frontend `x-api-key`
  (`6b4d4759-8fd1-b25a-c099-09c2af9c70ce`); it identifies the app, not a user, and
  is safe in source.
- Member actions need `authorization: Basic base64("<tokenId>:")` where the token
  comes from `POST /tokens` (body `{login, credential, provId: "118", storeLogin: true}`),
  valid ~90 days.
- Endpoints: `GET /pointsofinterest` (car metadata near a point),
  `GET /bookingproposals` (the availability oracle — only bookable cars appear),
  `GET /bookees/{id}`, `GET /unavailabilities`, `GET /prices`,
  `GET|POST /bookings`, `POST /tokens`, `DELETE /bookings/{id}` (cancel; verify
  exact method/shape during implementation against the live app).
- CityFlitzer = `bookeeType.name == "cityFlitzer"`. The API's `distance` field is
  unreliable; compute haversine client-side.

## Decisions (from brainstorming)

| Question | Decision |
| --- | --- |
| Autobook behavior | Book immediately + notify. Safety rails: criteria confirmation, `--dry-run`, `--max-price`, explicit `--for` duration. |
| Notification channels | Telegram + ntfy.sh, pluggable notifier interface. |
| Auth storage | OS keyring first, chmod-600 file fallback, `TEILAUTO_TOKEN` env override. Password never persisted. |
| Name | Command `teilauto`, PyPI package `teilauto-cli`. |
| v1 extras | Price queries, `config` command, `cars show` with unavailabilities. |
| Not in v1 | systemd/launchd service helpers (README "future extensions" only), geocoding, quiet hours. |
| Stack | click 8.4 + rich 15 + rich-click 1.9 + httpx 0.28 + keyring + platformdirs. Approach A (layered). |

## Command surface

```
teilauto
├── auth
│   ├── login                 # prompt email + password → POST /tokens; store token; never store password
│   ├── status                # token present? expiry, customer id
│   └── logout                # delete stored token
├── cars
│   ├── list                  # nearby cars: name, plate, fuel, distance, address, bookable flag
│   │                         #   --lat/--lng, --radius, --type cityflitzer|all, --available,
│   │                         #   --from/--for (availability window), --min-fuel
│   └── show <id>             # detail + blocked time ranges (unavailabilities)
├── price <car-id>            # --from (default now), --for DURATION | --until TIME
├── bookings
│   ├── list                  # upcoming by default; --all includes past
│   ├── show <id>
│   ├── create <car-id>       # --from --for/--until; shows price, confirms (--yes skips)
│   └── cancel <id>           # confirms (--yes skips)
├── watch                     # notify-only availability watcher (MVP parity)
│                             #   --radius, --min-fuel, --window, --interval
├── autobook                  # poll → book closest match immediately → notify → exit
│                             #   --for/--until (required), --radius, --min-fuel, --max-price,
│                             #   --deadline, --interval, --dry-run, --yes
├── config
│   ├── list | get <key> | set <key> <value> | unset <key> | path
└── notify
    └── test                  # send test message through configured channels
```

### Conventions

- `-h`/`--help` on every command/group; rich-click renders grouped, colored help.
- `--json` on every data-producing command: one stable JSON document to stdout.
- Root options: `--version`, `-v/--verbose` (log HTTP requests), `-q/--quiet`.
- Time parsing: `now`, `HH:MM`, `tomorrow HH:MM`, ISO-8601. Durations: `30m`, `2h`, `1h30m`.
- `--for DURATION` and `--until TIME` are mutually exclusive ways to set the end
  of a window; passing both is a usage error.
- Precedence: flags > `TEILAUTO_*` env vars > config file > built-in defaults.
- Confirmation prompts on money-touching actions (`bookings create/cancel`,
  `autobook` start); `--yes` for scripting.

## Architecture

`src/` layout; strict layering — CLI never touches httpx, services never print.

```
src/teilauto/
├── __init__.py               # __version__
├── cli/
│   ├── __init__.py           # root group, rich-click config, error handler, entry point
│   ├── auth.py  cars.py  bookings.py  price.py  watch.py  autobook.py
│   ├── config_cmd.py  notify_cmd.py
│   └── options.py            # shared decorators: location, time-window, --json
├── api/
│   ├── client.py             # CantamenClient: httpx.Client, timeouts, retry/backoff, auth header injection
│   ├── models.py             # frozen dataclasses: Car, BookingProposal, Booking, Price, Token, ...
│   └── errors.py             # ApiError, AuthRequiredError, NotFoundError, RateLimitedError
├── services/
│   ├── availability.py       # merge POI + proposals, haversine filter, fuel filter
│   ├── booking.py            # create/cancel with price lookup
│   ├── watcher.py            # generator-based poll engine: yields AvailabilityEvent; backoff on failure
│   └── notify/
│       ├── base.py           # Notifier protocol; dispatch-to-all with per-channel error isolation
│       ├── telegram.py
│       └── ntfy.py
├── core/
│   ├── config.py             # TOML config via platformdirs; env overrides; defaults
│   ├── tokenstore.py         # keyring → file fallback → env; chmod 600
│   ├── timeparse.py          # friendly datetime/duration parsing (zoneinfo, local tz)
│   └── geo.py                # haversine
└── output/
    ├── render.py             # rich tables/panels; TTY auto-degrade
    └── json_out.py           # dataclass → JSON with documented schema
```

### Key flows

**Availability (cars list / watch / autobook):**
1. `pointsofinterest` → `bookeeId → CarMeta` (filter type, haversine ≤ radius).
2. `bookingproposals` for `[start, end]` → bookable ids + earliest free time.
3. Intersect, apply min-fuel; sort by distance.

**Watcher engine:** a generator that polls at `--interval` (default 120 s), diffs
against the previous bookable set, and yields only *newly* available cars.
Failures double the sleep (cap 30 min) and reset on success. In-memory state only.
Consumed by both `watch` (event → notify) and `autobook` (first match → book).

**Autobook:** require auth up front → show criteria panel → confirm (`--yes`
skips) → poll → on candidates sorted by distance: check `--max-price` via
`/prices` if set → `POST /bookings` → notify result on all channels → exit 0.
If the POST races and fails (car snatched), log and continue polling. `--dry-run`
does everything except the POST and sends a "would have booked" notification.
`--deadline` reached → notify "no car found", exit 2.

**Auth:** `login` prompts (click hidden prompt for password), calls `POST /tokens`,
stores `{tokenId, expiry, customerId}` via tokenstore. Client injects
`authorization: Basic b64(tokenId + ":")` when a token exists; on 401 raises
`AuthRequiredError` → root handler prints "run `teilauto auth login`" and exits 3.

## Config

`~/.config/teilauto/config.toml` (platformdirs; correct per-OS path):

```toml
[location]
lat = 51.33853
lng = 12.39163
radius_m = 500

[defaults]
min_fuel = 0
window_min = 30
interval_sec = 120

[notify]
channels = ["telegram"]        # any of: telegram, ntfy

[notify.telegram]
chat_id = "123456789"          # bot token lives in keyring

[notify.ntfy]
topic = "my-topic"
server = "https://ntfy.sh"
```

Secrets (Cantamen token, Telegram bot token) go to keyring (service
`teilauto-cli`); when no keyring backend is available (headless Linux), fall back
to `secrets.json` next to the config with `0600` perms, warning once. Env
overrides: `TEILAUTO_TOKEN`, `TEILAUTO_TG_BOT_TOKEN`, plus `TEILAUTO_<SECTION>_<KEY>`
for config values.

## Output

- **Human:** rich tables (cars, bookings), panels (car detail, autobook summary),
  fuel color-coded (green ≥ 50, yellow ≥ 25, red below), distances in m.
  Non-TTY output degrades to plain text automatically.
- **JSON:** `--json` emits exactly one JSON document to stdout; schema mirrors the
  dataclasses (snake_case, ISO-8601 UTC timestamps); documented in README for
  scripting (`jq` examples).

## Error handling

Exception hierarchy in `api/errors.py` + `core` errors; caught once in the root
CLI callback wrapper. Human message to stderr with actionable hint. Exit codes:

| Code | Meaning |
| --- | --- |
| 0 | success |
| 1 | generic/API error |
| 2 | usage error (click) / autobook deadline with no match |
| 3 | auth required or token expired |
| 4 | resource not found |

Watcher/autobook loops never die from notifier failures or transient API errors
(backoff instead). Ctrl-C exits cleanly with a short message.

## Testing

- pytest; `respx` to mock httpx with recorded real-API JSON fixtures under
  `tests/fixtures/`.
- click `CliRunner` for command tests: help output, JSON schema, exit codes,
  confirmation prompts, config precedence.
- Watcher engine tested with a fake clock/injected sleeper (no real sleeps).
- No live API calls in CI.

## Packaging & distribution

- `pyproject.toml`, hatchling backend, src layout,
  `[project.scripts] teilauto = "teilauto.cli:main"`.
- `requires-python >= 3.10`; `tomli` conditional dep for 3.10 only.
- Dev tooling: uv, ruff (lint + format), pytest.
- CI (GitHub Actions): ruff + pytest matrix, Python 3.10/3.12/3.14 ×
  Linux/macOS/Windows. Release workflow publishing to PyPI on tag (trusted
  publishing) — included but inert until PyPI project exists.
- Install docs: `uv tool install teilauto-cli`, `pipx install teilauto-cli`.
- MIT license, CHANGELOG.md (Keep a Changelog), `.gitignore`.

## README structure (funnel)

1. Hero: one-line pitch, badges (CI, PyPI, Python versions, license).
2. Demo block (rich table screenshot/asciinema placeholder).
3. Install (uv/pipx, 2 lines).
4. 30-second quickstart: `auth login` → `cars list` → `autobook`.
5. Autobook showcase (the killer feature) incl. notification setup.
6. Full command reference (generated help excerpts).
7. Configuration reference.
8. JSON output & scripting recipes.
9. Responsible use: unofficial API, personal use, gentle polling (120 s default),
   autobook spends real money.
10. Future extensions: systemd/launchd service helpers, geocoding, quiet hours.
11. Development & contributing.

## Non-goals (v1)

- systemd/launchd unit generation (documented as future extension only).
- Geocoding/address search (coords only).
- Multi-provider support beyond provId 118 (keep provId configurable in config).
- Persisted watcher state across restarts.
