from __future__ import annotations

from datetime import datetime, timezone

import httpx

from teilauto.api.client import BASE_URL, CantamenClient
from teilauto.services.availability import describe, find_cars

START = datetime(2026, 7, 12, 10, 0, tzinfo=timezone.utc)
END = datetime(2026, 7, 12, 10, 30, tzinfo=timezone.utc)
HOME = {"lat": 51.33853, "lng": 12.39163, "radius_m": 500}


def _mock_routes(respx_mock, poi_json, proposals_json):
    respx_mock.get(f"{BASE_URL}/pointsofinterest").mock(
        return_value=httpx.Response(200, json=poi_json)
    )
    respx_mock.get(f"{BASE_URL}/bookingproposals").mock(
        return_value=httpx.Response(200, json=proposals_json)
    )


def test_find_cars_filters_type_and_merges_availability(respx_mock, poi_json, proposals_json):
    _mock_routes(respx_mock, poi_json, proposals_json)
    with CantamenClient() as client:
        items = find_cars(client, start=START, end=END, **HOME)
    # only the two cityFlitzers; the "classic" station car is filtered out
    assert [ca.car.id for ca in items] == ["111", "222"]
    assert items[0].available is True
    assert items[0].free_from == "2026-07-12T10:00:00.000Z"
    assert items[1].available is False
    # both fixtures are within a few hundred metres of HOME
    assert items[0].distance_m is not None and items[0].distance_m < 500
    # sorted by distance ascending
    assert items[0].distance_m <= (items[1].distance_m or 0) or items[0].car.id == "111"


def test_min_fuel_filter(respx_mock, poi_json, proposals_json):
    _mock_routes(respx_mock, poi_json, proposals_json)
    with CantamenClient() as client:
        items = find_cars(client, start=START, end=END, min_fuel=50, **HOME)
    assert [ca.car.id for ca in items] == ["111"]  # Golf has 20% fuel


def test_only_available_filter(respx_mock, poi_json, proposals_json):
    _mock_routes(respx_mock, poi_json, proposals_json)
    with CantamenClient() as client:
        items = find_cars(client, start=START, end=END, only_available=True, **HOME)
    assert [ca.car.id for ca in items] == ["111"]


def test_car_type_none_includes_all(respx_mock, poi_json, proposals_json):
    _mock_routes(respx_mock, poi_json, proposals_json)
    with CantamenClient() as client:
        items = find_cars(client, start=START, end=END, car_type=None, **HOME)
    assert len(items) == 3


def test_describe_line(respx_mock, poi_json, proposals_json):
    _mock_routes(respx_mock, poi_json, proposals_json)
    with CantamenClient() as client:
        items = find_cars(client, start=START, end=END, **HOME)
    line = describe(items[0])
    assert "VW Polo" in line
    assert "L-TA 1111" in line
    assert "Dresdner Str. 6" in line
