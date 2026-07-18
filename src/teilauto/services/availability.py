from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from teilauto.api.client import CantamenClient
from teilauto.api.models import CITYFLITZER_TYPE, Car
from teilauto.core.geo import haversine_m


@dataclass(frozen=True)
class CarAvailability:
    car: Car
    distance_m: int | None
    available: bool
    free_from: str | None


def find_cars(
    client: CantamenClient,
    *,
    lat: float,
    lng: float,
    radius_m: int,
    start: datetime,
    end: datetime,
    car_type: str | None = CITYFLITZER_TYPE,
    min_fuel: float = 0.0,
    only_available: bool = False,
) -> list[CarAvailability]:
    """Merge car metadata (POI) with the bookability oracle (proposals).

    The API's own distance field is unreliable; distances are recomputed via
    haversine and cars outside radius_m are dropped. Cars without coordinates
    are kept (distance unknown, sorted last); cars with unknown fuel are treated as 0%.
    """
    cars = client.points_of_interest(lat=lat, lng=lng, radius_m=radius_m, start=start, end=end)
    free_from_by_id = {
        p.bookee_id: p.free_from
        for p in client.booking_proposals(lat=lat, lng=lng, radius_m=radius_m, start=start, end=end)
    }
    items: list[CarAvailability] = []
    for car in cars:
        # the API has spelled the type both "cityFlitzer" and "cityflitzer"
        if car_type is not None and (car.car_type or "").casefold() != car_type.casefold():
            continue
        if (car.fuel or 0) < min_fuel:
            continue
        distance = None
        if car.lat is not None and car.lng is not None:
            distance = round(haversine_m(lat, lng, car.lat, car.lng))
            if distance > radius_m:
                continue
        available = car.id in free_from_by_id
        if only_available and not available:
            continue
        items.append(
            CarAvailability(
                car=car,
                distance_m=distance,
                available=available,
                free_from=free_from_by_id.get(car.id),
            )
        )
    items.sort(key=lambda ca: (ca.distance_m is None, ca.distance_m or 0))
    return items


def describe(ca: CarAvailability) -> str:
    """One-line plain-text car summary for notifications and logs."""
    car = ca.car
    bits = [f"{car.name} ({car.plate})" if car.plate else car.name]
    if ca.distance_m is not None:
        bits.append(f"{ca.distance_m}m away")
    if car.fuel is not None:
        bits.append(f"fuel {car.fuel:.0f}%")
    line = ", ".join(bits)
    if car.address:
        line += f" @ {car.address}"
    return line
