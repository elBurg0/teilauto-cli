from __future__ import annotations

import base64
import sys
from datetime import datetime, timezone
from typing import Any

import httpx

from teilauto.api.errors import ApiError, AuthRequiredError, NotFoundError, RateLimitedError
from teilauto.api.models import (
    Booking,
    Car,
    Price,
    Proposal,
    TokenInfo,
    Unavailability,
    cars_from_poi,
)

# Public app key baked into the buchen.teilauto.net frontend JS.
# It identifies the app (not a user) and only unlocks read-only data.
API_KEY = "6b4d4759-8fd1-b25a-c099-09c2af9c70ce"
BASE_URL = "https://de1.cantamen.de/casirest/v3"
PROV_ID = "118"  # teilauto/CityFlitzer Mitteldeutschland


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


class CantamenClient:
    """Thin typed client for the Cantamen casirest/v3 API."""

    def __init__(
        self,
        *,
        token_id: str | None = None,
        base_url: str = BASE_URL,
        api_key: str = API_KEY,
        timeout: float = 20.0,
        verbose: bool = False,
        retries: int = 2,
    ) -> None:
        headers = {"x-api-key": api_key, "Accept": "application/json"}
        if token_id:
            encoded = base64.b64encode(f"{token_id}:".encode()).decode()
            headers["authorization"] = f"Basic {encoded}"
        self._http = httpx.Client(base_url=base_url, headers=headers, timeout=timeout)
        self._verbose = verbose
        self._retries = retries

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> CantamenClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _request(
        self, method: str, path: str, *, params: dict | None = None, json: dict | None = None
    ) -> Any:
        last_error: str = "no attempts made"
        for _attempt in range(self._retries + 1):
            try:
                resp = self._http.request(method, path, params=params, json=json)
            except httpx.TransportError as exc:
                last_error = f"network error: {exc}"
                continue
            if self._verbose:
                print(f"[http] {method} {path} -> {resp.status_code}", file=sys.stderr)
            if resp.status_code == 401:
                raise AuthRequiredError()
            if resp.status_code == 404:
                raise NotFoundError(f"Not found: {path}")
            if resp.status_code == 429:
                raise RateLimitedError("Rate limited by the API — slow down and retry later.")
            if resp.status_code >= 500:
                last_error = f"server error {resp.status_code}"
                continue
            if resp.status_code >= 400:
                raise ApiError(f"API error {resp.status_code}: {resp.text[:200]}")
            if resp.status_code == 204 or not resp.content:
                return None
            return resp.json()
        raise ApiError(f"Request failed after {self._retries + 1} attempts ({last_error}).")

    # -- read-only ---------------------------------------------------------

    def points_of_interest(
        self, *, lat: float, lng: float, radius_m: int, start: datetime, end: datetime
    ) -> list[Car]:
        data = self._request(
            "GET",
            "/pointsofinterest",
            params={
                "expand": "place.bookee.bookeeType",
                "lat": lat,
                "lng": lng,
                "range": radius_m,
                "start": iso_utc(start),
                "end": iso_utc(end),
                "sort": "distance",
            },
        )
        return cars_from_poi(data or [])

    def booking_proposals(
        self, *, lat: float, lng: float, radius_m: int, start: datetime, end: datetime
    ) -> list[Proposal]:
        data = self._request(
            "GET",
            "/bookingproposals",
            params={
                "expand": "bookeeId",
                "lat": lat,
                "lng": lng,
                "range": radius_m,
                "start": iso_utc(start),
                "end": iso_utc(end),
            },
        )
        return [Proposal.from_api(item) for item in data or []]

    def get_car(self, bookee_id: str) -> Car:
        data = self._request(
            "GET", f"/bookees/{bookee_id}", params={"expand": ["bookeeType", "place"]}
        )
        return Car.from_bookee(data)

    def unavailabilities(
        self, bookee_id: str, start: datetime, end: datetime
    ) -> list[Unavailability]:
        data = self._request(
            "GET",
            "/unavailabilities",
            params={"bookeeId": bookee_id, "start": iso_utc(start), "end": iso_utc(end)},
        )
        return [Unavailability.from_api(item) for item in data or []]

    def price(self, bookee_id: str, start: datetime, end: datetime) -> Price:
        data = self._request(
            "GET",
            "/prices",
            params={"bookeeId": bookee_id, "start": iso_utc(start), "end": iso_utc(end)},
        )
        if isinstance(data, list):
            data = data[0] if data else {}
        return Price.from_api(data or {})

    # -- member actions ------------------------------------------------------

    def login(self, login: str, credential: str, prov_id: str = PROV_ID) -> TokenInfo:
        data = self._request(
            "POST",
            "/tokens",
            json={
                "login": login,
                "credential": credential,
                "provId": prov_id,
                "storeLogin": True,
            },
        )
        return TokenInfo.from_api(data)

    def list_bookings(self) -> list[Booking]:
        data = self._request("GET", "/bookings")
        return [Booking.from_api(item) for item in data or []]

    def get_booking(self, booking_id: str) -> Booking:
        data = self._request("GET", f"/bookings/{booking_id}")
        return Booking.from_api(data)

    def create_booking(self, bookee_id: str, start: datetime, end: datetime) -> Booking:
        data = self._request(
            "POST",
            "/bookings",
            json={
                "bookeeId": bookee_id,
                "timeRange": {"start": iso_utc(start), "end": iso_utc(end)},
            },
        )
        return Booking.from_api(data)

    def cancel_booking(self, booking_id: str) -> None:
        self._request("DELETE", f"/bookings/{booking_id}")
