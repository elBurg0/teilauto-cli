from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from teilauto.api.client import BASE_URL, CantamenClient, iso_utc
from teilauto.api.errors import ApiError, AuthRequiredError, NotFoundError, RateLimitedError

START = datetime(2026, 7, 12, 10, 0, tzinfo=timezone.utc)
END = datetime(2026, 7, 12, 10, 30, tzinfo=timezone.utc)


def test_iso_utc_formats_z():
    assert iso_utc(START) == "2026-07-12T10:00:00.000Z"


def test_points_of_interest_parses_cars(respx_mock, poi_json):
    route = respx_mock.get(f"{BASE_URL}/pointsofinterest").mock(
        return_value=httpx.Response(200, json=poi_json)
    )
    with CantamenClient() as client:
        cars = client.points_of_interest(lat=51.33, lng=12.39, radius_m=500, start=START, end=END)
    assert [c.id for c in cars] == ["111", "222", "333"]
    params = route.calls.last.request.url.params
    assert params["range"] == "500"
    assert params["start"] == "2026-07-12T10:00:00.000Z"
    assert route.calls.last.request.headers["x-api-key"]


def test_booking_proposals(respx_mock, proposals_json):
    respx_mock.get(f"{BASE_URL}/bookingproposals").mock(
        return_value=httpx.Response(200, json=proposals_json)
    )
    with CantamenClient() as client:
        props = client.booking_proposals(lat=51.33, lng=12.39, radius_m=500, start=START, end=END)
    assert props[0].bookee_id == "111"


def test_token_header_sent(respx_mock, bookings_json):
    route = respx_mock.get(f"{BASE_URL}/bookings").mock(
        return_value=httpx.Response(200, json=bookings_json)
    )
    with CantamenClient(token_id="tok-abc123") as client:
        bookings = client.list_bookings()
    assert len(bookings) == 2
    auth = route.calls.last.request.headers["authorization"]
    assert auth.startswith("Basic ")  # base64("tok-abc123:")
    assert auth == "Basic dG9rLWFiYzEyMzo="


def test_create_booking_body(respx_mock, bookings_json):
    route = respx_mock.post(f"{BASE_URL}/bookings").mock(
        return_value=httpx.Response(200, json=bookings_json[0])
    )
    with CantamenClient(token_id="t") as client:
        booking = client.create_booking("111", START, END)
    assert booking.id == "b-1"
    import json as jsonlib

    body = jsonlib.loads(route.calls.last.request.content)
    assert body == {
        "bookeeId": "111",
        "timeRange": {"start": "2026-07-12T10:00:00.000Z", "end": "2026-07-12T10:30:00.000Z"},
    }


def test_login_posts_credentials(respx_mock, token_json):
    route = respx_mock.post(f"{BASE_URL}/tokens").mock(
        return_value=httpx.Response(200, json=token_json)
    )
    with CantamenClient() as client:
        info = client.login("me@example.org", "secret")
    assert info.id == "tok-abc123"
    import json as jsonlib

    body = jsonlib.loads(route.calls.last.request.content)
    assert body["login"] == "me@example.org"
    assert body["provId"] == "118"
    assert body["storeLogin"] is True


def test_price_takes_first_list_item(respx_mock, prices_json):
    respx_mock.get(f"{BASE_URL}/prices").mock(return_value=httpx.Response(200, json=prices_json))
    with CantamenClient() as client:
        price = client.price("111", START, END)
    assert price.total == 4.90


def test_401_raises_auth_required(respx_mock):
    respx_mock.get(f"{BASE_URL}/bookings").mock(return_value=httpx.Response(401))
    with CantamenClient() as client, pytest.raises(AuthRequiredError):
        client.list_bookings()


def test_404_and_429(respx_mock):
    respx_mock.get(f"{BASE_URL}/bookees/nope").mock(return_value=httpx.Response(404))
    respx_mock.get(f"{BASE_URL}/prices").mock(return_value=httpx.Response(429))
    with CantamenClient() as client:
        with pytest.raises(NotFoundError):
            client.get_car("nope")
        with pytest.raises(RateLimitedError):
            client.price("111", START, END)


def test_retries_5xx_then_succeeds(respx_mock, proposals_json):
    route = respx_mock.get(f"{BASE_URL}/bookingproposals")
    route.side_effect = [httpx.Response(500), httpx.Response(200, json=proposals_json)]
    with CantamenClient() as client:
        props = client.booking_proposals(lat=1, lng=2, radius_m=3, start=START, end=END)
    assert len(props) == 1
    assert route.call_count == 2


def test_exhausted_retries_raise_api_error(respx_mock):
    respx_mock.get(f"{BASE_URL}/bookingproposals").mock(return_value=httpx.Response(502))
    with CantamenClient(retries=1) as client, pytest.raises(ApiError, match="502"):
        client.booking_proposals(lat=1, lng=2, radius_m=3, start=START, end=END)


def test_cancel_booking_deletes(respx_mock):
    route = respx_mock.delete(f"{BASE_URL}/bookings/b-1").mock(return_value=httpx.Response(204))
    with CantamenClient(token_id="t") as client:
        client.cancel_booking("b-1")
    assert route.called
