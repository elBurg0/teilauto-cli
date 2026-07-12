from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from teilauto.services.availability import CarAvailability


@dataclass(frozen=True)
class WatchTick:
    nearby: int
    available: int
    new: tuple[CarAvailability, ...]
    error: str | None = None


def watch(
    fetch: Callable[[], list[CarAvailability]],
    *,
    interval: float,
    max_sleep: float = 1800.0,
    sleeper: Callable[[float], None] = time.sleep,
) -> Iterator[WatchTick]:
    """Poll `fetch` forever, yielding a tick per cycle.

    `new` contains cars that transitioned into availability since the last
    successful poll (the first tick reports everything available as new).
    Failed polls yield an error tick, double the sleep (capped at max_sleep)
    and keep the previous seen-set so recovery does not re-notify.
    """
    seen: set[str] = set()
    sleep = interval
    while True:
        try:
            cars = fetch()
        except Exception as exc:
            yield WatchTick(nearby=0, available=0, new=(), error=str(exc))
            sleep = min(sleep * 2, max_sleep)
        else:
            available = [ca for ca in cars if ca.available]
            current = {ca.car.id for ca in available}
            new = tuple(ca for ca in available if ca.car.id not in seen)
            seen = current
            sleep = interval
            yield WatchTick(nearby=len(cars), available=len(available), new=new)
        sleeper(sleep)
