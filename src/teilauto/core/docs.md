# Noridoc: core

Path: @/src/teilauto/core

### Overview

Cross-cutting infrastructure with no CLI or HTTP dependencies: layered TOML configuration (`config.py`), secret/token storage with keyring-to-file fallback (`tokenstore.py`), human-friendly time and duration parsing (`timeparse.py`), and haversine distance (`geo.py`).

### How it fits into the larger codebase

`load_settings()` produces the frozen `Settings` dataclass exposed as the lazy, cached `AppContext.settings` property in @/src/teilauto/cli/__init__.py — it only runs the first time a command actually reads `app.settings`, so commands that never need settings (`config` subcommands, `auth logout`, `--version`) work even against a broken `config.toml`. @/src/teilauto/cli/config_cmd.py drives the raw read/write/coerce helpers directly, and additionally validates a coerced value's type against `DEFAULTS` before writing it (`_validate_value`), so bad types are rejected at `config set` time rather than only surfacing later when `load_settings()` runs. `tokenstore.load_token()` supplies the session token that `AppContext` injects into `CantamenClient` (@/src/teilauto/api/client.py); the same secret store holds the Telegram bot token consumed by `build_notifiers()` in @/src/teilauto/services/notify/base.py. `parse_time`/`parse_duration` back the `--from/--for/--until/--deadline` options in @/src/teilauto/cli/options.py and @/src/teilauto/cli/autobook.py. `haversine_m` is used by @/src/teilauto/services/availability.py because the API's own distance field is unreliable. Config errors raise `ConfigError` from @/src/teilauto/api/errors.py so the root handler can render them uniformly.

### Core Implementation

**config.py** — precedence is built-in `DEFAULTS` ← `config.toml` (deep-merged) ← `TEILAUTO_<SECTION>_<KEY>` env vars (dots→underscores, uppercased). Env values are coerced to the *type of the default* (bool/list/float/int/str); `notify.channels` accepts a comma-separated string. `KNOWN_KEYS` is derived from the leaf keys of `DEFAULTS` and doubles as the validation whitelist for `config get/set` and as the set of env vars scanned. The config directory comes from `platformdirs.user_config_path("teilauto")`, overridable wholesale via `TEILAUTO_CONFIG_DIR` (this is how tests isolate themselves). `coerce_value()` turns CLI strings into bool/int/float/list before writing TOML. Invalid TOML raises `ConfigError` with a fix-or-delete hint rather than a traceback. A separate helper, `_cast(key, value, caster)`, wraps every type coercion that can fail — both the env-var override casting in `_merged()` and every field of the final `Settings(...)` construction in `load_settings()` — catching `(TypeError, ValueError)` and re-raising as `ConfigError` (hinting at `config set`/`config unset`) instead of letting a raw exception escape. So a malformed value anywhere in `config.toml` or the environment (e.g. `lat = "abc"`) surfaces as a clean, handled error the moment `load_settings()` runs.

**tokenstore.py** — secrets are namespaced under keyring service `teilauto-cli`. Write path: try keyring; on any exception fall back to `secrets.json` in the config dir, warning once per process (`_warned_fallback`). The fallback file is created 0600-from-birth: `os.open(tmp, O_CREAT|O_WRONLY|O_TRUNC, 0o600)` then atomic `os.replace` onto the real path, plus a belt-and-braces `chmod(0o600)`. Read path: keyring first, then the file. Env overrides always win: `TEILAUTO_TOKEN` short-circuits `load_token()` entirely (returns a `StoredToken` with no expiry/customer), and `TEILAUTO_TG_BOT_TOKEN` is checked before the store in the notifier factory. The Cantamen session token is stored as a JSON blob `{id, expiry, customer_id}` under key `cantamen-token`; the account password is never persisted anywhere.

**timeparse.py** — `parse_time` accepts `now`, `HH:MM`, `today/tomorrow HH:MM`, and ISO-8601 (trailing `Z` normalized to `+00:00`); a bare `HH:MM` more than a minute in the past rolls over to tomorrow. `parse_duration` accepts `30m`, `2h`, `1h30m`, `45min`, or a bare minute count.

**geo.py** — plain haversine on WGS84 coordinates returning metres.

### Things to Know

- The DST correctness of `parse_time` is subtle and documented in its docstring: in real CLI usage (no explicit `now`), rollover arithmetic is done on a *naive* wall-clock datetime and only the final candidate is localized via `naive.astimezone()`, so the system supplies the correct offset for the target date. When tests pass an explicit `now`, its tzinfo is reused as-is — a real `ZoneInfo` self-corrects across DST boundaries, a fixed-offset `timezone` intentionally does not.
- `secrets.json` is *also* consulted when keyring reads fail, so a machine that later gains a keyring backend still finds file-stored secrets; `delete_secret` scrubs both locations.
- `Settings` is intentionally flat and frozen — CLI code never re-reads config mid-run; env/config changes only apply to new invocations.
- `notify.telegram.bot_token` is deliberately absent from `DEFAULTS`/`KNOWN_KEYS`: it is a secret handled by @/src/teilauto/cli/config_cmd.py via `SECRET_KEYS`, never written to the TOML file.

Created and maintained by Nori.
