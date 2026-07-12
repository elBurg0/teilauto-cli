from __future__ import annotations

import json

import httpx

from teilauto.api.client import BASE_URL
from teilauto.cli import cli


def test_bookings_require_auth(runner, isolated_config):
    result = runner.invoke(cli, ["bookings", "list"])
    assert result.exit_code != 0
    assert isinstance(result.exception, Exception)


def test_bookings_list_hides_past_by_default(runner, logged_in, respx_mock, bookings_json):
    respx_mock.get(f"{BASE_URL}/bookings").mock(
        return_value=httpx.Response(200, json=bookings_json)
    )
    result = runner.invoke(cli, ["bookings", "list", "--json"])
    assert result.exit_code == 0, result.output
    ids = [b["id"] for b in json.loads(result.output)]
    assert ids == ["b-1"]  # b-0 ended 2026-07-01, before "now" (2026-07-12+)


def test_bookings_list_all(runner, logged_in, respx_mock, bookings_json):
    respx_mock.get(f"{BASE_URL}/bookings").mock(
        return_value=httpx.Response(200, json=bookings_json)
    )
    result = runner.invoke(cli, ["bookings", "list", "--all", "--json"])
    assert len(json.loads(result.output)) == 2


def test_bookings_show(runner, logged_in, respx_mock, bookings_json):
    respx_mock.get(f"{BASE_URL}/bookings/b-1").mock(
        return_value=httpx.Response(200, json=bookings_json[0])
    )
    result = runner.invoke(cli, ["bookings", "show", "b-1"])
    assert result.exit_code == 0
    assert "b-1" in result.output


def test_create_prompts_and_books(
    runner, logged_in, respx_mock, poi_json, prices_json, bookings_json
):
    bookee = poi_json[0]["places"][0]["bookees"][0] | {"place": poi_json[0]["places"][0]}
    respx_mock.get(f"{BASE_URL}/bookees/111").mock(return_value=httpx.Response(200, json=bookee))
    respx_mock.get(f"{BASE_URL}/prices").mock(return_value=httpx.Response(200, json=prices_json))
    post = respx_mock.post(f"{BASE_URL}/bookings").mock(
        return_value=httpx.Response(200, json=bookings_json[0])
    )
    result = runner.invoke(cli, ["bookings", "create", "111", "--for", "1h"], input="y\n")
    assert result.exit_code == 0, result.output
    assert post.called
    assert "Booked" in result.output


def test_create_aborts_on_no(runner, logged_in, respx_mock, poi_json, prices_json):
    bookee = poi_json[0]["places"][0]["bookees"][0] | {"place": poi_json[0]["places"][0]}
    respx_mock.get(f"{BASE_URL}/bookees/111").mock(return_value=httpx.Response(200, json=bookee))
    respx_mock.get(f"{BASE_URL}/prices").mock(return_value=httpx.Response(200, json=prices_json))
    post = respx_mock.post(f"{BASE_URL}/bookings")
    result = runner.invoke(cli, ["bookings", "create", "111", "--for", "1h"], input="n\n")
    assert result.exit_code != 0
    assert not post.called


def test_cancel_with_yes(runner, logged_in, respx_mock):
    route = respx_mock.delete(f"{BASE_URL}/bookings/b-1").mock(return_value=httpx.Response(204))
    result = runner.invoke(cli, ["bookings", "cancel", "b-1", "--yes"])
    assert result.exit_code == 0, result.output
    assert route.called
    assert "cancelled" in result.output.lower()
