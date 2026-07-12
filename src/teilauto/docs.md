# Noridoc: teilauto (package)

Path: @/src/teilauto

### Overview

The `teilauto` Python package — a publish-ready CLI (PyPI `teilauto-cli`, command `teilauto`) for the teilauto/CityFlitzer carsharing service, built on the reverse-engineered Cantamen `casirest/v3` API. The package is strictly layered; each subpackage has its own docs.md.

### How it fits into the larger codebase

This is the entire application; @/tests exercises it via click's `CliRunner` and respx-mocked HTTP. `__init__.py` only exposes `__version__` (from installed package metadata, `0.0.0.dev0` on an uninstalled checkout).

### Core Implementation

Layering, top to bottom — imports only ever point downward, and two invariants are enforced by convention throughout: **the CLI never touches httpx** and **services never print**.

| Layer | Responsibility |
| --- | --- |
| @/src/teilauto/cli | rich-click commands, all terminal output, exit-code mapping |
| @/src/teilauto/output | rich renderers + `--json` serialization |
| @/src/teilauto/services | availability merge, transition-based watch loop, notifiers |
| @/src/teilauto/api | `CantamenClient` (httpx, retries, error mapping), frozen models, `TeilautoError` hierarchy |
| @/src/teilauto/core | config (defaults ← file ← env), secret/token store, time parsing, haversine |

Data path for the flagship flow: `cli/autobook.py` → `services/watcher.watch()` polling `services/availability.find_cars()` → `api/client.CantamenClient` (`/pointsofinterest` + `/bookingproposals`, then `/prices` and `POST /bookings`) → notification fan-out via `services/notify` → exit code from `api/errors.py` via `cli.main()`.

### Things to Know

- Every module starts with `from __future__ import annotations`; the package supports Python 3.10+ (hence `tomli` fallback in core and `timezone.utc` instead of `datetime.UTC`).
- All timestamps cross the API boundary as UTC `...T...Z` strings (`iso_utc` in @/src/teilauto/api/client.py); models keep them as raw strings; only @/src/teilauto/output/render.py localizes them for humans.
- Exit codes are a stable contract: 0 ok, 1 generic/API/config error, 2 usage or autobook no-match, 3 auth required, 4 not found.
- The design spec lives at @/docs/superpowers/specs/2026-07-12-teilauto-cli-design.md and the task-by-task implementation plan at @/docs/superpowers/plans/2026-07-12-teilauto-cli.md.

Created and maintained by Nori.
