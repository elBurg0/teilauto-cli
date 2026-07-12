from __future__ import annotations

import httpx
import pytest

from teilauto.api.client import BASE_URL
from teilauto.cli import cli


class StopLoop(Exception):
    """Raised by the fake sleeper to end the infinite watch loop in tests.

    (Not KeyboardInterrupt: CliRunner only catches Exception subclasses.)
    """


@pytest.fixture
def one_cycle(monkeypatch):
    """Let the watch loop run exactly one poll, then stop it."""

    def fake_sleep(seconds):
        raise StopLoop

    monkeypatch.setattr("teilauto.cli.watch.time.sleep", fake_sleep)


def _mock_search(respx_mock, poi_json, proposals_json):
    respx_mock.get(f"{BASE_URL}/pointsofinterest").mock(
        return_value=httpx.Response(200, json=poi_json)
    )
    respx_mock.get(f"{BASE_URL}/bookingproposals").mock(
        return_value=httpx.Response(200, json=proposals_json)
    )


def test_watch_prints_status_and_new_car(runner, isolated_config, respx_mock,
                                         poi_json, proposals_json, one_cycle):
    _mock_search(respx_mock, poi_json, proposals_json)
    result = runner.invoke(cli, ["watch"])
    assert isinstance(result.exception, StopLoop)
    # click >= 8.2: result.output is stdout only; warnings go to result.stderr
    assert "bookable" in result.output
    assert "VW Polo" in result.output
    assert "no notification channels" in result.stderr.lower()


def test_watch_notifies_via_ntfy(runner, isolated_config, respx_mock, monkeypatch,
                                 poi_json, proposals_json, one_cycle):
    monkeypatch.setenv("TEILAUTO_NOTIFY_CHANNELS", "ntfy")
    monkeypatch.setenv("TEILAUTO_NOTIFY_NTFY_TOPIC", "t")
    _mock_search(respx_mock, poi_json, proposals_json)
    ntfy_route = respx_mock.post("https://ntfy.sh/t").mock(return_value=httpx.Response(200))
    result = runner.invoke(cli, ["watch"])
    assert isinstance(result.exception, StopLoop)
    # startup message + one new car
    assert ntfy_route.call_count == 2


def test_watch_reports_failing_startup_notification(runner, isolated_config, respx_mock,
                                                    monkeypatch, poi_json, proposals_json,
                                                    one_cycle):
    monkeypatch.setenv("TEILAUTO_NOTIFY_CHANNELS", "ntfy")
    monkeypatch.setenv("TEILAUTO_NOTIFY_NTFY_TOPIC", "t")
    _mock_search(respx_mock, poi_json, proposals_json)
    respx_mock.post("https://ntfy.sh/t").mock(return_value=httpx.Response(500))
    result = runner.invoke(cli, ["watch"])
    assert isinstance(result.exception, StopLoop)
    assert "notify failed" in result.stderr
