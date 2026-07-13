import pytest

import routes_algorithm as algo


def test_build_maps_link_single_stop_has_no_waypoints():
    origin = (-34.60, -58.38)
    stops = [{"lat": -34.61, "lng": -58.39}]
    link = algo.build_maps_link(origin, stops)
    assert link.startswith("https://www.google.com/maps/dir/?")
    assert "origin=-34.6%2C-58.38" in link
    assert "destination=-34.61%2C-58.39" in link
    assert "waypoints=" not in link


def test_build_maps_link_includes_waypoints_for_multiple_stops():
    origin = (-34.60, -58.38)
    stops = [
        {"lat": -34.601, "lng": -58.381},
        {"lat": -34.602, "lng": -58.382},
        {"lat": -34.603, "lng": -58.383},
    ]
    link = algo.build_maps_link(origin, stops)
    assert "destination=-34.603%2C-58.383" in link
    assert "waypoints=-34.601%2C-58.381%7C-34.602%2C-58.382" in link


def test_build_maps_link_rejects_empty_stops():
    with pytest.raises(ValueError):
        algo.build_maps_link((-34.6, -58.4), [])


def test_build_maps_link_rejects_more_than_nine_stops():
    stops = [{"lat": -34.6, "lng": -58.4} for _ in range(10)]
    with pytest.raises(ValueError):
        algo.build_maps_link((-34.6, -58.4), stops)


def test_build_maps_link_accepts_exactly_nine_stops():
    stops = [{"lat": -34.6 - i * 0.001, "lng": -58.4 - i * 0.001} for i in range(9)]
    link = algo.build_maps_link((-34.6, -58.4), stops)
    assert link.startswith("https://www.google.com/maps/dir/?")
