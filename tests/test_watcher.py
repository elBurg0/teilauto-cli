from __future__ import annotations

from itertools import islice

from teilauto.api.models import Car
from teilauto.services.availability import CarAvailability
from teilauto.services.watcher import watch


def _car(car_id: str, available: bool = True) -> CarAvailability:
    return CarAvailability(
        car=Car(
            id=car_id,
            name=f"Car {car_id}",
            plate=None,
            fuel=50,
            car_type="cityFlitzer",
            lat=None,
            lng=None,
            address=None,
        ),
        distance_m=100,
        available=available,
        free_from=None,
    )


def test_first_tick_reports_available_as_new():
    fetch_results = iter([[_car("1"), _car("2", available=False)]])
    ticks = list(islice(watch(lambda: next(fetch_results), interval=1, sleeper=lambda s: None), 1))
    assert ticks[0].nearby == 2
    assert ticks[0].available == 1
    assert [ca.car.id for ca in ticks[0].new] == ["1"]


def test_only_transitions_are_new():
    results = iter([[_car("1")], [_car("1"), _car("2")], [_car("1"), _car("2")]])
    gen = watch(lambda: next(results), interval=1, sleeper=lambda s: None)
    t1, t2, t3 = islice(gen, 3)
    assert [ca.car.id for ca in t1.new] == ["1"]
    assert [ca.car.id for ca in t2.new] == ["2"]
    assert t3.new == ()


def test_disappear_and_reappear_is_new_again():
    results = iter([[_car("1")], [], [_car("1")]])
    gen = watch(lambda: next(results), interval=1, sleeper=lambda s: None)
    t1, t2, t3 = islice(gen, 3)
    assert len(t1.new) == 1
    assert t2.new == ()
    assert len(t3.new) == 1


def test_backoff_doubles_and_resets():
    sleeps: list[float] = []
    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        if calls["n"] in (2, 3):
            raise RuntimeError("api down")
        return [_car("1")]

    gen = watch(fetch, interval=10, max_sleep=25, sleeper=sleeps.append)
    ticks = list(islice(gen, 6))
    assert ticks[1].error == "api down"
    assert ticks[2].error == "api down"
    assert ticks[3].error is None
    assert sleeps == [10, 20, 25, 10, 10]


def test_error_keeps_seen_set():
    results = iter([[_car("1")], RuntimeError("x"), [_car("1")]])

    def fetch():
        item = next(results)
        if isinstance(item, Exception):
            raise item
        return item

    gen = watch(fetch, interval=1, sleeper=lambda s: None)
    t1, t2, t3 = islice(gen, 3)
    assert len(t1.new) == 1
    assert t2.error == "x"
    assert t3.new == ()  # car "1" was already known before the outage
