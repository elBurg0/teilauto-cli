from __future__ import annotations

from dataclasses import dataclass, field

CITYFLITZER_TYPE = "cityFlitzer"


@dataclass(frozen=True)
class Car:
    id: str
    name: str
    plate: str | None
    fuel: float | None
    car_type: str | None
    lat: float | None
    lng: float | None
    address: str | None

    @classmethod
    def from_bookee(cls, bookee: dict, place: dict | None = None) -> Car:
        place = place or bookee.get("place") or {}
        coord = place.get("geoCoordinate") or {}
        return cls(
            id=str(bookee["id"]),
            name=bookee.get("displayName") or bookee.get("name") or "?",
            plate=bookee.get("licenseNumber"),
            fuel=bookee.get("fuelLevel"),
            car_type=(bookee.get("bookeeType") or {}).get("name"),
            lat=coord.get("latitude"),
            lng=coord.get("longitude"),
            address=place.get("name"),
        )


def cars_from_poi(poi: list[dict]) -> list[Car]:
    """Flatten a /pointsofinterest response into cars, deduplicated by id."""
    seen: dict[str, Car] = {}
    for point in poi:
        for place in point.get("places", []):
            for bookee in place.get("bookees", []):
                car = Car.from_bookee(bookee, place)
                seen.setdefault(car.id, car)
    return list(seen.values())


@dataclass(frozen=True)
class Proposal:
    bookee_id: str
    free_from: str | None

    @classmethod
    def from_api(cls, data: dict) -> Proposal:
        return cls(
            bookee_id=str(data.get("bookeeId")),
            free_from=(data.get("timeRange") or {}).get("start"),
        )


@dataclass(frozen=True)
class Price:
    total: float | None
    currency: str | None
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict) -> Price:
        total_cents = 0
        currency: str | None = None
        found = False
        for item in data.get("priceItems") or []:
            gross = item.get("gross") or {}
            if "amount" in gross:
                total_cents += gross["amount"]
                currency = gross.get("currency") or currency
                found = True
        if not found:
            gross = data.get("gross") or {}
            if "amount" in gross:
                total_cents = gross["amount"]
                currency = gross.get("currency")
                found = True
        return cls(total=total_cents / 100 if found else None, currency=currency, raw=data)


@dataclass(frozen=True)
class Booking:
    id: str
    bookee_id: str | None
    start: str | None
    end: str | None
    state: str | None
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict) -> Booking:
        time_range = data.get("timeRange") or {}
        bookee_id = data.get("bookeeId")
        return cls(
            id=str(data.get("id")),
            bookee_id=str(bookee_id) if bookee_id is not None else None,
            start=time_range.get("start"),
            end=time_range.get("end"),
            state=data.get("state") or data.get("bookingState"),
            raw=data,
        )


@dataclass(frozen=True)
class Unavailability:
    start: str | None
    end: str | None

    @classmethod
    def from_api(cls, data: dict) -> Unavailability:
        time_range = data.get("timeRange") or data
        return cls(start=time_range.get("start"), end=time_range.get("end"))


@dataclass(frozen=True)
class TokenInfo:
    id: str
    expiry: str | None
    customer_id: str | None

    @classmethod
    def from_api(cls, data: dict) -> TokenInfo:
        customer = data.get("customerId")
        return cls(
            id=str(data["id"]),
            expiry=data.get("expiry"),
            customer_id=str(customer) if customer is not None else None,
        )
