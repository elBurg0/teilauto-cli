from __future__ import annotations

import sys
from dataclasses import dataclass, field

import rich_click as click

from teilauto.api.client import CantamenClient
from teilauto.api.errors import AuthRequiredError, TeilautoError
from teilauto.core import tokenstore
from teilauto.core.config import Settings, load_settings
from teilauto.core.tokenstore import StoredToken
from teilauto.output.render import err_console

click.rich_click.SHOW_ARGUMENTS = True

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@dataclass
class AppContext:
    settings: Settings
    verbose: bool = False
    quiet: bool = False
    _token: StoredToken | None = field(default=None, init=False, repr=False)
    _token_loaded: bool = field(default=False, init=False, repr=False)

    @property
    def token(self) -> StoredToken | None:
        if not self._token_loaded:
            self._token = tokenstore.load_token()
            self._token_loaded = True
        return self._token

    def client(self) -> CantamenClient:
        token = self.token
        return CantamenClient(token_id=token.id if token else None, verbose=self.verbose)

    def require_auth_client(self) -> CantamenClient:
        if self.token is None:
            raise AuthRequiredError()
        return CantamenClient(token_id=self.token.id, verbose=self.verbose)


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(package_name="teilauto-cli", prog_name="teilauto")
@click.option("-v", "--verbose", is_flag=True, help="Show HTTP requests and debug detail.")
@click.option("-q", "--quiet", is_flag=True, help="Suppress non-essential output.")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, quiet: bool) -> None:
    """Manage teilauto/CityFlitzer carsharing from your terminal.

    Search cars, check prices, manage bookings — and auto-book a car the
    moment it becomes available.
    """
    ctx.obj = AppContext(settings=load_settings(), verbose=verbose, quiet=quiet)


from teilauto.cli.auth import auth  # noqa: E402
from teilauto.cli.bookings import bookings  # noqa: E402
from teilauto.cli.cars import cars  # noqa: E402
from teilauto.cli.config_cmd import config_group  # noqa: E402
from teilauto.cli.notify_cmd import notify  # noqa: E402
from teilauto.cli.price import price  # noqa: E402
from teilauto.cli.watch import watch_cmd  # noqa: E402

cli.add_command(auth)
cli.add_command(bookings)
cli.add_command(cars)
cli.add_command(config_group)
cli.add_command(notify)
cli.add_command(price)
cli.add_command(watch_cmd)


def main() -> None:
    try:
        rv = cli(standalone_mode=False)
    except click.exceptions.Exit as exc:  # raised only in edge paths; keep for safety
        sys.exit(exc.exit_code)
    except click.exceptions.Abort as exc:
        if isinstance(exc.__cause__, KeyboardInterrupt) or isinstance(
            exc.__context__, KeyboardInterrupt
        ):
            err_console.print("\nStopped.")
            sys.exit(130)
        err_console.print("Aborted.")
        sys.exit(1)
    except click.ClickException as exc:
        exc.show()
        sys.exit(exc.exit_code)
    except TeilautoError as exc:
        err_console.print(f"[red]Error:[/red] {exc}")
        if exc.hint:
            err_console.print(f"[dim]{exc.hint}[/dim]")
        sys.exit(exc.exit_code)
    except KeyboardInterrupt:
        err_console.print("\nStopped.")
        sys.exit(130)
    if isinstance(rv, int):
        sys.exit(rv)
