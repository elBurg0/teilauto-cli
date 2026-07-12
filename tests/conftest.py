from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def poi_json():
    return load_fixture("pointsofinterest.json")


@pytest.fixture
def proposals_json():
    return load_fixture("bookingproposals.json")


@pytest.fixture
def prices_json():
    return load_fixture("prices.json")


@pytest.fixture
def bookings_json():
    return load_fixture("bookings.json")


@pytest.fixture
def token_json():
    return load_fixture("token.json")


@pytest.fixture
def unavailabilities_json():
    return load_fixture("unavailabilities.json")
