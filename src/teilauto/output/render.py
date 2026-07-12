from __future__ import annotations

from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from teilauto.api.models import Booking, Car, Unavailability
from teilauto.services.availability import CarAvailability

console = Console()
err_console = Console(stderr=True)


def fuel_text(fuel: float | None) -> Text:
    if fuel is None:
        return Text("?", style="dim")
    style = "green" if fuel >= 50 else "yellow" if fuel >= 25 else "red"
    return Text(f"{fuel:.0f}%", style=style)


def local_time(iso: str | None) -> str:
    """Render an API ISO/Z timestamp as local '%Y-%m-%d %H:%M'."""
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return "—"
    return dt.astimezone().strftime("%Y-%m-%d %H:%M")


def kv_panel(title: str, mapping: dict[str, object]) -> Panel:
    body = Text()
    width = max((len(key) for key in mapping), default=0)
    for key, value in mapping.items():
        body.append(f"{key.rjust(width)}  ", style="bold dim")
        body.append(f"{value}\n")
    return Panel(body, title=title, expand=False)


def cars_table(items: list[CarAvailability]) -> Table:
    table = Table(title="Cars", header_style="bold")
    for column in ("ID", "Name", "Plate", "Fuel", "Distance", "Address", "Available"):
        table.add_column(column)
    for ca in items:
        available = Text("✓ now", style="green") if ca.available else Text("✗", style="dim")
        table.add_row(
            ca.car.id,
            ca.car.name,
            ca.car.plate or "—",
            fuel_text(ca.car.fuel),
            f"{ca.distance_m} m" if ca.distance_m is not None else "—",
            ca.car.address or "—",
            available,
        )
    return table


def car_detail(car: Car) -> Panel:
    return kv_panel(
        f"{car.name} ({car.id})",
        {
            "plate": car.plate or "—",
            "type": car.car_type or "—",
            "fuel": f"{car.fuel:.0f}%" if car.fuel is not None else "—",
            "address": car.address or "—",
            "position": (
                f"{car.lat}, {car.lng}" if car.lat is not None and car.lng is not None else "—"
            ),
        },
    )


def unavailability_table(items: list[Unavailability]) -> Table:
    table = Table(title="Blocked time ranges", header_style="bold")
    table.add_column("From")
    table.add_column("Until")
    for item in items:
        table.add_row(local_time(item.start), local_time(item.end))
    return table


def bookings_table(bookings: list[Booking]) -> Table:
    table = Table(title="Bookings", header_style="bold")
    for column in ("ID", "Car", "From", "Until", "State"):
        table.add_column(column)
    for booking in bookings:
        table.add_row(
            booking.id,
            booking.bookee_id or "—",
            local_time(booking.start),
            local_time(booking.end),
            booking.state or "—",
        )
    return table
