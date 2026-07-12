# Noridoc: notify

Path: @/src/teilauto/services/notify

### Overview

Pluggable push-notification channels (Telegram bot API and ntfy.sh) behind a minimal `Notifier` protocol (`name` attribute + `send(title, message)`), plus a factory that builds notifiers from configuration and a fan-out helper that never raises.

### How it fits into the larger codebase

`build_notifiers(settings)` and `send_all()` are the only entry points, consumed by the `watch`, `autobook`, and `notify test` commands (@/src/teilauto/cli/watch.py, @/src/teilauto/cli/autobook.py, @/src/teilauto/cli/notify_cmd.py). The factory reads `Settings.channels` from @/src/teilauto/core/config.py and pulls the Telegram bot token from the secret store (@/src/teilauto/core/tokenstore.py, `TG_BOT_TOKEN_KEY`) with `TEILAUTO_TG_BOT_TOKEN` taking precedence. Misconfiguration (enabled channel with missing token/chat_id/topic, or an unknown channel name) raises `ConfigError` from @/src/teilauto/api/errors.py with a copy-pasteable `teilauto config set ...` hint.

### Core Implementation

`base.py` defines the `Notifier` `Protocol` and `send_all()`, which loops over all notifiers, catches *every* exception, and returns human-readable `"channel: error"` strings instead of raising — this is the invariant that keeps long-running watch/autobook loops alive through notifier outages. `telegram.py` POSTs to `api.telegram.org/bot<token>/sendMessage`; `ntfy.py` POSTs the message body to `<server>/<topic>`.

### Things to Know

- **Token-leak protection** (see commit `fe7d14a`): `TelegramNotifier.send` deliberately avoids `raise_for_status()` and never interpolates the httpx exception text into its error messages, because both can embed the request URL — which contains the bot token. Transport errors surface as `Telegram request failed (<ExceptionTypeName>)` (type name only); HTTP errors as `Telegram API returned HTTP <code>`. These strings flow into `send_all()` results and end up on stderr, so they must stay token-free.
- `NtfyNotifier` puts the title in an HTTP header, which is latin-1 only — callers keep titles ASCII and put emoji in the body (all call sites follow this convention).
- `send_all` never writes output itself; callers decide whether to print the returned error strings (services never print — see @/src/teilauto/services/docs.md).

Created and maintained by Nori.
