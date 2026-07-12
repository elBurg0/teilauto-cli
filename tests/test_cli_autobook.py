from __future__ import annotations

import json
from datetime import datetime, timedelta

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
    deadline = (datetime.now().astimezone() + timedelta(seconds=2)).isoformat()
    result = runner.invoke(
        cli,
        ["autobook", "--for", "1h", "--yes", "--max-price", "2.00", "--deadline", deadline],
    )
    assert not post.called
    assert result.exception is not None  # NoMatchError via runner
    price_calls = [c for c in respx_mock.calls if c.request.url.path.endswith("/prices")]
    assert price_calls  # the candidate loop actually executed


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


def test_autobook_until_in_past_exits_2(runner, logged_in, monkeypatch,
                                        respx_mock, poi_json, proposals_json):
    monkeypatch.setattr("teilauto.cli.autobook.time.sleep", lambda s: None)
    _mock_search(respx_mock, poi_json, proposals_json)
    result = runner.invoke(cli, ["autobook", "--until", "2020-01-01T10:00:00", "--yes"])
    assert result.exception is not None  # NoMatchError (exit 2 via main)
    post = [c for c in respx_mock.calls if c.request.method == "POST"]
    assert not post


def test_autobook_max_price_fails_closed_on_price_error(runner, logged_in, monkeypatch,
                                                        respx_mock, poi_json, proposals_json):
    monkeypatch.setattr("teilauto.cli.autobook.time.sleep", lambda s: None)
    _mock_search(respx_mock, poi_json, proposals_json)
    respx_mock.get(f"{BASE_URL}/prices").mock(return_value=httpx.Response(500))
    post = respx_mock.post(f"{BASE_URL}/bookings")
    deadline = (datetime.now().astimezone() + timedelta(seconds=2)).isoformat()
    result = runner.invoke(
        cli, ["autobook", "--for", "1h", "--yes", "--max-price", "10", "--deadline", deadline]
    )
    assert not post.called
    assert result.exception is not None  # deadline give-up, exit 2
    price_calls = [c for c in respx_mock.calls if c.request.url.path.endswith("/prices")]
    assert price_calls  # the candidate loop actually executed


def test_autobook_gives_up_on_permanently_failing_car(runner, logged_in, monkeypatch,
                                                      respx_mock, poi_json, proposals_json,
                                                      prices_json):
    monkeypatch.setattr("teilauto.cli.autobook.time.sleep", lambda s: None)
    _mock_search(respx_mock, poi_json, proposals_json)
    respx_mock.get(f"{BASE_URL}/prices").mock(return_value=httpx.Response(200, json=prices_json))
    post = respx_mock.post(f"{BASE_URL}/bookings").mock(
        return_value=httpx.Response(400, json={"message": "nope"})
    )
    deadline = (datetime.now().astimezone() + timedelta(seconds=2)).isoformat()
    result = runner.invoke(
        cli, ["autobook", "--for", "1h", "--yes", "--deadline", deadline]
    )
    # a permanently failing car is attempted at most 3 times, then dropped
    assert post.call_count == 3
    assert result.exception is not None


def test_autobook_json_requires_yes(runner, logged_in):
    result = runner.invoke(cli, ["autobook", "--for", "1h", "--json"])
    assert result.exit_code == 2
    assert "--yes" in result.stderr
