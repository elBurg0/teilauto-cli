from __future__ import annotations

import rich_click as click

from teilauto.api.client import CantamenClient
from teilauto.cli.options import json_option
from teilauto.core import tokenstore
from teilauto.core.tokenstore import StoredToken
from teilauto.output.json_out import print_json
from teilauto.output.render import console, kv_panel, local_time


@click.group()
def auth() -> None:
    """Log in to your teilauto account and manage the session token."""


@auth.command()
@click.option("--email", prompt="Email", help="Your teilauto account email.")
@click.option(
    "--password",
    prompt="Password",
    hide_input=True,
    help="Account password (never stored — only the session token is kept).",
)
@click.pass_obj
def login(app, email: str, password: str) -> None:
    """Authenticate once; the returned token is valid for about 90 days."""
    with CantamenClient(verbose=app.verbose) as client:
        info = client.login(email, password, prov_id=app.settings.prov_id)
    tokenstore.save_token(StoredToken(id=info.id, expiry=info.expiry, customer_id=info.customer_id))
    console.print(f"[green]✓ Logged in.[/green] Token valid until {local_time(info.expiry)}.")


@auth.command()
@json_option
@click.pass_obj
def status(app, as_json: bool) -> None:
    """Show whether you are logged in and until when the token is valid."""
    token = app.token
    if as_json:
        print_json(
            {
                "logged_in": token is not None,
                "expiry": token.expiry if token else None,
                "customer_id": token.customer_id if token else None,
            }
        )
        if token is None:
            raise SystemExit(3)
        return
    if token is None:
        console.print("[yellow]Not logged in.[/yellow] Run `teilauto auth login`.")
        raise SystemExit(3)
    console.print(
        kv_panel(
            "Session",
            {
                "logged in": "yes",
                "token expiry": local_time(token.expiry),
                "customer id": token.customer_id or "—",
            },
        )
    )


@auth.command()
def logout() -> None:
    """Delete the stored session token."""
    tokenstore.delete_token()
    console.print("Logged out — token removed.")
