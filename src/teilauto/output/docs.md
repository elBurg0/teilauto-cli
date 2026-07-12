# Noridoc: output

Path: @/src/teilauto/output

### Overview

All user-facing rendering: `render.py` holds the shared rich `Console` objects and the table/panel builders for cars, bookings, and key-value detail views; `json_out.py` converts arbitrary dataclass graphs to JSON for the `--json` flag.

### How it fits into the larger codebase

Every command in @/src/teilauto/cli prints through the module-level `console` (stdout) and `err_console` (stderr) defined in `render.py` — including the root error handler in @/src/teilauto/cli/__init__.py. `print_json()` is the single stdout emitter in JSON mode. The renderers take the models from @/src/teilauto/api/models.py and `CarAvailability` from @/src/teilauto/services/availability.py as-is; no layer below this one ever prints.

### Core Implementation

`render.py`: `cars_table` / `bookings_table` / `unavailability_table` build rich Tables; `kv_panel` builds the aligned key-value panels used for car detail, booking confirmation, auth status, and the autobook criteria summary. `fuel_text` color-codes fuel (green ≥50%, yellow ≥25%, red below, dim `?` for unknown). `local_time` converts the API's raw ISO/`Z` timestamp strings into local `%Y-%m-%d %H:%M` (returning `—` for missing/unparsable values) — this is the only place API timestamps get humanized. Rich auto-degrades to plain text on non-TTY output.

`json_out.py`: `to_jsonable` recursively unwraps dataclasses (by field), dicts, lists/tuples, `datetime` (→ ISO), and `Path` (→ str); `print_json` emits exactly one indented, non-ASCII-escaped JSON document via `click.echo`.

### Things to Know

- The stdout-purity invariant for `--json` lives in the callers, but this module enables it: progress/diagnostics go through `err_console`, data through `print_json`, so `teilauto ... --json | jq` always sees a single document.
- JSON schemas mirror the dataclass fields (snake_case); `Booking` and `Price` include their `raw` API dict, so JSON consumers see the full upstream payload.
- Timestamps inside JSON output remain the API's raw ISO strings (models store strings, not datetimes); only human rendering localizes them.

Created and maintained by Nori.
