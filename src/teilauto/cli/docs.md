# Noridoc: cli

Path: @/src/teilauto/cli

### Overview

The rich-click command layer: one module per command group (`auth`, `cars`, `price`, `bookings`, `watch`, `autobook`, `config`, `notify`), the root group + `main()` entry point in `__init__.py`, and shared option decorators in `options.py`. This layer owns all printing and all exit-code decisions; it never touches httpx directly (that is @/src/teilauto/api's job).

### How it fits into the larger codebase

`pyproject.toml` maps the `teilauto` script to `teilauto.cli:main`. The root group builds an `AppContext` as `ctx.obj` with both `token` and `settings` as lazily loaded, cached properties — the root `cli()` callback does not call `load_settings()` (@/src/teilauto/core/config.py) itself; it only runs the first time a command actually reads `app.settings`. This means `config get/set/unset`, `auth logout`, and `--version` work even against a broken `config.toml`, since they never touch `app.settings`. Commands get clients via `app.client()` (anonymous or token-bearing) or `app.require_auth_client()` (raises `AuthRequiredError` when logged out). Business logic is delegated to @/src/teilauto/services; rendering to @/src/teilauto/output.

```
main() ── error mapping ──> exit code
  └─ cli (root group, builds AppContext)
       ├─ auth / cars / price / bookings / config / notify   (one-shot commands)
       └─ watch / autobook  ──> services.watcher.watch(fetch) loop
                                    └─ fetch() = services.availability.find_cars(client, ...)
```

### Core Implementation

**Error handling / exit codes** (`__init__.py`): `main()` runs the group with `standalone_mode=False` so exceptions reach it, then maps: `click.exceptions.Exit` → its code (rich-click can swallow `ctx.exit()` return paths, so both the exception and an integer return value `rv` are honored — see commit `9cb9612`); `Abort` caused by `KeyboardInterrupt` → 130 with "Stopped.", other aborts (declined confirmation) → 1; `ClickException` (usage errors) → self-rendered, exit 2; `TeilautoError` → red message + dim hint on stderr, exit per the hierarchy in @/src/teilauto/api/errors.py (1/2/3/4); bare `KeyboardInterrupt` → 130.

**Shared options** (`options.py`): `location_options` (`--lat/--lng/--radius`, `None` defaults resolved from `Settings` via `resolve_location`), `window_options` (`--from` default `now`, `--for` duration XOR `--until` end time — both is a `UsageError`), `json_option` (`--json`). `resolve_window` parses via @/src/teilauto/core/timeparse.py and rejects non-positive windows.

**Command modules**: `auth.py` (login prompts email + hidden password, POSTs `/tokens`, stores only the token; `status --json` exits 3 when logged out after printing JSON), `cars.py` (`list` = one `find_cars` call, `show` = bookee detail + unavailabilities, default window 24h), `price.py`, `bookings.py` (`list` filters past bookings client-side unless `--all`; `create` prompts for confirmation and shows a price-confirmed panel before booking *unless* `--json`, matching the `autobook` convention: `--json` requires `--yes` up front — `if as_json and not yes: raise click.UsageError(...)` — and both the panel and its price lookup are skipped entirely in JSON mode, so `--json` booking never fetches a price before creating the booking; `cancel` prompts unless `--yes`), `config_cmd.py` (validates keys against `KNOWN_KEYS` plus the `SECRET_KEYS` mapping that routes `notify.telegram.bot_token` to the keyring instead of the TOML file; `get` on a secret only reports `(set)`/`(not set)`; `set` runs the coerced value through `_validate_value()`, which checks it against the corresponding `DEFAULTS` leaf type before writing to TOML — rejecting e.g. `location.lat abc` up front with a `ConfigError` instead of writing a value that only breaks later at `load_settings()` time; the one deliberate exception is a `str`-typed default receiving a numeric coercion, e.g. `notify.telegram.chat_id 42`, which is converted back to `"42"` rather than rejected, since chat ids are strings that happen to look numeric), `notify_cmd.py` (`notify test` fan-out with per-channel ✓/✗ and exit 1 if any failed), `watch.py`, and `autobook.py`.

**Autobook money-safety rails** (`autobook.py`): booking length is mandatory (`--for` XOR `--until`); criteria panel + confirmation before starting (`--yes` skips; `--json` *requires* `--yes` because JSON mode cannot prompt); auth is required up front unless `--dry-run`; `--max-price` fails **closed** — if the price lookup errors or returns no total, the car is skipped, never booked; each car gets at most 3 booking attempts (`failed_counts`, replayed from `WatchTick.retryable` on later ticks) before being abandoned; `--until` doubles as an implicit deadline (once that wall-clock time passes there is nothing left to book) and `--deadline` gives up explicitly — both notify and raise `NoMatchError` (exit 2). `--dry-run` performs everything except the `POST /bookings` and sends a "would have booked" notification. In `--json` mode all human chatter is suppressed or routed to stderr and `finish()` prints exactly one status document (`booked` / `dry_run` / `no_match`) to stdout.

### Things to Know

- Subcommand modules are imported *after* the root group is defined at the bottom of `__init__.py` (with `noqa: E402`) to avoid circular imports, then registered with `add_command`.
- `AppContext.token` and `AppContext.settings` are both lazy, cached properties; `TEILAUTO_TOKEN` env makes `token` non-None without any stored login. Because `settings` is only loaded on first read, a broken `config.toml` no longer breaks every command — only the ones that read `app.settings` (e.g. `cars list`, `bookings create`, `autobook`, `watch`) surface the resulting `ConfigError`; `config get/set/unset`, `auth logout`, and `--version` are unaffected.
- Watch and autobook print a startup banner *and* send a startup notification; both `watch` and `autobook` now surface per-channel notify failures on stderr at every `send_all()` call site (autobook: start, dry-run, booked, and give-up messages) rather than relying on `send_all`'s never-raise contract silently.
- `autobook`'s booking window is recomputed at booking time (`booking_window()`): `start = now`, end = `now + duration` or the fixed `--until` — so a car found 20 minutes into the hunt is still booked for the full `--for` duration.
- Deadline checks run before the first poll and after every tick, so `--deadline` in the past exits 2 immediately.
- Both `KeyboardInterrupt` mappings exist because click wraps Ctrl-C in `Abort` inside prompts but lets it propagate bare inside the poll loops.

Created and maintained by Nori.
