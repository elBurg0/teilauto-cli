# Noridoc: services

Path: @/src/teilauto/services

### Overview

The business-logic layer: `availability.py` answers "which cars near a point are bookable for a window", `watcher.py` turns any such fetch into an endless transition-detecting poll loop, and @/src/teilauto/services/notify delivers push notifications. A hard layering rule applies here: **services never print** — they return data (or yield ticks / return error strings) and leave all terminal output to @/src/teilauto/cli.

### How it fits into the larger codebase

Sits between @/src/teilauto/api (whose `CantamenClient` and models it consumes) and @/src/teilauto/cli (which supplies the client, calls `find_cars`, and iterates `watch()` ticks). `cars list` calls `find_cars` once; `watch` and `autobook` wrap it in a closure and feed it to the `watch()` generator. Distance filtering uses `haversine_m` from @/src/teilauto/core/geo.py.

### Core Implementation

**availability.py** — `find_cars()` merges two API calls: `/pointsofinterest` (car metadata) and `/bookingproposals` (the availability oracle — a car is bookable iff it appears there, and the proposal's `timeRange.start` becomes `free_from`). It then filters by car type (default `cityFlitzer`), minimum fuel (unknown fuel counts as 0%), and *recomputed* haversine distance (cars beyond `radius_m` are dropped; the API's own distance field is untrusted). Result: `CarAvailability(car, distance_m, available, free_from)` sorted closest-first, with coordinate-less cars kept but sorted last (`distance_m=None`). `describe()` renders a one-line plain-text summary used in notifications and logs.

**watcher.py** — `watch(fetch, interval, max_sleep=1800, sleeper=time.sleep)` is a generator yielding one `WatchTick` per poll cycle, forever (the consumer `return`s/breaks to stop). Each tick carries counts, `new` (cars that *transitioned* into availability since the last successful poll — the first tick reports everything available as new), `retryable` (the full currently-available set, used by autobook's retry logic), and `error`. On a failed poll it yields an error tick and doubles the sleep (capped at `max_sleep`); on success the sleep resets to `interval`.

### Things to Know

- **Seen-set survives failed polls**: on an exception, `seen` is *not* cleared, so when the API recovers, cars that were already known-available are not re-reported as `new` — this prevents notification bursts after outages. `seen` is replaced with the current available set only on successful polls, so a car that disappears and reappears *is* reported again (intended: it became available again).
- The `sleeper` parameter exists for tests (@/tests/test_watcher.py injects a fake, so no test ever sleeps); `interval` is honored between every tick, including after a successful match check by the consumer.
- `WatchTick.retryable` looks redundant with `new` but is not: autobook uses it to retry cars whose booking POST failed on a previous tick (they are no longer "new" but still available). See @/src/teilauto/cli/autobook.py.
- State is in-memory only; a restarted watcher re-notifies everything (a documented non-goal to persist it).

Created and maintained by Nori.
