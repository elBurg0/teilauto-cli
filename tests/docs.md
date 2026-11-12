# Noridoc: tests

Path: @/tests

### Overview

The pytest suite for the whole package: unit tests per core module (config, tokenstore, timeparse, geo, models, watcher, JSON serialization) and CLI-level tests per command group driven through click's `CliRunner`. No test ever hits the live Cantamen API or performs a real sleep.

### How it fits into the larger codebase

Tests import the public surfaces documented in @/src/teilauto: the `cli` group from @/src/teilauto/cli, `CantamenClient` from @/src/teilauto/api/client.py, and the core/services modules directly. HTTP is mocked with `respx` against `BASE_URL`, using recorded-API-shaped JSON under @/tests/fixtures (POIs, proposals, prices, bookings, live-shaped bookings, token, unavailabilities). CI (@/.github/workflows/ci.yml) runs the suite across three OSes and Python 3.10/3.12/3.14.

### Core Implementation

`conftest.py` provides the isolation machinery: `isolated_config` points `TEILAUTO_CONFIG_DIR` at a tmp dir, strips `TEILAUTO_TOKEN`/`TEILAUTO_TG_BOT_TOKEN`, and monkeypatches the `keyring` module inside @/src/teilauto/core/tokenstore.py with a `_NoKeyring` stub that always raises — so all secret storage in tests exercises the `secrets.json` fallback path. `logged_in` builds on that by saving a `StoredToken` with a far-future expiry. Fixture loaders expose each JSON file in @/tests/fixtures as a pytest fixture.

CLI tests invoke `cli` (not `main()`) via `CliRunner` and assert on exit codes, stdout/stderr text, JSON schemas, and confirmation prompts. The endless loops are bounded without wall-clock time: watcher unit tests inject `sleeper=lambda s: None` and `islice` the generator; `watch` CLI tests monkeypatch `teilauto.cli.watch.time.sleep` with a fake that raises a custom `Exception` subclass to end the loop (deliberately not `KeyboardInterrupt` — `CliRunner` only catches `Exception` subclasses); autobook tests no-op `time.sleep` and let the booking/deadline path terminate naturally.

### Things to Know

- The bookings fixture is pinned to far-future dates (commit `2cdfa16`) so the `bookings list` past-filter tests do not depend on the real clock.
- `bookings.json` keeps the legacy flat shape; `bookings_live.json` and `unavailabilities.json` mirror the live responses (expanded `bookee`, nested `unavailabilityTimeRanges`) with made-up data.
- Usage-error assertions read `result.stderr` because click ≥ 8.2 prints usage errors there.
- Autobook has no `--max-price` option and never calls `/prices`; `test_cli_autobook.py` asserts this directly (`--max-price` is rejected as an unknown option, and the booked/dry-run JSON has no `price` key) and asserts the default 1h window is what gets POSTed when neither `--for` nor `--until` is given. A reminder that autobook has several pre-loop guard clauses (auth, criteria confirmation, deadline checks) that can short-circuit a test unintentionally if it's meant to reach the polling loop.
- `test_models.py` covers both `Price.from_api` shapes: the live `priceIncl`/`code` schema and the legacy `gross`/`currency` fallback. `test_availability.py` covers `find_cars` matching a lowercase `"cityflitzer"` bookee type against the default `cityFlitzer` filter.
- Since `main()` is bypassed, tests asserting `TeilautoError` behavior check `result.exception` / exit codes from click itself, not the human error rendering done in @/src/teilauto/cli/__init__.py.

Created and maintained by Nori.
