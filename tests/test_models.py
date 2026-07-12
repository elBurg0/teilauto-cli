from __future__ import annotations

from teilauto.api.errors import (
    ApiError,
    AuthRequiredError,
    NoMatchError,
    NotFoundError,
    TeilautoError,
)
from teilauto.api.models import (
    Booking,
    Car,
    Price,
    Proposal,
    TokenInfo,
    Unavailability,
    cars_from_poi,
)


def test_error_exit_codes_and_hint():
    assert TeilautoError("x").exit_code == 1
    assert ApiError("x").exit_code == 1
    err = AuthRequiredError()
    assert err.exit_code == 3
    assert "teilauto auth login" in (err.hint or "")
    assert NotFoundError("x").exit_code == 4
    assert NoMatchError("x").exit_code == 2


def test_cars_from_poi(poi_json):
    cars = cars_from_poi(poi_json)
    assert [c.id for c in cars] == ["111", "222", "333"]
    polo = cars[0]
    assert polo == Car(
        id="111", name="VW Polo", plate="L-TA 1111", fuel=80,
        car_type="cityFlitzer", lat=51.339, lng=12.392, address="Dresdner Str. 6",
    )


def test_proposal_from_api(proposals_json):
    p = Proposal.from_api(proposals_json[0])
    assert p.bookee_id == "111"
    assert p.free_from == "2026-07-12T10:00:00.000Z"


def test_price_sums_gross_items(prices_json):
    price = Price.from_api(prices_json[0])
    assert price.total == 4.90
    assert price.currency == "EUR"


def test_price_unknown_shape_gives_none():
    price = Price.from_api({"something": "else"})
    assert price.total is None
    assert price.raw == {"something": "else"}


def test_booking_from_api(bookings_json):
    b = Booking.from_api(bookings_json[0])
    assert (b.id, b.bookee_id, b.state) == ("b-1", "111", "CONFIRMED")
    assert b.start == "2099-01-01T10:00:00.000Z"


def test_unavailability_from_api(unavailabilities_json):
    u = Unavailability.from_api(unavailabilities_json[0])
    assert u.start == "2026-07-12T18:00:00.000Z"


def test_token_info(token_json):
    t = TokenInfo.from_api(token_json)
    assert (t.id, t.customer_id) == ("tok-abc123", "cust-9")
    assert t.expiry == "2026-10-10T00:00:00.000Z"


def test_cars_from_poi_dedupes_by_id(poi_json):
    doubled = poi_json + poi_json  # same cars appear in two POI points
    cars = cars_from_poi(doubled)
    assert [c.id for c in cars] == ["111", "222", "333"]


def test_price_falls_back_to_top_level_gross():
    price = Price.from_api({"gross": {"amount": 250, "currency": "EUR"}})
    assert price.total == 2.50
    assert price.currency == "EUR"
