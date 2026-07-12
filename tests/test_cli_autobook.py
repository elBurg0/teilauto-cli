from __future__ import annotations

import json

import httpx

from teilauto.api.client import BASE_URL
from teilauto.cli import cli


def _mock_search(respx_mock, poi_json, proposals_json):
    respx_mock.get(f"{BASE_URL}/pointsofinterest").mock(
        return_value=httpx.Response(200, json=poi_json)
    )
    respx_mock.get(f"{BASE_URL}/bookingproposals").mock(
        return_value=httpx.Response(200, json=proposals_json)
    )


def test_autobook_requires_duration(runner, logged_in):
    result = runner.invoke(cli, ["autobook", "--yes"])
    assert result.exit_code == 2
    # click >= 8.2: usage errors are printed to stderr
    assert "--for" in result.stderr


def test_autobook_requires_login(runner, isolated_config):
    result = runner.invoke(cli, ["autobook", "--for", "1h", "--yes"])
    assert result.exception is not None


def test_autobook_books_first_match(runner, logged_in, respx_mock,
                                    poi_json, proposals_json, prices_json, bookings_json):
    _mock_search(respx_mock, poi_json, proposals_json)
    respx_mock.get(f"{BASE_URL}/prices").mock(return_value=httpx.Response(200, json=prices_json))
    post = respx_mock.post(f"{BASE_URL}/bookings").mock(
        return_value=httpx.Response(200, json=bookings_json[0])
    )
    result = runner.invoke(cli, ["autobook", "--for", "1h", "--yes", "--json"])
    assert result.exit_code == 0, result.output
    assert post.called
    data = json.loads(result.output)
    assert data["status"] == "booked"
    assert data["booking"]["id"] == "b-1"
    assert data["car"]["id"] == "111"


def test_autobook_dry_run_does_not_post(runner, logged_in, respx_mock,
                                        poi_json, proposals_json, prices_json):
    _mock_search(respx_mock, poi_json, proposals_json)
    respx_mock.get(f"{BASE_URL}/prices").mock(return_value=httpx.Response(200, json=prices_json))
    post = respx_mock.post(f"{BASE_URL}/bookings")
    result = runner.invoke(cli, ["autobook", "--for", "1h", "--yes", "--dry-run", "--json"])
    assert result.exit_code == 0, result.output
    assert not post.called
    assert json.loads(result.output)["status"] == "dry_run"


def test_autobook_respects_max_price(runner, logged_in, respx_mock, monkeypatch,
                                     poi_json, proposals_json, prices_json):
    # stop after the first cycle: candidate too expensive, then deadline passes
    monkeypatch.setattr("teilauto.cli.autobook.time.sleep", lambda s: None)
    _mock_search(respx_mock, poi_json, proposals_json)
    respx_mock.get(f"{BASE_URL}/prices").mock(return_value=httpx.Response(200, json=prices_json))
    post = respx_mock.post(f"{BASE_URL}/bookings")
    result = runner.invoke(
        cli,
        ["autobook", "--for", "1h", "--yes", "--max-price", "2.00", "--deadline", "now"],
    )
    assert not post.called
    assert result.exception is not None  # NoMatchError via runner


def test_autobook_keeps_polling_when_booking_races(runner, logged_in, respx_mock, monkeypatch,
                                                   poi_json, proposals_json, prices_json,
                                                   bookings_json):
    monkeypatch.setattr("teilauto.cli.autobook.time.sleep", lambda s: None)
    _mock_search(respx_mock, poi_json, proposals_json)
    respx_mock.get(f"{BASE_URL}/prices").mock(return_value=httpx.Response(200, json=prices_json))
    post = respx_mock.post(f"{BASE_URL}/bookings")
    post.side_effect = [
        httpx.Response(409, json={"message": "already booked"}),
        httpx.Response(200, json=bookings_json[0]),
    ]
    result = runner.invoke(cli, ["autobook", "--for", "1h", "--yes"])
    assert result.exit_code == 0, result.output
    assert post.call_count == 2
    assert "Booked" in result.output
