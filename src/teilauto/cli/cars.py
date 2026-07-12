from __future__ import annotations

import rich_click as click

from teilauto.api.models import CITYFLITZER_TYPE
from teilauto.cli.options import (
    json_option,
    location_options,
    resolve_location,
    resolve_window,
    window_options,
)
from teilauto.output.json_out import print_json
from teilauto.output.render import car_detail, cars_table, console, unavailability_table
from teilauto.services.availability import find_cars


@click.group()
def cars() -> None:
    """Find cars near you and inspect their availability."""


@cars.command("list")
@location_options
@window_options
@click.option("--type", "car_type", type=click.Choice(["cityflitzer", "all"]),
              default="cityflitzer", show_default=True, help="Car type filter.")
@click.option("--available", "only_available", is_flag=True,
              help="Show only cars bookable in the window.")
@click.option("--min-fuel", type=float, default=None, metavar="PERCENT",
              help="Hide cars below this fuel level (default: config).")
@json_option
@click.pass_obj
def list_cars(app, lat, lng, radius_m, start_text, duration_text, until_text,
              car_type, only_available, min_fuel, as_json) -> None:
    """List cars near a location, closest first."""
    settings = app.settings
    lat, lng, radius_m = resolve_location(settings, lat, lng, radius_m)
    start, end = resolve_window(
        start_text, duration_text, until_text, default_minutes=settings.window_min
    )
    with app.client() as client:
        items = find_cars(
            client,
            lat=lat, lng=lng, radius_m=radius_m, start=start, end=end,
            car_type=None if car_type == "all" else CITYFLITZER_TYPE,
            min_fuel=settings.min_fuel if min_fuel is None else min_fuel,
            only_available=only_available,
        )
    if as_json:
        print_json(items)
        return
    if not items:
        console.print("No cars found — try a bigger --radius or --type all.")
        return
    console.print(cars_table(items))


@cars.command("show")
@click.argument("car_id")
@window_options
@json_option
@click.pass_obj
def show_car(app, car_id, start_text, duration_text, until_text, as_json) -> None:
    """Show one car in detail, including when it is blocked (next 24h by default)."""
    start, end = resolve_window(start_text, duration_text, until_text, default_minutes=1440)
    with app.client() as client:
        car = client.get_car(car_id)
        blocked = client.unavailabilities(car_id, start, end)
    if as_json:
        print_json({"car": car, "unavailabilities": blocked})
        return
    console.print(car_detail(car))
    if blocked:
        console.print(unavailability_table(blocked))
    else:
        console.print("[green]No blocked time ranges in the window.[/green]")
