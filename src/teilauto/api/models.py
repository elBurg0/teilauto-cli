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
        # the live API sends priceIncl/code; gross/currency is the legacy shape
        def amount_of(container: dict) -> tuple[int, str | None] | None:
            for gross in (container.get("priceIncl"), container.get("gross")):
                if gross and "amount" in gross:
                    return gross["amount"], gross.get("code") or gross.get("currency")
            return None

        total_cents = 0
        currency: str | None = None
        found = False
        for item in data.get("priceItems") or []:
            parsed = amount_of(item)
            if parsed:
                total_cents += parsed[0]
                currency = parsed[1] or currency
                found = True
        if not found:
            parsed = amount_of(data)
            if parsed:
                total_cents, currency = parsed
                found = True
        return cls(total=total_cents / 100 if found else None, currency=currency, raw=data)


@dataclass(frozen=True)
class Booking:
    id: str
    bookee_id: str | None
    start: str | None
    end: str | None
    state: str | None
    car_name: str | None = None
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict) -> Booking:
        time_range = data.get("timeRange") or {}
        bookee = data.get("bookee") or {}
        # bookee.id is a per-booking virtual id ("B118_…"), not the car id
        bookee_id = data.get("bookeeId") or bookee.get("actualBookeeId")
        name = bookee.get("name")
        plate = bookee.get("displayName") or bookee.get("licenseNumber")
        car_name = f"{name} ({plate})" if name and plate else name or plate
        state = data.get("state") or data.get("bookingState")
        if not state and data.get("cancelled"):
            state = "CANCELLED"
        return cls(
            id=str(data.get("id")),
            bookee_id=str(bookee_id) if bookee_id is not None else None,
            start=time_range.get("start"),
            end=time_range.get("end"),
            state=state or data.get("billingState"),
            car_name=car_name,
            raw=data,
        )

    @property
    def car_label(self) -> str:
        if self.car_name and self.bookee_id:
            return f"{self.car_name} [{self.bookee_id}]"
        return self.car_name or self.bookee_id or "—"


@dataclass(frozen=True)
class Unavailability:
    start: str | None
    end: str | None

    @classmethod
    def from_api(cls, data: dict) -> Unavailability:
        time_range = data.get("timeRange") or data
        return cls(start=time_range.get("start"), end=time_range.get("end"))


def unavailabilities_from_api(data: list[dict]) -> list[Unavailability]:
    items: list[Unavailability] = []
    for entry in data:
        nested = entry.get("unavailabilityTimeRanges")
        if nested is None:
            items.append(Unavailability.from_api(entry))
        else:
            items.extend(Unavailability.from_api(r) for r in nested)
    return items


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
