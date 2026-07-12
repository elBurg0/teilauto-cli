# Noridoc: notify

Path: @/src/teilauto/services/notify

### Overview

Pluggable push-notification channels (Telegram bot API and ntfy.sh) behind a minimal `Notifier` protocol (`name` attribute + `send(title, message)`), plus a factory that builds notifiers from configuration and a fan-out helper that never raises.

### How it fits into the larger codebase

`build_notifiers(settings)` and `send_all()` are the only entry points, consumed by the `watch`, `autobook`, and `notify test` commands (@/src/teilauto/cli/watch.py, @/src/teilauto/cli/autobook.py, @/src/teilauto/cli/notify_cmd.py). The factory reads `Settings.channels` from @/src/teilauto/core/config.py and pulls the Telegram bot token from the secret store (@/src/teilauto/core/tokenstore.py, `TG_BOT_TOKEN_KEY`) with `TEILAUTO_TG_BOT_TOKEN` taking precedence. Misconfiguration (enabled channel with missing token/chat_id/topic, or an unknown channel name) raises `ConfigError` from @/src/teilauto/api/errors.py with a copy-pasteable `teilauto config set ...` hint.

### Core Implementation

`base.py` defines the `Notifier` `Protocol` and `send_all()`, which loops over all notifiers, catches *every* exception, and returns human-readable `"channel: error"` strings instead of raising — this is the invariant that keeps long-running watch/autobook loops alive through notifier outages. `telegram.py` POSTs to `api.telegram.org/bot<token>/sendMessage`; `ntfy.py` POSTs the message body to `<server>/<topic>`.

Callers are expected to print the error strings `send_all()` returns rather than discard them: `watch.py` already did this per tick, and `autobook.py`'s four call sites (autobook-started, give-up, dry-run, booked) now do too, each printing `notify failed: <error>` to `err_console`. So a stale bot token or bad topic is visible on stderr instead of silently swallowed — this printing happens unconditionally, including in `--json` mode, since it targets stderr and does not touch the JSON stdout contract.

### Things to Know

- **Token/topic-leak protection**: both `TelegramNotifier.send` and `NtfyNotifier.send` deliberately avoid `raise_for_status()` and never interpolate the httpx exception text into their error messages, because both can embed the full request URL — which contains the bot token (Telegram) or the topic name (ntfy, since the topic is the last URL path segment and can itself be secret). Transport errors are caught around the `httpx` call and re-raised as `RuntimeError(f"... request failed ({type(exc).__name__})")` (exception type name only, never the exception text); HTTP errors are surfaced via a manual status-code check as `RuntimeError(f"... returned HTTP <code>")`. These strings flow into `send_all()` results and end up on stderr, so they must stay secret-free.
- `NtfyNotifier` puts the title in an HTTP header, which is latin-1 only — callers keep titles ASCII and put emoji in the body (all call sites follow this convention).
- `send_all` never writes output itself; callers decide whether to print the returned error strings (services never print — see @/src/teilauto/services/docs.md).

Created and maintained by Nori.
