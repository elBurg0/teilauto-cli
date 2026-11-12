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


def test_cars_list_table(runner, isolated_config, respx_mock, poi_json, proposals_json):
    _mock_search(respx_mock, poi_json, proposals_json)
    result = runner.invoke(cli, ["cars", "list"])
    assert result.exit_code == 0, result.output
    assert "VW Polo" in result.output
    assert "L-TA 1111" in result.output
    assert "Kombi" not in result.output  # station car filtered by default type


def test_cars_list_json(runner, isolated_config, respx_mock, poi_json, proposals_json):
    _mock_search(respx_mock, poi_json, proposals_json)
    result = runner.invoke(cli, ["cars", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data[0]["car"]["id"] == "111"
    assert data[0]["available"] is True


def test_cars_list_type_all(runner, isolated_config, respx_mock, poi_json, proposals_json):
    _mock_search(respx_mock, poi_json, proposals_json)
    result = runner.invoke(cli, ["cars", "list", "--type", "all", "--json"])
    assert len(json.loads(result.output)) == 3


def test_cars_list_empty_message(runner, isolated_config, respx_mock):
    respx_mock.get(f"{BASE_URL}/pointsofinterest").mock(return_value=httpx.Response(200, json=[]))
    respx_mock.get(f"{BASE_URL}/bookingproposals").mock(return_value=httpx.Response(200, json=[]))
    result = runner.invoke(cli, ["cars", "list"])
    assert result.exit_code == 0
    assert "No cars" in result.output


def test_cars_show(runner, isolated_config, respx_mock, poi_json, unavailabilities_json):
    bookee = poi_json[0]["places"][0]["bookees"][0] | {"place": poi_json[0]["places"][0]}
    respx_mock.get(f"{BASE_URL}/bookees/111").mock(return_value=httpx.Response(200, json=bookee))
    respx_mock.get(f"{BASE_URL}/unavailabilities").mock(
        return_value=httpx.Response(200, json=unavailabilities_json)
    )
    result = runner.invoke(cli, ["cars", "show", "111"])
    assert result.exit_code == 0
    assert "VW Polo" in result.output
    assert "Blocked time ranges" in result.output
    assert "2026-07-13" in result.output


def test_price_json(runner, isolated_config, respx_mock, prices_json):
    respx_mock.get(f"{BASE_URL}/prices").mock(return_value=httpx.Response(200, json=prices_json))
    result = runner.invoke(cli, ["price", "111", "--for", "1h", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["total"] == 4.9
    assert data["currency"] == "EUR"
    assert data["car_id"] == "111"


def test_price_unknown_hints_login(runner, isolated_config, respx_mock):
    respx_mock.get(f"{BASE_URL}/prices").mock(return_value=httpx.Response(200, json=[]))
    result = runner.invoke(cli, ["price", "111", "--for", "30m"])
    assert result.exit_code == 0
    assert "unknown" in result.output
    assert "auth login" in result.output
