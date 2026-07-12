# Noridoc: teilauto-cli

Path: @/

### Overview

`teilauto-cli` is a publish-ready Python CLI (command `teilauto`) for the teilauto/CityFlitzer carsharing service in Leipzig/Mitteldeutschland. It talks to the reverse-engineered Cantamen `casirest/v3` API to search cars, check prices, and manage bookings, and adds two long-running modes: `watch` (notify-only) and `autobook` (books the first matching car and notifies via Telegram/ntfy).

### How it fits into the larger codebase

This is the repository root of a standalone, uv-managed, hatchling-built src-layout package. All application code lives in @/src/teilauto (see its docs.md for the layer map); @/tests holds the respx-mocked pytest suite; @/docs/superpowers contains the approved design spec and the task-by-task implementation plan the codebase was built from — the spec is the authoritative record of intent (API notes, safety-rail decisions, non-goals). Like `.superpowers/sdd/`, `docs/` is gitignored and local-only — a working-artifact directory from the agent-driven build, not part of the published repo's git history; it exists on disk for whoever built the package but ships to no one. @/.github/workflows runs lint + format + tests on a 3-OS × Python 3.10/3.12/3.14 matrix and publishes to PyPI via trusted publishing on `v*` tags.

```
┌────────────┐   TEILAUTO_* env / config.toml / OS keyring
│  teilauto   │──────────────────────────────────────────────┐
│  (CLI)      │                                              │
└─────┬───────┘                                              │
      │ httpx (api layer only)                               │
      ▼                                                      ▼
https://de1.cantamen.de/casirest/v3        Telegram bot API / ntfy.sh
(provider 118; public x-api-key for reads,        (notifications)
 Basic token from POST /tokens for member actions)
```

### Core Implementation

Entry point: `[project.scripts] teilauto = "teilauto.cli:main"` in @/pyproject.toml. Runtime stack: rich-click (click 8.x) for commands, rich for output, httpx for HTTP, keyring + platformdirs for secret and config storage, tomli-w (+tomli on 3.10) for the config file. Every data command supports `--json` with a single-document stdout contract, and exit codes are a stable scripting API (0 ok / 1 error / 2 usage-or-no-match / 3 auth / 4 not found) — both are documented for users in @/README.md. `[tool.hatch.build.targets.wheel]` in @/pyproject.toml excludes `**/docs.md`: the per-directory noridocs stay tracked in git as maintained tooling docs but are stripped from the built wheel, so they're absent from a `pip install`ed copy of the package.

### Things to Know

- The API is unofficial and undocumented; the `x-api-key` committed in @/src/teilauto/api/client.py is the public app identifier from the official site's frontend JS, not a secret. The README's "Responsible use" section frames the polling etiquette (120 s default interval) that the config defaults encode.
- `autobook` spends real money; its safety rails (confirmation, `--dry-run`, fail-closed `--max-price`, retry cap, deadlines) are detailed in @/src/teilauto/cli/docs.md.
- The `.superpowers/sdd/` directory holds per-task briefs/reports and review diffs from the agent-driven build process — development artifacts, not part of the package.
- Commits follow Conventional Commits; @/CHANGELOG.md follows Keep a Changelog.

Created and maintained by Nori.
