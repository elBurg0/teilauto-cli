from __future__ import annotations

from teilauto.core.geo import haversine_m


def test_zero_distance():
    assert haversine_m(51.34, 12.37, 51.34, 12.37) == 0.0


def test_known_distance_leipzig():
    # Leipzig Hbf -> Augustusplatz is roughly 1.0-1.3 km
    d = haversine_m(51.3455, 12.3821, 51.3387, 12.3818)
    assert 700 < d < 800


def test_symmetry():
    a = haversine_m(51.3, 12.3, 51.4, 12.5)
    b = haversine_m(51.4, 12.5, 51.3, 12.3)
    assert abs(a - b) < 1e-6
