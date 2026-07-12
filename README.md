# teilauto-cli

> Book a CityFlitzer before anyone else does — from your terminal.

[![CI](https://github.com/maxboettinger/teilauto-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/maxboettinger/teilauto-cli/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/teilauto-cli)](https://pypi.org/project/teilauto-cli/)
[![Python versions](https://img.shields.io/pypi/pyversions/teilauto-cli)](https://pypi.org/project/teilauto-cli/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

An unofficial command-line client for [teilauto](https://teilauto.net)/CityFlitzer
carsharing (Leipzig & Mitteldeutschland). Search cars, check prices, and manage
bookings without opening a browser — plus `teilauto autobook`, which watches for
a matching car and books it the instant one becomes free, then pings you on
Telegram or ntfy.

## Install

```bash
uv tool install teilauto-cli     # or: pipx install teilauto-cli
```

Requires Python 3.10+.

## 30 seconds to your first car

```bash
teilauto auth login                        # once; token lasts ~90 days
teilauto config set location.lat 51.3385    # your home coordinates
teilauto config set location.lng 12.3916
teilauto cars list                          # what's nearby?
teilauto bookings create 111 --for 1h       # book the VW Polo for an hour
```

`cars list` shows what's parked around you, closest first:

```
                                    Cars
┏━━━━━┳━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ ID  ┃ Name    ┃ Plate     ┃ Fuel ┃ Distance ┃ Address         ┃ Available ┃
┡━━━━━╇━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━┩
│ 111 │ VW Polo │ L-TA 1111 │ 80%  │ 120 m    │ Dresdner Str. 6 │ ✓ now     │
│ 222 │ VW Golf │ L-TA 2222 │ 20%  │ 120 m    │ Dresdner Str. 6 │ ✗         │
└─────┴─────────┴───────────┴──────┴──────────┴─────────────────┴───────────┘
```

## Autobook (the good part)

`autobook` runs `cars list` on a loop and books the first car that matches your
criteria — no manual refreshing, no lost race against other members.

```bash
teilauto autobook --for 45m --radius 800 --max-price 10 --deadline 18:00
```

What it does:

1. Prints the criteria (location, duration, min fuel, max price, deadline) and
   asks you to confirm — skip with `--yes` (required if you also pass `--json`,
   since JSON mode can't prompt).
2. Polls `cars list` every `--interval` seconds (120s by default) for cars
   newly available in your window.
3. For each candidate, fetches the live price. If `--max-price` is set and the
   price can't be determined, the car is **skipped** — it fails closed rather
   than risking an over-budget booking. (Use `--max-price` only when logged in;
   unauthenticated price lookups return empty data.)
4. Books the first car that passes, notifies you, and exits immediately.
   If a booking attempt fails (someone beat you to it), that car is retried up
   to 3 times before autobook gives up on it and moves on.
5. Give up early with `--until` (also usable as the booking's fixed end time)
   or `--deadline` — autobook exits with code 2 once the deadline passes with
   nothing booked.
6. `--dry-run` does everything except the actual booking (no login required)
   — use it to sanity-check your criteria first.

This spends real money on your real account the moment a match is found.
There's an inherent race: someone else's app can win the same car between your
poll and your booking request — that's what the retry logic is for, not a bug.

## Notifications

Configure Telegram, ntfy, or both — `watch` and `autobook` send updates through
whichever channels you enable.

**Telegram** — create a bot with [@BotFather](https://t.me/BotFather), then:

```bash
teilauto config set notify.telegram.bot_token 123456:ABC-your-bot-token   # stored in OS keyring
teilauto config set notify.telegram.chat_id 987654321                    # your chat/user id
teilauto config set notify.channels telegram
```

**ntfy** — pick a topic name, subscribe to it in the [ntfy app](https://ntfy.sh/),
then:

```bash
teilauto config set notify.ntfy.topic my-teilauto-alerts
teilauto config set notify.channels telegram,ntfy   # comma-separated to use both
```

Verify either (or both) with:

```bash
teilauto notify test
```

## Commands

| Command | What it does |
| --- | --- |
| `teilauto auth login` | Log in; stores a session token good for ~90 days. |
| `teilauto auth status` | Show whether you're logged in and until when. |
| `teilauto auth logout` | Delete the stored token. |
| `teilauto cars list` | List cars near a location, closest first. |
| `teilauto cars show CAR_ID` | Car detail plus blocked time ranges (next 24h by default). |
| `teilauto price CAR_ID` | Price of booking a car for a time window. Login required for real prices; unauthenticated requests return "unknown". |
| `teilauto bookings list` | Your bookings (upcoming only by default). |
| `teilauto bookings show BOOKING_ID` | One booking in detail. |
| `teilauto bookings create CAR_ID` | Book a car for a time window (asks for confirmation). |
| `teilauto bookings cancel BOOKING_ID` | Cancel a booking. |
| `teilauto watch` | Poll for newly available cars and notify — never books. |
| `teilauto autobook` | Poll and book the first match automatically. |
| `teilauto notify test` | Send a test message through every configured channel. |
| `teilauto config list/get/set/unset/path` | Inspect and edit configuration. |

Every command and group supports `-h`/`--help` for its full option list.

## Configuration

Config lives in a TOML file; run `teilauto config path` to find it (it uses
[platformdirs](https://pypi.org/project/platformdirs/), so the location
follows OS convention — e.g. `~/.config/teilauto/config.toml` on Linux).
`teilauto config list` shows the effective configuration — defaults, then file,
then environment overrides:

| Key | Default | Meaning |
| --- | --- | --- |
| `location.lat` | `51.33853` | Home latitude used when `--lat` isn't given. |
| `location.lng` | `12.39163` | Home longitude used when `--lng` isn't given. |
| `location.radius_m` | `500` | Default search radius in metres. |
| `defaults.min_fuel` | `0.0` | Default minimum fuel level (%) filter. |
| `defaults.window_min` | `30` | Default booking/search window length in minutes. |
| `defaults.interval_sec` | `120` | Default poll interval for `watch`/`autobook`, in seconds. |
| `api.prov_id` | `'118'` | Cantamen provider id (teilauto Mitteldeutschland). |
| `notify.channels` | `[]` | Active notification channels: `telegram`, `ntfy`, or both. |
| `notify.telegram.chat_id` | `''` | Telegram chat/user id to message. |
| `notify.ntfy.topic` | `''` | ntfy.sh topic to publish to. |
| `notify.ntfy.server` | `'https://ntfy.sh'` | ntfy server, if self-hosting. |

`notify.telegram.bot_token` is a secret and doesn't appear in `config list` —
set it with `config set`, and it's stored in the OS keyring, not the file.

Every key can be overridden with an environment variable:
`TEILAUTO_<SECTION>_<KEY>` (dots become underscores, uppercased) —
e.g. `TEILAUTO_LOCATION_RADIUS_M=800`. Two extra env vars exist outside the
config-key scheme: `TEILAUTO_TOKEN` (override the session token) and
`TEILAUTO_TG_BOT_TOKEN` (override the Telegram bot token), plus
`TEILAUTO_CONFIG_DIR` to point the whole config directory somewhere else
(handy for tests or multiple profiles).

**Secrets** (session token, Telegram bot token) are stored in this order:
OS keyring first; if no keyring is available, a `secrets.json` file in the
config directory with `chmod 600` permissions; environment variables always
win over both. Your account password is never stored anywhere — only the
session token returned by login.

## JSON output & scripting

Every data-producing command takes `--json` for machine-readable output.

```bash
teilauto cars list --available --json | jq -r '.[].car.name'
teilauto auth status --json | jq .expiry
```

Exit codes are stable and meant for scripting:

| Code | Meaning |
| --- | --- |
| `0` | Success. |
| `1` | Generic error (config problem, API error, aborted confirmation). |
| `2` | Usage error, or no matching car found (`autobook` deadline reached). |
| `3` | Authentication required — not logged in or token expired. |
| `4` | Requested resource not found (e.g. unknown booking id). |

## How it works / API notes

teilauto-cli talks to the Cantamen `casirest/v3` backend at
`https://de1.cantamen.de` — the same API the official `buchen.teilauto.net`
booking site uses, reverse-engineered by watching that site's network traffic.
Read-only endpoints (car listings, prices, availability) just need the public
`x-api-key` baked into that site's frontend JavaScript; it identifies the app,
not a user, so it's not treated as a secret here. Member actions (login,
creating/cancelling bookings) use a bearer-style token from `POST /tokens`,
scoped to provider id `118` (teilauto Mitteldeutschland). None of this is an
official, documented, or supported API — see Responsible use below.

## Responsible use

This is an **unofficial** client built by reverse-engineering the public
booking website; it is not affiliated with or endorsed by teilauto or
Cantamen. A few ground rules:

- Built for personal use on your own account, not for scraping at scale.
- Poll gently — the default interval is 120 seconds; don't turn it down
  aggressively across multiple instances.
- `autobook` and `bookings create` spend real money on your real account the
  moment a match is found. Read the confirmation prompt.
- The underlying endpoints are undocumented and can change or break without
  notice — there's no SLA here.

## Future extensions

Not implemented, but reasonable next steps: systemd/launchd service unit
helpers for running `watch`/`autobook` as a background service, geocoding
(address → coordinates, so you don't have to look up lat/lng by hand), and
quiet hours (suppress notifications overnight).

## Development

```bash
git clone https://github.com/maxboettinger/teilauto-cli
cd teilauto-cli
uv sync --dev
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Layout: `src/teilauto/api` (Cantamen client + models), `src/teilauto/cli`
(click commands, one module per command group), `src/teilauto/core`
(config, token storage, time parsing, geo), `src/teilauto/services`
(availability matching, notifiers, the poll loop), `src/teilauto/output`
(rendering — rich tables/panels and JSON).

Commits follow [Conventional Commits](https://www.conventionalcommits.org/).
Licensed under [MIT](LICENSE).
