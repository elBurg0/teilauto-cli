from __future__ import annotations

import rich_click as click

from teilauto.api.client import iso_utc
from teilauto.cli.options import json_option, resolve_window, window_options
from teilauto.output.json_out import print_json
from teilauto.output.render import console, kv_panel


@click.command()
@click.argument("car_id")
@window_options
@json_option
@click.pass_obj
def price(app, car_id, start_text, duration_text, until_text, as_json) -> None:
    """Show the price of booking CAR_ID for a time window."""
    start, end = resolve_window(
        start_text, duration_text, until_text, default_minutes=app.settings.window_min
    )
    with app.client() as client:
        result = client.price(car_id, start, end)
    if as_json:
        print_json(
            {
                "car_id": car_id,
                "start": iso_utc(start),
                "end": iso_utc(end),
                "total": result.total,
                "currency": result.currency,
            }
        )
        return
    total = f"{result.total:.2f} {result.currency}" if result.total is not None else "unknown"
    console.print(
        kv_panel(
            f"Price for car {car_id}",
            {
                "from": start.strftime("%Y-%m-%d %H:%M"),
                "until": end.strftime("%Y-%m-%d %H:%M"),
                "total": total,
            },
        )
    )
    if result.total is None and app.token is None:
        console.print(
            "[dim]Price data may require a login — run `teilauto auth login` and retry.[/dim]"
        )
