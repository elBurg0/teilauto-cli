# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-12

Initial public release.

### Added

- `teilauto auth` — `login`, `logout`, `status`: session-token authentication
  against the Cantamen `casirest/v3` API, token valid ~90 days.
- `teilauto cars` — `list`, `show`: find nearby cars with distance, fuel,
  and live bookability; inspect a single car's blocked time ranges.
- `teilauto price`: quote the cost of booking a car for a given time window.
- `teilauto bookings` — `list`, `show`, `create`, `cancel`: full booking
  lifecycle, with a confirmation prompt before anything that costs money.
- `teilauto watch`: poll for newly available cars near you and notify —
  never books on its own.
- `teilauto autobook`: poll and book the first matching car the instant it's
  available, with safety rails (`--dry-run`, `--max-price` that fails closed
  on unknown price, `--deadline`/`--until`, a criteria confirmation, and a
  3-attempt retry cap per car if a booking is lost to another member).
- `teilauto notify test`: send a test message through every configured
  notification channel.
- `teilauto config` — `list`, `get`, `set`, `unset`, `path`: TOML-backed
  configuration with `TEILAUTO_*` environment variable overrides for every key.
- Telegram and ntfy.sh notification channels, selectable via `notify.channels`.
- `--json` output on every data-producing command, for scripting with `jq`.
- Stable, documented exit codes (0 ok, 1 error, 2 usage/no-match, 3 auth
  required, 4 not found).
- Secret storage via the OS keyring, falling back to a chmod-600
  `secrets.json`, with environment-variable overrides taking precedence over
  both; account passwords are never persisted.
- CI across Linux/macOS/Windows and Python 3.10–3.14 (lint, format check,
  tests), plus a tag-triggered PyPI release workflow.
- 132-test suite covering the API client, CLI commands, config, token
  storage, time parsing, geo, and notification services.
