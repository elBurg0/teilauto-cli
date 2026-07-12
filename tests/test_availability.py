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
    assert items[0].distance_m <= (items[1].distance_m or 10**9)


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


def _poi(places):
    return [{"id": "poi-x", "places": places}]


def _place(place_id, name, lat, lng, bookees):
    place = {"id": place_id, "name": name, "bookees": bookees}
    if lat is not None:
        place["geoCoordinate"] = {"latitude": lat, "longitude": lng}
    return place


def _bookee(car_id, fuel=80):
    return {
        "id": car_id,
        "displayName": f"Car {car_id}",
        "licenseNumber": f"L-{car_id}",
        "fuelLevel": fuel,
        "bookeeType": {"name": "cityFlitzer"},
    }


def test_sorted_closest_first_and_no_coords_last(respx_mock):
    poi = _poi(
        [
            _place("p-far", "Far", 51.3420, 12.3960, [_bookee("far")]),
            _place("p-near", "Near", 51.3386, 12.3917, [_bookee("near")]),
            _place("p-nowhere", "Nowhere", None, None, [_bookee("nowhere")]),
        ]
    )
    respx_mock.get(f"{BASE_URL}/pointsofinterest").mock(return_value=httpx.Response(200, json=poi))
    respx_mock.get(f"{BASE_URL}/bookingproposals").mock(return_value=httpx.Response(200, json=[]))
    with CantamenClient() as client:
        items = find_cars(client, start=START, end=END, **HOME)
    assert [ca.car.id for ca in items] == ["near", "far", "nowhere"]
    assert items[2].distance_m is None  # coordless cars are kept and sorted last


def test_radius_drops_distant_car(respx_mock):
    poi = _poi([_place("p-out", "Out of range", 51.36, 12.42, [_bookee("out")])])  # ~3km away
    respx_mock.get(f"{BASE_URL}/pointsofinterest").mock(return_value=httpx.Response(200, json=poi))
    respx_mock.get(f"{BASE_URL}/bookingproposals").mock(return_value=httpx.Response(200, json=[]))
    with CantamenClient() as client:
        items = find_cars(client, start=START, end=END, **HOME)
    assert items == []


def test_unknown_fuel_counts_as_zero(respx_mock):
    poi = _poi([_place("p1", "Somewhere", 51.3386, 12.3917, [_bookee("nofuel", fuel=None)])])
    respx_mock.get(f"{BASE_URL}/pointsofinterest").mock(return_value=httpx.Response(200, json=poi))
    respx_mock.get(f"{BASE_URL}/bookingproposals").mock(return_value=httpx.Response(200, json=[]))
    with CantamenClient() as client:
        assert find_cars(client, start=START, end=END, min_fuel=10, **HOME) == []
        assert len(find_cars(client, start=START, end=END, min_fuel=0, **HOME)) == 1
